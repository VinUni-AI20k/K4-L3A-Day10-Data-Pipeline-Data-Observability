# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                              |
| ------------------ | ------------------------------------- |
| Họ và tên       | Chử Trần Phương Nam                  |
| MSSV               | 2A202602675                           |
| Khóa/Lớp         | K4-L3-DAY10                          |
| Tên nhóm         | GOHOME                     |
| Vai trò chính    | Trưởng nhóm & Pipeline Integrator    |
| Repository         | https://github.com/Nam-phuong624/K4-L3A-Day10-Data-Pipeline-Data-Observability        |
| Ngày hoàn thành | 2026-09-25                            |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable        | File/hàm phụ trách                           | Input nhận vào                   | Output bàn giao                            | Trạng thái   |
| ------------------------- | --------------------------------------------- | --------------------------------- | ------------------------------------------- | ------------ |
| Config & utils            | `core/config.py`, `core/utils.py`            | `.env`, `settings.yaml`          | `Settings` object, I/O helpers             | Hoàn thành   |
| Phase 1 orchestration     | `src/pipelines/phase1.py`                    | raw records, settings             | `baseline_metrics.json`, `phase1_report.md` | Hoàn thành   |
| Corruption flow           | `src/pipelines/corruption_flow.py`           | baseline artifacts                | `corruption_report.md`, 3-state metrics    | Hoàn thành   |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                   | Thành viên/module được hỗ trợ | Kết quả                                              |
| ---------------------------- | ------------------------------------ | ------------------------------------------------------ |
| Tích hợp signature mới      | reporting.py (Đạt)                   | `generate_corruption_report` nhận đủ baseline params  |
| Kiểm tra end-to-end pipeline | Tất cả module                         | Cả 2 scripts chạy exit code 0                         |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                          | File/hàm/artifact liên quan              | Kết quả bàn giao                       | Cách xác minh                        |
| ----------------------------------------------- | ----------------------------------------- | --------------------------------------- | ------------------------------------ |
| Kết nối 7 bước Phase 1                         | `src/pipelines/phase1.py`                | `data/reports/phase1_report.md`        | `python script/run_phase1.py`        |
| Kết nối luồng Corrupt→Eval→Repair→Compare      | `src/pipelines/corruption_flow.py`       | `data/reports/corruption_report.md`    | `python script/run_corruption_flow.py` |
| Guard kiểm tra baseline artifacts trước khi chạy | `corruption_flow.py` (dòng 25-28)        | RuntimeError nếu thiếu baseline        | Xóa baseline rồi chạy lại           |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Kết nối toàn bộ các module độc lập (ingestion, cleaning, embedding, evaluation, observability) thành 2 luồng thực thi có thứ tự rõ ràng, đảm bảo artifacts được sinh ra đúng vị trí và đúng thứ tự phụ thuộc.

### Cách triển khai

- `phase1.py`: 7 bước tuần tự — load → clean → save CSV/JSON → build ChromaDB → testset → evaluate → quality+freshness. Mỗi bước in progress và kết quả key để dễ debug.
- `corruption_flow.py`: Guard check baseline tồn tại trước khi tiếp tục. Load baseline metrics/quality/freshness, chạy corrupt→eval→quality, sau đó repair→eval→quality, cuối cùng gọi `generate_corruption_report` với đủ 10 params.
- Settings được load 1 lần từ `core/config.py`, truyền qua tất cả module để paths nhất quán.

### Input, output và contract

