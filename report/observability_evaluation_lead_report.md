# Báo Cáo Cá Nhân (Individual Role Report) — Day 10: Data Pipeline & Data Observability

> **Vai trò:** Observability & Evaluation Lead (Thành viên 4)  
> **Nhóm thực hiện:** BungChay (`K4A-L3-DAY10`)  
> **Dự án:** K4-L3A-Day10-BungChay

---

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| **Họ và tên** | [Điền Họ và Tên của bạn] |
| **MSSV** | [Điền MSSV của bạn] |
| **Khóa / Lớp** | K4A - Level 3 (Day 10) |
| **Tên nhóm** | BungChay |
| **Vai trò chính** | **Observability & Evaluation Lead** |
| **Repository** | `K4-L3A-Day10-BungChay` |
| **Ngày hoàn thành** | 2026-09-25 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu chính (Ownership)

| Module / Deliverable | File / Hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :---: |
| **Data Quality Gate** | `src/observability/quality.py`<br>`run_data_quality_checks` | Clean / Corrupted DataFrame | `baseline_quality_report.json`<br>`corrupted_quality_report.json`<br>`repaired_quality_report.json` | **Hoàn thành** |
| **Freshness SLA Monitoring** | `src/observability/quality.py`<br>`build_freshness_report` | Clean DataFrame có cột `age_days` | `freshness_report.json`<br>`is_fresh` boolean status | **Hoàn thành** |
| **Benchmark Test Set** | `src/evaluation/testset.py`<br>`build_test_set` | Clean DataFrame (24 records) | `data/eval/test_set.json`<br>(10 câu hỏi qua 4 nghiệp vụ) | **Hoàn thành** |
| **Automated Reporting** | `src/observability/reporting.py`<br>`generate_phase1_report`<br>`generate_corruption_report` | Metrics summary & Quality status | `data/reports/phase1_report.md`<br>`data/reports/corruption_report.md` | **Hoàn thành** |
| **Interactive Dashboard (Bonus B1)** | `dashboard.py`<br>`data/reports/dashboard.html` | Toàn bộ artifacts đo lường | Giao diện Streamlit & Web HTML tương tác 3 trạng thái | **Hoàn thành** |

### Việc hỗ trợ ngoài phạm vi chính
- **Hỗ trợ Pipeline Lead:** Chuẩn đoán và giải quyết dứt điểm lỗi xung đột thư viện `torch 2.2.2` và `transformers 5.x` trên macOS, giúp lệnh kiểm tra môi trường in ra `Môi trường sẵn sàng`.
- **Hỗ trợ Debug RAG Evaluation:** Xử lý an toàn trường hợp fallback trong `src/evaluation/metrics.py::_judge_answer` khi chạy chế độ `mock` LLM.

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File / Hàm / Artifact liên quan | Kết quả bàn giao | Cách xác minh thực tế |
| :--- | :--- | :--- | :--- |
| **Dựng Data Quality Gate** | `src/observability/quality.py` | 4 Expectations kiểm định dữ liệu sạch đạt `PASS`, bắt lỗi khi tiêm dữ liệu hỏng đạt `FAIL`. | `python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); print(run_data_quality_checks(df, s, 'test')['success'])"` $\to$ `True` |
| **Giám sát Freshness SLA** | `src/observability/quality.py` | Phát hiện tỷ lệ bài báo cũ `age_days > 180` (4.2% $\le$ 25%), xác nhận dữ liệu tươi mới. | `data/quality/freshness_report.json` ghi nhận `is_fresh: True`. |
| **Sinh Bộ Đề Benchmark** | `src/evaluation/testset.py` | `data/eval/test_set.json` gồm 10 câu hỏi chuẩn phủ đủ 4 nhóm (`summary`, `authors`, `date`, `categories`). | `python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(len(ts))"` $\to$ `10` |
| **Báo Cáo Đối Chiếu 3 Trạng Thái** | `src/observability/reporting.py` | `data/reports/corruption_report.md` chứa bảng đối chiếu 3 cột rõ ràng (Baseline vs Corrupted vs Repaired). | Kiểm tra file Markdown sinh ra sau khi chạy `python script/run_corruption_flow.py`. |
| **Dashboard Trực Quan (Bonus B1)** | `dashboard.py`<br>`data/reports/dashboard.html` | Ứng dụng Streamlit 5 tabs và trang HTML độc lập có biểu đồ Chart.js động. | Chạy `.venv/bin/streamlit run dashboard.py` hoặc mở trực tiếp `dashboard.html`. |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Trong hệ thống RAG phục vụ tra cứu tài liệu học thuật, dữ liệu đầu vào có thể bị lỗi âm thầm (**Silent Failure**): dữ liệu bị lỗi thời (stale), tóm tắt bị rỗng hoặc nhiễu, mã bài báo bị nhân bản. Mô hình LLM không hề báo lỗi crash mà vẫn trả lời tự tin, dẫn đến hiện tượng **Hallucination** nghiêm trọng. Vai trò của tôi là dựng **"chốt kiểm dịch dữ liệu"** tự động trước khi nạp vào Vector Database và xây dựng thước đo chuẩn để chứng minh AI suy giảm khi dữ liệu bẩn và phục hồi khi được sửa chữa.

