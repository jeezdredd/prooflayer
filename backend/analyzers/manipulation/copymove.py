import math
from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy import ndimage
from scipy.stats import chi2

MAX_SIDE = 2048
MAX_KEYPOINTS = 4000
PATCH_N = 6
SIGMA0 = 1.0
MIN_STEP = 1.0
PATCH_SCALE = 1.0
MIN_PAIR_DISTANCE = 16.0
MAX_SATURATED_SHARE = 0.1
MIN_TEXTURE_RATIO = 4.0
LEVELS = 6
POS_TOL = 0.06
POS_TOL_PX = 4.0
DENSE_DIFF = 6.0
HULL_GROW = 2.5


@dataclass
class CopyMoveGroup:
    matches: int
    target_mask: np.ndarray
    source_mask: np.ndarray
    transform: list
    log10_nfa: float


@dataclass
class CopyMoveResult:
    scale: float
    keypoints: int
    validated_matches: int
    groups: list[CopyMoveGroup] = field(default_factory=list)
    tau_level0: float = 0.0


def _work_image(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = rgb.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    if scale < 1.0:
        rgb = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return rgb, scale


def _pyramid(img: np.ndarray) -> list[np.ndarray]:
    levels = [img.astype(np.float32)]
    for _ in range(1, LEVELS):
        if min(levels[-1].shape[:2]) < 16:
            break
        levels.append(cv2.pyrDown(levels[-1]))
    return levels


def _keypoints(rgb: np.ndarray):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sift = cv2.SIFT_create(nfeatures=MAX_KEYPOINTS)
    kps = sift.detect(gray, None)
    if not kps:
        return np.zeros((0, 4), dtype=np.float64)
    arr = np.array([[k.pt[0], k.pt[1], k.size, k.angle] for k in kps], dtype=np.float64)
    _, keep = np.unique(np.round(arr, 2), axis=0, return_index=True)
    return arr[np.sort(keep)]


def _descriptors(levels: list[np.ndarray], kps: np.ndarray):
    n = PATCH_N + 2
    k = len(kps)
    desc = np.zeros((k, 3, PATCH_N, PATCH_N, 2), dtype=np.float32)
    level_of = np.zeros(k, dtype=np.int32)
    ok = np.zeros(k, dtype=bool)
    steps = np.maximum(kps[:, 2] * PATCH_SCALE / (n - 1), MIN_STEP)
    lv = np.clip(np.floor(np.log2(steps)).astype(int), 0, len(levels) - 1)
    offs = (np.arange(n) - (n - 1) / 2.0)
    gy, gx = np.meshgrid(offs, offs, indexing="ij")
    for level in np.unique(lv):
        idx = np.nonzero(lv == level)[0]
        img = levels[level]
        f = 2.0**level
        theta = np.deg2rad(kps[idx, 3])
        c, s = np.cos(theta), np.sin(theta)
        st = (steps[idx] / f)[:, None, None]
        cx = (kps[idx, 0] / f - 0.5 + 0.5 / f)[:, None, None]
        cy = (kps[idx, 1] / f - 0.5 + 0.5 / f)[:, None, None]
        sx = cx + st * (c[:, None, None] * gx[None] - s[:, None, None] * gy[None])
        sy = cy + st * (s[:, None, None] * gx[None] + c[:, None, None] * gy[None])
        hh, ww = img.shape[:2]
        inside = (sx.min(axis=(1, 2)) >= 0) & (sy.min(axis=(1, 2)) >= 0)
        inside &= (sx.max(axis=(1, 2)) <= ww - 1) & (sy.max(axis=(1, 2)) <= hh - 1)
        patches = np.zeros((len(idx), 3, n, n), dtype=np.float32)
        coords = np.stack([sy.ravel(), sx.ravel()])
        for ch in range(3):
            patches[:, ch] = ndimage.map_coordinates(img[:, :, ch], coords, order=1, mode="nearest").reshape(len(idx), n, n)
        gxv = patches[:, :, 1:-1, 2:] - patches[:, :, 1:-1, :-2]
        gyv = patches[:, :, 2:, 1:-1] - patches[:, :, :-2, 1:-1]
        desc[idx] = np.stack([gxv, gyv], axis=-1)
        sat = ((patches >= 250) | (patches <= 5)).mean(axis=(1, 2, 3))
        sigma = SIGMA0 / f
        energy = (gxv**2 + gyv**2).mean(axis=(1, 2, 3)) / 2.0
        textured = energy >= MIN_TEXTURE_RATIO * 2.0 * sigma**2
        ok[idx] = inside & (sat <= MAX_SATURATED_SHARE) & textured
        level_of[idx] = level
    return desc, level_of, ok


def _threshold(n_tests: float, eps: float, entries: int, sigma: float) -> float:
    p = (eps / max(n_tests, 1.0)) ** (1.0 / entries)
    return 2.0 * sigma**2 * float(chi2.ppf(p, df=1))


def _match(desc, level_of, kps, eps):
    k = len(desc)
    flat = desc.reshape(k, -1, 2)
    flipped = desc[:, :, ::-1, :, :].copy()
    flipped[..., 1] = -flipped[..., 1]
    flat_flip = flipped.reshape(k, -1, 2)
    entries = flat.shape[1]
    n_tests = k * (k - 1)
    taus = np.array([_threshold(n_tests, eps, entries, SIGMA0 / 2.0**lv) for lv in range(LEVELS)])
    ii, jj = np.triu_indices(k, 1)
    same_level = level_of[ii] == level_of[jj]
    dist = np.hypot(kps[ii, 0] - kps[jj, 0], kps[ii, 1] - kps[jj, 1])
    far = dist >= np.maximum(MIN_PAIR_DISTANCE, 0.5 * (kps[ii, 2] + kps[jj, 2]))
    keep = same_level & far
    ii, jj = ii[keep], jj[keep]
    out = []
    for variant, other in ((0, flat), (1, flat_flip)):
        ci, cj = ii, jj
        tau = taus[level_of[ci]]
        order = np.argsort(-np.abs(flat).sum(axis=(0, 2)))
        for e in order:
            if len(ci) == 0:
                break
            d = ((flat[ci, e] - other[cj, e]) ** 2).sum(axis=1)
            sel = d <= tau
            ci, cj, tau = ci[sel], cj[sel], tau[sel]
        for a, b in zip(ci.tolist(), cj.tolist()):
            out.append((a, b, variant))
    return out, taus[0]


def _transform_from(kps, a, b, flip):
    ds = kps[b, 2] / kps[a, 2]
    dth = math.radians(kps[b, 3] - kps[a, 3])
    return ds, dth, flip


def _consistent(kps, m1, m2):
    a1, b1, f1 = m1
    for a2, b2 in ((m2[0], m2[1]), (m2[1], m2[0])):
        if m2[2] != f1:
            continue
        if a2 in (a1, b1) or b2 in (a1, b1):
            continue
        va = kps[a2, :2] - kps[a1, :2]
        vb = kps[b2, :2] - kps[b1, :2]
        la, lb = np.hypot(*va), np.hypot(*vb)
        if la < MIN_PAIR_DISTANCE or lb < MIN_PAIR_DISTANCE:
            continue
        ds, dth, _ = _transform_from(kps, a1, b1, f1)
        if abs(lb / la - ds) > 0.15 * ds:
            continue
        ta = (kps[b1, :2] - kps[a1, :2])
        tb = (kps[b2, :2] - kps[a2, :2])
        if f1 == 0 and np.hypot(*(ta - tb)) <= POS_TOL * max(la, lb) + POS_TOL_PX and abs(lb - la) <= POS_TOL * la + POS_TOL_PX:
            return True
        ang_a = math.atan2(va[1], va[0])
        ang_b = math.atan2(vb[1], vb[0])
        diff = (ang_b - ang_a - dth + math.pi) % (2 * math.pi) - math.pi
        if f1 == 0 and abs(diff) < 0.2:
            return True
        if f1 == 1 and abs(lb - la) <= POS_TOL * la + POS_TOL_PX:
            return True
    return False


def _groups(kps, matches):
    n = len(matches)
    if n == 0:
        return []
    adj = [[j for j in range(n) if j != i and _consistent(kps, matches[i], matches[j])] for i in range(n)]
    used = set()
    groups = []
    for i in sorted(range(n), key=lambda t: -len(adj[t])):
        if i in used:
            continue
        members = [i] + [j for j in adj[i] if j not in used]
        for j in members:
            used.add(j)
        groups.append(members)
    return groups


def _oriented_points(kps, matches, members):
    a0, b0, _ = matches[members[0]]
    src, dst = [kps[a0, :2]], [kps[b0, :2]]
    for idx in members[1:]:
        a, b, _ = matches[idx]
        da = np.hypot(*(kps[a, :2] - kps[a0, :2])) + np.hypot(*(kps[b, :2] - kps[b0, :2]))
        db = np.hypot(*(kps[b, :2] - kps[a0, :2])) + np.hypot(*(kps[a, :2] - kps[b0, :2]))
        if db < da:
            a, b = b, a
        src.append(kps[a, :2])
        dst.append(kps[b, :2])
    return np.array(src, dtype=np.float32), np.array(dst, dtype=np.float32)


def _region_masks(rgb, kps, matches, members):
    h, w = rgb.shape[:2]
    src, dst = _oriented_points(kps, matches, members)
    a0, b0, flip = matches[members[0]]
    if len(src) >= 3:
        m, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    else:
        m = None
    if m is None:
        ds, dth, _ = _transform_from(kps, a0, b0, flip)
        c, s = ds * math.cos(dth), ds * math.sin(dth)
        rot = np.array([[c, -s], [s, c]], dtype=np.float64)
        t = kps[b0, :2] - rot @ kps[a0, :2]
        m = np.hstack([rot, t[:, None]]).astype(np.float64)
    m = np.asarray(m, dtype=np.float64)
    radius = float(np.median(kps[[matches[i][0] for i in members], 2])) * HULL_GROW
    img = rgb.astype(np.float32)
    warped = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(-1000, -1000, -1000))
    diff = np.abs(img - warped).mean(axis=2)
    diff = cv2.blur(diff, (5, 5))
    similar = diff <= DENSE_DIFF
    hull_t = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(hull_t, cv2.convexHull(dst.astype(np.int32)), 1)
    for p in dst:
        cv2.circle(hull_t, (int(p[0]), int(p[1])), int(max(radius, 4)), 1, -1)
    hull_t = cv2.dilate(hull_t, np.ones((3, 3), np.uint8), iterations=int(max(radius, 4)))
    target = similar & (hull_t > 0)
    lab, n = ndimage.label(target)
    if n:
        seeds = {int(lab[int(min(max(p[1], 0), h - 1)), int(min(max(p[0], 0), w - 1))]) for p in dst}
        seeds.discard(0)
        target = np.isin(lab, list(seeds)) if seeds else np.zeros_like(target)
    inv = cv2.invertAffineTransform(m)
    source = cv2.warpAffine(target.astype(np.uint8), inv, (w, h), flags=cv2.INTER_NEAREST) > 0
    return target, source, m.tolist()


