# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên nhóm:** `1Prompt4All`
- **Mã nhóm / lớp:** `K4-L3-DAY10`
- **Repository:** [K4-L3A-Day10-Data-Pipeline-Data-Observability](https://github.com/D3vNguy3n/K4-L3A-Day10-Data-Pipeline-Data-Observability)

## Thành viên và phân công

| STT | Họ và tên | MSSV | Email | Vai trò chính | Phạm vi sở hữu | Output bàn giao | Báo cáo cá nhân |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Nguyễn Hoàng Lê Nguyên | `2A202602472` | Chưa cung cấp | Trưởng nhóm / Pipeline Integrator | `src/core/`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, hai entrypoint | Pipeline chạy end-to-end, metrics và báo cáo ba trạng thái | `report/2A202602472_NguyenHoangLeNguyen.md` |
| 2 | Giang Thế Vũ | `2A202602478` | Chưa cung cấp | Data Foundation & Recovery | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, raw/clean schema và repair từ raw | Raw records, clean dataset, data lineage và dữ liệu repaired | `report/2A202602478_GiangTheVu.md` |
| 3 | Trần Đức Lộc | `2A202602431` | Chưa cung cấp | RAG & Vector Index | `src/retrieval/`, MiniLM embeddings và ChromaDB | Ba vector collections, semantic search và QA retrieval | `report/2A202602431_TranDucLoc.md` |
| 4 | Đặng Hữu Cương | `2A202602572` | Chưa cung cấp | Observability & Evaluation | `src/observability/`, `src/evaluation/`, quality/freshness artifacts | GX quality gate, benchmark test set, metrics và Markdown reports | `report/2A202602572_DangHuuCuong.md` |

## Chi tiết trách nhiệm cá nhân

### Nguyễn Hoàng Lê Nguyên — 2A202602472

- Điều phối contract chung giữa raw data, clean dataframe, vector index, evaluation và reporting.
- Quản lý cấu hình đường dẫn artifact trong `src/core/config.py`.
- Kết nối baseline flow trong `src/pipelines/phase1.py`.
- Kết nối corruption → evaluate → repair → compare trong `src/pipelines/corruption_flow.py`.
- Chạy nghiệm thu hai entrypoint, kiểm tra artifact contract và tính idempotent của repair.
- Tổng hợp số liệu kỹ thuật vào báo cáo nhóm và hỗ trợ tích hợp các module.

### Giang Thế Vũ — 2A202602478

- Parse Crossref payload thành `PaperRecord`, chuẩn hóa DOI, title, abstract, authors, categories và publication date.
- Triển khai live API retry/backoff và offline fallback từ snapshot.
- Xây dựng clean dataframe, tính `age_days`, tạo `text_for_embedding` và deduplicate theo `paper_id`.
- Bảo toàn raw lineage để repair luôn tái tạo từ nguồn sạch, không sửa trực tiếp corrupted data.
- Xác minh 24 raw records tạo thành 24 clean records có DOI duy nhất.

### Trần Đức Lộc — 2A202602431

- Quản lý embedding model `sentence-transformers/all-MiniLM-L6-v2`.
- Xây dựng và nạp ba Chroma collections độc lập: `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- Triển khai semantic search, exact lookup và QA extraction.
- Bảo đảm rebuild collection không làm phát sinh segment mồ côi qua các lần chạy lặp.
- Xác minh mỗi collection có 24 documents và smoke test trả đúng số lượng kết quả.

### Đặng Hữu Cương — 2A202602572

- Xây dựng benchmark 10 câu thuộc bốn loại `summary`, `authors`, `date`, `categories`.
- Triển khai bốn loại expectation bắt buộc bằng Great Expectations 1.x.
- Giám sát freshness theo ngưỡng 180 ngày và tỷ lệ stale tối đa 25%.
- Tính retrieval hit rate, token F1, judge metrics và quản lý answer artifacts.
- Sinh `phase1_report.md` và `corruption_report.md`, đối chiếu baseline/corrupted/repaired.

## Contract phối hợp

| Bàn giao | Owner | Người nhận | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| Raw records | Giang Thế Vũ | Nguyễn Hoàng Lê Nguyên | 24 records, parse được offline |
| Clean dataframe | Giang Thế Vũ | Trần Đức Lộc, Đặng Hữu Cương | DOI unique, đủ embedding text, quality pass |
| Chroma index/search | Trần Đức Lộc | Nguyễn Hoàng Lê Nguyên, Đặng Hữu Cương | 3 collections, mỗi collection 24 docs |
| Test set và quality signals | Đặng Hữu Cương | Nguyễn Hoàng Lê Nguyên | 10 câu cố định, baseline pass/corrupted fail |
| End-to-end artifacts | Nguyễn Hoàng Lê Nguyên | Cả nhóm | Hai entrypoint exit code 0, repair phục hồi metrics |

## Kết quả nghiệm thu chung

| Trạng thái | Retrieval hit rate | Mean token F1 | Quality gate | Freshness |
| --- | ---: | ---: | --- | --- |
| Baseline | 1.000 | 1.000 | PASSED | PASSED |
| Corrupted | 0.000 | 0.007 | FAILED | FAILED |
| Repaired | 1.000 | 1.000 | PASSED | PASSED |

> Mỗi thành viên cần tự rà soát phần được phân công, tạo báo cáo cá nhân tương ứng và có commit trên nhánh `main` trước khi nộp.
