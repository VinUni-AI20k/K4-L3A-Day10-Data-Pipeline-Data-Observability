# Báo Cáo Đối Chiếu Định Lượng 3 Trạng Thái (Corruption & Repair Report)
*Generated at: 2026-09-25 10:19:22 UTC*

## 1. Bảng So Sánh Đối Đầu (Head-to-Head Comparison)

| Tiêu chí Đánh giá | Baseline (Dữ liệu Sạch) | Corrupted (Dữ liệu Tiêm Lỗi) | Repaired (Sau Phục Hồi) |
| :--- | :---: | :---: | :---: |
| **Data Quality Gate (GX 1.x)** | **`PASS`** | **`FAIL`** | **`PASS`** |
| **Freshness SLA (Stale %)** | `0.0%` | `52.38%` | `0.0%` |
| **Retrieval Hit Rate** | **`100.0%`** | **`60.0%`** | **`100.0%`** |
| **Mean Token F1** | **`0.5000`** | **`0.1000`** | **`0.5000`** |
| **Judge Accuracy** | **`60.0%`** | **`20.0%`** | **`60.0%`** |

---

## 2. Phân Tích Hiện Tượng Silent Failure & Sự Suy Giảm
- **Sự cố dữ liệu bẩn:** Khi tiêm các lỗi thường gặp (drop latest records, blank summary, inject noise, truncate title, stale date, duplicate rows), hệ thống RAG không báo lỗi crash hệ thống (no runtime errors) nhưng chất lượng câu trả lời bị suy giảm nghiêm trọng (**Silent Failure**).
- **Suy giảm Retrieval Hit Rate:** Từ `100.0%` sụt giảm xuống `60.0%` (chênh lệch `40.0%`).
- **Suy giảm Token F1:** Từ `0.5000` sụt giảm xuống `0.1000`.
- **Phát hiện bởi Quality Gate:** Cổng Great Expectations 1.x đã báo `FAIL`. Bộ dữ liệu lỗi được index trong collection riêng chỉ để đo ảnh hưởng; luồng production phải dừng trước bước index khi gate thất bại.

---

## 3. Đánh Giá Khả Năng Phục Hồi (Idempotent Recovery)
- **Cơ chế phục hồi:** Áp dụng phương thức phục hồi Idempotent Repair bằng cách nạp lại dữ liệu gốc từ bản lưu trữ thô (`data/raw/`), làm sạch lại toàn bộ trường dữ liệu và purge triệt để vector lỗi trong ChromaDB.
- **Kết quả phục hồi:**
  - Quality Gate chuyển từ `FAIL` trở lại **`PASS`**.
  - Retrieval Hit Rate phục hồi từ `60.0%` lên **`100.0%`**.
  - Token F1 phục hồi từ `0.1000` lên **`0.5000`**.
- **Kết luận:** Các chỉ số sau phục hồi được đối chiếu trực tiếp với baseline trên cùng bộ câu hỏi. Hit Rate: `100.0%` so với `100.0%`; Token F1: `0.5000` so với `0.5000`.
