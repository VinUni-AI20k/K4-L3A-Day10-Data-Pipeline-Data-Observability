# BẢN PHÂN CÔNG NHIỆM VỤ & CHIẾN LƯỢC PHỐI HỢP NHÓM (4 THÀNH VIÊN)
## Đề tài: Data Pipeline & Data Observability for RAG (Day 10)

> **Mục tiêu tối thượng:** Hoàn thành xuất sắc 100/100 điểm chuẩn (+10 điểm bonus) trong 240 phút.  
> **Nguyên tắc cốt lõi:** **"Phân tách độc lập — Giao ước chuẩn hóa (Data Contract) — Song mã cùng chạy — Không dẫm chân, Không chờ đợi"**.

---

## 1. NGUYÊN TẮC VÀNG CHỐNG "DẪM CHÂN & CHỜ NHAU" (ANTI-BLOCKING PROTOCOL)

Để 4 thành viên làm việc song song 100% thời gian mà không bị tình trạng *"Tôi phải chờ bạn làm xong mới làm tiếp được"*, nhóm áp dụng 3 quy tắc kỹ thuật sau:

### Quy tắc 1: Đóng băng giao ước dữ liệu (Data Contract Freeze)
Mọi module giao tiếp với nhau qua cấu trúc chuẩn. Không ai được tự ý đổi tên cột hoặc kiểu dữ liệu:
- **`PaperRecord` (giữa Ingestion & Cleaning):** `paper_id` (str), `title` (str), `summary` (str), `authors` (list[str]), `categories` (list[str]), `primary_category` (str), `published` (str), `updated` (str), `abs_url` (str), `pdf_url` (str), `comment` (str).
- **`papers_clean.csv/json` (giữa Cleaning và RAG / Observability / Evaluation):** DataFrame bắt buộc có đủ các cột:
  - `paper_id`, `title`, `summary`, `authors`, `categories`, `published`
  - `age_days` (int)
  - `authors_joined` (str), `categories_joined` (str), `summary_chars` (int)
  - `text_for_embedding` (str định dạng 5 dòng: Title, Authors, Published, Categories, Summary)
- **`test_set.json` (giữa Evaluation và Pipeline):** List 10 items có: `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`.

### Quy tắc 2: Tận dụng Snapshot có sẵn để Dev song song ngay từ phút đầu tiên
- Dự án **đã có sẵn file snapshot** `data/raw/crossref_response.json` (24 bài báo mẫu).
- Thành viên phụ trách RAG (TV3), Observability (TV4) **KHÔNG CẦN CHỜ** Thành viên Ingestion (TV2) viết xong crawler! TV3 và TV4 có thể dùng ngay dữ liệu từ file này để test GX 1.x và ChromaDB.

### Quy tắc 3: Phân quyền File độc quyền (File Ownership Matrix)
Mỗi thành viên sở hữu danh sách file riêng, cam kết **không chỉnh sửa file của người khác** trên Git để triệt tiêu 100% nguy cơ Merge Conflict:

```text
Thành viên 1 (Lead & Integrator):    src/core/, src/pipelines/, script/, docs/SUBMISSION.md, docs/TEAM.md
Thành viên 2 (Data Foundation):      src/ingestion/crossref.py, src/ingestion/cleaning.py, src/ingestion/corruption.py
Thành viên 3 (RAG & Vector):         src/retrieval/ (embeddings.py, index.py, qa.py, agent.py, llm.py)
Thành viên 4 (Observability & Eval): src/observability/ (quality.py, reporting.py), src/evaluation/testset.py
```

---

## 2. BẢNG PHÂN CÔNG CHI TIẾT THEO 4 VAI TRÒ

---

### 👤 THÀNH VIÊN 1: PIPELINE LEAD & SYSTEM INTEGRATOR (Trưởng nhóm)
> **Sứ mệnh:** Giữ nhịp tiến độ, kết nối các mắt xích, điều phối pipeline end-to-end, quản trị Git và bảo vệ bài thi.

