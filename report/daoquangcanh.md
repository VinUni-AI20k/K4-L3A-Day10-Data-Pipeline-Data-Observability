# Member Role Report — Day 10: Data Pipeline & Data Observability

> Báo cáo cá nhân cho vai trò Source owner, phản ánh phần việc đã triển khai và kết quả đã kiểm chứng.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đào Quang Cảnh              |
| MSSV               | 2A202602542                    |
| Khóa/Lớp         | K4              |
| Tên nhóm         | CDCV     |
| Vai trò chính    | Source owner                 |
| Repository         | https://github.com/DngVinh/K4-L3A-Day10-CDCV |
| Ngày hoàn thành | 2026-09-25               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Crossref payload parsing | `src/ingestion/crossref.py` — `parse_crossref_payload()` | JSON theo cấu trúc `message.items` của Crossref | `list[PaperRecord]` có schema ổn định, DOI không trùng | Hoàn thành và đã kiểm chứng với 24 records |
| Source fetching và raw preservation | `fetch_source_records()` | `Settings`, Crossref REST API hoặc snapshot offline | `crossref_response.json`, `crossref_records.json` | Hoàn thành; có retry, timeout và fallback offline |
| Raw-record loading và validation | `load_raw_records()` | Đường dẫn file JSON chứa danh sách raw records | `list[PaperRecord]` đã kiểm tra schema | Hoàn thành và đã kiểm chứng load lại 24 records |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Thống nhất contract dữ liệu đầu vào | Thành viên 2 — `cleaning.py` | Bàn giao schema `PaperRecord` gồm 11 trường; `paper_id` và `title` bắt buộc, `authors` và `categories` luôn là list |
| Hỗ trợ dữ liệu phục hồi | Thành viên 4 — `corruption_flow.py` | Raw snapshot có thể được đọc lại bằng `load_raw_records()` để tái tạo dữ liệu sau corruption |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Parse metadata Crossref | `parse_crossref_payload()` | Chuẩn hóa DOI, title, summary, authors, categories, ngày và URL; loại record thiếu DOI/title và DOI trùng | Parse snapshot và assert đủ 24 DOI duy nhất |
| Làm sạch trường văn bản ở tầng source | `_clean_text()`, `_authors()`, `_categories()` | Loại JATS/XML, giải mã HTML entity, chuẩn hóa khoảng trắng và loại giá trị lặp | Kiểm tra summary đầu tiên không còn ký tự `<` và edge case `A &amp; B` thành `A & B` |
| Hỗ trợ online/offline | `fetch_source_records()` | Offline mặc định; live API khi `REFRESH_SOURCE=true`; retry ba lần và fallback snapshot | Mock lỗi kết nối, xác nhận API được thử ba lần và vẫn trả về 24 records |
| Kiểm tra raw schema khi đọc lại | `load_raw_records()` | Phát hiện file không phải JSON array, thiếu trường, sai kiểu list, DOI/title rỗng và DOI trùng | Load lại `data/raw/crossref_records.json`, nhận đủ 24 `PaperRecord` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Output chính là `data/raw/crossref_records.json` gồm 24 bản ghi. Mỗi bản ghi tuân theo schema 11 trường: `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment`. File này là đầu vào trực tiếp cho bước cleaning và cũng là nguồn đáng tin cậy để repair dữ liệu về sau.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một nguồn dữ liệu đầu vào ổn định và có thể tái hiện. Dữ liệu Crossref thực tế có nhiều trường tùy chọn, abstract chứa JATS/XML, ngày tháng có thể thiếu tháng/ngày, API có thể timeout hoặc trả lỗi tạm thời. Phần Source owner giải quyết việc chuyển payload không đồng nhất đó thành schema cố định, đồng thời bảo toàn dữ liệu thô và duy trì khả năng chạy offline.

### Cách triển khai

`parse_crossref_payload()` duyệt `message.items`, chuẩn hóa DOI về chữ thường và bỏ record không có DOI hoặc title. Parser loại thẻ JATS/XML khỏi abstract, giải mã HTML entity, ghép `given` và `family` thành tên tác giả, loại giá trị tác giả/chuyên ngành lặp, đồng thời chọn các trường ngày và URL theo chuỗi fallback.

