# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Việt Hoàng Hải |
| MSSV | 2A202602967 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | SVSoppi |
| Vai trò chính | Phụ trách Data Observability & Benchmark Evaluation (`src/observability/quality.py`, `src/evaluation/testset.py`) |
| Repository | `hoangtrunghieu0025-lab/K4-L3-DAY10-SVSoppi-DataPipeline` |
| Ngày hoàn thành | 2026-09-25 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| **Quality Gate (GX 1.x)** | `src/observability/quality.py`<br>- `run_data_quality_checks`<br>- `_build_expectations`<br>- `_summarize_result` | Clean `pd.DataFrame`, `Settings`, `report_name` | `data/quality/<name>_quality_report.json`<br>`data/quality/gx/<name>_validation.json` | Hoàn thành |
| **Freshness SLA** | `src/observability/quality.py`<br>- `build_freshness_report`<br>- `_freshness_payload`<br>- `_age_days` | Clean `pd.DataFrame`, `Settings`, `report_path` | `data/quality/*freshness_report.json`, trường `freshness` trong quality report | Hoàn thành |
| **Test Set Generator** | `src/evaluation/testset.py`<br>- `build_test_set`<br>- `_select_papers`<br>- `_ground_truth` | Clean `pd.DataFrame`, `output_path` | `data/eval/test_set.json` (10 câu hỏi chuẩn hóa cho 4 loại câu hỏi) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| **Chuẩn hóa Data Contract** | Hoàng Trung Hiếu (`src/observability/reporting.py`) | Thống nhất cấu trúc dictionary trả về từ `quality.py` (khóa `checks`, `failed_expectations`, `unexpected_count`) để `reporting.py` hiển thị chính xác bảng vi phạm thay vì bị lỗi rỗng `None`. |
| **Kiểm thử tích hợp RAG QA** | Toàn nhóm (`src/retrieval/qa.py`) | Đảm bảo định dạng câu hỏi trong `testset.py` bọc nháy đơn quanh title (`'{title}'`) và dùng đúng từ khóa (`summary`, `authored`, `published`, `belong to`) để hàm trích xuất regex trong `qa.py` hoạt động chính xác. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng bộ 8 Expectations Great Expectations 1.x | `src/observability/quality.py` (`_build_expectations`) | Bắt thành công 3 lỗi nghiêm trọng khi dữ liệu bị corrupt: trùng ID, title quá ngắn, summary rỗng. | Chạy `python -m src.pipelines.corruption_flow`, kiểm tra `corrupted_quality_report.json` có `success: false` (5/8 pass, 3 fail). |
| Thiết lập kiểm tra Freshness SLA (180 ngày, ngưỡng vi phạm 25%) | `src/observability/quality.py` (`_freshness_payload`) | Bắt được lỗi `stale_date` khi 9/22 dòng (40.91%) bị lùi ngày quá hạn, gắn cờ `is_fresh: false`. | Kiểm tra trường `freshness.stale_ratio` trong `data/quality/corrupted_quality_report.json` = 0.4091. |
| Sinh bộ 10 câu hỏi đánh giá benchmark | `src/evaluation/testset.py` (`build_test_set`) | Bộ 10 câu hỏi đa dạng (3 summary, 3 authors, 2 date, 2 categories) kèm `ground_truth_doc_ids` chuẩn xác. | `data/eval/test_set.json` được sinh đầy đủ 10 mẫu; đánh giá baseline đạt Hit Rate 1.0 và Token F1 1.0. |

### Output cụ thể bàn giao

1. **`data/quality/corrupted_quality_report.json`**: Báo cáo chất lượng dữ liệu ở trạng thái corrupted ghi nhận chính xác 3 expectation bị vi phạm:
   - `expect_column_values_to_be_unique(paper_id)`: 6 dòng trùng (do `duplicate_rows`).
   - `expect_column_value_lengths_to_be_between(title)`: 4 dòng vi phạm độ dài tối thiểu 20 ký tự (do `truncate_title`).
   - `expect_column_value_lengths_to_be_between(summary)`: 3 dòng vi phạm độ dài tối thiểu 30 ký tự (do `blank_summary`).
