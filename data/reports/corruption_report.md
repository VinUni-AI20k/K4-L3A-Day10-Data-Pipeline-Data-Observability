# Corruption and Idempotent Repair Report

## Quantitative comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Samples | 10 | 10 | 10 |
| Retrieval hit rate | 100.0% | 0.0% | 100.0% |
| Mean token F1 | 1.000 | 0.007 | 1.000 |
| Judge accuracy | 100.0% | 0.0% | 100.0% |
| Mean judge score | 5.000 | 1.000 | 5.000 |
| Data quality gate | PASSED | FAILED | PASSED |
| Freshness SLA | PASSED | FAILED | PASSED |
| Stale ratio | See baseline report | 100.0% | 4.2% |

## Observed failure signals

- Corrupted GX expectations: 2 failed.
- Corrupted stale rows: 24 of 24.
- Repair GX expectations: 6 passed.
- Repair stale rows: 1 of 24.

## Conclusion

The isolated corrupted collection demonstrates silent RAG degradation while the quality gate raises explicit failure signals. Repair rebuilds clean records from the preserved raw snapshot, recreates a separate vector collection, and reuses the identical benchmark. Re-running the repair is idempotent because no corrupted artifact is used as its source.
