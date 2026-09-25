# Phase 1 Baseline Report

## Source Summary

| Field | Value |
| --- | --- |
| `source_api` | Crossref REST API |
| `source_query` | agentic retrieval augmented generation large language model |
| `source_filter` | from-pub-date:2026-03-29,has-abstract:true |
| `raw_records` | 24 |
| `clean_rows` | 24 |
| `evaluation_questions` | 10 |
| `embedding_model` | sentence-transformers/all-MiniLM-L6-v2 |
| `embedding_backend` | chroma |
| `collection_name` | papers-baseline |
| `top_k` | 4 |
| `run_timestamp_utc` | 2026-09-25T08:51:48.790180+00:00 |

## Evaluation Metrics

| Metric | Value |
| --- | ---: |
| `samples` | 10 |
| `retrieval_hit_rate` | 100.00% |
| `mean_token_f1` | 100.00% |
| `judge_accuracy` | 100.00% |
| `mean_judge_score` | 5.0000 |
| `ragas` | {'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'} |

## Data Quality

- Overall success: **True**
- GX success: **True**
- Freshness success: **True**
- Row count: **24**

| Expectation | Success | Observed | Unexpected |
| --- | --- | ---: | ---: |
| `expect_table_row_count_to_be_between` | True | 24 | N/A |
| `expect_column_values_to_not_be_null` | True | N/A | 0 |
| `expect_column_values_to_be_unique` | True | N/A | 0 |
| `expect_column_values_to_not_be_null` | True | N/A | 0 |
| `expect_column_values_to_not_be_null` | True | N/A | 0 |
| `expect_column_value_lengths_to_be_between` | True | N/A | 0 |

## Freshness SLA

| Field | Value |
| --- | --- |
| `latest_published` | 2026-07-22 |
| `oldest_published` | 2026-03-28 |
| `stale_rows` | 1 |
| `total_rows` | 24 |
| `stale_ratio` | 0.0417 |
| `threshold_days` | 180 |
| `max_stale_ratio` | 0.2500 |
| `is_fresh` | True |

## Conclusion

The baseline run preserves raw lineage, produces a cleaned embedding dataset, indexes the corpus, evaluates the same benchmark set used later for comparison, and records data quality plus freshness signals for observability.
