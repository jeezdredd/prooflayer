from PIL import Image

from analyzers.management.commands.retrain_detector import _collect_extra, _sample_group, _source_of


def _tree(tmp_path, layout):
    root = tmp_path / "extra"
    for sub, names in layout.items():
        (root / sub).mkdir(parents=True)
        for name in names:
            path = root / sub / name
            if name.endswith((".jpg", ".png", ".webp")):
                Image.new("RGB", (8, 8)).save(path)
            else:
                path.write_text("not an image")
    return str(root)


class TestCollectExtra:
    def test_maps_ai_generated_to_fake_and_keeps_real(self, tmp_path):
        root = _tree(tmp_path, {"real": ["a.jpg", "b.png"], "ai_generated": ["flux__001.png"]})
        got = _collect_extra([root])
        labels = sorted((p.split("/")[-1], lb) for p, lb in got)
        assert labels == [("a.jpg", "real"), ("b.png", "real"), ("flux__001.png", "fake")]

    def test_accepts_fake_dir_too(self, tmp_path):
        root = _tree(tmp_path, {"fake": ["x.webp"]})
        assert [lb for _, lb in _collect_extra([root])] == ["fake"]

    def test_ignores_non_images_and_missing_dirs(self, tmp_path):
        root = _tree(tmp_path, {"real": ["ok.jpg", "notes.txt", "README.md"]})
        assert [p.split("/")[-1] for p, _ in _collect_extra([root])] == ["ok.jpg"]
        assert _collect_extra([str(tmp_path / "nope")]) == []

    def test_multiple_roots_concatenate(self, tmp_path):
        a = _tree(tmp_path / "one", {"real": ["1.jpg"]})
        b = _tree(tmp_path / "two", {"ai_generated": ["2.jpg"]})
        assert len(_collect_extra([a, b])) == 2


class TestSourceParsing:
    def test_symlink_prefix_is_stripped(self):
        assert _source_of("/d/fake/extra_3_midjourney-7__004.png") == "midjourney-7"

    def test_double_underscore_wins_over_single(self):
        assert _source_of("/d/fake/midjourney-7__004.png") == "midjourney-7"

    def test_single_underscore_fallback(self):
        assert _source_of("/d/real/flickr_12345.jpg") == "flickr"

    def test_sample_group_strips_frame_suffix(self):
        assert _sample_group("/d/fake/abc-uuid_f30.jpg") == "abc-uuid"
        assert _sample_group("/d/fake/abc-uuid_spec.png") == "abc-uuid"
        assert _sample_group("/d/fake/plain.jpg") == "plain"
