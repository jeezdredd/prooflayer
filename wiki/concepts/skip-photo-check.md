---
type: concept
created: 2026-05-10
---

# skip_photo_check (video frame bypass)

`AIImageDetector` runs a `_photographic_score` filter to short-circuit on screenshots / diagrams / UI captures (entropy + unique colors + edge density thresholds). On non-photographic content the detector returns `(0.5, "inconclusive")` with note.

**Problem:** [[analyzers/video-frames]] feeds JPEG frames into the detector. AI-generated video (Veo 3, Sora etc) often has smooth gradients that fall BELOW the entropy threshold, even though the frame is photographic. Result: all frames inconclusive 0.5, video verdict useless.

**Fix:** metadata-passed flag. Video analyzer sets:

```python
output = detector.analyze(frame_path, {"skip_photo_check": True})
```

Detector now:

```python
skip_photo_check = bool(metadata.get("skip_photo_check"))
photo_check = _photographic_score(image)
if not skip_photo_check and not photo_check["is_photographic"]:
    return inconclusive_with_note
# continue to ensemble
```

Video frames are presumed photographic and bypass filter. Direct-uploaded images still get the filter.

Evidence still carries `content_check` for transparency.

## See also

- [[analyzers/video-frames]]
- [[analyzers/ai-ensemble]]
