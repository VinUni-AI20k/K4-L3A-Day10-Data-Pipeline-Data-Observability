# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** GOHOME
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-GOHOME-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Chử Trần Phương Nam | `2A202602675` | | Trưởng nhóm / Pipeline Integrator (`core/`, `phase1.py`, `corruption_flow.py`) | `report/2A202602675_ChuTranPhuongNam.md` |
| 2 | Ngụy Khắc Phi Long | `2A202602532` | | Data Foundation & Recovery (`crossref.py`, `cleaning.py`, raw data, idempotent repair) | `report/2A202602532_NguyKhacPhiLong.md` |
| 3 | Nguyễn Đức Phát | `2A202602753` | | RAG & Vector Index (`retrieval/index.py`, `embeddings.py`, ChromaDB) | `report/2A202602753_NguyenDucPhat.md` |
| 4 | Đỗ Thành Đạt | `2A202602874` | | Observability & Evaluation (`quality.py` GX 1.x, `testset.py`, `reporting.py`) | `report/2A202602874_DoThanhDat.md` |

---

## # Cá nhân

### Chử Trần Phương Nam — 2A202602675

- **Vai trò:** Trưởng nhóm & Điều phối Pipeline.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập cấu hình hệ thống `core/config.py` và đường dẫn artifacts `core/utils.py`.
  - Kết nối luồng thực thi end-to-end trong `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`.
  - Kiểm tra tính nhất quán của các artifacts qua 3 trạng thái và theo dõi Contributor tracking trên GitHub nhánh `main`.
- **Điều học được / Đóng góp chính:**
  - Hiểu sâu sắc về thiết kế Idempotent Pipeline và quản lý trạng thái luồng dữ liệu đa tầng.

### Ngụy Khắc Phi Long — 2A202602532

- **Vai trò:** Phụ trách Ingestion, Làm sạch & Phục hồi dữ liệu.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref API với cơ chế retry (429/503) và fallback offline trong `src/ingestion/crossref.py`.
  - Chuẩn hóa schema, tính toán trường `age_days`, `summary_chars` và `text_for_embedding` trong `src/ingestion/cleaning.py`.
  - Thiết kế 6 dạng corruption (`corruption.py`) và thực thi cơ chế Idempotent Repair phục hồi dữ liệu từ raw snapshot.
- **Điều học được / Đóng góp chính:**
  - Kỹ thuật truy vết nguồn gốc dữ liệu (Data Lineage) và bảo toàn raw snapshot trước khi biến đổi.

### Nguyễn Đức Phát — 2A202602753

- **Vai trò:** Phụ trách RAG, Vector Database & Embedding.
- **Công việc chi tiết đã hoàn thành:**
  - Quản lý mô hình embedding `sentence-transformers/all-MiniLM-L6-v2` trong `src/retrieval/embeddings.py`.
  - Nạp và quản lý 3 collection riêng biệt trong ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`) qua `src/retrieval/index.py`.
  - Xây dựng QA Agent truy vấn ngữ cảnh và trả lời câu hỏi trong `src/retrieval/qa.py`.
- **Điều học được / Đóng góp chính:**
  - Cách cô lập các không gian vector để so sánh khách quan giữa dữ liệu sạch và dữ liệu bị lỗi.

### Đỗ Thành Đạt — 2A202602874

- **Vai trò:** Phụ trách Data Observability & Benchmark Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Quality Gate theo chuẩn mới **Great Expectations 1.x** (6 expectations, ephemeral context) và giám sát Freshness SLA trong `src/observability/quality.py`.
  - Xây dựng bộ 10 câu hỏi đánh giá chuẩn (3 loại) trong `src/evaluation/testset.py`.
  - Đo lường `hit_rate`, `token_f1`, `judge_accuracy` và xuất bảng đối chiếu 3 trạng thái vào `data/reports/corruption_report.md` qua `src/observability/reporting.py`.
- **Điều học được / Đóng góp chính:**
  - Cách thiết lập hệ thống cảnh báo sớm (Quality Gate) chặn đứng hiện tượng Silent Failure trước khi dữ liệu vào serving layer.
