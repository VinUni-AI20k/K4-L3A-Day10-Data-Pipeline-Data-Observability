# Báo Cáo Nghiệm Thu Pha 1: Baseline RAG Pipeline

> **Ngày thực hiện:** 2026-07-22  
> **Trạng thái tổng thể:** HOÀN THÀNH (PASS)  
> **Bộ dữ liệu:** Crossref Academic Publications (24 records)

---

## 1. Tổng Quan Thu Thập Dữ Liệu (Source & Ingestion)

- **Nguồn dữ liệu:** Crossref REST API
- **Tổng số bản ghi tải về:** 24
- **Truy vấn nguồn (Query):** `agentic retrieval augmented generation large language model`
- **Bảo toàn dữ liệu gốc (Lineage):** Đã lưu trữ `crossref_response.json` và `crossref_records.json`.

---

## 2. Kiểm Định Chất Lượng Dữ Liệu (Data Observability)

### 2.1. Great Expectations 1.x (Quality Gate)
- **Trạng thái kiểm định:** **`PASS`**
- **Tổng số Expectation kiểm tra:** 4/4 passed
  1. `ExpectTableRowCountToBeBetween`: Số dòng trong khoảng [5, 5000].
  2. `ExpectColumnValuesToNotBeNull`: `paper_id`, `title`, `text_for_embedding` không bị rỗng.
  3. `ExpectColumnValuesToBeUnique`: `paper_id` là khóa duy nhất, không trùng lặp.
  4. `ExpectColumnValueLengthsToBeBetween`: Trường `summary` có độ dài >= 30 ký tự.

### 2.2. Freshness SLA Monitoring
- **Đánh giá độ tươi:** **`PASS`**
- **Bài báo mới nhất:** `2026-07-22`
- **Bài báo cũ nhất:** `2026-03-28`
- **Tỷ lệ bài báo quá hạn (> 180 ngày):** `4.2%` (Ngưỡng cho phép: <= 25%)

---

## 3. Đo Lường Hiệu Năng RAG Baseline

Đánh giá trên bộ kiểm thử chuẩn hóa gồm 10 câu hỏi đa dạng qua 4 dạng nghiệp vụ (`summary`, `authors`, `date`, `categories`):

| Chỉ số đánh giá | Giá trị Baseline | Đánh giá |
| :--- | :---: | :--- |
| **Retrieval Hit Rate** | **100.00%** | Khả năng truy xuất đúng tài liệu Ground Truth |
| **Mean Token F1** | **1.0000** | Độ chính xác từ ngữ giữa câu trả lời và Ground Truth |
| **Judge Accuracy** | **100.00%** | Tỷ lệ câu trả lời được LLM Judge chấm đúng |
| **Mean Judge Score** | **5.00 / 5.0** | Điểm số chất lượng trung bình của LLM Judge |

---

## 4. Kết Luận Pha 1

Hệ thống Baseline Pipeline đã hoàn thành trọn vẹn chu trình: Ingestion -> Cleaning -> Quality Gate (GX 1.x) -> Indexing -> Evaluation. Dữ liệu đầu vào chuẩn sạch giúp Agent đạt hiệu năng tối ưu, sẵn sàng cho thử thách tiêm lỗi dữ liệu (Data Corruption) ở Pha 2.
