import gzip
import io
import logging
import os
import subprocess
from datetime import timedelta
from urllib.parse import urlparse

import boto3
import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

GEO_URL = "http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,isp,org,query,proxy,hosting"


def _geo_lookup(ip: str) -> dict:
    try:
        r = requests.get(GEO_URL.format(ip=ip), timeout=4)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "success":
            return data
    except Exception as exc:
        logger.warning("geo lookup failed: %s", exc)
    return {}


def _short_ua(ua: str) -> str:
    if not ua:
        return "?"
    for marker in ["Firefox/", "Chrome/", "Safari/", "Edg/", "OPR/"]:
        if marker in ua:
            tail = ua.split(marker)[1].split(" ")[0]
            base = marker.rstrip("/")
            os_hint = ""
            for os_marker in ["Windows", "Mac OS", "Linux", "Android", "iPhone", "iPad"]:
                if os_marker in ua:
                    os_hint = os_marker
                    break
            return f"{base} {tail}" + (f" / {os_hint}" if os_hint else "")
    return ua[:60]


VERDICT_COLOR = 0x5865F2  # discord blurple


@shared_task(queue="default", autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def notify_visit(ip: str, path: str, referrer: str, user_agent: str) -> str:
    webhook = getattr(settings, "DISCORD_WEBHOOK_URL", "")
    if not webhook:
        return "disabled"

    geo = _geo_lookup(ip)
    loc_parts = [geo.get("city"), geo.get("regionName"), geo.get("country")]
    loc = ", ".join([p for p in loc_parts if p]) or "unknown"
    cc = geo.get("countryCode", "")
    isp = geo.get("isp") or geo.get("org") or "?"
    flags = []
    if geo.get("proxy"):
        flags.append("proxy")
    if geo.get("hosting"):
        flags.append("hosting/vpn")
    flag_str = " " + " ".join(f"`{f}`" for f in flags) if flags else ""

    embed = {
        "title": f"🌍 New visit{' · ' + cc if cc else ''}",
        "color": VERDICT_COLOR,
        "fields": [
            {"name": "IP", "value": f"`{ip}`{flag_str}", "inline": True},
            {"name": "Location", "value": loc, "inline": True},
            {"name": "ISP", "value": isp[:80], "inline": False},
            {"name": "Path", "value": f"`{path}`", "inline": True},
            {"name": "Referrer", "value": referrer or "direct", "inline": True},
            {"name": "User Agent", "value": _short_ua(user_agent), "inline": False},
        ],
    }
    payload = {"username": "ProofLayer", "embeds": [embed]}

    try:
        r = requests.post(webhook, json=payload, timeout=5)
        r.raise_for_status()
        return "sent"
    except Exception as exc:
        logger.warning("discord webhook failed: %s", exc)
        raise


BACKUP_BUCKET = "prooflayer-backups"
BACKUP_RETENTION_DAYS = 14


def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
        region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
        config=boto3.session.Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
        except Exception as exc:
            logger.warning("create_bucket %s failed: %s", bucket, exc)


@shared_task(queue="default", soft_time_limit=600, time_limit=900)
def backup_postgres() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return "no_db_url"
    parsed = urlparse(db_url)
    env = dict(os.environ)
    env["PGPASSWORD"] = parsed.password or ""
    cmd = [
        "pg_dump", "--no-owner", "--no-acl", "--format=plain",
        "-h", parsed.hostname or "db",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "prooflayer",
        parsed.path.lstrip("/"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=600)
    except FileNotFoundError:
        logger.error("pg_dump binary missing in worker image")
        return "no_pg_dump"
    if proc.returncode != 0:
        logger.error("pg_dump failed rc=%s err=%s", proc.returncode, proc.stderr[:500])
        return "dump_failed"

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(proc.stdout)
    buf.seek(0)

    ts = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    key = f"daily/prooflayer-{ts}.sql.gz"
    client = _s3_client()
    _ensure_bucket(client, BACKUP_BUCKET)
    client.put_object(Bucket=BACKUP_BUCKET, Key=key, Body=buf.read(), ContentType="application/gzip")

    cutoff = timezone.now() - timedelta(days=BACKUP_RETENTION_DAYS)
    try:
        listed = client.list_objects_v2(Bucket=BACKUP_BUCKET, Prefix="daily/").get("Contents", [])
        for obj in listed:
            if obj["LastModified"] < cutoff:
                client.delete_object(Bucket=BACKUP_BUCKET, Key=obj["Key"])
    except Exception as exc:
        logger.warning("retention sweep failed: %s", exc)

    logger.info("postgres backup uploaded: %s (%d bytes)", key, len(proc.stdout))
    return key
