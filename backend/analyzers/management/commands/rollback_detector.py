from django.core.management.base import BaseCommand, CommandError

from analyzers import auto_retrain


class Command(BaseCommand):
    help = "Swap the live image detector with the previous one kept by the last automatic retrain"

    def handle(self, *args, **options):
        try:
            auto_retrain.rollback()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"live model is now the previous one: {auto_retrain.LIVE}"))