### Cách triển khai
1. **Kiến trúc Great Expectations 1.x Ephemeral Context:**
   - Không sử dụng cú pháp cũ gây lỗi (`context.sources.pandas_default`).
   - Sử dụng `gx.get_context(mode="ephemeral")` chạy trực tiếp trên RAM, gắn kết DataFrame qua `context.data_sources.add_pandas()`, tạo asset và batch definition.
   - Định nghĩa 4 Expectations thiết yếu:
     - `gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)`: Đảm bảo số lượng bản ghi tối thiểu.
     - `gxe.ExpectColumnValuesToNotBeNull`: Đảm bảo `paper_id`, `title`, `text_for_embedding` không bị rỗng.
     - `gxe.ExpectColumnValuesToBeUnique(column="paper_id")`: Khử trùng lặp khóa chính.
     - `gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30)`: Ngăn chặn tóm tắt cụt lủn / thiếu thông tin.
2. **Freshness SLA Monitoring:**
   - Đo lường tuổi đời của từng tài liệu `age_days = (run_date - published).days`.
   - Nếu tỷ lệ bài báo cũ (`age_days > 180`) vượt ngưỡng **25%**, hệ thống lập tức gắn cờ cảnh báo `is_fresh = False`.
3. **Bộ Đề Thi Benchmark Test Set:**
   - Chọn lọc các bài báo đại diện và sinh tự động 10 câu hỏi bao phủ 4 dạng bài toán: `summary`, `authors`, `date`, `categories`.
   - Mỗi câu hỏi liên kết chặt chẽ với `ground_truth` và `ground_truth_doc_ids` phục vụ chấm Retrieval Hit Rate và Token F1.

### Input, Output và Contract Kỹ Thuật

