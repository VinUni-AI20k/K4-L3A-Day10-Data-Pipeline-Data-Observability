# Corruption vs Repair — 3-State Comparison Report

## Metrics Comparison

| Metric | Baseline | Corrupted | Δ Corrupted | Repaired | Δ Repaired |
| --- | ---: | ---: | ---: | ---: | ---: |
| retrieval_hit_rate | 1.0000 | 0.8000 | -0.2000 | 1.0000 | +0.0000 |
| mean_token_f1 | 1.0000 | 0.5882 | -0.4118 | 1.0000 | +0.0000 |
| judge_accuracy | 1.0000 | 0.6000 | -0.4000 | 1.0000 | +0.0000 |
| mean_judge_score | 5 | 3.2000 | -1.8000 | 5 | +0.0000 |

## Data Quality & Freshness

| State | GX Pass | GX Failures | is_fresh | Stale Ratio | Stale Rows |
| --- | :---: | --- | :---: | ---: | ---: |
| Baseline | ✅ | none | ✅ | 0.0 | 1/24 |
| Corrupted | ❌ | column values to be unique, column value lengths to be between | ❌ | 0.3 | 7/23 |
| Repaired | ✅ | none | ✅ | 0.0 | 1/24 |

## Analysis

### Corruption Impact (Silent Failure)
- `retrieval_hit_rate` dropped from 1.0000 → 0.8000 (-0.2000)
- `mean_token_f1` dropped from 1.0000 → 0.5882 (-0.4118)
- GX quality gate detected violations (duplicate paper_id, blank summary) — `success=False`
- Freshness SLA: stale ratio rose from 0.0417 → 0.3043

### Repair Recovery (Idempotent from Raw Snapshot)
- `retrieval_hit_rate` restored to 1.0000
- `mean_token_f1` restored to 1.0000
- GX quality gate passed — `success=True`
- Freshness SLA restored to is_fresh=True
