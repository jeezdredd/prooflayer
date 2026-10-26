import io
import re
import struct

import numpy as np
from PIL import Image

GAINMAP_MIN_GRAD_CORR = 0.30
GAINMAP_MAX_ASPECT_DELTA = 0.03
GAINMAP_MIN_STD = 1.0
THUMB_MISMATCH_CORR = 0.5
MAKERNOTE_MIN_BYTES = 256
PREVIEW_SIDE = 512
COMPARE_WIDTH = 256
MP_UNDEFINED = 0x000000
XMP_PREFIX = b"http://ns.adobe.com/xap/1.0/"
GAINMAP_XMP = re.compile(r"urn:com:apple:photo:20\d\d:aux:hdrgainmap|hdrgm:|ns\.adobe\.com/hdr-gain-map", re.IGNORECASE)


def _u16(data: bytes, off: int, bo: str) -> int:
    return struct.unpack_from(bo + "H", data, off)[0]


def _u32(data: bytes, off: int, bo: str) -> int:
    return struct.unpack_from(bo + "I", data, off)[0]


def segments(data: bytes) -> list[tuple[int, int, bytes]]:
    out = []
    if data[:2] != b"\xff\xd8":
        return out
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            return out
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker == 0xD8 or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            i += 2
            continue
        if marker in (0xD9, 0xDA):
            return out
        length = _u16(data, i + 2, ">")
        out.append((marker, i, data[i + 4:i + 2 + length]))
        i += 2 + length
    return out


def _ifd(tiff: bytes, off: int, bo: str) -> tuple[dict, int]:
    entries = {}
    if off <= 0 or off + 2 > len(tiff):
        return entries, 0
    count = _u16(tiff, off, bo)
    if count > 1000:
        return entries, 0
    for k in range(count):
        e = off + 2 + 12 * k
        if e + 12 > len(tiff):
            break
        tag, typ, cnt = struct.unpack_from(bo + "HHI", tiff, e)
        entries[tag] = (typ, cnt, e + 8)
    nxt = off + 2 + 12 * count
    return entries, _u32(tiff, nxt, bo) if nxt + 4 <= len(tiff) else 0


def _int(tiff: bytes, entry, bo: str) -> int | None:
    typ, _cnt, value_off = entry
    if typ == 3:
        return _u16(tiff, value_off, bo)
    if typ == 4:
        return _u32(tiff, value_off, bo)
    return None


def _bytes(tiff: bytes, entry, bo: str) -> bytes:
    typ, cnt, value_off = entry
    size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1}.get(typ, 1) * cnt
    if size <= 4:
        return tiff[value_off:value_off + size]
    ptr = _u32(tiff, value_off, bo)
    return tiff[ptr:ptr + size]


def parse_exif(payload: bytes) -> dict:
    tiff = payload[6:]
    if len(tiff) < 8 or tiff[:2] not in (b"MM", b"II"):
        return {}
    bo = ">" if tiff[:2] == b"MM" else "<"
    ifd0, ifd1_off = _ifd(tiff, _u32(tiff, 4, bo), bo)
    exif = {}
    if 0x8769 in ifd0:
        exif, _ = _ifd(tiff, _int(tiff, ifd0[0x8769], bo) or 0, bo)
    out = {"makernote": b""}
    if 0x927C in exif:
        out["makernote"] = _bytes(tiff, exif[0x927C], bo)
    if 0xA002 in exif and 0xA003 in exif:
        out["pixels"] = (_int(tiff, exif[0xA002], bo), _int(tiff, exif[0xA003], bo))
    if ifd1_off:
        ifd1, _ = _ifd(tiff, ifd1_off, bo)
        if 0x0201 in ifd1 and 0x0202 in ifd1:
            start = _int(tiff, ifd1[0x0201], bo) or 0
            thumb = tiff[start:start + (_int(tiff, ifd1[0x0202], bo) or 0)]
            if thumb[:2] == b"\xff\xd8":
                out["thumb"] = thumb
    return out


