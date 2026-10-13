import json
import time
from pathlib import Path
from statistics import median

from django.core.management.base import BaseCommand

from analyzers.text.binoculars import DEFAULT_OBSERVER, DEFAULT_PERFORMER, BinocularsScorer

LANGS = ("en", "ru", "fr")
LABELS = ("human", "ai", "ai_humanized")


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def auc(ai: list[float], human: list[float]) -> float:
    pairs = len(ai) * len(human)
    if not pairs:
        return float("nan")
    wins = sum(1.0 if a < h else 0.5 if a == h else 0.0 for a in ai for h in human)
    return wins / pairs


def rate_below(values: list[float], threshold: float) -> float:
    return sum(v < threshold for v in values) / len(values) if values else float("nan")


def knots(t1: float, t5: float, human: list[float], ai: list[float]) -> list[list[float]]:
    candidates = [
        (median(ai), 0.95), (t1, 0.8), (t5, 0.55), (median(human), 0.15), (quantile(human, 0.9), 0.05),
    ]
    out = []
    for score, prob in candidates:
        if not out or score > out[-1][0]:
            out.append([round(score, 5), prob])
    return out


class Command(BaseCommand):
    help = "Score dataset/text_eval with Binoculars, calibrate per-language thresholds on calib, report test metrics"

    def add_arguments(self, parser):
        parser.add_argument("--data", default="dataset/text_eval")
        parser.add_argument("--observer", default=DEFAULT_OBSERVER)
        parser.add_argument("--performer", default=DEFAULT_PERFORMER)
        parser.add_argument("--per-class", type=int, default=150, help="max texts per label per split per language")
        parser.add_argument("--scores", required=True, help="jsonl cache of scores, appended and resumed")
        parser.add_argument("--calibration-out", default="")
        parser.add_argument("--report-only", action="store_true")

    def handle(self, *args, **opts):
        data, cache_path = Path(opts["data"]), Path(opts["scores"])
        cache = {}
        if cache_path.exists():
            for line in open(cache_path):
                row = json.loads(line)
                cache[row["key"]] = row
        if not opts["report_only"]:
            self._score(data, cache, cache_path, opts)
        self._report(cache, opts)

    def _items(self, data: Path, per_class: int):
        for lang in LANGS:
            for label in LABELS:
                path = data / lang / f"{label}.jsonl"
                if not path.exists():
                    continue
                counts = {"calib": 0, "test": 0}
                for line in open(path):
                    row = json.loads(line)
                    textsight = row["source"].startswith("textsight")
                    if counts[row["split"]] >= per_class and not textsight:
                        continue
                    if not textsight:
                        counts[row["split"]] += 1
                    yield lang, label, row

    def _score(self, data: Path, cache: dict, cache_path: Path, opts):
        scorer = BinocularsScorer(opts["observer"], opts["performer"])
        pair = f'{opts["observer"]}|{opts["performer"]}'
        todo = [item for item in self._items(data, opts["per_class"]) if f'{pair}|{item[2]["id"]}' not in cache]
        self.stdout.write(f"{len(todo)} texts to score with {pair} on {scorer.device}")
        started = time.time()
        with open(cache_path, "a") as fh:
            for i, (lang, label, row) in enumerate(todo, 1):
                key = f'{pair}|{row["id"]}'
                try:
                    result = scorer.score(row["text"])
                except ValueError:
                    continue
                entry = {
                    "key": key, "pair": pair, "id": row["id"], "lang": lang, "label": label, "split": row["split"],
                    "source": row["source"], "generator": row.get("generator", ""), "humanize": row.get("humanize", ""),
                    "score": round(result.score, 5), "tokens": result.tokens,
                }
                cache[key] = entry
                fh.write(json.dumps(entry) + "\n")
                if i % 25 == 0:
                    fh.flush()
                    rate = (time.time() - started) / i
                    self.stdout.write(f"  {i}/{len(todo)}  {rate:.2f} s/text  eta {rate * (len(todo) - i) / 60:.1f} min")
                    self.stdout.flush()

    def _report(self, cache: dict, opts):
        pair = f'{opts["observer"]}|{opts["performer"]}'
        rows = [r for r in cache.values() if r["pair"] == pair]
        calibration = {"observer": opts["observer"], "performer": opts["performer"], "direction": "lower_is_ai", "languages": {}}
        self.stdout.write(f"\n{pair}")
        self.stdout.write(f'{"lang":5}{"AUC":>7}{"thr@1%":>9}{"TPR@1%":>8}{"FPR@1%":>8}{"TPR@5%":>8}{"FPR@5%":>8}{"hum TPR@1%":>12}{"n h/ai":>10}')

        def pick(lang, label, split, source_prefix=None, exclude_prefix=None):
            return [
                r["score"] for r in rows
                if r["lang"] == lang and r["label"] == label and r["split"] == split
                and (source_prefix is None or r["source"].startswith(source_prefix))
                and (exclude_prefix is None or not r["source"].startswith(exclude_prefix))
            ]

        for lang in LANGS:
            calib_h = pick(lang, "human", "calib")
            test_h = pick(lang, "human", "test", exclude_prefix="textsight")
            test_ai = pick(lang, "ai", "test", exclude_prefix="textsight")
            hum = pick(lang, "ai_humanized", "test")
            if len(calib_h) < 20 or not test_ai:
                continue
            t1, t5 = quantile(calib_h, 0.01), quantile(calib_h, 0.05)
            calib_ai = pick(lang, "ai", "calib") or test_ai
            calibration["languages"][lang] = {
                "threshold_fpr1": round(t1, 5), "threshold_fpr5": round(t5, 5),
                "human_median": round(median(calib_h), 5), "ai_median": round(median(calib_ai), 5),
                "knots": knots(t1, t5, calib_h, calib_ai),
                "n_human": len(calib_h), "n_ai": len(calib_ai),
            }
            self.stdout.write(
                f"{lang:5}{auc(test_ai, test_h):>7.3f}{t1:>9.4f}{rate_below(test_ai, t1):>8.2f}{rate_below(test_h, t1):>8.3f}"
                f"{rate_below(test_ai, t5):>8.2f}{rate_below(test_h, t5):>8.3f}{rate_below(hum, t1):>12.2f}{f'{len(test_h)}/{len(test_ai)}':>10}"
            )
            ts_ai, ts_h = pick(lang, "ai", "test", source_prefix="textsight"), pick(lang, "human", "test", source_prefix="textsight")
            if ts_ai:
                self.stdout.write(f"      textsight-2026 ai n={len(ts_ai)} TPR@1%={rate_below(ts_ai, t1):.2f}  human n={len(ts_h)} FPR@1%={rate_below(ts_h, t1):.3f}")
            for mode in sorted({r["humanize"] for r in rows if r["lang"] == lang and r["label"] == "ai_humanized"}):
                vals = [r["score"] for r in rows if r["lang"] == lang and r["label"] == "ai_humanized" and r["humanize"] == mode]
                self.stdout.write(f"      humanized {mode}: n={len(vals)} TPR@1%={rate_below(vals, t1):.2f}")
        if opts["calibration_out"]:
            out = Path(opts["calibration_out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(calibration, indent=1))
            self.stdout.write(f"calibration written to {out}")