#### 🎯 Phạm vi phụ trách & File sở hữu:
- `src/core/config.py`, `src/core/utils.py`
- `src/pipelines/phase1.py` (Baseline Pipeline)
- `src/pipelines/corruption_flow.py` (Pha tiêm lỗi & Phục hồi)
- `script/run_phase1.py`, `script/run_corruption_flow.py`
- `docs/TEAM.md`, `report/group_report.md`

#### 📋 Nhiệm vụ cụ thể từng mốc thời gian:
1. **Phút 0 – 30 (Khởi tạo):**
   - Fork repo gốc về GitHub cá nhân: `K4-L3-DAY10-TenNhom-DataPipeline`.
   - Mời 3 thành viên làm Collaborator, nhắc nhở họ accept email.
   - Tạo các branch: `feat/data-foundation`, `feat/rag-vector`, `feat/observability-eval`, `feat/pipeline-integration`.
   - Setup môi trường ảo (`uv sync` hoặc `pip install -e .`), tạo `.env` mẫu.
2. **Phút 30 – 95 (Viết khung tích hợp):**
   - Viết sẵn khung điều phối luồng trong `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py` (gọi các hàm theo interface đã thống nhất).
   - Thiết lập cấu trúc thư mục đầu ra `data/raw`, `data/clean`, `data/results`, `data/reports`, `data/quality`.
3. **Phút 95 – 120 (Chốt Phase 1):**
   - Review và merge PR của TV2, TV3, TV4 vào nhánh `main`.
   - Chạy lệnh kiểm thử toàn tuyến: `python script/run_phase1.py`.
   - Kiểm tra các file artifact sinh ra: `papers_clean.csv`, `test_set.json`, `baseline_metrics.json`, `phase1_report.md`.
4. **Phút 120 – 210 (Tích hợp Phase 2 & Repair):**
   - Tích hợp hàm `corrupt_clean_dataframe` (từ TV2) và luồng Repair vào `src/pipelines/corruption_flow.py`.
   - Chạy kiểm thử: `python script/run_corruption_flow.py`.
   - Xác nhận bảng so sánh 3 trạng thái xuất hiện đúng chuẩn.
5. **Phút 210 – 240 (Nghiệm thu & Demo):**
   - Lên bảng thuyết trình Live Demo (3-5 phút): chỉ ra hiện tượng Silent Failure và cách Idempotent Repair khắc phục.
   - Kiểm tra GitHub: Vào **Insights > Contributors** đảm bảo cả 4 thành viên đều có commit trên nhánh `main`.
   - Đôn đốc cả 4 thành viên tự submit link repo lên VLearn LMS trước 23:59:59.

#### 🧪 Lệnh tự kiểm tra độc lập (Self-Verification):
```bash
python -c "from core.config import load_settings; s=load_settings(); print(f'Cấu hình chuẩn: {s.paths.project_dir}')"
python script/run_phase1.py
python script/run_corruption_flow.py
```

---

### 👤 THÀNH VIÊN 2: DATA FOUNDATION & RECOVERY OWNER (Kỹ sư Dữ liệu)
> **Sứ mệnh:** Xây dựng tầng móng dữ liệu sạch, đảm bảo Data Lineage, cơ chế Fallback offline và bộ kịch bản phá hủy/phục hồi dữ liệu.

#### 🎯 Phạm vi phụ trách & File sở hữu:
- `src/ingestion/crossref.py`
- `src/ingestion/cleaning.py`
- `src/ingestion/corruption.py`

#### 📋 Nhiệm vụ cụ thể từng mốc thời gian:
1. **Phút 0 – 30 (Ingestion & Raw Preservation):**
   - Viết hàm `parse_crossref_payload()` trong `src/ingestion/crossref.py`: bóc tách DOI (`paper_id`), `title`, lọc bỏ thẻ `<jats:p>` trong `summary`, parse tác giả, ngày tháng ISO.
   - Viết hàm `fetch_source_records()` với cơ chế fallback: nếu gọi API Crossref lỗi/mất mạng $\rightarrow$ đọc snapshot `data/raw/crossref_response.json`.
   - Viết hàm `load_raw_records()` đọc file JSON thành `list[PaperRecord]`.
   - Ghi 2 file: `data/raw/crossref_response.json` và `data/raw/crossref_records.json`.
