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
