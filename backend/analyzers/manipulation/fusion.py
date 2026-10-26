from dataclasses import asdict, dataclass, field

import numpy as np

from analyzers.manipulation.regions import Component, bbox_of, components, image_score, iou, min_area

KIND_COPY_MOVE = "copy_move"
KIND_JPEG_GRID = "jpeg_history"
KIND_INCONSISTENT = "inconsistent"

STATUS_REGIONS = "regions_found"
STATUS_CLEAN = "no_local_edits"
STATUS_INCONCLUSIVE = "inconclusive"
STATUS_ABSTAIN = "abstain"

LEARNED = ("catnet", "safire")


@dataclass
class FusionConfig:
    t: dict = field(default_factory=lambda: {"catnet": {}, "safire": {}})
    strong: dict = field(default_factory=lambda: {"catnet": {}, "safire": {}})
    default_t: float = 0.9
    default_strong: float = 0.98
    pair_iou: float = 0.3
    compact_area: float = 0.25
    compact_solidity: float = 0.5
    max_total_area: float = 0.5
    zero_log10_nfa: float = -2.0
    zero_kinds: tuple = ("foreign_grid", "missing_grid")
    zero_max_area: float = 0.25
    zero_missing_min_outside: float = 0.1
    zero_missing_ratio: float = 3.0
    copymove_min_matches: int = 3
    copymove_min_area_share: float = 0.0005
    tile_threshold: float = 0.5
    tile_min_overlap: float = 0.3
    min_short_side: int = 384
    low_quality: int = 70
    use_zero: bool = True
    use_copymove: bool = True
    use_learned_pair: bool = True
    use_learned_single: bool = True

    def threshold(self, method: str, input_class: str, strong: bool = False) -> float:
        table = self.strong if strong else self.t
        default = self.default_strong if strong else self.default_t
        return float(table.get(method, {}).get(input_class, table.get(method, {}).get("all", default)))


@dataclass
class MethodOutputs:
    shape: tuple[int, int]
    orig_shape: tuple[int, int]
    is_jpeg: bool
    jpeg_quality: int | None
    catnet: np.ndarray | None = None
    safire: np.ndarray | None = None
    zero_regions: list = field(default_factory=list)
    zero_main_grid: int | None = None
    copymove_groups: list = field(default_factory=list)
    tile_boxes: np.ndarray | None = None
    tile_scores: np.ndarray | None = None
    is_photo: bool | None = None
    image_ai_verdict: str | None = None


@dataclass
class Region:
    bbox: tuple[int, int, int, int]
    kind: str
    confidence: str
    methods: list
    score: float
    area_share: float
    likely_ai: bool = False


@dataclass
class ManipulationMap:
    status: str
    abstain: bool
    reason: str
    score: float
    regions: list
    map: np.ndarray | None
    method_scores: dict
    input_class: str

    def summary(self) -> dict:
        out = asdict(self)
        out.pop("map")
        out["regions"] = [asdict(r) if isinstance(r, Region) else r for r in self.regions]
        return out


def input_class_of(out: MethodOutputs, config: FusionConfig) -> str:
    if not out.is_jpeg:
        return "nonjpeg"
    if out.jpeg_quality is not None and out.jpeg_quality < 80:
        return "jpeg_low"
    return "jpeg"


def _scale_bbox(bbox, shape, orig_shape):
    sy = orig_shape[0] / shape[0]
    sx = orig_shape[1] / shape[1]
    x0, y0, x1, y1 = bbox
    return (int(x0 * sx), int(y0 * sy), int(round(x1 * sx)), int(round(y1 * sy)))


