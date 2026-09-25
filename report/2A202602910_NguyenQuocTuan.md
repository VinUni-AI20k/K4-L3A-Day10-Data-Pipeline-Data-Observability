# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| Họ và tên | Nguyễn Quốc Tuấn |
| MSSV | 2A202602910 |
| Khóa/Lớp | K4 |
| Tên nhóm | ILV |
| Vai trò chính | Pipeline Integration, Data Corruption & Idempotent Repair, Demo Dashboard |
| Repository | K4-L3A-Day10-ILV |
| Ngày hoàn thành | 2026-09-25 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Pipeline Orchestration | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | Cấu hình `Settings`, dữ liệu từ ingestion | Toàn bộ 5 artifacts baseline và 3 báo cáo đối chiếu | Hoàn thành |
| Data Corruption Suite | `src/ingestion/corruption.py` | `papers_clean.csv/json` | Dữ liệu bị tiêm 6 lỗi `papers_clean_corrupted.csv/json` | Hoàn thành |
| Idempotent Repair | `src/pipelines/corruption_flow.py` | Raw snapshot / clean data nguồn | Vector index và dữ liệu hồi phục `papers_clean_repaired.csv` | Hoàn thành |
| Interactive UI Demo | `script/run_dashboard.py` | JSON metrics, ChromaDB collections | Dashboard UI chạy tại `http://localhost:8000` (Bonus B1) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| Sửa lỗi alias `test_set_json` | `src/core/config.py` (Hỗ trợ nhóm) | Khắc phục `AttributeError` khi chạy test lệnh nhanh của giảng viên |
| Tối ưu cache vector index | `src/retrieval/index.py` | Tăng tốc độ phản hồi Live QA xuống dưới 0.3s không cần nạp lại model |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Thực thi luồng Baseline end-to-end | `src/pipelines/phase1.py` | 5 artifacts chuẩn tại `data/` | Chạy `python script/run_phase1.py` (Exit code 0) |
| Tiêm 6 kịch bản lỗi thực tế | `src/ingestion/corruption.py` | Gây sụt giảm Token F1 từ 1.0 xuống 0.25 | Chạy `python script/run_corruption_flow.py` |
| Idempotent Repair & Đối chiếu | `src/pipelines/corruption_flow.py` | Khôi phục 100% metrics, xóa sạch Ghost Vectors | Kiểm tra `data/reports/corruption_report.md` |
| Xây dựng UI Demo kiểm thử song song | `script/run_dashboard.py` | Web Dashboard trực quan hóa 3 trạng thái | Mở trình duyệt `http://localhost:8000` |

Output tiêu biểu: Báo cáo `data/reports/corruption_report.md` chứng minh định lượng sự sụt giảm của Retrieval Hit Rate (100% -> 80% -> 100%), Token F1 (1.0 -> 0.25 -> 1.0) và cảnh báo đỏ từ chốt chặn Great Expectations 1.x.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xây dựng kiến trúc điều phối (orchestration) tích hợp toàn bộ các module riêng lẻ thành một luồng dữ liệu khép kín: từ Ingestion, Quality Gate, Vector Store, Benchmark Evaluation cho đến Tiêm lỗi có kiểm soát để bóc trần hiện tượng **Silent Failure** và thực hiện **Idempotent Repair** khôi phục hệ thống an toàn.

