import logging
import os
import shutil
import tempfile

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

MEDIA_TYPES = {
    "image": ["image/jpeg", "image/png", "image/webp"],
    "video": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"],
    "audio": ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/flac", "audio/mp4"],
}

HF_REPO = {
    "image": "jeezdredd/prooflayer-image-detector",
    "video": "jeezdredd/prooflayer-video-detector",
    "audio": "jeezdredd/prooflayer-audio-detector",
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
        parser.add_argument("--hf-token", type=str, default=os.environ.get("HF_TOKEN", ""))
        parser.add_argument("--no-push", action="store_true", help="Skip push to HuggingFace Hub")
        parser.add_argument("--use-cifake", action="store_true", help="Include CIFAKE base dataset")

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

        count = qs.count()
        self.stdout.write(f"Found {count} approved {media_type} submissions")

        if count < options["min_samples"]:
            self.stderr.write(
                f"Need at least {options['min_samples']} samples (got {count}). "
                f"Use --min-samples to lower threshold."
            )
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_dir = os.path.join(tmpdir, "dataset")
            os.makedirs(os.path.join(dataset_dir, "real"), exist_ok=True)
            os.makedirs(os.path.join(dataset_dir, "fake"), exist_ok=True)

            copied = 0
            for submission in qs:
                if not submission.file or not os.path.exists(submission.file.path):
                    continue

                src = submission.file.path
                dst_dir = os.path.join(dataset_dir, submission.verified_label)

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

            self.stdout.write(f"Prepared {copied} training samples in {dataset_dir}")

            if options["use_cifake"] and media_type == "image":
                self.stdout.write("Loading CIFAKE base dataset...")
                self._load_cifake(dataset_dir)

            self.stdout.write(f"Starting fine-tune ({options['epochs']} epochs)...")
            model_dir = os.path.join(tmpdir, "model_output")
            self._finetune(dataset_dir, model_dir, options["epochs"])

            if not options["no_push"] and options["hf_token"]:
                self.stdout.write(f"Pushing to {HF_REPO[media_type]}...")
                self._push_to_hub(model_dir, HF_REPO[media_type], options["hf_token"])
                self.stdout.write(self.style.SUCCESS(f"Done. Model at {HF_REPO[media_type]}"))
            else:
                self.stdout.write(f"Model saved locally: {model_dir}")
                self.stdout.write("Use --hf-token to push or --no-push intentional")

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

    def _finetune(self, dataset_dir, output_dir, epochs):
        try:
            import torch
            from datasets import Dataset, Image as HFImage
            from transformers import (
                AutoFeatureExtractor,
                AutoModelForImageClassification,
                Trainer,
                TrainingArguments,
            )
            import numpy as np
            from PIL import Image as PILImage
        except ImportError as e:
            self.stderr.write(f"Missing dependency: {e}")
            return

        media_type = "image"
        base_model = BASE_MODELS[media_type]

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

        feature_extractor = AutoFeatureExtractor.from_pretrained(base_model)
        model = AutoModelForImageClassification.from_pretrained(
            base_model,
            num_labels=2,
            id2label=id2label,
            label2id=label2id,
            ignore_mismatched_sizes=True,
        )

        def preprocess(examples):
            images = [PILImage.open(p).convert("RGB") for p in examples["image_path"]]
            return feature_extractor(images=images, return_tensors="pt")

        import random
        random.shuffle(samples)
        split = int(len(samples) * 0.9)
        train_samples = samples[:split]
        eval_samples = samples[split:]

        def make_dataset(items):
            def gen():
                for item in items:
                    img = PILImage.open(item["image_path"]).convert("RGB")
                    inputs = feature_extractor(images=img, return_tensors="pt")
                    yield {
                        "pixel_values": inputs["pixel_values"].squeeze(0),
                        "label": item["label"],
                    }
            return list(gen())

        train_data = make_dataset(train_samples)
        eval_data = make_dataset(eval_samples)

        import torch
        from torch.utils.data import Dataset as TorchDataset

        class SimpleDataset(TorchDataset):
            def __init__(self, data):
                self.data = data
            def __len__(self):
                return len(self.data)
            def __getitem__(self, idx):
                return self.data[idx]

        def compute_metrics(eval_pred):
            logits, labels = eval_pred
            preds = np.argmax(logits, axis=1)
            acc = (preds == labels).mean()
            return {"accuracy": acc}

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="accuracy",
            logging_steps=50,
            remove_unused_columns=False,
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=SimpleDataset(train_data),
            eval_dataset=SimpleDataset(eval_data),
            compute_metrics=compute_metrics,
        )

        trainer.train()
        trainer.save_model(output_dir)
        feature_extractor.save_pretrained(output_dir)
        self.stdout.write(self.style.SUCCESS(f"Model saved to {output_dir}"))

    def _push_to_hub(self, model_dir, repo_id, token):
        from transformers import AutoModelForImageClassification, AutoFeatureExtractor
        model = AutoModelForImageClassification.from_pretrained(model_dir)
        fe = AutoFeatureExtractor.from_pretrained(model_dir)
        model.push_to_hub(repo_id, token=token)
        fe.push_to_hub(repo_id, token=token)
