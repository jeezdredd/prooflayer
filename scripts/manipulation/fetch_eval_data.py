import argparse
import csv
import hashlib
import io
import json
import random
import re
import ssl
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import certifi
import pyarrow.parquet as pq
from huggingface_hub import HfFileSystem
from PIL import Image

ROOT = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation")
MANIFEST_DIR = ROOT / "manifests"
UA = "prooflayer-eval/1.0 (research evaluation; bounded download)"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
MAX_MEMBER_BYTES = 80 * 1024 * 1024
SAFE_NAME = re.compile(r"^[A-Za-z0-9._\-]+$")

TGIF_TOKEN = "xEeAzrY7ES9KA8o"
TGIF2_FLUX_TOKEN = "KG48tLZZzifC5WE"
TGIF_DAV = "https://cloud.ilabt.imec.be/public.php/dav/files/{token}/{path}"

LICENCES = {
    "tgif": "CC BY-SA 4.0 (TGIF, IDLab Ghent; COCO sources CC BY 4.0)",
    "cocoglide": "no explicit licence (GRIP TruFor release, COCO-derived); internal evaluation only",
    "grip_cmfd": "not stated (GRIP research release); internal evaluation only",
    "opensdi": "CC BY-SA 4.0 (card also says academic use); internal evaluation only",
    "sid": "CC BY 4.0",
    "vision": "CC BY-SA 4.0 (VISION, Univ. Florence)",
    "unsplash": "Unsplash Lite terms: use allowed, redistribution of images not allowed",
}

_lock = threading.Lock()
_ssl_ctx = ssl.create_default_context(cafile=certifi.where())


def load_manifest(source: str) -> dict:
    path = MANIFEST_DIR / f"{source}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"source": source, "files": {}}


def save_manifest(manifest: dict) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f"{manifest['source']}.json"
    tmp = path.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    tmp.replace(path)


def record(manifest: dict, path: Path, url: str, source: str, member: str | None = None) -> None:
    data = path.read_bytes()
    entry = {
        "url": url,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "source": source,
        "licence": LICENCES[source],
    }
    if member:
        entry["member"] = member
    with _lock:
        manifest["files"][str(path.relative_to(ROOT))] = entry


def open_url(url: str, headers: dict | None = None, timeout: int = 120):
    hdrs = {"User-Agent": UA}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs)
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)


def download(url: str, dest: Path, headers: dict | None = None, retries: int = 3) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True
    for attempt in range(retries):
        try:
            with open_url(url, headers) as resp, open(dest.with_suffix(dest.suffix + ".part"), "wb") as fh:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
            dest.with_suffix(dest.suffix + ".part").replace(dest)
            return True
        except Exception as exc:
            print(f"retry {attempt + 1} {url}: {exc}", file=sys.stderr)
            time.sleep(2 + attempt * 3)
    return False


def safe_basename(name: str) -> str | None:
    base = name.rsplit("/", 1)[-1]
    if not base or base.startswith(".") or not SAFE_NAME.match(base):
        return None
    return base


def stream_tar(url: str, out_dir: Path, wanted, limit: int, manifest: dict, source: str, headers: dict) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    taken = 0
    with open_url(url, headers, timeout=300) as resp:
        with tarfile.open(fileobj=resp, mode="r|gz") as tar:
            for member in tar:
                if taken >= limit:
                    break
                if not member.isreg() or member.size > MAX_MEMBER_BYTES:
                    continue
                base = safe_basename(member.name)
                if base is None or Path(base).suffix.lower() not in IMAGE_EXT or not wanted(base):
                    continue
                dest = out_dir / base
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                data = fh.read()
                dest.write_bytes(data)
                record(manifest, dest, url, source, member.name)
                taken += 1
                if taken % 50 == 0:
                    print(f"  {out_dir.name}: {taken}", flush=True)
    return taken


