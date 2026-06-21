from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from users.emails import deliver


class Command(BaseCommand):
    help = "Send a test email through the configured backend and log it"

    def add_arguments(self, parser):
        parser.add_argument("to")

    def handle(self, *args, **options):
        msg = EmailMultiAlternatives(
            subject="ProofLayer email test",
            body="This is a test email from manage.py send_test_email.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[options["to"]],
        )
        status = deliver(msg, kind="test")
        self.stdout.write(self.style.SUCCESS(f"delivered: {status} -> {options['to']}"))
