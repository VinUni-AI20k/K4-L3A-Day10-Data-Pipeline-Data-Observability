# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Thị Thu Trang |
| MSSV | 2A202602581 |
| Khóa/Lớp | K4 |
| Tên nhóm | [Điền sau] |
| Vai trò chính | Observability & Evaluation Lead (Thành viên 4) |
| Repository | [Điền sau] |
| Ngày hoàn thành | 2026-09-25 (đang tiếp tục cập nhật) |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data Quality Gate (GX 1.x) | `src/observability/quality.py::run_data_quality_checks` | `pandas.DataFrame` đúng Data Contract (`papers_clean`) | `data/quality/baseline_quality_report.json` | Hoàn thành (code + verify bằng dữ liệu tạm đúng contract; chờ `papers_clean.csv` thật từ TV2 để chạy lại) |
| Freshness SLA | `src/observability/quality.py::build_freshness_report` | Cùng DataFrame trên, cột `age_days` | `data/quality/freshness_report.json` | Hoàn thành (tương tự) |
| Benchmark test set | `src/evaluation/testset.py::build_test_set` | DataFrame clean | `data/eval/test_set.json` (10 câu, 4 loại) | Hoàn thành |
| Báo cáo markdown | `src/observability/reporting.py::generate_phase1_report`, `generate_corruption_report` | `metrics`, `quality`, `freshness` dict | `data/reports/phase1_report.md`, `corruption_report.md` | Một phần: hàm đã code và verify logic render, nhưng **chưa sinh được artifact chính thức** vì `src/ingestion/corruption.py` (TV2) và `src/pipelines/phase1.py`, `corruption_flow.py` (TV1) vẫn còn `NotImplementedError` tại thời điểm báo cáo này |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra trạng thái `src/ingestion/corruption.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` để xác định blocker trước khi code `reporting.py` | Thành viên 1 (Lead), Thành viên 2 (Data Foundation) | Xác nhận cả 3 file còn nguyên `TODO(student)`, chưa chỉnh sửa file của người khác — chỉ đọc để nắm trạng thái |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Cài đặt 4 expectation GX 1.x (ephemeral context) | `src/observability/quality.py` | `data/quality/baseline_quality_report.json` — `success: true`, 6/6 expectation PASS | `python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'baseline'); print(res['success'])"` |
| Freshness SLA (`age_days > 180` → cảnh báo nếu > 25%) | `src/observability/quality.py` | `data/quality/freshness_report.json` — stale_ratio 4.17% (1/24), `is_fresh: true` | `python -c "from core.config import load_settings; from observability.quality import build_freshness_report; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); print(build_freshness_report(df, s, s.paths.freshness_report))"` |
| Sinh 10 câu hỏi benchmark, phủ đều 4 loại | `src/evaluation/testset.py` | `data/eval/test_set.json` — phân bố 3 summary / 3 authors / 2 date / 2 categories, đúng 5 field bắt buộc | Tự viết bộ kiểm tra invariant (id không trùng, không rỗng, `ground_truth_doc_ids` trỏ đúng `paper_id` có thật) — tất cả PASS |
| Sinh báo cáo markdown baseline & so sánh 3 trạng thái | `src/observability/reporting.py` | Code hoàn chỉnh, đã verify công thức `%Δ` và cấu trúc bảng bằng fixture tách bạch (dữ liệu GX thật + metrics giả lập chỉ để test) | Ghi ra file tạm ở scratchpad, **không** ghi đè `data/reports/*.md` thật để tránh lẫn số liệu giả vào deliverable |

**Output cụ thể:** `data/quality/baseline_quality_report.json` và `data/quality/freshness_report.json` là 2 artifact thật đã tồn tại trong repo tại thời điểm báo cáo, sinh ra từ code chính thức (không phải giả lập), tuy input hiện vẫn là DataFrame tự dựng đúng Data Contract (vì `papers_clean.csv` thật của TV2 chưa có) — cần chạy lại khi có input thật.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần việc của tôi giải quyết bài toán "Silent Failure" ở đúng lớp mà đề bài nhấn mạnh: Agent/RAG không tự báo lỗi khi dữ liệu bẩn, nên cần một **chốt kiểm dịch dữ liệu độc lập** (Data Quality Gate + Freshness SLA) chặn đứng trước khi dữ liệu vào Vector Store, và một **bộ đề thi benchmark cố định** để đo lường khách quan mức độ suy giảm/hồi phục của hệ thống RAG qua từng trạng thái dữ liệu.