2. **Phút 30 – 65 (Cleaning & Pre-embed Modeling):**
   - Hoàn thiện `build_clean_dataframe()` trong `src/ingestion/cleaning.py`:
     - Khử trùng lặp theo `paper_id`.
     - Tính `age_days = (run_date - published).days`.
     - Tạo `text_for_embedding` đúng định dạng chuẩn 5 phần: `Title`, `Authors`, `Published`, `Categories`, `Summary`.
     - Thêm các cột phụ: `authors_joined`, `categories_joined`, `summary_chars`.
   - Xuất dữ liệu sạch ra `data/clean/papers_clean.csv` và `papers_clean.json`.
3. **Phút 65 – 120 (Hỗ trợ tích hợp & Viết trước Corruption Suite):**
   - Commit code và tạo PR nhánh `feat/data-foundation`.
   - Bắt tay vào viết `src/ingestion/corruption.py` với 6 kịch bản lỗi:
     1. Drop latest records: Bỏ rơi 20% bài mới nhất.
     2. Blank summary: Xóa trắng tóm tắt ở một số dòng.
     3. Inject noise: Chèn chuỗi vô nghĩa vào tóm tắt.
     4. Truncate title: Cắt ngắn title `< 8` ký tự.
     5. Stale date: Lùi `published` về 365 ngày trước.
     6. Duplicate rows: Nhân đôi dòng dữ liệu.
4. **Phút 120 – 165 (Hoàn thiện Corruption & Idempotent Repair Logic):**
   - Ghi chi tiết các dòng bị sửa vào `data/results/corruption_log.json`.
   - Viết hàm phục hồi: đọc lại bản nguyên bản từ `data/raw/crossref_records.json` $\rightarrow$ chạy lại hàm clean để trả về DataFrame sạch hoàn toàn mà không cần sửa tay.
5. **Phút 165 – 240 (Báo cáo cá nhân & Hỗ trợ demo):**
   - Viết báo cáo cá nhân `report/<MSSV>_HoTen.md` mô tả kỹ thuật Data Lineage và tính Idempotent.
   - Sẵn sàng giải thích câu hỏi phản biện của Giảng viên về Ingestion/Cleaning.

#### 🧪 Lệnh tự kiểm tra độc lập (Self-Verification):
```bash
# Kiểm tra Ingestion
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"

# Kiểm tra Cleaning
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"

# Kiểm tra Corruption
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```

---

### 👤 THÀNH VIÊN 3: RAG SPECIALIST & VECTOR INDEX OWNER (Kỹ sư RAG & Agent)
> **Sứ mệnh:** Quản trị toàn bộ không gian Vector Database, cô lập các Collection, tối ưu mô hình Embedding và QA Agent.

#### 🎯 Phạm vi phụ trách & File sở hữu:
- `src/retrieval/embeddings.py`
- `src/retrieval/index.py`
- `src/retrieval/qa.py`
- `src/retrieval/agent.py`
- `src/retrieval/llm.py`

#### 📋 Nhiệm vụ cụ thể từng mốc thời gian:
1. **Phút 0 – 30 (Setup mô hình Embedding & Vector DB):**
   - Kiểm tra load mô hình embedding `sentence-transformers/all-MiniLM-L6-v2`.
   - Đảm bảo kết nối ChromaDB thư viện hoạt động ổn định trên thư mục local `data/chroma`.
2. **Phút 30 – 65 (Xây dựng & Kiểm chứng Vector Store Multi-Collection):**
   - Hoàn thiện cơ chế cô lập 3 collection tách biệt trong ChromaDB:
     - `papers-baseline`: Nạp từ dữ liệu sạch ban đầu.
     - `papers-corrupted`: Nạp từ dữ liệu sau khi bị tiêm độc tố.
     - `papers-repaired`: Nạp từ dữ liệu sau khi phục hồi.
   - Đảm bảo hàm `LocalEmbeddingIndex.build(...)` nạp đủ metadata (`paper_id`, `title`, `published`, `authors_joined`, `summary`, v.v.).
   - Kiểm tra truy vấn tương đồng Cosine (`index.search(query, top_k)`).
