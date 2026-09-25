# Phase 1 Report — Baseline Pipeline

_Generated at 2026-09-25T08:36:59+00:00_

## 1. Source Summary

| Field | Value |
| :--- | :--- |
| source_api | Crossref REST API |
| source_mode | loaded from raw snapshot |
| run_date | 2026-09-25T08:36:57+00:00 |
| raw_records | 24 |
| clean_rows | 24 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection | papers-baseline |
| llm_provider | mock |

## 2. Retrieval & Answer Evaluation

| Metric | Value |
| :--- | ---: |
| Samples | 10 |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| LLM Judge Accuracy | 1.0000 |
| Mean LLM Judge Score | 5 |

- RAGAS `skipped`: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## 3. Data Quality Gate (Great Expectations 1.x)

**Overall Quality Gate:** ✅ PASS

| Expectation | Column | Status | Observed |
| :--- | :--- | :---: | :--- |
| `expect_table_row_count_to_be_between` | table | ✅ PASS | 24 |
| `expect_column_values_to_not_be_null` | paper_id | ✅ PASS | 0 unexpected |
| `expect_column_values_to_be_unique` | paper_id | ✅ PASS | 0 unexpected |
| `expect_column_values_to_not_be_null` | title | ✅ PASS | 0 unexpected |
| `expect_column_value_lengths_to_be_between` | title | ✅ PASS | 0 unexpected |
| `expect_column_values_to_not_be_null` | summary | ✅ PASS | 0 unexpected |
| `expect_column_value_lengths_to_be_between` | summary | ✅ PASS | 0 unexpected |
| `expect_column_values_to_not_be_null` | text_for_embedding | ✅ PASS | 0 unexpected |

## 4. Freshness SLA

| Field | Value |
| :--- | :--- |
| Is fresh | ✅ PASS |
| Total rows | 24 |
| Stale rows (age_days > threshold) | 0 |
| Stale ratio | 0.0000 |
| Latest published | 2026-09-15 |
| Oldest published | 2026-04-01 |