def fetch_tgif(args, manifest: dict) -> None:
    headers = {"X-Requested-With": "XMLHttpRequest"}
    plan = [
        (TGIF_TOKEN, "masks/masks_testing.tar.gz", "tgif/masks", lambda b: True, 100000),
        (TGIF_TOKEN, "orig/orig_testing.tar.gz", "tgif/orig", lambda b: b.endswith("_orig.png"), args.tgif_orig),
        (TGIF_TOKEN, "ps-sp/ps-sp_testing.tar.gz", "tgif/ps-sp", lambda b: True, args.tgif_sp),
        (TGIF_TOKEN, "sd2-sp/sd2-sp_testing.tar.gz", "tgif/sd2-sp", lambda b: True, args.tgif_sd2sp),
        (TGIF_TOKEN, "sd2-fr/sd2-fr_testing.tar.gz", "tgif/sd2-fr", lambda b: True, args.tgif_fr),
        (TGIF2_FLUX_TOKEN, "masks-flux/masks-flux_testing.tar.gz", "tgif/masks-flux", lambda b: True, 100000),
        (TGIF2_FLUX_TOKEN, "flux1filldev-sp/flux1filldev-sp_testing.tar.gz", "tgif/flux1filldev-sp", lambda b: True, args.tgif_flux),
    ]
    only = set(args.only or [])
    for token, path, out, wanted, limit in plan:
        name = out.split("/")[-1]
        if only and name not in only:
            continue
        existing = len(list((ROOT / out).glob("*"))) if (ROOT / out).exists() else 0
        if existing >= limit:
            print(f"{out}: have {existing}")
            continue
        url = TGIF_DAV.format(token=token, path=path)
        print(f"{out}: streaming {url}", flush=True)
        n = stream_tar(url, ROOT / out, wanted, limit, manifest, "tgif", headers)
        print(f"{out}: {n}", flush=True)
        save_manifest(manifest)


def extract_zip(zip_path: Path, out_dir: Path, manifest: dict, url: str, source: str) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.file_size > MAX_MEMBER_BYTES:
                continue
            parts = [p for p in info.filename.split("/") if p]
            if not parts or any(p in ("..", "__MACOSX") or p.startswith(".") for p in parts):
                continue
            base = safe_basename(parts[-1])
            if base is None or Path(base).suffix.lower() not in IMAGE_EXT:
                continue
            sub = [safe_basename(p) for p in parts[1:-1]]
            if any(s is None for s in sub):
                continue
            dest = out_dir.joinpath(*sub, base)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
            record(manifest, dest, url, source, info.filename)
            n += 1
    return n


def fetch_zip_source(manifest: dict, url: str, name: str, source: str) -> None:
    zip_path = ROOT / "_archives" / f"{name}.zip"
    if not download(url, zip_path):
        print(f"{name}: download failed")
        return
    n = extract_zip(zip_path, ROOT / name, manifest, url, source)
    print(f"{name}: {n} files")
    zip_path.unlink()
    save_manifest(manifest)


def fetch_cocoglide(args, manifest: dict) -> None:
    fetch_zip_source(manifest, "https://www.grip.unina.it/download/prog/TruFor/CocoGlide.zip", "cocoglide", "cocoglide")


def fetch_grip(args, manifest: dict) -> None:
    fetch_zip_source(manifest, "https://www.grip.unina.it/download/prog/CMFD/CMFDdb_grip.zip", "grip_cmfd", "grip_cmfd")


def parquet_cell_bytes(cell) -> bytes | None:
    if cell is None:
        return None
    if isinstance(cell, dict):
        return cell.get("bytes")
    if isinstance(cell, (bytes, bytearray)):
        return bytes(cell)
    return None