2. **`data/eval/test_set.json`**: Bộ benchmark 10 câu hỏi cố định dùng chung cho cả 3 trạng thái Baseline, Corrupted và Repaired, đảm bảo tính công bằng và nhất quán khi đo đạc tác động của dữ liệu lên Agent.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Trong một pipeline dữ liệu phục vụ RAG Agent, việc dữ liệu bị lỗi (schema biến dạng, trường bắt buộc bị null/rỗng, dữ liệu cũ quá hạn, hoặc bị trùng lặp) thường không gây crash code ngay tại thời điểm ingestion mà âm thầm đi vào vector store. Kết quả là Agent bị **silent failure**: truy xuất nhầm tài liệu, trích xuất chuỗi rỗng, hoặc đưa ra câu trả lời sai lệch hoàn toàn với thực tế mà không hề có ngoại lệ (exception) nào được ném ra.

Nhiệm vụ của tôi là:
1. Xây dựng **Quality Gate** tự động bằng Great Expectations 1.x chặn đứng dữ liệu bẩn trước khi đưa vào ChromaDB.
2. Xây dựng cơ chế giám sát **Freshness SLA** để cảnh báo khi dữ liệu học thuật bị quá hạn (lỗi thời).
3. Xây dựng công cụ tạo **Evaluation Test Set** chuẩn mực để định lượng chính xác chất lượng của hệ thống ở cả 2 khía cạnh: Retrieval (Hit Rate) và Generation (Token F1, Judge Score).

### Cách triển khai

1. **Great Expectations 1.x Fluent API (`quality.py`)**:
   - Khác với GX 0.17/0.18 dùng YAML và checkpoint phức tạp, tôi sử dụng chuẩn GX 1.x với `gx.get_context(mode="ephemeral")`.
   - Kết nối Pandas DataFrame thông qua Fluent API: `data_source = context.data_sources.add_pandas(...)` -> `add_dataframe_asset` -> `add_batch_definition_whole_dataframe`.
   - Thiết lập bộ 8 Expectation cốt lõi:
     - Số lượng dòng nằm trong khoảng cho phép: `ExpectTableRowCountToBeBetween(5, 5000)`.
     - Không được Null ở các trường trọng yếu: `ExpectColumnValuesToNotBeNull` cho `paper_id`, `title`, `summary`, `text_for_embedding`.
     - Tính định danh duy nhất: `ExpectColumnValuesToBeUnique(column="paper_id")`.
     - Chất lượng văn bản: `ExpectColumnValueLengthsToBeBetween` cho `summary` (tối thiểu 30 ký tự) và `title` (tối thiểu 20 ký tự).
   - Hàm `_summarize_result` chuẩn hóa output của GX thành JSON gọn nhẹ chứa `element_count`, `unexpected_count`, `partial_unexpected_list` để làm báo cáo.

2. **Freshness SLA Monitoring**:
   - Tính toán tuổi thọ dữ liệu dựa trên `age_days` (hoặc chênh lệch giữa ngày chạy và cột `published`).
   - Ngưỡng cấu hình: `freshness_threshold_days = 180` ngày. Nếu tỷ lệ bài viết cũ vượt quá `MAX_STALE_RATIO = 0.25` (25%), hệ thống ghi nhận vi phạm SLA (`is_fresh: false`).
   - Thiết kế Freshness như một **non-blocking alert** (cảnh báo đi kèm nhưng không chặn luồng build nếu GX gate pass), giúp phân tách rõ giữa tính "hợp lệ" và tính "mới".

