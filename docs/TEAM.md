# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** ILV
- **Mã Nhóm / Lớp:** K4-L3A-DAY10
- **Tên Repository Nộp Bài:** https://github.com/dwcsnh/K4-L3A-Day10-ILV

---

## # Thành viên

| STT | Họ và tên | MSSV | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|
| 1 | Đào Đức Anh | 2A202602567 | **Đội trưởng** / Phụ trách Ingestion & Làm sạch dữ liệu (`src/ingestion/crossref.py`, `src/ingestion/cleaning.py`) | `report/2A202602567_DaoDucAnh.md` |
| 2 | Nguyễn Thọ Đạt | 2A202602484 | Phụ trách Pha 3: Vector Indexing & ChromaDB (`src/retrieval/index.py`, embedding & semantic search) | `report/2A202602484_NguyenThoDat.md` |
| 3 | Cao Văn Trường | 2A202602562 | Phụ trách Observability (`src/observability/quality.py`, `src/observability/reporting.py`, Great Expectations 1.x & Freshness SLA) | `report/2A202602562_CaoVanTruong.md` |
| 4 | Trần Thu Phương | 2A202602366 | Phụ trách Pha 3: Benchmark Test Set (`src/evaluation/testset.py`, 5 dạng câu hỏi kiểm thử) | `report/2A202602366_TranThuPhuong.md` |
| 5 | Nguyễn Quốc Tuấn | 2A202602910 | Phụ trách Tích hợp Pipeline & Interactive Dashboard (`core/`, `pipelines/`, `corruption.py`, `run_dashboard.py`) | `report/2A202602910_NguyenQuocTuan.md` |

---

## # Cá nhân

### ## 1. Đào Đức Anh — 2A202602567
- **Vai trò:** Đội trưởng, Phụ trách Data Ingestion & Data Preparation.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref API với cơ chế Dual-Mode (Live API & Offline Snapshot Fallback) trong `src/ingestion/crossref.py`.
  - Chuẩn hóa schema, tính toán trường `age_days` và ghép chuỗi 5 thành phần `text_for_embedding` trong `src/ingestion/cleaning.py`.
  - Đảm bảo 24 tài liệu khoa học được làm sạch và lưu trữ chuẩn xác tại `data/clean/papers_clean.csv` và `.json`.
- **Đóng góp chính / Bài học:**
  - Nắm vững kiến trúc Dual-Mode Ingestion đảm bảo tính bền vững (resilience) cho hệ thống khi kết nối API ngoài bị gián đoạn.

### ## 2. Nguyễn Thọ Đạt — 2A202602484
- **Vai trò:** Phụ trách Pha 3 — Vector Database & Indexing.
- **Công việc chi tiết đã hoàn thành:**
  - Hiện thực hóa `LocalEmbeddingIndex` với mô hình nhúng `sentence-transformers/all-MiniLM-L6-v2` trong `src/retrieval/index.py`.
  - Thiết lập và quản lý 3 vector collection riêng biệt trong ChromaDB: `papers-baseline`, `papers-corrupted`, và `papers-repaired`.
  - Tối ưu hóa hàm `semantic_search()` và `lookup()` phục vụ truy xuất tài liệu chính xác cho QA Agent.
- **Đóng góp chính / Bài học:**
  - Hiểu rõ cơ chế lưu trữ vector đa collection và cách ly không gian biểu diễn để so sánh khách quan giữa dữ liệu sạch và dữ liệu bị ô nhiễm.

### ## 3. Cao Văn Trường — 2A202602562
- **Vai trò:** Phụ trách Data Observability & Quality Assurance.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng Quality Gate tự động theo chuẩn **Great Expectations 1.x** (Ephemeral Batch API) với 4 quy tắc kiểm tra tính toàn vẹn trong `src/observability/quality.py`.
  - Thiết lập cơ chế giám sát Freshness SLA (&le; 180 ngày, ngưỡng tối đa 25% bài báo quá hạn).
  - Tự động phát hiện vi phạm khi tiêm lỗi dữ liệu và xuất báo cáo chất lượng trong `src/observability/reporting.py`.
- **Đóng góp chính / Bài học:**
  - Làm chủ Fluent API mới của Great Expectations 1.x và hiểu sâu sắc tầm quan trọng của Data Quality Gate trước khi dữ liệu đi vào Vector Store.

### ## 4. Trần Thu Phương — 2A202602366
- **Vai trò:** Phụ trách Benchmark Test Set & Ground Truth Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module sinh bộ câu hỏi đánh giá chuẩn trong `src/evaluation/testset.py`.
  - Định nghĩa 5 dạng câu hỏi kiểm thử đại diện: `summary`, `authors`, `date`, `category`, và `multi_hop`.
  - Gán nhãn Ground Truth và liên kết doc IDs chuẩn xác cho từng câu hỏi, lưu trữ tại `data/eval/test_set.json`.
- **Đóng góp chính / Bài học:**
  - Hiểu cách thiết kế tập dữ liệu benchmark đa chiều để đánh giá toàn diện năng lực trích xuất và trả lời của hệ thống RAG.

### ## 5. Nguyễn Quốc Tuấn — 2A202602910
- **Vai trò:** Tích hợp Pipeline, Tiêm Lỗi & Xây dựng Demo Dashboard.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng cấu hình hệ sinh thái trong `src/core/config.py` và orchestration trong `src/pipelines/phase1.py` & `src/pipelines/corruption_flow.py`.
  - Hiện thực bộ 6 kịch bản tiêm lỗi thực tế trong `src/ingestion/corruption.py` để chứng minh Silent Failure và cơ chế Idempotent Repair khôi phục 100%.
  - Thiết kế Interactive Demo Dashboard tại `script/run_dashboard.py` phục vụ bảo vệ đồ án (Bonus B1 +5đ).
- **Đóng góp chính / Bài học:**
  - Nắm vững tính chất Idempotency trong Data Engineering và cách trực quan hóa sự suy giảm chất lượng dữ liệu.
