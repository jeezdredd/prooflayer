import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from analyzers import auto_retrain
from analyzers.models import RetrainRun
from analyzers.retrain_report import holdout_summary
from analyzers.tests.factories import AnalyzerConfigFactory
from users.tests.factories import UserFactory

RUN_URL = "admin:analyzers_retrainrun_run_retrain_now"
ROLLBACK_URL = "admin:analyzers_retrainrun_rollback_detector"


@pytest.fixture
def layout(tmp_path, monkeypatch):
    paths = {
        "LIVE": tmp_path / "image",
        "CANDIDATE": tmp_path / "image.candidate",
        "PREVIOUS": tmp_path / "image.previous",
        "POOL": tmp_path / "auto" / "pool",
        "CALIBRATION": tmp_path / "auto" / "calibration",
        "HOLDOUT": tmp_path / "auto" / "holdout",
    }
    for name, value in paths.items():
        monkeypatch.setattr(auto_retrain, name, value)
    return paths


@pytest.fixture
def superuser_client(client):
    user = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(user)
    client.user = user
    return client


@pytest.fixture
def staff_client():
    client = Client()
    client.force_login(UserFactory(is_staff=True))
    return client


def _model(path, tag):
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(json.dumps({"tag": tag}))


def _messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


@pytest.mark.django_db
class TestRunRetrainAction:
    def test_get_shows_confirmation_without_queueing(self, superuser_client, layout):
        with patch("analyzers.admin.run_weekly_retrain.delay") as delay:
            response = superuser_client.get(reverse(RUN_URL))
        assert response.status_code == 200
        assert b"Queue retrain" in response.content
        delay.assert_not_called()

    def test_superuser_post_queues_task(self, superuser_client, layout):
        with patch("analyzers.admin.run_weekly_retrain.delay") as delay:
            response = superuser_client.post(reverse(RUN_URL))
        assert response.status_code == 302
        assert response.url == reverse("admin:analyzers_retrainrun_changelist")
        delay.assert_called_once_with("image", triggered_by_id=superuser_client.user.id)

    def test_non_superuser_is_blocked(self, staff_client, layout):
        with patch("analyzers.admin.run_weekly_retrain.delay") as delay:
            response = staff_client.post(reverse(RUN_URL))
        assert response.status_code == 403
        delay.assert_not_called()

    def test_running_retrain_blocks_a_second_one(self, superuser_client, layout):
        RetrainRun.objects.create(status=RetrainRun.Status.STARTED)
        with patch("analyzers.admin.run_weekly_retrain.delay") as delay:
            response = superuser_client.post(reverse(RUN_URL))
        assert response.status_code == 302
        delay.assert_not_called()
        assert any("already running" in m for m in _messages(response))


@pytest.mark.django_db
class TestRollbackAction:
    def test_without_previous_model_shows_error(self, superuser_client, layout):
        _model(layout["LIVE"], "live")
        response = superuser_client.post(reverse(ROLLBACK_URL))
        assert response.status_code == 302
        assert any("Rollback failed" in m and "no previous model" in m for m in _messages(response))
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "live"

    def test_swaps_live_and_previous(self, superuser_client, layout):
        _model(layout["LIVE"], "new")
        _model(layout["PREVIOUS"], "old")
        response = superuser_client.post(reverse(ROLLBACK_URL))
        assert response.status_code == 302
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "old"
        assert json.loads((layout["PREVIOUS"] / "config.json").read_text())["tag"] == "new"
        assert any("rolled back" in m for m in _messages(response))

    def test_non_superuser_is_blocked(self, staff_client, layout):
        _model(layout["LIVE"], "new")
        _model(layout["PREVIOUS"], "old")
        response = staff_client.post(reverse(ROLLBACK_URL))
        assert response.status_code == 403
        assert json.loads((layout["LIVE"] / "config.json").read_text())["tag"] == "new"


@pytest.mark.django_db
class TestRetrainRunPages:
    def test_changelist_and_detail_render(self, superuser_client, layout):
        run = RetrainRun.objects.create(
            status=RetrainRun.Status.REJECTED,
            error="candidate catches fewer AI images",
            metrics={
                "live": {"ai_caught": 10, "real_fake": 0},
                "candidate": {"ai_caught": 9, "real_fake": 0},
                "knots": [[0.2, 0.1], [0.9, 0.5]],
                "problems": ["candidate catches fewer AI images"],
            },
        )
        changelist = superuser_client.get(reverse("admin:analyzers_retrainrun_changelist"))
        assert changelist.status_code == 200
        assert b"Run retrain now" in changelist.content
        assert b"Roll back image detector" in changelist.content
        detail = superuser_client.get(reverse("admin:analyzers_retrainrun_change", args=[run.id]))
        assert detail.status_code == 200
        assert b"Candidate" in detail.content

    def test_staff_does_not_see_superuser_actions(self, layout):
        user = UserFactory(is_staff=True)
        view = Permission.objects.get(content_type__app_label="analyzers", codename="view_retrainrun")
        user.user_permissions.add(view)
        client = Client()
        client.force_login(user)
        response = client.get(reverse("admin:analyzers_retrainrun_changelist"))
        assert response.status_code == 200
        assert b"Run retrain now" not in response.content

    def test_holdout_summary(self):
        metrics = {"live": {"ai_caught": 10, "real_fake": 0}, "candidate": {"ai_caught": 12, "real_fake": 1}}
        assert holdout_summary(metrics) == "AI caught 10 → 12, Real called AI 0 → 1"
        assert holdout_summary({}) == ""


@pytest.mark.django_db
class TestAnalyzerConfigAdmin:
    def test_list_is_editable_and_marks_drift(self, superuser_client):
        AnalyzerConfigFactory(name="not_in_code_analyzer")
        response = superuser_client.get(reverse("admin:analyzers_analyzerconfig_changelist"))
        assert response.status_code == 200
        assert b"form-0-weight" in response.content
        assert b"not in code" in response.content
        assert b"roster drift" in response.content

    def test_sync_roster_requires_post_and_superuser(self, superuser_client, staff_client):
        url = reverse("admin:analyzers_analyzerconfig_sync_roster")
        with patch("analyzers.admin.call_command") as command:
            assert superuser_client.get(url).status_code == 200
            command.assert_not_called()
            assert superuser_client.post(url).status_code == 302
            command.assert_called_once()
            assert staff_client.post(url).status_code == 403
            command.assert_called_once()
