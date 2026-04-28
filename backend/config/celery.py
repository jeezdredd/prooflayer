import os

from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("prooflayer")

app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
)

default_exchange = Exchange("default", type="direct")
ml_exchange = Exchange("ml", type="direct")
reports_exchange = Exchange("reports", type="direct")

app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("ml", ml_exchange, routing_key="ml"),
    Queue("reports", reports_exchange, routing_key="reports"),
)
app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

app.conf.task_routes = {
    "content.tasks.*": {"queue": "default"},
    "analyzers.tasks.aggregate_verdicts": {"queue": "default"},
}

app.autodiscover_tasks(lambda: ["content", "analyzers", "provenance", "users", "crowdsource", "reports"])