### Cách triển khai
- **Pipeline Orchestrator:** Kết nối các thành phần theo mô hình pipeline hướng module, kiểm soát logging chi tiết tại mỗi trạm trung chuyển dữ liệu.
- **Corruption Engine:** Thiết kế 6 hàm biến đổi mô phỏng lỗi thực tế: drop bài báo mới nhất, xóa trắng tóm tắt (`summary = ""`), tiêm nhiễu ký tự ngẫu nhiên, cắt cụt tiêu đề, làm cũ ngày xuất bản về 5 năm trước, và nhân bản dòng (`duplicate rows`).
- **Idempotency Strategy:** Khi phục hồi, xóa sạch collection ô nhiễm trong ChromaDB và tái chạy ingestion từ nguồn thay vì update chắp vá.

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| Input | Đối tượng `Settings` chứa toàn bộ đường dẫn cấu hình và ngưỡng SLA |
| Output | Bộ 3 trạng thái metrics (`baseline`, `corrupted`, `repaired`) và markdown report |
| Module phụ thuộc | `ingestion/`, `observability/`, `retrieval/`, `evaluation/` |
| Module sử dụng output | Giao diện Dashboard `script/run_dashboard.py` và báo cáo bảo vệ đồ án |
| Điều kiện lỗi cần xử lý | Ngoại lệ khi mất mạng, file raw bị hỏng, hoặc vector collection đã tồn tại |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả hai script chạy thành công với exit code 0, bảng đối chiếu 3 trạng thái hiển thị đầy đủ và mọi file kết quả được ghi vào `data/`.
- **Kết quả thực tế:** Exit code 0, 100% bài test pass, các file `corruption_report.md` và `baseline_metrics.json` được tạo hoàn chỉnh.
- **Artifact/log:** `data/reports/corruption_report.md`, `data/reports/phase1_report.md`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Trong Pha 5, khi thực hiện phục hồi dữ liệu từ trạng thái Corrupted, nhóm cần quyết định cách làm sạch bộ vector index trong ChromaDB.
- **Các phương án đã cân nhắc:**
  1. Dùng lệnh `collection.update()` hoặc `collection.upsert()` để ghi đè các bản ghi cũ.
  2. Xóa bỏ hoàn toàn collection cũ (`client.delete_collection()`) và tái lập chỉ mục toàn bộ từ nguồn dữ liệu sạch (Full Rebuild).
