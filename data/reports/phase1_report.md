# Báo Cáo Pha 1 — Baseline Data Pipeline & Observability

## 1. Tổng Quan Thu Thập & Chuẩn Hóa Dữ Liệu (Source & Ingestion)
- **Nguồn dữ liệu:** Crossref REST API
- **Tổng số bài báo thu thập (Raw records):** 24
- **Tổng số bài báo sau làm sạch (Cleaned records):** 24
- **Vị trí lưu trữ Raw Lineage:** `data/raw/crossref_response.json` & `data/raw/crossref_records.json`
- **Vị trí lưu trữ Clean Data:** `data/clean/papers_clean.csv` & `data/clean/papers_clean.json`

## 2. Kiểm Soát Chất Lượng Dữ Liệu (Data Quality Gate & Freshness SLA)
- **Great Expectations 1.x Quality Gate:** `PASS (Thành công)`
- **Số quy tắc kiểm tra (Expectations):** 4 nhóm (Table row count, Non-null, Uniqueness DOI, Min length summary)
- **Freshness SLA Status:** `FRESH (Tươi mới)`
- **Số bài báo quá hạn (> 180 ngày):** 1 / 24 (4.2%)

## 3. Chỉ Số Hiệu Năng RAG Baseline (Baseline Benchmark Metrics)
- **Số lượng câu hỏi đánh giá:** 5
- **Retrieval Hit Rate:** `100.0%`
- **Mean Token F1:** `1.0000`
- **Judge Accuracy:** `100.0%`
- **Mean Judge Score (Thang 1-5):** `5.00 / 5.0`

## 4. Kết Luận Pha 1
Dữ liệu sạch đã vượt qua toàn bộ các bài kiểm tra chất lượng của Great Expectations 1.x và Freshness SLA, sẵn sàng làm nền tảng chuẩn mực (Ground Truth Baseline) cho các thử nghiệm đối chiếu ở Pha 2.