### Cách triển khai

- `run_data_quality_checks`: dùng đúng API ephemeral của Great Expectations 1.x (`gx.get_context(mode="ephemeral")` → `add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `get_batch`), sau đó gọi `batch.validate(expectation)` cho từng expectation và gom kết quả bằng `result.to_json_dict()` (API chính thức của GX, đảm bảo JSON-safe, không tự bóc field thủ công).
- `build_freshness_report`: tính `stale_ratio` dựa trên `settings.freshness_threshold_days` (không hardcode số 180) để nếu cấu hình đổi thì hàm vẫn đúng.
- `build_test_set`: chọn dòng theo thứ tự sort cố định (`sort_values("paper_id")`) thay vì random, để test set **tái lập được** — đúng vai trò "ground truth bất di bất dịch" mà `nhiemvu.md` yêu cầu; gán loại câu hỏi theo round-robin qua 4 loại để tự động phủ đều mà không cần hardcode tỉ lệ.
- `reporting.py`: tách 2 hàm helper dùng chung (`_quality_section`, `_freshness_section`) cho cả `phase1_report` và `corruption_report` để không lặp code; công thức `%Δ` tự tính từ tham số đầu vào, không viết số cứng trong template.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `papers_clean.csv/json` (contract: `paper_id, title, summary, authors, categories, published, age_days, authors_joined, categories_joined, summary_chars, text_for_embedding`) do TV2 (`cleaning.py`) tạo ra |
| Output | `data/quality/*.json`, `data/eval/test_set.json`, `data/reports/*.md` |
| Module phụ thuộc | `src/ingestion/cleaning.py` (TV2), `src/ingestion/corruption.py` (TV2), `src/core/config.py`/`core/utils.py` (TV1) |
| Module sử dụng output | `src/evaluation/metrics.py::evaluate_pipeline` (đọc `test_set.json`), `src/pipelines/phase1.py`, `corruption_flow.py` (TV1, gọi `quality.py`/`reporting.py`) |
| Điều kiện lỗi cần xử lý | `build_test_set` raise `ValueError` nếu DataFrame có ít hơn 5 dòng, tránh sinh test set rỗng/vô nghĩa |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'baseline'); print('success =', res['success'])"
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(len(ts), 'cau hoi')"
```

- **Kết quả mong đợi:** `success = True` trên dữ liệu sạch; `10 cau hoi` với phân bố phủ đều 4 loại.
- **Kết quả thực tế:** đúng như mong đợi, khi chạy trên DataFrame tự dựng đúng contract từ `data/raw/crossref_records.json` (vì `papers_clean.csv` thật chưa có tại thời điểm test).
- **Artifact/log:** `data/quality/baseline_quality_report.json`, `data/quality/freshness_report.json`, `data/eval/test_set.json` — không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Tại thời điểm cần code và verify `quality.py`/`testset.py`, `src/ingestion/cleaning.py` (TV2) vẫn còn `NotImplementedError`, nên không có `papers_clean.csv` thật để test.
- **Các phương án đã cân nhắc:**
  1. Chờ TV2 hoàn thành `cleaning.py` rồi mới bắt đầu code/test.
  2. Tự dựng một DataFrame tạm, đúng 100% Data Contract đã chốt trong `nhiemvu.md`, lấy dữ liệu từ snapshot `data/raw/crossref_records.json` có sẵn, để code và verify độc lập.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Đúng nguyên tắc "Song mã cùng chạy — Không dẫm chân, Không chờ đợi" mà `nhiemvu.md` đặt ra làm nguyên tắc vàng của nhóm; đồng thời Data Contract đã đóng băng nên DataFrame tạm dựng đúng contract có giá trị test tương đương dữ liệu thật, chỉ khác nội dung, không khác schema.
- **Bằng chứng quyết định phù hợp:** Toàn bộ smoke-test (GX 6 expectation, freshness, 10 câu hỏi test) đều chạy đúng logic và cho `success/is_fresh` hợp lý; khi cố ý đưa dữ liệu lỗi vào (trùng `paper_id`, `summary` rỗng), GX bắt đúng loại lỗi — chứng minh code đã sẵn sàng nhận dữ liệu thật mà không cần sửa lại khi TV2 bàn giao.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  AttributeError: 'str' object has no attribute 'resolve'
  ```
  xảy ra khi gọi `load_settings(project_dir=...)` trong script test.
- **Lệnh hoặc bước tái hiện:** `load_settings(project_dir=r"C:\...\K4-L3A-Day10-...")` — truyền một chuỗi thay vì `pathlib.Path`.
- **Nguyên nhân gốc:** `src/core/config.py::load_settings` gọi `.resolve()` trực tiếp lên `project_dir`, kỳ vọng tham số là `Path`, nhưng script test truyền vào `str` (raw string Windows path).
- **Cách xử lý:** Sửa script test để bọc `Path(...)` quanh đường dẫn trước khi truyền vào `load_settings` — không sửa `core/config.py` vì đó không phải file tôi sở hữu và hành vi hiện tại (yêu cầu `Path`) là hợp lý theo type hint đã khai báo.
- **Cách xác minh sau khi sửa:** Chạy lại script, `load_settings` trả về `Settings` hợp lệ, các bước tiếp theo (`run_data_quality_checks`, `build_freshness_report`) chạy thành công.
- **Điều học được:** Luôn đối chiếu type hint của hàm thuộc module người khác sở hữu trước khi gọi trong script test, thay vì đoán kiểu dữ liệu.

Nếu chưa xử lý xong (blocker khác, vẫn còn mở tại thời điểm báo cáo):

- **Phạm vi bị ảnh hưởng:** Không thể sinh `data/quality/corrupted_quality_report.json`, `data/results/{baseline,corrupted,repaired}_metrics.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md` **chính thức** (bằng dữ liệu thật).
- **Những gì đã loại trừ:** Không phải lỗi trong `quality.py`/`testset.py`/`reporting.py` của tôi — cả 3 hàm đã verify chạy đúng bằng dữ liệu hợp lệ và dữ liệu cố ý làm lỗi thủ công. Nguyên nhân thuần túy là `src/ingestion/corruption.py` (TV2) và `src/pipelines/phase1.py`, `corruption_flow.py` (TV1) chưa được triển khai.
- **Bước tiếp theo:** Khi TV1/TV2 bàn giao, chạy lại các lệnh tự-kiểm-tra đã ghi ở mục 4 và trong `myddocs/thucthi.md` để sinh artifact chính thức, không cần sửa lại code hiện tại.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?** Crossref API (hoặc snapshot offline `data/raw/crossref_response.json`) → `crossref.py` bóc tách thành `PaperRecord` (DOI, title, summary đã lọc HTML tag, authors, categories, published) → `cleaning.py` chuẩn hóa, khử trùng lặp theo `paper_id`, tính `age_days`, ghép `text_for_embedding` → `papers_clean.csv/json` → `retrieval/index.py` dùng MiniLM embed và nạp vào ChromaDB theo từng collection (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?** `test_set.json` (10 câu, do tôi sinh) giữ `ground_truth_doc_ids` là `paper_id` đúng của bài báo được hỏi; `evaluation/metrics.py::evaluate_pipeline` so khớp `retrieved_doc_ids` của Agent với `ground_truth_doc_ids` để tính `retrieval_hit_rate`, và so khớp văn bản trả lời với `ground_truth` để tính `token_f1`.
3. **Quality checks khác freshness monitoring ở điểm nào?** Quality checks (GX) kiểm tra tính toàn vẹn cấu trúc/nội dung tại một thời điểm snapshot (đủ dòng, không null, không trùng, đủ độ dài) — trả lời câu hỏi "dữ liệu có sạch không". Freshness monitoring kiểm tra tính thời sự của dữ liệu theo thời gian (`age_days`) — trả lời câu hỏi "dữ liệu có còn mới không", một dữ liệu có thể hoàn toàn sạch về cấu trúc nhưng vẫn cũ/lỗi thời.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?** Để phép so sánh có ý nghĩa thống kê — nếu đổi câu hỏi giữa các trạng thái, sự sụt giảm/phục hồi của Hit Rate hay Token F1 có thể do đổi độ khó câu hỏi chứ không phải do chất lượng dữ liệu, làm mất giá trị chứng minh của thí nghiệm.
5. **Repair được xem là thành công dựa trên artifact và metric nào?** Dựa trên: (a) `repaired_quality_report`/`freshness` trả về `success=True`/`is_fresh` tương đương baseline; (b) `repaired_metrics.json` có `retrieval_hit_rate`, `mean_token_f1` hồi phục về gần mức baseline (so với mức sụt giảm rõ rệt ở `corrupted_metrics.json`) — tức là quy trình nạp lại từ `data/raw/crossref_records.json` gốc và chạy lại `cleaning.py` một cách idempotent, không cần sửa tay.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | [Chưa có — chờ `phase1.py`] | [Chưa có — chờ `corruption_flow.py`] | [Chưa có] | Phụ thuộc pipeline TV1/TV2, chưa chạy được tại thời điểm báo cáo |
| `mean_token_f1` | [Chưa có] | [Chưa có] | [Chưa có] | như trên |
| `judge_accuracy` | [Chưa có] | [Chưa có] | [Chưa có] | như trên |
| `mean_judge_score` | [Chưa có] | [Chưa có] | [Chưa có] | như trên |
| Quality checks (GX) | `success = true` (6/6 PASS) | [Chưa có — chờ `corruption.py`] | [Chưa có] | Baseline dùng DataFrame tạm đúng contract, cần chạy lại với `papers_clean.csv` thật |
| Freshness status | `is_fresh = true`, stale 4.17% (1/24) | [Chưa có] | [Chưa có] | như trên |

### Kết luận từ số liệu

Chưa thể hoàn thành 2 chuỗi nguyên nhân–bằng chứng đầy đủ (corruption → suy giảm metric; repair → phục hồi metric) vì chưa có `corrupted_metrics.json`/`repaired_metrics.json` thật. Bằng chứng gián tiếp duy nhất hiện có là **smoke-test có kiểm soát** (không phải corruption suite thật của TV2): khi tôi cố ý làm trùng `paper_id` và xóa trắng `summary` trên DataFrame tạm, `run_data_quality_checks` phát hiện đúng 2/6 expectation fail (`expect_column_values_to_be_unique`, `expect_column_value_lengths_to_be_between`) — cho thấy cơ chế phát hiện lỗi hoạt động đúng ở mức đơn vị, nhưng **chưa chứng minh được** mức độ ảnh hưởng thực tế lên Agent RAG (Hit Rate/Token F1) vì bước đó cần `corruption.py` + `phase1.py`/`corruption_flow.py` thật.

Kết quả khác với kỳ vọng ban đầu: tôi kỳ vọng có thể hoàn thành toàn bộ vòng lặp corrupt → evaluate → repair → compare trong buổi làm việc, nhưng do phần việc của TV1/TV2 (`corruption.py`, `phase1.py`, `corruption_flow.py`) chưa được triển khai, phần phân tích định lượng 3 trạng thái phải để trống trung thực thay vì suy diễn số liệu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Great Expectations 1.x có API ephemeral khác hẳn cú pháp cũ (`add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `batch.validate(expectation)`), và `result.to_json_dict()` là cách an toàn nhất để serialize kết quả ra JSON mà không cần tự bóc field.
2. Một bộ evaluation set chỉ có giá trị khoa học nếu nó **deterministic và bất biến** giữa các lần chạy/các trạng thái dữ liệu — nếu không, mọi kết luận về "sụt giảm" hay "phục hồi" đều mất ý nghĩa so sánh.
3. Trong làm việc nhóm phụ thuộc chuỗi (ingestion → cleaning → observability → pipeline → report), việc tự dựng dữ liệu test đúng contract giúp không bị block hoàn toàn, nhưng không thể thay thế cho việc tích hợp thật — cần ghi nhận trung thực ranh giới giữa "code đã verify" và "artifact chính thức đã sinh ra".

### Nếu có thêm thời gian

Tôi sẽ viết thêm bộ `pytest` cho `quality.py` và `testset.py` (kiểm tra invariant tự động thay vì script thủ công như hiện tại), đồng thời chủ động trao đổi sớm hơn với TV1/TV2 ngay từ SYNC 1 (phút 30) để phát hiện blocker ở `cleaning.py`/`corruption.py` sớm hơn, thay vì phát hiện muộn ở phase 95–165.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trần Thị Thu Trang
**Ngày xác nhận:** 2026-09-25