def parse_mpf(payload: bytes, base: int) -> list[dict]:
    tiff = payload[4:]
    if len(tiff) < 8 or tiff[:2] not in (b"MM", b"II"):
        return []
    bo = ">" if tiff[:2] == b"MM" else "<"
    ifd, _ = _ifd(tiff, _u32(tiff, 4, bo), bo)
    if 0xB002 not in ifd:
        return []
    raw = _bytes(tiff, ifd[0xB002], bo)
    images = []
    for k in range(len(raw) // 16):
        attr, size, off, _d1, _d2 = struct.unpack_from(bo + "IIIHH", raw, 16 * k)
        images.append({"type": attr & 0xFFFFFF, "size": size, "offset": 0 if off == 0 else base + off})
    return images


def _gray(img: Image.Image, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(img.convert("L").resize(size, Image.Resampling.BILINEAR), dtype=np.float64)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else 0.0


def _grad(a: np.ndarray) -> np.ndarray:
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    return np.hypot(gx, gy)


def _preview(data: bytes) -> Image.Image | None:
    try:
        img = Image.open(io.BytesIO(data))
        img.draft("RGB", (max(img.width // 8, PREVIEW_SIDE), max(img.height // 8, PREVIEW_SIDE)))
        img = img.convert("RGB")
        img.thumbnail((PREVIEW_SIDE * 2, PREVIEW_SIDE * 2))
        return img
    except Exception:
        return None


def _oriented(preview: Image.Image, other: Image.Image) -> Image.Image:
    if (other.width < other.height) != (preview.width < preview.height):
        return preview.rotate(90, expand=True)
    return preview


def thumb_corr(thumb: bytes, preview: Image.Image) -> float | None:
    try:
        t = Image.open(io.BytesIO(thumb)).convert("RGB")
    except Exception:
        return None
    base = _oriented(preview, t)
    size = (t.width, t.height)
    best = _corr(_gray(t, size), _gray(base, size))
    ta = t.width / t.height
    if abs(ta - base.width / base.height) > 0.05:
        crop_w = int(round(base.height * ta))
        if 0 < crop_w <= base.width:
            left = (base.width - crop_w) // 2
            box = (left, 0, left + crop_w, base.height)
        else:
            crop_h = int(round(base.width / ta))
            top = (base.height - crop_h) // 2
            box = (0, top, base.width, top + crop_h)
        best = max(best, _corr(_gray(t, size), _gray(base.crop(box), size)))
    return best


def gainmap_state(chunk: bytes, mp_type: int, preview: Image.Image) -> str:
    if chunk[:2] != b"\xff\xd8":
        return "broken"
    xmp = b"".join(p for m, _o, p in segments(chunk) if m == 0xE1 and p.startswith(XMP_PREFIX))
    if mp_type != MP_UNDEFINED and not GAINMAP_XMP.search(xmp.decode("utf-8", errors="replace")):
        return "none"
    try:
        img = Image.open(io.BytesIO(chunk))
        img.load()
    except Exception:
        return "broken"
    if img.width < 32 or img.height < 32:
        return "broken"
    base = _oriented(preview, img)
    aspect = img.width / img.height
    main_aspect = base.width / base.height
    if abs(aspect - main_aspect) / main_aspect > GAINMAP_MAX_ASPECT_DELTA:
        return "misaligned"
    best = 0.0
    std = 0.0
    for width in (min(img.width, COMPARE_WIDTH), 128):
        size = (width, max(1, int(round(width / aspect))))
        g = _gray(img, size)
        std = max(std, float(g.std()))
        best = max(best, _corr(_grad(g), _grad(_gray(base, size))))
    if std < GAINMAP_MIN_STD:
        return "flat"
    return "aligned" if best >= GAINMAP_MIN_GRAD_CORR else "misaligned"


def inspect(path: str) -> dict | None:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    segs = segments(data)
    if not segs:
        return None
    exif = {}
    images = []
    size = None
    for marker, offset, payload in segs:
        if marker == 0xE1 and payload.startswith(b"Exif\x00") and not exif:
            exif = parse_exif(payload)
        elif marker == 0xE2 and payload.startswith(b"MPF\x00"):
            images = parse_mpf(payload, offset + 8)
        elif marker in (0xC0, 0xC1, 0xC2) and len(payload) >= 5:
            size = (_u16(payload, 3, ">"), _u16(payload, 1, ">"))
    preview = _preview(data)
    makernote = exif.get("makernote", b"")
    pixels = exif.get("pixels")
    out = {
        "mpo": len(images) > 1,
        "makernote": len(makernote) >= MAKERNOTE_MIN_BYTES,
        "dims_ok": not (pixels and size and pixels not in (size, size[::-1])),
        "thumb_mismatch": False,
        "gainmap": "none",
    }
    if preview is None:
        return out
    if exif.get("thumb"):
        corr = thumb_corr(exif["thumb"], preview)
        out["thumb_mismatch"] = corr is not None and corr < THUMB_MISMATCH_CORR
    for image in images[1:]:
        chunk = data[image["offset"]:image["offset"] + image["size"]]
        state = gainmap_state(chunk, image["type"], preview)
        if state == "aligned":
            out["gainmap"] = state
            break
        if state != "none" and out["gainmap"] == "none":
            out["gainmap"] = state
    return out


def camera_level(structure: dict | None, camera_exif: bool) -> int:
    if not structure or not camera_exif:
        return 0
    clean = structure["dims_ok"] and not structure["thumb_mismatch"]
    if structure["gainmap"] == "aligned" and clean:
        return 3
    if structure["makernote"] and clean:
        return 2
    return 1
