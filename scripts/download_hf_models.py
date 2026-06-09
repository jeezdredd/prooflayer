#!/usr/bin/env python3
"""
Pre-download HuggingFace models into the hf_cache Docker volume.
Run once after deploy:

  docker compose -f deploy/compose.prod.yml exec celery_worker python3 /app/scripts/download_hf_models.py
"""

from transformers import AutoModelForImageClassification, AutoImageProcessor

MODELS = [
    ("Wvolf/ViT_Deepfake_Detection", False),
    ("prithivMLmods/Deep-Fake-Detector-v2-Model", True),
]

for model_id, needs_processor in MODELS:
    print(f"Downloading {model_id} ...")
    AutoModelForImageClassification.from_pretrained(model_id)
    if needs_processor:
        AutoImageProcessor.from_pretrained(model_id)
    print(f"  done")

print("All models cached.")
