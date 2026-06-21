import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .emails import deliver
from .models import EmailVerificationToken

logger = logging.getLogger(__name__)
User = get_user_model()

SUBJECT = "Verify your ProofLayer account"

_TEXT_TEMPLATE = """Hi {username},

Confirm your ProofLayer account by opening the link below:

{link}

The link expires in 48 hours. If you did not sign up, ignore this email.

- ProofLayer
"""

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Verify your ProofLayer account</title>
</head>
<body style="margin:0;padding:0;background:#09090b;font-family:'Courier New',Courier,monospace;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#09090b;padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

          <!-- LOGO -->
          <tr>
            <td style="padding-bottom:32px;">
              <span style="font-family:Georgia,serif;font-size:28px;font-weight:bold;color:#f4f4f5;letter-spacing:-0.5px;">
                Proof<span style="font-style:italic;color:#7c6af7;">Layer</span>
              </span>
            </td>
          </tr>

          <!-- CARD -->
          <tr>
            <td style="background:#111113;border:1px solid rgba(255,255,255,0.07);border-radius:4px;padding:40px 40px 36px;">

              <!-- BADGE -->
              <div style="margin-bottom:24px;">
                <span style="display:inline-block;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:#52525b;border:1px solid rgba(255,255,255,0.06);padding:4px 10px;border-radius:2px;">
                  Account Verification
                </span>
              </div>

              <!-- HEADING -->
              <h1 style="margin:0 0 12px;font-family:Georgia,serif;font-size:22px;color:#f4f4f5;font-weight:normal;line-height:1.3;">
                Confirm your email address
              </h1>
              <p style="margin:0 0 28px;font-size:13px;color:#71717a;line-height:1.6;">
                Hi <strong style="color:#a1a1aa;">{username}</strong>, click the button below to verify your ProofLayer account. This link expires in <strong style="color:#a1a1aa;">48 hours</strong>.
              </p>

              <!-- CTA BUTTON -->
              <table cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
                <tr>
                  <td style="background:#7c6af7;border-radius:3px;">
                    <a href="{link}" style="display:inline-block;padding:14px 32px;font-family:'Courier New',Courier,monospace;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:#ffffff;text-decoration:none;font-weight:bold;">
                      Verify Email &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <!-- FALLBACK LINK -->
              <p style="margin:0 0 4px;font-size:11px;color:#52525b;letter-spacing:0.05em;text-transform:uppercase;">
                Or copy this link:
              </p>
              <p style="margin:0;font-size:11px;color:#71717a;word-break:break-all;line-height:1.5;">
                <a href="{link}" style="color:#7c6af7;text-decoration:none;">{link}</a>
              </p>

            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="padding-top:24px;">
              <p style="margin:0;font-size:10px;color:#3f3f46;letter-spacing:0.08em;line-height:1.6;">
                If you did not sign up for ProofLayer, ignore this email.<br />
                &copy; 2025 ProofLayer &mdash;
                <a href="https://prooflayer.cloud/privacy" style="color:#52525b;text-decoration:none;">Privacy</a> &middot;
                <a href="https://prooflayer.cloud/terms" style="color:#52525b;text-decoration:none;">Terms</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


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
    username = user.username or user.email

    text_body = _TEXT_TEMPLATE.format(username=username, link=link)
    html_body = _HTML_TEMPLATE.format(username=username, link=link)

    msg = EmailMultiAlternatives(
        subject=SUBJECT,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    status = deliver(msg, kind="verification", user=user)

    logger.info("verification email %s user=%s", status, user_id)
    return status