3. **Cơ chế sinh Benchmark Test Set (`testset.py`)**:
   - Sử dụng kế hoạch phân bổ cân đối 10 câu hỏi: 3 `summary`, 3 `authors`, 2 `date`, 2 `categories`.
   - Lọc các bài viết sạch, loại bỏ các bài có dấu nháy đơn `'` trong tiêu đề để tránh lỗi cú pháp câu lệnh truy vấn.
   - Chọn mẫu trải đều (`_select_papers`) theo vị trí index phân bổ trên toàn bộ corpus đã sắp xếp, tránh thiên vị một nhóm bài.
   - Trích xuất ground truth chuẩn xác theo từng loại: câu đầu tiên của summary (`first_sentence`), danh sách tác giả nối chuỗi (`authors_joined`), ngày xuất bản chuẩn ISO (`YYYY-MM-DD`), và danh mục thể loại (`categories_joined`).

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| **Input** | `pd.DataFrame` sau bước clean (các cột: `paper_id`, `title`, `summary`, `text_for_embedding`, `published`, `authors_joined`, `categories_joined`, `age_days`), `Settings`. |
| **Output** | 1. `data/quality/<name>_quality_report.json`: Báo cáo chi tiết từng check, số vi phạm, trạng thái freshness.<br>2. `data/quality/gx/<name>_validation.json`: Raw result từ GX 1.x.<br>3. `data/eval/test_set.json`: Danh sách 10 object câu hỏi đánh giá benchmark. |
| **Module phụ thuộc** | `src/ingestion/cleaning.py` (cung cấp clean dataframe), `core/config.py`, `core/utils.py`. |
| **Module sử dụng output** | `src/pipelines/phase1.py` & `src/pipelines/corruption_flow.py` (dùng quality report làm gate quyết định index), `src/observability/reporting.py` (render báo cáo markdown), `src/evaluation/rag_eval.py` (chạy test set đo metrics). |
| **Điều kiện lỗi cần xử lý** | DataFrame rỗng hoặc thiếu cột; cột `published` có định dạng lạ hoặc epoch millisecond; cột text chứa giá trị null; ngoại lệ khi chạy GX Expectation. |

### Cách xác minh

Chạy kiểm thử chất lượng và freshness trên cả 3 trạng thái dữ liệu qua pipeline tích hợp:

```bash
python -m src.pipelines.corruption_flow
```

- **Kết quả mong đợi:**
  - Trạng thái Baseline: 8/8 Expectation PASS, Freshness SLA PASS (`is_fresh: true`, stale ratio 0.00). Quality Gate cho phép đi tiếp vào Chroma indexing.
  - Trạng thái Corrupted: 5/8 Expectation PASS, 3 FAIL (bắt được unique paper_id, title length, summary length). Freshness SLA FAIL (`is_fresh: false`, stale ratio 40.91% > 25%). Quality Gate trả về `success: false`.
  - Trạng thái Repaired: 8/8 Expectation PASS, Freshness SLA PASS (`is_fresh: true`, stale ratio 0.00), phục hồi 100%.
- **Kết quả thực tế:**
  - `data/quality/baseline_quality_report.json`: `success: true`, `evaluated_expectations: 8`, `successful_expectations: 8`.
  - `data/quality/corrupted_quality_report.json`: `success: false`, `failed_expectations`: `["expect_column_values_to_be_unique(paper_id)", "expect_column_value_lengths_to_be_between(title)", "expect_column_value_lengths_to_be_between(summary)"]`, `stale_rows: 9`, `total_rows: 22`, `stale_ratio: 0.4091`.
  - `data/quality/repaired_quality_report.json`: `success: true`, 8/8 PASS.
