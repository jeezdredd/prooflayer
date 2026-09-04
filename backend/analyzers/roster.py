from analyzers.models import AnalyzerConfig

WEIGHT_TOLERANCE = 1e-6


def expected_roster() -> dict[str, dict]:
    from analyzers.management.commands.seed_analyzers import ANALYZERS

    return {entry["name"]: entry for entry in ANALYZERS}


def roster_drift() -> dict:
    """Compare seeded AnalyzerConfig rows against the roster the code expects.

    Rows only change when seed_analyzers runs, which happens on backend boot - not
    on a worker-only rebuild and not on a code deploy that skips the backend. Every
    weight rebalance and every added or renamed analyzer is invisible until then.
    """
    expected = expected_roster()
    rows = {row.name: row for row in AnalyzerConfig.objects.all()}

    missing = sorted(name for name in expected if name not in rows)
    inactive_expected = sorted(name for name in expected if name in rows and not rows[name].is_active)
    stale_active = sorted(name for name, row in rows.items() if name not in expected and row.is_active)
    class_mismatch = sorted(
        name for name, spec in expected.items()
        if name in rows and rows[name].analyzer_class != spec["analyzer_class"]
    )
    weight_mismatch = sorted(
        name for name, spec in expected.items()
        if name in rows and abs(rows[name].weight - float(spec["weight"])) > WEIGHT_TOLERANCE
    )
    drift = {
        "missing": missing,
        "inactive_expected": inactive_expected,
        "stale_active": stale_active,
        "class_mismatch": class_mismatch,
        "weight_mismatch": weight_mismatch,
    }
    return {
        "expected": len(expected),
        "active": sum(1 for row in rows.values() if row.is_active),
        "drift": drift,
        "in_sync": not any(drift.values()),
    }


def describe_drift(report: dict) -> str:
    parts = []
    for key, names in report["drift"].items():
        if names:
            parts.append(f"{key}: {', '.join(names)}")
    return "; ".join(parts)
