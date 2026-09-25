# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Mạnh Hải           |
| MSSV               | 2A202602988                    |
| Khóa/Lớp         |  K4          |
| Tên nhóm         | 36 Quê Tôi   |
| Vai trò chính    | THU THẬP DỮ LIỆU, LÀM SẠCH & DỰNG TRẠM KIỂM SOÁT CHẤT LƯỢNG GX 1.X                 |
| Repository         | https://github.com/trump22/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Thu thập dữ liệu Crossref (dual-mode) | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | `Settings` (query, filter, `max_results`), snapshot `data/raw/crossref_response.json` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` (24 records) | Hoàn thành |
| Làm sạch & tạo trường embedding | `src/ingestion/cleaning.py`: `build_clean_dataframe` | Danh sách `PaperRecord`, `run_date` | `data/clean/papers_clean.csv` / `.json` (24 dòng, có `age_days`, `text_for_embedding`) | Hoàn thành |
| Trạm kiểm soát chất lượng GX 1.x + Freshness | `src/observability/quality.py`: `run_data_quality_checks`, `build_freshness_report` | DataFrame sạch, `Settings` | `data/quality/<report_name>.json`, `data/quality/freshness_report.json` | Hoàn thành |

Ownership giới hạn ở Pha 2 (CP1: thu thập, làm sạch, Quality Gate). Đầu ra của phần này là đầu vào của Pha 3 trở đi: index Chroma, test set, đánh giá và corruption đều đọc `papers_clean.*` và gọi `run_data_quality_checks`.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Không có (chỉ làm phần Pha 2) | - | - |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Parse payload Crossref: DOI chuẩn hóa, title, summary (bỏ thẻ JATS), authors, subject, ngày ISO 8601 | `src/ingestion/crossref.py` | 24 `PaperRecord` | Lệnh Bước 1 in `Đã nạp 24 bài báo` |
| Cơ chế Dual-Mode: retry 429/5xx, fallback snapshot offline | `src/ingestion/crossref.py` | Raw response + raw records | `data/raw/crossref_response.json`, `crossref_records.json` |
| Làm sạch, tính `age_days`, tạo `text_for_embedding` 5 dòng, khử trùng theo `paper_id` | `src/ingestion/cleaning.py` | DataFrame 24 dòng | `data/clean/papers_clean.csv`; lệnh Bước 2 in `Clean thành công 24 dòng` |
| Quality Gate GX 1.x (6 expectation + freshness) | `src/observability/quality.py` | Report JSON | `data/quality/baseline_quality_report.json` (7/7 pass); lệnh Bước 3 in `Quality check status = True` |
| Freshness report | `src/observability/quality.py` | `data/quality/freshness_report.json` | `stale_rows` 1/24, `is_fresh: true` |

Output cụ thể: `data/quality/baseline_quality_report.json` ghi `success: true` (7 check đạt, 0 lỗi) trên dữ liệu sạch, và `data/quality/corrupted_quality_report.json` ghi `success: false` (3 check lỗi: `ExpectColumnValuesToBeUnique`, `ExpectColumnValueLengthsToBeBetween`, `FreshnessCheck`) khi dữ liệu bị tiêm lỗi.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Đưa dữ liệu thô từ Crossref về dạng sạch, có schema cố định và có "chốt chặn" chất lượng trước khi dữ liệu được embed vào ChromaDB. Nếu không có bước này, dữ liệu rác hoặc cũ sẽ đi thẳng vào vector store và gây Silent Failure ở agent.

### Cách triển khai

