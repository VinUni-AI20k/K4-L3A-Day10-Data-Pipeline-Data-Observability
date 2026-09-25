# Báo Cáo Đối Chiếu 3 Trạng Thái: Baseline vs Corrupted vs Repaired

> **Mục tiêu:** Chứng minh hiện tượng Silent Failure khi RAG gặp dữ liệu bẩn và năng lực tự phục hồi an toàn (Idempotent Repair) từ nguồn Raw.

---

## 1. Bảng So Sánh Hiệu Năng Tổng Hợp (3 Trạng Thái)

| Tiêu chí đánh giá | 🟢 Baseline (Sạch) | 🔴 Corrupted (Bị tiêm lỗi) | 🔵 Repaired (Sau phục hồi) | Biến thiên (Corrupt $\to$ Repair) |
| :--- | :---: | :---: | :---: | :---: |
| **Data Quality Gate (GX 1.x)** | **PASS** | **`FAIL (ALARM)`** | **`PASS`** | Phát hiện & Phục hồi |
| **Freshness SLA (> 180 ngày)** | **PASS** | **`FAIL (STALE)`** | **`PASS`** | Phục hồi độ tươi |
| **Retrieval Hit Rate** | **100.00%** | **70.00%** | **100.00%** | $\uparrow$ +30.0% |
| **Mean Token F1** | **1.0000** | **0.9000** | **1.0000** | $\uparrow$ +0.1000 |
| **Judge Accuracy** | **100.00%** | **90.00%** | **100.00%** | $\uparrow$ +10.0% |
| **Judge Score (Thang 5)** | **5.00 / 5.0** | **4.60 / 5.0** | **5.00 / 5.0** | $\uparrow$ +0.40 |

---

## 2. Phân Tích Hiện Tượng "Silent Failure" (Dữ Liệu Bị Tiêm Lỗi)

Khi tiêm 6 kịch bản lỗi thực tế (bỏ rơi 20% bản ghi mới, xóa trắng summary, chèn noise ký tự, cắt ngắn tiêu đề, làm cũ ngày xuất bản, nhân đôi dòng trùng lặp):
1. **Agent không dừng chương trình:** RAG Agent vẫn trả lời câu hỏi của người dùng một cách trôi chảy, không phát sinh bất kỳ ngoại lệ runtime crash nào.
2. **Sự sụp đổ chỉ số ngầm:** Điểm Retrieval Hit Rate và Mean Token F1 bị sụt giảm nghiêm trọng từ **100.00%** xuống **70.00%**, dẫn đến hiện tượng Hallucination (ảo giác thông tin) ở quy mô diện rộng.
3. **Vai trò cảnh báo của Data Quality Gate:** Great Expectations 1.x đã lập tức gióng chuông báo động (`FAIL (ALARM)`) khi dữ liệu vi phạm các chốt chặn chất lượng (độ dài summary, tính duy nhất của ID, không rỗng).

---

## 3. Cơ Chế Phục Hồi An Toàn (Idempotent Repair)

- **Nguyên tắc bảo toàn nguồn gốc (Data Lineage):** Pipeline kích hoạt quy trình tự phục hồi bằng cách đọc lại trực tiếp từ snapshot bản thô nguyên gốc `data/raw/crossref_records.json`.
- **Tính Idempotent:** Tái áp dụng logic làm sạch chuẩn hóa, tính lại `age_days`, tạo mới không gian nhúng vector mà không để lại bất kỳ vector rác ("ghost vectors") nào.
- **Kết quả nghiệm thu:** Sau khi phục hồi, toàn bộ chỉ số Retrieval Hit Rate (100.00%) và Token F1 (1.0000) lấy lại 100% phong độ tương đương trạng thái Baseline ban đầu, đồng thời Data Quality Gate quay trở về trạng thái **PASS**.
