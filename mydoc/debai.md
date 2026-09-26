# KẾ HOẠCH & HƯỚNG DẪN HOÀN THÀNH BÀI LAB DAY 10
## Data Pipeline & Data Observability for RAG

> **Môn học:** AI-ENGINEER-K4 — VinUni  
> **Thời lượng thực chiến:** 240 phút (4 tiếng)  
> **Hình thức:** Làm việc nhóm (Teamwork) từ 3 – 5 thành viên  
> **Hạn nộp bài (Deadline):** 23:59:59 ngày làm lab (hoặc theo thông báo chính thức trên VLearn LMS)  
> ⚠️ **LƯU Ý SỐNG CÒN:** Dù cả nhóm dùng chung 1 GitHub Repository, **TỪNG THÀNH VIÊN VẪN PHẢI TỰ NỘP ĐƯỜNG LINK REPO LÊN VLEARN LMS BẰNG TÀI KHOẢN CỦA MÌNH**. Quên nộp = 0 điểm!

---

## 1. TỔNG QUAN BÀI TOÁN & BẢN CHẤT NGHIỆP VỤ

### 1.1. Hiểm họa "Silent Failure" (Thất bại thầm lặng)
- Trong phần mềm truyền thống, lỗi sẽ gây crash (`throw Exception`).
- Trong AI Agent & RAG, khi **Data Pipeline bị lỗi** (thiếu dữ liệu, làm sạch sai, trùng lặp, dữ liệu cũ/mốc meo), hệ thống **KHÔNG HỀ BÁO LỖI**. Agent vẫn trả lời tự tin, trôi chảy nhưng **trả lời sai sự thật (Hallucination)**.
- **Mục tiêu của bài lab:** Đóng vai trò Kỹ sư Dữ liệu & MLOps, xây dựng một **Data Pipeline chuẩn chỉ** cho dữ liệu học thuật từ **Crossref Academic API**, tích hợp **Data Quality Gate** bằng **Great Expectations 1.x** và giám sát **Freshness SLA** để chặn đứng dữ liệu bẩn trước khi vào Vector Store (**ChromaDB**).

### 1.2. Kiến trúc luồng dữ liệu 7 tầng
```text
Crossref API (hoặc Snapshot Offline data/raw/crossref_response.json)
  ├── 1. Ingestion & Raw Preservation -> data/raw/crossref_records.json
  ├── 2. Cleaning & Transformation    -> data/clean/papers_clean.csv
  ├── 3. Data Observability Gate      -> Great Expectations 1.x & Freshness SLA
  ├── 4. Embedding & Vector Index     -> sentence-transformers (MiniLM) + ChromaDB
  ├── 5. Evaluation Baseline          -> Hit Rate, Token F1 (trên 10 câu test_set.json)
  ├── 6. Controlled Corruption        -> Tiêm 6 dạng lỗi dữ liệu thực tế
  └── 7. Idempotent Repair & Compare  -> Phục hồi từ Raw & So sánh 3 trạng thái
```

### 1.3. Cơ chế 2 chế độ (Dual-Mode)
- 🟢 **Chế độ Dev / Offline (Khuyến nghị):** Đọc trực tiếp từ file snapshot có sẵn `data/raw/crossref_response.json` (không lo mất mạng hoặc lỗi `429 Too Many Requests` từ Crossref).
- 🌐 **Chế độ Live API:** Gọi trực tiếp Crossref REST API khi cần cập nhật mới nhất.

---

## 2. LỘ TRÌNH 7 CHECKPOINTS (TIMELINE 240 PHÚT)