- **Artifact/log:**
  - `data/quality/corrupted_quality_report.json`
  - `data/quality/gx/corrupted_validation.json`
  - `data/eval/test_set.json`

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương án triển khai Data Quality Gate giữa việc dùng Great Expectations phiên bản cũ (GX 0.17/0.18 Checkpoint với file YAML cấu hình trên ổ đĩa) hoặc thư viện Pydantic/Pandera tự viết, so với việc nâng cấp lên **Great Expectations 1.x Fluent API** chạy chế độ in-memory (ephemeral).
- **Các phương án đã cân nhắc:**
  1. *Phương án A: GX 0.18 Checkpoint + thư mục `great_expectations/`*. Tạo cây thư mục `great_expectations/great_expectations.yml`, datasources YAML và checkpoint file.
  2. *Phương án B: Viết rule kiểm tra thủ công bằng Pandas hoặc Pydantic*. Dùng code Python thuần kiểm tra `df['paper_id'].duplicated()`, `df['title'].str.len() < 20`, v.v.
  3. *Phương án C (Được chọn): Great Expectations 1.x Fluent API in-memory (`mode="ephemeral"`, `gxe.Expectation`)*.
- **Lý do chọn:**
  - So với Phương án A: GX 1.x Fluent API loại bỏ hoàn toàn sự rườm rà của các file YAML cấu hình phức tạp, không làm rác repository với hàng tá thư mục ẩn, cho phép khởi tạo context động trong RAM và liên kết trực tiếp với Pandas DataFrame thông qua `context.data_sources.add_pandas(...)`.
  - So với Phương án B: Giữ được chuẩn hóa công nghiệp (enterprise observability) của framework Great Expectations, tự động sinh validation payload chi tiết (unexpected values, counts, percentages), phục vụ trực tiếp cho việc xuất báo cáo chuyên nghiệp.
- **Bằng chứng quyết định phù hợp:** Code chạy mượt mà, thời gian validate chỉ mất dưới 0.3 giây cho toàn bộ 8 expectation; artifact `corrupted_quality_report.json` bóc tách được chi tiết danh sách 6 `paper_id` trùng và các chuỗi bị lỗi cắt ngắn, giúp `reporting.py` render ra bảng phân tích chi tiết.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi tích hợp với `src/observability/reporting.py`, báo cáo `corruption_report.md` sinh ra mâu thuẫn:
  ```markdown
  Quality Gate (GX 1.x) | ❌ FAIL
  Failed checks: None — the quality gate did NOT catch the corruption
  ```
  Dù Quality Gate báo FAIL nhưng bảng danh sách lỗi lại hoàn toàn rỗng.
- **Lệnh hoặc bước tái hiện:** Chạy tích hợp flow: `python -m src.pipelines.corruption_flow`.
- **Nguyên nhân gốc:** Lệch Data Contract nội bộ. Module `reporting.py` được viết ban đầu dựa trên giả định output của GX raw (chứa key `"results"` và mỗi item có key `"column"`). Tuy nhiên, hàm `run_data_quality_checks` trong `quality.py` đã rút gọn và đóng gói kết quả vào key `"checks"`, với thông tin cột nằm trong `item["kwargs"]["column"]`. Khi `reporting.py` gọi `quality.get("results", [])`, hàm trả về mảng rỗng `[]`, dẫn đến không in ra được dòng lỗi nào dù `success: false`.
- **Cách xử lý:** Tôi đã phối hợp cùng Lead (Hoàng Trung Hiếu) để chuẩn hóa contract đầu ra của `quality.py`:
  - Trong `quality.py`: cung cấp cả `checks` (danh sách chi tiết), `failed_expectations` (danh sách ngắn dạng chuỗi `expectation(column)`), và `alerts` (chuỗi cảnh báo format sẵn).
  - Cập nhật `reporting.py` đọc đúng cấu trúc `checks` và truy xuất `kwargs.get("column", "table")`.
- **Cách xác minh sau khi sửa:** Chạy lại `python -m src.pipelines.corruption_flow`. File `data/reports/corruption_report.md` lập tức hiển thị đầy đủ và chính xác 3 check bị fail kèm số bản ghi vi phạm:
  - `expect_column_values_to_be_unique` trên cột `paper_id` (6 vi phạm)
  - `expect_column_value_lengths_to_be_between` trên cột `title` (4 vi phạm)
  - `expect_column_value_lengths_to_be_between` trên cột `summary` (3 vi phạm)
