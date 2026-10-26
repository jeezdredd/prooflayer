import io
import math
from dataclasses import dataclass, field

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image
from scipy import ndimage
from scipy.special import gammaln

from analyzers.manipulation.imageio import luminance

INVALID = -1
NEIGHBOURHOOD_W = 9
ROW_CHUNK = 64
CELL = 3
LOG10E = math.log10(math.e)


def dct_matrix() -> np.ndarray:
    c = np.zeros((8, 8))
    for u in range(8):
        a = math.sqrt(1 / 8) if u == 0 else math.sqrt(2 / 8)
        for k in range(8):
            c[u, k] = a * math.cos((2 * k + 1) * u * math.pi / 16)
    return c


DCT8 = dct_matrix().astype(np.float32)


@dataclass
class GridRegion:
    grid: int
    kind: str
    log10_nfa: float
    bbox: tuple[int, int, int, int]
    pixels: int
    main_density_inside: float = 0.0
    main_density_outside: float = 0.0


@dataclass
class GridResult:
    main_grid: int | None
    main_log10_nfa: float
    main_share: float
    global_grids: list[tuple[int, float]]
    foreign_mask: np.ndarray
    missing_mask: np.ndarray
    regions: list[GridRegion] = field(default_factory=list)
    votes: np.ndarray | None = None


def log10_binomial_tail(n: float, k: float, p: float) -> float:
    if k <= 0:
        return 0.0
    if k > n:
        return -math.inf
    j = np.arange(k, n + 1, 1.0) if n - k < 2_000_000 else np.arange(k, k + 2_000_000, 1.0)
    logs = gammaln(n + 1) - gammaln(j + 1) - gammaln(n - j + 1) + j * math.log(p) + (n - j) * math.log1p(-p)
    m = float(np.max(logs))
    total = m + math.log(float(np.sum(np.exp(logs - m))))
    return min(0.0, total * LOG10E)


def log10_nfa(n_tests_log10: float, n: float, k: float) -> float:
    return n_tests_log10 + log10_binomial_tail(n, k, 1 / 64)


def zero_counts(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w = y.shape
    bh, bw = h - 7, w - 7
    zeros = np.zeros((bh, bw), dtype=np.int8)
    yf = y.astype(np.float32)
    for r0 in range(0, bh, ROW_CHUNK):
        r1 = min(bh, r0 + ROW_CHUNK)
        strip = yf[r0 : r1 + 7]
        vert = sliding_window_view(strip, 8, axis=0) @ DCT8.T
        horiz = sliding_window_view(vert, 8, axis=1)
        coefs = np.einsum("hwul,vl->hwuv", horiz, DCT8, optimize=True)
        small = np.abs(coefs) < 0.5
        count = small.sum(axis=(2, 3), dtype=np.int16) - small[:, :, 0, 0]
        zeros[r0:r1] = count.astype(np.int8)
    yi = y.astype(np.int32)
    hdiff = (yi[:, 1:] != yi[:, :-1]).astype(np.int32)
    vdiff = (yi[1:, :] != yi[:-1, :]).astype(np.int32)
    h_any = _box_sum(hdiff, 8, 7)[:bh, :bw] > 0
    v_any = _box_sum(vdiff, 7, 8)[:bh, :bw] > 0
    constant = ~h_any | ~v_any
    return zeros, constant


def _box_sum(a: np.ndarray, kh: int, kw: int) -> np.ndarray:
    c = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.int64)
    c[1:, 1:] = a.cumsum(0).cumsum(1)
    return c[kh:, kw:] - c[:-kh, kw:] - c[kh:, :-kw] + c[:-kh, :-kw]


