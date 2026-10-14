import json
import math
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import torch
from django.core.management.base import BaseCommand
from torch.utils.data import DataLoader, WeightedRandomSampler
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

from analyzers.management.commands.eval_text_detectors import quantile
from analyzers.text.classifier import TextClassifier
from analyzers.text.noise import add_noise
from analyzers.text.normalize import normalize_for_model

LANGS = ("en", "ru", "fr")
MIN_CROP = 64
OUT_OF_DOMAIN_HUMAN = ("wiki-pre2022",)
STRICT_STEP = 0.05
NOISE_SHARE = 0.3


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in open(path) if line.strip()]


def auc_high(ai: list[float], human: list[float]) -> float:
    if not ai or not human:
        return float("nan")
    ranked = sorted([(v, 1) for v in ai] + [(v, 0) for v in human])
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(1 for k in range(i, j) if ranked[k][1])
        i = j
    return (rank_sum - len(ai) * (len(ai) + 1) / 2) / (len(ai) * len(human))


def rate_at_least(values: list[float], threshold: float) -> float:
    return sum(v >= threshold for v in values) / len(values) if values else float("nan")


def knots(t1: float, t5: float, human: list[float], ai: list[float], strict: float | None = None) -> list[list[float]]:
    if strict is None:
        candidates = [(median(human), 0.05), (t5, 0.45), (t1, 0.75), (max(median(ai), t1 + STRICT_STEP), 0.89)]
    else:
        candidates = [(median(human), 0.05), (t5, 0.45), (t1, 0.75), (strict, 0.89), (strict + STRICT_STEP, 0.97)]
    out = []
    for score, prob in candidates:
        if not out or score > out[-1][0]:
            out.append([round(score, 5), prob])
        else:
            out[-1][1] = max(out[-1][1], prob)
    return out