| Checkpoint | Thời lượng | Nội dung công việc | Sản phẩm đầu ra (Deliverables) | Lệnh & Tín hiệu hoàn thành |
| :--- | :---: | :--- | :--- | :--- |
| **CP0** | 0 – 30m | Khởi tạo môi trường, config `.env`, nạp raw data | Môi trường ảo `.venv`, `.env`, `data/raw/crossref_records.json` | In `Môi trường sẵn sàng`, tải đủ 24 bài báo |
| **CP1** | 30 – 65m | Data Cleaning, tính `age_days`, dựng Quality Gate GX 1.x | `src/ingestion/cleaning.py`, `src/observability/quality.py`, `papers_clean.csv` | Clean được 24 dòng, GX validation trả về `True` |
| **CP2** | 65 – 95m | Sinh Benchmark Test Set & Index ChromaDB | `src/evaluation/testset.py`, collection `papers-baseline` | Sinh đủ 10 câu hỏi test, index 24 docs |
| **CP3** | 95 – 120m | Chạy Baseline Pipeline End-to-End | `script/run_phase1.py`, `baseline_metrics.json`, `phase1_report.md` | Hit Rate & Token F1 hợp lệ, file report markdown hoàn tất |
| **CP4** | 120 – 165m | Tiêm 6 lỗi dữ liệu (Corruption) & Đo lường sụt giảm RAG | `src/ingestion/corruption.py`, `corruption_log.json`, `corrupted_metrics.json` | Log 6 dạng lỗi, metrics sụt giảm rõ rệt |
| **CP5** | 165 – 210m | Idempotent Repair từ Raw & Báo cáo đối chiếu 3 trạng thái | `script/run_corruption_flow.py`, `corruption_report.md`, `repaired_metrics.json` | Bảng so sánh 3 cột: Baseline vs Corrupted vs Repaired |
| **CP6** | 210 – 240m | Live Demo trên bảng, Q&A phản biện & Nộp bài LMS | Trình chiếu 3-5 phút trước lớp, 100% commit nhánh `main`, nộp LMS | Hoàn tất bảo vệ, 100% thành viên có commit & nộp link LMS |

---

## 3. CHI TIẾT CÁC PHẦN VIỆC CẦN CODE (CÁC KHỐI `TODO(student)`)

Dưới đây là danh sách toàn bộ các file mã nguồn cần triển khai:

### 3.1. `src/ingestion/crossref.py` (Raw Ingestion & Fallback)
- **Hàm `parse_crossref_payload(data: dict) -> list[PaperRecord]`:**
  - Bóc tách danh sách bài báo từ key `message.items`.
  - Chuẩn hóa: `paper_id` (DOI), `title`, `summary` (loại bỏ HTML/XML tag như `<jats:p>`), `authors`, `categories`, `published` (parse ISO format).
- **Hàm `fetch_source_records(settings)` & `load_raw_records()`:**
  - Hỗ trợ fallback: nếu API lỗi / mất mạng thì nạp ngay snapshot `data/raw/crossref_response.json`.
  - Ghi 2 artifact: `data/raw/crossref_response.json` (raw API response) và `data/raw/crossref_records.json` (danh sách `PaperRecord`).

### 3.2. `src/ingestion/cleaning.py` (Làm sạch & Pre-embed)
- **Hàm `build_clean_dataframe(records, run_date) -> pd.DataFrame`:**
  - Loại bỏ khoảng trắng thừa, chuẩn hóa định dạng.
  - Khử trùng lặp bản ghi theo khóa duy nhất `paper_id`.
  - Tính toán độ tuổi bài báo: `age_days = (run_date - published).days`.
  - Ghép trường `text_for_embedding` theo cấu trúc:
    ```text
    Title: <title>
    Authors: <authors>
    Published: <published>
    Categories: <categories>
    Summary: <summary>
    ```

### 3.3. `src/observability/quality.py` (Great Expectations 1.x & Freshness)
- **Cú pháp chuẩn GX 1.x (BẮT BUỘC KHÔNG DÙNG CÚ PHÁP CŨ):**
  ```python
  context = gx.get_context(mode="ephemeral")
  data_source = context.data_sources.add_pandas(name="papers_source")
  data_asset = data_source.add_dataframe_asset(name="papers_asset")
  batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
  batch = batch_def.get_batch(batch_parameters={"dataframe": df})
  ```
- **4 Expectations thiết yếu:**
  1. `ExpectTableRowCountToBeBetween`: Số dòng từ 5 đến 5000.
  2. `ExpectColumnValuesToNotBeNull`: Các cột `paper_id`, `title`, `text_for_embedding` không được null.
  3. `ExpectColumnValuesToBeUnique`: Cột `paper_id` là duy nhất.
  4. `ExpectColumnValueLengthsToBeBetween`: Cột `summary` có độ dài tối thiểu 30 ký tự.
- **Freshness SLA Monitoring:**
  - Tính tỷ lệ bài báo có `age_days > 180` ngày.
  - Nếu tỷ lệ > 25% $\rightarrow$ cảnh báo `is_fresh = False`.

### 3.4. `src/evaluation/testset.py` (Bộ đề thi Benchmark)
- **Hàm `build_test_set(df, output_path) -> list[dict]`:**
  - Sinh đủ 10 câu hỏi test trải đều trên 4 category:
    1. `summary`: Hỏi tóm tắt nội dung bài báo.
    2. `authors`: Hỏi ai là tác giả.
    3. `date`: Hỏi thời điểm xuất bản.
    4. `categories`: Hỏi chuyên ngành / lĩnh vực.
  - Cấu trúc từng câu: `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`.

