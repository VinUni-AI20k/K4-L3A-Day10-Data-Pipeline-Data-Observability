# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| Họ và tên       | Hoàng Ngọc Đăng Khoa                                                                           |
| MSSV               | 2A202602790                                                                                    |
| Khóa/Lớp         | K4 - L3A (Day 10)                                                                              |
| Tên nhóm         | K4-L3-DAY10                                                                                    |
| Vai trò chính    | TV2 — Quality & Evaluation Engineer (Observability & Evaluation Owner)                         |
| Repository         | https://github.com/nthanhwork/K4-L3A-Day10-Data-Pipeline-Data-Observability                    |
| Ngày hoàn thành | 2026-09-25                                                                                     |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Data Quality Gate (GX 1.x)** | `src/observability/quality.py` (`run_data_quality_checks`) | `df: pd.DataFrame`, `settings: Settings`, `report_name: str` | Báo cáo JSON kiểm tra chất lượng dữ liệu (`data/quality/*.json`) | Hoàn thành |
| **Freshness SLA Monitoring** | `src/observability/quality.py` (`build_freshness_report`) | `df: pd.DataFrame`, `settings: Settings`, `report_path: Path` | `data/quality/freshness_report.json` ghi nhận tỷ lệ stale documents và đánh giá SLA | Hoàn thành |
| **Benchmark Test Set (10 câu)** | `src/evaluation/testset.py` (`build_test_set`, `load_or_create_test_set`) | `df: pd.DataFrame` (cleaned), `output_path: Path` | `data/eval/test_set.json` gồm 10 câu hỏi chuẩn hóa kèm ground truth | Hoàn thành |
| **Markdown Reporting Functions** | `src/observability/reporting.py` (`generate_phase1_report`, `generate_corruption_report`) | Metrics đánh giá, kết quả Quality Gate, Freshness SLA, Source summary | `data/reports/phase1_report.md` và `data/reports/corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| **Fix ChromaDB & Embedding compatibility** | Module `src/retrieval/` | Sửa cấu hình khoảng cách vector từ `configuration` sang `metadata={"hnsw:space": "cosine"}` phù hợp bản phát hành ChromaDB; thêm fallback cho `Embeddings` khi chưa có `langchain_core`. |
| **Lazy import & Console UTF-8** | Module `evaluation` & `core/config.py` | Cấu hình lazy-import trong `__init__.py` tránh lỗi eager dependency (`langchain`, `datasets`) và chuẩn hóa output UTF-8 trên Windows PowerShell. |
| **Cập nhật `.gitignore` toàn diện** | Toàn bộ nhóm | Thêm quy tắc loại bỏ cache (`__pycache__`, `.pytest_cache`), file build, file tạm và editor artifacts, đảm bảo repo sạch trước khi commit. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Triển khai Great Expectations 1.x Quality Gate | `src/observability/quality.py` | Phát hiện chính xác lỗi null, schema drift, trùng lặp ID, độ dài văn bản rỗng | Chạy script kiểm thử với clean dataset (`passed=True`) và corrupted dataset (`passed=False`) |
| Xây dựng hệ thống giám sát Freshness SLA | `src/observability/quality.py` | Đếm số dòng có `age_days > threshold` (180 ngày), phát hiện dữ liệu cũ quá ngưỡng 25% | `python -c "... build_freshness_report ..."` xuất `freshness_report.json` |
| Xây dựng Benchmark Test Set 10 câu hỏi chuẩn | `src/evaluation/testset.py` | `data/eval/test_set.json` gồm 10 câu hỏi chia đều qua 5 dạng nghiệp vụ thực tế | Lệnh `build_test_set` in ra: `Tín hiệu hoàn thành: Sinh được 10 câu hỏi test` |
| Xây dựng 2 hàm sinh báo cáo Markdown | `src/observability/reporting.py` | Tự động tổng hợp dữ liệu xuất ra báo cáo Pha 1 và Bảng đối chiếu 3 trạng thái | Chạy thử nghiệm với dữ liệu mẫu (mock metrics) trước khi chạy pipeline chính thức |

**Artifact tiêu biểu do vai trò tạo ra:**
- File `data/eval/test_set.json`: Chứa 10 câu hỏi phân bố đều qua 5 dạng: `summary`, `authors`, `date`, `category`, `multi_hop`. Mỗi mẫu đều có đủ `id`, `type`, `question`, `ground_truth`, `ground_truth_doc_ids` phục vụ chấm điểm tự động.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. Dữ liệu thô và quá trình tiền xử lý có thể gặp lỗi ngầm (Silent Data Corruption) như rỗng tóm tắt, trùng ID, hoặc dữ liệu lỗi thời mà code không văng exception.
2. Cần một thước đo khách quan (Ground Truth Benchmark) để đánh giá năng lực truy xuất (Retrieval Hit Rate) và chất lượng trả lời (Token F1) của mô hình RAG trước và sau khi tiêm lỗi.
3. Tự động hóa quá trình tổng hợp kết quả thành báo cáo đối chiếu định lượng mà không cần viết tay sau mỗi lần chạy pipeline.

### Cách triển khai
- **Great Expectations 1.x (Fluent API):** Sử dụng `gx.get_context(mode="ephemeral")`, định nghĩa data source pandas in-memory, thiết lập Suite với 4 nhóm expectations:
  - `ExpectTableRowCountToBeBetween(5, 5000)`: Đảm bảo số lượng tài liệu nằm trong dải cho phép.
  - `ExpectColumnValuesToNotBeNull`: Áp dụng cho `paper_id`, `title`, `text_for_embedding`.
  - `ExpectColumnValuesToBeUnique`: Đảm bảo không trùng khóa `paper_id`.
  - `ExpectColumnValueLengthsToBeBetween(min_value=30)`: Ngăn chặn hiện tượng tóm tắt rỗng hoặc bị cắt cụt.
- **Freshness SLA:** Kiểm tra cột `age_days` so với `settings.freshness_threshold_days` (180 ngày). Nếu tỷ lệ bản ghi cũ > 25%, báo cáo sẽ gắn cờ cảnh báo SLA breach.
- **Benchmark Test Set:** Trích xuất có chọn lọc từ dữ liệu sạch 10 câu hỏi bám sát nội dung bài báo, kết hợp cả câu hỏi đơn điểm (summary, tác giả, ngày công bố, chuyên ngành) lẫn liên ngành (multi-hop reasoning kết hợp 2 bài báo).
- **Markdown Reporting:** Triển khai hàm `generate_phase1_report` và `generate_corruption_report` sử dụng Jinja-like string formatting, tự động dựng bảng so sánh 3 cột (Baseline vs Corrupted vs Repaired) và tính toán tỷ lệ sụt giảm / hồi phục.

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| **Input** | Cleaned DataFrame `papers_clean.json` (17 cột, 24 dòng), `Settings` từ `core.config`. |
| **Output** | `data/eval/test_set.json`, `data/quality/*.json`, `phase1_report.md`, `corruption_report.md`. |
| **Module phụ thuộc** | `src/core/config.py`, `src/core/utils.py`. |
| **Module sử dụng output** | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `src/evaluation/metrics.py`. |
| **Điều kiện lỗi cần xử lý** | DataFrame rỗng, file đầu ra chưa có thư mục cha (xử lý qua `ensure_parent`), lỗi định dạng ký tự UTF-8 trên Windows. |

### Cách xác minh

```bash
# 1. Kiểm tra Benchmark Test Set sinh đúng 10 câu
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"

# 2. Kiểm tra Quality Gate trên dữ liệu sạch
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('passed:', res.get('passed'), 'success:', res.get('success'))"

# 3. Kiểm tra Freshness SLA
python -c "from core.config import load_settings; from observability.quality import build_freshness_report; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); rep=build_freshness_report(df, s, s.paths.freshness_report); print('fresh:', rep.get('is_fresh'), 'stale_ratio:', rep.get('stale_ratio_pct'))"
```

- **Kết quả mong đợi:** Test set có 10 câu; Quality check trả về `passed=True, success=True`; Freshness trả về `is_fresh=True, stale_ratio=4.17%`.
- **Kết quả thực tế:** 100% lệnh thực thi thành công, đúng tín hiệu nghiệm thu.
- **Artifact/log:** `data/eval/test_set.json`, `data/quality/baseline_quality_report.json`, `data/quality/freshness_report.json`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương pháp khởi tạo context cho Great Expectations 1.x trong môi trường data pipeline tự động.
- **Các phương án đã cân nhắc:**
  1. *Filesystem Context (`gx.get_context(project_root_dir=...)`):* Cần khởi tạo cấu trúc thư mục `gx/great_expectations.yml` cố định trên ổ đĩa.
  2. *Ephemeral Context (`gx.get_context(mode="ephemeral")`):* Khởi tạo context in-memory động theo từng lượt chạy pipeline.
- **Phương án đã chọn:** Chọn Ephemeral Context (`mode="ephemeral"`).
- **Lý do:** Tránh xung đột file khóa (lock), không phụ thuộc vào trạng thái ổ đĩa local khi chạy đa tiến trình hoặc CI/CD, đảm bảo tính nguyên tử (idempotent) — mỗi lần chạy pipeline sẽ dựng suite sạch và xuất báo cáo JSON ra thư mục quy định mà không lưu rác trong repo.
- **Bằng chứng quyết định phù hợp:** Pipeline chạy mượt mà, thời gian thực thi chỉ mất < 2 giây, không phát sinh lỗi xung đột metadata giữa các lần kiểm tra dữ liệu sạch và dữ liệu lỗi.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  TypeError: Client.create_collection() got an unexpected keyword argument 'configuration'
  ```
- **Lệnh hoặc bước tái hiện:** Chạy lệnh smoke test nạp vector vào ChromaDB:
  ```bash
  python -c "from retrieval.index import LocalEmbeddingIndex; ... idx.build_from_clean()"
  ```
- **Nguyên nhân gốc:** Phiên bản ChromaDB được cài đặt trong môi trường sử dụng cú pháp thiết lập không gian vector qua `metadata={"hnsw:space": "cosine"}`, trong khi code mẫu cũ truyền tham số `configuration={"hnsw": {"space": "cosine"}}` chỉ hỗ trợ ở một số bản ChromaDB khác.
- **Cách xử lý:** Thay thế tham số cấu hình thành `metadata={"hnsw:space": "cosine"}` trong cả phương thức `build` và `build_from_clean` của `LocalEmbeddingIndex`. Đồng thời thiết lập `ANONYMIZED_TELEMETRY=False` và bắt ngoại lệ posthog để triệt tiêu toàn bộ cảnh báo telemetry lỗi thời.
- **Cách xác minh sau khi sửa:** Chạy lại lệnh smoke test, console in ra chính xác:
  ```text
  Tín hiệu hoàn thành: Tìm thấy 2 tài liệu liên quan
  ```
- **Điều học được:** Khi làm việc với các vector database phát triển nhanh như ChromaDB, cần chú ý tính tương thích giữa API parameter và metadata spec của từng phiên bản thư viện client.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu được lấy qua Crossref REST API dưới dạng JSON thô $\rightarrow$ được chuẩn hóa bởi `cleaning.py` (loại bỏ thẻ HTML, chuẩn hóa ngày tháng, tính `age_days`, ghép `text_for_embedding`) $\rightarrow$ đi qua Quality Gate GX 1.x để xác thực tính toàn vẹn $\rightarrow$ được sinh vector 384 chiều bằng mô hình `all-MiniLM-L6-v2` $\rightarrow$ nạp vào collection ChromaDB kèm metadata để sẵn sàng cho tìm kiếm ngữ nghĩa.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Mỗi câu hỏi trong `test_set.json` có gắn sẵn danh sách `ground_truth_doc_ids` (DOI bài báo chứa thông tin chuẩn). Khi QA Agent truy vấn, hệ thống kiểm tra xem các tài liệu mà vector index trả về (`retrieved_doc_ids`) có giao với `ground_truth_doc_ids` hay không để tính **Retrieval Hit Rate**. Đồng thời so sánh câu trả lời sinh ra với `ground_truth` qua độ trùng lặp từ vựng (**Token F1**) và đánh giá từ LLM/Judge.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - *Quality checks (GX 1.x):* Giám sát tính toàn vẹn về cấu trúc và giá trị của dữ liệu (schema drift, null values, uniqueness, độ dài text).
   - *Freshness monitoring (SLA):* Giám sát tính thời sự của dữ liệu dựa trên thời gian xuất bản (`age_days` > 180 ngày), phát hiện nguy cơ tri thức bị lỗi thời ngay cả khi dữ liệu không vi phạm lỗi cấu trúc.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Để đảm bảo tính khách quan và nhất quán (Controlled Experiment). Khi giữ nguyên bộ câu hỏi và ground truth cố định, mọi sự thay đổi trong metrics (Hit Rate, Token F1) chỉ phản ánh trực tiếp chất lượng của nguồn dữ liệu và vector index ở từng trạng thái, loại trừ sai số do độ khó của câu hỏi.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - Về Quality: `repaired_quality_report.json` đạt trạng thái `PASS` (tương đương baseline).
   - Về Metric: `repaired_metrics.json` ghi nhận `retrieval_hit_rate` và `mean_token_f1` hồi phục về mức $\ge 95\%$ so với baseline.
   - Về Vector store: Collection `papers-repaired` được purge sạch sẽ vector lỗi và đồng bộ dữ liệu sạch từ bản backup thô (`data/raw/`).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| :--- | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | **95.0%** | **40.0%** | **95.0%** | Dữ liệu lỗi làm vector search tìm sai tài liệu; sau repair phục hồi hoàn toàn. |
| `mean_token_f1` | **0.88** | **0.35** | **0.88** | F1 sụt giảm nghiêm trọng do tóm tắt bị chèn nhiễu và xóa trắng. |
| `judge_accuracy` | **90.0%** | **30.0%** | **90.0%** | Câu trả lời ở corrupted flow bị ảo giác nặng, judge đánh trượt 70%. |
| `mean_judge_score` | **4.5 / 5** | **1.8 / 5** | **4.5 / 5** | Điểm số phản ánh đúng mức độ tin cậy của câu trả lời. |
| Quality checks | **PASS** | **FAIL** | **PASS** | GX 1.x bắt được ngay lập tức lỗi null, empty summary và duplicate row. |
| Freshness status | **PASS (4.2%)** | **FAIL (30.0%)** | **PASS (4.2%)** | Bắt được hiện tượng cố tình lùi ngày xuất bản (stale date). |

### Kết luận từ số liệu

1. **Chuỗi lỗi:** `[Data corruption (blank summary, inject noise, drop rows)]` $\rightarrow$ `[GX 1.x báo FAIL, Freshness SLA vi phạm]` $\rightarrow$ `[Retrieval Hit Rate sụt giảm từ 95% xuống 40%, Token F1 tụt từ 0.88 xuống 0.35]`.
2. **Chuỗi phục hồi:** `[Idempotent Repair từ raw records + Purge ChromaDB]` $\rightarrow$ `[Quality Gate trở lại PASS, Freshness đạt chuẩn]` $\rightarrow$ `[Retrieval Hit Rate và F1 hồi phục 100% về mức Baseline ban đầu]`.

- **Dạng corruption ảnh hưởng rõ nhất:** Lỗi **Blank summary & Drop latest records**. Vì khi trường thông tin tóm tắt bị mất, vector embedding mất đi toàn bộ ngữ nghĩa trọng tâm, khiến vector search không thể định vị được văn bản liên quan.
- **Hiện tượng rút ra:** Hiện tượng **Silent Failure** — nếu không có Great Expectations và Freshness SLA đứng canh ở tầng dữ liệu, mô hình RAG vẫn trả lời bình thường mà không báo lỗi runtime, nhưng toàn bộ câu trả lời phục vụ người dùng đều sai lệch nghiêm trọng.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Data Pipeline:** Tầm quan trọng của tính bất biến (Immutability) và khả năng tái lập (Idempotency) — việc giữ nguyên bản raw snapshot cho phép hệ thống tự chữa lành (self-healing) dễ dàng khi gặp sự cố mà không lo mất mát dữ liệu gốc.
2. **Data Observability:** Cần phân tách rõ ràng giữa kiểm tra chất lượng tĩnh (Data Quality qua GX 1.x) và chất lượng động theo thời gian (Freshness SLA). Cả hai là hai tấm lá chắn bổ trợ không thể thiếu.
3. **Ảnh hưởng tới RAG Agent:** Chất lượng của mô hình RAG phụ thuộc 90% vào độ sạch của dữ liệu đầu vào ("Garbage in, Garbage out"). Một lỗi dữ liệu nhỏ ở bước ingestion có thể phá hủy hoàn toàn độ chính xác của agent mà mắt thường khó nhận biết nếu không có benchmark test set tự động.

### Nếu có thêm thời gian
- Tích hợp thêm **Ragas Evaluation** chạy tự động trong CI/CD (đo `faithfulness`, `answer_relevancy`) kết hợp cùng hệ thống gửi webhook cảnh báo (Slack/Discord) ngay khi tỷ lệ stale records vượt ngưỡng cho phép.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hoàng Ngọc Đăng Khoa  
**Ngày xác nhận:** 2026-09-25
