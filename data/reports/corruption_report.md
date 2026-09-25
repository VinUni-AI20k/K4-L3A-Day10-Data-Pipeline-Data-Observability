# Data Corruption and Repair Report

## Evaluation metrics

| Metric | Baseline | Corrupted | Repaired | Corruption delta | Repair delta |
|---|---:|---:|---:|---:|---:|
| samples | 10 | 10 | 10 | 0 | 0 |
| retrieval_hit_rate | 100.00% | 70.00% | 100.00% | -30.00% | 30.00% |
| mean_token_f1 | 0.9055 | 0.6775 | 0.9055 | -0.2280 | 0.2280 |
| judge_accuracy | 80.00% | 70.00% | 90.00% | -10.00% | 20.00% |
| mean_judge_score | 4.4000 | 3.4000 | 4.4000 | -1.0000 | 1.0000 |

## Data quality comparison

| Check | Corrupted | Repaired |
|---|---:|---:|
| Overall quality gate | FAIL | PASS |
| row_count_between_5_and_5000 | PASS | PASS |
| paper_id_not_null | PASS | PASS |
| title_not_null | PASS | PASS |
| text_for_embedding_not_null | PASS | PASS |
| paper_id_unique | FAIL | PASS |
| summary_length_at_least_30 | FAIL | PASS |

## Freshness comparison

| Metric | Corrupted | Repaired |
|---|---:|---:|
| Status | FAIL | PASS |
| Total rows | 21 | 24 |
| Stale rows | 10 | 1 |
| Stale ratio | 47.62% | 4.17% |
| Latest publication | 2026-06-12 | 2026-07-22 |
| Oldest publication | 2021-04-30 | 2026-03-28 |

## Outcome

The corrupted dataset is expected to fail one or more quality checks. A successful repair restores the raw source records, uniqueness, required content and freshness before rebuilding the vector index.