3. **Phút 65 – 95 (Hoàn thiện Multi-Provider QA Agent):**
   - Hoàn thiện module `src/retrieval/agent.py`: Agent trang bị 2 tool `semantic_search_papers` và `lookup_paper`.
   - Cấu hình chuyển đổi linh hoạt qua các provider (`gemini`, `openai`, `mock`) trong `src/retrieval/llm.py`.
   - Tạo prompt nghiêm ngặt chống ảo giác: chỉ trả lời dựa trên context tìm được, không có thì nói rõ không có.
4. **Phút 95 – 165 (Phối hợp đo lường suy giảm RAG):**
   - Hỗ trợ TV1 chạy test RAG trên Baseline $\rightarrow$ quan sát Hit Rate và Token F1 cao.
   - Khi có dữ liệu Corrupted từ TV2, nạp vào collection `papers-corrupted` $\rightarrow$ quan sát metrics bị tụt dốc thê thảm (minh chứng Silent Failure).
5. **Phút 165 – 240 (Phục hồi Vector & Báo cáo cá nhân):**
   - Nạp dữ liệu repaired vào collection `papers-repaired` $\rightarrow$ chứng minh metrics hồi phục tương đương baseline.
   - Viết báo cáo cá nhân `report/<MSSV>_HoTen.md` phân tích ảnh hưởng của vector drift khi văn bản bị nhiễu.

#### 🧪 Lệnh tự kiểm tra độc lập (Self-Verification):
```bash
# Kiểm tra Embedding model
python -c "from retrieval.embeddings import MiniLMEmbeddings; m=MiniLMEmbeddings('all-MiniLM-L6-v2'); v=m.embed_query('Machine Learning'); print(f'Embedding OK, dim={len(v)}')"

# Kiểm tra ChromaDB Collection
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); idx=LocalEmbeddingIndex.build(df, s); print('Index ChromaDB OK: ' + idx.collection_name)"
```

---

### 👤 THÀNH VIÊN 4: OBSERVABILITY & EVALUATION LEAD (Kỹ sư QA & Giám sát)
> **Sứ mệnh:** Dựng chốt kiểm dịch dữ liệu Great Expectations 1.x, đo lường Freshness SLA, thiết kế bộ đề thi chuẩn và lập báo cáo đối kháng 3 trạng thái.

#### 🎯 Phạm vi phụ trách & File sở hữu:
- `src/observability/quality.py`
- `src/observability/reporting.py`
- `src/evaluation/testset.py`

#### 📋 Nhiệm vụ cụ thể từng mốc thời gian:
1. **Phút 0 – 30 (Nghiên cứu cú pháp GX 1.x & Chuẩn bị đề thi):**
   - Đọc kỹ yêu cầu cú pháp Great Expectations 1.x (chạy `ephemeral context`, không dùng cú pháp cũ gây crash).
   - Thiết kế sẵn cấu trúc 10 câu hỏi đánh giá trong đầu cho 4 nhóm bài toán.
2. **Phút 30 – 65 (Dựng Trạm Kiểm Dịch Data Quality Gate & Freshness SLA):**
   - Viết `src/observability/quality.py`:
     - Cài đặt 4 Expectations bắt buộc:
       1. `ExpectTableRowCountToBeBetween`: Min 5, Max 5000.
       2. `ExpectColumnValuesToNotBeNull`: Cho `paper_id`, `title`, `text_for_embedding`.
       3. `ExpectColumnValuesToBeUnique`: Cho `paper_id`.
       4. `ExpectColumnValueLengthsToBeBetween`: Cho `summary` (min 30 ký tự).
     - Viết hàm `build_freshness_report()`: Tính tỷ lệ bài có `age_days > 180`. Nếu $> 25\%$ $\rightarrow$ `is_fresh = False`.
   - Xuất file kết quả: `data/quality/baseline_quality_report.json` và `freshness_report.json`.
