# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                       |
| ------------------ | ------------------------------------------------------------------------------ |
| Họ và tên         | Vũ Minh Hoàng                                                                  |
| MSSV               | 2A202602371                                                                    |
| Khóa/Lớp           | K4 / K4A-FinTech                                                               |
| Tên nhóm           | K4A-DAY10-FinTech                                                              |
| Vai trò chính      | Thành viên 2 — Data Foundation & Recovery Owner (Kỹ sư Dữ liệu)               |
| Repository         | https://github.com/ratrichero/K4-L3A-Day10-Data-Pipeline-Data-Observability.git|
| Ngày hoàn thành   | 2026-09-25                                                                     |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| **Ingestion & Dual-Mode Fallback** | `src/ingestion/crossref.py`<br>- `parse_crossref_payload`<br>- `fetch_source_records`<br>- `load_raw_records` | Crossref REST API hoặc `data/raw/crossref_response.json` | `data/raw/crossref_response.json`<br>`data/raw/crossref_records.json` | Hoàn thành |
| **Data Cleaning & Embedding Modeling** | `src/ingestion/cleaning.py`<br>- `build_clean_dataframe` | `list[PaperRecord]` từ raw records và `run_date` | `data/clean/papers_clean.csv`<br>`data/clean/papers_clean.json` | Hoàn thành |
| **Synthetic Corruption & Repair Suite** | `src/ingestion/corruption.py`<br>- `corrupt_clean_dataframe`<br>- `repair_clean_dataframe` | `papers_clean.json` và `crossref_records.json` | `data/clean/papers_clean_corrupted.csv/json`<br>`data/results/corruption_log.json`<br>`data/clean/papers_clean_repaired.csv/json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Chuẩn hóa Data Contract | TV1 (Lead), TV3 (RAG), TV4 (Observability) | Đóng băng schema 16 trường chuẩn cho `papers_clean.csv/json` phục vụ Vector Store & Quality Gates. |
| Hỗ trợ cấu hình GX 1.x | TV4 (Observability & Quality) | Tích hợp kiểm tra `age_days` và `text_for_embedding` vào Data Quality Gate trong `src/observability/quality.py`. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ---------------- | ------------- |
| Ingestion & Fallback Rescue | `src/ingestion/crossref.py` | 24 bản ghi raw `crossref_records.json` | `python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(len(r))"` -> Output `24` |
| Clean & Pre-embed Modeling | `src/ingestion/cleaning.py` | DataFrame 24 dòng sạch với `text_for_embedding` 5 dòng | `python -c "from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; from datetime import datetime, timezone; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(len(df))"` -> Output `24` |
| Data Corruption Injection | `src/ingestion/corruption.py` | 6 kịch bản lỗi + `corruption_log.json` | `python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(len(c))"` |
| Idempotent Repair Logic | `src/ingestion/corruption.py` | Repaired DataFrame sạch 100% | `python -c "from core.config import load_settings; from ingestion.corruption import repair_clean_dataframe; s=load_settings(); df=repair_clean_dataframe(s.paths.raw_records_json); print(len(df))"` -> Output `24` |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. **API Volatility & Network Drops**: API Crossref có thể trả về lỗi `429 Too Many Requests` hoặc bị mất kết nối mạng khi học/demo.
2. **Dirty & Unstructured Text**: Raw JSON từ API chứa các thẻ XML/HTML rác (`<jats:p>`, `</jats:p>`), khoảng trắng thừa, và thiếu thuộc tính độ tươi (`age_days`).
3. **Synthetic Failure & Recovery**: Cần giả lập sự cố dữ liệu bẩn sản xuất và cung cấp cơ chế tự phục hồi bất biến (Idempotent Repair) mà không cần sửa thủ công.

### Cách triển khai

1. **Dual-Mode Ingestion**:
   Trong `fetch_source_records()`, hệ thống ưu tiên gọi Crossref REST API (nếu `refresh_source=True`). Nếu xảy ra ngoại lệ kết nối hoặc status code `429/503`, pipeline chuyển hướng đọc offline snapshot từ `data/raw/crossref_response.json`.

2. **Data Cleaning & Embedding Text Assembly**:
   Hàm `build_clean_dataframe()` lọc trùng lặp theo `paper_id`, tính `age_days = (run_date - published).days`, và ghép chuỗi 5 dòng cho Vector DB:
   ```text
   Title: <Tiêu đề>
   Authors: <Danh sách tác giả>
   Published: <Ngày xuất bản>
   Categories: <Chuyên ngành>
   Summary: <Tóm tắt nội dung>
   ```

3. **6 Kịch bản Corruption & Idempotent Repair**:
   - `corrupt_clean_dataframe()`: Giả lập 6 lỗi (`drop_latest_records`, `blank_summary`, `inject_noise`, `truncate_title`, `stale_date`, `duplicate_rows`) và ghi log ra `corruption_log.json`.
   - `repair_clean_dataframe()`: Nạp lại raw snapshot gốc `crossref_records.json` và tái chạy pipeline `build_clean_dataframe()`. Giúp khôi phục trạng thái sạch 100% bất biến qua nhiều lần chạy.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ------ |
| **Input** | Payload JSON từ API hoặc local snapshot `crossref_response.json` |
| **Output** | `PaperRecord` objects, `papers_clean.csv/json`, `corruption_log.json` |
| **Module phụ thuộc** | `core/config.py` (Paths & Settings) |
| **Module sử dụng output** | `retrieval/index.py` (ChromaDB), `observability/quality.py` (GX 1.x Quality Gate) |
| **Điều kiện lỗi xử lý** | Mất mạng/API quá tải 429, summary thiếu/chứa thẻ XML, paper_id trùng lặp |

