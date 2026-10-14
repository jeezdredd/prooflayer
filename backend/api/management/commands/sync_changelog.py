from django.core.management.base import BaseCommand

from api.changelog import sync


class Command(BaseCommand):
    help = "Load api/changelog.json into ChangelogEntry rows (insert new, update existing by slug)"

    def handle(self, *args, **options):
        created, updated = sync()
        self.stdout.write(f"changelog: {created} new, {updated} updated")