- **Điều học được:** Khi làm việc nhóm đa module, Data Contract giữa các tầng phải được tài liệu hóa và thống nhất rõ ràng. Việc dùng hàm an toàn như `.get(..., [])` tuy giúp pipeline không bị sập (crash) nhưng lại vô tình tạo ra **silent failure** trong tầng reporting nếu schema bị lệch.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - Dữ liệu thô từ Crossref API (`/works`) được lưu nguyên bản vào `crossref_response.json`, sau đó được lọc sạch thẻ JATS XML và bóc tách thành các đối tượng `PaperRecord` trong `crossref_records.json`.
   - Module `cleaning.py` nhận danh sách record này, loại bỏ trùng lặp theo `paper_id`, tính `age_days`, tạo các cột chuỗi nối `authors_joined`, `categories_joined`, và ghép 5 thành phần (title, authors, published, categories, summary) thành `text_for_embedding`.
   - Dataframe sạch bắt buộc phải đi qua **Quality Gate (GX 1.x)** trong `quality.py`. Chỉ khi Quality Gate trả về `success: true`, dữ liệu mới được chuyển sang `src/retrieval/indexing.py` để mô hình `all-MiniLM-L6-v2` nhúng thành vector và nạp vào collection của ChromaDB (dùng khoảng cách Cosine).

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - Mỗi câu hỏi trong `test_set.json` chứa `ground_truth_doc_ids` (chính là `paper_id` của bài viết mang thông tin trả lời) và chuỗi `ground_truth` đáp án chuẩn.
   - **Retrieval Hit Rate:** Đánh giá tầng truy xuất. Kiểm tra xem `ground_truth_doc_ids` có xuất hiện trong Top-4 tài liệu do ChromaDB trả về hay không (`retrieval_hit = true/false`).
   - **Mean Token F1 & Judge Score:** Đánh giá tầng sinh câu trả lời. Token F1 so khớp tập từ vựng giữa câu trả lời sinh ra bởi Agent và `ground_truth`. Judge Evaluator (hoặc Mock Heuristic) chấm điểm từ 1-5 và tính `judge_accuracy`. Hai tầng chỉ số này giúp phân biệt rõ: hệ thống sai do *tìm không ra tài liệu* hay do *tìm đúng nhưng tài liệu bị sai/nhiễu*.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - **Quality checks (GX 1.x):** Kiểm tra tính *toàn vẹn cấu trúc và logic dữ liệu* tại một thời điểm (Data Validity/Integrity). Ví dụ: ID có bị duplicate không, các trường cốt lõi có bị null không, độ dài văn bản có hợp lệ không. Nếu vi phạm, đây là lỗi nghiêm trọng (blocking gate) và pipeline phải dừng lại, không được nạp vào vector store.
   - **Freshness monitoring:** Kiểm tra tính *cập nhật theo thời gian* (Data Timeliness/Recency) dựa trên SLA (bài viết quá 180 ngày). Dữ liệu có thể hoàn toàn hợp lệ về mặt cấu trúc (không null, không trùng) nhưng vẫn bị cũ (lạc hậu). Freshness là **non-blocking alert**: ghi nhận cảnh báo để lên lịch refresh dữ liệu, nhưng không chặn pipeline chạy tiếp nếu cấu trúc vẫn hợp lệ.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   - Để đảm bảo tính khách quan và khoa học của thực nghiệm (kiểm soát biến số). Test set đóng vai trò là "thước đo cố định".
   - Nếu sinh lại test set trên dữ liệu corrupted, các câu hỏi và ground truth sẽ lấy theo dữ liệu đã hỏng (ví dụ: ngày bị lùi 1 năm, title bị cắt vụn). Khi đó Agent trả lời ngày sai nhưng hệ thống chấm lại coi là "đúng", dẫn đến đánh giá sai lệch hoàn toàn. Giữ nguyên test set chuẩn sạch giúp đo lường chính xác mức độ suy giảm do từng loại corruption gây ra.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - **Artifact kiểm chứng tính Idempotent:** `clean_matches_baseline == True` (được log trong `corruption_flow.py`), xác nhận 24/24 dòng của `papers_clean_repaired.json` trùng khớp hoàn toàn với `papers_clean.json` (bỏ qua `age_days`).
   - **Quality & Freshness Artifacts:** `repaired_quality_report.json` đạt `success: true` (8/8 pass) và `repaired_freshness_report.json` đạt `is_fresh: true` (stale ratio = 0.00).
   - **Agent Metrics Artifact:** `repaired_metrics.json` khôi phục tuyệt đối 100% so với baseline:
     - `retrieval_hit_rate`: 0.60 -> **1.00**
     - `mean_token_f1`: 0.50 -> **1.00**
     - `judge_accuracy`: 0.50 -> **1.00**
     - `mean_judge_score`: 3.00 -> **5.00**

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | **1.00** | **0.60** | **1.00** | Bị sụt giảm 40% (4/10 câu bị trượt). Cả 4 câu này đều trỏ vào các bài thuộc 20% mới nhất bị xóa bởi `drop_latest_records`. |
| `mean_token_f1` | **1.00** | **0.50** | **1.00** | Giảm một nửa. Mức sụt giảm sâu hơn hit rate vì ngoài 4 câu miss retrieval, có thêm câu eval_009 tìm đúng bài nhưng nội dung bị `inject_noise` nên trả lời rác (`?????`). |
| `judge_accuracy` | **1.00** | **0.50** | **1.00** | Chạy qua Fallback Heuristic Judge bám theo Token F1 (ngưỡng F1 >= 0.5). |
| `mean_judge_score` | **5.00** | **3.00** | **5.00** | Tương ứng với tỷ lệ câu trả lời đúng 5/10 câu. |
| Quality checks (GX) | **8/8 PASS** | **5/8 PASS** (Gate FAIL) | **8/8 PASS** | Bắt được 3 lỗi cấu trúc: duplicate ID (6 dòng), title ngắn (4 dòng), summary rỗng (3 dòng). |
| Freshness status | **Fresh (0.0%)** | **Stale (40.9%)** | **Fresh (0.0%)** | Bắt được lỗi `stale_date` khi 8 bài bị lùi ngày làm tỷ lệ quá hạn vượt ngưỡng 25%. |

