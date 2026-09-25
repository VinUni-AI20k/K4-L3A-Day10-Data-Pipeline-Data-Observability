# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin        | Nội dung |
| ---------------- | -------- |
| Khóa/Lớp         | K4 — K4-L3-DAY10 |
| Tên nhóm         | SVSoppi |
| Repository       | https://github.com/hoangtrunghieu0025-lab/K4-L3-DAY10-SVSoppi-DataPipeline |
| Ngày hoàn thành  | 2026-09-25 |

### Thành viên và phân công

> ⚠️ Cột Họ tên/MSSV cần từng thành viên tự điền. GitHub account được lấy từ lịch sử commit thực tế.

| STT | Họ và tên | MSSV | GitHub | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- | --- |
| 1 | [Họ tên] | [MSSV] | `hoangtrunghieu0025-lab` | Trưởng nhóm — Pipeline integration & reporting | `pipelines/phase1.py`, `pipelines/corruption_flow.py`, `pipelines/common.py`, `observability/reporting.py`; tích hợp và chạy lại toàn bộ flow |
| 2 | [Họ tên] | [MSSV] | `glacerjust` | Source & cleaning owner | `ingestion/crossref.py`, `ingestion/cleaning.py`; `data/raw/`, `data/clean/` |
| 3 | [Họ tên] | [MSSV] | `Tai Nguyen Van` | Corruption & vector store owner | `ingestion/corruption.py`, `script/smoke_test_chroma.py`; `corruption_log.json` |
| 4 | [Họ tên] | [MSSV] | `nguyenviethoanghai` | Observability & evaluation-set owner | `observability/quality.py` (GX 1.x + freshness), `evaluation/testset.py`; `data/quality/`, `data/eval/` |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành đủ 7 tầng của pipeline: ingestion từ Crossref (có fallback snapshot offline), cleaning, quality gate bằng Great Expectations 1.x kèm freshness SLA, embedding MiniLM + ChromaDB, đánh giá trên test set 10 câu, tiêm 6 loại lỗi và repair idempotent. Cả hai lệnh `run_phase1.py` và `run_corruption_flow.py` chạy end-to-end với exit code 0 và sinh đủ artifact theo `docs/SUBMISSION.md`.

Trên dữ liệu sạch, baseline đạt hit rate 1.00 và Token F1 1.00. Sau khi tiêm lỗi, hit rate giảm còn 0.60 và Token F1 còn 0.50. Quality gate phát hiện 3 expectation bị vi phạm (trùng `paper_id`, `title` quá ngắn, `summary` quá ngắn), còn freshness SLA báo stale vì 40.9% số dòng quá 180 ngày (ngưỡng 25%). Lỗi gây thiệt hại rõ nhất là **drop_latest_records**: 4/10 câu hỏi mất tài liệu đúng. Nguy hiểm nhất là **stale_date**: agent vẫn truy xuất đúng tài liệu nhưng trả lời sai ngày một cách tự tin (silent failure). Repair dựng lại dữ liệu từ `data/raw/crossref_records.json`, cho kết quả trùng khớp 24/24 dòng với baseline, và đưa mọi chỉ số về đúng mức baseline.

