import hashlib
import json
import logging
import shutil
import tempfile
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

from analyzers.aggregator import aggregate
from analyzers.implementations.custom_detector import CALIBRATION_FILENAME, RETRAIN_MODEL_DIR, CustomDetector
from analyzers.management.commands.eval_detectors import DEFAULT_ANALYZERS, IMAGE_EXTENSIONS, FakeConfig, FakeResult, _collect
from analyzers.registry import load_analyzer_class
from content.services import extract_metadata

logger = logging.getLogger(__name__)

ROOT = Path(RETRAIN_MODEL_DIR)
LIVE = ROOT / "image"
CANDIDATE = ROOT / "image.candidate"
PREVIOUS = ROOT / "image.previous"
AUTO = ROOT / "auto"
POOL = AUTO / "pool"
CALIBRATION = AUTO / "calibration"
HOLDOUT = AUTO / "holdout"
STATE = AUTO / "state.json"

FAKE_VERDICTS = {"fake", "likely_fake"}
CALIBRATION_EVERY = 5
FIRST_ROW_GROUP = 6
REAL_ANCHOR = 0.5
HIGH_ANCHOR = 0.8
MAX_REAL_KNOT = 0.99
MAX_POOL_FILES = 3000
LABEL_DIRS = ("real", "ai_generated")


@dataclass
class HoldoutMetrics:
    real: int = 0
    ai: int = 0
    real_fake: int = 0
    real_suspicious: int = 0
    ai_caught: int = 0
    ai_authentic: int = 0

    def add(self, label: int, verdict: str) -> None:
        if label:
            self.ai += 1
            self.ai_caught += verdict in FAKE_VERDICTS
            self.ai_authentic += verdict == "authentic"
        else:
            self.real += 1
            self.real_fake += verdict in FAKE_VERDICTS
            self.real_suspicious += verdict == "suspicious"


def image_count(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for f in root.rglob("*") if f.suffix.lower() in IMAGE_EXTENSIONS)


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def write_state(state: dict) -> None:
    AUTO.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def fit_knots(real_raw: list[float], ai_raw: list[float]) -> list[list[float]] | None:
    if not real_raw:
        return None
    top = min(max(real_raw), MAX_REAL_KNOT)
    ai_median = sorted(ai_raw)[len(ai_raw) // 2] if ai_raw else 0.0
    high = max(top + (1.0 - top) / 2, ai_median)
    high = min(max(high, top + 1e-3), 1.0 - 1e-3)
    return [[0.0, 0.0], [round(top, 4), REAL_ANCHOR], [round(high, 4), HIGH_ANCHOR], [1.0, 1.0]]


def gate(live: HoldoutMetrics, candidate: HoldoutMetrics) -> list[str]:
    problems = []
    if candidate.real_fake > 0:
        problems.append(f"{candidate.real_fake} real photos called AI")
    if candidate.real_suspicious > live.real_suspicious:
        problems.append(f"real photos called suspicious {live.real_suspicious} -> {candidate.real_suspicious}")
    if candidate.ai_caught < live.ai_caught:
        problems.append(f"AI caught {live.ai_caught} -> {candidate.ai_caught}")
    if candidate.ai_authentic > live.ai_authentic:
        problems.append(f"AI called authentic {live.ai_authentic} -> {candidate.ai_authentic}")
    if not problems and candidate.ai_caught == live.ai_caught and candidate.ai_authentic == live.ai_authentic:
        problems.append("no improvement over the live model")
    return problems


def _bucket(path: Path) -> Path:
    digest = int(hashlib.sha256(path.name.encode()).hexdigest(), 16)
    return CALIBRATION if digest % CALIBRATION_EVERY == 0 else POOL


def distribute(source: Path) -> int:
    moved = 0
    for label in LABEL_DIRS:
        base = source / label
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if f.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            target = _bucket(f) / f.relative_to(source)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), target)
            moved += 1
    return moved


def trim_pool(limit: int = MAX_POOL_FILES) -> int:
    files = sorted((f for f in POOL.rglob("*") if f.suffix.lower() in IMAGE_EXTENSIONS), key=lambda f: f.stat().st_mtime)
    excess = files[: max(0, len(files) - limit)]
    for f in excess:
        f.unlink()
    return len(excess)


def fetch_new(per_model: int, real: int, row_groups: int) -> int:
    state = read_state()
    start = int(state.get("row_group", FIRST_ROW_GROUP))
    with tempfile.TemporaryDirectory() as tmp:
        call_command(
            "fetch_openfake",
            out=tmp,
            per_model=per_model,
            real=real,
            start_row_group=start,
            row_groups_per_shard=row_groups,
            max_passes=1,
            stdout=StringIO(),
        )
        for against in (HOLDOUT, POOL, CALIBRATION):
            if image_count(against):
                call_command("dedupe_dataset", target=tmp, against=str(against), stdout=StringIO())
        moved = distribute(Path(tmp))
    state["row_group"] = start + row_groups
    write_state(state)
    return moved


