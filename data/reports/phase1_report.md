# Phase 1 Baseline Report

## Source Summary
- Records ingested: 24
- Source: Crossref REST API
- Query: agentic retrieval augmented generation large language model

## Baseline Metrics

| Metric | Value |
| --- | --- |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 1.0000 |
| mean_judge_score | 5 |
| samples | 10 |

## Data Quality (Great Expectations 1.x)
- Overall success: **True**
  - [PASS] expect_table_row_count_to_be_between
  - [PASS] expect_column_values_to_not_be_null (column: paper_id)
  - [PASS] expect_column_values_to_be_unique (column: paper_id)
  - [PASS] expect_column_values_to_not_be_null (column: title)
  - [PASS] expect_column_values_to_not_be_null (column: text_for_embedding)
  - [PASS] expect_column_value_lengths_to_be_between (column: summary)

## Freshness SLA
- is_fresh: **True**
- stale_rows: 1 / 24
- stale_ratio: 0.0417
- threshold_days: 180
- latest_published: 2026-07-22
- oldest_published: 2026-03-28
