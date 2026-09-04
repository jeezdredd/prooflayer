import json
import logging
import os
import random
import re
import shutil
import tempfile
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.db import DatabaseError

logger = logging.getLogger(__name__)

RETRAIN_MODEL_DIR = os.environ.get(
    "RETRAIN_MODEL_DIR",
    "/root/.cache/huggingface/prooflayer-retrained",
)

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
EXTRA_LABEL_DIRS = {"real": "real", "fake": "fake", "ai_generated": "fake"}


def _readable(path: str) -> bool:
    from PIL import Image

    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def _collect_extra(dirs: list[str]) -> list[tuple[str, str]]:
    """(path, label) for every decodable image under <dir>/{real,fake,ai_generated}.

    Unreadable files are dropped here rather than crashing the Trainer mid-epoch;
    dataset/hf/real carries 250 zero-content macOS quarantine stubs.
    """
    out = []
    for root in dirs:
        for sub, label in EXTRA_LABEL_DIRS.items():
            class_dir = os.path.join(root, sub)
            if not os.path.isdir(class_dir):
                continue
            for name in sorted(os.listdir(class_dir)):
                path = os.path.join(class_dir, name)
                if name.lower().endswith(IMAGE_EXTENSIONS) and _readable(path):
                    out.append((path, label))
    return out


def _source_of(image_path: str) -> str:
    name = os.path.basename(os.path.realpath(image_path))
    stem = os.path.splitext(name)[0]
    stem = re.sub(r"^extra_\d+_", "", stem)
    return stem.split("__", 1)[0] if "__" in stem else stem.split("_", 1)[0]


def _sample_group(image_path: str) -> str:
    """Group key so frames of one video never straddle the train/eval split."""
    stem = os.path.splitext(os.path.basename(image_path))[0]
    for marker in ("_f", "_spec"):
        if marker in stem:
            stem = stem.rsplit(marker, 1)[0]
            break
    return stem


MEDIA_TYPES = {
    "image": ["image/jpeg", "image/png", "image/webp"],
    "video": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"],
    "audio": ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/flac", "audio/mp4"],
}

BASE_MODELS = {
    "image": "Nahrawy/AIorNot",
    "video": "Nahrawy/AIorNot",
    "audio": "Nahrawy/AIorNot",
}


