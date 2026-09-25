# Pipeline Observatory — UI demo

Dashboard tiếng Việt đọc trực tiếp artifacts trong `data/`, không cần cài thư viện frontend hay dùng CDN. Server giao diện chỉ dùng Python standard library.

## Khởi động

Tại thư mục gốc của repo, dùng Python 3.11–3.13:

```powershell
python script/run_ui.py
```

Nếu đã có virtualenv hoạt động:

```powershell
.\.venv\Scripts\python.exe script/run_ui.py
```

Mở http://127.0.0.1:8765. Có thể đổi cổng bằng `--port 8888`. Dừng server bằng Ctrl+C.

## Kịch bản trình bày

1. Chọn các bước trên sơ đồ để giải thích hành trình Crossref → cleaning → quality → ChromaDB → đánh giá → tiêm lỗi → phục hồi.
2. Tại **Bên trong corpus**, xem raw snapshot, tìm kiếm bài báo và bấm tiêu đề để xem tóm tắt cùng JSON.
3. Bấm **Chạy baseline**. UI gọi `script/run_phase1.py` bằng cùng Python chạy server, cập nhật log và artifacts mỗi 3 giây.
4. Khi baseline hoàn tất, bấm **Tiêm lỗi & phục hồi** để gọi `script/run_corruption_flow.py`.
5. Chuyển Baseline / Corrupted / Repaired để xem dữ liệu và quality report; biểu đồ benchmark luôn đối chiếu cả ba trạng thái.
6. Chọn nguồn **Trạng thái đang chọn** trong bảng dữ liệu để kiểm tra từng dataset.

## Điều kiện và ý nghĩa kết quả

- Chỉ xem UI/raw snapshot: không cần API key hoặc dependencies của pipeline.
- Chạy pipeline thực: cần cài dependencies theo README, cấu hình `.env`, và kết nối mạng/model cache theo pipeline hiện có. Thao tác này ghi artifacts, có thể tải model hoặc gọi API tính phí theo cấu hình của nhóm.
- Nếu `.venv` không khởi động được vì Python gốc đã đổi vị trí, tạo lại virtualenv với Python 3.11–3.13 đang hoạt động và cài `python -m pip install -e .` trước khi chạy pipeline.
- Chưa có artifact: UI hiển thị `—` hoặc “Chưa có dữ liệu”; không tạo số liệu giả. File JSON bị lỗi có cảnh báo đọc file.
- Snapshot raw là dữ liệu sẵn có của repo, không phải dữ liệu vừa lấy trực tiếp từ Crossref.
- Chỉ số và freshness là kết quả của lần chạy đã lưu, không được tính lại theo thời gian mở UI. Các file có thể thuộc các lần chạy khác nhau; UI không coi chúng là một giao dịch nguyên tử.
- Mã pipeline lab vẫn lập chỉ mục khi Quality Gate thất bại để đo suy giảm. Trạng thái thực thi “Hoàn tất” chỉ có nghĩa script kết thúc với exit code 0, không đồng nghĩa chất lượng PASS.
- Nút chạy khóa trong lúc một job do UI khởi tạo đang chạy. Không chạy thêm pipeline từ terminal đồng thời. Log UI giữ tối đa 600 dòng và không tồn tại sau khi khởi động lại server.
- Server chỉ lắng nghe trên localhost, chỉ phục vụ các assets được cho phép và yêu cầu token phiên cho lệnh chạy. Không triển khai server này trực tiếp lên Internet.

## Kiểm tra

```powershell
python -m unittest discover -s script -p test_ui.py
node --check ui/app.js
```

Bài kiểm tra dùng mock cho lệnh chạy, không gọi LLM hoặc sửa dữ liệu pipeline.