Giới hạn quan trọng nhất là judge chạy bằng `LLM_PROVIDER=mock`, nên đây là **heuristic judge dựa trên Token F1**, không phải LLM judge thật (xem mục 12).

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API ──(lỗi/429)──> snapshot data/raw/crossref_response.json
    -> data/raw/crossref_records.json               (raw preservation / lineage)
    -> cleaning: age_days, *_joined, text_for_embedding, dedup
    -> data/clean/papers_clean.{csv,json}
    -> QUALITY GATE (GX 1.x + freshness SLA)        (fail => dừng, không index)
    -> MiniLM embedding -> Chroma "papers-baseline"
    -> evaluate trên data/eval/test_set.json         -> baseline_metrics.json, phase1_report.md
    -> corrupt (6 loại, seed=42)                    -> corruption_log.json
    -> quality gate + freshness => DATA INCIDENT
    -> index "papers-corrupted" (mô phỏng: nếu không có gate) -> corrupted_metrics.json
    -> REPAIR: build lại từ raw records -> kiểm tra trùng khớp baseline -> quality gate
    -> index "papers-repaired" -> repaired_metrics.json
    -> corruption_report.md (Baseline vs Corrupted vs Repaired)
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` (query + filter) | Gọi API timeout 10s; lỗi mạng/HTTP thì fallback snapshot; bóc tách JATS; fallback categories | `data/raw/crossref_response.json`, `crossref_records.json` | glacerjust |
| Cleaning | `PaperRecord` list, `run_date` | `age_days`, `authors_joined`/`categories_joined`, `text_for_embedding` 5 phần, dedup `paper_id`, loại title/summary rỗng | `data/clean/papers_clean.{csv,json}` | glacerjust |
| Embedding/index | Clean dataframe | `all-MiniLM-L6-v2`, Chroma cosine, 3 collection tách biệt | `data/chroma/` | (có sẵn trong starter); smoke test: Tai Nguyen Van |
| Evaluation | Clean dataframe | 10 câu cố định, 4 `question_type`, ground truth lấy từ dữ liệu sạch | `data/eval/test_set.json`, `data/results/*_metrics.json` | nguyenviethoanghai |
| Observability | Dataframe bất kỳ trạng thái | 8 expectation GX 1.x (ephemeral context) + freshness SLA | `data/quality/*.json`, `data/quality/gx/*` | nguyenviethoanghai |
| Corruption/repair | Clean dataframe / raw records | 6 loại lỗi có seed; repair = rebuild từ raw | `corruption_log.json`, `papers_clean_{corrupted,repaired}.*` | Tai Nguyen Van (corruption), hoangtrunghieu0025-lab (repair flow) |
| Orchestration & reporting | Tất cả artifact trên | Thứ tự chạy, gate chặn index, kiểm tra idempotent, báo cáo Markdown | `data/reports/*.md` | hoangtrunghieu0025-lab |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `mock` (heuristic judge — xem mục 12) |
| `LLM_MODEL` | `gemini-2.5-flash` (không được gọi khi `mock`) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | `age_days > 180`, stale khi tỷ lệ > 25% |
| Random seed | 42 (`corrupt_clean_dataframe`) |

### Lệnh cài đặt

```bash
python -m pip install uv
python -m uv sync
```

### Lệnh chạy

```bash
.venv\Scripts\python script/run_phase1.py
.venv\Scripts\python script/run_corruption_flow.py
```

`REFRESH_SOURCE=1` gọi lại Crossref API; `REFRESH_TEST_SET=1` sinh lại test set. Mặc định cả hai được tái sử dụng để kết quả tái lập được.

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công (exit 0) | 2026-09-25 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công (exit 0) | 2026-09-25 | `data/results/{corrupted,repaired}_metrics.json`, `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `https://api.crossref.org/works` |
| Query/filter | `agentic retrieval augmented generation large language model`; `from-pub-date:<hôm nay − 180 ngày>,has-abstract:true`; `rows=24` |
| Khoảng ngày xuất bản | 2026-04-01 → 2026-09-15 |
| Số record nhận được | 24 (cả 24 đều có abstract dạng JATS XML) |
| Cơ chế retry/backoff | Không retry. Gọi 1 lần với timeout 10s; nếu lỗi mạng/HTTP (kể cả 429) thì fallback sang snapshot `crossref_response.json` |

### Clean schema (hợp đồng dữ liệu giữa các module)

| Trường | Kiểu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | str (DOI) | Có | Khóa định danh document | Item không có DOI bị bỏ khi parse; trùng thì dedup (GX unique) |
| `title` | str | Có | Tiêu đề | Rỗng thì bị loại; GX yêu cầu độ dài ≥ 20 |
| `summary` | str | Có | Abstract đã bỏ thẻ JATS | Rỗng thì bị loại; GX yêu cầu độ dài ≥ 30 |
| `authors_joined` | str | Có | Tác giả, cách nhau bởi dấu phẩy | Chuỗi rỗng |
| `categories_joined` | str | Có | Subject, fallback `[container-title, type]` | Chuỗi rỗng nếu thiếu cả hai |
| `published` | str ISO | Có | Ngày xuất bản | Thiếu ngày/tháng thì lấy ngày 01; thiếu hẳn thì `1970-01-01` |
| `age_days` | int | Có | `(run_date − published).days` | Dùng cho freshness SLA |
| `abs_url`, `pdf_url` | str | Không | Link bài báo | Chuỗi rỗng |
| `text_for_embedding` | str | Có | Văn bản đưa vào embedding | GX not-null |

### Quy tắc cleaning

| Quy tắc | Quality dimension | Số record bị tác động | Cách xác minh |
| --- | --- | --: | --- |
| Bỏ thẻ JATS/HTML trong abstract, chuẩn hóa khoảng trắng | Validity | 24 | `data/raw/crossref_records.json` không còn `<jats:` |
| Fallback categories = `[container-title, type]` khi thiếu `subject` | Completeness | 24 (9 bài chỉ có `type`) | `categories` không rỗng ở cả 24 record |
| Dedup theo `paper_id` | Uniqueness | 0 (24 → 24) | GX `expect_column_values_to_be_unique` PASS |
| Loại record có title/summary rỗng | Completeness | 0 | Summary ngắn nhất 834 ký tự, title ngắn nhất 92 ký tự |

`text_for_embedding` gồm 5 dòng cố định: `Title / Authors / Published (YYYY-MM-DD) / Categories / Summary`. Document ID trong Chroma có dạng `<paper_id>::<index>`, nên các dòng bị nhân bản vẫn được index riêng (để đo tác động của duplicate), còn `paper_id` là khóa nghiệp vụ. `age_days` được tính lại theo `run_date` mỗi lần chạy, nên đây là cột duy nhất được bỏ qua khi kiểm tra idempotent.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| Các `question_type` | `summary` ×3, `authors` ×3, `date` ×2, `categories` ×2 |
| Ground-truth document ID | `paper_id` của bài báo được chọn; bài được chọn trải đều theo `paper_id` đã sắp xếp, loại tiêu đề chứa dấu `'` |
| Embedding model | `all-MiniLM-L6-v2` |
| Vector store/collection | ChromaDB (cosine): `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | `mock`: answer trích xuất từ metadata; judge là heuristic dựa trên Token F1 |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha256 bắt đầu bằng `0969e2951266`) |

Test set được sinh **một lần từ dữ liệu sạch** và tái sử dụng cho cả ba trạng thái. Nếu sinh lại từ dữ liệu lỗi, ground truth sẽ mang chính lỗi đó (ví dụ ngày bị lùi), và chỉ số sẽ đo sai: dữ liệu hỏng vẫn được chấm "đúng".

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | 24 items |
| Cleaned dataset | `data/clean/` | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/chroma/` | Có | Manifest `data/embeddings/` không commit vì chứa đường dẫn tuyệt đối của máy local; pipeline tự sinh lại |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | |
| Quality/freshness | `data/quality/` | Có | + raw GX validation trong `data/quality/gx/` |
| Baseline report | `data/reports/phase1_report.md` | Có | |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | --: | --- |
| `retrieval_hit_rate` | 1.00 | 10/10 câu có tài liệu đúng trong top-4 (câu hỏi chứa tiêu đề chính xác nên bước exact-title lookup luôn khớp) |
| `mean_token_f1` | 1.00 | Answer trích xuất từ metadata trùng khớp ground truth |
| `judge_accuracy` | 1.00 | Heuristic judge (`mock`): đúng khi F1 ≥ 0.5 |
| `mean_judge_score` | 5.00 | Heuristic: 5 nếu F1 ≥ 0.95 |
| Ragas | N/A | Bỏ qua (cần `RUN_RAGAS=1` và LLM thật) |

## 8. Data quality và freshness

### Quality checks (GX 1.x — `gx.get_context(mode="ephemeral")` → `data_sources.add_pandas`)

| Check | Quality dimension | Ngưỡng/kỳ vọng | Baseline | Corrupted |
| --- | --- | --- | --- | --- |
| `ExpectTableRowCountToBeBetween` | Completeness | 5–5000 dòng | PASS (24) | PASS (22) |
| `ExpectColumnValuesToNotBeNull` × 4 | Completeness | `paper_id`, `title`, `summary`, `text_for_embedding` | PASS | PASS (summary bị xóa là `""`, không phải null) |
| `ExpectColumnValuesToBeUnique` | Uniqueness | `paper_id` | PASS | **FAIL** — 6 giá trị vi phạm |
| `ExpectColumnValueLengthsToBeBetween` | Validity | `summary` ≥ 30 | PASS | **FAIL** — 3 dòng |
| `ExpectColumnValueLengthsToBeBetween` | Validity | `title` ≥ 20 | PASS | **FAIL** — 4 dòng |

Bằng chứng: `data/quality/baseline_quality_report.json`, `data/quality/corrupted_quality_report.json`.

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | Clean dataframe trước khi index (`data/quality/freshness_report.json`) |
| Timestamp mới nhất | 2026-09-15 (cũ nhất 2026-04-01) |
| Ngưỡng freshness | `age_days > 180`; stale khi tỷ lệ > 25% |
| Trạng thái baseline | **Fresh**: 0/24 dòng quá hạn, `max_age_days = 177` |
| Trạng thái corrupted | **Stale**: 9/22 dòng quá hạn (40.9%) |

Lưu ý: bài cũ nhất đang có 177 ngày tuổi, nên chỉ vài ngày nữa sẽ vượt ngưỡng 180. Freshness SLA thay đổi theo ngày chạy, và đây chính là tín hiệu thật cần refresh nguồn định kỳ.

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | --: | --- | --- | --- |
| `drop_latest_records` | Bỏ 20% bài mới nhất | 5 | Row count / freshness | 4/10 câu mất tài liệu đúng (eval_004, 005, 007, 010); GX **không bắt** được vì 22 dòng vẫn nằm trong 5–5000 | Rebuild từ raw |
| `blank_summary` | `summary = ""` | 3 | Summary length | GX FAIL `summary` | Rebuild từ raw |
| `inject_noise` | Chèn token rác vào summary | 3 | — | eval_009 trả lời `?????` (F1 0); GX **không bắt** được | Rebuild từ raw |
| `truncate_title` | Cắt title còn 7 ký tự | 3 | Title length | GX FAIL `title` (4 dòng, tính cả bản duplicate) | Rebuild từ raw |
| `stale_date` | Lùi `published` 365 ngày | 8 | Freshness | Freshness STALE; eval_003 truy xuất đúng nhưng trả lời sai năm | Rebuild từ raw |
| `duplicate_rows` | Nhân bản dòng | 3 | Unique `paper_id` | GX FAIL unique (6 giá trị) | Rebuild từ raw |

Corruption log: `data/results/corruption_log.json`. Log có đủ 6 loại, ghi `affected_paper_ids`, giá trị trước/sau (title, published), `seed = 42`, và số dòng 24 → 22 (19 `paper_id` duy nhất).

**Repair không vá dữ liệu lỗi.** Pipeline bỏ hẳn dataframe hỏng và chạy lại `build_clean_dataframe(load_raw_records(raw))` từ bản raw đã bảo toàn. Sau đó flow tự kiểm chứng rằng kết quả trùng khớp 24/24 dòng với baseline (bỏ qua `age_days`), rồi bắt dữ liệu phải qua lại quality gate trước khi index. Vì chỉ phụ thuộc vào raw, repair chạy lại bao nhiêu lần cũng cho cùng kết quả (idempotent).

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | --: | --: | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.00 | 0.60 | 1.00 | −0.40 | 100% | Cả 4 câu miss đều trỏ tới bài bị drop |
| `mean_token_f1` | 1.00 | 0.50 | 1.00 | −0.50 | 100% | Giảm nhiều hơn hit rate vì có lỗi khiến trả lời sai dù truy xuất đúng |
| `judge_accuracy` | 1.00 | 0.50 | 1.00 | −0.50 | 100% | Heuristic judge, bám theo F1 |
| `mean_judge_score` | 5.00 | 3.00 | 5.00 | −2.00 | 100% | Heuristic judge |
| Quality checks (pass/8) | 8/8 PASS | 5/8 → gate FAIL | 8/8 PASS | −3 | 100% | Fail: unique, title, summary |
| Freshness status | Fresh (0%) | Stale (40.9%) | Fresh (0%) | +40.9 điểm % | 100% | |

Các kết luận nhân quả (bằng chứng: `corruption_log.json` ↔ `corrupted_answers.json`):

1. **drop_latest_records → không có tín hiệu GX → hit rate −0.40.** Cả 4 câu truy xuất sai (eval_004, 005, 007, 010) đều có tài liệu đích nằm trong danh sách bị drop. Row count giảm 24 → 22 nhưng vẫn trong ngưỡng 5–5000, nên đây là lỗi mà **gate hiện tại bỏ lọt**.
2. **stale_date → freshness STALE → answer sai dù retrieval đúng.** eval_003 có `retrieval_hit = true` nhưng trả lời `2025-08-01` trong khi ground truth là 2026-08-01. Đây là silent failure điển hình: agent tìm đúng tài liệu và trả lời tự tin, nhưng sai sự thật. Chỉ freshness SLA phát hiện được lỗi này.
3. **inject_noise → không có tín hiệu GX → answer rác.** eval_009 truy xuất đúng tài liệu nhưng câu đầu của summary đã thành token nhiễu `?????`. Summary vẫn dài hơn 30 ký tự nên GX không bắt được.
4. **Repair từ raw → gate PASS và freshness Fresh → cả 4 chỉ số về đúng baseline.** Dữ liệu repair trùng khớp 24/24 dòng với baseline, nên chỉ số trùng khớp tuyệt đối là kết quả được kỳ vọng.

Một điểm cần lưu ý khi đọc số: eval_004 (`categories`) retrieval **miss** nhưng Token F1 = 1.0. Bài đích không có `container-title`, nên categories chỉ là `posted-content`, và một bài khác cùng loại đã trả lời trùng chữ. Token F1 đã cho ra kết quả đúng giả (false positive) ở câu này.

## 11. Vấn đề tích hợp quan trọng

**Vấn đề 1 — Crossref không trả `subject`.**
- **Triệu chứng:** Token F1 baseline chỉ đạt 0.80 dù hit rate = 1.00.
- **Nguyên nhân:** Cả 24/24 item không có trường `subject`, nên `categories` rỗng. Hai câu `categories` (eval_004, eval_008) có ground truth rỗng, và `_token_f1` trả 0 khi một trong hai chuỗi rỗng.
- **Cách xử lý:** Trong `crossref.py`, fallback `categories = [container-title, type]`. `crossref_records.json` được sinh lại **offline** từ `crossref_response.json` đã lưu (chỉ `categories`/`primary_category` thay đổi); test set được sinh lại với `REFRESH_TEST_SET=1`.
- **Cách xác minh:** Không còn ground truth rỗng; baseline Token F1 = 1.00 (PR #4).

**Vấn đề 2 — Báo cáo tự mâu thuẫn do lệch contract.**
- **Triệu chứng:** `corruption_report.md` ghi "Quality Gate ❌ FAIL" nhưng lại liệt kê "không có expectation nào fail".
- **Nguyên nhân:** `reporting.py` đọc khóa `results`, trong khi `quality.py` trả về `checks` (tên cột nằm trong `kwargs.column`).
- **Cách xử lý:** Sửa `reporting.py` theo đúng output của `quality.py` (commit `3a93285`).
- **Cách xác minh:** Báo cáo hiện liệt kê đúng 3 expectation fail kèm số dòng vi phạm.

**Vấn đề 3 — Dữ liệu lỗi phải lan tới embedding.** Corruption tác động lên dataframe đã clean, nên `corruption.py` phải dựng lại `text_for_embedding` (và `age_days`). Nếu không, vector trong Chroma vẫn là bản sạch và chỉ số sẽ không đổi.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Judge chạy bằng `mock` (heuristic theo F1) | `judge_*` không độc lập với Token F1 | Chạy lại với `LLM_PROVIDER=gemini` và so sánh `judge_accuracy` với heuristic |
| Gate không bắt được `drop_latest_records` và `inject_noise` | 2/6 loại lỗi lọt qua GX | Thêm expectation so row count với lần chạy trước (±10%); kiểm tra tỷ lệ ký tự không phải chữ trong `summary` |
| Token F1 có false positive với câu trả lời ngắn và chung chung (eval_004) | Đánh giá quá cao answer sai | Đánh giá `categories` kèm `retrieval_hit`; hoặc tính F1 chỉ khi retrieval đúng |
| Ingestion không retry/backoff | 1 lần lỗi mạng là dùng snapshot cũ | Retry có exponential backoff cho 429/5xx; log rõ khi dùng snapshot |
| Nếu API lỗi và chưa có snapshot, `crossref_records.json` bị ghi đè thành rỗng | Mất lineage | Không ghi đè raw records khi parse ra 0 record |
| Categories fallback có độ đặc hiệu thấp (`journal-article`) | Câu hỏi `categories` dễ trúng ngẫu nhiên | Lấy thêm subject từ OpenAlex theo DOI |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [ ] Phân công khớp với module, artifact và kết quả thực tế (**từng thành viên điền Họ tên/MSSV**).
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