| Thành phần           | Mô tả                                                              |
| -------------------- | ------------------------------------------------------------------- |
| Input                | `data/raw/crossref_records.json`, `.env`                          |
| Output               | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` |
| Module phụ thuộc    | Tất cả module trong `src/`                                         |
| Module sử dụng output | Không có (đây là entrypoint cuối cùng)                             |
| Điều kiện lỗi       | Thiếu baseline artifacts → RuntimeError với hướng dẫn rõ ràng    |

### Cách xác minh

```bash
conda run -n vin python script/run_phase1.py
conda run -n vin python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả 2 chạy exit code 0, in kết quả metrics cuối.
- **Kết quả thực tế:** Phase 1: hit_rate=1.0, token_f1=1.0, GX=True, is_fresh=True. Corruption flow: 3-state comparison in ra console.
- **Artifact/log:** `data/reports/phase1_report.md`, `data/reports/corruption_report.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Corruption flow cần hiển thị dữ liệu baseline trong bảng so sánh 3 trạng thái, nhưng ban đầu `generate_corruption_report` không nhận baseline quality/freshness.
- **Các phương án đã cân nhắc:** (1) Đọc lại file baseline bên trong `generate_corruption_report`. (2) Load ở `corruption_flow.py` và truyền vào.
- **Phương án đã chọn:** Load ở orchestrator (`corruption_flow.py`) và truyền vào function.
- **Lý do:** Orchestrator là nơi quyết định artifacts nào được đọc — function reporting chỉ nên nhận data, không tự đọc file.
- **Bằng chứng:** Bảng Data Quality trong `corruption_report.md` hiển thị đầy đủ cả 3 trạng thái với số liệu thật.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `generate_corruption_report` nhận `baseline_quality` nhưng function không có param đó → `TypeError: unexpected keyword argument`.
- **Nguyên nhân gốc:** Signature function chỉ có 8 params (thiếu `baseline_quality` và `baseline_freshness`), trong khi caller truyền 10.
- **Cách xử lý:** Thêm 2 params mới vào signature, cập nhật bảng Data Quality để render đầy đủ 3 dòng từ dữ liệu thật.
- **Cách xác minh:** `python script/run_corruption_flow.py` → bảng hiển thị ✅/❌ đúng cho cả 3 trạng thái.
- **Điều học được:** Khi thêm data flow mới vào orchestrator, luôn kiểm tra signature của các function nhận data đó.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** Fetch API (hoặc load từ file) → parse thành `PaperRecord` → `build_clean_dataframe` tạo `text_for_embedding` → `LocalEmbeddingIndex.build` encode bằng MiniLM → lưu vào ChromaDB collection.
2. **Evaluation set:** 10 câu hỏi được sinh từ data thực tế, mỗi câu có `paper_id` là ground-truth. Khi evaluate, retrieval lấy top-k docs → hit = ground-truth paper_id có trong kết quả.
3. **Quality checks vs Freshness:** GX checks tính hợp lệ cấu trúc dữ liệu (null, unique, length). Freshness checks xem dữ liệu có còn mới không dựa trên `published` date (threshold 180 ngày, stale ratio > 25% → is_fresh=False).
4. **Cùng test set:** Dùng cùng test set đảm bảo thay đổi metrics phản ánh đúng tác động của data corruption/repair, không phải do câu hỏi khác nhau.
5. **Repair thành công khi:** `repaired_metrics.json` có `retrieval_hit_rate` ≥ baseline, GX `success=True`, `is_fresh=True`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét                                         |
| ---------------------- | -------: | --------: | -------: | ------------------------------------------------- |
| `retrieval_hit_rate`  |   1.0000 |    0.8000 |   1.0000 | Corruption làm mất 20% retrieval accuracy        |
| `mean_token_f1`       |   1.0000 |    0.5882 | 1.0000   | Token F1 giảm mạnh do blank summary + noise      |
| `judge_accuracy`      |   1.0000 |    0.6000 |   1.0000 | 40% câu hỏi bị trả lời sai sau corruption        |
| `mean_judge_score`    |        5 |    3.2000 |        5 | Score trung bình giảm từ 5 xuống 3.2             |
| Quality checks         |     Pass |      Fail |     Pass | GX phát hiện duplicate + blank summary           |
| Freshness status       |     True |     False |     True | 7/23 records stale (30.4%) → vượt ngưỡng 25%   |

### Kết luận từ số liệu

1. Corruption (blank_summary + inject_noise + duplicate_rows) → GX `success=False`, stale_ratio=30.4% → `retrieval_hit_rate` giảm từ 1.0 xuống 0.8, `mean_token_f1` giảm từ 1.0 xuống 0.59.
2. Repair từ raw snapshot → GX `success=True`, `is_fresh=True` → cả hai metrics phục hồi hoàn toàn về 1.0.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Idempotent Pipeline:** Repair từ raw snapshot đảm bảo reproducibility — chạy lại nhiều lần vẫn cho kết quả như nhau.
2. **Orchestrator pattern:** Tách biệt logic nghiệp vụ (các module) khỏi luồng thực thi (pipeline) giúp test và debug từng phần độc lập.
3. **Silent Failure là nguy hiểm nhất:** Pipeline chạy không lỗi nhưng metrics giảm 40% — không có Quality Gate thì không ai biết.

### Nếu có thêm thời gian

Thêm checksum verification cho raw snapshot trước khi repair, đảm bảo file `crossref_records.json` không bị thay đổi so với lúc ban đầu.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Chử Trần Phương Nam
**Ngày xác nhận:** 2026-09-25