def compute_votes(y: np.ndarray) -> np.ndarray:
    h, w = y.shape
    zeros, constant = zero_counts(y)
    bh, bw = zeros.shape
    by, bx = np.mgrid[0:bh, 0:bw]
    grid_of_block = ((by % 8) * 8 + (bx % 8)).astype(np.int32)
    keyed = np.full((h, w), -1, dtype=np.int32)
    keyed[:bh, :bw] = zeros.astype(np.int32) * 128 + constant.astype(np.int32) * 64 + grid_of_block
    best_key = ndimage.maximum_filter(keyed, size=8, origin=3, mode="constant", cval=-1)
    best_zero = np.where(best_key >= 0, best_key // 128, -1).astype(np.int16)
    zpad = np.full((h + 7, w + 7), -1, dtype=np.int16)
    zpad[7 : 7 + bh, 7 : 7 + bw] = zeros
    count = np.zeros((h, w), dtype=np.int16)
    for dy in range(8):
        for dx in range(8):
            count += zpad[7 - dy : 7 - dy + h, 7 - dx : 7 - dx + w] == best_zero
    vote = np.where(best_key >= 0, best_key % 64, INVALID).astype(np.int16)
    is_constant = (best_key % 128) >= 64
    vote[(count != 1) | is_constant | (best_key < 0)] = INVALID
    vote[:7, :] = INVALID
    vote[-7:, :] = INVALID
    vote[:, :7] = INVALID
    vote[:, -7:] = INVALID
    return vote


def _tests_log10(h: int, w: int) -> float:
    return 2 * math.log10(64) + 2 * math.log10(h * w)


def detect_global(votes: np.ndarray, eps_log10: float) -> tuple[int | None, float, list[tuple[int, float]]]:
    h, w = votes.shape
    nt = _tests_log10(h, w)
    valid = votes[votes >= 0]
    counts = np.bincount(valid.astype(np.int64), minlength=64)
    found = []
    for g in range(64):
        lnfa = log10_nfa(nt, h * w / 64, counts[g] / 64)
        if lnfa < eps_log10:
            found.append((g, lnfa))
    if not found:
        return None, 0.0, []
    found.sort(key=lambda t: t[1])
    return found[0][0], found[0][1], found


def detect_regions(
    votes: np.ndarray, grids: list[int], eps_log10: float, kind: str, w_size: int = NEIGHBOURHOOD_W
) -> tuple[np.ndarray, list[GridRegion]]:
    h, w = votes.shape
    nt = _tests_log10(h, w)
    min_size = math.ceil(64 * nt / math.log10(64))
    mask = np.zeros((h, w), dtype=bool)
    regions = []
    cell = CELL
    ch, cw = -(-h // cell), -(-w // cell)
    reach = math.ceil(w_size / cell) - 1
    flat = votes.ravel()
    order = np.argsort(flat, kind="stable")
    sorted_votes = flat[order]
    for g in grids:
        lo = np.searchsorted(sorted_votes, g, side="left")
        hi = np.searchsorted(sorted_votes, g, side="right")
        if hi - lo < min_size:
            continue
        idx = order[lo:hi]
        ys, xs = idx // w, idx % w
        occ = np.zeros((ch, cw), dtype=np.uint8)
        occ[ys // cell, xs // cell] = 1
        if reach > 0:
            occ = ndimage.maximum_filter(occ, size=2 * reach + 1)
        labels, n = ndimage.label(occ, structure=np.ones((3, 3), dtype=bool))
        pl = labels[ys // cell, xs // cell]
        sizes = np.bincount(pl, minlength=n + 1)
        for lab in np.nonzero(sizes >= min_size)[0]:
            if lab == 0:
                continue
            sel = pl == lab
            ry, rx = ys[sel], xs[sel]
            y0, y1, x0, x1 = int(ry.min()), int(ry.max()) + 1, int(rx.min()), int(rx.max()) + 1
            lnfa = log10_nfa(nt, (y1 - y0) * (x1 - x0) / 64, float(sizes[lab]) / 64)
            if lnfa < eps_log10:
                mask[ry, rx] = True
                regions.append(
                    GridRegion(grid=int(g), kind=kind, log10_nfa=float(lnfa), bbox=(x0, y0, x1, y1), pixels=int(sizes[lab]))
                )
    if mask.any():
        mask = ndimage.binary_closing(mask, structure=np.ones((w_size, w_size), dtype=bool))
    return mask, regions


def jpeg99_luminance(rgb: np.ndarray) -> np.ndarray:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=99, subsampling=0)
    return luminance(np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB")))


def zero_detect(rgb: np.ndarray, eps: float = 1.0, keep_votes: bool = False) -> GridResult:
    eps_log10 = math.log10(eps)
    y = luminance(rgb)
    votes = compute_votes(y)
    main, main_nfa, found = detect_global(votes, eps_log10)
    excluded = {main} if main is not None else set()
    foreign, regions = detect_regions(votes, [g for g in range(64) if g not in excluded], eps_log10, "foreign_grid")
    missing = np.zeros_like(foreign)
    if main is not None:
        votes2 = compute_votes(jpeg99_luminance(rgb))
        votes2[votes == main] = INVALID
        missing, regions2 = detect_regions(votes2, [0], eps_log10, "missing_grid")
        is_main = votes == main
        total_main = int(is_main.sum())
        for r in regions2:
            x0, y0, x1, y1 = r.bbox
            area = max((x1 - x0) * (y1 - y0), 1)
            inside = int(is_main[y0:y1, x0:x1].sum())
            r.main_density_inside = inside / area
            r.main_density_outside = (total_main - inside) / max(votes.size - area, 1)
        regions += regions2
    valid = votes >= 0
    main_share = float((votes == main).sum() / max(valid.sum(), 1)) if main is not None else 0.0
    return GridResult(
        main_grid=main,
        main_log10_nfa=main_nfa,
        main_share=main_share,
        global_grids=found,
        foreign_mask=foreign,
        missing_mask=missing,
        regions=regions,
        votes=votes if keep_votes else None,
    )
