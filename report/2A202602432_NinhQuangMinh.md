# Báo cáo cá nhân — Ninh Quang Minh — Day 10 Data Pipeline

> Bản ghi kết quả kỹ thuật đã kiểm ngày 25/09/2026. Mã nguồn và bản nháp báo cáo được chuẩn bị với hỗ trợ của Codex; Minh cần tự rà soát, diễn giải và xác nhận các mục cá nhân trước khi nộp. Kết quả pipeline toàn nhóm chưa được ghi là hoàn thành.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Ninh Quang Minh |
| MSSV | 2A202602432 |
| Email | minhnq.chc@gmail.com |
| Khóa/Lớp | K4 |
| Tên nhóm | G36 |
| Vai trò chính | Data Foundation — Crossref ingestion, bảo toàn raw, cleaning |
| Repository | https://github.com/tuanfptu/K4-L3-DAY10-G36-DataPipeline |
| Ngày hoàn thành phần Data Foundation | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

| Phần việc sở hữu | File/hàm | Input | Output | Trạng thái |
|---|---|---|---|---|
| Chọn nguồn ADAS | `data/raw/adas_selected_dois.json` | Context P-065, metadata Crossref | 24 DOI và trọng tâm từng bài | Đã chọn và xác minh metadata |
| Thu thập và parse | `src/ingestion/crossref.py` | Crossref API hoặc snapshot offline | `crossref_response.json`, 24 `PaperRecord` trong `crossref_records.json` | Đã chạy Bước 2 |
| Làm sạch | `src/ingestion/cleaning.py` | 24 `PaperRecord`, ngày chạy | `papers_clean.csv`, `papers_clean.json`, DataFrame 24 dòng | Đã kiểm tra độc lập |

Tuân dùng raw/clean để ghép pipeline và repair; Tùng dùng `paper_id` và `text_for_embedding` để index/tạo test set; Đức Anh dùng schema, `summary_chars`, `age_days` để kiểm quality/freshness; Nguyên dùng clean baseline để tạo dữ liệu lỗi và báo cáo. Các phần này do những thành viên tương ứng tích hợp và nghiệm thu.

## 3. Kết quả và bằng chứng của phần Data Foundation

