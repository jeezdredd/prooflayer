---
type: model
created: 2026-05-14
source: backend/analyzers/models.py
table: analyzer_configs
---

# AnalyzerConfig

Registry row per analyzer. Admin-editable. Controls dispatch.

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField(100) unique | `metadata`, `ela`, `ai_detector`, `llm_vision`, `video_frame`, `audio_spectrogram`, `llm_text` |
| `analyzer_class` | CharField(255) | dotted Python path e.g. `analyzers.implementations.clip_detector.AIImageDetector` |
| `version` | CharField(20) | semver-ish, e.g. `"2.0.0"` |
| `is_active` | Boolean | dispatcher filter |
| `weight` | Float | aggregation multiplier (default 1.0) |
| `queue` | CharField(50) | celery queue: `default` / `ml` / `reports` |
| `timeout` | PositiveInt | soft_time_limit seconds (default 120) |
| `created_at` | DateTime | auto |

## Wiring

- `analyzers/registry.py:load_analyzer_class(dotted_path)` imports + returns class
- `analyzers/tasks.py:dispatch_analysis` iterates `AnalyzerConfig.objects.filter(is_active=True)` and schedules `run_analyzer.s(submission_id, cfg.id).set(queue=cfg.queue, soft_time_limit=cfg.timeout, time_limit=cfg.timeout+30)`
- Aggregator reads `cfg.weight` per [[concepts/aggregation]]

## Seeded via fixtures or management cmd

`content/management/commands/seed_demo_data.py` includes AnalyzerConfig seeds. Initial weight values currently default 1.0 - tune in admin if needed (e.g. AI ensemble > metadata).

## See also

- [[concepts/aggregation]]
- [[analyzers/_index]]
