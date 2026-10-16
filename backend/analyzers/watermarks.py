import cv2
import numpy as np

DWT_DCT_SCALE = 36
DWT_DCT_BLOCK = 4
MIN_SIDE = 256
DAMAGED_MATCH = 0.8
DAMAGED_MIN_BITS = 46


def _bits(value: int) -> list[int]:
    return [int(b) for b in bin(value)[2:]]


def _byte_bits(data: bytes) -> list[int]:
    return [int(b) for byte in data for b in f"{byte:08b}"]


KNOWN_WATERMARKS = (
    {"name": "Stable Diffusion XL", "vendor": "Stability AI", "bits": _bits(0b101100111110110010010000011110111011000110011110), "min_match": 0.9},
    {"name": "FLUX.1", "vendor": "Black Forest Labs", "bits": _bits(0b001010101111111010000111100111001111010100101110), "min_match": 0.9},
    {"name": "Stable Diffusion 1.x", "vendor": "Stability AI", "bits": _byte_bits(b"StableDiffusionV1"), "min_match": 0.9},
    {"name": "Stable Diffusion 2.x", "vendor": "Stability AI", "bits": _byte_bits(b"SDV2"), "min_match": 0.97},
)


def _haar_ll(channel: np.ndarray) -> np.ndarray:
    x = channel.astype(np.float64)
    return (x[0::2, 0::2] + x[0::2, 1::2] + x[1::2, 0::2] + x[1::2, 1::2]) / 2.0


def _block_bits(bgr: np.ndarray) -> np.ndarray:
    rows, cols = bgr.shape[:2]
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
    ll = _haar_ll(yuv[: rows // 4 * 4, : cols // 4 * 4, 1])
    b = DWT_DCT_BLOCK
    br, bc = ll.shape[0] // b, ll.shape[1] // b
    blocks = ll[: br * b, : bc * b].reshape(br, b, bc, b).transpose(0, 2, 1, 3).reshape(br * bc, b * b)
    pos = np.argmax(np.abs(blocks[:, 1:]), axis=1) + 1
    values = np.abs(blocks[np.arange(len(blocks)), pos])
    return (values % DWT_DCT_SCALE > 0.5 * DWT_DCT_SCALE).astype(np.float64)


def _decode(per_block: np.ndarray, length: int) -> list[int]:
    index = np.arange(len(per_block)) % length
    return [int(per_block[index == i].mean() * 255 > 127) for i in range(length)]


def decode_dwt_dct(bgr: np.ndarray, length: int) -> list[int]:
    return _decode(_block_bits(bgr), length)


def find_known_watermark(path: str) -> dict | None:
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None or min(bgr.shape[:2]) < MIN_SIDE:
        return None
    per_block = _block_bits(bgr)
    best = None
    for mark in KNOWN_WATERMARKS:
        length = len(mark["bits"])
        if len(per_block) < length:
            continue
        decoded = _decode(per_block, length)
        match = sum(a == b for a, b in zip(decoded, mark["bits"])) / length
        if match >= mark["min_match"]:
            state = "intact"
        elif match >= DAMAGED_MATCH and length >= DAMAGED_MIN_BITS:
            state = "damaged"
        else:
            continue
        if best is None or match > best["match"]:
            best = {"name": mark["name"], "vendor": mark["vendor"], "match": round(match, 3), "bits": length, "state": state}
    return best
