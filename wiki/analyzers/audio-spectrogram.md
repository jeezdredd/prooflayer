---
type: analyzer
created: 2026-05-14
source: backend/analyzers/implementations/audio_analyzer.py
---

# Audio Spectrogram Analyzer

Computes spectral features via librosa to detect synthetic-voice artifacts and unnatural frequency distributions.

## MIME

`audio/mpeg`, `audio/wav`, `audio/x-wav`, `audio/ogg`, `audio/flac`, `audio/mp4`

## Features extracted

- Spectral centroid stats
- Spectral rolloff
- Zero-crossing rate
- MFCCs distribution
- Pitch variance
- Background noise floor

## Verdict heuristics

- Unnaturally clean / no breathing pauses -> `suspicious` or `fake`
- Suspicious uniformity in MFCC space -> `suspicious`
- Natural noise floor + pitch variance -> `authentic`
- Edge cases / silence / corruption -> `inconclusive` or `error`

## Dependencies

- `librosa` for spectral analysis
- `soundfile` / `pydub` backends

## Gap: video audio

Currently only invoked on audio-MIME submissions. Video with embedded audio track does NOT run this. To enable, [[analyzers/video-frames]] would need to ffmpeg-extract WAV and dispatch as side-channel, or a new `MediaContainerAnalyzer` would orchestrate.

## See also

- [[analyzers/_index]]
- [[analyzers/video-frames]] - audio gap
