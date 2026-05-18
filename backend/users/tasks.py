import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .models import EmailVerificationToken

logger = logging.getLogger(__name__)
User = get_user_model()


SUBJECT = "Verify your ProofLayer email"
BODY_TEMPLATE = """Hi {username},

Confirm your ProofLayer account by opening the link below:

{link}

The link expires in 48 hours. If you did not sign up, ignore this email.

- ProofLayer
"""


@shared_task(queue="default", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_verification_email(user_id: int) -> str:
    user = User.objects.get(pk=user_id)
    if user.is_verified:
        return "already_verified"
    token = EmailVerificationToken.objects.create(user=user)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token.token}"
    body = BODY_TEMPLATE.format(username=user.username or user.email, link=link)
    send_mail(
        subject=SUBJECT,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info("verification email sent user=%s", user_id)
    return "sent"
