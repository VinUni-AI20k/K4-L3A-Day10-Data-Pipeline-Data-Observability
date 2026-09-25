# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                                        |
| ------------------ | ----------------------------------------------- |
| Khóa/Lớp         | K4-L3-DAY10                                    |
| Tên nhóm         | GOHOME                                          |
| Repository         | https://github.com/Nam-phuong624/K4-L3A-Day10-Data-Pipeline-Data-Observability              |
| Ngày hoàn thành | 2026-09-25                                      |

### Thành viên và phân công

| STT | Họ và tên           | MSSV         | Vai trò chính                        | Module/deliverable sở hữu                                         |
| --: | -------------------- | ------------ | ------------------------------------- | ------------------------------------------------------------------ |
|   1 | Chử Trần Phương Nam | 2A202602675  | Trưởng nhóm / Pipeline Integrator    | `core/config.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
|   2 | Ngụy Khắc Phi Long  | 2A202602532  | Data Foundation & Recovery           | `ingestion/crossref.py`, `ingestion/cleaning.py`, `ingestion/corruption.py` |
|   3 | Nguyễn Đức Phát     | 2A202602753  | RAG & Vector Index                   | `retrieval/embeddings.py`, `retrieval/index.py`, `retrieval/qa.py` |
|   4 | Đỗ Thành Đạt        | 2A202602874  | Observability & Evaluation           | `observability/quality.py`, `evaluation/testset.py`, `observability/reporting.py` |

## 2. Tóm tắt kết quả

Nhóm GOHOME hoàn thành toàn bộ 6 checkpoint kỹ thuật (CP0–CP5). Pipeline gồm 2 luồng thực thi chính: Phase 1 (baseline) và Corruption Flow (3-state comparison).

**Baseline pipeline** sinh ra: 24 bài báo sạch từ Crossref API, ChromaDB collection `papers-baseline` với 24 documents, bộ test set 10 câu cố định, và báo cáo `phase1_report.md` với hit_rate=1.0 / token_f1=1.0 / GX 6/6 pass / is_fresh=True.

**Corruption ảnh hưởng rõ nhất:** `blank_summary` (3 records) là corruption gây hại nhất — làm `text_for_embedding` mất phần nội dung chính, vector không encode đủ ngữ nghĩa, khiến `mean_token_f1` giảm từ 1.0 xuống 0.59 (-41%). `stale_date` (6 records) đẩy stale_ratio lên 30.4% vượt ngưỡng 25%, trigger `is_fresh=False`.

**Sau repair:** Rebuild từ raw snapshot `crossref_records.json` phục hồi hoàn toàn — hit_rate=1.0, token_f1=1.0, GX pass, is_fresh=True.

**Giới hạn:** Mock LLM được dùng thay LLM thật (`LLM_PROVIDER=mock`) nên `judge_score` là deterministic, không phản ánh real-world answer quality. RAGAS metrics không chạy (cần `RUN_RAGAS=1`).

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    → data/raw/crossref_response.json  (raw response)
    → data/raw/crossref_records.json   (parsed records — raw snapshot for repair)
    → cleaning & data modeling         (age_days, text_for_embedding)
    → data/clean/papers_clean.json     (24 records sạch)
    → MiniLM embedding + ChromaDB      (collection: papers-baseline)
    → evaluation baseline              (hit_rate, token_f1, judge_accuracy)
    → GX 1.x quality checks            (6 expectations, ephemeral context)
    → freshness SLA check              (threshold 180 ngày, 25% stale)
    → data/reports/phase1_report.md

    --- corruption flow ---
    → 6 mutations injected             (data/results/corruption_log.json)
    → data/clean/papers_clean_corrupted.json
    → ChromaDB (papers-corrupted) → corrupted metrics
    → GX + freshness on corrupted data
    → repair từ raw snapshot (idempotent)
    → data/clean/papers_clean_repaired.json
    → ChromaDB (papers-repaired) → repaired metrics
    → GX + freshness on repaired data
    → data/reports/corruption_report.md (3-state comparison)
```

### Trách nhiệm của từng khối