class Command(BaseCommand):
    help = "Fine-tune AI detectors using approved training submissions"

    def add_arguments(self, parser):
        parser.add_argument("--media-type", choices=["image", "video", "audio"], default="image")
        parser.add_argument("--epochs", type=int, default=3)
        parser.add_argument("--min-samples", type=int, default=10)
        parser.add_argument("--use-cifake", action="store_true", help="Include CIFAKE base dataset")
        parser.add_argument(
            "--extra-dir", action="append", default=[],
            help="labelled tree with real/ and ai_generated/ (or fake/) subdirs; repeatable",
        )
        parser.add_argument("--base-model", default="", help="HF id or local path to fine-tune from")
        parser.add_argument("--no-class-weights", action="store_true", help="disable inverse-frequency loss weights")
        parser.add_argument("--batch-size", type=int, default=16)
        parser.add_argument("--learning-rate", type=float, default=2e-5)

    def handle(self, *args, **options):
        from content.models import Submission

        media_type = options["media_type"]
        mime_types = MEDIA_TYPES[media_type]

        qs = Submission.objects.filter(
            approved_for_training=True,
            verified_label__in=["real", "fake"],
            mime_type__in=mime_types,
            status="completed",
        )

        extra_files = _collect_extra(options["extra_dir"])
        try:
            count = qs.count()
        except DatabaseError as exc:
            if not extra_files:
                raise
            self.stderr.write(f"Submission query failed ({str(exc).splitlines()[0][:80]}); training on --extra-dir only")
            qs = Submission.objects.none()
            count = 0
        self.stdout.write(f"Found {count} approved {media_type} submissions, {len(extra_files)} extra files")

        if count + len(extra_files) < options["min_samples"]:
            self.stderr.write(
                f"Need at least {options['min_samples']} samples (got {count + len(extra_files)}). "
                f"Use --min-samples to lower threshold."
            )
            return

        persistent_model_dir = os.path.join(RETRAIN_MODEL_DIR, media_type)

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = os.path.join(tmpdir, "dataset")
            os.makedirs(os.path.join(dataset_dir, "real"), exist_ok=True)
            os.makedirs(os.path.join(dataset_dir, "fake"), exist_ok=True)

            from content.storage_utils import local_file

            copied = 0
            for submission in qs:
                if not submission.file:
                    continue

                dst_dir = os.path.join(dataset_dir, submission.verified_label)
                try:
                    with local_file(submission.file) as src:
                        if media_type == "image":
                            dst = os.path.join(dst_dir, f"{submission.id}.jpg")
                            shutil.copy2(src, dst)
                            copied += 1

                        elif media_type == "video":
                            extracted = self._extract_frames(src, dst_dir, str(submission.id), submission.verified_label)
                            copied += extracted

                        elif media_type == "audio":
                            spec_path = self._audio_to_spectrogram(src, dst_dir, str(submission.id))
                            if spec_path:
                                copied += 1
                except Exception as exc:
                    self.stderr.write(f"Skipping {submission.id}: {exc}")
                    continue

            for src, label in extra_files:
                dst = os.path.join(dataset_dir, label, f"extra_{copied}_{os.path.basename(src)}")
                os.symlink(os.path.abspath(src), dst)
                copied += 1

            self.stdout.write(f"Prepared {copied} training samples in {dataset_dir}")

            if options["use_cifake"] and media_type == "image":
                self.stdout.write("Loading CIFAKE base dataset...")
                self._load_cifake(dataset_dir)

            self.stdout.write(f"Starting fine-tune ({options['epochs']} epochs)...")
            tmp_model_dir = os.path.join(tmpdir, "model_output")
            self._finetune(dataset_dir, tmp_model_dir, options["epochs"], media_type, options)

            if not os.path.exists(tmp_model_dir):
                self.stderr.write("Fine-tune produced no output. Aborting save.")
                return

            if os.path.exists(persistent_model_dir):
                shutil.rmtree(persistent_model_dir)
            os.makedirs(os.path.dirname(persistent_model_dir), exist_ok=True)
            shutil.copytree(tmp_model_dir, persistent_model_dir)
            self.stdout.write(self.style.SUCCESS(f"Model saved to {persistent_model_dir}"))

    def _extract_frames(self, video_path, dst_dir, submission_id, label):
        try:
            import cv2
        except ImportError:
            self.stderr.write("opencv not installed")
            return 0

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0

        extracted = 0
        frame_idx = 0
        max_frames = 8

        while cap.isOpened() and extracted < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % 30 == 0:
                dst = os.path.join(dst_dir, f"{submission_id}_f{frame_idx}.jpg")
                cv2.imwrite(dst, frame)
                extracted += 1
            frame_idx += 1

        cap.release()
        return extracted

    def _audio_to_spectrogram(self, audio_path, dst_dir, submission_id):
        try:
            import librosa
            import librosa.display
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            self.stderr.write("librosa/matplotlib not installed")
            return None

        try:
            y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=30.0)
            mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
            mel_db = librosa.power_to_db(mel, ref=np.max)

            fig, ax = plt.subplots(figsize=(4, 4))
            librosa.display.specshow(mel_db, sr=sr, ax=ax)
            ax.axis("off")

            dst = os.path.join(dst_dir, f"{submission_id}_spec.png")
            plt.savefig(dst, bbox_inches="tight", pad_inches=0)
            plt.close(fig)
            return dst
        except Exception as exc:
            self.stderr.write(f"Spectrogram failed for {submission_id}: {exc}")
            return None

    def _load_cifake(self, dataset_dir):
        try:
            from datasets import load_dataset
        except ImportError:
            self.stderr.write("datasets not installed, skipping CIFAKE")
            return

        try:
            ds = load_dataset("batgs/CIFAKE", split="train")
            from PIL import Image as PILImage
            max_per_class = 5000
            counts = {"real": 0, "fake": 0}

            for item in ds:
                label = "real" if item["label"] == 0 else "fake"
                if counts[label] >= max_per_class:
                    continue
                img = item["image"]
                if not isinstance(img, PILImage.Image):
                    img = PILImage.fromarray(img)
                dst = os.path.join(dataset_dir, label, f"cifake_{counts[label]}.jpg")
                img.convert("RGB").save(dst, "JPEG")
                counts[label] += 1

            self.stdout.write(f"CIFAKE loaded: {counts}")
        except Exception as exc:
            self.stderr.write(f"CIFAKE load failed: {exc}")

    def _finetune(self, dataset_dir, output_dir, epochs, media_type="image", options=None):
        options = options or {}
        try:
            import torch
            from torch.utils.data import Dataset as TorchDataset
            from transformers import (
                AutoImageProcessor,
                AutoModelForImageClassification,
                Trainer,
                TrainingArguments,
            )
            import numpy as np
            from PIL import Image as PILImage
        except ImportError as e:
            self.stderr.write(f"Missing dependency: {e}")
            return

        base_model = options.get("base_model") or BASE_MODELS[media_type]

        label2id = {"real": 0, "fake": 1}
        id2label = {0: "Real", 1: "AI"}

        samples = []
        for label_name, label_id in label2id.items():
            label_dir = os.path.join(dataset_dir, label_name)
            if not os.path.exists(label_dir):
                continue
            for fname in os.listdir(label_dir):
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    samples.append({"image_path": os.path.join(label_dir, fname), "label": label_id})

        self.stdout.write(f"Total samples: {len(samples)}")

        feature_extractor = AutoImageProcessor.from_pretrained(base_model)
        model = AutoModelForImageClassification.from_pretrained(
            base_model,
            num_labels=2,
            id2label=id2label,
            label2id=label2id,
            ignore_mismatched_sizes=True,
            use_safetensors=True,
        )

        groups = {}
        for item in samples:
            groups.setdefault(_sample_group(item["image_path"]), []).append(item)
        group_keys = sorted(groups)
        random.Random(1337).shuffle(group_keys)

        split_at = max(1, int(len(group_keys) * 0.9))
        train_samples = [s for k in group_keys[:split_at] for s in groups[k]]
        eval_samples = [s for k in group_keys[split_at:] for s in groups[k]]
        if not eval_samples:
            eval_samples = train_samples[-1:]
        self.stdout.write(
            f"Split by source group: {len(group_keys)} groups -> "
            f"{len(train_samples)} train / {len(eval_samples)} eval"
        )

        counts = {label_id: sum(1 for s in train_samples if s["label"] == label_id) for label_id in label2id.values()}
        class_weights = None
        if not options.get("no_class_weights") and all(counts.values()):
            total = sum(counts.values())
            class_weights = torch.tensor(
                [total / (len(counts) * counts[i]) for i in sorted(counts)], dtype=torch.float32
            )
        self.stdout.write(f"Train class counts {counts}, loss weights {class_weights.tolist() if class_weights is not None else 'off'}")

        class LazyImageDataset(TorchDataset):
            """Decodes and preprocesses on __getitem__.

            Materialising every pixel_values tensor up front costs ~600KB per image,
            which OOMs the worker on any realistic dataset size.
            """

            def __len__(self):
                return len(self.items)

            def __init__(self, items, augment=False):
                self.items = items
                self.augment = augment

            def __getitem__(self, idx):
                item = self.items[idx]
                img = PILImage.open(item["image_path"]).convert("RGB")
                if self.augment and random.random() < 0.5:
                    img = img.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
                inputs = feature_extractor(images=img, return_tensors="pt")
                return {
                    "pixel_values": inputs["pixel_values"].squeeze(0),
                    "label": item["label"],
                }

        def compute_metrics(eval_pred):
            logits, labels = eval_pred
            preds = np.argmax(logits, axis=1)
            acc = (preds == labels).mean()
            return {"accuracy": acc}

        batch_size = int(options.get("batch_size") or 16)
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=float(options.get("learning_rate") or 2e-5),
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model="accuracy",
            logging_steps=25,
            remove_unused_columns=False,
            report_to=[],
            use_cpu=os.environ.get("PROOFLAYER_FORCE_CPU") == "1",
            dataloader_num_workers=0,
        )

        class WeightedTrainer(Trainer):
            def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
                labels = inputs.pop("labels")
                outputs = model(**inputs)
                weight = class_weights.to(outputs.logits.device) if class_weights is not None else None
                loss = torch.nn.functional.cross_entropy(outputs.logits, labels, weight=weight)
                return (loss, outputs) if return_outputs else loss

        trainer = WeightedTrainer(
            model=model,
            args=training_args,
            train_dataset=LazyImageDataset(train_samples, augment=True),
            eval_dataset=LazyImageDataset(eval_samples),
            compute_metrics=compute_metrics,
        )

        trainer.train()
        final_eval = trainer.evaluate()
        trainer.save_model(output_dir)
        feature_extractor.save_pretrained(output_dir)
        meta = {
            "base_model": base_model,
            "epochs": epochs,
            "train_counts": {id2label[k]: v for k, v in counts.items()},
            "eval_samples": len(eval_samples),
            "eval_accuracy": float(final_eval.get("eval_accuracy", 0.0)),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": sorted({_source_of(s["image_path"]) for s in train_samples}),
        }
        with open(os.path.join(output_dir, "training_meta.json"), "w") as fh:
            json.dump(meta, fh, indent=2)
        self.stdout.write(f"eval accuracy {meta['eval_accuracy']:.3f} on {len(eval_samples)} held-out")
        self.stdout.write(self.style.SUCCESS(f"Model saved to {output_dir}"))

