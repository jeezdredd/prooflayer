from typing import Any

STATUS_VARIANTS: dict[str, str] = {
    "started": "info",
    "success": "success",
    "skipped": "warning",
    "rejected": "warning",
    "failed": "danger",
}

HOLDOUT_ROWS: tuple[tuple[str, str, int], ...] = (
    ("ai_caught", "AI caught", 1),
    ("ai_authentic", "AI called authentic", -1),
    ("real_fake", "Real called AI", -1),
    ("real_suspicious", "Real called suspicious", -1),
    ("ai", "AI images", 0),
    ("real", "Real photos", 0),
)


def status_variant(status: str) -> str:
    return STATUS_VARIANTS.get(status, "")


def holdout_rows(metrics: dict[str, Any] | None) -> list[dict[str, Any]]:
    metrics = metrics or {}
    live = metrics.get("live") or {}
    candidate = metrics.get("candidate") or {}
    if not live and not candidate:
        return []
    rows = []
    for key, label, direction in HOLDOUT_ROWS:
        before = live.get(key)
        after = candidate.get(key)
        delta = after - before if isinstance(before, int) and isinstance(after, int) else None
        if delta is None or delta == 0 or direction == 0:
            variant = ""
        else:
            variant = "success" if delta * direction > 0 else "danger"
        rows.append(
            {"key": key, "label": label, "live": before, "candidate": after, "delta": delta, "variant": variant},
        )
    return rows


def holdout_summary(metrics: dict[str, Any] | None) -> str:
    rows = {row["key"]: row for row in holdout_rows(metrics)}
    if not rows:
        return ""
    parts = []
    for key in ("ai_caught", "real_fake"):
        row = rows[key]
        parts.append(f"{row['label']} {_value(row['live'])} → {_value(row['candidate'])}")
    return ", ".join(parts)


def _value(value: Any) -> str:
    return "-" if value is None else str(value)
