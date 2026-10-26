import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy.fft import dctn

STD_LUMA_Q50 = np.array(
    [
        [16, 11, 10, 16, 24, 40, 51, 61],
        [12, 12, 14, 19, 26, 58, 60, 55],
        [14, 13, 16, 24, 40, 57, 69, 56],
        [14, 17, 22, 29, 51, 87, 80, 62],
        [18, 22, 37, 56, 68, 109, 103, 77],
        [24, 35, 55, 64, 81, 104, 113, 92],
        [49, 64, 78, 87, 103, 121, 120, 101],
        [72, 92, 95, 98, 112, 100, 103, 99],
    ],
    dtype=np.float64,
)

NON_JPEG_RESAVE_QUALITY = 100


@dataclass
class LoadedImage:
    rgb: np.ndarray
    source_format: str
    is_jpeg: bool
    jpeg_bytes: bytes
    luma_qtable: np.ndarray
    jpeg_quality: int | None
    resaved: bool
    width: int
    height: int
    extra: dict = field(default_factory=dict)

    def catnet_rgb(self) -> np.ndarray:
        if not self.resaved:
            return self.rgb
        return np.asarray(Image.open(io.BytesIO(self.jpeg_bytes)).convert("RGB"))


def estimate_quality(luma_qtable: np.ndarray) -> int:
    best_q, best_err = 50, float("inf")
    for q in range(1, 101):
        scale = 5000 / q if q < 50 else 200 - 2 * q
        table = np.clip(np.floor((STD_LUMA_Q50 * scale + 50) / 100), 1, 255)
        err = float(np.abs(table - luma_qtable).sum())
        if err < best_err:
            best_q, best_err = q, err
    return best_q


def _luma_qtable(img: Image.Image) -> np.ndarray:
    tables = getattr(img, "quantization", None) or {}
    if 0 not in tables:
        return np.ones((8, 8), dtype=np.float64)
    return np.asarray(tables[0], dtype=np.float64).reshape(8, 8)


def jpeg_bytes_q(rgb: np.ndarray, quality: int, subsampling: int = 0) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality, subsampling=subsampling)
    return buf.getvalue()


def load_image(data: bytes) -> LoadedImage:
    img = Image.open(io.BytesIO(data))
    source_format = (img.format or "").upper()
    if source_format == "MPO":
        source_format = "JPEG"
    is_jpeg = source_format == "JPEG"
    if is_jpeg:
        rgb = np.asarray(img.convert("RGB"))
        qtable = _luma_qtable(img)
        return LoadedImage(
            rgb=rgb,
            source_format=source_format,
            is_jpeg=True,
            jpeg_bytes=data,
            luma_qtable=qtable,
            jpeg_quality=estimate_quality(qtable),
            resaved=False,
            width=rgb.shape[1],
            height=rgb.shape[0],
        )
    rgb = np.asarray(img.convert("RGB"))
    resaved = jpeg_bytes_q(rgb, NON_JPEG_RESAVE_QUALITY, 0)
    reloaded = Image.open(io.BytesIO(resaved))
    return LoadedImage(
        rgb=rgb,
        source_format=source_format,
        is_jpeg=False,
        jpeg_bytes=resaved,
        luma_qtable=_luma_qtable(reloaded),
        jpeg_quality=None,
        resaved=True,
        width=rgb.shape[1],
        height=rgb.shape[0],
    )


def load_path(path: str) -> LoadedImage:
    with open(path, "rb") as fh:
        return load_image(fh.read())


def decoded_luma(jpeg_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(jpeg_bytes))
    img.draft("YCbCr", img.size)
    if img.mode != "YCbCr":
        img = img.convert("YCbCr")
    return np.asarray(img)[:, :, 0].astype(np.float64)


def estimate_luma_coefficients(jpeg_bytes: bytes, qtable: np.ndarray) -> np.ndarray:
    y = decoded_luma(jpeg_bytes)
    h, w = y.shape
    hp, wp = -(-h // 8) * 8, -(-w // 8) * 8
    if (hp, wp) != (h, w):
        y = np.pad(y, ((0, hp - h), (0, wp - w)), mode="edge")
    blocks = (y - 128.0).reshape(hp // 8, 8, wp // 8, 8).transpose(0, 2, 1, 3)
    coefs = dctn(blocks, type=2, axes=(2, 3), norm="ortho")
    quant = np.rint(coefs / qtable[None, None, :, :])
    return quant.transpose(0, 2, 1, 3).reshape(hp, wp).astype(np.int32)


def luminance(rgb: np.ndarray) -> np.ndarray:
    r = rgb[:, :, 0].astype(np.float64)
    g = rgb[:, :, 1].astype(np.float64)
    b = rgb[:, :, 2].astype(np.float64)
    return np.rint(0.299 * r + 0.587 * g + 0.114 * b)
