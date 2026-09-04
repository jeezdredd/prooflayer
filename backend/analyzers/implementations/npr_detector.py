import gc
import hashlib
import logging
import os
import tempfile

import requests
import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn

from analyzers._device import get_device, to_device
from analyzers.base import AnalysisOutput, BaseAnalyzer

logger = logging.getLogger(__name__)

WEIGHTS_URL = "https://raw.githubusercontent.com/chuangchuangtan/NPR-DeepfakeDetection/main/model_epoch_last_3090.pth"
WEIGHTS_SHA256 = "b67a91555ce786a6d0463ff0cb2b0b874d1c3f971b0e3febd2ae5618a80f7e8a"
WEIGHTS_FILENAME = "npr_model_epoch_last_3090.pth"
WEIGHTS_CACHE_SUBDIR = "prooflayer-npr"
DOWNLOAD_TIMEOUT = 120

MAX_SIDE = 1024
NPR_INPUT_SCALE = 2.0 / 3.0
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

_state = {"model": None}


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes: int, planes: int, stride: int = 1, downsample: nn.Module | None = None):
        super().__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):
        identity = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        if self.downsample is not None:
            identity = self.downsample(x)
        return self.relu(out + identity)


def npr_residual(x: torch.Tensor) -> torch.Tensor:
    """Neighboring Pixel Relationships: what nearest-neighbour 2x down/up-sampling cannot reproduce."""
    down = F.interpolate(x, scale_factor=0.5, mode="nearest", recompute_scale_factor=True)
    up = F.interpolate(down, scale_factor=2.0, mode="nearest", recompute_scale_factor=True)
    return x - up


class NPRNet(nn.Module):
    """ResNet-50 stem + layer1 + layer2 over the NPR residual, as released by Tan et al. (CVPR 2024)."""

    def __init__(self):
        super().__init__()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=2, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(64, 3)
        self.layer2 = self._make_layer(128, 4, stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc1 = nn.Linear(512, 1)

    def _make_layer(self, planes: int, blocks: int, stride: int = 1) -> nn.Sequential:
        downsample = None
        out_planes = planes * Bottleneck.expansion
        if stride != 1 or self.inplanes != out_planes:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, out_planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_planes),
            )
        layers = [Bottleneck(self.inplanes, planes, stride, downsample)]
        self.inplanes = out_planes
        for _ in range(1, blocks):
            layers.append(Bottleneck(self.inplanes, planes))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(npr_residual(x) * NPR_INPUT_SCALE)
        x = self.maxpool(self.relu(self.bn1(x)))
        x = self.layer2(self.layer1(x))
        x = torch.flatten(self.avgpool(x), 1)
        return self.fc1(x)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weights_path() -> str:
    override = os.environ.get("NPR_WEIGHTS_PATH")
    if override:
        return override
    hf_home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return os.path.join(hf_home, WEIGHTS_CACHE_SUBDIR, WEIGHTS_FILENAME)


def _download(dest: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest), suffix=".part")
    os.close(fd)
    try:
        with requests.get(WEIGHTS_URL, stream=True, timeout=DOWNLOAD_TIMEOUT) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        actual = _sha256(tmp)
        if actual != WEIGHTS_SHA256:
            raise RuntimeError(f"NPR weights sha256 mismatch: expected {WEIGHTS_SHA256[:12]}, got {actual[:12]}")
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def ensure_weights() -> str:
    path = weights_path()
    if os.path.exists(path):
        if os.environ.get("NPR_WEIGHTS_PATH") or _sha256(path) == WEIGHTS_SHA256:
            return path
        logger.warning("NPR weights at %s failed checksum, re-downloading", path)
        os.unlink(path)
    logger.info("downloading NPR weights to %s", path)
    _download(path)
    return path


def _load():
    if _state["model"] is None:
        path = ensure_weights()
        state_dict = torch.load(path, map_location="cpu", weights_only=True)
        state_dict = {k.removeprefix("module."): v for k, v in state_dict.items()}
        model = NPRNet()
        model.load_state_dict(state_dict, strict=True)
        _state["model"] = to_device(model.eval())
        logger.info("npr_detector loaded %s on %s", os.path.basename(path), get_device())
    return _state["model"]


def _center_crop(image: Image.Image, max_side: int) -> Image.Image:
    w, h = image.size
    if w <= max_side and h <= max_side:
        return image
    cw, ch = min(w, max_side), min(h, max_side)
    left, top = (w - cw) // 2, (h - ch) // 2
    return image.crop((left, top, left + cw, top + ch))


def prepare(image: Image.Image) -> tuple[torch.Tensor, dict]:
    original = image.size
    image = _center_crop(image.convert("RGB"), MAX_SIDE)
    w, h = image.size
    w -= w % 2
    h -= h % 2
    if (w, h) != image.size:
        image = image.crop((0, 0, w, h))
    arr = torch.frombuffer(bytearray(image.tobytes()), dtype=torch.uint8).view(h, w, 3)
    x = arr.permute(2, 0, 1).float().div_(255.0)
    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)
    x = (x - mean) / std
    info = {"width": original[0], "height": original[1], "analysed_width": w, "analysed_height": h,
            "cropped": (w, h) != original}
    return x.unsqueeze(0), info


class NPRDetector(BaseAnalyzer):
    name = "npr_detector"
    version = "2.0.0"

    def supported_mime_types(self) -> list[str]:
        return ["image/jpeg", "image/png", "image/webp"]

    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput:
        try:
            image = Image.open(file_path)
            image.load()
        except Exception as exc:
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": f"cannot open image: {exc}"})

        try:
            model = _load()
            x, info = prepare(image)
            x = x.to(get_device())
            with torch.no_grad():
                logit = model(x).squeeze().float().cpu()
            ai_prob = float(torch.sigmoid(logit).item())
        except Exception as exc:
            logger.warning("npr_detector inference failed: %s", exc)
            return AnalysisOutput(confidence=0.0, verdict="error", evidence={"error": str(exc)})
        finally:
            gc.collect()

        evidence = {
            "model": "NPR ResNet (Tan et al., CVPR 2024)",
            "weights_sha256": WEIGHTS_SHA256[:12],
            "ai_probability": round(ai_prob, 4),
            "logit": round(float(logit), 4),
            "input": info,
            "training_corpus": "ProGAN 4-class (CNNDetection); authors report 92.2% mean acc over 28 generators",
        }

        if ai_prob >= 0.85:
            confidence, verdict = 0.8, "fake"
        elif ai_prob >= 0.65:
            confidence, verdict = 0.6, "suspicious"
        elif ai_prob < 0.15:
            confidence, verdict = 0.8, "authentic"
        elif ai_prob < 0.35:
            confidence, verdict = 0.6, "authentic"
        else:
            confidence, verdict = 0.4, "inconclusive"

        return AnalysisOutput(confidence=confidence, verdict=verdict, evidence=evidence)
