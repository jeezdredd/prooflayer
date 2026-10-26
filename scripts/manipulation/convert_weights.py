import argparse
import hashlib
from pathlib import Path

import numpy as np
import torch
from numpy._core.multiarray import scalar

WEIGHTS = Path("/Users/sevastyan0107/PycharmProjects/prooflayer/dataset/manipulation/weights")
EXPECTED = {
    "CAT_full_v2.pth.tar": "f82aaafdd1142775231feedcea0bb7027f7370561d9e8d107465454001865989",
    "safire.pth": "65bdf6880380162d57f77d71b3fd367c3f16aebca316f942a821da16e9225b12",
}
SOURCES = {
    "CAT_full_v2.pth.tar": "https://drive.usercontent.google.com/download?id=1tyOKVdx6UMys2OcNpUj9r6scxNIpcoLE&export=download&confirm=t",
    "safire.pth": "https://drive.usercontent.google.com/download?id=1KVbMC7z6eG7xDMoSbvelqD7JW3R0koSg&export=download&confirm=t",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(state: dict, prefix: str) -> dict:
    out = {}
    for k, v in state.items():
        key = k[len(prefix) :] if k.startswith(prefix) else k
        out[key] = v.long() if key.endswith("num_batches_tracked") else v.float().contiguous()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn the published checkpoints into fp32 state dicts loadable with weights_only=True")
    parser.add_argument("--dir", default=str(WEIGHTS))
    args = parser.parse_args()
    root = Path(args.dir)
    for name, digest in EXPECTED.items():
        got = sha256(root / name)
        if got != digest:
            raise SystemExit(f"{name}: sha256 {got} != {digest}; download from {SOURCES[name]}")
    allowed = [(scalar, "numpy.core.multiarray.scalar"), np.dtype, np.dtypes.Float64DType, np.dtypes.Float32DType]
    with torch.serialization.safe_globals(allowed):
        cat = torch.load(root / "CAT_full_v2.pth.tar", map_location="cpu", weights_only=True)
    torch.save(clean(cat["state_dict"], "model."), root / "catnet_v2_state.pt")
    saf = torch.load(root / "safire.pth", map_location="cpu", weights_only=True)
    torch.save(clean(saf["model"], "module."), root / "safire_state.pt")
    for name in ("catnet_v2_state.pt", "safire_state.pt"):
        print(name, sha256(root / name))


if __name__ == "__main__":
    main()
