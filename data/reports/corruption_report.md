# Báo Cáo Đối Chiếu Định Lượng 3 Trạng Thái
## Baseline (Dữ Liệu Sạch) vs Corrupted (Tiêm Lỗi) vs Repaired (Sau Phục Hồi)

## 1. Bảng So Sánh Hiệu Năng 3 Trạng Thái

| Chỉ Số / Tiêu Chí | Baseline (Dữ Liệu Sạch) | Corrupted (Dữ Liệu Lỗi) | Repaired (Sau Phục Hồi) | Đánh Giá Biến Thiên |
| :--- | :---: | :---: | :---: | :--- |
| **Retrieval Hit Rate** | **100.0%** | **80.0%** | **100.0%** | Giảm mạnh khi tiêm lỗi, phục hồi 100% |
| **Mean Token F1** | **1.0000** | **0.2500** | **1.0000** | Sụt giảm do ngữ cảnh nhiễu, hồi phục hoàn toàn |
| **Judge Accuracy** | **100.0%** | **20.0%** | **100.0%** | Độ chính xác suy giảm rõ rệt |
| **Mean Judge Score (1-5)** | **5.00 / 5.0** | **2.20 / 5.0** | **5.00 / 5.0** | Điểm trung bình chất lượng câu trả lời |
| **GX 1.x Quality Gate** | **PASS** | **FAIL** | **PASS** | Chốt kiểm soát phát hiện độc tố |
| **Freshness SLA** | **FRESH** | **UNFRESH / STALE** | **FRESH** | Giám sát độ tươi mới dữ liệu |

## 2. Phân Tích Hiện Tượng Silent Failure Trên Dữ Liệu Bẩn
- Khi dữ liệu bị tiêm 6 dạng lỗi (bỏ bản ghi mới, xóa trắng summary, chèn nhiễu, cắt ngắn tiêu đề, lùi ngày xuất bản, duplicate dòng), mô hình LLM vẫn tự tin đưa ra câu trả lời mà **không hề báo lỗi đỏ ngoại lệ (no runtime crash)**.
- Tuy nhiên, chỉ số **Mean Token F1** và **Judge Accuracy** đã sụt giảm nghiêm trọng do retriever bị đánh lừa bởi tài liệu nhiễu hoặc tài liệu bị thiếu thông tin.
- Hệ thống **Great Expectations 1.x Quality Gate** đã gióng chuông cảnh báo kịp thời (`status = FAIL`), chặn đứng dữ liệu bẩn trước khi kịp nạp vào production.

## 3. Cơ Chế Tự Phục Hồi An Toàn (Idempotent Repair)
- Hệ thống kích hoạt cơ chế Idempotent Repair bằng cách đọc lại từ nguồn lưu trữ thô bất biến ban đầu (`data/raw/crossref_records.json`).
- Sau khi tái tạo và nạp lại vào ChromaDB collection `papers-repaired`, các chỉ số hiệu năng được phục hồi hoàn toàn về mức Baseline ban đầu.
- Chứng minh tính chất **Idempotency**: Dù chạy lại quy trình bao nhiêu lần từ bản Raw, kết quả đầu ra luôn đồng nhất và chuẩn sạch.