| Việc đã thực hiện | Bằng chứng | Kết quả kiểm |
|---|---|---|
| Gọi Crossref theo 24 DOI chọn trước, giữ JSON response nguyên dạng | `data/raw/crossref_response.json`; `data/raw/adas_selected_dois.json` | 24 item, DOI khớp manifest |
| Chuẩn hóa DOI, title, abstract, tác giả, ngày, URL | `data/raw/crossref_records.json` | 24 record, đủ trường bắt buộc, không trùng DOI |
| Làm sạch và tạo dữ liệu cho embedding | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` | 24 dòng; mỗi `text_for_embedding` gồm Title, Authors, Published, Categories, Summary |
| Kiểm fallback offline và khử trùng lặp | Chạy giả lập lỗi kết nối và đầu vào lặp đôi | Offline vẫn trả 24; raw hash không đổi; 48 đầu vào lặp còn 24 DOI |

Tại ngày 25/09/2026, abstract ngắn nhất sau làm sạch là 794 ký tự; `age_days` lớn nhất là 174. Crossref không cấp `subject` cho 24 bài, nên `categories` là nhãn chủ đề suy ra từ title/abstract và `comment` ghi rõ nguồn suy ra. Chỉ 4 bản ghi có PDF URL từ Crossref; không tự tạo URL PDF.

## 4. Cách triển khai và contract

1. `fetch_source_records(settings)` đọc danh sách DOI, dùng Crossref REST API khi cần cập nhật; retry cho HTTP 429/5xx. Chỉ thay snapshot sau khi đủ 24 DOI hợp lệ. Nếu mạng lỗi, đọc snapshot hợp lệ trước đó.
2. `parse_crossref_payload(payload)` chuyển JSON Crossref thành `PaperRecord`; giải mã entity rồi bỏ JATS/HTML, chuẩn hóa text và giữ DOI làm ID. `load_raw_records(path)` đọc artifact đã parse mà không cần mạng.
3. `build_clean_dataframe(records, run_date)` loại record thiếu trường bắt buộc, tính `age_days`, `summary_chars`, nối authors/categories, dựng `text_for_embedding`, khử DOI trùng và sắp xếp ổn định.

| Contract | Chi tiết |
|---|---|
| Input | `data/raw/adas_selected_dois.json` và Crossref `message.items`, hoặc hai snapshot raw có sẵn |
| Output | `PaperRecord` với `paper_id, title, summary, authors, categories, primary_category, published, updated, abs_url, pdf_url, comment`; clean DataFrame có thêm `age_days, authors_joined, categories_joined, summary_chars, text_for_embedding` |
| ID và định dạng | `paper_id` là DOI chữ thường; `published`/ `updated` ở dạng ISO date; `text_for_embedding` gồm 5 dòng có nhãn |
| Lưu ý tích hợp | Chế độ DOI chọn trước dùng manifest; `source_query`/`source_filter` mặc định trong `core/config.py` không quyết định bộ 24 bài này |
| Điều kiện lỗi | API 429/5xx, mất mạng, phản hồi thiếu DOI, record thiếu abstract/ngày/tác giả; chỉ fallback về snapshot đã xác minh cùng bộ DOI |

**Lệnh Bước 2 đã chạy tại gốc repo bằng Python của môi trường Lab:**

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

Kết quả thực tế: `Tín hiệu hoàn thành: Đã tải 24 bài báo`. Lệnh làm sạch độc lập trong Guide cũng in `Clean thành công 24 dòng`. Trên máy Windows hiện tại, repo cần chạy qua ổ ánh xạ `X:\` do đường dẫn gốc quá dài cho import phụ thuộc.

## 5. Quyết định kỹ thuật và lỗi đã xử lý

- **Quyết định nguồn:** dùng danh sách 24 DOI đã kiểm thay cho top 24 của một truy vấn tìm kiếm động. Cách này giúp cùng bài báo khi chạy lại, bao phủ chủ đề P-065 và giữ test set ổn định. Đổi lại phải cập nhật manifest có chủ đích khi muốn thay bài.
- **Lỗi làm sạch:** ba abstract SAE chứa thẻ HTML được mã hóa. Nếu xóa thẻ trước khi giải mã entity, thẻ còn sót lại trong summary. Đã đổi thứ tự thành giải mã entity → xóa thẻ → chuẩn hóa khoảng trắng; kiểm tra lại không còn thẻ trong raw records hay clean embedding text.
- **Giới hạn nguồn:** xếp hạng Scopus Q chưa được xác minh; không gắn nhãn Q cho các bài. Freshness là số theo ngày chạy, cần đo lại khi demo.

## 6. Phần Minh tự hoàn thiện trước khi nộp

- **Hiểu luồng end-to-end:** tự giải thích raw → clean → quality → index → test set → corruption → repair và vì sao cùng test set phải dùng cho ba trạng thái.
- **Phân tích kết quả:** điền `retrieval_hit_rate`, `mean_token_f1`, judge scores, GX/freshness cho baseline/corrupted/repaired sau khi nhóm chạy thực tế; chưa có số liệu thì không kết luận tác động hay phục hồi.
- **Bài học cá nhân:** tự viết ba điều học được, một quyết định mình hiểu rõ, điều khác kỳ vọng và hướng cải thiện có thể đo.
- **Cam kết:** tự rà soát phần đóng góp, giải thích được code, xác nhận commit và điền ngày ký. Chưa đánh dấu các cam kết thay Minh.

| Metric/signal | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| `retrieval_hit_rate` | Chưa chạy | Chưa chạy | Chưa chạy |
| `mean_token_f1` | Chưa chạy | Chưa chạy | Chưa chạy |
| `judge_accuracy` / `mean_judge_score` | Chưa chạy | Chưa chạy | Chưa chạy |
| GX quality / freshness | Chưa chạy GX | Chưa chạy | Chưa chạy |

**Ninh Quang Minh xác nhận nội dung sau khi tự rà soát:** _chưa ký_.
