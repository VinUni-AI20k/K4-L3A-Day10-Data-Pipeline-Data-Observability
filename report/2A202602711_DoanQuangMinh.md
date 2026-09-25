# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đoàn Quang Minh           |
| MSSV               | 2A202602711                |
| Khóa/Lớp         | K4                        |
| Tên nhóm         | Phronesis                 |
| Vai trò chính    | Data Engineer (TV1)       |
| Repository         | github.com/.../K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25                |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Crossref Ingestion | `src/ingestion/crossref.py` | Crossref REST API | `data/raw/crossref_records.json` | Hoàn thành |
| Data Cleaning | `src/ingestion/cleaning.py` | `crossref_records.json` | `data/clean/papers_clean.csv`, `papers_clean.json` | Hoàn thành |
| Data Quality Gate | `src/observability/quality.py` | `papers_clean.csv` | `data/quality/baseline_quality_report.json` | Hoàn thành |
| Freshness Monitoring | `src/observability/quality.py` | `papers_clean.csv` | `data/quality/freshness_report.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Fix GX 1.x API usage | Toàn nhóm | Xác định API đúng cho GX 1.23.x: dùng `ValidationDefinition` thay vì gọi trực tiếp trên `Batch` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Parse Crossref payload: DOI chuẩn hóa, strip JATS XML, parse ISO date | `src/ingestion/crossref.py::parse_crossref_payload()` | 24 PaperRecord objects | Load raw records thành công |
| Dual-Mode fallback: HTTP 429/503 retry 3 lần → snapshot offline | `src/ingestion/crossref.py::fetch_source_records()` | Đọc từ `data/raw/crossref_response.json` khi API fail | Demo offline mode |
| Tính `age_days` = run_date - published, tạo `text_for_embedding` | `src/ingestion/cleaning.py::build_clean_dataframe()` | 24 clean rows với đầy đủ helper columns | `papers_clean.csv` |
| Khử trùng lặp theo `paper_id`, sort theo published desc | `src/ingestion/cleaning.py::build_clean_dataframe()` | 0 duplicate paper_id | Count sau dedupe |
| GX 1.x: 4 expectations (row count, not-null, unique, summary length) | `src/observability/quality.py::run_data_quality_checks()` | `passed=True` | Quality check status = True |
| Freshness: stale_ratio vs 25% threshold, báo cáo `is_fresh` | `src/observability/quality.py::build_freshness_report()` | `is_fresh=True`, `stale_ratio_pct=4.17%` | `freshness_report.json` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Xây dựng pipeline hoàn chỉnh từ nguồn dữ liệu Crossref đến tập dữ liệu sạch, đảm bảo chất lượng và độ tươi trước khi bước vào embedding và retrieval. Cụ thể: (1) parse chuẩn trường DOI, title, summary từ Crossref JSON, (2) tính tuổi dữ liệu để phát hiện bài cũ, (3) chuẩn hóa text phục vụ embedding vector, (4) thiết lập quality gate tự động với Great Expectations 1.x.

### Cách triển khai

**Crossref parsing & Dual-Mode:**
- Hàm `parse_crossref_payload()` duyệt `message.items[]`, chuẩn hóa DOI bằng `.lower().strip()`, strip JATS/XML tags bằng regex `</?[a-z][a-z0-9]*(?::[a-z][a-z0-9]*)?\s*>`, parse ngày từ `date-parts` thành ISO `YYYY-MM-DD`.
- Hàm `fetch_source_records()` dùng `urllib` vòng retry 3 lần cho HTTP 429/503 với exponential backoff (2s → 4s → 8s). Bất kỳ lỗi network/HTTP nào khác đều fallback ngay sang đọc `crossref_response.json`. Kết quả cuối cùng (live hoặc snapshot) đều được ghi đè vào snapshot để đảm bảo reproducibility.

**Data Cleaning:**
- `build_clean_dataframe()` nhận list `PaperRecord` + `run_date`, parse ISO date, tính `age_days = (run_date.date() - published_date.date()).days`.
- `text_for_embedding` ghép 5 trường theo template: `Title: ...\nAuthors: ...\nPublished: ...\nCategories: ...\nSummary: ...` — đảm bảo prompt cho embedding model có cấu trúc nhất quán.
- Dedupe bằng `drop_duplicates(subset=["paper_id"], keep="first")`, sort theo `published_date` giảm dần.

**Quality Gate (GX 1.x):**
- Dùng `gx.get_context(mode="ephemeral")` — chạy trên RAM, không sinh file checkpoint/data-source vào working directory.
- Tạo `ExpectationSuite` với 4 expectations, gắn vào `ValidationDefinition`, gọi `validation.run(batch_parameters={"dataframe": df})`.
- Mỗi expectation trả về `success` + `result` (unexpected_count, observed_value). Tổng hợp thành JSON report.

**Freshness Check:**
- Threshold = 180 ngày (configurable qua `settings.freshness_threshold_days`).
- `is_fresh = stale_ratio <= 0.25`. Nếu stale > 25% → cảnh báo trong JSON.

### Input, output và contract

| Thành phần | Mô tả |
| ------------------------------ | ------------------------------------------- |
| Input | Crossref REST API JSON response (hoặc `crossref_response.json` offline) |
| Output | `papers_clean.csv`, `papers_clean.json`, `freshness_report.json` |
| Module phụ thuộc | `core.config.Settings`, `ingestion.crossref.PaperRecord` |
| Module sử dụng output | Retrieval embedding (`src/retrieval/embeddings.py`), Evaluation (`src/evaluation/`) |
| Điều lỗi cần xử lý | HTTP 429/503 → retry + fallback; Missing DOI/title → skip row; Invalid date → age_days=None |

### Cách xác minh

```bash
# Full pipeline: raw → clean → quality gate
python -c "
from core.config import load_settings
from ingestion.crossref import load_raw_records
from ingestion.cleaning import build_clean_dataframe
from observability.quality import run_data_quality_checks, build_freshness_report
from datetime import datetime, timezone

