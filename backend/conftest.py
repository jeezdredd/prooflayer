import io
import pytest
from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from config.celery import app as celery_app
from users.tests.factories import UserFactory


@pytest.fixture(scope="session", autouse=True)
def _celery_eager():
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        result_backend="cache+memory://",
        broker_url="memory://",
    )


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Throttle and quota counters live in the shared Redis cache; without this
    they leak across tests and later requests get spurious 429s."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    user = UserFactory()
    api_client.force_authenticate(user=user)
    api_client.user = user
    return api_client


@pytest.fixture
def sample_jpeg():
    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile("test.jpg", buffer.read(), content_type="image/jpeg")


@pytest.fixture
def sample_png():
    img = Image.new("RGB", (100, 100), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile("test.png", buffer.read(), content_type="image/png")
