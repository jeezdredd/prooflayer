import hashlib
import time
from datetime import timedelta
from typing import Any

import redis
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Max
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from analyzers.ensemble import ensemble_info
from analyzers.auto_retrain import LIVE
from analyzers.implementations.custom_detector import training_meta
from analyzers.models import RetrainRun, TrainingSample
from analyzers.roster import describe_drift, roster_drift
from api.models import Feedback
from common.throttling import PublicReadThrottle
from content.models import Submission
from users.models import EmailLog

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


def _probe_email() -> dict[str, Any]:
    configured = bool(getattr(settings, "EMAIL_CONFIGURED", False))
    backend = getattr(settings, "EMAIL_MODE", "resend" if configured else "console")
    out = {
        "backend": backend,
        "from_email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        "recent_failures": 0,
    }
    if not configured:
        out["status"] = "skip" if settings.DEBUG else "down"
        return out
    try:
        since = timezone.now() - timedelta(hours=24)
        recent = EmailLog.objects.filter(created_at__gte=since, status__in=["failed", "console"]).count()
    except Exception:
        recent = 0
    out["recent_failures"] = recent
    out["status"] = "down" if recent else "ok"
    return out


def _probe_analyzers() -> dict[str, Any]:
    try:
        report = roster_drift()
    except Exception as exc:
        return {"status": "down", "error": str(exc)[:120]}
    info = ensemble_info()
    out = {
        "status": "ok" if report["in_sync"] else "down",
        "active": report["active"],
        "expected": report["expected"],
        "drift": report["drift"],
        "ensemble": info["label"],
        "fingerprint": info["fingerprint"],
    }
    if not report["in_sync"]:
        out["error"] = f"roster drift - run seed_analyzers ({describe_drift(report)})"[:200]
    return out


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


FEEDBACK_DISCORD_COLORS = {
    "accuracy": 0xF97316,
    "ux": 0x6366F1,
    "performance": 0xEAB308,
    "feature_request": 0x22C55E,
    "bug": 0xEF4444,
    "other": 0x6B7280,
}


class FeedbackThrottle(UserRateThrottle):
    rate = "5/hour"


class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FeedbackThrottle]

    def post(self, request):
        category = request.data.get("category", "other")
        message = (request.data.get("message") or "").strip()
        contact_email = (request.data.get("contact_email") or "").strip()

        if not message or len(message) < 10:
            return Response({"detail": "Message too short."}, status=400)

        if category not in Feedback.Category.values:
            category = "other"

        fb = Feedback.objects.create(
            category=category,
            message=message[:4000],
            contact_email=contact_email[:254],
            user=request.user,
        )

        webhook = getattr(settings, "DISCORD_WEBHOOK_URL", "")
        if webhook:
            label = dict(Feedback.Category.choices).get(category, category)
            color = FEEDBACK_DISCORD_COLORS.get(category, 0x6B7280)
            embed = {
                "title": f"Feedback: {label}",
                "description": message[:2000],
                "color": color,
                "fields": [
                    {"name": "User", "value": str(request.user.email), "inline": True},
                    {"name": "Contact", "value": contact_email or "-", "inline": True},
                    {"name": "ID", "value": str(fb.id)[:8], "inline": True},
                ],
            }
            try:
                requests.post(webhook, json={"username": "ProofLayer Feedback", "embeds": [embed]}, timeout=4)
            except Exception:
                pass

        return Response({"detail": "Feedback received. Thank you.", "id": str(fb.id)}, status=201)


def _last_retrain() -> dict | None:
    try:
        from analyzers.models import RetrainRun
        run = RetrainRun.objects.filter(status=RetrainRun.Status.SUCCESS).order_by("-finished_at").first()
        if run is None:
            return None
        return {
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "status": run.status,
            "samples_used": run.samples_used,
            "hf_revision": run.hf_revision or None,
            "media_type": run.media_type,
        }
    except Exception:
        return None


RETRAIN_WEEKDAY = 6
RETRAIN_HOUR_UTC = 3


def _next_weekly_run(now):
    days_ahead = (RETRAIN_WEEKDAY - now.weekday()) % 7
    candidate = (now + timedelta(days=days_ahead)).replace(hour=RETRAIN_HOUR_UTC, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _run_dict(run) -> dict | None:
    if run is None:
        return None
    return {
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "samples_used": run.samples_used,
        "error": run.error or "",
        "metrics": {k: run.metrics.get(k) for k in ("live", "candidate", "fetched", "db_samples")} if run.metrics else {},
    }


def _training_queue(media_type: str = "image") -> dict:
    now = timezone.now()
    runs = RetrainRun.objects.filter(media_type=media_type)
    last_success = runs.filter(status=RetrainRun.Status.SUCCESS).order_by("-finished_at").first()
    since = last_success.finished_at if last_success and last_success.finished_at else now - timedelta(days=365)
    return {
        "media_type": media_type,
        "new_samples": TrainingSample.objects.filter(media_type=media_type, created_at__gte=since).count(),
        "needed": getattr(settings, "RETRAIN_MIN_NEW_SAMPLES", 50),
        "last_success": _run_dict(last_success),
        "live_model_trained_at": training_meta(str(LIVE)).get("trained_at"),
        "last_attempt": _run_dict(runs.order_by("-started_at").first()),
        "next_run": _next_weekly_run(now).isoformat(),
    }


TIMING_CACHE_KEY = "status:verdict_timing"
STATUS_CACHE_KEY = "status:payload"
STATUS_CACHE_SECONDS = 10
TIMING_MIN_SAMPLES = 20


def _verdict_timing() -> dict[str, Any]:
    cached = cache.get(TIMING_CACHE_KEY)
    if cached is not None:
        return cached
    since = timezone.now() - timedelta(days=14)
    rows = (
        Submission.objects.filter(status=Submission.Status.COMPLETED, mime_type__startswith="image/", created_at__gte=since)
        .annotate(done=Max("analysis_results__created_at"))
        .exclude(done=None)
        .order_by("-created_at")
        .values_list("created_at", "done")[:300]
    )
    durations = sorted((done - created).total_seconds() for created, done in rows if done >= created)
    result = {"samples": len(durations), "image_median_s": None, "window_days": 14}
    if len(durations) >= TIMING_MIN_SAMPLES:
        mid = len(durations) // 2
        median = durations[mid] if len(durations) % 2 else (durations[mid - 1] + durations[mid]) / 2
        result["image_median_s"] = round(median, 1)
    cache.set(TIMING_CACHE_KEY, result, 600)
    return result


class SystemStatusView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PublicReadThrottle]

    def get(self, request):
        cached = cache.get(STATUS_CACHE_KEY)
        if cached is not None:
            return Response(cached)
        services = {
            "api": {"status": "ok"},
            "database": _probe_db(),
            "redis": _probe_redis(),
            "celery": _probe_celery(),
            "ollama": _probe_ollama(),
            "storage": _probe_storage(),
            "email": _probe_email(),
            "analyzers": _probe_analyzers(),
        }
        all_ok = all(s.get("status") in ("ok", "skip") for s in services.values())
        payload = {
            "overall": "operational" if all_ok else "degraded",
            "checked_at": time.time(),
            "services": services,
            "last_retrain": _last_retrain(),
            "training": _training_queue("image"),
            "verdict_timing": _verdict_timing(),
        }
        cache.set(STATUS_CACHE_KEY, payload, STATUS_CACHE_SECONDS)
        return Response(payload)
