from unittest.mock import patch

import pytest
from django.test import override_settings

from analyzers.models import RetrainRun
from analyzers.tasks import _email_retrain
from users.models import EmailLog
from users.tests.factories import UserFactory


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_retrain_email_logs():
    user = UserFactory()
    run = RetrainRun.objects.create(media_type="image", status="success", triggered_by=user)
    _email_retrain(run)
    assert EmailLog.objects.filter(kind="retrain").count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True)
def test_retrain_email_failure_swallowed():
    user = UserFactory()
    run = RetrainRun.objects.create(media_type="image", status="success", triggered_by=user)
    with patch("analyzers.tasks.deliver", side_effect=RuntimeError("boom")):
        _email_retrain(run)
