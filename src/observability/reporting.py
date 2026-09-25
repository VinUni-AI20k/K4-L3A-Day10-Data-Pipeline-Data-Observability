from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text

METRIC_LABELS = [
    ("retrieval_hit_rate", "Hit Rate (Retrieval)"),
    ("mean_token_f1", "Token F1 (trung binh)"),
    ("judge_accuracy", "LLM Judge Accuracy"),
    ("mean_judge_score", "LLM Judge Score (1-5)"),
]


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, (int, float)):
        return f"{value:.4f}" if isinstance(value, float) else str(value)
    return str(value)


def _delta(current: Any, baseline: Any) -> str:
    if not isinstance(current, (int, float)) or not isinstance(baseline, (int, float)):
        return "n/a"
    diff = float(current) - float(baseline)
    arrow = "=" if abs(diff) < 1e-9 else ("v" if diff < 0 else "^")
    return f"{diff:+.4f} {arrow}"


def _quality_lines(title: str, quality: dict[str, Any]) -> list[str]:
    lines = [f"### {title}", ""]
    lines.append(f"- Ket qua Quality Gate (GX 1.x): **{_fmt(quality.get('success'))}**")
    lines.append(f"- So expectation danh gia: {_fmt(quality.get('evaluated_expectations'))}")
    lines.append(f"- So expectation that bai: {_fmt(quality.get('unsuccessful_expectations'))}")
    lines.append("")
    lines.append("| Expectation | Cot | Ket qua | Gia tri quan sat |")
    lines.append("| :--- | :--- | :---: | :--- |")
    for item in quality.get("expectations", []):
        lines.append(
            f"| {item.get('expectation')} | {item.get('column') or '-'} "
            f"| {_fmt(item.get('success'))} | {_fmt(item.get('observed_value'))} |"
        )
    lines.append("")
    return lines