| Thành phần | Mô tả chi tiết |
| :--- | :--- |
| **Input** | Clean DataFrame chứa các cột: `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `text_for_embedding`. |
| **Output** | `baseline_quality_report.json`, `corrupted_quality_report.json`, `freshness_report.json`, `test_set.json`, `phase1_report.md`, `corruption_report.md`. |
| **Module phụ thuộc** | `src/ingestion/cleaning.py` (nhận DataFrame sạch), `src/core/config.py` (đường dẫn `Settings.paths`). |
| **Module sử dụng output** | `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py` (sử dụng quality status để quyết định gate và reporting). |
| **Điều kiện lỗi cần xử lý** | DataFrame rỗng, trường ngày tháng không hợp lệ (NaT), các bản ghi bị xóa tóm tắt hoặc nhân bản ID. |

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn cách khởi tạo Context cho Great Expectations 1.x trong pipeline.
- **Các phương án đã cân nhắc:**
  - *Phương án 1 (File-system Context):* Tạo thư mục `gx/` trên ổ đĩa kèm cấu hình `great_expectations.yml`.
  - *Phương án 2 (Ephemeral In-Memory Context):* Khởi tạo `gx.get_context(mode="ephemeral")` chạy hoàn toàn trên RAM.
- **Phương án đã chọn:** Phương án 2 (Ephemeral Context).
- **Lý do lựa chọn:**
  - **Tốc độ thực thi:** Khởi tạo tức thì, không tốn I/O đĩa.
  - **Stateless & Tái lập (Reproducibility):** Không để lại file rác (`.gx`, checkpoints cũ) làm bẩn git repo hoặc gây xung đột môi trường giữa các máy của thành viên trong nhóm.
  - **Đúng chuẩn tài liệu bài lab:** Phù hợp chính xác với hướng dẫn kỹ thuật trong Slide Khóa 4 Trang 51-52.
- **Bằng chứng:** Hàm `run_data_quality_checks` hoàn thành kiểm định 24 bản ghi chỉ trong chưa đầy 0.3 giây, xuất thẳng báo cáo JSON gọn gàng vào thư mục `data/quality/`.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng nguyên văn:**
  ```text
  NameError: name 'nn' is not defined
  [transformers] Disabling PyTorch because PyTorch >= 2.5 is required but found 2.2.2
  ```
- **Lệnh tái hiện:**
  ```bash
  python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
  ```
- **Nguyên nhân gốc:**
  - Trên hệ điều hành macOS x86_64, gói `torch` bị neo ở bản 2.2.2. Trong khi đó, `transformers 5.17.0` và `sentence-transformers 6.1.0` yêu cầu `torch >= 2.5.0` và gọi `nn.Module` khi thiếu torch dẫn đến crash. Đồng thời `numpy 2.4.6` gây xung đột C-API với `torch 2.2.2`.
- **Cách xử lý:**
  1. Hạ cấp `numpy` về bản ổn định: `pip install "numpy<2"` (phiên bản `1.26.4`).
  2. Cài đặt các phiên bản tương thích chặt chẽ: `pip install "transformers<4.45.0"` (4.44.2) và `pip install "sentence-transformers<4.0.0"` (3.4.1).
  3. Sửa `pyproject.toml` từ `"sentence-transformers>=5.0.0"` thành `"sentence-transformers>=3.0.0"`.
- **Cách xác minh sau khi sửa:**
  ```bash
  .venv/bin/python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
  # Kết quả: Môi trường sẵn sàng
  ```
- **Điều học được:** Khi làm việc với Machine Learning / Deep Learning, sự tương thích giữa Python binary wheels, C-API của NumPy và PyTorch là yếu tố sống còn; cần ghim dải phiên bản an toàn trước khi chạy pipeline.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - Crossref REST API cung cấp metadata bài báo dạng JSON (hoặc snapshot offline fallback) $\to$ bóc tách thành các đối tượng `PaperRecord` $\to$ làm sạch XML/HTML tags $\to$ tính `age_days` $\to$ ghép thành `text_for_embedding` (Title, Authors, Published, Categories, Summary) $\to$ qua mô hình `all-MiniLM-L6-v2` chuyển thành vector dense 384 chiều $\to$ nạp vào ChromaDB collection với chỉ mục HNSW Cosine.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - Khi đưa câu hỏi vào hệ thống, bộ tìm kiếm ChromaDB trả về danh sách tài liệu (`retrieved_doc_ids`). Nếu ID của tài liệu chuẩn (`ground_truth_doc_ids`) xuất hiện trong top kết quả, ta ghi nhận **Hit Rate = 1**. Câu trả lời sinh ra sau đó được so sánh từ vựng với `ground_truth` để tính **Token F1**, và được LLM Judge chấm điểm ngữ nghĩa từ 1 đến 5.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - *Quality checks (Great Expectations):* Kiểm tra **tính toàn vẹn về cấu trúc và cú pháp dữ liệu** (schema, null, duplicate, độ dài text) tại thời điểm nạp.
   - *Freshness monitoring:* Kiểm tra **tính cập nhật theo thời gian của tri thức** (SLA tuổi đời dữ liệu), cảnh báo khi tài liệu quá hạn dù cấu trúc dữ liệu vẫn hoàn toàn đúng format.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   - Để đảm bảo tính khách quan khoa học (cùng một thước đo Ground Truth chuẩn). Chỉ khi giữ nguyên bộ đề thi, sự sụt giảm chỉ số mới phản ánh chính xác tác hại của dữ liệu bị lỗi, và sự phục hồi điểm số mới chứng minh năng lực sửa chữa của pipeline.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - *Artifact:* Quality Gate xuất file `repaired_quality_report.json` đạt `PASS`.
   - *Metric:* Retrieval Hit Rate hồi phục từ **70.00% lên 100.00%**, Mean Token F1 hồi phục từ **0.9000 lên 1.0000**, và báo cáo `corruption_report.md` xác nhận AI lấy lại 100% độ chính xác ban đầu.

---

## 8. Phân tích kết quả thực nghiệm

### Metrics chính ghi nhận thực tế

| Metric / Signal | 🟢 Baseline | 🔴 Corrupted | 🔵 Repaired | Nhận xét cá nhân |
| :--- | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | **100.00%** | **70.00%** | **100.00%** | Sụt giảm 30% do 20% bài báo mới bị drop và tiêu đề bị cắt ngắn. Phục hồi 100% sau repair. |
| `mean_token_f1` | **1.0000** | **0.9000** | **1.0000** | Dữ liệu bị tiêm noise và xóa summary làm câu trả lời bị lệch, sau phục hồi đạt độ khớp tuyệt đối. |
| `judge_accuracy` | **100.00%** | **90.00%** | **100.00%** | Độ chính xác ngữ nghĩa suy giảm tương ứng với sự sai lệch của context retrieved. |
| `mean_judge_score` | **5.00 / 5.0** | **4.60 / 5.0** | **5.00 / 5.0** | Điểm số chất lượng trung bình phục hồi về mức tuyệt đối 5/5. |
| **Quality checks (GX)** | **PASS** | **FAIL (ALARM)** | **PASS** | Great Expectations 1.x phát hiện chính xác lỗi unique ID và summary rỗng. |
| **Freshness status** | **PASS** | **FAIL (STALE)** | **PASS** | Cảnh báo vi phạm SLA khi ngày xuất bản bị lùi 365 ngày trên 40% số bài. |

### Kết luận từ số liệu
1. **Chuỗi nguyên nhân - bằng chứng (Corruption):**
   - *Tiêm 6 lỗi dữ liệu* $\to$ *GX 1.x báo FAIL & Freshness báo STALE* $\to$ *Retrieval Hit Rate sụt giảm nghiêm trọng từ 100% xuống 70%* (Minh chứng sống động của Silent Failure).
2. **Chuỗi nguyên nhân - bằng chứng (Repair):**
   - *Kích hoạt Idempotent Repair từ Raw snapshot* $\to$ *GX 1.x & Freshness quay lại PASS* $\to$ *Retrieval Hit Rate và Token F1 lấy lại 100% phong độ ban đầu*.
3. **Kịch bản lỗi gây ảnh hưởng rõ rệt nhất:**
   - Lỗi **Drop latest records** và **Truncate title** gây thiệt hại nặng nề nhất cho bộ tìm kiếm ngữ nghĩa, khiến câu hỏi tra cứu theo tên bài báo hoàn toàn không tìm được tài liệu gốc.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Garbage In -> Garbage Out:** AI dù thông minh đến đâu cũng sẽ bị vô hiệu hóa nếu dữ liệu đầu vào bị sai lệch. 80% thành công của hệ thống RAG nằm ở chất lượng Data Pipeline.
2. **Sức mạnh của Data Observability Gate:** Việc đặt chốt kiểm định tự động bằng Great Expectations 1.x giúp ngăn chặn dữ liệu hỏng ngay từ "cửa ngõ", triệt tiêu hoàn toàn hiểm họa Silent Failure trước khi dữ liệu kịp thẩm thấu vào Vector DB.
3. **Nguyên tắc Idempotency & Data Lineage:** Luôn bảo tồn bản sao lưu thô nguyên gốc (Raw Preservation). Khi có sự cố, một pipeline có tính Idempotent có thể tái tạo toàn bộ hệ thống từ đầu một cách an toàn mà không cần can thiệp thủ công.

### Hướng cải thiện nếu có thêm thời gian
- Xây dựng cơ chế **Automated Self-Healing Pipeline (Bonus B2)**: Khi Great Expectations phát hiện kiểm định `FAIL`, pipeline sẽ tự động phát tín hiệu Event/Webhook kích hoạt hàm `repair` và tái nạp Vector Store tự động mà không cần kỹ sư phải gõ lệnh thủ công.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric thực tế để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này là sản phẩm độc lập phản ánh đúng đóng góp của vai trò Observability & Evaluation Lead.

**Ngày hoàn thành xác nhận:** 2026-09-25
