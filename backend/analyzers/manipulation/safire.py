from dataclasses import dataclass

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from analyzers.manipulation.safire_net import IMG_SIZE, SafireModel

POINTS_PER_SIDE = 16
POINTS_PER_BATCH = 64
KMEANS_ITERS = 50

_models: dict[str, SafireModel] = {}


@dataclass
class SafireOutput:
    prob: np.ndarray
    front_area: float
    back_area: float
    cluster_distance: float
    front_iou: float
    back_iou: float
    single_cluster: bool


def load_safire(weights_path: str) -> SafireModel:
    if weights_path not in _models:
        model = SafireModel()
        state = torch.load(weights_path, map_location="cpu", weights_only=True)
        missing, unexpected = model.load_state_dict(state, strict=False)
        bad = [k for k in missing if not k.startswith(("pixel_mean", "pixel_std"))]
        if bad or unexpected:
            raise RuntimeError(f"safire weights mismatch: missing={bad[:5]} unexpected={list(unexpected)[:5]}")
        _models[weights_path] = model.eval()
    return _models[weights_path]


def point_grid(n: int) -> np.ndarray:
    offset = 1 / (2 * n)
    side = np.linspace(offset, 1 - offset, n)
    xs = np.tile(side[None, :], (n, 1))
    ys = np.tile(side[:, None], (1, n))
    return np.stack([xs, ys], axis=-1).reshape(-1, 2) * IMG_SIZE


def cosine_kmeans2(x: torch.Tensor, iters: int = KMEANS_ITERS) -> torch.Tensor:
    xn = F.normalize(x, dim=1)
    mean = F.normalize(xn.mean(0, keepdim=True), dim=1)
    first = int(torch.argmin(xn @ mean.T))
    second = int(torch.argmin(xn @ xn[first : first + 1].T))
    centers = torch.stack([xn[first], xn[second]])
    labels = torch.zeros(x.shape[0], dtype=torch.long)
    for _ in range(iters):
        new_labels = torch.argmax(xn @ centers.T, dim=1)
        if torch.equal(new_labels, labels) and _ > 0:
            break
        labels = new_labels
        for c in range(2):
            sel = xn[labels == c]
            if len(sel):
                centers[c] = F.normalize(sel.mean(0), dim=0)
    return labels


@torch.inference_mode()
def safire_predict(rgb: np.ndarray, model: SafireModel, points_per_side: int = POINTS_PER_SIDE) -> SafireOutput:
    h, w = rgb.shape[:2]
    img = cv2.resize(rgb, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)
    x = torch.from_numpy(img).permute(2, 0, 1).contiguous().float()[None]
    features = model.encode(x)
    pts = torch.from_numpy(point_grid(points_per_side)).float()
    logits_list, iou_list = [], []
    for start in range(0, len(pts), POINTS_PER_BATCH):
        masks, iou = model.decode_points(features, pts[start : start + POINTS_PER_BATCH])
        logits_list.append(masks[:, 0])
        iou_list.append(iou[:, 0])
    logits = torch.cat(logits_list)
    ious = torch.cat(iou_list)
    fh, fw = features.shape[-2:]
    seg_feat = F.interpolate(logits[:, None], size=(fh, fw), mode="nearest")[:, 0] > 0
    areas = (logits > 0).float().mean(dim=(1, 2))
    feats = features[0].reshape(features.shape[1], -1)
    avg = []
    for i in range(len(logits)):
        m = seg_feat[i].reshape(-1)
        if bool(m.any()):
            avg.append(feats[:, m].mean(dim=1))
        else:
            px = int(pts[i, 0] / IMG_SIZE * fw)
            py = int(pts[i, 1] / IMG_SIZE * fh)
            avg.append(features[0, :, min(py, fh - 1), min(px, fw - 1)])
    avg = torch.stack(avg)
    labels = cosine_kmeans2(avg)
    groups = [torch.nonzero(labels == c).flatten() for c in range(2)]
    nonempty = [g for g in groups if len(g)]
    if len(nonempty) == 1:
        idx = nonempty[0][torch.argmax(ious[nonempty[0]])]
        low = torch.sigmoid(logits[idx])
        out = SafireOutput(
            prob=_upscale(low, h, w),
            front_area=float(areas[idx]),
            back_area=float(areas[idx]),
            cluster_distance=0.0,
            front_iou=float(ious[idx]),
            back_iou=float(ious[idx]),
            single_cluster=True,
        )
        return out
    best = [g[torch.argmax(ious[g])] for g in groups]
    if areas[best[0]] > areas[best[1]]:
        back, front = best[0], best[1]
    else:
        back, front = best[1], best[0]
    low = (torch.sigmoid(logits[front]) + 1 - torch.sigmoid(logits[back])) / 2
    c0 = F.normalize(avg[labels == 0].mean(0), dim=0)
    c1 = F.normalize(avg[labels == 1].mean(0), dim=0)
    return SafireOutput(
        prob=_upscale(low, h, w),
        front_area=float(areas[front]),
        back_area=float(areas[back]),
        cluster_distance=float(1 - (c0 @ c1)),
        front_iou=float(ious[front]),
        back_iou=float(ious[back]),
        single_cluster=False,
    )


def _upscale(low: torch.Tensor, h: int, w: int) -> np.ndarray:
    full = F.interpolate(low[None, None], size=(IMG_SIZE, IMG_SIZE), mode="bilinear", align_corners=False)
    full = F.interpolate(full, size=(h, w), mode="bilinear", align_corners=False)
    return full[0, 0].numpy().astype(np.float32)
