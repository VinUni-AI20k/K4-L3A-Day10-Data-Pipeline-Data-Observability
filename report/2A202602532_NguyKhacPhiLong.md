# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                               |
| ------------------ | -------------------------------------- |
| Họ và tên       | Ngụy Khắc Phi Long                    |
| MSSV               | 2A202602532                            |
| Khóa/Lớp         | K4-L3-DAY10                           |
| Tên nhóm         | GOHOME                     |
| Vai trò chính    | Data Foundation & Recovery Specialist  |
| Repository         | https://github.com/Nam-phuong624/K4-L3A-Day10-Data-Pipeline-Data-Observability       |
| Ngày hoàn thành | 2026-09-25                             |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable       | File/hàm phụ trách                    | Input nhận vào                        | Output bàn giao                               | Trạng thái |
| ------------------------ | --------------------------------------- | ------------------------------------- | --------------------------------------------- | ---------- |
| Crossref ingestion       | `src/ingestion/crossref.py`            | Crossref API / cache file             | `data/raw/crossref_records.json`              | Hoàn thành |
| Data cleaning            | `src/ingestion/cleaning.py`            | `list[PaperRecord]`                  | `papers_clean.csv`, `papers_clean.json`       | Hoàn thành |
| Corruption suite         | `src/ingestion/corruption.py`          | clean DataFrame                       | corrupted DataFrame, `corruption_log.json`    | Hoàn thành |
| Idempotent repair        | `corruption_flow.py` (bước 4)         | `crossref_records.json` (raw snapshot)| `papers_clean_repaired.csv/json`              | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động             | Thành viên/module được hỗ trợ | Kết quả                                                    |
| ---------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Định nghĩa `text_for_embedding` format | Phát (retrieval/index.py) | Format thống nhất: Title/Authors/Published/Categories/Summary |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                        | File/hàm/artifact liên quan           | Kết quả bàn giao                       | Cách xác minh                     |
| --------------------------------------------- | --------------------------------------- | --------------------------------------- | --------------------------------- |
| Fetch và parse 24 bài báo từ Crossref        | `crossref.py:fetch_source_records`    | `data/raw/crossref_records.json`       | `wc -l data/raw/crossref_records.json` |
| Chuẩn hóa và tính `text_for_embedding`       | `cleaning.py:build_clean_dataframe`   | `data/clean/papers_clean.json` (24 rows) | `python script/run_phase1.py` step [2/7] |
| Thiết kế 6 dạng corruption đủ trigger GX + Freshness | `corruption.py:corrupt_clean_dataframe` | `data/results/corruption_log.json` | Kiểm tra log: 6 mutation types   |
| Rebuild từ raw snapshot (idempotent)          | `crossref.py:load_raw_records` + `cleaning.py` | `data/clean/papers_clean_repaired.json` | Repaired có 24 rows = baseline  |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cung cấp dữ liệu sạch, chuẩn hóa làm nền tảng cho toàn bộ pipeline. Đồng thời thiết kế bộ corruption đủ để kích hoạt cả 2 loại signal (GX + Freshness), và đảm bảo repair phục hồi hoàn toàn từ nguồn gốc.

### Cách triển khai

**Crossref ingestion:**
- `_strip_jats()`: loại bỏ JATS XML tags khỏi abstract bằng regex.
- `_parse_date()`: xử lý date-parts dạng `[[year, month, day]]` với fallback an toàn.
- `fetch_source_records()`: kiểm tra cache trước, gọi API nếu `refresh_source=True`, retry tự động với 429/503.

**Cleaning:**
- Tính `age_days = (today - published).days` để dùng cho freshness check.
- `text_for_embedding` format: `"Title: {t}\nAuthors: {a}\nPublished: {p}\nCategories: {c}\nSummary: {s}"` — format này phải khớp chính xác với qa.py.
- Dedup theo `paper_id`, lọc record thiếu title hoặc summary, sort by published desc.

**Corruption (6 mutations):**
1. `drop_latest`: xóa 20% record mới nhất — giảm coverage retrieval.
2. `blank_summary`: làm trống summary 3 rows — vi phạm GX length check.
3. `inject_noise`: thêm `####NOISE####` vào summary — gây nhiễu embedding.
4. `truncate_title`: cắt title còn 7 ký tự — làm mất context retrieval.
5. `stale_date`: lùi published 3 năm trên 6 rows → 7/23 = 30.4% > 25% → `is_fresh=False`.
6. `duplicate_rows`: nhân đôi 3 rows — vi phạm GX uniqueness check.

### Input, output và contract

| Thành phần            | Mô tả                                                                   |
| --------------------- | ----------------------------------------------------------------------- |
| Input                 | Crossref REST API (hoặc `data/raw/crossref_response.json` nếu offline) |
| Output                | `papers_clean.json`: list of dicts với 13 trường chuẩn hóa             |
| Module phụ thuộc     | `core/config.py` (settings), `core/utils.py` (I/O)                    |
| Module sử dụng output | `retrieval/index.py` (embed), `observability/quality.py` (GX checks)  |
| Điều kiện lỗi        | API timeout → fallback local. Record thiếu DOI/title → bỏ qua.        |

### Cách xác minh

```bash
conda run -n vin python script/run_phase1.py
# Kiểm tra bước [2/7]: "Clean dataframe: 24 rows"
# Kiểm tra bước [3/7]: file clean được tạo
```