### Kết luận từ số liệu

1. **Chuỗi vi phạm thứ nhất (Structural Corruption):**
   `duplicate_rows` + `truncate_title` + `blank_summary` $\rightarrow$ Great Expectations Quality Gate phát hiện 3 check FAIL $\rightarrow$ Quality Gate chuyển trạng thái `success: false`, kích hoạt cơ chế chặn index vào vector store.
2. **Chuỗi vi phạm thứ hai (Silent Failure & Freshness):**
   `stale_date` $\rightarrow$ Freshness SLA chuyển `is_fresh: false` (stale ratio 40.9% > 25%), nhưng GX Quality Gate vẫn PASS về mặt schema $\rightarrow$ Agent truy xuất đúng tài liệu (eval_003) nhưng tự tin trả lời sai năm (`2025-08-01` thay vì `2026-08-01`), kéo Token F1 câu này về 0.0.
3. **Chuỗi phục hồi (Idempotent Repair):**
   Pipeline loại bỏ toàn bộ dữ liệu hỏng, rebuild lại từ `data/raw/crossref_records.json` $\rightarrow$ Quality Gate đạt 8/8 PASS, Freshness SLA đạt Fresh 100% $\rightarrow$ Cả 4 chỉ số Retrieval Hit Rate, Token F1, Judge Accuracy và Judge Score đều phục hồi hoàn toàn về 1.00 (mức phục hồi 100%).

### Corruption nào ảnh hưởng rõ nhất và vì sao?

