import hashlib
import time
from typing import Any

import redis
import requests
from django.conf import settings
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

PROBE_TIMEOUT = 2.0


def _probe_db() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            row = cur.fetchone()
            pgvector = row[0] if row else None
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "pgvector": pgvector or "missing",
        }
    except Exception as exc:
        return {"status": "down", "error": str(exc)[:120]}


def _probe_redis() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        url = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
        client = redis.from_url(url, socket_connect_timeout=PROBE_TIMEOUT, socket_timeout=PROBE_TIMEOUT)
        client.ping()
        info = client.info(section="server")
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "version": info.get("redis_version"),
        }
    except Exception as exc:
        return {"status": "down", "error": str(exc)[:120]}


def _probe_celery() -> dict[str, Any]:
    try:
        from config.celery import app as celery_app

        i = celery_app.control.inspect(timeout=PROBE_TIMEOUT)
        active = i.active() or {}
        scheduled = i.scheduled() or {}
        stats = i.stats() or {}
        workers = list(stats.keys())
        active_count = sum(len(v) for v in active.values())
        scheduled_count = sum(len(v) for v in scheduled.values())
        return {
            "status": "ok" if workers else "down",
            "workers": len(workers),
            "worker_names": workers,
            "active_tasks": active_count,
            "scheduled_tasks": scheduled_count,
        }
    except Exception as exc:
        return {"status": "down", "error": str(exc)[:120]}


def _probe_ollama() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        url = getattr(settings, "OLLAMA_URL", "http://ollama:11434")
        r = requests.get(f"{url}/api/tags", timeout=PROBE_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        models = [m.get("name") for m in data.get("models", [])]
        ps = requests.get(f"{url}/api/ps", timeout=PROBE_TIMEOUT)
        loaded = []
        if ps.ok:
            loaded = [m.get("name") for m in ps.json().get("models", [])]
        return {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "available_models": models,
            "loaded_models": loaded,
        }
    except Exception as exc:
        return {"status": "down", "error": str(exc)[:120]}


def _probe_storage() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        if not endpoint:
            return {"status": "skip", "reason": "no s3 endpoint configured"}
        r = requests.get(f"{endpoint}/minio/health/live", timeout=PROBE_TIMEOUT)
        ok = r.status_code in (200, 204)
        return {
            "status": "ok" if ok else "down",
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "endpoint": endpoint,
        }
    except Exception as exc:
        return {"status": "down", "error": str(exc)[:120]}


def _client_ip(request) -> str:
    cf = request.META.get("HTTP_CF_CONNECTING_IP", "")
    if cf:
        return cf.strip()
    real = request.META.get("HTTP_X_REAL_IP", "")
    if real:
        return real.strip()
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class VisitThrottle(AnonRateThrottle):
    rate = "30/min"


class RecordVisitView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [VisitThrottle]

    def post(self, request):
        if not getattr(settings, "DISCORD_WEBHOOK_URL", ""):
            return Response({"detail": "tracking disabled"}, status=204)

        ip = _client_ip(request)
        if not ip:
            return Response({"detail": "no ip"}, status=204)

        path = (request.data.get("path") or "/")[:200]
        referrer = (request.data.get("referrer") or "")[:300]
        ua = request.META.get("HTTP_USER_AGENT", "")[:300]

        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        dedupe_key = f"visit:{ip_hash}:{path}"
        try:
            url = getattr(settings, "REDIS_URL", "redis://redis:6379/0")
            r = redis.from_url(url, socket_connect_timeout=1.0, socket_timeout=1.0)
            if not r.set(dedupe_key, "1", nx=True, ex=3600):
                return Response({"detail": "deduped"}, status=204)
        except Exception:
            pass

        from api.tasks import notify_visit
        notify_visit.delay(ip=ip, path=path, referrer=referrer, user_agent=ua)
        return Response({"detail": "queued"}, status=202)


class SystemStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        services = {
            "api": {"status": "ok"},
            "database": _probe_db(),
            "redis": _probe_redis(),
            "celery": _probe_celery(),
            "ollama": _probe_ollama(),
            "storage": _probe_storage(),
        }
        all_ok = all(s.get("status") in ("ok", "skip") for s in services.values())
        return Response({
            "overall": "operational" if all_ok else "degraded",
            "checked_at": time.time(),
            "services": services,
        })
