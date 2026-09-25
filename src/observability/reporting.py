from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text

# Cac chi so duoc doi chieu giua 3 trang thai, theo dung key ma
# evaluation/metrics.py:evaluate_pipeline sinh ra.
METRIC_ROWS: tuple[tuple[str, str, bool], ...] = (
    # (key, nhan hien thi, cang cao cang tot)
    ("samples", "So cau hoi danh gia", True),
    ("retrieval_hit_rate", "Retrieval Hit Rate", True),
    ("mean_token_f1", "Mean Token F1", True),
    ("judge_accuracy", "LLM Judge Accuracy", True),
    ("mean_judge_score", "Mean Judge Score (1-5)", True),
)

# Nhan dep cho cac key thuong gap trong source_summary; key la khac se duoc
# in nguyen ban o cuoi bang nen phase1.py co the bo sung thoai mai.
SOURCE_LABELS: dict[str, str] = {
    "source_api": "Nguon du lieu",
    "source_query": "Query",
    "source_filter": "Filter",
    "raw_records": "So ban ghi raw",
    "clean_rows": "So dong sau cleaning",
    "dropped_rows": "So dong bi loai khi cleaning",
    "collection_name": "ChromaDB collection",
    "embedding_model": "Embedding model",
    "llm_provider": "LLM provider",
    "model_name": "LLM model",
    "top_k": "Top-K retrieval",
    "test_set_size": "Kich thuoc test set",
    "generated_at": "Thoi diem chay",
}


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _format_value(value: Any) -> str:
    """Dinh dang mot gia tri bat ky de dat vao o cua bang markdown."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (list, tuple)):
        return _escape_cell(", ".join(_format_value(item) for item in value)) or "n/a"
    if isinstance(value, dict):
        return _escape_cell("; ".join(f"{key}={_format_value(item)}" for key, item in value.items())) or "n/a"
    return _escape_cell(str(value))


def _format_delta(current: Any, baseline: Any, higher_is_better: bool = True) -> str:
    """Chenh lech so voi baseline, kem mui ten chi huong tot/xau."""
    if not isinstance(current, (int, float)) or not isinstance(baseline, (int, float)):
        return "n/a"
    if isinstance(current, bool) or isinstance(baseline, bool):
        return "n/a"
    delta = current - baseline
    if abs(delta) < 1e-9:
        return "0.0000 (=)"
    improved = delta > 0 if higher_is_better else delta < 0
    return f"{delta:+.4f} ({'tot hon' if improved else 'xau di'})"


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["_Khong co du lieu._", ""]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    lines.append("")
    return lines


def _expectation_rows(quality: dict[str, Any]) -> list[list[str]]:
    """Trich bang ket qua tung expectation cua Great Expectations."""
    rows: list[list[str]] = []
    for item in quality.get("expectations", []) or []:
        details = item.get("details") or {}
        observed = details.get("observed_value")
        unexpected = details.get("unexpected_count")
        note_parts: list[str] = []
        if observed is not None:
            note_parts.append(f"observed={_format_value(observed)}")
        if unexpected is not None:
            note_parts.append(f"unexpected={_format_value(unexpected)}")
        if not note_parts and details:
            note_parts.append(_format_value(details)[:120])
        rows.append(
            [
                f"`{item.get('name', 'unknown')}`",
                "PASS" if item.get("success") else "FAIL",
                _escape_cell(", ".join(note_parts)) or "-",
            ]
        )
    return rows


def _failed_expectations(quality: dict[str, Any]) -> list[str]:
    return [
        str(item.get("name", "unknown"))
        for item in (quality.get("expectations") or [])
        if not item.get("success")
    ]


def _freshness_rows(freshness: dict[str, Any]) -> list[list[str]]:
    keys = (
        ("latest_published", "Bai moi nhat"),
        ("oldest_published", "Bai cu nhat"),
        ("stale_rows", "So dong qua han"),
        ("total_rows", "Tong so dong"),
        ("stale_ratio", "Ty le qua han"),
        ("threshold_days", "Nguong tuoi (ngay)"),
        ("is_fresh", "Dat Freshness SLA"),
    )
    return [[label, _format_value(freshness.get(key))] for key, label in keys]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet bao cao markdown cho baseline phase ra `report_path`.

    `source_summary` la dict tu do do pipelines/phase1.py cung cap (cac key quen
    thuoc trong SOURCE_LABELS se duoc doi ten dep, key la van duoc in nguyen ban).
    `metrics` la summary tu evaluate_pipeline, `quality`/`freshness` lay tu
    observability/quality.py.
    """
    source_summary = source_summary or {}
    metrics = metrics or {}
    quality = quality or {}
    freshness = freshness or {}

    lines: list[str] = [
        "# Phase 1 Report - Baseline Pipeline (Du Lieu Sach)",
        "",
        f"_Sinh tu dong luc {now_utc().isoformat(timespec='seconds')}._",
        "",
        "## 1. Nguon Du Lieu & Cau Hinh",
        "",
    ]

    source_rows = [
        [label, _format_value(source_summary[key])]
        for key, label in SOURCE_LABELS.items()
        if key in source_summary
    ]
    source_rows.extend(
        [f"`{key}`", _format_value(value)]
        for key, value in source_summary.items()
        if key not in SOURCE_LABELS
    )
    lines.extend(_markdown_table(["Hang muc", "Gia tri"], source_rows))

    lines.extend(["## 2. Ket Qua Danh Gia RAG (Baseline)", ""])
    metric_rows = [
        [label, _format_value(metrics.get(key))]
        for key, label, _ in METRIC_ROWS
        if key in metrics
    ]
    lines.extend(_markdown_table(["Chi so", "Gia tri"], metric_rows))

    ragas = metrics.get("ragas")
    if isinstance(ragas, dict) and ragas:
        lines.extend(["### Ragas", ""])
        lines.extend(
            _markdown_table(
                ["Metric", "Gia tri"],
                [[f"`{key}`", _format_value(value)] for key, value in ragas.items()],
            )
        )

    lines.extend(
        [
            "## 3. Data Quality (Great Expectations 1.x)",
            "",
            f"**Trang thai tong the:** {'PASS' if quality.get('success') else 'FAIL'}",
            "",
        ]
    )
    if quality.get("message"):
        lines.extend([f"> {_escape_cell(str(quality['message']))}", ""])
    lines.extend(_markdown_table(["Expectation", "Ket qua", "Chi tiet"], _expectation_rows(quality)))

    failed = _failed_expectations(quality)
    if failed:
        lines.extend([f"**Expectation khong dat:** {', '.join(f'`{name}`' for name in failed)}", ""])

    lines.extend(["## 4. Freshness SLA", ""])
    lines.extend(_markdown_table(["Hang muc", "Gia tri"], _freshness_rows(freshness)))

    lines.extend(
        [
            "## 5. Nhan Xet",
            "",
            f"- Data quality gate: **{'PASS' if quality.get('success') else 'FAIL'}**"
            f"{'' if quality.get('success') else ' - du lieu chua du dieu kien de index an toan.'}",
            f"- Freshness SLA: **{'PASS' if freshness.get('is_fresh') else 'FAIL'}** "
            f"({_format_value(freshness.get('stale_rows'))}/{_format_value(freshness.get('total_rows'))} dong qua "
            f"{_format_value(freshness.get('threshold_days'))} ngay).",
        ]
    )
    if "retrieval_hit_rate" in metrics and "mean_token_f1" in metrics:
        lines.append(
            f"- Baseline RAG: Hit Rate {_format_value(metrics['retrieval_hit_rate'])}, "
            f"Token F1 {_format_value(metrics['mean_token_f1'])} tren "
            f"{_format_value(metrics.get('samples'))} cau hoi. Day la moc de doi chieu o Phase 2."
        )
    lines.append("")

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
    """Viet bao cao markdown doi chieu 3 trang thai Baseline / Corrupted / Repaired."""
    baseline_metrics = baseline_metrics or {}
    corrupted_metrics = corrupted_metrics or {}
    repaired_metrics = repaired_metrics or {}
    corrupted_quality = corrupted_quality or {}
    repaired_quality = repaired_quality or {}
    corrupted_freshness = corrupted_freshness or {}
    repaired_freshness = repaired_freshness or {}

    lines: list[str] = [
        "# Corruption Report - Doi Chieu Baseline vs Corrupted vs Repaired",
        "",
        f"_Sinh tu dong luc {now_utc().isoformat(timespec='seconds')}._",
        "",
        "## 1. Bang So Sanh Hieu Nang 3 Trang Thai",
        "",
    ]

    comparison_rows: list[list[str]] = []
    for key, label, higher_is_better in METRIC_ROWS:
        if key not in baseline_metrics and key not in corrupted_metrics and key not in repaired_metrics:
            continue
        baseline_value = baseline_metrics.get(key)
        comparison_rows.append(
            [
                label,
                _format_value(baseline_value),
                _format_value(corrupted_metrics.get(key)),
                _format_value(repaired_metrics.get(key)),
                _format_delta(corrupted_metrics.get(key), baseline_value, higher_is_better),
                _format_delta(repaired_metrics.get(key), baseline_value, higher_is_better),
            ]
        )
    lines.extend(
        _markdown_table(
            ["Chi so", "Baseline", "Corrupted", "Repaired", "Corrupted vs Baseline", "Repaired vs Baseline"],
            comparison_rows,
        )
    )

    lines.extend(["## 2. Data Quality Gate", ""])
    lines.extend(
        _markdown_table(
            ["Trang thai", "Ket qua tong the", "Expectation khong dat"],
            [
                [
                    "Corrupted",
                    "PASS" if corrupted_quality.get("success") else "FAIL",
                    ", ".join(f"`{name}`" for name in _failed_expectations(corrupted_quality)) or "-",
                ],
                [
                    "Repaired",
                    "PASS" if repaired_quality.get("success") else "FAIL",
                    ", ".join(f"`{name}`" for name in _failed_expectations(repaired_quality)) or "-",
                ],
            ],
        )
    )

    lines.extend(["## 3. Freshness SLA", ""])
    freshness_keys = (
        ("stale_rows", "So dong qua han"),
        ("total_rows", "Tong so dong"),
        ("stale_ratio", "Ty le qua han"),
        ("is_fresh", "Dat Freshness SLA"),
        ("latest_published", "Bai moi nhat"),
    )
    lines.extend(
        _markdown_table(
            ["Hang muc", "Corrupted", "Repaired"],
            [
                [label, _format_value(corrupted_freshness.get(key)), _format_value(repaired_freshness.get(key))]
                for key, label in freshness_keys
            ],
        )
    )

    lines.extend(["## 4. Phan Tich", ""])
    lines.extend(_analysis_lines(baseline_metrics, corrupted_metrics, repaired_metrics))
    lines.append("")

    write_text(Path(report_path), "\n".join(lines))