| Khối             | Input                          | Xử lý chính                               | Output/artifact                          | Owner |
| ----------------- | ------------------------------ | ------------------------------------------ | ---------------------------------------- | ----- |
| Ingestion         | Crossref REST API              | Fetch với retry 429/503, parse JATS XML    | `data/raw/crossref_records.json`        | Long  |
| Cleaning          | `list[PaperRecord]`           | Chuẩn hóa schema, tính `text_for_embedding` | `data/clean/papers_clean.json`         | Long  |
| Embedding/index   | clean DataFrame                | MiniLM encode, ChromaDB upsert            | `data/chroma/`, `data/embeddings/`     | Phát  |
| Evaluation        | index + test_set               | Retrieval top-5, extraction, judge mock   | `data/results/baseline_metrics.json`   | Đạt   |
| Observability     | clean DataFrame                | GX 1.x 6 expectations, freshness SLA     | `data/quality/*.json`                  | Đạt   |
| Corruption/repair | clean DataFrame / raw snapshot | 6 mutations, idempotent rebuild           | `data/results/corruption_log.json`     | Long  |
| Orchestration     | tất cả module                  | Kết nối 7 bước Phase 1, 6 bước Flow      | `data/reports/*.md`                    | Nam   |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng                            |
| ---------------------------- | ------------------------------------------- |
| `LLM_PROVIDER`             | `mock`                                     |
| `LLM_MODEL`                | `mock`                                     |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2`  |
| Số lượng Crossref records | 24                                          |
| Retrieval `top_k`          | 5                                           |
| Freshness threshold          | 180 ngày, stale_ratio > 0.25 → is_fresh=False |
| Random seed                  | Không dùng (deterministic pipeline)        |

### Lệnh cài đặt

```bash
# Tạo conda env với Python 3.11 (bắt buộc — datetime.UTC không có trong Python 3.10)
conda create -n vin python=3.11 -y
conda activate vin

# Cài torch CPU-only trước để tránh download bản CUDA (~2.8GB)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Cài các thư viện còn lại
pip install -r requirements.txt
```

### Lệnh chạy

```bash
# Baseline pipeline
conda run -n vin python script/run_phase1.py

# Corruption flow (chạy sau phase1)
conda run -n vin python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái   | Thời điểm chạy gần nhất | Bằng chứng                              |
| ----------------- | ------------ | ----------------------------- | --------------------------------------- |
| Baseline pipeline | Thành công   | 2026-09-25                    | `data/reports/phase1_report.md`        |
| Corruption flow   | Thành công   | 2026-09-25                    | `data/reports/corruption_report.md`    |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                                                      |
| --------------------------- | ------------------------------------------------------------ |
| Source                      | Crossref REST API (`api.crossref.org/works`)                |
| Query/filter                | `query=knowledge graph&filter=type:journal-article&rows=50` |
| Thời điểm lấy dữ liệu | 2026-09-25 (cached tại `data/raw/`)                         |
| Số record nhận được    | 24 records sau khi lọc (có DOI + title + summary)           |
| Cơ chế retry/backoff      | Retry tự động khi gặp HTTP 429/503, fallback load từ cache  |

### Raw và clean schema

| Trường             | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa                          | Xử lý khi thiếu/sai      |
| ------------------ | ------------- | ---------- | --------------------------------- | -------------------------- |
| `paper_id`        | str (DOI)     | Có        | Unique identifier                 | Bỏ qua record             |
| `title`           | str           | Có        | Tiêu đề bài báo                  | Bỏ qua record             |
| `summary`         | str           | Có        | Abstract (strip JATS XML)        | Bỏ qua record             |
| `authors`         | list[str]     | Không     | Danh sách tác giả                | Default `[]`              |
| `published`       | str YYYY-MM-DD | Có       | Ngày publish                     | Default `1970-01-01`      |
| `categories`      | list[str]     | Không     | Subject categories               | Default `[]`              |
| `age_days`        | int           | Derived    | Số ngày từ published đến hôm nay | Tính từ `published`       |
| `text_for_embedding` | str        | Derived    | Input cho MiniLM                 | Ghép từ 5 trường khác     |

### Quy tắc cleaning

| Quy tắc                                  | Quality dimension | Record bị tác động | Cách xác minh                   |
| ----------------------------------------- | ----------------- | ------------------: | -------------------------------- |
| Loại record không có DOI                | Completeness      |                   0 | `len(clean_df) == 24`           |
| Loại record không có title hoặc summary | Completeness      |                   0 | GX null check pass              |
| Dedup theo `paper_id`                   | Uniqueness        |                   0 | GX unique check pass            |
| Strip JATS XML tags từ abstract         | Validity          |                  24 | Không còn `<jats:...>` trong summary |

`text_for_embedding` được tạo bằng cách ghép 5 trường theo format cố định:
```
Title: {title}
Authors: {authors_joined}
Published: {published}
Categories: {categories_joined}
Summary: {summary}
```
Format này phải khớp chính xác với extraction patterns trong `qa.py`.