def fetch_opensdi(args, manifest: dict) -> None:
    fs = HfFileSystem()
    out = ROOT / "opensdi_flux"
    (out / "real").mkdir(parents=True, exist_ok=True)
    (out / "partial").mkdir(parents=True, exist_ok=True)
    (out / "masks").mkdir(parents=True, exist_ok=True)
    counts = {"real": len(list((out / "real").glob("*"))), "partial": len(list((out / "partial").glob("*")))}
    caps = {"real": args.opensdi_real, "partial": args.opensdi_partial}
    shards = sorted(fs.glob("datasets/nebula/OpenSDI_test/data/flux-*.parquet"))
    rng = random.Random(7)
    for shard in shards:
        if all(counts[k] >= caps[k] for k in caps):
            break
        url = f"https://huggingface.co/{shard.replace('datasets/', 'datasets/', 1).replace('/data/', '/resolve/main/data/')}"
        with fs.open(shard, "rb") as fh:
            pf = pq.ParquetFile(fh)
            groups = list(range(pf.num_row_groups))
            rng.shuffle(groups)
            for rg in groups:
                if all(counts[k] >= caps[k] for k in caps):
                    break
                meta = pf.read_row_group(rg, columns=["key", "label"]).to_pydict()
                kinds = []
                for key in meta["key"]:
                    parts = key.split("/")
                    if "real" in parts:
                        kinds.append("real")
                    elif parts[0] == "partial":
                        kinds.append("partial")
                    else:
                        kinds.append(None)
                keep = [i for i, k in enumerate(kinds) if k and counts[k] < caps[k]]
                if not keep:
                    continue
                tbl = pf.read_row_group(rg, columns=["key", "image", "mask"])
                for i in keep:
                    kind = kinds[i]
                    if counts[kind] >= caps[kind]:
                        continue
                    key = meta["key"][i]
                    raw = parquet_cell_bytes(tbl.column("image")[i].as_py())
                    if not raw:
                        continue
                    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", key)
                    ext = ".jpg" if raw[:3] == b"\xff\xd8\xff" else ".png"
                    dest = out / kind / (Path(stem).stem + ext)
                    dest.write_bytes(raw)
                    record(manifest, dest, url, "opensdi", key)
                    if kind == "partial":
                        mraw = parquet_cell_bytes(tbl.column("mask")[i].as_py())
                        if mraw:
                            mdest = out / "masks" / (Path(stem).stem + ".png")
                            Image.open(io.BytesIO(mraw)).convert("L").save(mdest)
                            record(manifest, mdest, url, "opensdi", key + "#mask")
                    counts[kind] += 1
                print(f"  opensdi {Path(shard).name} rg{rg}: {counts}", flush=True)
        save_manifest(manifest)
    print(f"opensdi: {counts}")


