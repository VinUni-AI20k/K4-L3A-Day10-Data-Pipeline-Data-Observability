# Phase 1 Baseline Report

Generated: 2026-09-25T10:12:14.491332+00:00

## Data Source Summary

- **source_api**: Crossref REST API
- **source_query**: agentic retrieval augmented generation large language model
- **raw_record_count**: 24
- **clean_record_count**: 24
- **embedding_model**: sentence-transformers/all-MiniLM-L6-v2
- **vector_collection**: papers-baseline
- **top_k**: 4

## Retrieval & Evaluation Metrics

- **Samples evaluated**: 5
- **Retrieval Hit Rate**: 1.0000
- **Mean Token F1**: 0.7745
- **LLM Judge Accuracy**: 0.6000
- **Mean LLM Judge Score**: 4.0000 / 5
- **Ragas**: skipped (Set RUN_RAGAS=1 to enable the slower Ragas pass.)

## Data Quality Gate (Great Expectations 1.x)

- **Overall status**: PASS
- **GX expectations status**: PASS
- **Row count**: 24

| Expectation | Result |
| :--- | :--- |
| row_count | PASS |
| paper_id_not_null | PASS |
| title_not_null | PASS |
| text_for_embedding_not_null | PASS |
| paper_id_unique | PASS |
| summary_length | PASS |

## Freshness Check

- **Status**: PASS
- **Latest published**: 2026-07-22
- **Oldest published**: 2026-03-28
- **Stale rows**: 1 / 24 (4.17%)
- **Freshness threshold**: 180 days
- **Max allowed stale ratio**: 25.00%

