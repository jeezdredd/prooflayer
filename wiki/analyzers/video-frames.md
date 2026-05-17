---
type: analyzer
created: 2026-05-14
source: backend/analyzers/implementations/video_analyzer.py
---

# Video Frame Sampler

Uniform-interval frames extracted from video -> passed through [[analyzers/ai-ensemble]] -> aggregated ratio.

## MIME

`video/mp4`, `video/quicktime`, `video/x-msvideo`, `video/x-matroska`, `video/webm`

## Sampling

```python
FRAME_INTERVAL = 30   # every Nth frame
MAX_FRAMES = 8         # cap
```

`cv2.VideoCapture(file_path)`, iterate, `if frame_idx % 30 == 0: process`.

For a 30fps video, samples roughly every 1 second, capped at 8 frames (~8 seconds covered).

## Per-frame call

```python
output = detector.analyze(frame_path, {"skip_photo_check": True})
```

> [!key-insight] skip_photo_check flag
> Video frames are by definition photographic. Photo check often returns false negatives on AI-generated video (Veo 3 etc) because of smooth gradients. We bypass it via metadata flag. See [[concepts/skip-photo-check]].

## Evidence shape

```json
{
  "frames_analyzed": 8,
  "ai_frame_ratio": 0.625,
  "frame_results": [
    {
      "frame": 0,
      "timestamp": 0.0,
      "confidence": 0.9,
      "verdict": "fake",
      "ai_probability_avg": 0.87
    },
    ...
  ]
}
```

## Verdict logic

```python
suspicious_frames = [r for r in frames if r.verdict in ("fake", "suspicious")]
ai_frame_ratio = len(suspicious) / len(frames)
avg_confidence = mean(r.confidence for r in frames)

if ai_frame_ratio >= 0.6:  fake @ min(0.95, avg_conf + 0.1)
elif ai_frame_ratio >= 0.3: suspicious @ avg_conf
elif ai_frame_ratio >= 0.1: inconclusive @ 0.45
else:                       inconclusive @ 0.30
```

## Dependencies

- `opencv-python` for `cv2.VideoCapture`
- [[analyzers/ai-ensemble]] for per-frame classification
- tempfile dir for JPEG-saved frames during analysis

## Gaps

- Audio track not extracted -> [[analyzers/audio-spectrogram]] not invoked
- No facial tracking, no temporal coherence check
- 8 frames * 2 models = 16 HF inferences -> can be slow + memory-heavy

## See also

- [[analyzers/_index]]
- [[concepts/skip-photo-check]]
- [[analyzers/ai-ensemble]]