def fetch_sid(args, manifest: dict) -> None:
    fs = HfFileSystem()
    shards = sorted(p for p in fs.glob("datasets/saberzl/SID_Set/data/*.parquet") if "valid" in p.rsplit("/", 1)[-1])
    if not shards:
        print("sid: no validation shards found")
        return
    shard = shards[0]
    out = ROOT / "sid_set"
    for sub in ("real", "tampered", "masks"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    url = "https://huggingface.co/" + shard.replace("/data/", "/resolve/main/data/")
    counts = {"real": 0, "tampered": 0}
    with fs.open(shard, "rb") as fh:
        pf = pq.ParquetFile(fh)
        names = pf.schema_arrow.names
        print(f"sid schema: {names}, {pf.num_row_groups} row groups")
        label_col = "label" if "label" in names else names[-1]
        for rg in range(pf.num_row_groups):
            if counts["real"] >= args.sid_real and counts["tampered"] >= args.sid_tampered:
                break
            tbl = pf.read_row_group(rg)
            labels = tbl.column(label_col).to_pylist()
            for i, lab in enumerate(labels):
                kind = {0: "real", 2: "tampered"}.get(int(lab))
                if kind is None:
                    continue
                cap = args.sid_real if kind == "real" else args.sid_tampered
                if counts[kind] >= cap:
                    continue
                raw = parquet_cell_bytes(tbl.column("image")[i].as_py())
                if not raw:
                    continue
                ext = ".jpg" if raw[:3] == b"\xff\xd8\xff" else ".png"
                name = f"sid_{rg:03d}_{i:04d}"
                dest = out / kind / (name + ext)
                dest.write_bytes(raw)
                record(manifest, dest, url, "sid", f"rg{rg}/row{i}")
                if kind == "tampered" and "mask" in names:
                    mraw = parquet_cell_bytes(tbl.column("mask")[i].as_py())
                    if mraw:
                        mdest = out / "masks" / (name + ".png")
                        Image.open(io.BytesIO(mraw)).convert("L").save(mdest)
                        record(manifest, mdest, url, "sid", f"rg{rg}/row{i}#mask")
                counts[kind] += 1
            print(f"  sid rg{rg}: {counts}", flush=True)
    save_manifest(manifest)
    print(f"sid: {counts}")


def fetch_vision(args, manifest: dict) -> None:
    list_path = ROOT / "_archives" / "VISION_files.txt"
    if not download("https://lesc.dinfo.unifi.it/VISION/VISION_files.txt", list_path):
        return
    urls = [u.strip() for u in list_path.read_text().splitlines() if u.strip()]
    nat = [u for u in urls if "/images/nat/" in u]
    by_device: dict[str, list[str]] = {}
    for u in nat:
        by_device.setdefault(u.split("/dataset/")[1].split("/")[0], []).append(u)
    rng = random.Random(11)
    jobs = []
    for device, items in sorted(by_device.items()):
        picks = rng.sample(sorted(items), min(args.vision_per_device, len(items)))
        for u in picks:
            idx = u.rsplit("_", 1)[-1]
            for variant in args.vision_variants:
                vu = u.replace("/images/nat/", f"/images/{variant}/").replace("_I_nat_", f"_I_{variant}_")
                if variant != "nat" and not vu.endswith(idx):
                    continue
                jobs.append((vu, ROOT / "vision" / variant / vu.rsplit("/", 1)[-1]))

    def run(job):
        vu, dest = job
        if download(vu, dest):
            record(manifest, dest, vu, "vision")

    with ThreadPoolExecutor(max_workers=4) as pool:
        for k, _ in enumerate(pool.map(run, jobs)):
            if k % 50 == 0:
                print(f"  vision {k}/{len(jobs)}", flush=True)
    save_manifest(manifest)
    print(f"vision: {len(jobs)} files")


def fetch_unsplash(args, manifest: dict) -> None:
    tsv = ROOT / "_archives" / "unsplash_photos.tsv"
    if not tsv.exists():
        zip_path = ROOT / "_archives" / "unsplash_lite.zip"
        if not download("https://unsplash.com/data/lite/latest", zip_path):
            return
        with zipfile.ZipFile(zip_path) as zf:
            member = next(n for n in zf.namelist() if n.endswith("photos.tsv000") or n.endswith("photos.csv000"))
            tsv.write_bytes(zf.read(member))
        zip_path.unlink()
    csv.field_size_limit(10**8)
    with open(tsv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    rng = random.Random(5)
    rng.shuffle(rows)
    picks = []
    for row in rows:
        url = row.get("photo_image_url") or ""
        if not url.startswith("https://images.unsplash.com/"):
            continue
        picks.append((row["photo_id"], url, row.get("exif_camera_make") or ""))
        if len(picks) >= args.unsplash:
            break
    out = ROOT / "unsplash"
    out.mkdir(parents=True, exist_ok=True)
    meta = []

    def run(item):
        pid, url, make = item
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", pid)
        dest = out / f"{safe}.jpg"
        full = f"{url}?w={args.unsplash_width}&fm=jpg&q=85"
        if download(full, dest):
            record(manifest, dest, full, "unsplash")
            return {"photo_id": pid, "camera_make": make, "file": dest.name}
        return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(run, picks):
            if res:
                meta.append(res)
    (out / "_meta.json").write_text(json.dumps(meta, indent=1))
    save_manifest(manifest)
    print(f"unsplash: {len(meta)}")


SOURCES = {
    "tgif": fetch_tgif,
    "cocoglide": fetch_cocoglide,
    "grip": fetch_grip,
    "opensdi": fetch_opensdi,
    "sid": fetch_sid,
    "vision": fetch_vision,
    "unsplash": fetch_unsplash,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded download of manipulation-map evaluation data")
    parser.add_argument("sources", nargs="+", choices=sorted(SOURCES))
    parser.add_argument("--only", nargs="*", help="tgif sub-folders to fetch (e.g. ps-sp orig)")
    parser.add_argument("--tgif-orig", type=int, default=343)
    parser.add_argument("--tgif-sp", type=int, default=400)
    parser.add_argument("--tgif-sd2sp", type=int, default=200)
    parser.add_argument("--tgif-fr", type=int, default=150)
    parser.add_argument("--tgif-flux", type=int, default=150)
    parser.add_argument("--opensdi-real", type=int, default=200)
    parser.add_argument("--opensdi-partial", type=int, default=200)
    parser.add_argument("--sid-real", type=int, default=150)
    parser.add_argument("--sid-tampered", type=int, default=150)
    parser.add_argument("--vision-per-device", type=int, default=6)
    parser.add_argument("--vision-variants", nargs="+", default=["nat", "natWA", "natFBH"])
    parser.add_argument("--unsplash", type=int, default=300)
    parser.add_argument("--unsplash-width", type=int, default=2048)
    args = parser.parse_args()
    for source in args.sources:
        manifest = load_manifest(source)
        SOURCES[source](args, manifest)
        save_manifest(manifest)


if __name__ == "__main__":
    main()