3. **Phút 65 – 95 (Xây dựng Bộ Đề Thi Benchmark Chuẩn):**
   - Viết `src/evaluation/testset.py`: Tự động sinh bộ 10 câu hỏi test phủ đủ 4 nhóm:
     1. `summary`: Tóm tắt nội dung bài báo.
     2. `authors`: Ai là tác giả của công trình.
     3. `date`: Thời điểm bài báo được xuất bản.
     4. `categories`: Lĩnh vực chuyên ngành.
   - Xuất ra `data/eval/test_set.json` (đóng vai trò Ground Truth bất di bất dịch xuyên suốt bài lab).
4. **Phút 95 – 165 (Kiểm chứng GX trên Dữ liệu Lỗi & Báo cáo Markdown):**
   - Cho chạy `run_data_quality_checks` trên dữ liệu sau khi tiêm lỗi $\rightarrow$ chứng minh Great Expectations phát hiện vi phạm và trả về `success = False` $\rightarrow$ xuất `data/quality/corrupted_quality_report.json`.
   - Hoàn thiện `src/observability/reporting.py` để sinh:
     - `data/reports/phase1_report.md`
     - `data/reports/corruption_report.md` (chứa bảng so sánh 3 cột: Baseline vs Corrupted vs Repaired).
5. **Phút 165 – 240 (Phân tích chỉ số đối chiếu & Báo cáo cá nhân):**
   - Đọc kết quả từ 3 file metrics (`baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`) và đưa ra nhận xét định lượng: sụt giảm bao nhiêu % Hit Rate, F1, và phục hồi ra sao.
   - Viết báo cáo cá nhân `report/<MSSV>_HoTen.md`.

#### 🧪 Lệnh tự kiểm tra độc lập (Self-Verification):
```bash
# Kiểm tra Data Quality Gate GX 1.x
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"

# Kiểm tra Sinh Bộ Đề Thi 10 câu
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

---

## 3. MA TRẬN TIẾN TRÌNH & ĐIỂM CHẠM ĐỒNG BỘ (SYNC CHECKPOINTS)

Mặc dù 4 người làm độc lập, nhóm sẽ có **4 điểm chạm đồng bộ nhanh (Stand-up Sync - tối đa 2 phút/lần)**:

```mermaid
sequenceDiagram
    autonumber
    participant TV1 as TV1 (Lead)
    participant TV2 as TV2 (Data)
    participant TV3 as TV3 (RAG)
    participant TV4 as TV4 (Observability)

    Note over TV1,TV4: PHÚT 30 - SYNC 1: Chốt Môi Trường & Snapshot
    TV2->>TV1: Đã lưu raw records vào data/raw/
    TV3->>TV1: Đã test embed model thành công
    TV4->>TV1: Đã khởi tạo ephemeral context GX 1.x

    Note over TV1,TV4: PHÚT 95 - SYNC 2: Ghép Baseline Pipeline (CP3)
    TV2->>TV1: Bàn giao papers_clean.csv
    TV4->>TV1: Bàn giao test_set.json & GX suite
    TV3->>TV1: Bàn giao Chroma collection papers-baseline
    TV1->>TV1: Chạy python script/run_phase1.py -> Thành công!

    Note over TV1,TV4: PHÚT 165 - SYNC 3: Tiêm Lỗi & Phục Hồi (CP4 & CP5)
    TV2->>TV1: Bàn giao corruption suite (6 lỗi) & log
    TV4->>TV1: Đã ghi nhận GX bắt được lỗi (success=False)
    TV3->>TV1: Đã index collection corrupted & repaired
    TV1->>TV1: Chạy python script/run_corruption_flow.py -> Xuất báo cáo 3 cột!

    Note over TV1,TV4: PHÚT 210 - SYNC 4: Live Demo & Nộp Bài (CP6)
    TV1->>TV4: Cả 4 cùng rà soát checklist SUBMISSION.md
    TV1->>TV1: Kiểm tra Insights > Contributors trên GitHub nhánh main
    TV1,TV2,TV3,TV4->>TV1: Cả 4 thành viên nộp link lên VLearn LMS!
