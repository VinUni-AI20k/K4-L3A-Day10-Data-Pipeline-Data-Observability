# Corruption Report — Baseline vs Corrupted vs Repaired

_Generated at 2026-09-25T08:37:27+00:00_

## 1. Evaluation Metrics (3 states)

| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Retrieval Hit Rate | 1.0000 | 0.6000 | 1.0000 | -0.4000 | +0.0000 |
| Mean Token F1 | 1.0000 | 0.5000 | 1.0000 | -0.5000 | +0.0000 |
| LLM Judge Accuracy | 1.0000 | 0.5000 | 1.0000 | -0.5000 | +0.0000 |
| Mean LLM Judge Score | 5 | 3 | 5 | -2.0000 | +0.0000 |

## 2. Observability Signals

| Signal | Corrupted | Repaired |
| :--- | :---: | :---: |
| Quality Gate (GX 1.x) | ❌ FAIL | ✅ PASS |
| Freshness SLA | ❌ FAIL | ✅ PASS |
| Stale ratio | 0.4091 | 0.0000 |
| Row count | 22 | 24 |

### Expectations failed on corrupted data

- `expect_column_values_to_be_unique` on `paper_id` (6 unexpected)
- `expect_column_value_lengths_to_be_between` on `title` (4 unexpected)
- `expect_column_value_lengths_to_be_between` on `summary` (3 unexpected)

## 3. Analysis

- **Retrieval Hit Rate** dropped (1.0000 → 0.6000) and fully recovered after repair (1.0000).
- **Mean Token F1** dropped (1.0000 → 0.5000) and fully recovered after repair (1.0000).
- **LLM Judge Accuracy** dropped (1.0000 → 0.5000) and fully recovered after repair (1.0000).
- **Mean LLM Judge Score** dropped (5 → 3) and fully recovered after repair (5).
- Quality gate on corrupted data: caught the corruption; freshness SLA: raised a stale alert.
