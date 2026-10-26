import argparse
import gzip
import json
import pickle
import resource
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from analyzers.manipulation.ai_tiles import load_tile_model
from analyzers.manipulation.catnet import load_catnet
from analyzers.manipulation.imageio import load_path
from analyzers.manipulation.pipeline import Models, run_methods
from analyzers.manipulation.safire import load_safire

ROOT = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation")
WEIGHTS = ROOT / "weights"


def pack(raw) -> dict:
    o = raw.outputs
    def u8(a):
        return None if a is None else np.round(np.clip(a, 0, 1) * 255).astype(np.uint8)
    return {
        "shape": o.shape,
        "orig_shape": o.orig_shape,
        "is_jpeg": o.is_jpeg,
        "jpeg_quality": o.jpeg_quality,
        "catnet": u8(o.catnet),
        "safire": u8(o.safire),
        "zero_main_grid": o.zero_main_grid,
        "zero_regions": [{k: (np.packbits(v) if k == "mask" else v) for k, v in r.items()} for r in o.zero_regions],
        "copymove_groups": [
            {
                "matches": g["matches"],
                "log10_nfa": g["log10_nfa"],
                "target_mask": np.packbits(g["target_mask"]),
                "source_mask": np.packbits(g["source_mask"]),
            }
            for g in o.copymove_groups
        ],
        "tile_boxes": o.tile_boxes,
        "tile_scores": o.tile_scores,
        "timings": raw.timings,
        "extra": raw.extra,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=str(ROOT / "index.json"))
    parser.add_argument("--cache", default=str(ROOT / "cache"))
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--safire-points", type=int, default=8)
    parser.add_argument("--methods", nargs="+", default=["catnet", "safire", "zero", "copymove", "tiles"])
    parser.add_argument("--subsets", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--start", type=int, default=0)
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    items = json.loads(Path(args.index).read_text())
    if args.subsets:
        items = [it for it in items if it["subset"] in args.subsets]
    items = [it for i, it in enumerate(items) if i % args.shards == args.shard]
    if args.start:
        items = items[args.start :] + items[: args.start]
    if args.reverse:
        items = items[::-1]
    if args.limit:
        items = items[: args.limit]
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    models = Models(threads=args.threads, safire_points=args.safire_points)
    if "catnet" in args.methods:
        models.catnet = load_catnet(str(WEIGHTS / "catnet_v2_state.pt"))
    if "safire" in args.methods:
        models.safire = load_safire(str(WEIGHTS / "safire_state.pt"))
    if "tiles" in args.methods:
        models.tile_model, models.tile_processor = load_tile_model()

    done = 0
    for it in items:
        dest = cache / (it["id"] + ".pkl.gz")
        if dest.exists():
            continue
        try:
            image = load_path(it["path"])
            t0 = time.perf_counter()
            raw = run_methods(image, models, tuple(args.methods))
            payload = pack(raw)
            payload["total_wall"] = time.perf_counter() - t0
            payload["maxrss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
            payload["item"] = it
            tmp = dest.with_suffix(".tmp")
            with gzip.open(tmp, "wb", compresslevel=3) as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(dest)
        except Exception:
            print(f"FAILED {it['id']}", file=sys.stderr)
            traceback.print_exc()
            continue
        done += 1
        if done % 10 == 0:
            print(f"shard {args.shard}: {done} done, last {it['id']} {payload['total_wall']:.1f}s", flush=True)
    print(f"shard {args.shard}: finished {done}", flush=True)


if __name__ == "__main__":
    main()
