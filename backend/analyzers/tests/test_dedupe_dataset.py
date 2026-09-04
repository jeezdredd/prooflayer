import os

from django.core.management import call_command
from PIL import Image

from analyzers.management.commands.dedupe_dataset import find_collisions


def _img(path, seed):
    import random

    rng = random.Random(seed)
    img = Image.new("RGB", (64, 64))
    px = img.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return img


class TestFindCollisions:
    def test_identical_image_in_both_trees_is_a_collision(self, tmp_path):
        ref, tgt = tmp_path / "ref", tmp_path / "tgt"
        _img(str(ref / "ai_generated" / "a__001.png"), 1)
        _img(str(tgt / "ai_generated" / "a__009.png"), 1)
        _img(str(tgt / "real" / "real__0001.png"), 2)
        hits = find_collisions(str(tgt), str(ref))
        assert [os.path.basename(t) for t, _ in hits] == ["a__009.png"]

    def test_reencoded_copy_is_caught_with_tolerance(self, tmp_path):
        ref, tgt = tmp_path / "ref", tmp_path / "tgt"
        img = _img(str(ref / "real" / "real__0001.png"), 3)
        os.makedirs(tgt / "real")
        img.save(tgt / "real" / "copy.jpg", format="JPEG", quality=70)
        assert len(find_collisions(str(tgt), str(ref), max_distance=6)) == 1

    def test_distinct_images_are_kept(self, tmp_path):
        ref, tgt = tmp_path / "ref", tmp_path / "tgt"
        _img(str(ref / "real" / "x.png"), 10)
        _img(str(tgt / "real" / "y.png"), 11)
        assert find_collisions(str(tgt), str(ref), max_distance=4) == []


class TestCommand:
    def test_dry_run_keeps_files(self, tmp_path, capsys):
        ref, tgt = tmp_path / "ref", tmp_path / "tgt"
        _img(str(ref / "ai_generated" / "a.png"), 5)
        _img(str(tgt / "ai_generated" / "b.png"), 5)
        call_command("dedupe_dataset", target=str(tgt), against=str(ref), dry_run=True)
        assert (tgt / "ai_generated" / "b.png").exists()
        assert "would remove 1" in capsys.readouterr().out

    def test_real_run_deletes_only_duplicates(self, tmp_path):
        ref, tgt = tmp_path / "ref", tmp_path / "tgt"
        _img(str(ref / "ai_generated" / "a.png"), 7)
        _img(str(tgt / "ai_generated" / "dup.png"), 7)
        _img(str(tgt / "ai_generated" / "keep.png"), 8)
        call_command("dedupe_dataset", target=str(tgt), against=str(ref))
        assert not (tgt / "ai_generated" / "dup.png").exists()
        assert (tgt / "ai_generated" / "keep.png").exists()
        assert (ref / "ai_generated" / "a.png").exists()