- **Ingestion:** `parse_crossref_payload` duyệt `message.items`, chuẩn hóa DOI về chữ thường và bỏ tiền tố `doi.org`, lấy title đầu tiên, làm sạch abstract bằng regex bỏ thẻ HTML/JATS rồi `html.unescape`, ghép tên tác giả từ `given`/`family`, đọc ngày từ `date-parts` (thiếu tháng/ngày thì mặc định 1) và xuất dạng `YYYY-MM-DD`. Record thiếu DOI, title, summary hoặc ngày bị loại. `fetch_source_records` chỉ gọi API khi bật `REFRESH_SOURCE` hoặc chưa có snapshot; mỗi lần gọi retry tối đa 3 lần (backoff 2s, 4s) với 429/5xx, nếu vẫn lỗi thì đọc snapshot offline.
- **Cleaning:** chuẩn hóa khoảng trắng, tính `age_days = (run_date - published).days`, tạo `authors_joined`, `categories_joined`, `summary_chars`, và `text_for_embedding` gồm 5 dòng (Title, Authors, Published, Categories, Summary). Cuối cùng khử trùng theo `paper_id` và sắp xếp theo ngày xuất bản giảm dần.
- **Quality Gate:** dùng API GX 1.x (`gx.get_context(mode="ephemeral")`, `add_pandas`, `add_dataframe_asset`, `add_batch_definition_whole_dataframe`). Các expectation: số dòng 5–5000, `paper_id`/`title`/`text_for_embedding` không null, `paper_id` duy nhất, độ dài `summary` ≥ 30. Freshness được tính riêng: cảnh báo khi hơn 25% bài có `age_days > 180`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `Settings`; snapshot Crossref; `list[PaperRecord]`; DataFrame sạch |
| Output                         | `list[PaperRecord]`; DataFrame với 16 cột (gồm `age_days`, `text_for_embedding`); dict report có khóa `success`, `checks` |
| Module phụ thuộc             | `core/config.py`, `core/utils.py` |
| Module sử dụng output        | `retrieval/index.py`, `evaluation/testset.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | API trả 429/5xx hoặc mất mạng (fallback snapshot); record thiếu DOI/title/abstract/ngày; DOI trùng; DataFrame rỗng |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã nạp {len(r)} bài báo')"
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
```

