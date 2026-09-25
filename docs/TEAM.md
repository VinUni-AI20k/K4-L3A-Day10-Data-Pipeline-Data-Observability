# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `SVSoppi`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-SVSoppi-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | GitHub | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Hoàng Trung Hiếu | 2A202602945 | `hoangtrunghieu0025-lab` | Trưởng nhóm / Pipeline Integrator (`phase1.py`, `corruption_flow.py`, `common.py`, `reporting.py`) | `report/2A202602945_HoangTrungHieu.md` |
| 2 | Ngô Kỳ Anh | 2A202602916 | `glacerjust` | Data Foundation (`crossref.py`, `cleaning.py`, raw data) | `report/2A202602916_NgoKyAnh.md` |
| 3 | Nguyễn Văn Tài | 2A202603004 | `Tai Nguyen Van` | Corruption & Vector Store (`corruption.py`, Chroma smoke test) | `report/2A202603004_NguyenVanTai.md` |
| 4 | Nguyễn Việt Hoàng Hải | 2A202602967 | `nguyenviethoanghai` | Observability & Evaluation (`quality.py` GX 1.x, `testset.py`) | `report/2A202602967_NguyenVietHoangHai.md` |

---

## # Cá nhân

### ## HoangTrungHieu-2A202602945
- **Vai trò:** Trưởng nhóm & Điều phối Pipeline.
- **Công việc chi tiết đã hoàn thành:**
  - Chốt data contract (schema clean dataframe) cho cả nhóm và điều phối merge qua Pull Request (#2, #4, #5).
  - Viết `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` và `src/pipelines/common.py`: quality gate chặn index khi fail, test set cố định cho 3 trạng thái, repair từ raw kèm kiểm chứng idempotent (24/24 dòng khớp baseline).
  - Viết `src/observability/reporting.py`: `phase1_report.md` và bảng đối chiếu 3 trạng thái trong `corruption_report.md`.
  - Chạy tích hợp end-to-end; phát hiện và sửa 2 lỗi tích hợp: lệch khóa `checks`/`results` giữa `quality.py` và `reporting.py`; Crossref thiếu `subject` làm 2 câu `categories` có ground truth rỗng.
  - Viết `report/group_report.md`.
- **Điều học được / Đóng góp chính:**
  - Idempotent repair nghĩa là dựng lại từ nguồn raw, không vá dữ liệu hỏng; và phải kiểm chứng bằng cách so với baseline, không chỉ nhìn metric.
  - Quality gate chỉ bắt được lỗi mà nó có expectation tương ứng: `drop_latest_records` và `inject_noise` lọt qua GX dù làm hit rate giảm 0.40.

### ## NgoKyAnh-2A202602916
- **Vai trò:** Phụ trách Ingestion & Làm sạch dữ liệu.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng `src/ingestion/crossref.py`: gọi Crossref API, fallback về snapshot `crossref_response.json` khi lỗi mạng/HTTP, bỏ thẻ JATS, lưu 2 raw artifact (PR #1).
  - Xây dựng `src/ingestion/cleaning.py`: tính `age_days`, `authors_joined`/`categories_joined`, ghép `text_for_embedding` 5 phần, khử trùng theo `paper_id`.
  - Lấy dữ liệu mới từ API (24 bài, xuất bản 2026-04-01 → 2026-09-15).
- **Điều học được / Đóng góp chính:**
  - [Tự điền]

### ## NguyenVanTai-2A202603004
- **Vai trò:** Phụ trách Corruption Suite & Vector Store.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng `src/ingestion/corruption.py` với 6 loại lỗi có `seed` cố định, ghi `corruption_log.json` chi tiết (paper_id bị tác động, giá trị trước/sau).
  - Dựng lại `text_for_embedding` và `age_days` sau khi tiêm lỗi để lỗi lan tới tầng embedding.
  - Viết `script/smoke_test_chroma.py` kiểm tra nạp dữ liệu vào ChromaDB.
- **Điều học được / Đóng góp chính:**
  - [Tự điền]

### ## NguyenVietHoangHai-2A202602967
- **Vai trò:** Phụ trách Data Observability & Benchmark Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng Quality Gate theo chuẩn **Great Expectations 1.x** (ephemeral context, `add_pandas`) với 8 expectation trong `src/observability/quality.py` (PR #3).
  - Xây dựng Freshness SLA: stale khi hơn 25% bài có `age_days > 180`; ghi report vào `data/quality/`.
  - Xây dựng `src/evaluation/testset.py`: 10 câu hỏi cho 4 loại `summary`/`authors`/`date`/`categories`.
- **Điều học được / Đóng góp chính:**
  - [Tự điền]