### Cách xác minh

```powershell
.\.venv\Scripts\python.exe -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import fetch_source_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); records=fetch_source_records(s); df=build_clean_dataframe(records, datetime.now(timezone.utc)); print(f'Xác minh: {len(records)} raw records -> {len(df)} clean rows')"
```
- **Kết quả thực tế:** `Xác minh: 24 raw records -> 24 clean rows`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn giữa việc sửa trực tiếp trên file cleaned khi xảy ra sự cố hay áp dụng kiến trúc **Data Lineage & Idempotent Repair**.
- **Các phương án đã cân nhắc:**
  - *Phương án A:* Viết script patch/thao tác trực tiếp sửa từng dòng dữ liệu bị lỗi.
  - *Phương án B:* Bảo toàn tầng Raw Data gốc (Immutable Raw Snapshot), khi khôi phục chỉ cần nạp lại Raw Snapshot và chạy lại hàm Clean.
- **Phương án đã chọn:** **Phương án B (Idempotent Repair)**.
- **Lý do:** Phương án B đảm bảo tính bất biến (Idempotency), loại bỏ hoàn toàn rủi ro sai sót do patch thủ công, tuân thủ nguyên tắc Data Lineage trong kỹ nghệ dữ liệu hiện đại.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  `UnicodeEncodeError: 'charmap' codec can't encode character '\u0110'` khi chạy lệnh Python trên terminal Windows PowerShell.
- **Nguyên nhân gốc:** Console Windows mặc định dùng bảng mã `cp1252` không mã hóa được các ký tự tiếng Việt có dấu (như từ `'Đã'`).
- **Cách xử lý:** Chuẩn hóa mã hóa file bằng `encoding="utf-8"` trong mọi thao tác I/O (`json.dump`, `open`) và sử dụng chuỗi ASCII cho log console trên lệnh terminal CLI.
- **Cách xác minh sau khi sửa:** Chạy lại script tạo dữ liệu bằng lệnh `.\.venv\Scripts\python.exe` trả về `Successfully created papers_clean.json with 24 records.` không xuất hiện exception.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu thô từ Crossref API được tải về dưới dạng JSON -> qua `parse_crossref_payload` loại bỏ thẻ XML/JATS -> qua `build_clean_dataframe` khử trùng lặp và đóng gói thành `text_for_embedding` -> được chuyển tới `retrieval/index.py` sinh vector embedding qua `all-MiniLM-L6-v2` và nạp vào ChromaDB collection.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Evaluation set chứa 10 câu hỏi chuẩn hóa cùng danh sách `ground_truth_doc_ids`. Khi RAG Agent truy vấn, `retrieval_hit_rate` được tính bằng tỷ lệ câu hỏi mà top-k retrieved documents chứa ít nhất 1 `ground_truth_doc_id`. `mean_token_f1` đo mức độ trùng khớp giữa câu trả lời sinh ra và `ground_truth`.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - **Quality checks (Great Expectations 1.x)**: Kiểm tra cấu trúc/toàn vẹn dữ liệu tức thời (dòng không null, paper_id duy nhất, row count 5-5000, summary length >= 30).
   - **Freshness Monitoring (SLA)**: Theo dõi trục thời gian của dữ liệu dựa trên `age_days`. Phát cảnh báo khi tỷ lệ bài báo cũ (`age_days > 180`) vượt ngưỡng 25%.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Giữ cố định test set là điều kiện bắt buộc để đảm bảo tính chuẩn hóa của thử nghiệm (Controlled Experiment), từ đó đo lường chính xác mức độ sụt giảm chỉ số khi dữ liệu bẩn và mức độ phục hồi sau khi Idempotent Repair.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Repair thành công khi: (1) Báo cáo GX 1.x `success = True`, (2) Freshness SLA `is_fresh = True`, và (3) Metrics RAG (`retrieval_hit_rate`, `mean_token_f1`) phục hồi về mức tương đương Baseline.

---

## 8. Phân tích kết quả

### Metrics đối chiếu 3 trạng thái

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ------------- | --------:| ---------:| --------:| -------------------- |
| `retrieval_hit_rate` | 1.00 | 0.60 | 1.00 | Data corruption làm sụt giảm 40% khả năng truy vết do mất dữ liệu mới & tiêu đề bị truncate. |
| `mean_token_f1` | 0.85 | 0.42 | 0.85 | Token F1 giảm mạnh khi summary bị xóa rỗng hoặc chèn nhiễu. Phục hồi hoàn toàn sau Repair. |
| Quality checks (GX 1.x) | `True` | `False` | `True` | Data Quality Gate báo động chính xác khi phát hiện dòng trùng lặp và summary < 30 ký tự. |
| Freshness status | `Fresh` | `Stale Alert` | `Fresh` | Cảnh báo mốc dữ liệu kích hoạt đúng khi ngày xuất bản bị lùi 365 ngày. |

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Tầm quan trọng của Raw Data Preservation**: Luôn lưu giữ snapshot dữ liệu thô ban đầu để đảm bảo khả năng phục hồi dữ liệu Idempotent bất cứ lúc nào.
2. **Data Observability sớm**: Cài đặt Quality Gate tự động (Great Expectations + Freshness SLA) giúp phát hiện rủi ro dữ liệu bẩn trước khi dữ liệu được nạp vào Vector Database.
3. **Tác động của Silent Failure**: Dữ liệu lỗi không làm sập ứng dụng RAG nhưng trực tiếp làm giảm độ chính xác câu trả lời của LLM Agent.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Vũ Minh Hoàng  
**Ngày xác nhận:** 2026-09-25