- **Kết quả mong đợi:** `Đã nạp 24 bài báo`, `Clean thành công 24 dòng`, `Quality check status = True`.
- **Kết quả thực tế:** đúng như mong đợi; `age_days` nằm trong khoảng 65–181 ngày, 1/24 bài quá 180 ngày.
- **Artifact/log:** `data/raw/crossref_records.json`, `data/clean/papers_clean.csv`, `data/quality/baseline_quality_report.json`, `data/quality/freshness_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `fetch_source_records` cần quyết định khi nào gọi API Crossref thật và khi nào dùng snapshot có sẵn.
- **Các phương án đã cân nhắc:** (1) luôn gọi API rồi fallback snapshot khi lỗi; (2) ưu tiên snapshot, chỉ gọi API khi bật `REFRESH_SOURCE` hoặc chưa có snapshot.
- **Phương án đã chọn:** phương án 2, vẫn giữ retry và fallback cho trường hợp gọi API.
- **Lý do:** dữ liệu ổn định (luôn 24 bài) nên các bước sau (test set, metrics, so sánh 3 trạng thái) tái lập được; tránh 429 làm gián đoạn lab. Đổi lại, dữ liệu không tự cập nhật nếu không bật `REFRESH_SOURCE`.
- **Bằng chứng quyết định phù hợp:** chạy lại nhiều lần đều ra 24 record và cùng một `crossref_records.json`. Nhánh gọi API thật (retry/429) chưa được kiểm thử trực tiếp.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** sau khi chạy Bước 1, `git diff data/raw/crossref_records.json` cho thấy 24 dòng khác snapshot gốc: trường `comment` bị đổi từ `"Crossref record <DOI>"` thành `"Crossref record"`.
- **Bước tái hiện:** chạy `fetch_source_records(load_settings())` khi `crossref_records.json` đã có sẵn trong repo.
- **Nguyên nhân gốc:** hàm parse ghi `comment` cố định, không kèm DOI, nên ghi đè file raw records có sẵn bằng nội dung khác.
- **Cách xử lý:** đổi thành `comment=f"Crossref record {paper_id}"` trong `parse_crossref_payload`.
- **Cách xác minh sau khi sửa:** chạy lại Bước 1, `git status` không còn báo `crossref_records.json` bị thay đổi.
- **Điều học được:** khi tái tạo artifact đã có trong repo, nên so sánh diff với bản gốc để bảo đảm data lineage không bị thay đổi âm thầm.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
5. Repair được xem là thành công dựa trên artifact và metric nào?

**Câu trả lời:**

1. Crossref (hoặc snapshot) → `parse_crossref_payload` → `crossref_records.json` → `build_clean_dataframe` → `papers_clean.*` → Quality Gate → embed bằng MiniLM và nạp vào ChromaDB.
2. Test set gồm câu hỏi kèm `ground_truth` và `ground_truth_doc_ids`. Retrieval hit tính khi tài liệu đúng nằm trong top-k, còn Token F1 và Judge so sánh câu trả lời với ground truth.
3. Quality checks kiểm tra tính đúng đắn của nội dung dữ liệu (null, trùng, độ dài); freshness kiểm tra dữ liệu có mới hay không dựa trên `age_days`. Một tập dữ liệu có thể sạch nhưng đã cũ, hoặc mới nhưng bị lỗi.
4. Cùng một test set giúp mọi thay đổi về chỉ số chỉ đến từ dữ liệu, không phải từ đề thi.
5. Repair thành công khi quality gate và freshness pass trở lại và `repaired_metrics.json` trở về bằng `baseline_metrics.json` (đã kiểm chứng: hai file trùng khớp).

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |    1.000 |     0.700 |    1.000 | Giảm 3/10 câu khi mất hoặc hỏng tài liệu đích |
| `mean_token_f1`      |    0.928 |     0.828 |    0.928 | Giảm khi summary bị xóa hoặc chèn nhiễu |
| `judge_accuracy`     |    0.800 |     0.700 |    0.800 | Giảm nhẹ; 2 câu multi_hop luôn sai ở cả 3 trạng thái |
| `mean_judge_score`   |     4.40 |      4.00 |     4.40 | Phục hồi hoàn toàn sau repair |
| Quality checks         | PASS (7/7) | FAIL (4 đạt, 3 lỗi) | PASS (7/7) | Gate phát hiện `paper_id` trùng, summary quá ngắn và freshness |
| Freshness status       | Fresh (1/24 stale) | Không fresh (7/24 stale) | Fresh (1/24 stale) | Vượt ngưỡng 25% khi tiêm lỗi stale date |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

1. Tiêm lỗi (trùng dòng, summary rỗng, lùi ngày 5 năm) → check unique, độ dài summary và freshness đều fail → hit rate giảm từ 1.0 xuống 0.7 và Token F1 giảm từ 0.928 xuống 0.828.
2. Repair từ raw snapshot → quality và freshness pass trở lại → cả bốn metric về đúng giá trị baseline.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Chưa đủ dữ liệu để kết luận riêng từng loại lỗi vì cả 6 lỗi được tiêm cùng lúc. Lỗi làm mất hoặc hỏng tài liệu đích (drop, truncate title) trực tiếp làm hit rate giảm; blank/noise summary làm giảm Token F1.

Kết quả nào khác với kỳ vọng ban đầu?

Slide kỳ vọng hit rate "giảm sâu" (ví dụ ≤ 40%) nhưng thực tế chỉ giảm xuống 0.7. Nguyên nhân có thể do chỉ có 10 câu hỏi và seed cố định 42 chọn dòng hỏng ít trùng với các bài trong test set; chưa kiểm chứng thêm bằng nhiều seed khác nhau.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Nên lưu raw snapshot và chỉ sinh dữ liệu sạch từ đó, để pipeline có thể tái tạo và kiểm tra lineage.
2. Quality check và freshness check là hai tín hiệu khác nhau, cần theo dõi cả hai.
3. Dữ liệu hỏng không gây lỗi runtime nhưng làm chất lượng câu trả lời giảm âm thầm, nên phải có Quality Gate trước khi index.

### Nếu có thêm thời gian

Kiểm thử trực tiếp nhánh gọi API thật (retry 429, ghi đè snapshot) bằng test có mock `requests`, để xác nhận fallback hoạt động; đo bằng việc test pass khi giả lập 429 liên tiếp.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Mạnh Hải
**Ngày xác nhận:** [2026-09-25]