class Command(BaseCommand):
    help = "Fine-tune a multilingual encoder on dataset/text_t4, calibrate per language on calib, report on test"

    def add_arguments(self, parser):
        parser.add_argument("--data", default="dataset/text_t4")
        parser.add_argument("--base", default="intfloat/multilingual-e5-small")
        parser.add_argument("--out", default="dataset/text_models/e5-small-t4")
        parser.add_argument("--epochs", type=int, default=3)
        parser.add_argument("--batch", type=int, default=16)
        parser.add_argument("--lr", type=float, default=4e-5)
        parser.add_argument("--max-len", type=int, default=384)
        parser.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
        parser.add_argument("--seed", type=int, default=3)
        parser.add_argument("--eval-only", action="store_true")
        parser.add_argument("--no-strict", action="store_true", help="never let the classifier alone reach p >= 0.9")

    def handle(self, *args, **opts):
        data, out = Path(opts["data"]), Path(opts["out"])
        random.seed(opts["seed"])
        torch.manual_seed(opts["seed"])
        if not opts["eval_only"]:
            self._train(read_rows(data / "train.jsonl"), out, opts)
        self._evaluate(read_rows(data / "calib.jsonl"), read_rows(data / "test.jsonl"), out, opts)

    def _train(self, rows: list[dict], out: Path, opts: dict):
        tokenizer = AutoTokenizer.from_pretrained(opts["base"])
        model = AutoModelForSequenceClassification.from_pretrained(opts["base"], num_labels=2).to(opts["device"])
        body = opts["max_len"] - 2

        def encode(text):
            return tokenizer(normalize_for_model(text), add_special_tokens=False)["input_ids"]

        noise_rng = random.Random(opts["seed"])
        encoded = [encode(r["text"]) for r in rows]
        noisy = [encode(add_noise(r["text"], noise_rng)) for r in rows]
        groups = Counter((r["lang"], r["label"]) for r in rows)
        weights = [1.0 / groups[(r["lang"], r["label"])] for r in rows]
        self.stdout.write(f"train rows {len(rows)} groups {dict(groups)}")

        def collate(indices):
            seqs = []
            for i in indices:
                ids = noisy[i] if random.random() < NOISE_SHARE else encoded[i]
                length = random.randint(min(len(ids), MIN_CROP), min(len(ids), body))
                start = random.randint(0, len(ids) - length)
                seqs.append(tokenizer.build_inputs_with_special_tokens(ids[start : start + length]))
            batch = tokenizer.pad({"input_ids": seqs}, pad_to_multiple_of=64, return_tensors="pt")
            batch["labels"] = torch.tensor([rows[i]["label"] for i in indices])
            return batch

        sampler = WeightedRandomSampler(weights, num_samples=len(rows), replacement=True)
        loader = DataLoader(list(range(len(rows))), batch_size=opts["batch"], sampler=sampler, collate_fn=collate)
        optimizer = torch.optim.AdamW(model.parameters(), lr=opts["lr"], weight_decay=0.01)
        total = len(loader) * opts["epochs"]
        scheduler = get_linear_schedule_with_warmup(optimizer, int(total * 0.06), total)
        model.train()
        started, step = time.time(), 0
        for epoch in range(opts["epochs"]):
            running = 0.0
            for batch in loader:
                batch = {k: v.to(opts["device"]) for k, v in batch.items()}
                loss = model(**batch).loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                running += loss.item()
                step += 1
                if step % 50 == 0:
                    memory = ""
                    if opts["device"] == "mps":
                        torch.mps.empty_cache()
                        memory = f" mps {torch.mps.driver_allocated_memory() / 2**30:.1f}G"
                    self.stdout.write(f"epoch {epoch + 1} step {step}/{total} loss {running / 50:.4f} {step / (time.time() - started):.2f} it/s{memory}")
                    running = 0.0
        out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(out)
        tokenizer.save_pretrained(out)
        (out / "training_meta.json").write_text(
            json.dumps(
                {
                    "base": opts["base"],
                    "rows": len(rows),
                    "groups": {f"{lang}/{label}": n for (lang, label), n in groups.items()},
                    "epochs": opts["epochs"],
                    "lr": opts["lr"],
                    "max_len": opts["max_len"],
                    "trained_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=1,
            )
        )

    def _evaluate(self, calib: list[dict], test: list[dict], out: Path, opts: dict):
        classifier = TextClassifier(str(out), device=opts["device"])
        scored = []
        for split, rows in (("calib", calib), ("test", test)):
            for i, r in enumerate(rows):
                result = classifier.score(r["text"])
                scored.append({k: r.get(k, "") for k in ("id", "lang", "label", "generator", "mode", "source")} | {"split": split, "score": round(result.score, 4)})
                if (i + 1) % 500 == 0:
                    self.stdout.write(f"scored {split} {i + 1}/{len(rows)}")
        with open(out / "scores.jsonl", "w") as fh:
            for s in scored:
                fh.write(json.dumps(s) + "\n")

        calibration = {"base": opts["base"], "trained_at": datetime.now(timezone.utc).isoformat(), "languages": {}}
        report = {}
        by = defaultdict(list)
        for s in scored:
            by[(s["split"], s["lang"])].append(s)
        for lang in LANGS:
            cal = by[("calib", lang)]
            human = [s["score"] for s in cal if not s["label"]]
            ai = [s["score"] for s in cal if s["label"]]
            if len(human) < 20 or len(ai) < 20:
                continue
            t1, t5 = quantile(human, 0.99), quantile(human, 0.95)
            strict = None if opts["no_strict"] else max(max(human), t1 + 0.01)
            calibration["languages"][lang] = {
                "threshold_fpr1": round(t1, 4),
                "threshold_fpr5": round(t5, 4),
                "threshold_strict": None if strict is None else round(strict, 4),
                "knots": knots(t1, t5, human, ai, strict),
                "calib_human": len(human),
                "calib_ai": len(ai),
            }
            report[lang] = self._lang_report(by[("test", lang)], t1, t5, strict)
        (out / "calibration.json").write_text(json.dumps(calibration, indent=1))
        (out / "report.json").write_text(json.dumps(report, indent=1))
        self._print(report)

    def _lang_report(self, rows: list[dict], t1: float, t5: float, strict: float | None) -> dict:
        human = [s for s in rows if not s["label"]]
        ai = [s for s in rows if s["label"]]
        in_domain_human = [s["score"] for s in human if s["source"] not in OUT_OF_DOMAIN_HUMAN and not s["source"].startswith("textsight")]
        plain_ai = [s["score"] for s in ai if not s["mode"] and not s["source"].startswith("textsight")]
        report = {
            "auc_legacy": round(auc_high(plain_ai, in_domain_human), 4),
            "auc_all": round(auc_high([s["score"] for s in ai], in_domain_human), 4),
            "threshold_fpr1": round(t1, 4),
            "human_fpr_at_t1": round(rate_at_least(in_domain_human, t1), 4),
            "human_fpr_at_t5": round(rate_at_least(in_domain_human, t5), 4),
            "threshold_strict": None if strict is None else round(strict, 4),
            "human_fpr_at_strict": None if strict is None else round(rate_at_least(in_domain_human, strict), 4),
            "human_n": len(in_domain_human),
            "groups": {},
        }
        groups = defaultdict(list)
        for s in ai:
            key = s["generator"] or s["source"]
            if s["source"].startswith("textsight"):
                key = "textsight-2026"
            elif s["mode"]:
                key = f'{s["mode"]}:{key}' if s["mode"] in ("generate", "humanize") or s["mode"].startswith("attack:") else s["mode"]
                if s["source"] == "fresh-wiki":
                    key = f"wiki-{key}"
            else:
                key = f"legacy:{key}"
            groups[key].append(s["score"])
        textsight_human = [s["score"] for s in human if s["source"].startswith("textsight")]
        if textsight_human:
            groups["HUMAN textsight-wiki (FPR)"] = textsight_human
        for source in OUT_OF_DOMAIN_HUMAN:
            values = [s["score"] for s in human if s["source"] == source]
            if values:
                groups[f"HUMAN {source} (FPR)"] = values
        for key, values in sorted(groups.items()):
            report["groups"][key] = {
                "n": len(values),
                "at_t1": round(rate_at_least(values, t1), 3),
                "at_t5": round(rate_at_least(values, t5), 3),
                "at_strict": None if strict is None else round(rate_at_least(values, strict), 3),
            }
        return report

    def _print(self, report: dict):
        for lang, r in report.items():
            self.stdout.write(
                f"\n[{lang}] AUC legacy {r['auc_legacy']} all {r['auc_all']} | t1 {r['threshold_fpr1']} | "
                f"human FPR test @t1 {r['human_fpr_at_t1']} @t5 {r['human_fpr_at_t5']} @strict {r['human_fpr_at_strict']} (n={r['human_n']})"
            )
            for key, g in r["groups"].items():
                self.stdout.write(f"  {key:<48} n={g['n']:<4} @t1 {g['at_t1']:<6} @t5 {g['at_t5']:<6} @strict {g['at_strict']}")
        if not report:
            self.stdout.write("no language had enough calib rows")
        if any(math.isnan(r["auc_all"]) for r in report.values()):
            self.stdout.write("some AUCs are NaN (a class is missing in test)")