- **Kết quả mong đợi:** 24 rows sạch, không có null ở `paper_id`/`title`/`text_for_embedding`.
- **Kết quả thực tế:** 24 rows, GX 6/6 pass.
- **Artifact/log:** `data/clean/papers_clean.json`, `data/results/corruption_log.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Stale date corruption ban đầu chỉ tác động 4 rows → stale_ratio = 4/23 = 21.7% < 25% threshold → `is_fresh=True` (không trigger signal).
- **Các phương án:** (1) Giảm threshold xuống 20%. (2) Tăng số rows bị stale.
- **Phương án đã chọn:** Tăng stale_date từ rows 9:13 lên 9:15 (6 rows) → 7/23 = 30.4% > 25%.
- **Lý do:** Thay đổi threshold là thay đổi spec — nên giữ nguyên spec và điều chỉnh số lượng records bị corrupt để đảm bảo signal trigger đúng thiết kế.
- **Bằng chứng:** Sau sửa: `is_fresh=False` trong `corrupted_freshness_report.json`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `text_for_embedding` trong `corruption.py` (rebuild sau corrupt) không khớp format với `cleaning.py` — gây embedding khác nhau cho cùng một paper.
- **Nguyên nhân gốc:** Rebuild trong `corruption.py` dùng label "Abstract:" thay vì "Summary:", sai thứ tự fields.
- **Cách xử lý:** Cập nhật rebuild trong `corruption.py` dùng đúng format: `"Title: ...\nAuthors: ...\nPublished: ...\nCategories: ...\nSummary: ..."`.
- **Cách xác minh:** So sánh `text_for_embedding` của cùng paper trong `papers_clean.json` và `papers_clean_corrupted.json` (với rows không bị corrupt) — phải giống nhau.
- **Điều học được:** Mọi nơi tạo `text_for_embedding` phải dùng cùng format constant — nên extract ra một helper function chung.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** Crossref API trả về JSON thô. `parse_crossref_payload` lọc bỏ item thiếu DOI hoặc title, phần còn lại map thành `PaperRecord`. `build_clean_dataframe` ghép các trường thành `text_for_embedding` — đây là "kiện hàng" giao cho MiniLM. MiniLM encode thành vector 384 chiều, ChromaDB nhận và lưu với `paper_id` làm key để tra lại sau.
2. **Evaluation set:** 10 câu, mỗi câu gắn đúng một `paper_id`. Retrieval trả về top-k papers — kiểm tra xem `paper_id` đúng có xuất hiện không. Đơn giản như tracking đơn hàng: đúng địa chỉ thì hit, sai thì miss.
3. **Quality vs Freshness:** GX kiểm tra từng trường trong record — null không, trùng không, đủ dài không. Freshness nhìn vào ngày — data đúng format nhưng từ 3 năm trước thì cũng không dùng được. Hai loại check hoàn toàn độc lập nhau, thiếu một là hở một lỗ.
4. **Cùng test set:** Chỉ muốn đo tác động của data thay đổi. Nếu câu hỏi cũng thay đổi thì không biết cái gì gây ra chênh lệch metrics. Giữ test set cố định = giữ nguyên biến kiểm soát.
5. **Repair thành công khi:** Metrics khớp baseline, GX pass sạch, `is_fresh=True`. Nghĩa là data đã trở lại đúng trạng thái ban đầu — không còn record bị xóa, không trùng lặp, không quá hạn.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét                                      |
| ---------------------- | -------: | --------: | -------: | --------------------------------------------- |
| `retrieval_hit_rate`  |   1.0000 |    0.8000 |   1.0000 | Mất 5 paper do drop_latest, 2 câu hỏi không tìm được đích đến |
| `mean_token_f1`       |   1.0000 |    0.5882 |   1.0000 | blank_summary = giao hàng thiếu nội dung, extraction trả về rỗng |
| `judge_accuracy`      |   1.0000 |    0.6000 |   1.0000 | 4 câu "giao sai địa chỉ" — data không đủ để trả lời đúng |
| `mean_judge_score`    |        5 |    3.2000 |        5 | Điểm trung bình giảm tỷ lệ với số corruption tích luỹ |
| Quality checks         |     Pass |      Fail |     Pass | 2 violation bị bắt: trùng paper_id và summary quá ngắn |
| Freshness status       |     True |     False |     True | 6 records "hàng tồn kho cũ" vượt ngưỡng 25% cho phép |

### Kết luận từ số liệu

1. `drop_latest` + `blank_summary` + `inject_noise` → GX `success=False` (uniqueness + length violations) → `retrieval_hit_rate` 1.0→0.8, `mean_token_f1` 1.0→0.59.
2. Rebuild từ `crossref_records.json` (raw snapshot) → GX `success=True`, `is_fresh=True` → cả 2 metrics phục hồi về 1.0.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data Lineage quan trọng hơn tưởng:** Giữ raw snapshot riêng biệt mới có thể repair — nếu overwrite raw thì mất khả năng phục hồi.
2. **Corruption cần trigger đủ signal:** Mỗi dạng corruption phải đủ mạnh để kích hoạt ít nhất một quality signal — không phải corruption nào cũng làm giảm metrics.
3. **Format consistency là contract:** `text_for_embedding` phải nhất quán tuyệt đối giữa ingestion và corruption rebuild — sai format = sai embedding = sai retrieval.

### Nếu có thêm thời gian

Extract `TEXT_FOR_EMBEDDING_FORMAT` thành constant trong `core/config.py`, import ở cả `cleaning.py` và `corruption.py` để tránh drift.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngụy Khắc Phi Long
**Ngày xác nhận:** 2026-09-25
