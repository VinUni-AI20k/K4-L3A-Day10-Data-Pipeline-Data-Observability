# 📋 TIẾN ĐỘ THỰC HIỆN BÀI LAB (DAY 10)
> **Data Pipeline & Data Observability for Production RAG**  
> Cập nhật lần cuối: 25-09-2026

---

## 📊 Tổng quan tiến độ

| Done | Mốc | Checkpoint | Nội dung chính | Trạng thái | Đầu ra cần đạt (Pass Signal) |
| :---: | :---: | :--- | :--- | :---: | :--- |
| [x] | **CP0** | Setup & Raw Ingestion | Thiết lập môi trường `.venv` & thu thập dữ liệu thô | 🟢 **Hoàn thành** | `.venv` kích hoạt, có 2 file `data/raw/*.json` |
| [ ] | **CP1** | Cleaning & Quality Gate | Chuẩn hóa dữ liệu, tính `age_days`, dựng Great Expectations 1.x | 🟡 Đang làm | `data/clean/papers_clean.csv`, GX check `True` |
| [ ] | **CP2** | Benchmark & ChromaDB | Tạo bộ đề `test_set.json`, build MiniLM embedding & ChromaDB | ⚪ Chưa làm | `data/eval/test_set.json`, Chroma `papers-baseline` |
| [ ] | **CP3** | Baseline Pipeline E2E | Chạy RAG baseline hoàn chỉnh, đo Hit Rate & Token F1 | ⚪ Chưa làm | `baseline_metrics.json`, `phase1_report.md` |
| [ ] | **CP4** | Synthetic Corruption | Tiêm 6 loại lỗi dữ liệu, đo lường độ suy giảm chất lượng RAG | ⚪ Chưa làm | `corruption_log.json`, `corrupted_metrics.json` |
| [ ] | **CP5** | Idempotent Repair | Tự động sửa lỗi từ raw data, xuất báo cáo đối chiếu 3 trạng thái | ⚪ Chưa làm | `corruption_report.md` (3 cột Baseline/Corrupted/Repaired) |
| [ ] | **CP6** | Live Demo & Nộp bài | Demo trước lớp, giải thích cơ chế, nộp link repo LMS | ⚪ Chưa làm | 100% test pass, hoàn thành demo |

---

## 🎯 Chi tiết từng Checkpoint & Nhiệm vụ

### 🟢 Checkpoint 0: Setup & Raw Data Ingestion (Phút 0 - 30)
- [x] **Task 0.1:** Khởi tạo môi trường ảo Python (`.venv`) và cài đặt thư viện dependencies.
- [x] **Task 0.2:** Viết logic crawl / đọc dữ liệu bài báo khoa học trong `src/ingestion/crossref.py`:
  - [x] Hoàn thiện `parse_crossref_payload()` (bóc tách DOI, title, summary, authors, categories, published).
  - [x] Hoàn thiện `fetch_source_records()` (gọi Crossref API hoặc tự động fallback đọc snapshot offline nếu mạng lỗi).
  - [x] Hoàn thiện `load_raw_records()` (đọc `data/raw/crossref_records.json`).
- [x] **Lệnh kiểm tra CP0:**
  ```powershell
  python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
  ```
  *(Đạt yêu cầu khi console in: `Tín hiệu hoàn thành: Đã tải 24 bài báo`)*

---

### ⚪ Checkpoint 1: Cleaning & Data Observability Gate (Phút 30 - 65)
- [ ] **Task 1.1:** Làm sạch dữ liệu trong `src/ingestion/cleaning.py`:
  - Chuẩn hóa text, loại bỏ khoảng trắng thừa, thẻ HTML/XML.
  - Tính toán `age_days = (run_date - published).days`.
  - Ghép trường `text_for_embedding`.
  - Khử trùng lặp bản ghi theo `paper_id`.
- [ ] **Task 1.2:** Dựng trạm kiểm soát chất lượng dữ liệu với Great Expectations 1.x trong `src/observability/quality.py`:
  - 4 Expectation gates: row count (5-5000), not null, unique paper_id, summary length >= 30.
  - Freshness SLA: cảnh báo nếu tỉ lệ bài báo cũ quá 180 ngày > 25%.
- [ ] **Lệnh kiểm tra CP1:**
  ```powershell
  python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
  ```

---

### ⚪ Checkpoint 2: Benchmark Test Set & Vector Database (Phút 65 - 95)
- [ ] **Task 2.1:** Sinh bộ đề thi chuẩn 10 câu hỏi (`test_set.json`) trong `src/evaluation/testset.py`:
  - 4 dạng câu hỏi: `summary`, `authors`, `date`, `categories`.
- [ ] **Task 2.2:** Xây dựng Vector Index ChromaDB trong `src/retrieval/vectordb.py`:
  - Nhúng vector bằng `all-MiniLM-L6-v2`.
  - Lưu vào collection `papers-baseline`.

---

### ⚪ Checkpoint 3: Baseline Pipeline End-to-End (Phút 95 - 120)
- [ ] **Task 3.1:** Hoàn thiện pipeline tích hợp trong `src/pipelines/phase1.py` và module đánh giá `src/evaluation/metrics.py`.
- [ ] **Task 3.2:** Chạy kiểm thử toàn bộ pha Baseline:
  ```powershell
  python script/run_phase1.py
  ```
- [ ] **Đầu ra:** Xuất `data/results/baseline_metrics.json` và `data/reports/phase1_report.md`.

---

### ⚪ Checkpoint 4: Synthetic Corruption & Đo Lường Suy Giảm (Phút 120 - 165)
- [ ] **Task 4.1:** Cài đặt module tiêm lỗi giả lập trong `src/ingestion/corruption.py` (tiêm 6 loại lỗi: missing value, duplicate, schema mismatch, summary truncation, stale date, semantic noise).
- [ ] **Task 4.2:** Đo lường sự tụt giảm của RAG metrics (Hit Rate, F1, Great Expectations validation thất bại).

---

### ⚪ Checkpoint 5: Idempotent Repair & Báo Cáo Đối Chiếu (Phút 165 - 210)
- [ ] **Task 5.1:** Triển khai cơ chế tự phục hồi Idempotent Repair trong `src/pipelines/corruption_flow.py` (kéo lại từ raw snapshot, làm sạch lại, build lại vector collection).
- [ ] **Task 5.2:** Chạy kiểm thử toàn bộ luồng so sánh:
  ```powershell
  python script/run_corruption_flow.py
  ```
- [ ] **Đầu ra:** Xuất bảng so sánh 3 trạng thái tại `data/reports/corruption_report.md`.

---

### ⚪ Checkpoint 6: Live Demo & Nộp bài (Phút 210 - 240)
- [ ] **Task 6.1:** Kiểm tra toàn bộ code qua smoke test.
- [ ] **Task 6.2:** Chuẩn bị kịch bản trình bày demo trước lớp.