def copymove_detect(rgb: np.ndarray, eps: float = 0.01, min_matches: int = 2) -> CopyMoveResult:
    work, scale = _work_image(rgb)
    kps = _keypoints(work)
    result = CopyMoveResult(scale=scale, keypoints=len(kps), validated_matches=0)
    if len(kps) < 2:
        return result
    levels = _pyramid(work)
    desc, level_of, ok = _descriptors(levels, kps)
    sel = np.nonzero(ok)[0]
    if len(sel) < 2:
        return result
    kps_ok, desc_ok, lv_ok = kps[sel], desc[sel], level_of[sel]
    matches, tau0 = _match(desc_ok, lv_ok, kps_ok, eps)
    result.validated_matches = len(matches)
    result.tau_level0 = tau0
    h0, w0 = rgb.shape[:2]
    for members in _groups(kps_ok, matches):
        if len(members) < min_matches:
            continue
        target, source, m = _region_masks(work, kps_ok, matches, members)
        if scale < 1.0:
            target = cv2.resize(target.astype(np.uint8), (w0, h0), interpolation=cv2.INTER_NEAREST) > 0
            source = cv2.resize(source.astype(np.uint8), (w0, h0), interpolation=cv2.INTER_NEAREST) > 0
        k = len(kps_ok)
        lnfa = math.log10(max(k * (k - 1), 1)) + len(members) * math.log10(eps / max(k * (k - 1), 1))
        result.groups.append(CopyMoveGroup(matches=len(members), target_mask=target, source_mask=source, transform=m, log10_nfa=lnfa))
    result.groups.sort(key=lambda g: -g.matches)
    return result
