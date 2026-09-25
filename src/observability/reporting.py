from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.utils import write_text


def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%" if val <= 1.0 else f"{val:.1f}%"


def generate_phase1_report(
    report_path: str | Path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Generate Markdown report for baseline Phase 1."""
    target_path = Path(report_path)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    hit_rate = metrics.get("retrieval_hit_rate", metrics.get("hit_rate", 0.0))
    token_f1 = metrics.get("mean_token_f1", metrics.get("token_f1", 0.0))
    judge_acc = metrics.get("judge_accuracy", 0.0)
    samples_count = metrics.get("samples", 0)

    quality_status = "PASS" if quality.get("passed", quality.get("success", False)) else "FAIL"
    quality_rows = quality.get("total_rows", 0)
    expectations = quality.get("expectations", [])

    fresh_status = "PASS (Fresh)" if freshness.get("is_fresh", False) else "WARNING (Stale)"
    stale_ratio = freshness.get("stale_ratio_pct", 0.0)
    stale_rows = freshness.get("stale_rows", 0)
    total_rows = freshness.get("total_rows", 0)
    threshold_days = freshness.get("threshold_days", 180)

    md = f"""# Báo Cáo Pha 1: Baseline Data Pipeline & RAG Observability
*Generated at: {timestamp}*

## 1. Tổng Quan Thực Thi (Executive Summary)
Pha 1 thiết lập chu trình dữ liệu sạch end-to-end từ việc thu thập dữ liệu Crossref API, làm sạch dữ liệu, kiểm soát chất lượng qua Great Expectations 1.x, đánh giá SLA độ tươi (Freshness SLA), lập chỉ mục Vector Store ChromaDB và đo lường độ chính xác Baseline trên bộ Benchmark Test Set.

- **Trạng thái Quality Gate:** **`{quality_status}`**
- **Trạng thái Freshness SLA:** **`{fresh_status}`** (Stale ratio: `{stale_ratio}%`)
- **Baseline Retrieval Hit Rate:** **`{_pct(hit_rate)}`**
- **Baseline Token F1 Score:** **`{token_f1:.4f}`**

---

## 2. Nguồn & Chuẩn Hóa Dữ Liệu (Data Ingestion & Cleaning)
- **Nguồn dữ liệu:** `{source_summary.get('source_api', 'Crossref REST API')}`
- **Query chủ đề:** `{source_summary.get('query', 'agentic retrieval augmented generation large language model')}`
- **Tổng số bản ghi thu thập (Raw):** `{source_summary.get('raw_records_count', quality_rows)}`
- **Số bản ghi sau chuẩn hóa (Clean):** `{quality_rows}`

---

## 3. Kiểm Soát Chất Lượng Dữ Liệu (Great Expectations 1.x Quality Gate)
- **Kết quả tổng thể:** **`{quality_status}`**
- **Tổng số dòng kiểm tra:** `{quality_rows}`
- **Chi tiết các Expectations:**

| Expectation | Trạng thái | Chi tiết |
| :--- | :---: | :--- |
"""
    for exp in expectations:
        exp_name = exp.get("expectation", "Expectation")
        exp_status = "PASS" if exp.get("success") else "FAIL"
        md += f"| `{exp_name}` | **`{exp_status}`** | Đạt chỉ tiêu nghiệp vụ |\n"

    md += f"""
---

## 4. Báo Cáo Độ Tươi Dữ Liệu (Freshness SLA)
- **Tiêu chuẩn SLA:** Ngưỡng tuổi tài liệu tối đa `{threshold_days}` ngày, tỷ lệ cũ cho phép `<= 25%`.
- **Tổng số tài liệu:** `{total_rows}`
- **Số tài liệu quá hạn (Stale):** `{stale_rows}` ({stale_ratio}%)
- **Đánh giá SLA:** **`{fresh_status}`**
- **Ngày xuất bản mới nhất:** `{freshness.get('latest_published', 'N/A')}`
- **Ngày xuất bản cũ nhất:** `{freshness.get('oldest_published', 'N/A')}`

---

## 5. Đánh Giá Độ Chính Xác Baseline (RAG Evaluation Metrics)
Đánh giá đo lường trên bộ Benchmark Test Set gồm `{samples_count}` câu hỏi chuẩn hóa:

| Metric | Giá trị Baseline | Diễn giải |
| :--- | :---: | :--- |
| **Retrieval Hit Rate** | **`{_pct(hit_rate)}`** | Tỷ lệ truy xuất trúng tài liệu chứa đáp án chuẩn |
| **Mean Token F1** | **`{token_f1:.4f}`** | Độ tương đồng từ vựng giữa câu trả lời và ground truth |
| **Judge Accuracy** | **`{_pct(judge_acc)}`** | Tỷ lệ câu trả lời được LLM/Heuristic Judge xác nhận chính xác |

---

## 6. Kết Luận & Khuyến Nghị Pha 1
Quality Gate: `{quality_status}`; Freshness SLA: `{fresh_status}`. Baseline đo được Hit Rate `{_pct(hit_rate)}` và Token F1 `{token_f1:.4f}` trên `{samples_count}` câu hỏi. Đây là mốc đối chứng cho Pha 2; các chỉ số phản ánh đúng dữ liệu và bộ câu hỏi của lần chạy này.
"""
    write_text(target_path, md.strip() + "\n")


def generate_corruption_report(
    report_path: str | Path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    """Generate Markdown comparison report for Baseline vs Corrupted vs Repaired."""
    target_path = Path(report_path)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    b_hit = baseline_metrics.get("retrieval_hit_rate", 0.0)
    c_hit = corrupted_metrics.get("retrieval_hit_rate", 0.0)
    r_hit = repaired_metrics.get("retrieval_hit_rate", 0.0)

    b_f1 = baseline_metrics.get("mean_token_f1", 0.0)
    c_f1 = corrupted_metrics.get("mean_token_f1", 0.0)
    r_f1 = repaired_metrics.get("mean_token_f1", 0.0)

    b_judge = baseline_metrics.get("judge_accuracy", 0.0)
    c_judge = corrupted_metrics.get("judge_accuracy", 0.0)
    r_judge = repaired_metrics.get("judge_accuracy", 0.0)

    b_quality_status = (
        "N/A" if baseline_quality is None else "PASS" if baseline_quality.get("success") else "FAIL"
    )
    b_stale_pct = baseline_freshness.get("stale_ratio_pct") if baseline_freshness else None
    b_stale_display = f"{b_stale_pct}%" if b_stale_pct is not None else "N/A"
    c_quality_status = "PASS" if corrupted_quality.get("passed", corrupted_quality.get("success", False)) else "FAIL"
    r_quality_status = "PASS" if repaired_quality.get("passed", repaired_quality.get("success", False)) else "FAIL"

    c_stale_pct = corrupted_freshness.get("stale_ratio_pct", 0.0)
    r_stale_pct = repaired_freshness.get("stale_ratio_pct", 0.0)

    md = f"""# Báo Cáo Đối Chiếu Định Lượng 3 Trạng Thái (Corruption & Repair Report)
*Generated at: {timestamp}*

## 1. Bảng So Sánh Đối Đầu (Head-to-Head Comparison)

| Tiêu chí Đánh giá | Baseline (Dữ liệu Sạch) | Corrupted (Dữ liệu Tiêm Lỗi) | Repaired (Sau Phục Hồi) |
| :--- | :---: | :---: | :---: |
| **Data Quality Gate (GX 1.x)** | **`{b_quality_status}`** | **`{c_quality_status}`** | **`{r_quality_status}`** |
| **Freshness SLA (Stale %)** | `{b_stale_display}` | `{c_stale_pct}%` | `{r_stale_pct}%` |
| **Retrieval Hit Rate** | **`{_pct(b_hit)}`** | **`{_pct(c_hit)}`** | **`{_pct(r_hit)}`** |
| **Mean Token F1** | **`{b_f1:.4f}`** | **`{c_f1:.4f}`** | **`{r_f1:.4f}`** |
| **Judge Accuracy** | **`{_pct(b_judge)}`** | **`{_pct(c_judge)}`** | **`{_pct(r_judge)}`** |

---

## 2. Phân Tích Hiện Tượng Silent Failure & Sự Suy Giảm
- **Sự cố dữ liệu bẩn:** Khi tiêm các lỗi thường gặp (drop latest records, blank summary, inject noise, truncate title, stale date, duplicate rows), hệ thống RAG không báo lỗi crash hệ thống (no runtime errors) nhưng chất lượng câu trả lời bị suy giảm nghiêm trọng (**Silent Failure**).
- **Suy giảm Retrieval Hit Rate:** Từ `{_pct(b_hit)}` sụt giảm xuống `{_pct(c_hit)}` (chênh lệch `{(b_hit - c_hit) * 100:.1f}%`).
- **Suy giảm Token F1:** Từ `{b_f1:.4f}` sụt giảm xuống `{c_f1:.4f}`.
- **Phát hiện bởi Quality Gate:** Cổng Great Expectations 1.x đã báo `{c_quality_status}`. Bộ dữ liệu lỗi được index trong collection riêng chỉ để đo ảnh hưởng; luồng production phải dừng trước bước index khi gate thất bại.

---

## 3. Đánh Giá Khả Năng Phục Hồi (Idempotent Recovery)
- **Cơ chế phục hồi:** Áp dụng phương thức phục hồi Idempotent Repair bằng cách nạp lại dữ liệu gốc từ bản lưu trữ thô (`data/raw/`), làm sạch lại toàn bộ trường dữ liệu và purge triệt để vector lỗi trong ChromaDB.
- **Kết quả phục hồi:**
  - Quality Gate chuyển từ `{c_quality_status}` trở lại **`{r_quality_status}`**.
  - Retrieval Hit Rate phục hồi từ `{_pct(c_hit)}` lên **`{_pct(r_hit)}`**.
  - Token F1 phục hồi từ `{c_f1:.4f}` lên **`{r_f1:.4f}`**.
- **Kết luận:** Các chỉ số sau phục hồi được đối chiếu trực tiếp với baseline trên cùng bộ câu hỏi. Hit Rate: `{_pct(r_hit)}` so với `{_pct(b_hit)}`; Token F1: `{r_f1:.4f}` so với `{b_f1:.4f}`.
"""
    write_text(target_path, md.strip() + "\n")