### 3.5. `src/pipelines/phase1.py` (Baseline Pipeline End-to-End)
- Ghép nối tuần tự: Fetch Raw $\rightarrow$ Clean $\rightarrow$ Quality Gate GX 1.x $\rightarrow$ Index ChromaDB (`papers-baseline`) $\rightarrow$ Sinh `test_set.json` $\rightarrow$ Đánh giá RAG (Hit Rate, Token F1) $\rightarrow$ Xuất `baseline_metrics.json` và `data/reports/phase1_report.md`.

### 3.6. `src/ingestion/corruption.py` (Data Corruption Suite)
- **Triển khai 6 kịch bản lỗi:**
  1. `drop_latest`: Bỏ rơi 20% các bài báo mới nhất.
  2. `blank_summary`: Xóa trắng `summary` ở một số dòng.
  3. `inject_noise`: Chèn ký tự rác vô nghĩa vào tóm tắt.
  4. `truncate_title`: Cắt ngắn title xuống dưới 8 ký tự.
  5. `stale_date`: Lùi ngày xuất bản về 365 ngày trước.
  6. `duplicate_rows`: Nhân bản các dòng để tạo trùng lặp.
- Ghi nhật ký vào `data/results/corruption_log.json`.

### 3.7. `src/pipelines/corruption_flow.py` (Pha 2: Tiêm lỗi, Đánh giá, Phục hồi & So sánh)
- Nhúng dữ liệu bẩn vào collection ChromaDB `papers-corrupted`.
- Chạy đánh giá trên cùng tập testset $\rightarrow$ Xuất `corrupted_metrics.json` (chứng minh suy giảm / Silent Failure).
- Thực thi **Idempotent Repair**: Tự động load lại từ bản raw snapshot gốc `data/raw/crossref_records.json`, chạy lại cleaning, nạp vào collection `papers-repaired`.
- Chạy lại đánh giá $\rightarrow$ Xuất `repaired_metrics.json`.
- Xuất bảng so sánh đối đầu 3 trạng thái trong `data/reports/corruption_report.md`.

### 3.8. `src/observability/reporting.py` (Báo cáo Markdown đối chiếu)
- `generate_phase1_report(...)`: Sinh báo cáo Baseline.
- `generate_corruption_report(...)`: Sinh bảng so sánh 3 cột định lượng: **Baseline vs Corrupted vs Repaired**.

---

## 4. TIÊU CHÍ CHẤM ĐIỂM (RUBRIC - 100 ĐIỂM + 10 BONUS)

### 4.1. Thang điểm bắt buộc (100 điểm)
1. **Cấu trúc dự án & Quản lý môi trường (10đ):** Cấu trúc module chuẩn, setup ảo hóa qua `uv`/`pip`, không lỗi import path.
2. **Raw Data Ingestion & Lineage (15đ):** Tải và parse Crossref API, lưu 2 file raw artifact, hỗ trợ fallback offline.
3. **Data Cleaning & Pre-embed Modeling (15đ):** Lọc HTML tag, tính `age_days`, khử duplicate `paper_id`, ghép nối chuẩn `text_for_embedding`.
4. **Embedding & Vector Store Indexing (10đ):** Nạp vào ChromaDB với `all-MiniLM-L6-v2`, quản lý collection rõ ràng.
5. **Multi-Provider QA Agent (10đ):** Xử lý retrieval, kết nối LLM (Gemini/Mock/OpenAI), trích xuất answer chuẩn xác.
6. **Baseline Evaluation & Scoring (10đ):** Sinh bộ testset 10 câu (4 dạng), tính Hit Rate và Token F1 trên dữ liệu sạch.
7. **Data Observability (GX 1.x & Freshness SLA) (15đ):** Dùng đúng cú pháp GX 1.x, đủ 4 expectations, đo Freshness SLA cảnh báo dữ liệu cũ.
8. **Data Corruption Suite, Repair & Impact Analysis (15đ):** Tiêm đủ 6 dạng lỗi, chứng minh sụt giảm, phục hồi idempotent từ raw, báo cáo 3 trạng thái hoàn chỉnh.

### 4.2. Điểm thưởng Bonus (+10 điểm tối đa)
*(Chỉ xét khi phần bắt buộc đạt $\ge 85$ điểm)*
- **B1 (+5đ):** Interactive Observability Dashboard (Streamlit/Gradio) hiển thị trạng thái Data Quality, biểu đồ tuổi bài báo, Freshness.
- **B2 (+5đ):** Automated Self-Healing / Auto-Repair Pipeline tự động rollback khi GX fail.
- **B3 (+5đ):** End-to-End Automated Pytest Suite với CI / test script toàn diện coverage > 80%.

