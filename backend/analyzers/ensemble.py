import hashlib

ENSEMBLE_NAME = "Tribunal"
ENSEMBLE_SLUG = "tribunal"
ENSEMBLE_VERSION = "1.0"


def ensemble_label() -> str:
    return f"{ENSEMBLE_NAME} {ENSEMBLE_VERSION}"


def roster_fingerprint(entries) -> str:
    """Short stable hash of the seeded roster: names, weights, class paths.

    Changes whenever the tribunal's membership or voting weights change, so a
    verdict can be traced to the exact configuration that produced it even if the
    human-readable version was not bumped.
    """
    canonical = "|".join(
        f"{e['name']}:{e['analyzer_class']}:{float(e['weight']):.4f}"
        for e in sorted(entries, key=lambda e: e["name"])
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def ensemble_info() -> dict:
    from analyzers.management.commands.seed_analyzers import ANALYZERS

    return {
        "name": ENSEMBLE_NAME,
        "slug": ENSEMBLE_SLUG,
        "version": ENSEMBLE_VERSION,
        "label": ensemble_label(),
        "fingerprint": roster_fingerprint(ANALYZERS),
        "members": [{"name": e["name"], "weight": e["weight"]} for e in ANALYZERS],
    }
