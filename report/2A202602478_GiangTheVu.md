# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Giang Thế Vũ |
| MSSV | `2A202602478` |
| Khóa/Lớp | K4 — L3A |
| Nhóm | `1Prompt4All` — K4-L3-DAY10 |
| Vai trò chính | Data Foundation & Recovery |
| Repository | [GitHub repository](https://github.com/D3vNguy3n/K4-L3A-Day10-Data-Pipeline-Data-Observability) |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

Phần của tôi là đưa payload Crossref thành raw record ổn định, chuẩn hóa thành clean dataframe, và giữ lineage để repair dựng lại dữ liệu sạch từ snapshot gốc. Tôi không nhận ownership cho orchestration hai entrypoint, ChromaDB, Great Expectations hay bộ metric.

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Parse Crossref và raw contract | `src/ingestion/crossref.py`: `PaperRecord`, `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Payload `message.items` hoặc snapshot `data/raw/crossref_response.json` | `data/raw/crossref_records.json`, 24 `PaperRecord` | Hoàn thành |
| Clean schema | `src/ingestion/cleaning.py`: `build_clean_dataframe` | Danh sách `PaperRecord` và `run_date` | Dataframe có `paper_id`, `age_days`, `text_for_embedding`; ghi ra `data/clean/papers_clean.csv` và `.json` | Hoàn thành |
| Repair từ raw lineage | `load_raw_records` + `build_clean_dataframe` được `corruption_flow` gọi lại | `data/raw/crossref_records.json`, không đọc dataframe đã corrupt | `data/clean/papers_clean_repaired.csv` và `.json` | Hoàn thành |

Contract bàn giao:

- Raw records đi tới Nguyễn Hoàng Lê Nguyên để phase 1 và corruption flow có nguồn parse offline.
- Clean dataframe đi tới Trần Đức Lộc (cột `text_for_embedding`, `paper_id`) và Đặng Hữu Cương (schema để viết expectation và test set).
- Repair đọc lại raw snapshot. Dataframe corrupted không được dùng làm nguồn sửa.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chốt raw/clean schema trước khi index | Pipeline Integrator, RAG, Observability | Cùng tên cột `paper_id`, `published`, `summary`, `text_for_embedding`; DOI lowercase là document id |
| Đối chiếu repair với baseline | `corruption_flow.py` | Trên các trường nội dung, `papers_clean.json` và `papers_clean_repaired.json` trùng nhau sau lần chạy 2026-09-25 |
| Giải thích vì sao row count không đủ để phát hiện corruption | Observability | Corrupted vẫn 24 dòng; lỗi nằm ở uniqueness và độ dài summary |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse payload, gỡ JATS, chuẩn hóa DOI/tác giả/ngày | `parse_crossref_payload` | 24 record, không còn thẻ `<jats:p>` trong summary | Parse lại `crossref_response.json`: 24/24 abstract gốc có JATS, 0 summary sau parse còn dấu `<` |
| Cleaning và dedupe | `build_clean_dataframe` | 24/24 dòng giữ lại, 24 DOI duy nhất, summary ngắn nhất 193 ký tự | Rebuild từ raw snapshot với `run_date` 2026-09-25 |
| Tính tuổi bản ghi | cột `age_days` | 65–181 ngày; đúng 1 dòng > 180 ngày | Khớp `freshness_report.json`: 1/24 stale, ratio 4.2% |
| Repair từ raw | `papers_clean_repaired.json` | Cùng `paper_id`, title, summary, ngày, tác giả, categories và `text_for_embedding` với baseline | So khớp JSON hai file clean |

Output cụ thể: `data/raw/crossref_records.json` là bản đã parse (24 DOI duy nhất), còn `data/raw/crossref_response.json` giữ nguyên payload để đối chiếu. Clean baseline và clean repaired đều 24 dòng, publication từ `2026-03-28` đến `2026-07-22`. Không có dòng nào bị loại trên snapshot nghiệm thu vì mọi record đều có DOI, title, abstract và ngày hợp lệ.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref không trả một schema phẳng. `title` là list, `author` tách `given`/`family`, abstract bọc JATS, ngày có thể nằm ở `published`, `published-online`, `published-print`, `issued` hoặc `created`, và `date-parts` có thể chỉ có năm. Nếu đẩy nguyên item sang embedding thì document id, text và freshness đều không ổn định. Repair cũng không có chỗ bám nếu chỉ sửa file đã bị làm bẩn.

### Cách triển khai

`parse_crossref_payload` đọc `message.items`. Mỗi item được bỏ qua khi thiếu DOI, title, abstract, khi DOI đã gặp, hoặc khi không parse được ngày xuất bản. DOI được lowercase và trim để làm `paper_id`. Thẻ HTML/JATS bị gỡ bằng regex rồi `html.unescape`, khoảng trắng được gộp. Tác giả ghép `given` + `family`. Subject được khử trùng lặp, giữ thứ tự. Ngày ưu tiên `date-parts` (tháng/ngày thiếu thì mặc định 1), fallback sang `date-time`. PDF lấy link có `content-type` chứa `pdf`, không có thì dùng URL DOI.

`fetch_source_records` mặc định đọc snapshot offline để lần chạy lab lặp lại được. Khi `REFRESH_SOURCE` bật, hàm gọi `https://api.crossref.org/works` với query, filter `has-abstract:true`, `rows=24`, tối đa 3 lần. Status `429` và `500/502/503/504` được coi là retryable, backoff `2^attempt` giây. Response lỗi hoặc rỗng không ghi đè snapshot; hàm quay lại file offline. Bản parse luôn được ghi vào `crossref_records.json`.

`build_clean_dataframe` chuẩn hóa lại text và list, parse ngày UTC, rồi loại dòng thiếu `paper_id`/`title`, summary ngắn hơn 30 ký tự, hoặc `published` không parse được. `age_days` là số ngày từ ngày xuất bản tới `run_date`. `text_for_embedding` ghép năm dòng: Title, Authors, Published, Categories, Summary. Dedupe theo `paper_id` (`keep="first"`), sort `published` giảm dần rồi `paper_id` tăng dần, `kind="stable"`, để cửa sổ “mới nhất” mà corruption và test set dùng không đổi giữa các lần chạy.

Repair không vá từng ô của dataframe corrupted. `corruption_flow` gọi `load_raw_records` trên `crossref_records.json` rồi `build_clean_dataframe` với `now_utc()`. Cùng hàm cleaning với baseline nên document id và nội dung text được tạo lại từ nguồn chưa bị sáu scenario đụng tới.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Payload Crossref hoặc `data/raw/crossref_response.json`; khi repair thì `data/raw/crossref_records.json` |
| Output | `PaperRecord` 13 trường; dataframe clean gồm `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `age_days`, `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`, `abs_url`, `pdf_url`, `comment` |
| Module phụ thuộc | `core.config.Settings` (query, filter, đường dẫn), `core.utils.normalize_whitespace` |
| Module sử dụng output | `pipelines/phase1.py` ghi clean và chỉ index sau quality gate; `pipelines/corruption_flow.py` đọc raw để repair; retrieval đọc `text_for_embedding`; observability đọc `paper_id`, `summary`, `age_days` |
| Điều kiện lỗi | Payload không có `message.items` dạng list; snapshot offline mất; không còn record dùng được; dòng raw không phải object khi `load_raw_records` |

### Cách xác minh

```bash
cd /Users/thevu/VinAI/K4-L3A-Day10-Data-Pipeline-Data-Observability
PYTHONPATH=src python3 - << 'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
from ingestion.crossref import parse_crossref_payload, load_raw_records
from ingestion.cleaning import build_clean_dataframe

root = Path("data")
payload = json.loads((root / "raw/crossref_response.json").read_text())
parsed = parse_crossref_payload(payload)
loaded = load_raw_records(root / "raw/crossref_records.json")
run = datetime(2026, 9, 25, 8, 19, 21, tzinfo=timezone.utc)
df = build_clean_dataframe(loaded, run)
print(len(parsed), len(loaded), df["paper_id"].nunique(), int((df["age_days"] > 180).sum()))
print(any("<" in record.summary for record in parsed))
PY
```

- **Kết quả mong đợi:** 24 record parse được, trùng id với snapshot, 24 DOI duy nhất sau clean, đúng 1 dòng stale, summary không còn markup.
- **Kết quả thực tế:** in ra `24 24 24 1` và `False`. Cả 24 abstract trong payload đều chứa `<jats:p>`.
- **Artifact:** `data/raw/crossref_records.json`, `data/clean/papers_clean.json`, `data/clean/papers_clean_repaired.json`, `data/quality/freshness_report.json`. Không có secret trong các file này.

Hai entrypoint `script/run_phase1.py` và `script/run_corruption_flow.py` do Pipeline Integrator chạy nghiệm thu ngày 2026-09-25 (xem `data/reports/phase1_report.md`, run time `2026-09-25T08:19:21Z`). Tôi kiểm tra lại phần data contract trên artifact đó, không chạy lại embedding trong lượt viết báo cáo này.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Sau corruption, file clean đã mất 5 DOI mới nhất, summary bị xóa, title bị cắt, ngày bị lùi 5 năm, text embedding bị thêm noise, rồi bị duplicate để đủ 24 dòng. Cần một cách đưa dữ liệu về trạng thái sạch.
- **Các phương án đã cân nhắc:** (1) Sửa ngược từng scenario trên `papers_clean_corrupted` — điền lại summary, gỡ noise, xóa dòng trùng. (2) Bỏ qua dataframe lỗi, đọc `crossref_records.json` và chạy lại đúng `build_clean_dataframe`.
- **Phương án đã chọn:** Phương án (2). Raw snapshot là nguồn repair. Corrupted artifact chỉ để đo hỏng, không phải nguồn sửa.
- **Lý do:** Sửa ngược dễ sót một scenario và biến repair thành bản vá thủ công. Chạy lại cleaning giữ cùng quy tắc DOI, độ dài summary, `age_days` và `text_for_embedding`, nên document id không đổi và lần repair sau không phụ thuộc lần corrupt trước. Đổi lại, repair tốn một lượt parse/clean và không “vá tại chỗ” nếu raw snapshot cũng hỏng.
- **Bằng chứng:** So các trường `paper_id`, `title`, `summary`, `published`, `authors`, `categories`, `text_for_embedding` giữa `papers_clean.json` và `papers_clean_repaired.json` thì trùng nhau. Quality repaired 6/6 expectation pass, stale 1/24 (4.2%), khớp baseline. `repaired_metrics.json` đưa hit rate và token F1 về `1.0`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Abstract trong `data/raw/crossref_response.json` có dạng `<jats:p>...</jats:p>`. Nếu gán thẳng vào `summary`, text embedding mang token markup và độ dài summary bị cộng thêm thẻ.
- **Bước tái hiện:** Đọc `message.items[].abstract` của snapshot. Cả 24 item đều chứa chuỗi `<jats`.
- **Nguyên nhân gốc:** Crossref trả abstract theo JATS, không phải plain text. `title` còn là list nên ép `str()` sẽ thành `['...']`.
- **Cách xử lý:** `parse_crossref_payload` gỡ tag bằng regex, unescape HTML entity, lấy phần tử đầu của list, rồi mới ghi `crossref_records.json`. Cleaning chuẩn hóa whitespace lần nữa trước khi ghép `text_for_embedding`.
- **Cách xác minh:** Parse lại payload: 24 record, không summary nào còn ký tự `<`, id trùng file raw đã lưu. Summary ngắn nhất sau clean là 193 ký tự, trên ngưỡng 30 của quality gate.
- **Điều học được:** Contract raw phải là plain text đã chuẩn hóa. Giữ payload gốc để audit, nhưng không đưa payload đó thẳng vào index.

## 7. Hiểu biết về luồng end-to-end

1. Crossref (live hoặc snapshot) được parse thành `PaperRecord` và lưu `crossref_records.json`. Cleaning tính `age_days`, khử DOI trùng, tạo `text_for_embedding`. Quality gate và freshness chạy trên dataframe đó. Khi pass, MiniLM embed text và Chroma lưu document với id là DOI. Test set 10 câu được gắn vào các DOI này.
2. `data/eval/test_set.json` cố định 10 câu loại `summary`, `authors`, `date`, `categories`. Mỗi câu có `ground_truth` và `ground_truth_doc_ids`. Hit rate kiểm tra retrieval có trả về đúng DOI đó không. Token F1 đo độ trùng token giữa câu trả lời và `ground_truth`. Judge chấm đúng/sai trên cùng cặp đó.
3. Quality checks nhìn cấu trúc: số dòng, null, DOI unique, summary dài tối thiểu 30 ký tự. Freshness nhìn thời gian: tỷ lệ dòng có `age_days > 180` không được quá 25%. Một bảng có thể đủ dòng và unique nhưng vẫn stale.
4. Baseline, corrupted và repaired phải dùng cùng `test_set.json`. Nếu mỗi trạng thái một bộ câu, chênh hit rate không còn chỉ ra corruption. Bộ câu này bám các DOI mới nhất, đúng nhóm bị `drop_latest_records` xóa.
5. Repair thành công khi clean repaired được dựng từ raw, không từ file corrupted; GX 6/6 pass; freshness về 1/24 stale; collection repaired có đủ 24 document; `retrieval_hit_rate` và `mean_token_f1` về `1.0` như baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.000 | 1.000 | Năm DOI mới nhất bị xóa khỏi clean set trước khi index, nên 10 câu không còn ground-truth document |
| `mean_token_f1` | 1.000 | 0.007 | 1.000 | Phần token còn sót rất nhỏ vì summary và title đã bị phá trên các dòng còn lại |
| `judge_accuracy` | 1.000 | 0.000 | 1.000 | Đi theo retrieval: không có đúng document thì câu trả lời không khớp đáp án |
| `mean_judge_score` | 5.000 | 1.000 | 5.000 | Corrupted ở sàn điểm của judge heuristic |
| Quality checks | PASSED (6/6) | FAILED (4/6) | PASSED (6/6) | Fail uniqueness (`unexpected_count` 10) và độ dài summary (10 dòng) |
| Freshness status | PASSED, 1/24 stale (4.2%) | FAILED, 24/24 stale (100%) | PASSED, 1/24 stale (4.2%) | `stale_date` lùi publication 5 năm; mốc mới nhất tụt từ 2026-07-22 xuống 2021-06-12 |

Số lấy từ `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json` và ba cặp quality/freshness report.

### Kết luận từ số liệu

1. Drop 5 DOI mới nhất, xóa summary 5 dòng, cắt title, nhồi noise vào `text_for_embedding`, lùi ngày 5 năm, rồi duplicate 5 dòng để trả row count về 24 → GX fail uniqueness và summary length, stale ratio từ 4.2% lên 100% → hit rate từ 1.0 xuống 0.0, token F1 xuống 0.007.
2. `load_raw_records` + `build_clean_dataframe` trên snapshot chưa corrupt → 24 DOI unique, summary dài trở lại, `age_days` về dải 65–181, freshness pass → hit rate, token F1 và judge về đúng baseline.

Corruption đụng chất lượng dữ liệu rõ nhất, trên chính contract tôi giữ, là cặp blank summary và duplicate. Row count vẫn là 24 nên expectation “số dòng từ 5 đến 5000” vẫn pass. Uniqueness báo 10/24 dòng (`partial_unexpected_index_list` gồm 0–4 và 19–23): 5 DOI bị nhân đôi. Summary rỗng cũng thành 10 dòng vì 5 dòng blank bị copy thêm một lần. Freshness thì `stale_date` quyết định: mọi dòng đều vượt 180 ngày.

Trên phía agent, drop 5 DOI mới nhất (`10.1145/3637528.3671812`, `3671808`, `3671804`, `3671807`, `3671802` trong `corruption_log.json`) mới là nhát làm hit rate về 0, vì test set bám các document đó. Noise và title cụt làm câu trả lời kém thêm, nhưng không cần chúng hit rate cũng đã mất ground-truth id.

Điểm khác kỳ vọng của tôi: nhìn số dòng không thấy hỏng. Tôi tưởng corruption sẽ làm `papers_clean_corrupted` ngắn đi sau khi drop 20%. Log cho thấy `original_rows` và `corrupted_rows` đều là 24, vì duplicate bù lại đúng 5 dòng đã xóa. Kiểm tra bằng cách đếm DOI unique: 19, không phải 24. Gate uniqueness bắt được việc row count bỏ sót.

`age_days` cũng không phải thuộc tính bất biến của bài báo. Nó phụ thuộc `run_date`. Hai file clean trùng cả `age_days` vì cùng được tạo trong ngày 2026-09-25. Chạy repair sang ngày khác sẽ đổi tuổi bản ghi dù title và summary không đổi; bài `2026-03-28` đã 181 ngày nên vẫn là dòng stale duy nhất chừng nào chưa có bài cũ hơn trong snapshot.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot và hàm cleaning thuần là chỗ repair bám vào. Sửa file đã corrupt không còn là cùng một biến đổi, nên không chứng minh được pipeline tự phục hồi.
2. Một quality gate chỉ đếm số dòng sẽ pass bộ dữ liệu đã mất DOI, rỗng summary và bị nhân bản. Uniqueness, độ dài text và freshness bắt các lỗi mà row count không thấy.
3. RAG không tự báo khi nguồn sạch bị thay. Hit rate về 0 trong khi pipeline vẫn index đủ 24 vector. Observability phải đứng trước embedding, và metric phải gắn ground-truth document id chứ không chỉ nhìn câu trả lời có vẻ hợp lý.

### Nếu có thêm thời gian

Tôi muốn ghi thêm một manifest nhỏ cạnh raw snapshot: số record parse được, số record bị loại và lý do (thiếu DOI, thiếu abstract, ngày lỗi, DOI trùng). Cách đo: cố ý bỏ abstract của một item trong bản copy payload, chạy `parse_crossref_payload`, và kiểm tra manifest tăng đúng một dòng `missing_abstract` trong khi file raw gốc không bị ghi đè. Hiện tại dòng hỏng bị `continue` im lặng; với snapshot 24/24 thì không sao, nhưng live Crossref sẽ khó giải thích vì sao clean ít hơn `rows` đã xin.

## 10. Cam kết của thành viên

Giang Thế Vũ xác nhận:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Giang Thế Vũ
**Ngày xác nhận:** 2026-09-25
