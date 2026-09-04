import pytest
from django.core.management import call_command

from analyzers.checks import analyzer_roster_check
from analyzers.models import AnalyzerConfig
from analyzers.roster import describe_drift, expected_roster, roster_drift


@pytest.mark.django_db
class TestRosterDrift:
    def test_fresh_seed_is_in_sync(self):
        call_command("seed_analyzers", verbosity=0)
        report = roster_drift()
        assert report["in_sync"] is True
        assert report["active"] == report["expected"] == len(expected_roster())
        assert not any(report["drift"].values())

    def test_empty_db_reports_everything_missing(self):
        report = roster_drift()
        assert report["in_sync"] is False
        assert report["drift"]["missing"] == sorted(expected_roster())
        assert report["active"] == 0

    def test_weight_change_in_db_is_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="community_forensics").update(weight=1.0)
        report = roster_drift()
        assert report["drift"]["weight_mismatch"] == ["community_forensics"]
        assert report["in_sync"] is False

    def test_stale_active_row_is_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.create(
            name="npr_detector",
            analyzer_class="analyzers.implementations.npr_detector.NPRDetector",
            version="2.0.0",
            is_active=True,
        )
        report = roster_drift()
        assert report["drift"]["stale_active"] == ["npr_detector"]

    def test_stale_inactive_row_is_not_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.create(
            name="npr_detector",
            analyzer_class="analyzers.implementations.npr_detector.NPRDetector",
            version="2.0.0",
            is_active=False,
        )
        assert roster_drift()["in_sync"] is True

    def test_deactivated_expected_row_is_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="ai_detector").update(is_active=False)
        report = roster_drift()
        assert report["drift"]["inactive_expected"] == ["ai_detector"]

    def test_class_path_change_is_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="ai_detector").update(
            analyzer_class="analyzers.implementations.npr_detector.NPRDetector"
        )
        report = roster_drift()
        assert report["drift"]["class_mismatch"] == ["ai_detector"]

    def test_reseed_repairs_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="community_forensics").update(weight=0.1, is_active=False)
        assert roster_drift()["in_sync"] is False
        call_command("seed_analyzers", verbosity=0)
        assert roster_drift()["in_sync"] is True

    def test_describe_drift_names_each_bucket(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="ela").update(weight=9.0)
        AnalyzerConfig.objects.filter(name="metadata").delete()
        text = describe_drift(roster_drift())
        assert "weight_mismatch: ela" in text
        assert "missing: metadata" in text


@pytest.mark.django_db
class TestSeedAnalyzersCheckFlag:
    def test_check_exits_zero_when_in_sync(self, capsys):
        call_command("seed_analyzers", verbosity=0)
        call_command("seed_analyzers", check=True)
        assert "in sync" in capsys.readouterr().out

    def test_check_exits_one_on_drift_without_writing(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="ela").update(weight=9.0)
        with pytest.raises(SystemExit) as exc:
            call_command("seed_analyzers", check=True)
        assert exc.value.code == 1
        assert AnalyzerConfig.objects.get(name="ela").weight == 9.0


@pytest.mark.django_db
class TestAnalyzerRosterSystemCheck:
    def test_silent_when_in_sync(self):
        call_command("seed_analyzers", verbosity=0)
        assert analyzer_roster_check(None) == []

    def test_warns_with_id_on_drift(self):
        call_command("seed_analyzers", verbosity=0)
        AnalyzerConfig.objects.filter(name="ela").update(weight=9.0)
        warnings = analyzer_roster_check(None)
        assert len(warnings) == 1
        assert warnings[0].id == "analyzers.W001"
        assert "seed_analyzers" in warnings[0].msg
        assert "ela" in warnings[0].msg

    def test_silent_when_table_unavailable(self):
        from unittest.mock import patch
        from django.db import ProgrammingError

        with patch("analyzers.checks.roster_drift", side_effect=ProgrammingError("no table")):
            assert analyzer_roster_check(None) == []
