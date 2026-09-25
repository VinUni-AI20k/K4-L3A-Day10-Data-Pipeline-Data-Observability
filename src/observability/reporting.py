from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path: Path | str,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
<<<<<<< HEAD
    """Generate the baseline Markdown report from measured artifacts.
=======
    """Write markdown report for baseline phase.
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)

    Sections:
    1. Source summary.
    2. Retrieval/evaluation metrics.
    3. Data quality and freshness.
    4. Write markdown to report_path.
    """
<<<<<<< HEAD
    ragas = metrics.get("ragas", {})
    ragas_status = ragas.get("skipped") or ragas.get("error") or "Completed"
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source and dataset",
        "",
        "| Signal | Value |",
        "|---|---:|",
        f"| Source | {source_summary.get('source', 'Crossref REST API')} |",
        f"| Raw records | {source_summary.get('raw_records', 0)} |",
        f"| Clean records | {source_summary.get('clean_records', 0)} |",
        f"| Indexed documents | {source_summary.get('indexed_documents', 0)} |",
        f"| Benchmark questions | {metrics.get('samples', 0)} |",
        "",
        "## Baseline evaluation",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Retrieval Hit Rate | {metrics.get('retrieval_hit_rate', 0):.4f} |",
        f"| Mean Token F1 | {metrics.get('mean_token_f1', 0):.4f} |",
        f"| LLM Judge Accuracy | {metrics.get('judge_accuracy', 0):.4f} |",
        f"| Mean LLM Judge Score | {metrics.get('mean_judge_score', 0):.2f} / 5 |",
        f"| Ragas | {ragas_status} |",
        "",
        "## Data quality gate",
        "",
        "| Signal | Value |",
        "|---|---:|",
        f"| Overall success | {quality.get('success', False)} |",
        f"| Successful expectations | {quality.get('statistics', {}).get('successful_expectations', 0)} |",
        f"| Failed expectations | {quality.get('statistics', {}).get('unsuccessful_expectations', 0)} |",
        "",
        "## Freshness SLA",
        "",
        "| Signal | Value |",
        "|---|---:|",
        f"| Latest publication | {freshness.get('latest_published')} |",
        f"| Oldest publication | {freshness.get('oldest_published')} |",
        f"| Stale rows | {freshness.get('stale_rows', 0)} / {freshness.get('total_rows', 0)} |",
        f"| Stale ratio | {freshness.get('stale_ratio', 0):.2%} |",
        f"| Is fresh | {freshness.get('is_fresh', False)} |",
        "",
        "## Reproducibility",
        "",
        "Run `python script/run_phase1.py` from the project root with the project environment activated.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
=======
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Extract values with defaults for safety
    hit_rate = metrics.get("retrieval_hit_rate", 0.0)
    token_f1 = metrics.get("mean_token_f1", 0.0)
    judge_acc = metrics.get("judge_accuracy", 0.0)
    judge_score = metrics.get("mean_judge_score", 0.0)
    ragas = metrics.get("ragas", {})

    quality_passed = quality.get("gate_passed", False)
    quality_success = quality.get("success", False)
    stale_ratio = freshness.get("stale_ratio", 0.0)
    is_fresh = freshness.get("is_fresh", False)

    lines = [
        "# Phase 1: Baseline RAG Pipeline Report",
        "",
        "## Source Summary",
        "",
        f"- **Records fetched:** {source_summary.get('records_fetched', 'N/A')}",
        f"- **Records after cleaning:** {source_summary.get('records_cleaned', 'N/A')}",
        f"- **Run date:** {source_summary.get('run_date', 'N/A')}",
        f"- **Source API:** {source_summary.get('source_api', 'N/A')}",
        f"- **Query:** {source_summary.get('source_query', 'N/A')}",
        f"- **Max results:** {source_summary.get('max_results', 'N/A')}",
        "",
        "## Retrieval & Evaluation Metrics",
        "",
        f"- **Retrieval Hit Rate:** {hit_rate:.2%}",
        f"- **Token F1 (mean):** {token_f1:.4f}",
        f"- **LLM Judge Accuracy:** {judge_acc:.2%}",
        f"- **LLM Judge Score (mean):** {judge_score:.2f} / 5.0",
        "",
    ]

    if ragas and not ragas.get("skipped"):
        lines.extend([
            "### RAGAS Metrics",
            "",
            f"- **Answer Relevancy:** {ragas.get('answer_relevancy', 'N/A')}",
            f"- **Context Precision:** {ragas.get('context_precision', 'N/A')}",
            f"- **Context Recall:** {ragas.get('context_recall', 'N/A')}",
            f"- **Faithfulness:** {ragas.get('faithfulness', 'N/A')}",
            "",
        ])
    elif ragas and ragas.get("skipped"):
        lines.append(f"*RAGAS evaluation skipped: {ragas['skipped']}*\n")

    lines.extend([
        "## Data Quality & Freshness",
        "",
        f"- **Quality Gate Passed:** {'✅ Yes' if quality_passed else '❌ No'}",
        f"- **GX Validation Success:** {'✅ Yes' if quality_success else '❌ No'}",
        f"- **Fresh Data:** {'✅ Yes' if is_fresh else '❌ No'}",
        f"- **Stale Ratio:** {stale_ratio:.2%} (threshold: 25%)",
        f"- **Freshness Threshold:** {freshness.get('freshness_threshold_days', 'N/A')} days",
        f"- **Latest Published:** {freshness.get('latest_published', 'N/A')}",
        f"- **Oldest Published:** {freshness.get('oldest_published', 'N/A')}",
        f"- **Stale Rows:** {freshness.get('stale_rows', 'N/A')} / {freshness.get('total_rows', 'N/A')}",
        "",
        "## Pipeline Status",
        "",
        "✅ **Baseline pipeline completed successfully.**",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)


def generate_corruption_report(
    report_path: Path | str,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
<<<<<<< HEAD
    """Generate a Markdown comparison of baseline, corrupted, and repaired runs."""
    def metric(payload: dict[str, Any], name: str) -> float:
        return float(payload.get(name, 0.0))

    lines = [
        "# Data Corruption and Idempotent Repair Report",
        "",
        "## Baseline vs. corrupted vs. repaired",
        "",
        "| Metric | Baseline | Corrupted | Repaired |",
        "|---|---:|---:|---:|",
        f"| Retrieval Hit Rate | {metric(baseline_metrics, 'retrieval_hit_rate'):.4f} | "
        f"{metric(corrupted_metrics, 'retrieval_hit_rate'):.4f} | {metric(repaired_metrics, 'retrieval_hit_rate'):.4f} |",
        f"| Mean Token F1 | {metric(baseline_metrics, 'mean_token_f1'):.4f} | "
        f"{metric(corrupted_metrics, 'mean_token_f1'):.4f} | {metric(repaired_metrics, 'mean_token_f1'):.4f} |",
        f"| Judge Accuracy | {metric(baseline_metrics, 'judge_accuracy'):.4f} | "
        f"{metric(corrupted_metrics, 'judge_accuracy'):.4f} | {metric(repaired_metrics, 'judge_accuracy'):.4f} |",
        f"| Mean Judge Score | {metric(baseline_metrics, 'mean_judge_score'):.2f} | "
        f"{metric(corrupted_metrics, 'mean_judge_score'):.2f} | {metric(repaired_metrics, 'mean_judge_score'):.2f} |",
        "",
        "## Quality and freshness signals",
        "",
        "| Signal | Corrupted | Repaired |",
        "|---|---:|---:|",
        f"| Quality gate success | {corrupted_quality.get('success', False)} | {repaired_quality.get('success', False)} |",
        f"| Failed expectations | {corrupted_quality.get('statistics', {}).get('unsuccessful_expectations', 0)} | "
        f"{repaired_quality.get('statistics', {}).get('unsuccessful_expectations', 0)} |",
        f"| Freshness SLA | {corrupted_freshness.get('is_fresh', False)} | {repaired_freshness.get('is_fresh', False)} |",
        f"| Stale rows | {corrupted_freshness.get('stale_rows', 0)} / {corrupted_freshness.get('total_rows', 0)} | "
        f"{repaired_freshness.get('stale_rows', 0)} / {repaired_freshness.get('total_rows', 0)} |",
        f"| Stale ratio | {corrupted_freshness.get('stale_ratio', 0):.2%} | "
        f"{repaired_freshness.get('stale_ratio', 0):.2%} |",
        "",
        "## Conclusion",
        "",
        "The corrupted run demonstrates silent quality degradation while the application remains executable. "
        "The repaired run rebuilds clean data and a separate vector collection from preserved raw records, "
        "making the recovery idempotent and reproducible.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
=======
    """Write markdown report comparing baseline/corrupted/repaired."""
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def fmt(val: float) -> str:
        return f"{val:.4f}"

    def status(val: bool) -> str:
        return "✅" if val else "❌"

    b_hit = baseline_metrics.get("retrieval_hit_rate", 0.0)
    c_hit = corrupted_metrics.get("retrieval_hit_rate", 0.0)
    r_hit = repaired_metrics.get("retrieval_hit_rate", 0.0)

    b_f1 = baseline_metrics.get("mean_token_f1", 0.0)
    c_f1 = corrupted_metrics.get("mean_token_f1", 0.0)
    r_f1 = repaired_metrics.get("mean_token_f1", 0.0)

    b_judge = baseline_metrics.get("judge_accuracy", 0.0)
    c_judge = corrupted_metrics.get("judge_accuracy", 0.0)
    r_judge = repaired_metrics.get("judge_accuracy", 0.0)

    lines = [
        "# Corruption Comparison Report",
        "",
        "## Metrics Comparison",
        "",
        "| Metric | Baseline | Corrupted | Repaired |",
        "|--------|----------|-----------|----------|",
        f"| Retrieval Hit Rate | {fmt(b_hit)} | {fmt(c_hit)} | {fmt(r_hit)} |",
        f"| Token F1 | {fmt(b_f1)} | {fmt(c_f1)} | {fmt(r_f1)} |",
        f"| LLM Judge Accuracy | {fmt(b_judge)} | {fmt(c_judge)} | {fmt(r_judge)} |",
        "",
        "## Quality Gate Status",
        "",
        "| Phase | Quality Passed | Fresh Data | Stale Ratio |",
        "|-------|---------------|------------|-------------|",
        f"| Baseline | {status(baseline_metrics.get('gate_passed', False))} | {status(True)} | {freshness_str(corrupted_freshness)} |",
        f"| Corrupted | {status(corrupted_quality.get('gate_passed', False))} | {status(corrupted_freshness.get('is_fresh', False))} | {freshness_str(corrupted_freshness)} |",
        f"| Repaired | {status(repaired_quality.get('gate_passed', False))} | {status(repaired_freshness.get('is_fresh', False))} | {freshness_str(repaired_freshness)} |",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def freshness_str(freshness: dict[str, Any]) -> str:
    ratio = freshness.get("stale_ratio", 0.0)
    return f"{ratio:.2%}"
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
