---
type: analyzer
created: 2026-05-14
source: backend/analyzers/implementations/ela_analyzer.py
---

# Error Level Analysis (ELA)

Re-saves the image at a known JPEG quality (default 95) and compares pixel-level error against the original. Spliced or pasted regions retain different compression history -> stand out.

## MIME

`image/jpeg`, `image/png`, `image/webp`

## Algorithm

1. Open original as RGB
2. Re-save as JPEG quality=95 to buffer
3. Re-open re-saved version
4. Per-pixel `abs(orig - resave)` -> error map
5. Aggregate stats: `mean_error`, `max_error`, `std_error`, `uniformity_ratio` (block-wise std deviation), `block_mean`, `block_std`

## PNG / lossless caveat

Source format detection. If `PNG`/`WEBP` source, ELA heuristics are unreliable (no original compression artifact to compare). Evidence carries:

```json
"note": "lossless source (PNG/WebP/etc) - ELA heuristics unreliable",
"source_format": "PNG"
```

Verdict in that case: `inconclusive`.

## Evidence shape

```json
{
  "mean_error": 2.04,
  "max_error": 78,
  "std_error": 2.40,
  "block_mean": 2.04,
  "block_std": 0.98,
  "uniformity_ratio": 0.48,
  "source_format": "JPEG" | "PNG" | ...,
  "note": "...optional..."
}
```

## Verdict

- High `std_error` + nonuniform blocks -> `suspicious` or `fake`
- Low uniform error across image -> `authentic`
- Lossless source -> `inconclusive`

## Weight

Low-mid. Useful as supporting evidence on JPEGs only.

## See also

- [[analyzers/_index]]
- [[analyzers/ai-ensemble]] (complementary signal)
