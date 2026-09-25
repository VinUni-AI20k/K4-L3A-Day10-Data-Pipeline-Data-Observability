# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                               |
| --------------- | ------------------------------------------------------ |
| Họ và tên       | Nguyễn Bá Chính                                        |
| MSSV            | 2A202602654                                            |
| Khóa/Lớp        | K4                                                     |
| Tên nhóm        | 2ae                                                    |
| Vai trò chính   | Data Foundation & Observability                        |
| Repository      | https://github.com/vuxjqk/K4-L3-DAY10-2ae-DataPipeline |
| Ngày hoàn thành | 2026-09-25                                             |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable   | File/hàm phụ trách                                                                                       | Input nhận vào                                               | Output bàn giao                                                 | Trạng thái |
| -------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------- | ---------- |
| Crossref ingestion   | `src/ingestion/crossref.py` — `parse_crossref_payload()`, `fetch_source_records()`, `load_raw_records()` | Crossref API response hoặc `data/raw/crossref_response.json` | `list[PaperRecord]`, `data/raw/crossref_records.json`           | Hoàn thành |
| Data cleaning        | `src/ingestion/cleaning.py` — `build_clean_dataframe()`                                                  | `list[PaperRecord]`, `run_date`                              | Clean DataFrame với 24 records và các derived fields            | Hoàn thành |
| Data quality         | `src/observability/quality.py` — `run_data_quality_checks()`                                             | Clean/corrupted DataFrame, settings                          | `baseline_quality_report.json`, `corrupted_quality_report.json` | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report()`                                              | DataFrame có `published`, `age_days`                         | `data/quality/freshness_report.json`                            | Hoàn thành |
| Synthetic corruption | `src/ingestion/corruption.py` — `corrupt_clean_dataframe()`                                              | Clean DataFrame                                              | Corrupted DataFrame, `data/results/corruption_log.json`         | Hoàn thành |
| Team documentation   | `docs/TEAM.md`                                                                                           | Thông tin thành viên và phân công                            | TEAM.md đã điền đúng nhóm 2 người                               | Hoàn thành |

Tôi chịu trách nhiệm chính cho phần dữ liệu từ lúc nhận raw data cho đến khi dữ liệu được làm sạch, kiểm tra chất lượng và chủ động làm hỏng để kiểm thử Data Observability. Các output này được bàn giao cho phần RAG/Evaluation/Pipeline Integration của Trần Anh Vũ.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                     | Thành viên/module được hỗ trợ              | Kết quả                                                                                                                       |
| ----------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| Kiểm tra integration contract | RAG / Pipeline Integration của Trần Anh Vũ | Đảm bảo `text_for_embedding`, `paper_id`, `published`, `authors_joined`, `categories_joined` có schema phù hợp với downstream |
| Kiểm tra artifacts quality    | Pipeline tổng                              | Xác nhận clean data PASS nhưng corrupted data FAIL như kỳ vọng                                                                |
| Git integration               | Repo nhóm                                  | Merge 3 commits từ `feature/data-observability` vào `main` bằng merge commit `5bdba46`                                        |
| Tài liệu nhóm                 | `docs/TEAM.md`, `group_report.md`          | Cập nhật thông tin nhóm, vai trò và kết quả Data/Observability                                                                |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện          | File/hàm/artifact liên quan    | Kết quả bàn giao                                     | Cách xác minh                                      |
| ------------------------------ | ------------------------------ | ---------------------------------------------------- | -------------------------------------------------- |
| Parse Crossref data            | `src/ingestion/crossref.py`    | 24 `PaperRecord`                                     | Lệnh test in `Records: 24`                         |
| Làm sạch và chuẩn hóa          | `src/ingestion/cleaning.py`    | 24 clean rows, không duplicate/null `paper_id`       | `Rows = 24`, `Duplicates = 0`, `Null paper_id = 0` |
| Tạo dữ liệu cho embedding      | `text_for_embedding`           | Đủ 5 phần Title/Authors/Published/Categories/Summary | In trực tiếp record đầu tiên                       |
| Xây Quality Gate               | `src/observability/quality.py` | Baseline Quality `True`                              | `baseline_quality_report.json`                     |
| Theo dõi freshness             | `build_freshness_report()`     | Baseline Fresh `True`, stale ratio `4.17%`           | `freshness_report.json`                            |
| Inject lỗi dữ liệu             | `src/ingestion/corruption.py`  | 6 dạng corruption                                    | `corruption_log.json`                              |
| Kiểm chứng observability       | Quality + Freshness            | Corrupted Quality `False`, Fresh `False`             | Quality/Freshness test                             |
| Tích hợp code vào branch chính | Git history                    | Code Data/Observability có trên `main`               | Merge commit `5bdba46`                             |

Một output cụ thể do phần việc của tôi tạo ra là `data/results/corruption_log.json`. File này ghi lại đủ 6 loại lỗi dữ liệu được chủ động inject cùng số lượng và `paper_id` bị ảnh hưởng. Quality Gate sau đó phát hiện corrupted data là không hợp lệ, còn Freshness SLA phát hiện stale ratio tăng lên trên ngưỡng cho phép.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần tôi phụ trách giải quyết hai vấn đề chính.

Thứ nhất, dữ liệu lấy từ nguồn ngoài như Crossref không thể đưa trực tiếp vào RAG. Dữ liệu cần được parse về schema thống nhất, loại bỏ HTML/JATS tags, chuẩn hóa khoảng trắng, xử lý ngày tháng, loại duplicate và tạo `text_for_embedding`.

Thứ hai, một pipeline có thể chạy không lỗi nhưng dữ liệu bên trong đã sai. Đây là dạng **silent failure** nguy hiểm đối với RAG. Vì vậy cần Data Quality Gate và Freshness Monitoring để phát hiện dữ liệu thiếu, trùng, quá ngắn hoặc quá cũ trước khi downstream sử dụng.

### Cách triển khai

Ở bước ingestion, tôi đọc snapshot local nếu `REFRESH_SOURCE=False`. Nếu cần gọi Crossref API, module thực hiện tối đa 3 lần thử. Với lỗi 429 hoặc 503, hệ thống chờ theo exponential backoff `2^attempt`. Nếu API vẫn thất bại nhưng snapshot local tồn tại, pipeline fallback về snapshot thay vì dừng toàn bộ.

Crossref payload được chuyển thành `PaperRecord`. Abstract và title được loại bỏ HTML/JATS tags. Authors được ghép từ `given` và `family`. Ngày xuất bản ưu tiên `published`, sau đó `published-online`, rồi `published-print`.

Ở bước cleaning, tôi normalize title, summary, authors và categories. Record thiếu `paper_id`, title hoặc ngày xuất bản hợp lệ bị loại. Sau đó tính:

```text
age_days = run_date - published
```

và tạo các derived fields:

```text
authors_joined
categories_joined
summary_chars
text_for_embedding
```

`text_for_embedding` có cấu trúc:

```text
Title: ...
Authors: ...
Published: ...
Categories: ...
Summary: ...
```

DataFrame cuối cùng được deduplicate theo `paper_id`.

Ở Data Quality Gate, tôi sử dụng Great Expectations 1.x để kiểm tra:

* Row count từ 5 đến 5000.
* `paper_id` không null.
* `title` không null.
* `text_for_embedding` không null.
* `paper_id` unique.
* `summary` có ít nhất 30 ký tự.

Freshness được kiểm tra riêng. Một record được coi là stale nếu:

```text
age_days > 180
```

Dataset bị đánh dấu không fresh nếu hơn 25% records stale.

Cuối cùng, tôi tạo 6 corruption scenarios để kiểm thử observability:

1. Drop 20% records mới nhất.
2. Blank summary.
3. Inject noise vào summary.
4. Truncate title.
5. Làm ngày xuất bản cũ thêm 365 ngày.
6. Duplicate rows.

Sau corruption, các derived fields như `summary_chars` và `text_for_embedding` được build lại để lỗi thực sự truyền xuống downstream.

### Input, output và contract

| Thành phần              | Mô tả                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------- |
| Input                   | Crossref JSON hoặc `data/raw/crossref_response.json`; `Settings`; `run_date`                      |
| Output                  | `PaperRecord`, clean/corrupted DataFrame, quality/freshness reports, corruption log               |
| Module phụ thuộc        | `core.config`, `core.utils`, pandas, requests, Great Expectations                                 |
| Module sử dụng output   | `retrieval/index.py`, evaluation và pipeline orchestration                                        |
| Điều kiện lỗi cần xử lý | API 429/503, API unavailable, missing DOI/title/date, duplicate DOI, short summary, stale records |

### Cách xác minh

```bash
uv run --no-sync python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print('Records:', len(r)); print(r[0])"
```

```bash
uv run --no-sync python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print('Rows =',len(df)); print('Duplicates =',df['paper_id'].duplicated().sum()); print('Null paper_id =',df['paper_id'].isna().sum()); print('Short summaries =',(df['summary_chars']<30).sum())"
```

```bash
uv run --no-sync python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; from ingestion.corruption import corrupt_clean_dataframe; from observability.quality import run_data_quality_checks, build_freshness_report; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print('=== CLEAN ==='); print('Quality:',run_data_quality_checks(df,s,'baseline')['success']); print('Fresh:',build_freshness_report(df,s,s.paths.freshness_report)['is_fresh']); c=corrupt_clean_dataframe(df,s.paths.corruption_log); print('=== CORRUPTED ==='); print('Quality:',run_data_quality_checks(c,s,'corrupted')['success']); f=build_freshness_report(c,s,s.paths.freshness_report); print('Fresh:',f['is_fresh']); print('Stale ratio:',f['stale_ratio'])"
```

* **Kết quả mong đợi:** 24 clean rows; baseline Quality/Freshness PASS; corrupted Quality/Freshness FAIL.
* **Kết quả thực tế:** 24 records, 0 duplicate trong clean data, 0 null `paper_id`, 0 summary ngắn; baseline `Quality=True`, `Fresh=True`; corrupted `Quality=False`, `Fresh=False`, stale ratio `0.3333`.
* **Artifact/log:** `data/raw/crossref_records.json`, `data/quality/*.json`, `data/results/corruption_log.json`.

## 5. Một quyết định kỹ thuật quan trọng

* **Bối cảnh:** Khi cần phục hồi dữ liệu sau corruption, có thể sửa trực tiếp từng lỗi trong corrupted dataframe hoặc tái tạo dữ liệu từ raw snapshot.

* **Các phương án đã cân nhắc:**

  1. Tìm từng lỗi trong corrupted dataframe và sửa thủ công.
  2. Xem raw snapshot là source of truth và chạy lại transformation từ đầu.

* **Phương án đã chọn:** Giữ `data/raw/crossref_records.json` làm nguồn dữ liệu đáng tin cậy để downstream repair có thể tái tạo clean data bằng cùng cleaning logic.

* **Lý do:** Sửa trực tiếp từng lỗi trong corrupted dataframe dễ bỏ sót các lỗi mà Quality Gate chưa phát hiện, ví dụ noise hoặc title bị truncate. Rebuild từ raw giúp quá trình phục hồi deterministic, reproducible và gần với cách data pipeline thực tế xử lý lỗi.

* **Bằng chứng quyết định phù hợp:** Trong pipeline tổng, repaired metrics trở lại đúng baseline:

  * Retrieval Hit Rate: `1.0`
  * Mean Token F1: `1.0`
  * Judge Accuracy: `1.0`
  * Mean Judge Score: `5`

  Quality Gate cũng trở lại PASS và Freshness trở lại Fresh.

## 6. Một lỗi hoặc blocker đã xử lý

* **Triệu chứng/lỗi nguyên văn:**

```text
ModuleNotFoundError: No module named 'core'
```

* **Lệnh hoặc bước tái hiện:**

```bash
python -c "from core.config import load_settings"
```

* **Nguyên nhân gốc:** Project sử dụng cấu trúc `src/` package và dependencies được quản lý bởi môi trường `uv`. Lệnh `python` ban đầu sử dụng Python ngoài project environment nên không nhận package `core`.

* **Cách xử lý:** Chạy Python thông qua environment của project:

```bash
uv run --no-sync python -c "from core.config import load_settings; print('core OK')"
```

Sau đó sử dụng cùng cách chạy cho các test ingestion, cleaning và observability.

Ngoài ra, khi kiểm tra code tôi phát hiện `cleaning.py` thiếu import `normalize_whitespace`, còn `quality.py` thiếu `great_expectations as gx` và `write_json`. Các import này được bổ sung trước khi chạy Quality Gate.

* **Cách xác minh sau khi sửa:** Lệnh ingestion chạy thành công và trả về:

```text
Records: 24
```

Quality Gate tiếp tục chạy thành công với:

```text
Quality: True
```

trên baseline và:

```text
Quality: False
```

trên corrupted data.

* **Điều học được:** Khi gặp `ModuleNotFoundError`, cần kiểm tra đúng interpreter/environment trước khi cho rằng logic code bị sai. Đồng thời, một module có thể nhìn đúng về logic nhưng vẫn fail runtime chỉ vì thiếu dependency/import, vì vậy smoke test theo từng tầng là cần thiết.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**

   Crossref API hoặc snapshot local cung cấp JSON thô. `crossref.py` parse JSON thành `PaperRecord` và lưu raw records để đảm bảo data lineage. `cleaning.py` chuẩn hóa dữ liệu, tính `age_days`, deduplicate và tạo `text_for_embedding`. Sau khi Data Quality Gate xác nhận dữ liệu đủ tốt, MiniLM chuyển `text_for_embedding` thành embedding và ChromaDB lưu vector cùng metadata để phục vụ retrieval.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**

   Mỗi câu hỏi trong `test_set.json` có câu trả lời ground truth và `ground_truth_doc_ids`. Khi retrieval chạy top-k, hệ thống kiểm tra document đích có xuất hiện trong các kết quả được lấy ra hay không để tính Hit Rate. Phần answer quality so câu trả lời của agent với ground truth bằng Token F1 và judge score.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**

   Quality checks kiểm tra cấu trúc và tính hợp lệ của dữ liệu như null, duplicate, row count và độ dài summary. Freshness monitoring tập trung vào độ mới theo thời gian của dữ liệu. Một dataset có thể không duplicate và không null nhưng vẫn quá cũ, vì vậy hai loại giám sát giải quyết hai vấn đề khác nhau.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**

   Nếu thay test set giữa các trạng thái thì không thể xác định metric thay đổi do dữ liệu hay do câu hỏi thay đổi. Giữ nguyên test set tạo điều kiện so sánh công bằng và giúp đo đúng tác động của corruption cũng như mức phục hồi sau repair.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**

   Repair thành công khi dữ liệu repaired vượt lại Quality Gate, Freshness trở lại Fresh và các metric RAG phục hồi về baseline. Trong kết quả nhóm, repaired đạt Hit Rate `1.0`, Token F1 `1.0`, Judge Accuracy `1.0`, Mean Judge Score `5`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal        |          Baseline |         Corrupted |          Repaired | Nhận xét của cá nhân                                                          |
| -------------------- | ----------------: | ----------------: | ----------------: | ----------------------------------------------------------------------------- |
| `retrieval_hit_rate` |               1.0 |               0.7 |               1.0 | Corruption làm mất ground-truth documents khỏi index; repair phục hồi toàn bộ |
| `mean_token_f1`      |               1.0 |             0.772 |               1.0 | Answer quality giảm khi summary/title/date bị tác động                        |
| `judge_accuracy`     |               1.0 |               0.8 |               1.0 | Corrupted data làm một số answer bị đánh giá sai                              |
| `mean_judge_score`   |                 5 |                 4 |                 5 | Giảm một điểm trung bình rồi phục hồi hoàn toàn                               |
| Quality checks       |          PASS 6/6 |          FAIL 4/6 |          PASS 6/6 | Duplicate và summary length là hai signal bị fail                             |
| Freshness status     | Fresh, 1/24 stale | Stale, 7/21 stale | Fresh, 1/24 stale | Stale ratio tăng từ 4.17% lên 33.33% rồi trở lại baseline                     |

### Kết luận từ số liệu

1. `drop_latest_records` + `stale_date` → Freshness từ PASS chuyển sang FAIL với stale ratio `33.33%` → Retrieval Hit Rate giảm từ `1.0` xuống `0.7`.

2. Repair từ raw records → Quality Gate trở lại PASS và Freshness trở lại Fresh → Hit Rate, Token F1 và Judge Accuracy đều quay lại `1.0`, Mean Judge Score trở lại `5`.

**Corruption ảnh hưởng rõ nhất:** `drop_latest_records` ảnh hưởng rõ nhất tới retrieval vì nó xóa trực tiếp các tài liệu đích khỏi dataset. Trong 10 câu evaluation, 3 câu mất ground-truth document nên Hit Rate giảm đúng 30%.

**Kết quả khác với kỳ vọng ban đầu:** `inject_noise` không gây giảm metric rõ ràng như tôi ban đầu kỳ vọng. Nguyên nhân là noise được thêm ở cuối summary, trong khi answer extraction và semantic retrieval vẫn có thể dựa trên phần nội dung đúng ở phía trước. Ngoài ra Quality Gate hiện chưa có expectation riêng để phát hiện chuỗi noise. Điều này cho thấy một corruption tồn tại trong data không đồng nghĩa mọi metric đều chắc chắn giảm; khả năng phát hiện phụ thuộc vào rule và benchmark đang sử dụng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline không chỉ là lấy dữ liệu rồi đưa vào model.** Raw data cần được bảo toàn, transformation phải reproducible và mỗi stage cần có contract rõ ràng để downstream có thể tin tưởng dữ liệu nhận được.

2. **Data quality và observability là hai lớp bảo vệ quan trọng chống silent failure.** AI Agent có thể vẫn trả lời trôi chảy khi dữ liệu bị stale, duplicate hoặc mất record. Vì vậy không thể chỉ dựa vào việc chương trình "chạy không lỗi".

3. **Chất lượng dữ liệu ảnh hưởng trực tiếp đến RAG.** Khi corrupted data được index, Retrieval Hit Rate giảm từ `1.0` xuống `0.7` và Token F1 giảm xuống `0.772`. Khi dữ liệu được repair từ raw, các metric phục hồi về baseline mà không cần thay đổi model.

### Nếu có thêm thời gian

Tôi muốn mở rộng Data Quality Gate để phát hiện cả hai corruption hiện chưa được bắt trực tiếp:

```text
truncate_title
inject_noise
```

Cụ thể:

* Thêm expectation độ dài tối thiểu cho `title`.
* Thêm regex/rule phát hiện chuỗi noise bất thường trong `summary`.
* Thêm automated pytest kiểm tra clean data PASS và từng corruption phải tạo signal tương ứng.

Hiệu quả có thể đo bằng số corruption scenarios được Quality Gate phát hiện. Mục tiêu là tăng từ việc chỉ bắt rõ duplicate/short-summary/freshness lên phát hiện đầy đủ hơn cả 6 nhóm lỗi.

## 10. Cam kết của thành viên

* [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
* [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
* [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
* [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
* [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
* [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Bá Chính

**Ngày xác nhận:** 2026-09-25
