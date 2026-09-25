# Báo Cáo Pha 1: Baseline Data Pipeline & RAG Observability
*Generated at: 2026-09-25 10:11:47 UTC*

## 1. Tổng Quan Thực Thi (Executive Summary)
Pha 1 thiết lập chu trình dữ liệu sạch end-to-end từ việc thu thập dữ liệu Crossref API, làm sạch dữ liệu, kiểm soát chất lượng qua Great Expectations 1.x, đánh giá SLA độ tươi (Freshness SLA), lập chỉ mục Vector Store ChromaDB và đo lường độ chính xác Baseline trên bộ Benchmark Test Set.

- **Trạng thái Quality Gate:** **`PASS`**
- **Trạng thái Freshness SLA:** **`PASS (Fresh)`** (Stale ratio: `0.0%`)
- **Baseline Retrieval Hit Rate:** **`100.0%`**
- **Baseline Token F1 Score:** **`0.5000`**

---

## 2. Nguồn & Chuẩn Hóa Dữ Liệu (Data Ingestion & Cleaning)
- **Nguồn dữ liệu:** `Crossref REST API`
- **Query chủ đề:** `agentic retrieval augmented generation large language model`
- **Tổng số bản ghi thu thập (Raw):** `24`
- **Số bản ghi sau chuẩn hóa (Clean):** `24`

---

## 3. Kiểm Soát Chất Lượng Dữ Liệu (Great Expectations 1.x Quality Gate)
- **Kết quả tổng thể:** **`PASS`**
- **Tổng số dòng kiểm tra:** `24`
- **Chi tiết các Expectations:**

| Expectation | Trạng thái | Chi tiết |
| :--- | :---: | :--- |
| `expect_table_row_count_to_be_between` | **`PASS`** | Đạt chỉ tiêu nghiệp vụ |
| `expect_column_values_to_not_be_null` | **`PASS`** | Đạt chỉ tiêu nghiệp vụ |
| `expect_column_values_to_be_unique` | **`PASS`** | Đạt chỉ tiêu nghiệp vụ |
| `expect_column_values_to_not_be_null` | **`PASS`** | Đạt chỉ tiêu nghiệp vụ |
| `expect_column_values_to_not_be_null` | **`PASS`** | Đạt chỉ tiêu nghiệp vụ |
| `expect_column_value_lengths_to_be_between` | **`PASS`** | Đạt chỉ tiêu nghiệp vụ |

---

## 4. Báo Cáo Độ Tươi Dữ Liệu (Freshness SLA)
- **Tiêu chuẩn SLA:** Ngưỡng tuổi tài liệu tối đa `180` ngày, tỷ lệ cũ cho phép `<= 25%`.
- **Tổng số tài liệu:** `24`
- **Số tài liệu quá hạn (Stale):** `0` (0.0%)
- **Đánh giá SLA:** **`PASS (Fresh)`**
- **Ngày xuất bản mới nhất:** `2026-09-15T00:00:00`
- **Ngày xuất bản cũ nhất:** `2026-04-01T00:00:00`

---

## 5. Đánh Giá Độ Chính Xác Baseline (RAG Evaluation Metrics)
Đánh giá đo lường trên bộ Benchmark Test Set gồm `10` câu hỏi chuẩn hóa:

| Metric | Giá trị Baseline | Diễn giải |
| :--- | :---: | :--- |
| **Retrieval Hit Rate** | **`100.0%`** | Tỷ lệ truy xuất trúng tài liệu chứa đáp án chuẩn |
| **Mean Token F1** | **`0.5000`** | Độ tương đồng từ vựng giữa câu trả lời và ground truth |
| **Judge Accuracy** | **`60.0%`** | Tỷ lệ câu trả lời được LLM/Heuristic Judge xác nhận chính xác |

---

## 6. Kết Luận & Khuyến Nghị Pha 1
Quality Gate: `PASS`; Freshness SLA: `PASS (Fresh)`. Baseline đo được Hit Rate `100.0%` và Token F1 `0.5000` trên `10` câu hỏi. Đây là mốc đối chứng cho Pha 2; các chỉ số phản ánh đúng dữ liệu và bộ câu hỏi của lần chạy này.
