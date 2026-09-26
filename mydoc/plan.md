# KẾ HOẠCH THỰC THI CHI TIẾT (ACTION PLAN)
## Vai trò: THÀNH VIÊN 2 — DATA FOUNDATION & RECOVERY OWNER (Kỹ sư Dữ liệu)

> **Sứ mệnh:** Xây dựng tầng móng dữ liệu sạch, đảm bảo Data Lineage, cơ chế Dual-Mode Ingestion (Offline Fallback), bộ kịch bản phá hủy dữ liệu (Data Corruption) và cơ chế tự phục hồi bất biến (Idempotent Data Repair).

---

## 1. DANG SÁCH FILE SỞ HỮU & PHẠM VI TRÁCH NHIỆM

### File Mã Nguồn (Source Code):
- `src/ingestion/crossref.py` — Module Thu thập Dữ liệu & Offline Fallback Rescue.
- `src/ingestion/cleaning.py` — Module Tiền xử lý & Chuẩn hóa Dữ liệu Embedding.
- `src/ingestion/corruption.py` — Module Tiêm 6 Lỗi Dữ liệu & Tự Phục Hồi Idempotent.

### File Artifacts Đầu Ra:
- `data/raw/crossref_response.json` (Snapshot API phản hồi gốc)
- `data/raw/crossref_records.json` (Danh sách bài báo raw dạng JSON)
- `data/clean/papers_clean.csv` & `data/clean/papers_clean.json` (Dữ liệu sạch sau tiền xử lý)
- `data/clean/papers_clean_corrupted.csv` & `data/clean/papers_clean_corrupted.json` (Dữ liệu sau khi tiêm lỗi)
- `data/clean/papers_clean_repaired.csv` & `data/clean/papers_clean_repaired.json` (Dữ liệu sau khi phục hồi)
- `data/results/corruption_log.json` (Nhật ký tiêm lỗi chi tiết)

---

## 2. KẾ HOẠCH TIẾN ĐỘ THỰC THI CHI TIẾT (TIMELINE)

### 📌 GIAI ĐOẠN 1: INGESTION & DUAL-MODE RESCUE (Phút 0 – 30) — [✅ ĐÃ HOÀN THÀNH]
- [x] **Trích xuất thông tin bài báo**: Hoàn thiện `parse_crossref_payload()` bóc tách DOI (`paper_id`), `title`, lọc sạch thẻ HTML/XML `<jats:p>` trong `summary`, trích xuất danh sách `authors` và chuẩn hóa ngày tháng ISO 8601 (`YYYY-MM-DD`).
- [x] **Cơ chế Cứu hộ Offline (Dual-Mode)**: Viết `fetch_source_records()` tự động chuyển sang đọc snapshot mẫu `data/raw/crossref_response.json` khi API Crossref gặp sự cố (mã 429/503) hoặc phòng lab mất mạng.
- [x] **Lưu trữ Raw Records**: Viết `load_raw_records()` và xuất 2 file raw artifacts `crossref_response.json` và `crossref_records.json`.

---

### 📌 GIAI ĐOẠN 2: DATA CLEANING & PRE-EMBED MODELING (Phút 30 – 65) — [✅ ĐÃ HOÀN THÀNH]
- [x] **Khử trùng lặp**: Lọc trùng lặp bản ghi theo khóa duy nhất `paper_id` và loại bỏ dòng không hợp lệ.
- [x] **Tính toán Độ Tươi (Freshness)**: Tính toán `age_days = (run_date - published).days`.
- [x] **Tạo Chuỗi Nội Dung Tổng Hợp (`text_for_embedding`)**: Tạo định dạng chuẩn 5 dòng cho Vector DB:
  ```text
  Title: <Tiêu đề>
  Authors: <Danh sách tác giả>
  Published: <Ngày xuất bản>
  Categories: <Chuyên ngành>
  Summary: <Tóm tắt nội dung>
  ```
- [x] **Tạo Cột Phụ Trợ**: Bổ sung `authors_joined`, `categories_joined`, `summary_chars`.
- [x] **Xuất Dữ Liệu Sạch**: Đã khởi tạo thành công 24 bản ghi tại `data/clean/papers_clean.json` và `data/clean/papers_clean.csv`.

---

