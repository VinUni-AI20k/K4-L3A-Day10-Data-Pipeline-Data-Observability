# Phase 1 — Baseline Data Pipeline Report

## Source and lineage

| Field | Value |
| --- | --- |
| Source | Crossref REST API |
| Mode | offline parsed snapshot |
| Parsed records | 24 |
| Clean records | 24 |
| Run time (UTC) | 2026-09-25T08:19:21.515188+00:00 |
| Raw snapshot | `data\raw\crossref_records.json` |

## Baseline evaluation

| Metric | Value |
| --- | ---: |
| Samples | 10 |
| Retrieval hit rate | 100.0% |
| Mean token F1 | 1.000 |
| Judge accuracy | 100.0% |
| Mean judge score (1–5) | 5.000 |

## Data observability

| Signal | Result |
| --- | --- |
| GX expectations | PASSED |
| Overall quality gate | PASSED |
| Freshness SLA | PASSED |
| Stale rows | 1 / 24 (4.2%) |
| Publication range | 2026-03-28 → 2026-07-22 |

## Conclusion

The baseline data passed the automated quality and freshness gates before indexing. Evaluation was run against the fixed ten-question benchmark; detailed answers and metrics are stored in `data/results/`.