```

---

## 4. CHIẾN THUẬT SĂN ĐIỂM THƯỞNG BONUS (+10 ĐIỂM)

Sau khi hoàn thành phần bắt buộc lúc Phút 180 (đạt 85 - 100 điểm), nhóm có thể triển khai thêm 2 hạng mục bonus cực nhanh:

1. **Dashboard Trực Quan (Bonus B1 +5 điểm):**
   - **Người làm:** TV4 hoặc TV3.
   - **Cách làm:** Viết 1 file ngắn `script/dashboard.py` bằng **Streamlit** (khoảng 50 dòng code) đọc `baseline_quality_report.json`, `corrupted_quality_report.json`, và vẽ biểu đồ cột so sánh `Hit Rate` & `Token F1` giữa 3 trạng thái.
   - Chạy lệnh: `streamlit run script/dashboard.py`.
2. **Pytest CI Suite tự động (Bonus B3 +5 điểm):**
   - **Người làm:** TV1 hoặc TV2.
   - **Cách làm:** Tạo thư mục `tests/` với 3 file test:
     - `test_cleaning.py`: Kiểm tra DataFrame sạch có đủ cột, không bị null.
     - `test_gx_suite.py`: Kiểm tra GX bắt được lỗi khi đưa DataFrame hỏng vào.
     - `test_idempotency.py`: Chạy hàm repair 2 lần, khẳng định kết quả đồng nhất.
   - Chạy lệnh: `pytest tests/`.

---

## 5. BẢNG CHECKLIST HÀNH ĐỘNG DÀNH CHO TỪNG THÀNH VIÊN TRƯỚC 23:59:59

| Thành viên | Checklist bắt buộc phải hoàn thành | Trạng thái |
| :--- | :--- | :---: |
| **TV1 (Lead)** | - [ ] Tạo repo, mời đủ thành viên, phân nhánh Git<br>- [ ] Chạy thành công `run_phase1.py` và `run_corruption_flow.py`<br>- [ ] Hoàn thành `report/group_report.md` và `docs/TEAM.md`<br>- [ ] Xác nhận 100% thành viên có commit trên GitHub nhánh `main`<br>- [ ] Nộp link repo lên VLearn LMS bằng tài khoản cá nhân | 🔲 |
| **TV2 (Data)** | - [ ] Hoàn thành `crossref.py` (có fallback offline)<br>- [ ] Hoàn thành `cleaning.py` (tính `age_days`, `text_for_embedding`)<br>- [ ] Hoàn thành `corruption.py` (đủ 6 kịch bản lỗi)<br>- [ ] Hoàn thành file báo cáo cá nhân `report/<MSSV2>_HoTen.md`<br>- [ ] Có commit trên nhánh `main` và nộp link LMS cá nhân | 🔲 |
| **TV3 (RAG)** | - [ ] Quản lý 3 collection ChromaDB tách biệt rõ ràng<br>- [ ] Tối ưu QA Agent trả lời dựa trên context<br>- [ ] Đo lường độ sụt giảm của Retrieval Hit Rate khi dữ liệu bị lỗi<br>- [ ] Hoàn thành file báo cáo cá nhân `report/<MSSV3>_HoTen.md`<br>- [ ] Có commit trên nhánh `main` và nộp link LMS cá nhân | 🔲 |
| **TV4 (Eval)** | - [ ] Dựng xong Great Expectations 1.x chuẩn (ephemeral mode, 4 expectations)<br>- [ ] Hoàn thành Freshness SLA (cảnh báo `age_days > 180`)<br>- [ ] Sinh file `test_set.json` đủ 10 câu hỏi qua 4 nhóm nghiệp vụ<br>- [ ] Xuất file báo cáo `corruption_report.md` đủ 3 cột đối chiếu<br>- [ ] Hoàn thành file báo cáo cá nhân `report/<MSSV4>_HoTen.md`<br>- [ ] Có commit trên nhánh `main` và nộp link LMS cá nhân | 🔲 |

---