def _analysis_lines(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> list[str]:
    """Sinh nhan xet truc tiep tu so lieu do duoc (khong hard-code ket luan)."""
    notes: list[str] = []
    for key, label, _ in METRIC_ROWS:
        if key == "samples":
            continue
        baseline_value = baseline_metrics.get(key)
        corrupted_value = corrupted_metrics.get(key)
        repaired_value = repaired_metrics.get(key)
        if not isinstance(baseline_value, (int, float)) or not isinstance(corrupted_value, (int, float)):
            continue

        drop = baseline_value - corrupted_value
        drop_percent = (drop / baseline_value * 100) if baseline_value else 0.0
        note = f"- **{label}**: {baseline_value:.4f} -> {corrupted_value:.4f} khi du lieu bi lam ban"
        note += f" (giam {drop_percent:.1f}%)." if drop > 0 else " (khong giam)."
        if isinstance(repaired_value, (int, float)):
            gap = repaired_value - baseline_value
            if abs(gap) < 1e-9:
                note += f" Sau repair ve dung muc baseline ({repaired_value:.4f})."
            elif gap > 0:
                note += f" Sau repair dat {repaired_value:.4f}, cao hon baseline {gap:+.4f}."
            else:
                note += f" Sau repair dat {repaired_value:.4f}, van thieu {gap:+.4f} so voi baseline."
        notes.append(note)

    if not notes:
        return ["_Khong du so lieu de phan tich._"]

    recovered = all(
        isinstance(repaired_metrics.get(key), (int, float))
        and isinstance(baseline_metrics.get(key), (int, float))
        and repaired_metrics[key] >= baseline_metrics[key] - 1e-9
        for key, _, _ in METRIC_ROWS
        if key != "samples" and key in baseline_metrics
    )
    notes.append("")
    notes.append(
        "**Ket luan:** Idempotent repair doc lai tu raw snapshot da khoi phuc "
        + ("hoan toan cac chi so ve muc baseline." if recovered else "mot phan cac chi so, van con khoang cach so voi baseline.")
    )
    return notes
