<<<<<<< HEAD
# Phase 1 Baseline Report

## Source and dataset

| Signal | Value |
|---|---:|
| Source | Crossref REST API |
| Raw records | 24 |
| Clean records | 24 |
| Indexed documents | 24 |
| Benchmark questions | 10 |

## Baseline evaluation

| Metric | Value |
|---|---:|
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| LLM Judge Accuracy | 1.0000 |
| Mean LLM Judge Score | 5.00 / 5 |
| Ragas | Set RUN_RAGAS=1 to enable the slower Ragas pass. |

## Data quality gate

| Signal | Value |
|---|---:|
| Overall success | True |
| Successful expectations | 6 |
| Failed expectations | 0 |

## Freshness SLA

| Signal | Value |
|---|---:|
| Latest publication | 2026-09-15 |
| Oldest publication | 2026-04-01 |
| Stale rows | 0 / 24 |
| Stale ratio | 0.00% |
| Is fresh | True |

## Reproducibility

Run `python script/run_phase1.py` from the project root with the project environment activated.
=======
# Phase 1: Baseline RAG Pipeline Report

## Source Summary

- **Records fetched:** 24
- **Records after cleaning:** 24
- **Run date:** 2026-09-25T08:51:08.725188+00:00
- **Source API:** Crossref REST API
- **Query:** agentic retrieval augmented generation large language model
- **Max results:** 24

## Retrieval & Evaluation Metrics

- **Retrieval Hit Rate:** 100.00%
- **Token F1 (mean):** 0.2699
- **LLM Judge Accuracy:** 20.00%
- **LLM Judge Score (mean):** 1.80 / 5.0

*RAGAS evaluation skipped: Set RUN_RAGAS=1 to enable the slower Ragas pass.*

## Data Quality & Freshness

- **Quality Gate Passed:** ✅ Yes
- **GX Validation Success:** ✅ Yes
- **Fresh Data:** ✅ Yes
- **Stale Ratio:** 0.00% (threshold: 25%)
- **Freshness Threshold:** 180 days
- **Latest Published:** 2026-09-15
- **Oldest Published:** 2026-04-01
- **Stale Rows:** 0 / 24

## Pipeline Status

✅ **Baseline pipeline completed successfully.**
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
