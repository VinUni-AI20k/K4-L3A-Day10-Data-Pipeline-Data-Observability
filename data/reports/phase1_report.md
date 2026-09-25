# Phase 1 Baseline Report

## Data source and artifacts

| Item | Value |
|---|---|
| source | Crossref REST API |
| query | agentic retrieval augmented generation large language model |
| filter | from-pub-date:2026-03-29,has-abstract:true |
| raw_records | 24 |
| clean_records | 24 |
| removed_records | 0 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection | papers-baseline |
| test_samples | 10 |

## Retrieval and evaluation

| Metric | Value |
|---|---:|
| samples | 10 |
| retrieval_hit_rate | 100.00% |
| mean_token_f1 | 0.9055 |
| judge_accuracy | 90.00% |
| mean_judge_score | 4.4000 |

### Ragas

```json
{
  "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
}
```

## Data quality gate

Overall status: **PASS**

| Expectation | Status |
|---|---:|
| row_count_between_5_and_5000 | PASS |
| paper_id_not_null | PASS |
| title_not_null | PASS |
| text_for_embedding_not_null | PASS |
| paper_id_unique | PASS |
| summary_length_at_least_30 | PASS |

## Freshness

Freshness status: **PASS**

| Item | Value |
|---|---:|
| Latest publication | 2026-07-22 |
| Oldest publication | 2026-03-28 |
| Freshness threshold (days) | 180 |
| Stale papers | 1 / 24 |
| Stale ratio | 4.17% |
| Maximum allowed stale ratio | 25.00% |