`age_days` = `(date.today() - date.fromisoformat(published)).days` — dùng cho freshness SLA.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế                              |
| ---------------------------------------- | ---------------------------------------------- |
| Số câu hỏi                            | 10                                             |
| Các `question_type`                   | `summary` (3), `authors` (3), `date` (2), `categories` (2) |
| Ground-truth document ID                 | `paper_id` (DOI) của paper được chọn         |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2`     |
| Vector store/collection                  | ChromaDB, tên collection theo trạng thái      |
| Retrieval `top_k`                      | 5                                              |
| LLM provider/model                       | `mock` (deterministic, không cần API key)     |
| Test set dùng chung cho ba trạng thái  | `data/eval/test_set.json` (cached, không tái sinh) |

Test set được giữ nguyên cho cả 3 trạng thái vì đây là controlled experiment — muốn đo tác động của data thay đổi, không phải câu hỏi thay đổi. Nếu dùng test set khác nhau, không thể quy kết thay đổi metrics cho data corruption hay repair.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                     | Trạng thái | Ghi chú              |
| ------------------------ | ------------------------------------- | ------------ | --------------------- |
| Raw response/records     | `data/raw/`                          | Có          | 2 files JSON          |
| Cleaned dataset          | `data/clean/papers_clean.csv/json`   | Có          | 24 rows               |
| Embedding manifest       | `data/embeddings/papers_embeddings.json` | Có      | 24 vectors            |
| Evaluation set           | `data/eval/test_set.json`            | Có          | 10 câu, 3 loại        |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có          | hit_rate=1.0          |
| Quality/freshness        | `data/quality/`                      | Có          | 6 files JSON          |
| Baseline report          | `data/reports/phase1_report.md`      | Có          | GX 6/6 pass           |

### Baseline metrics

| Metric                 |  Giá trị | Diễn giải                                                           |
| ---------------------- | --------: | -------------------------------------------------------------------- |
| `retrieval_hit_rate` |    1.0000 | 10/10 câu hỏi đều tìm được đúng paper trong top-5                 |
| `mean_token_f1`      |    1.0000 | Extracted answer khớp hoàn toàn với ground-truth (token-level)     |
| `judge_accuracy`     |    1.0000 | Mock judge cho 10/10 câu điểm cao nhất                             |
| `mean_judge_score`   |    5.0000 | Điểm trung bình tối đa (thang 1-5)                                 |
| Ragas                  |       N/A | Chưa bật — cần `RUN_RAGAS=1`                                       |

Kết quả 1.0 trên baseline là expected — test set được sinh từ chính data dùng để index, và `qa.py` dùng pattern-based extraction trên metadata. Đây là closed-domain setup để tạo controlled baseline cho việc đo tác động corruption.

## 8. Data quality và freshness

### Quality checks

| Check                                 | Quality dimension | Ngưỡng/kỳ vọng    | Kết quả baseline | Bằng chứng                            |
| ------------------------------------- | ----------------- | ------------------ | ----------------- | -------------------------------------- |
| Row count between 5 and 5000          | Volume            | 5 ≤ n ≤ 5000      | Pass (24 rows)    | `baseline_quality_report.json`        |
| `paper_id` not null                  | Completeness      | 0 null             | Pass              | `baseline_quality_report.json`        |
| `title` not null                     | Completeness      | 0 null             | Pass              | `baseline_quality_report.json`        |
| `text_for_embedding` not null        | Completeness      | 0 null             | Pass              | `baseline_quality_report.json`        |
| `paper_id` unique                    | Uniqueness        | 0 duplicate        | Pass              | `baseline_quality_report.json`        |
| `summary` length ≥ 30               | Validity          | min_length=30      | Pass              | `baseline_quality_report.json`        |

### Freshness

| Thuộc tính               | Giá trị                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| Freshness được đo tại  | `papers_clean.json` (clean DataFrame, cột `published`)             |
| Timestamp mới nhất       | 2026-07-22                                                           |
| Ngưỡng freshness         | 180 ngày; stale_ratio > 25% → `is_fresh=False`                    |
| Trạng thái baseline      | Fresh (`is_fresh=True`, stale_ratio=0.0417, stale_rows=1/24)       |
| Lý do                     | Chỉ 1/24 records vượt 180 ngày (4.2%) — dưới ngưỡng 25%          |

## 9. Corruption scenarios và repair

| Corruption       | Cách tạo                            | Records bị tác động | Quality signal kỳ vọng         | Tác động thực tế                        | Cách repair                  |
| ---------------- | ------------------------------------ | ------------------: | ------------------------------ | --------------------------------------- | ----------------------------- |
| `drop_latest`   | Xóa 20% records mới nhất           |                   4 | Giảm coverage retrieval        | 2/10 test questions miss (hit_rate↓)   | Rebuild từ raw snapshot      |
| `blank_summary` | Đặt summary = "" trên 3 rows       |                   3 | GX length < 30 → FAIL          | F1=0 cho summary questions, token_f1↓ | Rebuild từ raw snapshot      |
| `inject_noise`  | Thêm `####NOISE####` vào summary    |                   3 | Embedding noise                | Retrieval kém chính xác hơn            | Rebuild từ raw snapshot      |
| `truncate_title`| Cắt title còn 7 ký tự              |                   3 | Mất context retrieval          | Embedding mất title signal             | Rebuild từ raw snapshot      |
| `stale_date`    | Lùi published 3 năm trên 6 rows    |                   6 | stale_ratio > 25% → is_fresh=False | stale_ratio=30.4%, `is_fresh=False` | Rebuild từ raw snapshot      |
| `duplicate_rows`| Nhân đôi 3 rows                    |                   3 | GX uniqueness FAIL             | GX `success=False`                    | Rebuild từ raw snapshot      |

