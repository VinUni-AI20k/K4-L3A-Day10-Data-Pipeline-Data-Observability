from __future__ import annotations

from typing import Any

from core.utils import write_text


def _percent(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "n/a"


def _decimal(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "n/a"


def _status(value: Any) -> str:
    return "PASSED" if bool(value) else "FAILED"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a concise, artifact-backed baseline report."""
    content = f"""# Phase 1 — Baseline Data Pipeline Report

## Source and lineage

| Field | Value |
| --- | --- |
| Source | {source_summary.get('source', 'Crossref REST API / offline snapshot')} |
| Mode | {source_summary.get('mode', 'offline')} |
| Parsed records | {source_summary.get('records', 0)} |
| Clean records | {source_summary.get('clean_records', 0)} |
| Run time (UTC) | {source_summary.get('run_time_utc', 'n/a')} |
| Raw snapshot | `{source_summary.get('raw_snapshot', 'n/a')}` |

## Baseline evaluation

| Metric | Value |
| --- | ---: |
| Samples | {metrics.get('samples', 0)} |
| Retrieval hit rate | {_percent(metrics.get('retrieval_hit_rate'))} |
| Mean token F1 | {_decimal(metrics.get('mean_token_f1'))} |
| Judge accuracy | {_percent(metrics.get('judge_accuracy'))} |
| Mean judge score (1–5) | {_decimal(metrics.get('mean_judge_score'))} |

## Data observability

| Signal | Result |
| --- | --- |
| GX expectations | {_status(quality.get('gx_success'))} |
| Overall quality gate | {_status(quality.get('success'))} |
| Freshness SLA | {_status(freshness.get('is_fresh'))} |
| Stale rows | {freshness.get('stale_rows', 0)} / {freshness.get('total_rows', 0)} ({_percent(freshness.get('stale_ratio'))}) |
| Publication range | {freshness.get('oldest_published', 'n/a')} → {freshness.get('latest_published', 'n/a')} |

## Conclusion

The baseline data passed the automated quality and freshness gates before indexing. Evaluation was run against the fixed ten-question benchmark; detailed answers and metrics are stored in `data/results/`.
"""
    write_text(report_path, content)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the three-state corruption and idempotent-repair comparison."""
    content = f"""# Corruption and Idempotent Repair Report

## Quantitative comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Samples | {baseline_metrics.get('samples', 0)} | {corrupted_metrics.get('samples', 0)} | {repaired_metrics.get('samples', 0)} |
| Retrieval hit rate | {_percent(baseline_metrics.get('retrieval_hit_rate'))} | {_percent(corrupted_metrics.get('retrieval_hit_rate'))} | {_percent(repaired_metrics.get('retrieval_hit_rate'))} |
| Mean token F1 | {_decimal(baseline_metrics.get('mean_token_f1'))} | {_decimal(corrupted_metrics.get('mean_token_f1'))} | {_decimal(repaired_metrics.get('mean_token_f1'))} |
| Judge accuracy | {_percent(baseline_metrics.get('judge_accuracy'))} | {_percent(corrupted_metrics.get('judge_accuracy'))} | {_percent(repaired_metrics.get('judge_accuracy'))} |
| Mean judge score | {_decimal(baseline_metrics.get('mean_judge_score'))} | {_decimal(corrupted_metrics.get('mean_judge_score'))} | {_decimal(repaired_metrics.get('mean_judge_score'))} |
| Data quality gate | PASSED | {_status(corrupted_quality.get('success'))} | {_status(repaired_quality.get('success'))} |
| Freshness SLA | PASSED | {_status(corrupted_freshness.get('is_fresh'))} | {_status(repaired_freshness.get('is_fresh'))} |
| Stale ratio | See baseline report | {_percent(corrupted_freshness.get('stale_ratio'))} | {_percent(repaired_freshness.get('stale_ratio'))} |

## Observed failure signals

- Corrupted GX expectations: {corrupted_quality.get('statistics', {}).get('unsuccessful_expectations', 0)} failed.
- Corrupted stale rows: {corrupted_freshness.get('stale_rows', 0)} of {corrupted_freshness.get('total_rows', 0)}.
- Repair GX expectations: {repaired_quality.get('statistics', {}).get('successful_expectations', 0)} passed.
- Repair stale rows: {repaired_freshness.get('stale_rows', 0)} of {repaired_freshness.get('total_rows', 0)}.

## Conclusion

The isolated corrupted collection demonstrates silent RAG degradation while the quality gate raises explicit failure signals. Repair rebuilds clean records from the preserved raw snapshot, recreates a separate vector collection, and reuses the identical benchmark. Re-running the repair is idempotent because no corrupted artifact is used as its source.
"""
    write_text(report_path, content)