s = load_settings()
records = load_raw_records(s.paths.raw_records_json)
df = build_clean_dataframe(records, datetime.now(timezone.utc))
s.paths.clean_csv.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(s.paths.clean_csv, index=False, date_format='iso')
df.to_json(s.paths.clean_json, orient='records', indent=2, date_format='iso')

res = run_data_quality_checks(df, s, 'test')
print(f'Quality: passed={res[\"passed\"]}')

fresh = build_freshness_report(df, s, s.paths.freshness_report)
print(f'Freshness: is_fresh={fresh[\"is_fresh\"]}, stale_ratio={fresh[\"stale_ratio_pct\"]}%')
"
```

- **Kết quả mong đợi:** Quality passed=True, Freshness is_fresh=True, stale_ratio < 25%
- **Kết quả thực tế:** Quality PASSED, Freshness is_fresh=True, stale_ratio=4.17%, stale_rows=1/24
- **Artifact/log:** `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`, `data/quality/freshness_report.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Great Expectations 1.23.x không có method `expect_*` trực tiếp trên object `Batch` trả về từ `add_batch_definition_whole_dataframe().get_batch()`.
- **Các phương án đã cân nhắc:**
  1. Dùng `batch.expect_table_row_count_to_be_between(...)` trực tiếp trên Batch — phương án theo tài liệu cũ, **không hoạt động** trên GX 1.23.1.
  2. Dùng `data_source.read_dataframe(df)` — trả về đối tượng kiểu Batch, vẫn không có method `expect_*`.
  3. Dùng `ExpectationSuite` + `ValidationDefinition` — pattern đúng cho GX 1.x.
- **Phương án đã chọn:** Phương án 3: tạo `ExpectationSuite`, add expectations, dùng `ValidationDefinition` với `validation.run(batch_parameters={"dataframe": df})`.
- **Lý do:** API cũ (legacy) đã bị loại bỏ từ GX 1.x. `ValidationDefinition.run()` là entry point chính thức cho GX 1.x ephemeral context. Cách này đúng với version 1.23.1 đang được cài đặt trong `.venv`.
- **Bằng chứng quyết định phù hợp:** Test thực tế: `validation.run()` trả về `ExpectationSuiteValidationResult` với đầy đủ `success`, `results[].exception_info`, `results[].result` — tất cả 4 expectations chạy thành công và trả kết quả đúng.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `AttributeError: 'Batch' object has no attribute 'expect_table_row_count_to_be_between'`
- **Lệnh hoặc bước tái hiện:** Gọi `batch.expect_table_row_count_to_be_between(...)` sau `batch_def.get_batch(batch_parameters={"dataframe": df})` trên GX 1.23.1.
- **Nguyên nhân gốc:** GX 1.x loại bỏ instance method `expect_*` trên `Batch` object. API đã thay đổi từ phiên bản 0.x/1.0 legacy sang fluent API.
- **Cách xử lý:** Thay thế bằng `ExpectationSuite` + `ValidationDefinition` pattern:
  ```python
  suite = context.suites.add(gx.ExpectationSuite(name=f"{report_name}_suite"))
  suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
  validation = context.validation_definitions.add(
      gx.ValidationDefinition(data=batch_def, suite=suite, name=f"{report_name}_validation")
  )
  result = validation.run(batch_parameters={"dataframe": df})
  ```
- **Cách xác minh sau khi sửa:** Chạy pipeline: Quality check status = **True**.
- **Điều học được:** Tài liệu Great Expectations trên internet phần lớn viết cho phiên bản 0.1x–0.1x. Khi dùng pip install thường được cài bản 1.23.x, phải kiểm tra `gx.__version__` và dùng API tương ứng. Luôn xác minh bằng `dir()` hoặc `inspect.signature()` khi tài liệu không đáng tin.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Dữ liệu đi từ Crossref đến vector index:**
   Crossref API → `crossref_response.json` → `parse_crossref_payload()` → `PaperRecord` list → `build_clean_dataframe()` → `papers_clean.csv` → `src/retrieval/embeddings.py` embed từng row (`text_for_embedding` column) → Chroma vector DB. Mỗi bước đều có quality gate và persistence checkpoint.