Ngày xuất bản được ưu tiên theo thứ tự `published`, `published-print`, `published-online`, `issued`, `created`. Ngày thiếu tháng hoặc ngày được chuẩn hóa lần lượt thành tháng 1 và ngày 1. `updated` ưu tiên `indexed`, `deposited`, `created`, sau đó fallback về `published`. PDF URL được lấy từ `link` có content type PDF; nếu không có thì dùng URL DOI.

`fetch_source_records()` chạy snapshot offline theo mặc định để kết quả có thể tái hiện. Khi `REFRESH_SOURCE=true`, hàm gọi Crossref với timeout, thử lại tối đa ba lần cho lỗi mạng hoặc HTTP tạm thời (`429`, `500`, `502`, `503`, `504`) và dùng exponential backoff. Response chỉ được ghi vào raw artifact sau khi JSON đã parse thành ít nhất một record hợp lệ. Nếu live API thất bại, hàm tự động quay về snapshot.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input | Crossref JSON có `message.items`, hoặc `data/raw/crossref_response.json`; cấu hình query/filter/max results từ `Settings` |
| Output | `list[PaperRecord]`, `data/raw/crossref_response.json`, `data/raw/crossref_records.json` |
| Module phụ thuộc | `src/core/config.py`, `src/core/utils.py`, thư viện `requests` |
| Module sử dụng output | `src/ingestion/cleaning.py`, `src/pipelines/phase1.py`, luồng repair trong `corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Mất mạng, timeout, 429/5xx, JSON sai cấu trúc, trường tùy chọn bị thiếu, DOI/title rỗng, DOI trùng và raw-record schema không hợp lệ |

### Cách xác minh

```bash
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records, load_raw_records; s=load_settings(); r=fetch_source_records(s); loaded=load_raw_records(s.paths.raw_records_json); assert len(r)==len(loaded)==24; assert '<' not in r[0].summary; assert len({x.paper_id for x in r})==24; print(f'Loaded {len(r)} papers')"
```

- **Kết quả mong đợi:** Đọc được 24 bài báo, 24 DOI duy nhất và abstract đã loại thẻ XML.
- **Kết quả thực tế:** `Loaded 24 papers`; kiểm thử edge cases và kiểm thử retry/fallback đều `PASS`.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Nếu luôn gọi live API, pipeline có thể thất bại trong buổi demo do mất mạng hoặc rate limit. Nếu chỉ dùng snapshot, pipeline không thể lấy dữ liệu mới.
- **Các phương án đã cân nhắc:** (1) luôn gọi API và dừng khi lỗi; (2) chỉ đọc snapshot; (3) hỗ trợ hai chế độ với live API tùy chọn và fallback snapshot.
- **Phương án đã chọn:** Chế độ offline có khả năng tái hiện là mặc định; đặt `REFRESH_SOURCE=true` để gọi live API, có retry và fallback về snapshot.
- **Lý do:** Giữ được cả freshness khi cần lẫn reproducibility khi học tập/demo. Chỉ ghi raw response sau khi parse thành công giúp tránh phá hỏng snapshot tốt bằng response lỗi.
- **Bằng chứng quyết định phù hợp:** Chế độ offline trả đủ 24 records; khi mock `ConnectionError`, hàm thử gọi API ba lần rồi fallback và vẫn trả đủ 24 records.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `NotImplementedError: Student task: implement source fetching.`
- **Lệnh hoặc bước tái hiện:** Gọi `fetch_source_records(load_settings())` trên starter repository.
- **Nguyên nhân gốc:** Ba hàm `parse_crossref_payload()`, `fetch_source_records()` và `load_raw_records()` mới chỉ có pseudo-code, chưa có implementation.
- **Cách xử lý:** Cài đặt parser và schema validation, bổ sung gọi API có timeout/retry, raw preservation, chế độ offline và fallback snapshot.
- **Cách xác minh sau khi sửa:** Chạy lệnh nghiệm thu và nhận `Loaded 24 papers`; chạy thêm edge-case test và retry/fallback test đều `PASS`.
- **Điều học được:** Fallback chỉ đáng tin cậy khi raw artifact được bảo toàn và kiểm tra trước khi ghi; không nên để một response lỗi ghi đè nguồn phục hồi.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. Crossref payload được lưu nguyên bản, parse thành `PaperRecord`, làm sạch thành DataFrame và tạo `text_for_embedding`. MiniLM biến trường này thành vector và ChromaDB lưu vector cùng metadata để truy vấn.
2. Mỗi câu hỏi evaluation chứa đáp án chuẩn và `ground_truth_doc_ids`. Retrieval hit được tính khi DOI chuẩn xuất hiện trong top-k; câu trả lời được so với ground truth bằng Token F1 và LLM Judge.
3. Quality checks kiểm tra tính đầy đủ, duy nhất, hợp lệ và độ dài trường. Freshness monitoring tập trung vào tuổi dữ liệu và tỷ lệ record quá SLA 180 ngày.
4. Cùng một test set giữ nguyên độ khó và ground truth, nên chênh lệch metric có thể quy về thay đổi của dữ liệu thay vì thay đổi câu hỏi.
5. Repair thành công khi dữ liệu được tái tạo từ raw source, quality/freshness trở lại trạng thái baseline và metrics repaired phục hồi gần hoặc bằng baseline trên cùng test set.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | Chưa có | Chưa có | Chưa có | Pipeline evaluation chưa được thành viên phụ trách tích hợp chạy |
| `mean_token_f1` | Chưa có | Chưa có | Chưa có | Không tự suy diễn số liệu khi artifact metrics chưa tồn tại |
| `judge_accuracy` | Chưa có | Chưa có | Chưa có | Chờ `baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json` |
| `mean_judge_score` | Chưa có | Chưa có | Chưa có | Chờ kết quả chạy end-to-end |
| Quality checks | Chưa có | Chưa có | Chưa có | Ngoài phạm vi Source owner; chờ `quality.py` hoàn thiện |
| Freshness status | Chưa có | Chưa có | Chưa có | Ngoài phạm vi Source owner; chờ freshness artifact |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

Hiện chưa thể hoàn thành hai chuỗi nhân quả bằng số liệu vì pipeline baseline/corruption/repair và các metric artifact chưa được tạo. Sau khi tích hợp, cần điền đúng số liệu từ `data/results/` và `data/quality/`, không kết luận dựa trên kỳ vọng.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Chưa kết luận vì chưa có `corrupted_metrics.json`. Về giả thuyết, drop record hoặc blank summary của tài liệu thuộc test set có thể ảnh hưởng trực tiếp đến retrieval hit và answer quality, nhưng phải xác nhận bằng artifact thực tế.

Kết quả nào khác với kỳ vọng ban đầu?

Chưa có kết quả end-to-end để đối chiếu kỳ vọng. Phần Source owner đã xác minh riêng rằng parser, schema, retry và fallback hoạt động đúng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw preservation và schema contract giúp pipeline có thể chạy lại, debug và repair mà không phụ thuộc hoàn toàn vào API bên ngoài.
2. Observability phải bắt đầu ngay từ source: cần phát hiện payload sai cấu trúc, record thiếu identity và duplicate trước khi chúng lan sang các tầng sau.
3. DOI, title hoặc summary sai ở nguồn sẽ ảnh hưởng trực tiếp tới document identity, embedding, retrieval và cuối cùng là câu trả lời của RAG.

### Nếu có thêm thời gian

Bổ sung pytest tự động cho nhiều biến thể payload Crossref và kiểm thử HTTP bằng mock, bao gồm `Retry-After`, timeout, malformed JSON và snapshot hỏng. Đo cải thiện bằng coverage của `crossref.py`, tỷ lệ test pass và khả năng phát hiện regression trước khi chạy pipeline end-to-end.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đào Quang Cảnh

**Ngày xác nhận:** 2026-09-25
