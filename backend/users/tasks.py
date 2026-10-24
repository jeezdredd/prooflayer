import logging
import time

import requests

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.url_safety import UnsafeUrlError, safe_post
from content.models import Submission, VerdictObjection
from content.viewer import result_url

from . import mail
from .models import ApiKey, EmailVerificationToken, ProductUpdate, ProductUpdateDelivery
from .webhooks import build_payload, encode

logger = logging.getLogger(__name__)
User = get_user_model()

UPDATE_SEND_INTERVAL = 0.6


@shared_task(queue="default", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_verification_email(user_id: int) -> str:
    user = User.objects.get(pk=user_id)
    if user.is_verified:
        return "already_verified"
    token = (
        EmailVerificationToken.objects.filter(
            user=user, used_at__isnull=True, expires_at__gt=timezone.now()
        )
        .order_by("-created_at")
        .first()
    )
    if token is None:
        token = EmailVerificationToken.objects.create(user=user)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token.token}"
    status = mail.send(kind="verification", to=[user.email], context=mail.verification_context(user, link), user=user)
    logger.info("verification email %s user=%s", status, user_id)
    return status


@shared_task(queue="default", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_password_reset_email(user_id: int) -> str:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return "missing"
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    status = mail.send(kind="password_reset", to=[user.email], context=mail.password_reset_context(user, link), user=user)
    logger.info("password reset email %s user=%s", status, user_id)
    return status


def _objection_recipients(objection):
    classroom = objection.submission.classroom
    if classroom is not None:
        owner = classroom.owner
        return [(owner.email, mail.lang_of(owner), owner)] if owner.email else []
    return [(email, "en", None) for _name, email in getattr(settings, "ADMINS", []) if email]


@shared_task(queue="default", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_objection_notice(objection_id) -> str:
    objection = (
        VerdictObjection.objects.select_related("submission__classroom__owner", "author")
        .filter(id=objection_id)
        .first()
    )
    if objection is None:
        return "missing"
    recipients = _objection_recipients(objection)
    if not recipients:
        logger.info("objection notice skipped objection=%s (no recipient)", objection_id)
        return "skipped"
    classroom = objection.submission.classroom
    due_at = timezone.localtime(objection.due_at)
    statuses = []
    for email, lang, recipient in recipients:
        context = mail.objection_context(
            lang=lang,
            student=objection.author.username or objection.author.email,
            title=objection.submission.original_filename,
            classroom=classroom.name if classroom else "",
            reason=objection.reason,
            due=due_at.strftime("%d.%m.%Y %H:%M") if lang == "ru" else due_at.strftime("%b %d, %Y %H:%M"),
            link=result_url(objection.submission),
        )
        statuses.append(mail.send(kind="objection", to=[email], context=context, user=recipient))
    logger.info("objection notice %s objection=%s", statuses, objection_id)
    return statuses[0] if len(set(statuses)) == 1 else "mixed"


def send_product_update_to(update, user) -> str:
    return mail.send(
        kind="update",
        to=[user.email],
        context=mail.update_context(update, user),
        user=user,
        headers=mail.unsubscribe_headers(user),
    )


def update_audience(update):
    return (
        User.objects.filter(is_active=True, is_verified=True, email_updates=True)
        .exclude(email="")
        .exclude(update_deliveries__update=update)
        .order_by("pk")
    )


@shared_task(queue="default", soft_time_limit=60 * 60 * 3)
def send_product_update(update_id: int) -> int:
    update = ProductUpdate.objects.filter(pk=update_id).first()
    if update is None or update.status == ProductUpdate.Status.SENT:
        return 0
    if update.status != ProductUpdate.Status.SENDING:
        update.status = ProductUpdate.Status.SENDING
        update.save(update_fields=["status"])
    sent = 0
    for user in update_audience(update).iterator():
        try:
            send_product_update_to(update, user)
        except Exception as exc:
            logger.warning("product update %s to user=%s failed: %s", update_id, user.pk, exc)
            continue
        ProductUpdateDelivery.objects.get_or_create(update=update, user=user)
        sent += 1
        time.sleep(UPDATE_SEND_INTERVAL)
    update.status = ProductUpdate.Status.SENT
    update.sent_at = timezone.now()
    update.recipients = update.deliveries.count()
    update.save(update_fields=["status", "sent_at", "recipients"])
    logger.info("product update %s sent to %s users", update_id, sent)
    return sent


WEBHOOK_TIMEOUT = 10
WEBHOOK_RETRYABLE_STATUS = 500


class WebhookRetryable(Exception):
    pass


@shared_task(
    queue="default",
    autoretry_for=(WebhookRetryable, requests.RequestException),
    retry_backoff=30,
    retry_backoff_max=600,
    max_retries=3,
)
def deliver_submission_webhook(submission_id):
    submission = Submission.objects.select_related("api_key").filter(id=submission_id).first()
    key = submission.api_key if submission else None
    if key is None or not key.is_active or not key.webhook_url or not key.webhook_secret:
        return "skipped"
    body, headers = encode(build_payload(submission), key.webhook_secret)
    try:
        response = safe_post(key.webhook_url, data=body, headers=headers, timeout=WEBHOOK_TIMEOUT)
    except UnsafeUrlError:
        _record(key, "blocked_url")
        return "blocked_url"
    except requests.RequestException:
        _record(key, "network_error")
        raise
    _record(key, str(response.status_code))
    if response.status_code >= WEBHOOK_RETRYABLE_STATUS:
        raise WebhookRetryable(f"receiver returned {response.status_code}")
    return str(response.status_code)


def _record(key, status_text):
    ApiKey.objects.filter(pk=key.pk).update(last_webhook_at=timezone.now(), last_webhook_status=status_text[:40])
