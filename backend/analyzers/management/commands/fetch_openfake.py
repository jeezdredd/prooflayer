import io
import os
import re

from django.core.management.base import BaseCommand

DATASET = "ComplexDataLab/OpenFake"
SHARD_GLOB = "datasets/ComplexDataLab/OpenFake/core/test-*.parquet"
REAL_LABELS = {"real", "0", "human"}
MAX_SIDE = 1024
BATCH_ROWS = 32


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", (value or "unknown").lower()).strip("-") or "unknown"


def _image_bytes(cell) -> bytes | None:
    if cell is None:
        return None
    if isinstance(cell, dict):
        return cell.get("bytes")
    if isinstance(cell, (bytes, bytearray)):
        return bytes(cell)
    return None


class Command(BaseCommand):
    help = "Sample OpenFake per generator into a local eval tree, streaming parquet row groups (memory-bounded)"

    def add_arguments(self, parser):
        parser.add_argument("--out", default="dataset/openfake")
        parser.add_argument("--per-model", type=int, default=12, help="AI images per generator")
        parser.add_argument("--real", type=int, default=150, help="real images total")
        parser.add_argument("--row-groups-per-shard", type=int, default=2, help="row groups to read from each shard per pass")
        parser.add_argument("--max-passes", type=int, default=3)
        parser.add_argument("--models", nargs="*", default=[], help="only these generator names (substring match)")

    def handle(self, *args, **options):
        import pyarrow.parquet as pq
        from huggingface_hub import HfFileSystem
        from PIL import Image

        out = options["out"]
        real_dir = os.path.join(out, "real")
        ai_dir = os.path.join(out, "ai_generated")
        os.makedirs(real_dir, exist_ok=True)
        os.makedirs(ai_dir, exist_ok=True)

        wanted = [m.lower() for m in options["models"]]
        per_model = options["per_model"]
        real_cap = options["real"]

        fs = HfFileSystem()
        shards = sorted(fs.glob(SHARD_GLOB))
        if not shards:
            self.stderr.write("no shards found")
            return
        self.stdout.write(f"{len(shards)} test shards")

        taken: dict[str, int] = {}
        real_taken = 0
        scanned = 0
        skipped = 0
        rg_cursor = {shard: 0 for shard in shards}

        def want(label: str, model: str) -> bool:
            if label in REAL_LABELS:
                return real_taken < real_cap
            if wanted and not any(w in model for w in wanted):
                return False
            return taken.get(model, 0) < per_model

        def saturated() -> bool:
            return real_taken >= real_cap and bool(taken) and all(v >= per_model for v in taken.values())

        for pass_no in range(options["max_passes"]):
            progressed = False
            for shard in shards:
                with fs.open(shard, "rb") as fh:
                    pf = pq.ParquetFile(fh)
                    start = rg_cursor[shard]
                    stop = min(start + options["row_groups_per_shard"], pf.num_row_groups)
                    if start >= stop:
                        continue
                    progressed = True
                    rg_cursor[shard] = stop
                    for rg in range(start, stop):
                        meta = pf.read_row_group(rg, columns=["label", "model"]).to_pydict()
                        labels = [str(v).lower() for v in meta["label"]]
                        models = [_slug(str(v)) for v in meta["model"]]
                        scanned += len(labels)
                        keep = [i for i, (lb, md) in enumerate(zip(labels, models)) if want(lb, md)]
                        if not keep:
                            continue
                        images = pf.read_row_group(rg, columns=["image"]).column("image")
                        for i in keep:
                            lb, md = labels[i], models[i]
                            if not want(lb, md):
                                continue
                            raw = _image_bytes(images[i].as_py())
                            if not raw:
                                skipped += 1
                                continue
                            try:
                                img = Image.open(io.BytesIO(raw)).convert("RGB")
                                if max(img.size) > MAX_SIDE:
                                    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
                            except Exception as exc:
                                skipped += 1
                                self.stderr.write(f"decode failed: {exc}")
                                continue
                            if lb in REAL_LABELS:
                                real_taken += 1
                                img.save(os.path.join(real_dir, f"real__{real_taken:04d}.png"), format="PNG")
                            else:
                                taken[md] = taken.get(md, 0) + 1
                                img.save(os.path.join(ai_dir, f"{md}__{taken[md]:03d}.png"), format="PNG")
                        del images
                self.stdout.write(
                    f"  pass {pass_no + 1} {os.path.basename(shard)}: scanned {scanned}, "
                    f"real {real_taken}/{real_cap}, ai {sum(taken.values())} over {len(taken)} models"
                )
                if saturated():
                    break
            if saturated() or not progressed:
                break

        self.stdout.write(f"scanned {scanned}, skipped {skipped}")
        self.stdout.write(f"real: {real_taken}")
        for model, n in sorted(taken.items()):
            self.stdout.write(f"  {model:28} {n}")
        self.stdout.write(self.style.SUCCESS(f"written to {out}"))
