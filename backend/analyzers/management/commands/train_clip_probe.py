from datetime import datetime, timezone

import numpy as np
from django.core.management.base import BaseCommand

from analyzers.clip_probe_core import DEFAULT_BACKBONE, embed_paths, predict, save_head, train_logreg
from analyzers.management.commands.eval_detectors import _auc, _collect, _generator_of

THRESHOLDS = (0.5, 0.7, 0.9, 0.95, 0.98)


class Command(BaseCommand):
    help = "Train a logistic-regression probe on frozen CLIP features (UniversalFakeDetect-style)"

    def add_arguments(self, parser):
        parser.add_argument("--train-dir", action="append", required=True)
        parser.add_argument("--eval-dir", default="")
        parser.add_argument("--backbone", default=DEFAULT_BACKBONE)
        parser.add_argument("--l2", type=float, default=1e-3)
        parser.add_argument("--limit", type=int, default=100000, help="images per class per dir")
        parser.add_argument("--out", default="")
        parser.add_argument("--cache-dir", default="")

    def handle(self, *args, **opts):
        train = []
        for d in opts["train_dir"]:
            samples, skipped = _collect(d, opts["limit"])
            train.extend(samples)
            self.stdout.write(f"train {d}: {len(samples)} images ({skipped} unreadable skipped)")
        paths = [p for p, _ in train]
        y = np.array([label for _, label in train], dtype=np.float64)
        x = embed_paths(paths, opts["backbone"], opts["cache_dir"] or None)
        weights, bias = train_logreg(x, y, l2=opts["l2"])
        train_auc = _auc(list(predict(x, weights, bias)), list(y))
        self.stdout.write(f"backbone {opts['backbone']} dim {x.shape[1]}  train AUC {train_auc:.3f}")

        meta = {
            "backbone": opts["backbone"],
            "l2": opts["l2"],
            "train_dirs": opts["train_dir"],
            "train_counts": {"real": int((y == 0).sum()), "ai": int((y == 1).sum())},
            "train_auc": round(train_auc, 4),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        if opts["eval_dir"]:
            meta["eval"] = self._evaluate(opts["eval_dir"], opts["backbone"], weights, bias, opts["cache_dir"] or None)

        if opts["out"]:
            save_head(opts["out"], opts["backbone"], weights, bias, meta)
            self.stdout.write(self.style.SUCCESS(f"head saved to {opts['out']}"))

    def _evaluate(self, directory, backbone, weights, bias, cache_dir):
        samples, _ = _collect(directory, 100000)
        paths = [p for p, _ in samples]
        y = np.array([label for _, label in samples])
        scores = predict(embed_paths(paths, backbone, cache_dir), weights, bias)
        auc = _auc(list(scores), list(y))
        real, ai = scores[y == 0], scores[y == 1]
        self.stdout.write(f"eval {directory}: {len(real)} real / {len(ai)} ai  AUC {auc:.3f}")
        self.stdout.write(f"  real: p50 {np.median(real):.3f} p95 {np.quantile(real, .95):.3f} max {real.max():.3f}")
        for t in THRESHOLDS:
            self.stdout.write(f"  t={t:.2f}  FPR {float((real >= t).mean()):6.1%}  TPR {float((ai >= t).mean()):6.1%}")
        per_gen = {}
        for path, label, score in zip(paths, y, scores):
            if label == 1:
                per_gen.setdefault(_generator_of(path) or "unknown", []).append(float(score))
        self.stdout.write("  per generator mean score:")
        for gen, vals in sorted(per_gen.items(), key=lambda kv: np.mean(kv[1])):
            self.stdout.write(f"    {gen:26} {np.mean(vals):.3f}  (n={len(vals)})")
        return {"auc": round(auc, 4), "real_max": round(float(real.max()), 4),
                "per_generator": {g: round(float(np.mean(v)), 4) for g, v in per_gen.items()}}
