import os

from django.core.management.base import BaseCommand

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
CLASS_DIRS = ("real", "ai_generated", "fake")


def _fingerprints(root: str) -> dict[str, tuple]:
    import imagehash
    from PIL import Image

    out = {}
    for sub in CLASS_DIRS:
        class_dir = os.path.join(root, sub)
        if not os.path.isdir(class_dir):
            continue
        for name in sorted(os.listdir(class_dir)):
            if not name.lower().endswith(IMAGE_EXTENSIONS):
                continue
            path = os.path.join(class_dir, name)
            try:
                with Image.open(path) as img:
                    out[path] = (str(imagehash.phash(img)), str(imagehash.dhash(img)))
            except Exception:
                continue
    return out


def find_collisions(target: str, against: str, max_distance: int = 0) -> list[tuple[str, str]]:
    """(target_path, reference_path) for every target image that duplicates a reference one.

    Distance 0 means identical phash and dhash. A small positive distance also catches
    re-encoded copies; keep it tight so distinct images of the same prompt survive.
    """
    import imagehash

    ref = _fingerprints(against)
    tgt = _fingerprints(target)
    if max_distance == 0:
        index = {}
        for path, fp in ref.items():
            index.setdefault(fp, path)
        return [(path, index[fp]) for path, fp in tgt.items() if fp in index]
    hits = []
    ref_items = [(p, imagehash.hex_to_hash(a), imagehash.hex_to_hash(b)) for p, (a, b) in ref.items()]
    for path, (a, b) in tgt.items():
        ha, hb = imagehash.hex_to_hash(a), imagehash.hex_to_hash(b)
        for rp, ra, rb in ref_items:
            if (ha - ra) <= max_distance and (hb - rb) <= max_distance:
                hits.append((path, rp))
                break
    return hits


class Command(BaseCommand):
    help = "Remove images from --target that duplicate images in --against (perceptual hash)"

    def add_arguments(self, parser):
        parser.add_argument("--target", required=True, help="dataset tree to clean (files are deleted here)")
        parser.add_argument("--against", required=True, help="reference dataset tree (untouched)")
        parser.add_argument("--max-distance", type=int, default=0, help="hamming tolerance on phash and dhash")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        hits = find_collisions(options["target"], options["against"], options["max_distance"])
        for target_path, ref_path in hits:
            self.stdout.write(f"  {os.path.relpath(target_path, options['target'])}  ==  {os.path.relpath(ref_path, options['against'])}")
            if not options["dry_run"]:
                os.unlink(target_path)
        verb = "would remove" if options["dry_run"] else "removed"
        self.stdout.write(self.style.SUCCESS(f"{verb} {len(hits)} duplicate(s) from {options['target']}"))
