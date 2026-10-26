---
type: analyzer
created: 2026-05-14
source: backend/analyzers/implementations/metadata_analyzer.py
---

# Metadata / EXIF Analyzer

Reads EXIF/XMP metadata. Looks for editing software signatures, missing camera fields, timestamp drift, GPS anomalies.

## MIME

`image/jpeg`, `image/png`, `image/webp`

## Signals checked

- `metadata_presence` - any EXIF block exists or stripped
- `ai_tool` detection - "DALL-E", "Stable Diffusion", "Midjourney", "Adobe Firefly" tool tag in XMP / EXIF Software field
- `dates` - inconsistency between `DateTimeOriginal`, `DateTimeDigitized`, file mtime
- `gps` - GPS coordinates plausibility
- `flags` - composite list e.g. `["metadata_stripped"]`, `["ai_tool_detected"]`

## Evidence shape

```json
{
  "metadata_presence": {"stripped": bool, "details": str|null},
  "ai_tool": {"detected": bool, "tool": str|null, "field": str|null},
  "dates": {"suspicious": bool, "details": str|null},
  "gps": {"suspicious": bool, "details": str|null},
  "flags": ["metadata_stripped" | "ai_tool_detected"]
}
```

## Verdict

- AI tool tag detected -> `fake` w/ high conf
- Metadata fully stripped -> `inconclusive` (cannot prove either way)
- Suspicious date / GPS -> `suspicious`
- Clean signatures -> `authentic`

## Weight

Low. Metadata is easy to strip or fabricate. Use as supporting signal only.

## See also

- [[analyzers/_index]]
- [[concepts/aggregation]]

## Camera file level (2026-10-26, `metadata` 1.10.0, Tribunal 1.11.0)

`analyzers/camera_file.py` reads the JPEG structure and stores `evidence.camera_file` = `{mpo, makernote, dims_ok, thumb_mismatch, gainmap, level}`:
- 0: no camera EXIF; 1: camera EXIF only; 2: plus a MakerNote of 256+ bytes, matching EXIF pixel size, no mismatching thumbnail;
- 3: camera EXIF, an HDR gain map (MPF secondary image of type undefined, or XMP `aux:hdrgainmap` / `hdrgm`) whose gradients line up with the main picture (correlation >= 0.30 at 256 or 128 px, aspect within 3%, std >= 1), matching pixel size, thumbnail not mismatching.

Only level 3 votes (aggregator `CAMERA_FILE_*`): weight 4.0, p 0.02, skipped when any AI mark is present. With the vote, a single confident AI detector cannot convict (verdict becomes inconclusive) and two or more give needs_review. Level 2 was rejected: forgers who re-encode an AI image through Apple ImageIO with copied EXIF reach it (74 -> 26 of their images caught), but none reached level 3. Benchmark and numbers: [[concepts/detector-evaluation]].