- **Về mặt định lượng (Metrics):** Lỗi `drop_latest_records` gây thiệt hại nặng nề nhất khi trực tiếp làm mất 4/10 câu hỏi đánh giá, làm giảm Retrieval Hit Rate từ 1.00 xuống 0.60. Điều đáng chú ý là **GX Quality Gate hiện tại không bắt được lỗi này**, vì số dòng giảm từ 24 xuống 22 vẫn nằm gọn trong khoảng cho phép của rule `ExpectTableRowCountToBeBetween(5, 5000)`.
- **Về mặt bản chất hệ thống RAG:** Lỗi `stale_date` nguy hiểm nhất vì đây là một **silent failure** kinh điển: Agent không gặp lỗi truy xuất, tìm đúng bài viết, trả lời cực kỳ trôi chảy nhưng nội dung đã bị sai lệch 1 năm. Nếu không có cơ chế Freshness SLA, hệ thống sẽ hoàn toàn không thể phát hiện lỗi này.

### Kết quả nào khác với kỳ vọng ban đầu?

- **Hiện tượng False Positive ở câu eval_004 (`categories`):**
  Bài viết đích của câu eval_004 nằm trong số các bài bị xóa bởi `drop_latest_records` (Retrieval Miss). Tuy nhiên, Token F1 của câu này lại đạt **1.0 (tuyệt đối)**!
  *Giải thích:* Do bài viết đích không có `container-title` nên categories fallback chỉ là `posted-content`. Khi tài liệu đúng bị drop, Agent truy xuất nhầm một bài viết khác cũng có category là `posted-content`, dẫn đến câu trả lời vô tình trùng khớp từ khóa. Điều này cho thấy chỉ số Token F1 đơn lẻ có thể đánh lừa người đánh giá, và bắt buộc phải đọc kèm với `retrieval_hit_rate`.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về Data Pipeline:** Chiến lược **Idempotent Repair** (tái thiết lập từ Raw Source bảo toàn) vượt trội hoàn toàn so với việc cố gắng "vá" từng bản ghi bị hỏng (ad-hoc patching). Lưu trữ Raw Data bất biến là chìa khóa sống còn của Data Engineering.
2. **Về Data Observability:** Một Quality Gate dù hiện đại (như GX 1.x) cũng chỉ phát hiện được những gì ta chủ động định nghĩa. Các lỗi về sụt giảm bất thường (data loss/drop) hoặc nhiễu nội dung (`inject_noise`) sẽ dễ dàng lọt qua nếu chỉ kiểm tra schema tĩnh (type, null, range).
3. **Về ảnh hưởng của Data đến RAG Agent:** RAG Agent phụ thuộc hoàn toàn vào "chân lý" nằm trong Vector Store (Garbage In, Confident Garbage Out). Dữ liệu hỏng không làm Agent crash mà khiến Agent đưa ra thông tin sai lệch một cách đầy thuyết phục.

### Nếu có thêm thời gian

Tôi muốn triển khai thêm 2 Expectation nâng cao để bịt kín 2 lỗ hổng đang để lọt lỗi:
1. **Dynamic Row Count Anomaly Detection:** Thay vì cố định `(5, 5000)`, bổ sung expectation so sánh số dòng với lần chạy trước đó (ví dụ: cảnh báo nếu giảm quá 10% dòng mà không có flag xác nhận).
2. **Text Noise & Gibberish Detection:** Sử dụng `ExpectColumnValuesToMatchRegex` hoặc tính toán entropy ký tự trong `summary` để phát hiện chuỗi ký tự lặp rác (`?????`) do `inject_noise` tạo ra.
*Cách đo lường:* Chạy lại `corruption_flow.py`; kỳ vọng Quality Gate sẽ bắt được cả 5/6 kịch bản corruption (thay vì 3/6 như hiện tại), ngăn chặn hoàn toàn việc index dữ liệu nhiễu hoặc thiếu hụt.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Việt Hoàng Hải  
**Ngày xác nhận:** 2026-09-25