def _tiles_ai(mask: np.ndarray, out: MethodOutputs, config: FusionConfig) -> bool:
    if out.tile_boxes is None or out.tile_scores is None or len(out.tile_boxes) == 0:
        return False
    overlapping, high = 0, 0
    for (x0, y0, x1, y1), s in zip(out.tile_boxes, out.tile_scores):
        area = max((x1 - x0) * (y1 - y0), 1)
        share = mask[y0:y1, x0:x1].sum() / area
        if share >= config.tile_min_overlap:
            overlapping += 1
            if s >= config.tile_threshold:
                high += 1
    if overlapping == 0:
        return False
    return high >= min(2, overlapping)


def fuse(out: MethodOutputs, config: FusionConfig) -> ManipulationMap:
    h, w = out.shape
    cls = input_class_of(out, config)
    scores = {}
    for name in LEARNED:
        prob = getattr(out, name)
        if prob is not None:
            scores[name] = image_score(prob, out.orig_shape)
    best_zero = min((r["log10_nfa"] for r in out.zero_regions), default=0.0)
    scores["zero_log10_nfa"] = best_zero
    scores["copymove_matches"] = max((g["matches"] for g in out.copymove_groups), default=0)
    fused_score = _fused_score(scores, cls, config)

    def result(status, reason, regions=None, fmap=None, abstain=False):
        return ManipulationMap(
            status=status,
            abstain=abstain,
            reason=reason,
            score=fused_score,
            regions=regions or [],
            map=fmap,
            method_scores=scores,
            input_class=cls,
        )

    if out.is_photo is False:
        return result(STATUS_ABSTAIN, "not_a_photo", abstain=True)
    if min(out.orig_shape) < config.min_short_side:
        return result(STATUS_ABSTAIN, "too_small", abstain=True)
    if out.image_ai_verdict in ("fake", "likely_fake"):
        return result(STATUS_ABSTAIN, "whole_image_ai", abstain=True)
    low_quality = out.is_jpeg and out.jpeg_quality is not None and out.jpeg_quality < config.low_quality

    accepted: list[tuple[np.ndarray, Region, np.ndarray]] = []
    candidate_area = np.zeros((h, w), dtype=bool)

    if config.use_copymove:
        need = max(1, int(config.copymove_min_area_share * h * w))
        for g in out.copymove_groups:
            if g["matches"] < config.copymove_min_matches:
                continue
            mask = g["target_mask"] | g["source_mask"]
            if g["target_mask"].sum() < need:
                continue
            region = Region(
                bbox=_scale_bbox(bbox_of(mask), out.shape, out.orig_shape),
                kind=KIND_COPY_MOVE,
                confidence="high",
                methods=["copymove"],
                score=float(g["matches"]),
                area_share=float(mask.mean()),
            )
            accepted.append((mask, region, mask.astype(np.float32)))

    if not low_quality:
        if config.use_zero:
            need = min_area((h, w), out.orig_shape)
            for r in out.zero_regions:
                if r["kind"] not in config.zero_kinds or r["log10_nfa"] > config.zero_log10_nfa:
                    continue
                mask = r["mask"]
                if mask.sum() < need or mask.mean() > config.zero_max_area:
                    continue
                if r["kind"] == "missing_grid":
                    outside = r.get("main_density_outside", 0.0)
                    inside = r.get("main_density_inside", 0.0)
                    if outside < config.zero_missing_min_outside or outside < config.zero_missing_ratio * inside:
                        continue
                candidate_area |= mask
                region = Region(
                    bbox=_scale_bbox(bbox_of(mask), out.shape, out.orig_shape),
                    kind=KIND_JPEG_GRID,
                    confidence="high",
                    methods=["zero_" + r["kind"]],
                    score=float(-r["log10_nfa"]),
                    area_share=float(mask.mean()),
                )
                accepted.append((mask, region, mask.astype(np.float32)))

        comps: dict[str, list[Component]] = {}
        for name in LEARNED:
            prob = getattr(out, name)
            if prob is None:
                continue
            t = config.threshold(name, cls)
            comps[name] = [c for c in components(prob, ref_shape=out.orig_shape) if c.score >= t]
            for c in comps[name]:
                candidate_area |= c.mask

        used = {name: set() for name in comps}
        if config.use_learned_pair and "catnet" in comps and "safire" in comps:
            for i, a in enumerate(comps["catnet"]):
                for j, b in enumerate(comps["safire"]):
                    if iou(a.mask, b.mask) >= config.pair_iou:
                        mask = a.mask | b.mask
                        prob = np.maximum(out.catnet * a.mask, out.safire * b.mask)
                        region = Region(
                            bbox=_scale_bbox(bbox_of(mask), out.shape, out.orig_shape),
                            kind=KIND_INCONSISTENT,
                            confidence="high",
                            methods=["catnet", "safire"],
                            score=float((a.score + b.score) / 2),
                            area_share=float(mask.mean()),
                        )
                        accepted.append((mask, region, prob))
                        used["catnet"].add(i)
                        used["safire"].add(j)
        if config.use_learned_single:
            for name, items in comps.items():
                strong = config.threshold(name, cls, strong=True)
                prob_map = getattr(out, name)
                for i, c in enumerate(items):
                    if i in used[name] or c.score < strong:
                        continue
                    if c.area_share > config.compact_area or c.solidity < config.compact_solidity:
                        continue
                    region = Region(
                        bbox=_scale_bbox(c.bbox, out.shape, out.orig_shape),
                        kind=KIND_INCONSISTENT,
                        confidence="medium",
                        methods=[name],
                        score=c.score,
                        area_share=c.area_share,
                    )
                    accepted.append((c.mask, region, prob_map * c.mask))

    for mask, _, _ in accepted:
        candidate_area |= mask
    if candidate_area.mean() > config.max_total_area:
        return result(STATUS_ABSTAIN, "global_change", abstain=True)

    if not accepted:
        ran_all = all(getattr(out, n) is not None for n in LEARNED)
        quiet = all(scores.get(n, 0.0) < config.threshold(n, cls) / 2 for n in LEARNED if n in scores)
        quiet = quiet and best_zero > config.zero_log10_nfa / 2
        if ran_all and quiet and not low_quality:
            return result(STATUS_CLEAN, "no_region_passed")
        return result(STATUS_INCONCLUSIVE, "low_quality_jpeg" if low_quality else "weak_signals")

    fmap = np.zeros((h, w), dtype=np.float32)
    regions = []
    for mask, region, prob in accepted:
        region.likely_ai = region.kind != KIND_COPY_MOVE and _tiles_ai(mask, out, config)
        fmap = np.maximum(fmap, np.clip(prob, 0.0, 1.0))
        regions.append(region)
    regions = _merge_regions(regions)
    return result(STATUS_REGIONS, "regions_accepted", regions=regions, fmap=fmap)


def _box_iou(a, b) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _merge_regions(regions: list[Region]) -> list[Region]:
    rank = {"high": 2, "medium": 1}
    merged: list[Region] = []
    for r in sorted(regions, key=lambda x: (-rank.get(x.confidence, 0), -x.area_share)):
        for m in merged:
            if _box_iou(m.bbox, r.bbox) >= 0.5:
                m.methods = sorted(set(m.methods) | set(r.methods))
                m.likely_ai = m.likely_ai or r.likely_ai
                break
        else:
            merged.append(r)
    return merged


def _fused_score(scores: dict, cls: str, config: FusionConfig) -> float:
    parts = []
    for name in LEARNED:
        if name in scores:
            parts.append(min(1.0, scores[name] / (2 * max(config.threshold(name, cls), 1e-6))))
    if scores.get("zero_log10_nfa", 0.0) < 0:
        parts.append(min(1.0, -scores["zero_log10_nfa"] / (2 * -config.zero_log10_nfa)))
    if scores.get("copymove_matches", 0):
        parts.append(min(1.0, scores["copymove_matches"] / (2 * config.copymove_min_matches)))
    return float(max(parts, default=0.0))
