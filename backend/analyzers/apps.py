from django.apps import AppConfig


class AnalyzersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analyzers"

    def ready(self):
        from . import checks  # noqa: F401
