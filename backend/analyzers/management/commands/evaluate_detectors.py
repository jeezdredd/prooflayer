import csv
import os
import sys
import time
from pathlib import Path

from django.core.management.base import BaseCommand

from analyzers.aggregator import aggregate
from analyzers.models import AnalyzerConfig
from analyzers.registry import load_analyzer_class


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _collect_samples(labeled_dir: Path) -> list[tuple[Path, str]]:
    samples = []
    for label in ("real", "fake"):
        d = labeled_dir / label
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                samples.append((f, label))
    return samples


def _run_single(analyzer, file_path: Path) -> dict:
    try:
        result = analyzer.analyze(str(file_path), {})
        return {
            "verdict": result.verdict,
            "confidence": result.confidence,
            "evidence": result.evidence or {},
            "error": False,
        }
    except Exception as exc:
        return {
            "verdict": "error",
            "confidence": 0.0,
            "evidence": {},
            "error": True,
            "error_msg": str(exc),
        }


def _is_positive(verdict: str) -> bool:
    return verdict in ("fake", "suspicious", "likely_fake")


def _compute_metrics(results: list[tuple[str, str]]) -> dict:
    tp = tn = fp = fn = 0
    probs = []
    labels = []
    for pred_verdict, true_label, ai_prob in results:
        pred_positive = _is_positive(pred_verdict)
        true_positive = true_label == "fake"
        if pred_positive and true_positive:
            tp += 1
        elif not pred_positive and not true_positive:
            tn += 1
        elif pred_positive and not true_positive:
            fp += 1
        else:
            fn += 1
        if ai_prob is not None:
            probs.append(ai_prob)
            labels.append(1 if true_positive else 0)

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    auc = None
    if len(probs) >= 2 and len(set(labels)) == 2:
        auc = _roc_auc(probs, labels)

    brier = None
    if probs:
        brier = sum((p - l) ** 2 for p, l in zip(probs, labels)) / len(probs)

    return {
        "samples": total,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "auc": round(auc, 4) if auc is not None else "n/a",
        "brier": round(brier, 4) if brier is not None else "n/a",
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def _roc_auc(probs: list[float], labels: list[int]) -> float:
    paired = sorted(zip(probs, labels), key=lambda x: -x[0])
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return 0.5
    tp_count = 0
    auc = 0.0
    prev_fp = 0
    for _, label in paired:
        if label == 1:
            tp_count += 1
        else:
            auc += tp_count
            prev_fp += 1
    return auc / (pos * neg)


class Command(BaseCommand):
    help = "Evaluate per-analyzer and ensemble accuracy on labeled samples"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="samples/labeled",
            help="Root directory with real/ and fake/ subdirs",
        )
        parser.add_argument(
            "--analyzers",
            default="",
            help="Comma-separated analyzer names to run (default: all active image analyzers)",
        )
        parser.add_argument(
            "--out",
            default="",
            help="Path to write CSV results (optional)",
        )
        parser.add_argument(
            "--no-ensemble",
            action="store_true",
            help="Skip ensemble aggregation step",
        )

    def handle(self, *args, **options):
        labeled_dir = Path(options["dir"])
        if not labeled_dir.is_absolute():
            labeled_dir = Path(os.getcwd()) / labeled_dir

        samples = _collect_samples(labeled_dir)
        if not samples:
            self.stderr.write(f"No samples found in {labeled_dir}")
            return

        self.stdout.write(f"Found {len(samples)} samples ({sum(1 for _, l in samples if l == 'real')} real, {sum(1 for _, l in samples if l == 'fake')} fake)")

        filter_names = [n.strip() for n in options["analyzers"].split(",") if n.strip()]

        configs = AnalyzerConfig.objects.filter(is_active=True)
        if filter_names:
            configs = configs.filter(name__in=filter_names)

        image_configs = []
        for cfg in configs:
            try:
                cls = load_analyzer_class(cfg.analyzer_class)
                inst = cls()
                mimes = inst.supported_mime_types()
                if any(m.startswith("image/") for m in mimes):
                    image_configs.append((cfg, inst))
            except Exception as exc:
                self.stderr.write(f"  skip {cfg.name}: {exc}")

        if not image_configs:
            self.stderr.write("No image analyzers available")
            return

        self.stdout.write(f"Running {len(image_configs)} analyzer(s): {', '.join(c.name for c, _ in image_configs)}\n")

        per_analyzer_results = {cfg.name: [] for cfg, _ in image_configs}
        ensemble_inputs: dict[Path, list] = {}

        for i, (file_path, true_label) in enumerate(samples, 1):
            self.stdout.write(f"  [{i:3d}/{len(samples)}] {file_path.name}", ending="\r")
            self.stdout.flush()

            file_results_for_ensemble = []

            for cfg, inst in image_configs:
                t0 = time.perf_counter()
                out = _run_single(inst, file_path)
                elapsed = time.perf_counter() - t0

                if out["error"]:
                    self.stderr.write(f"\n  ERROR {cfg.name} on {file_path.name}: {out.get('error_msg', '')}")
                    continue

                ai_prob = out["evidence"].get("ai_probability")
                per_analyzer_results[cfg.name].append((out["verdict"], true_label, ai_prob))

                fake_result = _FakeResult(cfg, out["verdict"], out["confidence"], out["evidence"])
                file_results_for_ensemble.append(fake_result)

            ensemble_inputs[file_path] = (file_results_for_ensemble, true_label)

        self.stdout.write("")

        rows = []

        for cfg, _ in image_configs:
            res = per_analyzer_results[cfg.name]
            if not res:
                continue
            m = _compute_metrics(res)
            m["analyzer"] = cfg.name
            rows.append(m)
            self._print_row(m)

        if not options["no_ensemble"] and len(image_configs) > 1:
            ensemble_preds = []
            for file_path, (file_results, true_label) in ensemble_inputs.items():
                if not file_results:
                    continue
                try:
                    score, verdict = aggregate(file_results)
                    ai_prob = score
                    ensemble_preds.append((verdict, true_label, ai_prob))
                except Exception as exc:
                    self.stderr.write(f"\n  ENSEMBLE ERROR on {file_path.name}: {exc}")

            if ensemble_preds:
                m = _compute_metrics(ensemble_preds)
                m["analyzer"] = "ENSEMBLE"
                rows.append(m)
                self.stdout.write("\n--- ENSEMBLE ---")
                self._print_row(m)

        if options["out"]:
            out_path = Path(options["out"])
            fieldnames = ["analyzer", "samples", "accuracy", "precision", "recall", "f1", "auc", "brier", "tp", "tn", "fp", "fn"]
            with open(out_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(f"\nCSV written to {out_path}")

    def _print_row(self, m: dict):
        name = m["analyzer"]
        self.stdout.write(
            f"  {name:<30}  n={m['samples']:3d}  "
            f"acc={m['accuracy']:.3f}  prec={m['precision']:.3f}  "
            f"rec={m['recall']:.3f}  F1={m['f1']:.3f}  "
            f"AUC={m['auc']}  Brier={m['brier']}  "
            f"TP={m['tp']} TN={m['tn']} FP={m['fp']} FN={m['fn']}"
        )


class _FakeResult:
    def __init__(self, config, verdict, confidence, evidence):
        self.analyzer = config
        self.verdict = verdict
        self.confidence = confidence
        self.evidence = evidence
