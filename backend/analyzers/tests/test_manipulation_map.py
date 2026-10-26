import io
import os

import numpy as np
import pytest
import torch
import cv2
from PIL import Image
from scipy import ndimage

from analyzers.manipulation.catnet import catnet_map, dct_volume, load_catnet
from analyzers.manipulation.catnet_net import CATNet
from analyzers.manipulation.copymove import copymove_detect
from analyzers.manipulation.fusion import (
    KIND_COPY_MOVE,
    KIND_INCONSISTENT,
    KIND_JPEG_GRID,
    STATUS_ABSTAIN,
    STATUS_CLEAN,
    STATUS_INCONCLUSIVE,
    STATUS_REGIONS,
    FusionConfig,
    MethodOutputs,
    fuse,
)
from analyzers.manipulation.imageio import estimate_luma_coefficients, load_image, luminance
from analyzers.manipulation.jpeg_grid import compute_votes, log10_binomial_tail, zero_detect
from analyzers.manipulation.regions import components, image_score
from analyzers.manipulation.safire import cosine_kmeans2, point_grid

WEIGHTS = "/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation/weights"


def textured(h: int, w: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, (h, w, 3))
    fine = ndimage.gaussian_filter(base, sigma=(1.2, 1.2, 0)) * 40
    coarse = ndimage.gaussian_filter(rng.normal(0, 1, (h, w, 3)), sigma=(12, 12, 0)) * 400
    yy, xx = np.mgrid[0:h, 0:w]
    ramp = (xx / w * 60 + yy / h * 30)[:, :, None]
    return np.clip(110 + fine + coarse + ramp, 5, 250).astype(np.uint8)