### 4.3. Các lỗi bị trừ điểm nặng (Cần tránh tuyệt đối)
- ❌ **Lộ API Key vào Git:** Trừ 20 điểm (hoặc 0 điểm nếu lộ ở public repo).
- ❌ **Bịa đặt số liệu báo cáo:** Trừ 20 điểm.
- ❌ **Đạo văn / Copy code nhóm khác:** Hủy kết quả bài lab (0 điểm).
- ❌ **Code không chạy được trên máy chấm:** Trừ 15 điểm.
- ❌ **Dùng sai cú pháp GX 1.x (dùng cú pháp cũ bị crash):** Trừ 10 điểm.
- ❌ **Hardcode đường dẫn tuyệt đối local (`C:\...` hay `D:\...`):** Trừ 5 điểm.
- ❌ **Thiếu các file quy ước (`TEAM.md`, `SUBMISSION.md`,...):** Trừ 5 điểm / file.
- ❌ **Không tự nộp link repo trên VLearn LMS:** 0 điểm cá nhân!

---

## 5. BỘ CHECKLIST NGHIỆM THU TRƯỚC KHI HẾT GIỜ

Nhóm cần kiểm tra kỹ danh sách sau trước 23:59:59:

- [ ] **Môi trường & Dependency:**
  - Lệnh test in ra `Môi trường sẵn sàng`:
    ```bash
    python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
    ```
- [ ] **Chạy thành công 2 script chính (Exit code 0):**
  - Chạy Pha 1: `python script/run_phase1.py`
  - Chạy Pha 2: `python script/run_corruption_flow.py`
- [ ] **Đầy đủ các artifacts dữ liệu:**
  - `data/raw/crossref_response.json` & `crossref_records.json`
  - `data/clean/papers_clean.csv` & `papers_clean.json`
  - `data/chroma/` (chứa dữ liệu vector)
  - `data/eval/test_set.json` (đủ 10 câu hỏi)
  - `data/quality/baseline_quality_report.json`, `corrupted_quality_report.json`, `freshness_report.json`
  - `data/results/baseline_metrics.json`, `corruption_log.json`, `corrupted_metrics.json`, `repaired_metrics.json`
  - `data/reports/phase1_report.md` & `corruption_report.md`
- [ ] **Hồ sơ báo cáo:**
  - Điền đầy đủ thông tin nhóm vào `docs/TEAM.md` (họ tên, MSSV, vai trò, đóng góp chi tiết).
  - Hoàn thành báo cáo nhóm `report/group_report.md`.
  - Từng thành viên tạo file báo cáo cá nhân `report/<MSSV>_HoTen.md`.
- [ ] **Bảo mật:**
  - File `.env` tuyệt đối nằm trong `.gitignore`, không bao giờ commit lên GitHub.
- [ ] **Kiểm tra Contributor trên GitHub (Nhánh `main`):**
  - Vào repo trên GitHub $\rightarrow$ **Insights** $\rightarrow$ **Contributors**.
  - **100% thành viên trong nhóm bắt buộc phải có commit hiển thị trên nhánh `main`**.
- [ ] **Nộp link LMS cá nhân:**
  - Từng thành viên copy link repo (ví dụ: `https://github.com/<User>/K4-L3-DAY10-TenNhom-DataPipeline`) và bấm Submit trên cổng VLearn LMS trước hạn chót.

---

## 6. PHÂN CÔNG VAI TRÒ GỢI Ý (NHÓM 4 NGƯỜI)

1. **Thành viên 1 — Pipeline Lead & Integrator:**
   - Điều phối luồng, quản lý `core/config.py`, kết nối `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`. Theo dõi Git branch và Contributor.
2. **Thành viên 2 — Data Foundation & Ingestion Owner:**
   - Hoàn thiện `src/ingestion/crossref.py` (thu thập & fallback), `src/ingestion/cleaning.py` (làm sạch, tính `age_days`, pre-embed).
3. **Thành viên 3 — RAG & Vector Index Specialist:**
   - Phụ trách mô hình embedding MiniLM, quản lý ChromaDB collections, hoàn thiện logic truy vấn và QA Agent trong `src/retrieval/`.
4. **Thành viên 4 — Observability & Evaluation Lead:**
   - Dựng Great Expectations 1.x và Freshness SLA trong `src/observability/quality.py`, viết bộ tạo testset `src/evaluation/testset.py`, hoàn thiện hàm sinh báo cáo markdown trong `src/observability/reporting.py`.
