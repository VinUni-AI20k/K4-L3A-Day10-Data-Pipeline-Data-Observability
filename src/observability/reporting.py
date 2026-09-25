from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.utils import write_text


def _markdown_value(value: Any) -> str:
    """Format scalar report values without breaking Markdown tables."""
    if isinstance(value, bool):
        rendered = "PASS" if value else "FAIL"
    elif value is None:
        rendered = "N/A"
    elif isinstance(value, float):
        rendered = f"{value:.4f}"
    else:
        rendered = str(value)
    return rendered.replace("|", "\\|").replace("\n", " ")


def _metric_value(name: str, value: Any) -> str:
    if isinstance(value, float) and (
        "rate" in name.lower() or "accuracy" in name.lower()
    ):
        return f"{value:.2%}"
    return _markdown_value(value)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a self-contained Markdown report for the baseline phase."""
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Data source and artifacts",
        "",
        "| Item | Value |",
        "|---|---|",
    ]
    lines.extend(
        f"| {_markdown_value(key)} | {_markdown_value(value)} |"
        for key, value in source_summary.items()
    )

    lines.extend(
        [
            "",
            "## Retrieval and evaluation",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    for key, value in metrics.items():
        if key == "ragas":
            continue
        lines.append(f"| {_markdown_value(key)} | {_metric_value(key, value)} |")

    ragas = metrics.get("ragas")
    if ragas:
        lines.extend(
            [
                "",
                "### Ragas",
                "",
                "```json",
                json.dumps(ragas, indent=2, ensure_ascii=False),
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## Data quality gate",
            "",
            f"Overall status: **{_markdown_value(quality.get('success', False))}**",
            "",
            "| Expectation | Status |",
            "|---|---:|",
        ]
    )
    for result in quality.get("expectations", []):
        lines.append(
            f"| {_markdown_value(result.get('name'))} | "
            f"{_markdown_value(bool(result.get('success')))} |"
        )

    stale_ratio = freshness.get("stale_ratio", 0.0)
    maximum_stale_ratio = freshness.get("maximum_stale_ratio", 0.25)
    lines.extend(
        [
            "",
            "## Freshness",
            "",
            f"Freshness status: **{_markdown_value(freshness.get('is_fresh', False))}**",
            "",
            "| Item | Value |",
            "|---|---:|",
            f"| Latest publication | {_markdown_value(freshness.get('latest_published'))} |",
            f"| Oldest publication | {_markdown_value(freshness.get('oldest_published'))} |",
            f"| Freshness threshold (days) | {_markdown_value(freshness.get('freshness_threshold_days'))} |",
            f"| Stale papers | {_markdown_value(freshness.get('stale_rows'))} / {_markdown_value(freshness.get('total_rows'))} |",
            f"| Stale ratio | {float(stale_ratio):.2%} |",
            f"| Maximum allowed stale ratio | {float(maximum_stale_ratio):.2%} |",
            "",
        ]
    )
    write_text(Path(report_path), "\n".join(lines))


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
    """Write a comparison of baseline, corrupted and repaired pipeline states."""
    metric_names = [
        name
        for name in baseline_metrics
        if name != "ragas"
        and name in corrupted_metrics
        and name in repaired_metrics
    ]
    lines = [
        "# Data Corruption and Repair Report",
        "",
        "## Evaluation metrics",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Corruption delta | Repair delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in metric_names:
        baseline = baseline_metrics[name]
        corrupted = corrupted_metrics[name]
        repaired = repaired_metrics[name]
        if all(isinstance(value, (int, float)) for value in (baseline, corrupted, repaired)):
            corruption_delta: Any = corrupted - baseline
            repair_delta: Any = repaired - corrupted
        else:
            corruption_delta = "N/A"
            repair_delta = "N/A"
        lines.append(
            f"| {_markdown_value(name)} | {_metric_value(name, baseline)} | "
            f"{_metric_value(name, corrupted)} | {_metric_value(name, repaired)} | "
            f"{_metric_value(name, corruption_delta)} | {_metric_value(name, repair_delta)} |"
        )

    corrupted_results = {
        item.get("name"): bool(item.get("success"))
        for item in corrupted_quality.get("expectations", [])
    }
    repaired_results = {
        item.get("name"): bool(item.get("success"))
        for item in repaired_quality.get("expectations", [])
    }
    expectation_names = list(
        dict.fromkeys([*corrupted_results.keys(), *repaired_results.keys()])
    )
    lines.extend(
        [
            "",
            "## Data quality comparison",
            "",
            "| Check | Corrupted | Repaired |",
            "|---|---:|---:|",
            f"| Overall quality gate | {_markdown_value(corrupted_quality.get('success', False))} | {_markdown_value(repaired_quality.get('success', False))} |",
        ]
    )
    for name in expectation_names:
        lines.append(
            f"| {_markdown_value(name)} | "
            f"{_markdown_value(corrupted_results.get(name, False))} | "
            f"{_markdown_value(repaired_results.get(name, False))} |"
        )

    lines.extend(
        [
            "",
            "## Freshness comparison",
            "",
            "| Metric | Corrupted | Repaired |",
            "|---|---:|---:|",
            f"| Status | {_markdown_value(corrupted_freshness.get('is_fresh', False))} | {_markdown_value(repaired_freshness.get('is_fresh', False))} |",
            f"| Total rows | {_markdown_value(corrupted_freshness.get('total_rows'))} | {_markdown_value(repaired_freshness.get('total_rows'))} |",
            f"| Stale rows | {_markdown_value(corrupted_freshness.get('stale_rows'))} | {_markdown_value(repaired_freshness.get('stale_rows'))} |",
            f"| Stale ratio | {float(corrupted_freshness.get('stale_ratio', 0.0)):.2%} | {float(repaired_freshness.get('stale_ratio', 0.0)):.2%} |",
            f"| Latest publication | {_markdown_value(corrupted_freshness.get('latest_published'))} | {_markdown_value(repaired_freshness.get('latest_published'))} |",
            f"| Oldest publication | {_markdown_value(corrupted_freshness.get('oldest_published'))} | {_markdown_value(repaired_freshness.get('oldest_published'))} |",
            "",
            "## Outcome",
            "",
            "The corrupted dataset is expected to fail one or more quality checks. "
            "A successful repair restores the raw source records, uniqueness, required "
            "content and freshness before rebuilding the vector index.",
            "",
        ]
    )
    write_text(Path(report_path), "\n".join(lines))
