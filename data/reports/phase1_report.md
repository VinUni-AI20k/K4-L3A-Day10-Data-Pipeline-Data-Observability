# Baseline Pipeline Evaluation Report (Phase 1)

## 1. Executive Summary

- **Quality Gate Status:** PASSED
- **Freshness SLA Status:** PASSED (Fresh)
- **Total Evaluated Documents:** 24

## 2. Data Source & Ingestion Summary

- **Source API:** Crossref REST API
- **Search Query:** agentic retrieval augmented generation large language model
- **Total Raw Records:** 24
- **Total Clean Rows:** 24
- **Collection Name:** papers-baseline

## 3. Data Observability & Quality (Great Expectations 1.x)

- **Overall Success:** True
- **Total Expectations Evaluated:** 6
- **Passed Expectations:** 6
- **Failed Expectations:** 0

### Freshness SLA Metrics
- **Freshness SLA:** True
- **Latest Published:** 2026-07-22
- **Oldest Published:** 2026-03-28
- **Stale Rows Ratio:** 0.0417 (Threshold: 180 days)

## 4. Benchmark Retrieval & Answer Evaluation Metrics

| Metric | Value | Description |
|---|---:|---|
| samples | 10 | Number of benchmark questions evaluated |
| retrieval_hit_rate | 1.0000 | Ratio of questions where ground-truth document was retrieved in top-k |
| mean_token_f1 | 1.0000 | Mean token overlap F1 score between prediction and ground-truth |
| judge_accuracy | 1.0000 | Ratio of answers marked materially correct by judge |
| mean_judge_score | 5 | Mean score given by judge (scale 1 - 5) |