def _freshness_lines(title: str, freshness: dict[str, Any]) -> list[str]:
    return [
        f"### {title}",
        "",
        f"- Ngay xuat ban moi nhat: `{_fmt(freshness.get('latest_published'))}`",
        f"- Ngay xuat ban cu nhat: `{_fmt(freshness.get('oldest_published'))}`",
        f"- So ban ghi qua han (> {_fmt(freshness.get('threshold_days'))} ngay): "
        f"{_fmt(freshness.get('stale_rows'))}/{_fmt(freshness.get('total_rows'))} "
        f"({_fmt(freshness.get('stale_ratio'))})",
        f"- Trang thai SLA: **{_fmt(freshness.get('is_fresh'))}**",
        f"- Canh bao: {freshness.get('alert', '-')}",
        "",
    ]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Xuat bao cao Markdown cho pha baseline (CP3)."""
    lines: list[str] = [
        "# Phase 1 Report - Baseline Data Pipeline (Day 10)",
        "",
        f"> Sinh tu dong luc: `{now_utc().isoformat()}`",
        "",
        "## 1. Nguon du lieu & Lineage",
        "",
        "| Hang muc | Gia tri |",
        "| :--- | :--- |",
    ]
    for key, value in source_summary.items():
        lines.append(f"| {key} | {_fmt(value)} |")

    lines += [
        "",
        "## 2. Chi so danh gia RAG (Baseline)",
        "",
        "| Chi so | Gia tri |",
        "| :--- | ---: |",
    ]
    for key, label in METRIC_LABELS:
        lines.append(f"| {label} | {_fmt(metrics.get(key))} |")
    lines.append(f"| So cau hoi danh gia | {_fmt(metrics.get('samples'))} |")

    ragas = metrics.get("ragas")
    if isinstance(ragas, dict):
        lines += ["", "**Ragas:** " + ", ".join(f"`{k}={_fmt(v)}`" for k, v in ragas.items())]

    lines += ["", "## 3. Data Quality Gate", ""]
    lines += _quality_lines("Great Expectations 1.x - Baseline", quality)

    lines += ["## 4. Freshness SLA", ""]
    lines += _freshness_lines("Do tuoi du lieu - Baseline", freshness)

    lines += [
        "## 5. Ket luan",
        "",
        f"- Quality Gate: **{_fmt(quality.get('success'))}** | Freshness SLA: **{_fmt(freshness.get('is_fresh'))}**",
        f"- Hit Rate baseline dat **{_fmt(metrics.get('retrieval_hit_rate'))}**, "
        f"Token F1 dat **{_fmt(metrics.get('mean_token_f1'))}**.",
        "- Day la moc tham chieu de doi chieu voi pha Corruption va Repair.",
        "",
    ]
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
    """Xuat bao cao Markdown doi chieu 3 trang thai Baseline / Corrupted / Repaired (CP5)."""
    lines: list[str] = [
        "# Corruption & Repair Report - Doi Chieu 3 Trang Thai (Day 10)",
        "",
        f"> Sinh tu dong luc: `{now_utc().isoformat()}`",
        "",
        "## 1. Bang so sanh hieu nang RAG",
        "",
        "| Chi so | Baseline (sach) | Corrupted (ban) | Repaired (phuc hoi) | Delta ban vs sach | Delta phuc hoi vs sach |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in METRIC_LABELS:
        base = baseline_metrics.get(key)
        bad = corrupted_metrics.get(key)
        fixed = repaired_metrics.get(key)
        lines.append(
            f"| {label} | {_fmt(base)} | {_fmt(bad)} | {_fmt(fixed)} "
            f"| {_delta(bad, base)} | {_delta(fixed, base)} |"
        )
    lines.append(
        f"| So cau hoi danh gia | {_fmt(baseline_metrics.get('samples'))} "
        f"| {_fmt(corrupted_metrics.get('samples'))} | {_fmt(repaired_metrics.get('samples'))} | - | - |"
    )

    lines += ["", "## 2. Data Quality Gate (Great Expectations 1.x)", ""]
    lines += _quality_lines("Tren du lieu bi tiem loi (Corrupted)", corrupted_quality)
    lines += _quality_lines("Sau khi phuc hoi (Repaired)", repaired_quality)

    lines += ["## 3. Freshness SLA", ""]
    lines += _freshness_lines("Corrupted", corrupted_freshness)
    lines += _freshness_lines("Repaired", repaired_freshness)

    hit_recovered = repaired_metrics.get("retrieval_hit_rate") == baseline_metrics.get("retrieval_hit_rate")
    lines += [
        "## 4. Phan tich & Ket luan",
        "",
        "- **Silent Failure:** tren du lieu bi tiem loi, Agent van tra loi troi chay nhung "
        f"Hit Rate tut tu {_fmt(baseline_metrics.get('retrieval_hit_rate'))} xuong "
        f"{_fmt(corrupted_metrics.get('retrieval_hit_rate'))} - khong he co exception nao duoc nem ra.",
        f"- **Quality Gate bat duoc loi:** GX tren du lieu ban cho ket qua "
        f"**{_fmt(corrupted_quality.get('success'))}** voi "
        f"{_fmt(corrupted_quality.get('unsuccessful_expectations'))} expectation that bai.",
        f"- **Freshness canh bao:** {corrupted_freshness.get('alert', '-')}",
        f"- **Idempotent Repair:** tai tao tu `data/raw/crossref_records.json` da dua Quality Gate ve "
        f"**{_fmt(repaired_quality.get('success'))}** va Hit Rate ve "
        f"**{_fmt(repaired_metrics.get('retrieval_hit_rate'))}**"
        + (" - phuc hoi 100% phong do baseline." if hit_recovered else "."),
        "- Chay lai `script/run_corruption_flow.py` bao nhieu lan cung cho ket qua phuc hoi giong nhau "
        "vi buoc repair doc lai tu ban sao luu thô, khong phu thuoc trang thai hien tai.",
        "",
    ]
    write_text(Path(report_path), "\n".join(lines))
