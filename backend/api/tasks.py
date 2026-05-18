import logging

import requests
from celery import shared_task
from django.conf import settings

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
