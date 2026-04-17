import os

from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("prooflayer")
app.config_from_object("django.conf:settings", namespace="CELERY")

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
    "analyzers.tasks.run_analyzer": {"queue": "default"},
    "analyzers.tasks.run_ml_analyzer": {"queue": "ml"},
    "analyzers.tasks.aggregate_verdicts": {"queue": "default"},
}

app.autodiscover_tasks()
