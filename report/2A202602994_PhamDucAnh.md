# Báo cáo cá nhân — Data Observability & Dashboard

- **Họ và tên:** Phạm Đức Anh
- **MSSV:** 2A202602994
- **Vai trò:** Data Observability + Dashboard
- **Nhánh làm việc:** `feature/data-observability-dashboard`

## 1. Phạm vi phụ trách

Tôi phụ trách xây dựng Data Quality Gate bằng Great Expectations 1.x, giám sát Freshness SLA và dashboard trực quan cho pipeline RAG.

Các file chính:

- `src/observability/quality.py`
- `dashboard/app.py`
- `data/quality/baseline_quality_report.json`
- `data/quality/freshness_report.json`

## 2. Quality Gate

Quality Gate sử dụng ephemeral context và Pandas datasource theo API Great Expectations 1.x. Bộ kiểm tra gồm:

1. Số bản ghi nằm trong khoảng 5–5000.
2. `paper_id`, `title`, `text_for_embedding` không được null.
3. `paper_id` phải duy nhất.
4. `summary` phải dài tối thiểu 30 ký tự.

Kết quả baseline trên 24 bài báo:

| Chỉ số | Kết quả |
|---|---:|
| Số expectation | 6 |
| Số expectation đạt | 6 |
| Tỷ lệ thành công | 100% |
| Quality Gate | PASS |

Kiểm thử đối chứng với dữ liệu lỗi đã phát hiện đúng title null, `paper_id` trùng và summary quá ngắn.

## 3. Freshness SLA

- Ngưỡng stale: `age_days > 180`.
- Dataset bị cảnh báo nếu tỷ lệ stale lớn hơn 25%.
- Report gồm ngày xuất bản mới nhất/cũ nhất, số bản ghi stale, tỷ lệ stale và cờ `is_fresh`.

Kết quả baseline:

| Chỉ số | Kết quả |
|---|---:|
| Tổng bản ghi | 24 |
| Bản ghi stale | 0 |
| Tỷ lệ stale | 0% |
| Freshness SLA | PASS |

## 4. Dashboard

Dashboard Streamlit hỗ trợ:

- Chọn trạng thái Baseline, Corrupted hoặc Repaired nếu artifact tương ứng tồn tại.
- Chạy lại Quality Gate trực tiếp từ giao diện.
- Hiển thị trạng thái PASS/FAIL, tổng bản ghi, số expectation đạt và tỷ lệ stale.
- Hiển thị chi tiết từng expectation.
- Hiển thị ngày mới nhất/cũ nhất và biểu đồ phân bố `age_days`.
- Xem dữ liệu mẫu để phục vụ demo.

Lệnh chạy:

```bash
streamlit run dashboard/app.py
```

## 5. Kiểm thử

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); print(run_data_quality_checks(df, s, 'baseline')['success'])"
```

Kết quả mong đợi: `True`.

## 6. Kết luận

Phần Data Observability đã chặn được các lỗi dữ liệu quan trọng trước khi dữ liệu được đưa vào vector store. Freshness SLA giúp phát hiện dữ liệu quá hạn, còn dashboard hỗ trợ nhóm quan sát và trình bày trạng thái pipeline trực quan.