def scene(h: int, w: int, seed: int, noise: float = 3.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.float32) + rng.uniform(60, 180, 3)
    for _ in range(140):
        color = tuple(float(v) for v in rng.uniform(20, 235, 3))
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        if rng.random() < 0.5:
            axes = (int(rng.integers(4, 40)), int(rng.integers(4, 40)))
            cv2.ellipse(img, (x, y), axes, float(rng.uniform(0, 180)), 0, 360, color, -1)
        else:
            cv2.rectangle(img, (x, y), (x + int(rng.integers(4, 50)), y + int(rng.integers(4, 50))), color, -1)
    img = ndimage.gaussian_filter(img, sigma=(0.8, 0.8, 0))
    img += rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def jpeg(rgb: np.ndarray, quality: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def png(rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return buf.getvalue()


def decode(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).copy()


@pytest.fixture(scope="module")
def honest_jpeg_rgb():
    return decode(jpeg(textured(512, 512, 1), 80))


@pytest.fixture(scope="module")
def pasted_foreign_grid(honest_jpeg_rgb):
    donor = decode(jpeg(textured(512, 512, 2), 70))
    img = honest_jpeg_rgb.copy()
    img[101:261, 203:363] = donor[60:220, 61:221]
    mask = np.zeros(img.shape[:2], dtype=bool)
    mask[101:261, 203:363] = True
    return img, mask


@pytest.fixture(scope="module")
def pasted_no_grid(honest_jpeg_rgb):
    donor = scene(512, 512, 3, noise=1.0)
    img = honest_jpeg_rgb.copy()
    img[120:280, 160:320] = donor[120:280, 160:320]
    mask = np.zeros(img.shape[:2], dtype=bool)
    mask[120:280, 160:320] = True
    return img, mask


@pytest.fixture(scope="module")
def copied_patch():
    img = scene(512, 512, 4)
    img[296:392, 328:424] = img[64:160, 40:136]
    target = np.zeros(img.shape[:2], dtype=bool)
    target[296:392, 328:424] = True
    source = np.zeros(img.shape[:2], dtype=bool)
    source[64:160, 40:136] = True
    return img, target, source


def test_quality_estimate_matches_ijg_tables():
    for q in (50, 75, 90, 95):
        img = load_image(jpeg(textured(64, 64, 5), q))
        assert img.is_jpeg
        assert abs(img.jpeg_quality - q) <= 1


def test_non_jpeg_input_is_resaved_at_q100():
    img = load_image(png(textured(64, 64, 6)))
    assert not img.is_jpeg and img.resaved
    assert np.all(img.luma_qtable == 1)


def test_coefficient_estimate_reconstructs_decoded_luma():
    data = jpeg(textured(128, 128, 7), 75)
    img = load_image(data)
    coefs = estimate_luma_coefficients(data, img.luma_qtable)
    assert coefs.shape == (128, 128)
    blocks = coefs.reshape(16, 8, 16, 8).transpose(0, 2, 1, 3) * img.luma_qtable
    assert np.abs(blocks - np.rint(blocks)).max() == 0
    assert (coefs == 0).mean() > 0.5


def test_dct_volume_is_one_hot_and_clipped():
    coefs = np.array([[0, -3, 25], [20, -21, 7]])
    vol = dct_volume(coefs)
    assert vol.shape == (21, 2, 3)
    assert np.all(vol.sum(axis=0) == 1)
    assert vol[20, 0, 2] == 1 and vol[20, 1, 1] == 1 and vol[3, 0, 1] == 1


def test_catnet_architecture_runs_on_cpu_with_random_weights():
    torch.manual_seed(0)
    model = CATNet().eval()
    img = load_image(jpeg(textured(72, 96, 8), 85))
    prob = catnet_map(img, model)
    assert prob.shape == (72, 96)
    assert 0.0 <= prob.min() and prob.max() <= 1.0


def test_binomial_tail_is_monotone_and_bounded():
    a = log10_binomial_tail(1000, 20, 1 / 64)
    b = log10_binomial_tail(1000, 60, 1 / 64)
    assert 0.0 >= a > b
    assert log10_binomial_tail(1000, 0, 1 / 64) == 0.0


def test_zero_votes_follow_the_jpeg_grid(honest_jpeg_rgb):
    from_luma = compute_votes(luminance(honest_jpeg_rgb))
    valid = from_luma[from_luma >= 0]
    assert np.bincount(valid, minlength=64).argmax() == 0


def test_zero_finds_no_region_in_honest_jpeg(honest_jpeg_rgb):
    res = zero_detect(honest_jpeg_rgb)
    assert res.main_grid == 0
    assert not [r for r in res.regions if r.log10_nfa < -2]


def test_zero_finds_no_region_after_aligned_recompression(honest_jpeg_rgb):
    res = zero_detect(decode(jpeg(honest_jpeg_rgb, 75)))
    assert res.main_grid == 0
    assert not [r for r in res.regions if r.log10_nfa < -2]


def test_zero_detects_pasted_patch_with_foreign_grid(pasted_foreign_grid):
    img, mask = pasted_foreign_grid
    res = zero_detect(decode(png(img)))
    foreign = [r for r in res.regions if r.kind == "foreign_grid" and r.log10_nfa < -2]
    assert foreign
    assert (res.foreign_mask & mask).sum() > 0.5 * res.foreign_mask.sum()


def test_zero_detects_pasted_patch_without_grid(pasted_no_grid):
    img, mask = pasted_no_grid
    res = zero_detect(img)
    missing = [r for r in res.regions if r.kind == "missing_grid" and r.log10_nfa < -2]
    assert missing
    assert (res.missing_mask & mask).sum() > 0.5 * res.missing_mask.sum()
    assert missing[0].main_density_outside > 3 * missing[0].main_density_inside


def test_copymove_detects_copied_patch(copied_patch):
    img, target, source = copied_patch
    res = copymove_detect(img)
    assert res.groups and res.groups[0].matches >= 3
    found = res.groups[0].target_mask | res.groups[0].source_mask
    assert (found & (target | source)).sum() > 0.5 * found.sum()
    assert (found & target).sum() > 0.3 * target.sum()
    assert (found & source).sum() > 0.3 * source.sum()


def test_copymove_survives_block_aligned_jpeg_90(copied_patch):
    img, _, _ = copied_patch
    res = copymove_detect(decode(jpeg(img, 90)))
    assert res.groups and res.groups[0].matches >= 2


def test_copymove_silent_on_honest_scenes():
    for seed in (10, 11, 12):
        assert copymove_detect(scene(512, 512, seed)).validated_matches == 0


def test_copymove_silent_on_reencoded_honest_scenes():
    for seed, quality in ((13, 75), (14, 90)):
        assert copymove_detect(decode(jpeg(scene(512, 512, seed), quality))).validated_matches == 0


def test_components_and_image_score():
    prob = np.zeros((200, 200), dtype=np.float32)
    prob[50:100, 60:120] = 0.9
    comps = components(prob)
    assert len(comps) == 1
    assert comps[0].bbox == (60, 50, 120, 100)
    assert image_score(prob) == pytest.approx(0.9, abs=1e-3)
    assert image_score(np.zeros((200, 200), dtype=np.float32)) == 0.0


def test_kmeans_separates_two_directions():
    torch.manual_seed(0)
    a = torch.randn(10, 16) * 0.05 + torch.eye(16)[0]
    b = torch.randn(6, 16) * 0.05 + torch.eye(16)[1]
    labels = cosine_kmeans2(torch.cat([a, b]))
    assert len(set(labels[:10].tolist())) == 1 and len(set(labels[10:].tolist())) == 1
    assert labels[0] != labels[10]
    assert point_grid(8).shape == (64, 2)


def outputs(**kw) -> MethodOutputs:
    base = dict(shape=(200, 300), orig_shape=(800, 1200), is_jpeg=True, jpeg_quality=90)
    base.update(kw)
    return MethodOutputs(**base)


def blob(shape, box, value):
    m = np.zeros(shape, dtype=np.float32)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = value
    return m


CFG = FusionConfig(
    t={"catnet": {"all": 0.8}, "safire": {"all": 0.8}},
    strong={"catnet": {"all": 0.95}, "safire": {"all": 0.95}},
)


def test_fusion_accepts_agreeing_learned_maps():
    out = outputs(catnet=blob((200, 300), (100, 50, 160, 120), 0.9), safire=blob((200, 300), (105, 55, 165, 125), 0.85))
    res = fuse(out, CFG)
    assert res.status == STATUS_REGIONS
    assert res.regions[0].kind == KIND_INCONSISTENT and res.regions[0].confidence == "high"
    x0, y0, x1, y1 = res.regions[0].bbox
    assert 380 <= x0 <= 440 and 180 <= y0 <= 240
    assert res.map.shape == (200, 300) and res.map.max() > 0.8


def test_fusion_ignores_single_map_below_strong_threshold():
    out = outputs(catnet=blob((200, 300), (100, 50, 160, 120), 0.9), safire=np.zeros((200, 300), np.float32))
    res = fuse(out, CFG)
    assert res.status == STATUS_INCONCLUSIVE
    assert not res.regions


def test_fusion_accepts_compact_strong_single_map_as_medium():
    out = outputs(catnet=blob((200, 300), (100, 50, 160, 120), 0.99), safire=np.zeros((200, 300), np.float32))
    res = fuse(out, CFG)
    assert res.status == STATUS_REGIONS and res.regions[0].confidence == "medium"


def test_fusion_reports_clean_when_everything_is_quiet():
    out = outputs(catnet=np.full((200, 300), 0.05, np.float32), safire=np.full((200, 300), 0.1, np.float32))
    res = fuse(out, CFG)
    assert res.status == STATUS_CLEAN and not res.abstain


def test_fusion_abstains_on_global_change():
    out = outputs(catnet=blob((200, 300), (0, 0, 300, 160), 0.99), safire=blob((200, 300), (0, 0, 300, 160), 0.99))
    res = fuse(out, CFG)
    assert res.abstain and res.reason == "global_change"


def test_fusion_abstains_on_small_images_and_ai_verdicts_and_non_photos():
    assert fuse(outputs(orig_shape=(300, 1200)), CFG).reason == "too_small"
    assert fuse(outputs(image_ai_verdict="fake"), CFG).reason == "whole_image_ai"
    res = fuse(outputs(is_photo=False), CFG)
    assert res.status == STATUS_ABSTAIN and res.reason == "not_a_photo"


def test_fusion_accepts_copymove_and_zero_regions():
    t = np.zeros((200, 300), bool)
    t[20:60, 20:60] = True
    s = np.zeros((200, 300), bool)
    s[120:160, 200:240] = True
    z = np.zeros((200, 300), bool)
    z[80:130, 100:150] = True
    out = outputs(
        copymove_groups=[{"matches": 5, "log10_nfa": -9.0, "target_mask": t, "source_mask": s}],
        zero_regions=[
            {"kind": "foreign_grid", "grid": 9, "log10_nfa": -6.0, "mask": z},
            {"kind": "foreign_grid", "grid": 3, "log10_nfa": -1.0, "mask": z},
        ],
    )
    res = fuse(out, CFG)
    kinds = sorted(r.kind for r in res.regions)
    assert kinds == sorted([KIND_COPY_MOVE, KIND_JPEG_GRID])


def test_fusion_rejects_missing_grid_without_contrast():
    z = np.zeros((200, 300), bool)
    z[80:130, 100:150] = True
    region = {"kind": "missing_grid", "grid": 0, "log10_nfa": -50.0, "mask": z, "main_density_inside": 0.2, "main_density_outside": 0.25}
    assert fuse(outputs(zero_regions=[region]), CFG).status != STATUS_REGIONS
    region = dict(region, main_density_inside=0.02, main_density_outside=0.6)
    assert fuse(outputs(zero_regions=[region]), CFG).status == STATUS_REGIONS


def test_fusion_low_quality_jpeg_runs_copymove_only():
    z = np.zeros((200, 300), bool)
    z[80:130, 100:150] = True
    out = outputs(jpeg_quality=60, zero_regions=[{"kind": "foreign_grid", "grid": 9, "log10_nfa": -9.0, "mask": z}])
    res = fuse(out, CFG)
    assert res.status == STATUS_INCONCLUSIVE and res.reason == "low_quality_jpeg"


def test_fusion_marks_region_ai_when_tiles_agree():
    cat = blob((200, 300), (100, 40, 200, 140), 0.9)
    saf = blob((200, 300), (100, 40, 200, 140), 0.9)
    boxes = np.array([[100, 40, 150, 90], [150, 40, 200, 90], [0, 150, 50, 200]])
    out = outputs(catnet=cat, safire=saf, tile_boxes=boxes, tile_scores=np.array([0.9, 0.8, 0.99], np.float32))
    res = fuse(out, FusionConfig(t=CFG.t, strong=CFG.strong, tile_threshold=0.7))
    assert res.regions[0].likely_ai


@pytest.mark.skipif(not os.path.exists(f"{WEIGHTS}/catnet_v2_state.pt"), reason="CAT-Net weights not downloaded")
def test_catnet_real_weights_light_up_pasted_region(pasted_no_grid):
    img, mask = pasted_no_grid
    prob = catnet_map(load_image(png(img)), load_catnet(f"{WEIGHTS}/catnet_v2_state.pt"))
    assert prob[mask].mean() > prob[~mask].mean() + 0.2
