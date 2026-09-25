# Fixtures — dữ liệu mẫu để làm việc song song

Các file trong thư mục này là **artifact mẫu đúng contract** (schema/format) mà pipeline sẽ sinh ra.
Mục đích: mỗi thành viên tự kiểm thử module của mình **mà không cần chờ PR của người khác**.

| File | Sinh bởi (module thật) | Dùng bởi |
|---|---|---|
| `papers_clean.json` | `ingestion/cleaning.py` (Member 2) | Member 3 (corruption), Member 4 (quality, testset), retrieval |
| `papers_clean_corrupted.json` | `ingestion/corruption.py` (Member 3) | Member 4 (quality trên data lỗi) |
| `test_set.json` | `evaluation/testset.py` (Member 4) | retrieval / evaluation |
| `*_metrics.json` | `evaluation/metrics.py` | Member 3 (reporting) |
| `*_quality_report.json`, `freshness_report.json` | `observability/quality.py` (Member 4) | Member 3 (reporting) |

Quy tắc:
- **Không sửa** file trong `data/fixtures/` trong PR cá nhân (tránh conflict). Cần đổi contract → báo trưởng nhóm.
- Pipeline thật (`script/run_phase1.py`, `script/run_corruption_flow.py`) **không** đọc fixtures; chúng chỉ dùng cho test độc lập.
