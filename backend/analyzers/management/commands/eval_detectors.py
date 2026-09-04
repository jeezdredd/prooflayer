import json
import os
import time
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand
from PIL import Image

from analyzers.aggregator import aggregate
from analyzers.registry import load_analyzer_class
from content.services import extract_metadata

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

LABEL_DIRS = {
    "real": 0,
    "ai_generated": 1,
    "fake": 1,
}

DEFAULT_ANALYZERS = [
    ("community_forensics", "analyzers.implementations.community_forensics.CommunityForensicsDetector", 3.5),
    ("custom_detector", "analyzers.implementations.custom_detector.CustomDetector", 3.5),
    ("ai_detector", "analyzers.implementations.clip_detector.AIImageDetector", 1.0),
    ("metadata", "analyzers.implementations.metadata_analyzer.MetadataAnalyzer", 1.5),
    ("ela", "analyzers.implementations.ela_analyzer.ELAAnalyzer", 0.75),
]

FAKE_VERDICTS = {"fake", "likely_fake"}
GENERATOR_SEPARATOR = "__"


def _generator_of(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    if GENERATOR_SEPARATOR in stem:
        return stem.split(GENERATOR_SEPARATOR, 1)[0]
    return ""
REAL_VERDICTS = {"authentic", "authentic_edited"}


@dataclass
class FakeConfig:
    name: str
    weight: float


@dataclass
class FakeResult:
    analyzer: FakeConfig
    verdict: str
    confidence: float
    evidence: dict


@dataclass
class Stats:
    scores: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    errors: int = 0
    seconds: float = 0.0


def _auc(scores, labels) -> float | None:
    pairs = sorted(zip(scores, labels))
    pos = [i for i, (_, l) in enumerate(pairs) if l == 1]
    n_pos = len(pos)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = {}
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1
    rank_sum = sum(ranks[i] for i in pos)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def _is_readable(path: str) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def prob_scores_for(result) -> float | None:
    evidence = result.evidence or {}
    for key in ("ai_probability", "ai_probability_avg"):
        if evidence.get(key) is not None:
            return float(evidence[key])
    return None


def _collect(root: str, limit_per_class: int) -> tuple[list[tuple[str, int]], int]:
    samples = []
    skipped = 0
    for dirname, label in LABEL_DIRS.items():
        class_dir = os.path.join(root, dirname)
        if not os.path.isdir(class_dir):
            continue
        taken = 0
        for name in sorted(os.listdir(class_dir)):
            if taken >= limit_per_class:
                break
            if not name.lower().endswith(IMAGE_EXTENSIONS):
                continue
            path = os.path.join(class_dir, name)
            if not _is_readable(path):
                skipped += 1
                continue
            samples.append((path, label))
            taken += 1
    return samples, skipped


class Command(BaseCommand):
    help = "Run image analyzers over a labelled dataset and report per-analyzer accuracy"

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True, help="dir containing real/ and ai_generated/")
        parser.add_argument("--limit", type=int, default=50, help="images per class")
        parser.add_argument("--skip", nargs="*", default=[], help="analyzer names to skip")
        parser.add_argument("--json-out", default="", help="write raw per-image results here")

    def handle(self, *args, **options):
        samples, skipped = _collect(options["dataset"], options["limit"])
        if not samples:
            self.stderr.write("No labelled images found")
            return
        if skipped:
            self.stdout.write(f"skipped {skipped} unreadable files")

        skip = set(options["skip"])
        analyzers = []
        for name, dotted, weight in DEFAULT_ANALYZERS:
            if name in skip:
                continue
            try:
                analyzers.append((name, load_analyzer_class(dotted)(), weight))
            except Exception as exc:
                self.stderr.write(f"skip {name}: {exc}")

        from analyzers.ensemble import ensemble_info

        info = ensemble_info()
        self.stdout.write(f"{info['label']} (roster {info['fingerprint']}): {len(samples)} images, {len(analyzers)} analyzers")

        per_analyzer = {name: Stats() for name, _, _ in analyzers}
        ensemble = Stats()
        ensemble_verdicts = {}
        per_generator = {}
        rows = []

        for idx, (path, label) in enumerate(samples, 1):
            metadata = extract_metadata(path)
            results = []
            row = {"path": path, "label": label}

            for name, analyzer, weight in analyzers:
                started = time.time()
                try:
                    output = analyzer.analyze(path, dict(metadata))
                except Exception as exc:
                    per_analyzer[name].errors += 1
                    row[name] = f"exception:{exc}"
                    continue
                per_analyzer[name].seconds += time.time() - started

                if output.verdict == "error":
                    per_analyzer[name].errors += 1
                    row[name] = "error"
                    continue

                results.append(FakeResult(FakeConfig(name, weight), output.verdict, output.confidence, output.evidence))
                prob = (output.evidence or {}).get("ai_probability")
                if prob is None:
                    prob = (output.evidence or {}).get("ai_probability_avg")
                if prob is not None:
                    per_analyzer[name].scores.append(float(prob))
                    per_analyzer[name].labels.append(label)
                row[name] = {"verdict": output.verdict, "ai_probability": prob}

            if results:
                score, verdict = aggregate(results)
                ensemble.scores.append(score)
                ensemble.labels.append(label)
                key = ("ai" if label else "real", verdict)
                ensemble_verdicts[key] = ensemble_verdicts.get(key, 0) + 1
                row["ensemble"] = {"score": score, "verdict": verdict}
                generator = _generator_of(path)
                if label == 1 and generator:
                    bucket = per_generator.setdefault(generator, {"n": 0, "caught": 0, "scores": {}})
                    bucket["n"] += 1
                    bucket["caught"] += verdict in FAKE_VERDICTS
                    for r in results:
                        prob = prob_scores_for(r)
                        if prob is not None:
                            bucket["scores"].setdefault(r.analyzer.name, []).append(prob)

            rows.append(row)
            if idx % 10 == 0:
                self.stdout.write(f"  {idx}/{len(samples)}")

        self._report(per_analyzer, ensemble, ensemble_verdicts, len(samples))
        if per_generator:
            self._report_generators(per_generator, [name for name, _, _ in analyzers])

        if options["json_out"]:
            os.makedirs(os.path.dirname(os.path.abspath(options["json_out"])), exist_ok=True)
            with open(options["json_out"], "w") as fh:
                json.dump(rows, fh, indent=2, default=str)
            self.stdout.write(f"raw results -> {options['json_out']}")

    def _report_generators(self, per_generator, analyzer_names):
        detectors = [n for n in analyzer_names if any(n in b["scores"] for b in per_generator.values())]
        self.stdout.write("")
        self.stdout.write("Per generator (AI images only): caught = ensemble verdict fake/likely_fake; columns = mean ai_probability")
        header = f"{'generator':26} {'n':>4} {'caught':>7} " + " ".join(f"{d[:12]:>12}" for d in detectors)
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for generator, b in sorted(per_generator.items(), key=lambda kv: kv[1]["caught"] / max(kv[1]["n"], 1)):
            cells = []
            for d in detectors:
                vals = b["scores"].get(d)
                cells.append(f"{sum(vals) / len(vals):>12.3f}" if vals else f"{'-':>12}")
            self.stdout.write(f"{generator:26} {b['n']:>4} {b['caught'] / b['n']:>7.0%} " + " ".join(cells))

    def _report(self, per_analyzer, ensemble, ensemble_verdicts, total):
        self.stdout.write("")
        self.stdout.write(f"{'analyzer':22} {'n':>5} {'AUC':>7} {'acc@0.5':>8} {'mean_real':>10} {'mean_ai':>8} {'err':>5} {'s/img':>7}")
        self.stdout.write("-" * 78)

        for name, st in per_analyzer.items():
            if not st.scores:
                self.stdout.write(f"{name:22} {'-':>5} {'-':>7} {'-':>8} {'-':>10} {'-':>8} {st.errors:>5} {'-':>7}")
                continue
            auc = _auc(st.scores, st.labels)
            correct = sum(1 for s, l in zip(st.scores, st.labels) if (s >= 0.5) == bool(l))
            acc = correct / len(st.scores)
            real = [s for s, l in zip(st.scores, st.labels) if l == 0]
            ai = [s for s, l in zip(st.scores, st.labels) if l == 1]
            mean_real = sum(real) / len(real) if real else float("nan")
            mean_ai = sum(ai) / len(ai) if ai else float("nan")
            per_img = st.seconds / max(len(st.scores), 1)
            auc_txt = f"{auc:.3f}" if auc is not None else "-"
            self.stdout.write(
                f"{name:22} {len(st.scores):>5} {auc_txt:>7} {acc:>8.3f} "
                f"{mean_real:>10.3f} {mean_ai:>8.3f} {st.errors:>5} {per_img:>7.2f}"
            )

        if ensemble.scores:
            auc = _auc(ensemble.scores, ensemble.labels)
            correct = sum(1 for s, l in zip(ensemble.scores, ensemble.labels) if (s >= 0.5) == bool(l))
            auc_txt = f"{auc:.3f}" if auc is not None else "-"
            self.stdout.write("-" * 78)
            self.stdout.write(f"{'ENSEMBLE':22} {len(ensemble.scores):>5} {auc_txt:>7} {correct / len(ensemble.scores):>8.3f}")

        self.stdout.write("")
        self.stdout.write("Ensemble verdict distribution:")
        for truth in ("real", "ai"):
            items = {v: c for (t, v), c in ensemble_verdicts.items() if t == truth}
            if items:
                ordered = ", ".join(f"{v}={c}" for v, c in sorted(items.items(), key=lambda kv: -kv[1]))
                self.stdout.write(f"  true {truth:5}: {ordered}")