**Corruption log:** `data/results/corruption_log.json` — Có. Log ghi đủ 6 mutation types, số lượng records bị tác động, và danh sách DOI cụ thể.

**Cơ chế repair:** Rebuild hoàn toàn từ `data/raw/crossref_records.json` — raw snapshot được bảo toàn và không bao giờ bị ghi đè. `load_raw_records()` load lại từ file gốc, `build_clean_dataframe()` chạy lại toàn bộ cleaning pipeline. Không patch trực tiếp trên data bị corrupt (không phải "che lỗi") mà là khôi phục từ nguồn đáng tin cậy — đảm bảo idempotency.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét                        |
| ------------------------ | -------: | --------: | -------: | ----------------------: | ------------: | -------------------------------- |
| `retrieval_hit_rate`   |   1.0000 |    0.8000 |   1.0000 |                 -0.2000 |        +0.2000 | Phục hồi 100%                   |
| `mean_token_f1`        |   1.0000 |    0.5882 |   1.0000 |                 -0.4118 |        +0.4118 | Phục hồi 100%                   |
| `judge_accuracy`       |   1.0000 |    0.6000 |   1.0000 |                 -0.4000 |        +0.4000 | Phục hồi 100%                   |
| `mean_judge_score`     |   5.0000 |    3.2000 |   5.0000 |                 -1.8000 |        +1.8000 | Phục hồi 100%                   |
| Quality checks pass/fail |     Pass |      Fail |     Pass |              2 FAIL (uniqueness, length) | Pass       | GX phát hiện đúng 2 loại vi phạm |
| Freshness status         |     True |     False |     True |       stale_ratio 4%→30% | is_fresh=True | Phục hồi hoàn toàn              |

**Hai kết luận nhân quả:**

1. `blank_summary` (3 records) + `duplicate_rows` (3 records) → GX `expect_column_value_lengths_to_be_between` FAIL và `expect_column_values_to_be_unique` FAIL → `success=False`. Đồng thời `blank_summary` làm `text_for_embedding` mất nội dung → `mean_token_f1` giảm từ 1.0 xuống 0.59 (-41%). Đây là trường hợp Silent Failure điển hình: pipeline không crash, nhưng answer quality giảm mạnh.

2. Rebuild từ `data/raw/crossref_records.json` (idempotent repair) → GX 6/6 pass → `is_fresh=True` → `retrieval_hit_rate` và `mean_token_f1` đều phục hồi về 1.0. Chứng minh rằng vấn đề nằm hoàn toàn ở data layer, không phải model hay infrastructure.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `corruption_report.md` hiển thị "(see phase1_report.md)" và "—" cho cột Baseline trong bảng Data Quality — bảng so sánh 3 trạng thái không đầy đủ.
- **Nguyên nhân:** `generate_corruption_report()` thiếu 2 params `baseline_quality` và `baseline_freshness` trong signature — caller truyền vào nhưng function không nhận, dẫn đến `TypeError`.
- **Cách xử lý:** Thêm `baseline_quality` và `baseline_freshness` vào signature, cập nhật bảng Data Quality render đầy đủ 3 dòng từ data thật. `corruption_flow.py` load 2 file JSON này từ `data/quality/` trước khi gọi function.
- **Cách xác minh:** `python script/run_corruption_flow.py` → đọc `data/reports/corruption_report.md` → bảng Data Quality & Freshness hiển thị ✅/❌ cho cả Baseline, Corrupted, Repaired.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại                      | Ảnh hưởng                                 | Hướng cải thiện có thể kiểm chứng                            |
| -------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- |
| Mock LLM — judge score deterministic  | Không đo được real answer quality          | Cấu hình `LLM_PROVIDER=gemini/openai` và bật `RUN_RAGAS=1`  |
| `text_for_embedding` format hardcode  | Nếu drift giữa cleaning và corruption thì embedding sai | Extract thành constant dùng chung ở `core/config.py`  |
| Không có cosine similarity threshold  | Retrieval trả về kết quả dù score thấp    | Thêm `min_score` filter trong `LocalEmbeddingIndex.search()` |
| Freshness threshold cố định (180 ngày) | Không phù hợp cho domain có data thay đổi nhanh | Expose `freshness_threshold_days` trong `settings.yaml`     |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set (`data/eval/test_set.json`).
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [ ] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
