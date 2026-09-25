# Group Report — Day 10: Data Pipeline & Data Observability

> Dùng mẫu này cho báo cáo chung của nhóm 3–5 thành viên. Thay toàn bộ nội dung trong dấu `[ ]` bằng thông tin và kết quả thực tế. Xóa các dòng hướng dẫn không còn cần thiết trước khi nộp.

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4             |
| Tên nhóm         | 2ae    |
| Repository         | https://github.com/vuxjqk/K4A-DAY10-2ae/tree/main |
| Ngày hoàn thành | 2026-09-25               |

### Thành viên và phân công

Nhóm có 2 thành viên, nên mỗi người phụ trách nhiều khối hơn so với phân công gợi ý trong starter repo.

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Bá Chính | 2A202602654 | Data Foundation & Observability | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/observability/quality.py`, `src/ingestion/corruption.py`; raw/quality/corruption artifacts |
| 2 | Trần Anh Vũ | 2A202602570 | RAG, Evaluation & Pipeline Integration | `src/evaluation/testset.py`, `src/evaluation/metrics.py`, `src/observability/reporting.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`; tích hợp và sinh các artifacts end-to-end |


## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành đầy đủ pipeline Day 10 từ ingestion đến repair. Dữ liệu đầu vào gồm 24 bài báo từ Crossref snapshot; sau cleaning vẫn giữ đủ 24 dòng hợp lệ. Dữ liệu sạch được kiểm định bằng Great Expectations 1.x và Freshness SLA trước khi index bằng `sentence-transformers/all-MiniLM-L6-v2` vào ChromaDB. Nhóm tạo bộ test cố định gồm 10 câu thuộc bốn loại `summary`, `authors`, `date`, `categories`, sau đó chạy baseline, corrupted và repaired trên cùng test set.

Baseline đạt `retrieval_hit_rate = 1.0`, `mean_token_f1 = 1.0`, `judge_accuracy = 1.0`, `mean_judge_score = 5`. Sau khi tiêm 6 dạng corruption, Quality Gate chuyển sang FAIL, Freshness chuyển sang stale, Hit Rate giảm còn `0.7`, Token F1 còn `0.772`, Judge Accuracy còn `0.8`. Tác động rõ nhất đến retrieval là `drop_latest_records`, làm mất tài liệu đích của 3/10 câu hỏi.

Repair không sửa trực tiếp dữ liệu lỗi mà tái tạo lại từ `data/raw/crossref_records.json`, sau đó chạy lại cleaning, quality, embedding và evaluation. Kết quả repaired phục hồi toàn bộ metric về mức baseline. Giới hạn đáng chú ý nhất là quota Gemini free tier, nên một số lần judge phải dùng exact-match hoặc heuristic fallback thay vì gọi LLM.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> fallback snapshot: data/raw/crossref_response.json
    -> data/raw/crossref_records.json
    -> cleaning + data modeling
    -> data/clean/papers_clean.csv|json
    -> Quality Gate GX 1.x + Freshness SLA
    -> MiniLM embedding + ChromaDB papers-baseline
    -> data/eval/test_set.json
    -> baseline evaluation + phase1_report.md
    -> corruption (6 kịch bản)
    -> quality/freshness trên corrupted data
    -> ChromaDB papers-corrupted + corrupted_metrics.json
    -> repair từ raw records
    -> ChromaDB papers-repaired + repaired_metrics.json
    -> corruption_report.md
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref REST API / snapshot | Fetch, retry tối đa 3 lần, exponential backoff, fallback snapshot, parse DOI/title/abstract/authors/subjects/date | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Nguyễn Bá Chính |
| Cleaning | `list[PaperRecord]`, `run_date` | Normalize text, parse date, tính `age_days`, dedup `paper_id`, tạo `text_for_embedding` | `data/clean/papers_clean.csv`, `papers_clean.json` | Nguyễn Bá Chính |
| Embedding/index | Clean dataframe | MiniLM embedding, normalized vectors, ChromaDB cosine, collection riêng cho từng trạng thái | `data/chroma/`, `data/embeddings/*.json` | Trần Anh Vũ |
| Evaluation | Dataframe + vector index | Bộ test 10 câu; Hit Rate, Token F1, Judge Accuracy, Judge Score | `data/eval/test_set.json`, `data/results/*_metrics.json` | Trần Anh Vũ |
| Observability | Baseline/corrupted/repaired dataframe | GX 1.x expectations + Freshness SLA | `data/quality/*.json` | Nguyễn Bá Chính |
| Corruption/repair | Clean dataframe / raw records | 6 corruption; rebuild từ raw; kiểm tra idempotency | `corruption_log.json`, corrupted/repaired datasets | Nguyễn Bá Chính + Trần Anh Vũ |
| Orchestration | Settings + toàn bộ module | Điều phối Phase 1 và corruption flow | `phase1_report.md`, `corruption_report.md` | Trần Anh Vũ |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-3.7-flash` trong lần chạy báo cáo |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; stale nếu `age_days > 180`; dataset fail freshness nếu stale ratio > 25% |
| Random seed | Không dùng; test set và corruption được thiết kế deterministic |

Không commit `.env`, API key hoặc secret vào repository.

### Lệnh cài đặt

```bash
uv sync
```

Hoặc:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Hoặc khi môi trường đã được kích hoạt:

```bash
python script/run_phase1.py
```

Corruption + Repair:

```bash
uv run python script/run_corruption_flow.py
```

Hoặc:

```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công, exit code 0 | 2026-09-25 khoảng 16:04 GMT+7 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công, exit code 0 | 2026-09-25 khoảng 16:07 GMT+7 | `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json`, `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `https://api.crossref.org/works`; pipeline có fallback sang `data/raw/crossref_response.json` |
| Query/filter | `query="agentic retrieval augmented generation large language model"`; `from-pub-date:<run_date-180d>,has-abstract:true`; `rows=24` |
| Thời điểm chạy | 2026-09-25 |
| Số record nhận được | 24 items → 24 `PaperRecord` |
| Retry/backoff | Tối đa 3 lần; với 429/503 hoặc `RequestException` dùng `2^attempt` giây; nếu thất bại thì fallback snapshot |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | `str` (DOI) | Có | ID tài liệu | Bỏ record nếu thiếu |
| `title` | `str` | Có | Tiêu đề đã normalize | Bỏ record nếu thiếu |
| `summary` | `str` | Có theo quality contract | Abstract đã bỏ JATS/HTML | GX báo FAIL nếu dưới 30 ký tự |
| `authors` | `list[str]` | Không | Tác giả | Cho phép list rỗng |
| `authors_joined` | `str` | Không | Chuỗi tác giả dùng downstream | Chuỗi rỗng nếu thiếu |
| `categories` | `list[str]` | Không | Subject/category | Cho phép list rỗng |
| `categories_joined` | `str` | Không | Chuỗi category dùng downstream | Chuỗi rỗng nếu thiếu |
| `published` | `YYYY-MM-DD` | Có | Ngày xuất bản | Bỏ record nếu không parse được |
| `age_days` | `int` | Có | Tuổi dữ liệu so với `run_date` | Tính lại khi chạy |
| `summary_chars` | `int` | Có | Số ký tự summary | Tính sau cleaning/corruption |
| `text_for_embedding` | `str` | Có | Văn bản đưa vào embedding | GX yêu cầu không null |

### Quy tắc cleaning

| Quy tắc | Quality dimension | Số record bị tác động | Cách xác minh |
| --- | --- | ---: | --- |
| Loại record thiếu `paper_id` hoặc title | Completeness | 0 | 24 raw → 24 clean |
| Loại record có `published` không parse được | Validity | 0 | 24 raw → 24 clean |
| Dedup theo `paper_id`, giữ bản cuối | Uniqueness | 0 | GX uniqueness PASS |
| Bỏ JATS/HTML và normalize whitespace | Consistency/Validity | Áp dụng toàn bộ record | Kiểm tra `papers_clean.json` |

`text_for_embedding` được tạo từ đúng 5 phần:

```text
Title: ...
Authors: ...
Published: ...
Categories: ...
Summary: ...
```

Document ID nghiệp vụ là DOI (`paper_id`). `age_days` được tính bằng số ngày giữa `run_date` UTC và `published`, chặn dưới ở 0.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| `question_type` | `summary` (3), `authors` (3), `date` (2), `categories` (2) |
| Ground-truth document ID | DOI trong `ground_truth_doc_ids` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection | ChromaDB persistent; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | Gemini; report chạy với `gemini-3.7-flash` |
| Test set dùng chung | `data/eval/test_set.json` |

Cùng một test set được giữ nguyên cho baseline, corrupted và repaired. Điều này giúp thay đổi metric phản ánh thay đổi của dữ liệu/index thay vì thay đổi câu hỏi. Nếu tạo lại test set trên corrupted data, các tài liệu bị drop hoặc title bị cắt có thể biến mất khỏi benchmark và che giấu tác động thật của corruption.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | 24 records |
| Cleaned dataset | `data/clean/` | Có | CSV + JSON, 24 dòng |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/` | Có | 24 vectors baseline |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | 10 samples |
| Quality/freshness | `data/quality/` | Có | baseline/freshness reports |
| Baseline report | `data/reports/phase1_report.md` | Có | Báo cáo Phase 1 |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 10/10 câu có tài liệu đích trong top-4 |
| `mean_token_f1` | 1.0 | Câu trả lời baseline khớp ground truth |
| `judge_accuracy` | 1.0 | 10/10 đúng |
| `mean_judge_score` | 5 | Điểm trung bình tối đa |
| Ragas | N/A | Không bật `RUN_RAGAS=1` trong lần chạy |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `ExpectTableRowCountToBeBetween` | Completeness/Volume | 5–5000 rows | PASS, 24 rows | `baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull(paper_id)` | Completeness | 0 null | PASS | `baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull(title)` | Completeness | 0 null | PASS | `baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull(text_for_embedding)` | Completeness | 0 null | PASS | `baseline_quality_report.json` |
| `ExpectColumnValuesToBeUnique(paper_id)` | Uniqueness | Không trùng | PASS | `baseline_quality_report.json` |
| `ExpectColumnValueLengthsToBeBetween(summary)` | Validity | `min_value=30` | PASS | `baseline_quality_report.json` |

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | Clean dataframe thông qua `age_days` |
| Timestamp mới nhất | `2026-07-22` |
| Timestamp cũ nhất | `2026-03-28` |
| Ngưỡng freshness | `age_days > 180` là stale |
| Trạng thái baseline | Fresh |
| Lý do | 1/24 dòng stale = 4.17%, thấp hơn ngưỡng 25% |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | ---: | --- | --- | --- |
| `drop_latest_records` | Bỏ ceil(20%) bài mới nhất | 5 | Volume/freshness xấu đi | 3/10 câu mất ground-truth doc; Hit Rate giảm 1.0 → 0.7 | Rebuild từ raw |
| `blank_summary` | Gán `summary=""` | 2 | Summary length FAIL | GX FAIL; ảnh hưởng câu hỏi summary | Rebuild từ raw |
| `inject_noise` | Thêm chuỗi noise vào summary | 2 | Không có rule trực tiếp bắt noise | Tác động metric nhỏ/không rõ ở bộ test hiện tại | Rebuild từ raw |
| `truncate_title` | Cắt title còn 7 ký tự | 2 | Không có rule title length | Có thể làm sai lookup/retrieval theo title | Rebuild từ raw |
| `stale_date` | Lùi `published` 365 ngày và tăng `age_days` | 7 | Freshness FAIL | 7/21 stale = 33.33%, vượt 25% | Rebuild từ raw |
| `duplicate_rows` | Nhân bản 2 dòng | 2 | Uniqueness FAIL | GX uniqueness FAIL | Rebuild từ raw |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Log chứa đủ 6 loại corruption, số lượng record và danh sách `paper_ids` bị tác động.

Repair đọc lại `data/raw/crossref_records.json`, chạy lại `build_clean_dataframe`, Quality Gate, embedding, index và evaluation. Vì nguồn repair là raw snapshot thay vì corrupted dataframe, lỗi không bị che tạm thời mà được loại bỏ bằng cách tái tạo dữ liệu chuẩn. Repaired data được kiểm tra lại trước khi index.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | −0.30 (−30%) | 100% | Corruption làm mất 3 ground-truth docs |
| `mean_token_f1` | 1.0 | 0.772 | 1.0 | −0.228 (−22.8%) | 100% | Giảm rõ nhất ở `date` và `summary` |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | −0.20 | 100% | Repaired quay về baseline |
| `mean_judge_score` | 5 | 4 | 5 | −1 | 100% | Repaired quay về tối đa |
| Quality checks | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Unique + summary length bị fail | Phục hồi | Quality Gate bắt được corruption |
| Freshness status | Fresh, 1/24 stale | Stale, 7/21 stale | Fresh, 1/24 stale | 4.17% → 33.33% | Phục hồi | Freshness trở lại baseline |

### Kết luận nhân quả

1. `drop_latest_records` làm mất 5 bài mới nhất, trong đó có 3 tài liệu nằm trong ground truth của test set. Hậu quả là Retrieval Hit Rate giảm từ `1.0` xuống `0.7`; đồng thời `stale_date` làm stale ratio tăng lên `33.33%`, khiến Freshness SLA chuyển sang FAIL.

2. `blank_summary` và `duplicate_rows` làm Great Expectations phát hiện lỗi về độ dài summary và uniqueness. Song song đó, Token F1 giảm từ `1.0` xuống `0.772`, cho thấy lỗi dữ liệu đã lan tới tầng trả lời.

3. Repair từ raw records làm Quality Gate trở lại PASS, Freshness trở lại Fresh và toàn bộ bốn metric chính trở về đúng baseline: `1.0 / 1.0 / 1.0 / 5`.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi ghép module ingestion/quality, pipeline từng gặp `NameError` với `normalize_whitespace`, `gx` và `write_json`.

- **Nguyên nhân:** Các module đã gọi helper/library nhưng thiếu import tương ứng.

- **Cách xử lý:** Bổ sung:
  - `from core.utils import normalize_whitespace`
  - `import great_expectations as gx`
  - `from core.utils import write_json`

- **Cách xác minh:** Clean dataframe có 24 rows; baseline Quality trả về `True`; corrupted Quality trả về `False`; hai pipeline Phase 1 và corruption flow chạy thành công.

Một vấn đề vận hành khác là quota Gemini. Một số request có thể gặp lỗi 429/503 hoặc giới hạn theo ngày. Pipeline giảm phụ thuộc vào LLM judge bằng cách dùng exact match khi câu trả lời khớp hoàn toàn và sử dụng heuristic fallback khi cần; số lần fallback được ghi lại trong metrics.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Chưa có expectation riêng cho title quá ngắn và noise trong summary | `truncate_title` và `inject_noise` có thể lọt qua Quality Gate | Thêm rule độ dài title và regex phát hiện noise; chạy lại corrupted report để xác nhận thêm FAIL |
| Hit Rate chỉ kiểm tra ground-truth doc có trong top-k | Có trường hợp câu trả lời đúng từ tài liệu gần giống dù nguồn không đúng | Thêm `top1_doc_match`, MRR hoặc nDCG |
| Quota Gemini free tier | Judge/agent có thể phải fallback hoặc gặp 429/503 | Dùng quota ổn định hơn và kiểm tra `judge_fallback_count = 0` |
| Nhóm chỉ có 2 thành viên | Review chéo hạn chế | Thêm automated pytest/CI cho ingestion, cleaning, quality và evaluation |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report hoặc artifacts đã kiểm tra.