### 📌 GIAI ĐOẠN 3: SYNTHETIC DATA CORRUPTION SUITE (Phút 65 – 120) — [⏳ ĐANG THỰC HIỆN]
Triển khai module `src/ingestion/corruption.py` để giả lập 6 kịch bản sự cố dữ liệu bẩn sản xuất:

1. **Kịch bản 1 — Drop latest records**: Xóa bỏ 20% bản ghi mới nhất (để đo lường sự suy giảm Freshness SLA).
2. **Kịch bản 2 — Blank summary**: Xóa rỗng trường `summary` ở một số dòng đại diện.
3. **Kịch bản 3 — Inject noise**: Chèn ký tự rác/chuỗi vô nghĩa vào `summary`.
4. **Kịch bản 4 — Truncate title**: Cắt ngắn `title` xuống `< 8` ký tự.
5. **Kịch bản 5 — Stale date**: Lùi ngày xuất bản `published` về 365 ngày trước.
6. **Kịch bản 6 — Duplicate rows**: Nhân đôi một số dòng để kiểm tra tính duy nhất.

- **Ghi nhật ký tiêm lỗi**: Xuất file log chi tiết `data/results/corruption_log.json` lưu thông tin dòng bị ảnh hưởng và loại lỗi đã tiêm.

---

### 📌 GIAI ĐOẠN 4: IDEMPOTENT DATA REPAIR LOGIC (Phút 120 – 165) — [🎯 CHƯA THỰC HIỆN]
Triển khai logic tự phục hồi dữ liệu trong `src/ingestion/corruption.py`:
- **Nguyên lý Phục hồi Bất biến (Idempotent Repair)**:
  1. Không tự sửa thủ công từng dòng lỗi.
  2. Nạp lại toàn bộ dữ liệu gốc từ `data/raw/crossref_records.json` (tầng Data Lineage preserved).
  3. Chạy lại toàn bộ pipeline tiền xử lý `build_clean_dataframe()`.
  4. Xuất dữ liệu phục hồi ra `data/clean/papers_clean_repaired.csv` và `data/clean/papers_clean_repaired.json`.
  5. Đảm bảo chạy $N$ lần vẫn trả về đúng 1 kết quả sạch 100% (Tính Idempotent).

---

### 📌 GIAI ĐOẠN 5: BÁO CÁO CÁ NHÂN & HỖ TRỢ DEMO (Phút 165 – 240) — [🎯 CHƯA THỰC HIỆN]
- **Báo cáo Kỹ thuật Cá nhân**: Viết file `report/<MSSV>_HoTen.md` trình bày:
  - Kiến trúc Data Lineage và nguyên lý bảo tồn raw record.
  - Cơ chế Dual-Mode Ingestion (Offline Fallback).
  - Phân tích 6 kịch bản tiêm lỗi & Nguyên lý Idempotent Repair.
- **Hỗ trợ Live Demo**: Phối hợp cùng Trưởng nhóm (Thành viên 1) trình diễn kịch bản khôi phục tự động trên bảng khi có sự cố dữ liệu bẩn.

---

## 3. BỘ LỆNH TỰ KIỂM TRA ĐỘC LẬP (SELF-VERIFICATION COMMANDS)

Thực thi các câu lệnh sau trong terminal để kiểm chứng từng công đoạn:

```powershell
# 1. Kiểm tra Ingestion
.\.venv\Scripts\python.exe -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"

# 2. Kiểm tra Cleaning
.\.venv\Scripts\python.exe -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"

# 3. Kiểm tra Corruption
.\.venv\Scripts\python.exe -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```

---

## 4. GIAO ƯỚC DỮ LIỆU (DATA CONTRACT FREEZE)

Thành viên 2 cam kết tuân thủ Data Contract đã chốt với cả nhóm:
- `paper_id` (str): DOI chuẩn hóa.
- `title` (str): Tiêu đề chuẩn hóa.
- `summary` (str): Tóm tắt nội dung không chứa HTML/XML rác.
- `authors_joined` (str): Danh sách tác giả phân cách bằng phẩy.
- `categories_joined` (str): Danh sách chuyên ngành phân cách bằng phẩy.
- `published` (str): Định dạng `YYYY-MM-DD`.
- `age_days` (int): Số ngày kể từ ngày xuất bản.
- `text_for_embedding` (str): Chuỗi 5 dòng phục vụ Vector DB.
