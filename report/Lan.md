# Báo cáo cá nhân - Lan

- **Họ và tên:** Lan
- **Vai trò:** Corruption Suite & Testing
- **Checkpoint phụ trách:** CP4, Bonus B3

## Công việc chi tiết đã hoàn thành:
1. **`src/ingestion/corruption.py` (CP4):** 
   - Triển khai hàm `corrupt_clean_dataframe` với seed cố định `random.Random(42)`.
   - Implement đầy đủ 6 loại lỗi data corruption: Drop latest records, Blank summary, Inject noise, Truncate title, Stale date, Duplicate rows.
   - Rebuild lại `text_for_embedding` cho dữ liệu bẩn và xuất log ra `corruption_log.json`.
   - Đảm bảo tính idempotent: chạy 2 lần ra cùng 1 kết quả (không sửa `df` gốc).
2. **`tests/` (Bonus B3):** 
   - Viết toàn bộ test suite với `pytest` cho dự án.
   - Cấu hình `conftest.py` độc lập, đọc từ `data/raw/crossref_records.json` để không phụ thuộc vào tiến độ của đồng đội.
   - Viết test cho CP0, CP1, CP2, CP4 đảm bảo độ phủ code tốt (đặc biệt là 12 test case hoàn hảo cho `corruption.py`).
   - Cấu hình file `pyproject.toml` và tạo script `script/run_tests.py` để chạy test bằng 1 lệnh.

## Điều học được / Đóng góp chính:
- Hiểu rõ bản chất của Data Observability: dữ liệu có thể bị rác (Silent Data Corruption) theo nhiều cách tinh vi mà code không báo lỗi (runtime error).
- Thực hành viết Unit Test chuyên nghiệp với `pytest` và chia sẻ fixtures qua `conftest.py`.
- Học cách cô lập môi trường test, tự tạo DataFrame mock từ file raw khi phần code trước đó (cleaning) chưa hoàn thành.
