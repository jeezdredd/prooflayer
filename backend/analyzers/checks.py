from django.core.checks import Tags, Warning, register
from django.db import DatabaseError, ProgrammingError

from analyzers.roster import describe_drift, roster_drift


@register(Tags.database)
def analyzer_roster_check(app_configs, **kwargs):
    try:
        report = roster_drift()
    except (DatabaseError, ProgrammingError):
        return []
    if report["in_sync"]:
        return []
    return [
        Warning(
            "AnalyzerConfig rows drift from seed_analyzers.ANALYZERS "
            f"({describe_drift(report)}). Run `manage.py seed_analyzers` on the backend.",
            id="analyzers.W001",
        )
    ]