def train_candidate(epochs: int) -> str:
    if CANDIDATE.exists():
        shutil.rmtree(CANDIDATE)
    buf = StringIO()
    call_command(
        "retrain_detector",
        media_type="image",
        epochs=epochs,
        base_model=str(LIVE),
        extra_dir=[str(POOL)],
        output_dir=str(CANDIDATE),
        min_samples=1,
        stdout=buf,
    )
    if not (CANDIDATE / "config.json").exists():
        raise RuntimeError("training produced no candidate model")
    return buf.getvalue().strip().splitlines()[-1][:120] if buf.getvalue().strip() else ""


def calibrate_candidate() -> list[list[float]] | None:
    samples, _ = _collect(str(CALIBRATION), 100_000)
    detector = CustomDetector(model_dir=str(CANDIDATE))
    real_raw, ai_raw = [], []
    for path, label in samples:
        out = detector.analyze(path, {})
        raw = (out.evidence or {}).get("raw_probability")
        if raw is None:
            continue
        (ai_raw if label else real_raw).append(float(raw))
    knots = fit_knots(real_raw, ai_raw)
    if knots:
        (CANDIDATE / CALIBRATION_FILENAME).write_text(json.dumps({"knots": knots, "real": len(real_raw), "ai": len(ai_raw)}, indent=2))
    return knots


def holdout_metrics(model_dirs: list[Path], holdout: Path = HOLDOUT) -> list[HoldoutMetrics]:
    samples, _ = _collect(str(holdout), 100_000)
    custom_weight = next(weight for name, _, weight in DEFAULT_ANALYZERS if name == "custom_detector")
    others = [(name, load_analyzer_class(dotted)(), weight) for name, dotted, weight in DEFAULT_ANALYZERS if name != "custom_detector"]
    base = []
    for path, label in samples:
        metadata = extract_metadata(path)
        results = []
        for name, analyzer, weight in others:
            out = analyzer.analyze(path, dict(metadata))
            if out.verdict != "error":
                results.append(FakeResult(FakeConfig(name, weight), out.verdict, out.confidence, out.evidence))
        base.append((path, label, metadata, results))
    metrics = []
    for model_dir in model_dirs:
        detector = CustomDetector(model_dir=str(model_dir))
        current = HoldoutMetrics()
        for path, label, metadata, results in base:
            out = detector.analyze(path, dict(metadata))
            members = list(results)
            if out.verdict != "error":
                members.append(FakeResult(FakeConfig("custom_detector", custom_weight), out.verdict, out.confidence, out.evidence))
            _, verdict = aggregate(members)
            current.add(label, verdict)
        metrics.append(current)
    return metrics


def promote() -> None:
    if PREVIOUS.exists():
        shutil.rmtree(PREVIOUS)
    LIVE.rename(PREVIOUS)
    CANDIDATE.rename(LIVE)


def rollback() -> None:
    if not PREVIOUS.exists():
        raise RuntimeError("no previous model to roll back to")
    if CANDIDATE.exists():
        shutil.rmtree(CANDIDATE)
    LIVE.rename(CANDIDATE)
    PREVIOUS.rename(LIVE)
    CANDIDATE.rename(PREVIOUS)


@dataclass
class Outcome:
    status: str
    reason: str = ""
    new_samples: int = 0
    revision: str = ""
    metrics: dict | None = None


def run(db_new_samples: int, epochs: int) -> Outcome:
    if not image_count(HOLDOUT):
        return Outcome("skipped", "held-out set is missing")
    if not (LIVE / "config.json").exists():
        return Outcome("skipped", "no live model to fine-tune")
    fetched = fetch_new(
        per_model=getattr(settings, "AUTO_RETRAIN_PER_MODEL", 8),
        real=getattr(settings, "AUTO_RETRAIN_REAL", 120),
        row_groups=getattr(settings, "AUTO_RETRAIN_ROW_GROUPS", 1),
    )
    trim_pool()
    new_samples = fetched + db_new_samples
    needed = getattr(settings, "RETRAIN_MIN_NEW_SAMPLES", 50)
    if new_samples < needed:
        return Outcome("skipped", f"only {new_samples} new approved samples, need {needed}", new_samples)
    if not image_count(CALIBRATION):
        return Outcome("skipped", "calibration set is empty", new_samples)
    revision = train_candidate(epochs)
    knots = calibrate_candidate()
    live, candidate = holdout_metrics([LIVE, CANDIDATE])
    problems = gate(live, candidate)
    metrics = {"live": asdict(live), "candidate": asdict(candidate), "knots": knots, "fetched": fetched, "db_samples": db_new_samples, "problems": problems}
    if problems:
        shutil.rmtree(CANDIDATE, ignore_errors=True)
        return Outcome("rejected", "; ".join(problems), new_samples, revision, metrics)
    promote()
    logger.info("auto retrain promoted a new image model: %s", metrics)
    return Outcome("success", "", new_samples, revision, metrics)