2. **Evaluation set và ground-truth document IDs:**
   `src/evaluation/testset.py` chứa câu hỏi + `ground_truth_doc_ids` (list DOI). Agent retrieval trả về top-k documents → so sánh với ground truth để tính `retrieval_hit_rate` (có ít nhất 1 doc khớp). Answer quality tính bằng `mean_token_f1` và judge score.

3. **Quality checks khác freshness monitoring:**
   Quality checks đo lường **cấu trúc nội tại**: row count, null, unique, summary length — phản ánh data integrity. Freshness monitoring đo lường **độ tươi thời gian**: age_days > threshold — phản ánh data relevance. Cả hai đều là tín hiệu observability nhưng đo lường khía cạnh khác nhau.

4. **Vì sao dùng cùng test set:**
   Để đảm bảo **controlled experiment** — so sánh apples-to-apples giữa baseline/corrupted/repaired. Nếu test set thay đổi, không thể phân biệt metric thay đổi do corruption/repair hay do test set khác. Ground truth document IDs phải cố định.

5. **Repair thành công:**
   Artifact: `data/clean/papers_clean_repaired.csv`, `data/embeddings/papers_embeddings_repaired.json`. Metric: retrieval_hit_rate và judge_score phục hồi về ngang baseline (hoặc chênh ≤ ngưỡng cho phép). Quality gate báo `passed=True` trên repaired data.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | [TBD] | [TBD] | [TBD] | Chờ chạy phase1 pipeline đầy đủ |
| `mean_token_f1` | [TBD] | [TBD] | [TBD] | Chờ evaluation |
| `judge_accuracy` | [TBD] | [TBD] | [TBD] | Chờ evaluation |
| `mean_judge_score` | [TBD] | [TBD] | [TBD] | Chờ evaluation |
| Quality checks | **PASSED** | [TBD] | [TBD] | Tất cả 4 expectations thông qua |
| Freshness status | **PASSED (4.17% stale)** | [TBD] | [TBD] | 1/24 bài cũ hơn 180 ngày |

### Kết luận từ số liệu

1. **[Data corruption]** → **[quality/freshness signal thay đổi]** → **[agent metric thay đổi]**
   Corruption (trong `corruption.py`) thay đổi nội dung bài báo (xoá summary, null hoá title, thêm duplicate) → Quality gate sẽ detect qua các expectation failures (unexpected null, duplicate paper_id) → Retrieval agent nhận corrupted documents → hit_rate giảm, judge_score giảm.

2. **[Repair action]** → **[quality/freshness signal phục hồi]** → **[agent metric phục hồi]**
   Repair (trong `corruption.py::repair()`) khôi phục corrupted fields từ snapshot gốc hoặc heuristic → Quality gate phục hồi `passed=True` → Retrieval nhận clean documents → metrics quay về baseline.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Null hoá `title` hoặc `paper_id` sẽ ảnh hưởng rõ nhất vì break uniqueness expectation (quality gate fail ngay) và break retrieval matching (document không còn nhận diện được). Summary truncation ít ảnh hưởng hơn vì retrieval dựa trên embedding vector, không chỉ trên text length.

Kết quả nào khác với kỳ vọng ban đầu?

Kỳ vọng: stale_ratio = 0% (tất cả bài đều mới). Thực tế: 4.17% (1/24 bài). Lý do: Crossref query filter `from-pub-date:180` vẫn trả về 1 bài cách đây ~180 ngày (2026-03-28). Giả thuyết: threshold filter so sánh `<` không chặt, hoặc Crossref tính ngày theo timezone khác. Đã xác minh: `freshness_report.json` ghi nhận đúng ngày oldest (2026-03-28) → dữ liệu đúng, threshold cần được điều chỉnh nếu cần strict hơn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data quality là nền tảng cho mọi downstream task.** Một quality gate tốt phát hiện vấn đề sớm (trước khi embed vào vector DB), tiết kiệm chi phí và thời gian debug retrieval/evaluation. Quality check ở checkpoint CP4 là guardian trước khi data đi vào RAG pipeline.

2. **Great Expectations 1.x có API hoàn toàn khác 0.x.** Học được cách đọc source code và dùng `inspect.signature()` / `dir()` để khám phá API khi tài liệu không chính xác. Pattern đúng cho 1.x: `ExpectationSuite` → `ValidationDefinition` → `run(batch_parameters={"dataframe": df})`.

3. **Dual-Mode fallback đảm bảo reproducibility trong lab.** Khi không có mạng hoặc API rate-limited, pipeline vẫn chạy được từ snapshot, đảm bảo tất cả thành viên nhóm có cùng data để phát triển và test.

### Nếu có thêm thời gian

Triển khai **incremental refresh**: thay vì fetch lại toàn bộ 24 bài, chỉ fetch các bài mới từ `from-pub-date` = lần run cuối. Giảm API calls, giữ delta history. Cách đo: so sánh số API calls sau 5 ngày liên tiếp, track `papers_clean.csv` diff size.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng. (TV1 pipeline: verified; evaluation metrics: marked TBD)
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đoàn Quang Minh
**Ngày xác nhận:** 2026-09-25