- **Phương án đã chọn:** Phương án 2 (Xóa bỏ và tái lập chỉ mục sạch).
- **Lý do:** Khi tiêm lỗi nhân bản dòng hoặc xóa tài liệu ở nguồn (như kịch bản Drop latest), nếu chỉ update/upsert theo ID thì các vector rác cũ (Ghost Vectors) vẫn tồn tại âm thầm trong index và tiếp tục làm sai lệch kết quả tìm kiếm. Xóa và rebuild sạch là tiêu chuẩn vàng đảm bảo tính **Idempotency** (f(f(x)) = f(x)).
- **Bằng chứng:** Ở cột Repaired, hiện tượng trả về doc ID trùng lặp biến mất 100% và Token F1 quay lại 1.0 hoàn hảo.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  AttributeError: 'Paths' object has no attribute 'test_set_json'
  TypeError: LocalEmbeddingIndex.__init__() missing 2 required positional arguments: 'documents' and 'persist_path'
  ```
- **Lệnh tái hiện:** Chạy lệnh kiểm thử nhanh của giảng viên trong slide kiểm tra môi trường.
- **Nguyên nhân gốc:** Lớp `Paths` trong `src/core/config.py` đặt tên biến là `eval_testset`, trong khi câu lệnh kiểm tra của giảng viên truy cập thuộc tính `.test_set_json`; lớp `LocalEmbeddingIndex` yêu cầu bắt buộc truyền `documents` ngay trong hàm khởi tạo `__init__`.
- **Cách xử lý:** 
  1. Thêm `@property def test_set_json(self)` trỏ về `self.eval_testset` trong `src/core/config.py`.
  2. Bổ sung giá trị mặc định cho `documents` và `persist_path` trong `src/retrieval/index.py` đồng thời cung cấp hàm `build_from_clean()`.
- **Cách xác minh sau khi sửa:** Chạy lại lệnh một dòng của giảng viên: in ra tín hiệu hoàn thành tìm thấy 2 tài liệu thành công.
- **Điều học được:** Khi phát triển hệ thống theo nhóm, cần thiết kế giao diện lập trình (API contract) mềm dẻo, hỗ trợ alias và tương thích ngược với các công cụ kiểm thử tự động bên ngoài.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index:** Dữ liệu thô từ Crossref API được lưu vào `data/raw/`, chuyển qua module cleaning để bóc tách 5 trường nội dung (Title, Authors, Summary, Categories, Year) và tính `age_days`. Chuỗi ngữ cảnh `text_for_embedding` sau khi qua chốt chặn Great Expectations sẽ được mô hình `all-MiniLM-L6-v2` nhúng thành vector 384 chiều và lưu vào ChromaDB.
2. **Evaluation set và ground-truth document IDs:** Bộ test set gồm 5 câu hỏi thuộc các chiều truy vấn khác nhau kèm ID tài liệu chuẩn (`ground_truth_doc_ids`). Khi QA Agent chạy, ta so sánh tập ID tài liệu mà vector search lấy về với ground truth để tính **Retrieval Hit Rate** và so sánh câu trả lời sinh ra với câu chuẩn để tính **Token F1**.
3. **Quality checks vs Freshness monitoring:** Quality checks kiểm tra tính hợp lệ về mặt cấu trúc và chất lượng giá trị (schema, non-null, unique ID, độ dài tóm tắt); Freshness monitoring giám sát tuổi thọ của tài liệu theo thời gian thực dựa trên SLA (&le; 180 ngày) để đảm bảo tri thức luôn mới.
4. **Vì sao phải dùng cùng test set cho cả 3 trạng thái:** Đảm bảo nguyên tắc kiểm thử có kiểm soát (Controlled Experiment). Khi câu hỏi kiểm thử không đổi, mọi sự sai lệch về Hit Rate hay Token F1 chỉ phản ánh chính xác chất lượng của nguồn dữ liệu tại trạng thái đó.
5. **Tiêu chuẩn đánh giá Repair thành công:** Dựa trên việc các chốt chặn Great Expectations chuyển từ FAIL về PASS 100%, tỷ lệ tài liệu quá hạn về mức an toàn (4.2% &le; 25%), và toàn bộ metrics đánh giá hồi phục về mức Baseline (Hit Rate 100%, Token F1 1.0000, Judge Score 5.0/5.0).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| :--- | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | 100.0% | 80.0% | 100.0% | Sụt giảm khi tiêm lỗi drop/noise, hồi phục hoàn toàn sau repair |
| `mean_token_f1` | 1.0000 | 0.2500 | 1.0000 | Sụt giảm nghiêm trọng (-75%) do lỗi Blank Summary và nhiễu |
| `judge_accuracy` | 100.0% | 20.0% | 100.0% | Agent không trả lời được các câu hỏi bị xóa tóm tắt |
| `mean_judge_score` | 5.0 / 5.0 | 1.0 / 5.0 | 5.0 / 5.0 | Điểm đánh giá chất lượng câu trả lời rơi về mức tối thiểu |
| `quality_checks` | PASS (100%) | FAIL | PASS (100%) | Bắt quả tang lỗi Duplicate Rows và Blank Summary |
| `freshness_status` | FRESH (4.2%) | UNFRESH (41.7%) | FRESH (4.2%) | Cảnh báo vi phạm SLA khi tiêm lỗi 5-year stale date |

### Kết luận từ số liệu

1. **Chuỗi nguyên nhân – bằng chứng 1:** Tiêm lỗi `blank_summary` và `duplicate_rows` $\rightarrow$ Chốt chặn Great Expectations báo FAIL (`Unique paper_id` và `Length summary &ge; 30`) $\rightarrow$ Agent sinh ra câu trả lời rỗng, Mean Token F1 sụt từ 1.0 xuống 0.25.
2. **Chuỗi nguyên nhân – bằng chứng 2:** Kích hoạt cơ chế `idempotent_repair` xóa index ô nhiễm và re-ingest từ raw snapshot $\rightarrow$ Great Expectations báo PASS và SLA về mức FRESH (4.2%) $\rightarrow$ Mean Token F1 và Retrieval Hit Rate lập tức hồi sinh về 100%.
- **Lỗi ảnh hưởng rõ nhất:** Lỗi **Blank Summary** và **Duplicate Rows**. Blank Summary khiến LLM hoàn toàn mất ngữ cảnh để trả lời (Silent Failure), trong khi Duplicate Rows gây ô nhiễm không gian vector với các Ghost Vectors trùng lặp.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Kiến trúc Data Pipeline Idempotent:** Hiểu rõ tầm quan trọng của việc thiết kế luồng dữ liệu có khả năng tái thực thi nhiều lần mà không sinh ra tác dụng phụ hay rác dữ liệu.
2. **Data Observability chặn đứng Silent Failure:** Trong AI/RAG, code không báo lỗi đỏ không có nghĩa là hệ thống đang hoạt động tốt. Cần có chốt chặn chất lượng dữ liệu (Data Quality Gate) trước khi nạp vào vector store.
3. **Đánh giá định lượng đa chiều:** Kết hợp cả chỉ số thu hồi (Hit Rate), chỉ số so khớp token (F1), và đánh giá ngữ nghĩa (LLM Judge) để có cái nhìn toàn diện về chất lượng của Agent.

### Nếu có thêm thời gian
Xây dựng cơ chế **Active Data Drift Detection** tự động phân tích độ lệch phân phối vector embedding theo thời gian (Embedding Drift) kết hợp gửi cảnh báo tức thì qua Webhook/Slack khi phát hiện dị thường dữ liệu.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Quốc Tuấn  
**Ngày xác nhận:** 2026-09-25
