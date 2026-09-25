# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| Họ và tên | Nguyễn Thái Anh |
| MSSV | 2A202602810 |
| Khóa/Lớp | K4 - L3A (Day 10) |
| Tên nhóm | Phronesis |
| Vai trò chính | TV3 — Corruption & Pipeline Integration Owner |
| Repository | https://github.com/nthanhwork/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

Tôi tiếp nhận dữ liệu sạch, quality gate, test set và hàm báo cáo do các thành viên khác bàn giao; phụ trách ghép chúng thành hai luồng chạy được, tạo dữ liệu lỗi có kiểm soát và kiểm chứng phục hồi. Tôi không nhận là người triển khai ban đầu các module Crossref, cleaning, GX hay test set.

| Phần việc sở hữu | File/hàm chính | Đầu vào | Đầu ra đã kiểm chứng |
| :--- | :--- | :--- | :--- |
| Tiêm 6 lỗi dữ liệu | `src/ingestion/corruption.py::corrupt_clean_dataframe` | DataFrame sạch | DataFrame lỗi và `data/results/corruption_log.json` |
| Điều phối baseline | `src/pipelines/phase1.py::main` | Raw records, các module cleaning/quality/evaluation | Clean artifacts, Chroma `papers-baseline`, baseline metrics và báo cáo pha 1 |
| Điều phối corruption và repair | `src/pipelines/corruption_flow.py::main` | Baseline artifacts, raw records, test set cố định | Chroma `papers-corrupted`/`papers-repaired`, metrics và báo cáo so sánh |
| Kiểm chứng RAG và tích hợp | `src/retrieval/`, `src/evaluation/metrics.py` | Ba collection và cùng test set | 30 câu trả lời/chấm điểm qua ba trạng thái; kiểm tra collection 24/21/24 tài liệu |

Ngoài phạm vi chính, tôi chỉnh `src/observability/reporting.py` để báo cáo lấy trạng thái baseline và các kết luận từ artifact thực tế, tránh khẳng định sai rằng Token F1 đạt tối ưu hoặc chất lượng đã trở lại 100% khi số đo baseline chỉ là 0,500.

## 3. Kết quả bàn giao và bằng chứng

| Việc đã làm | Kết quả | Bằng chứng |
| :--- | :--- | :--- |
| Chạy baseline end-to-end | 24 bài báo sạch, 10 câu hỏi, quality PASS | `data/clean/papers_clean.json`, `data/eval/test_set.json`, `data/results/baseline_metrics.json` |
| Tiêm lỗi có thể lặp lại | Bỏ 5 bài mới; làm rỗng 7 summary; chèn noise 6; cắt 6 title; làm cũ 10 ngày xuất bản; nhân đôi 2 dòng | `data/results/corruption_log.json`; 21 dòng trong dữ liệu lỗi |
| Chạy quality và freshness trên dữ liệu lỗi | Quality FAIL do DOI trùng và summary quá ngắn; 11/21 dòng stale (52,38%) | `data/quality/corrupted_quality_report.json`, `corrupted_freshness_report.json` |
| Phục hồi từ raw | 24 dòng; quality PASS; nội dung `paper_id`/`text_for_embedding` và metrics khớp baseline | `data/clean/papers_clean_repaired.json`, `data/results/repaired_metrics.json` |
| Đánh giá bằng API model đã cấu hình | OpenAI `gpt-4o-mini` thực hiện 30/30 lượt LLM Judge; không có heuristic fallback | `data/results/baseline_answers.json`, `corrupted_answers.json`, `repaired_answers.json` |
| Xuất báo cáo | Bảng so sánh Baseline / Corrupted / Repaired phản ánh số đo thật | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` |

## 4. Giải thích kỹ thuật

### Thiết kế hai pipeline

`phase1.py` đọc raw records có sẵn (hoặc fetch khi bật refresh), làm sạch, ghi cùng một DataFrame ra CSV/JSON, chạy GX và freshness trước khi lập chỉ mục. Nếu quality gate của baseline thất bại, luồng dừng trước bước index. Sau đó pipeline tạo/nạp test set, xây collection `papers-baseline`, đánh giá và viết báo cáo.

`corruption_flow.py` dùng chính baseline clean data và test set đó để tạo dữ liệu lỗi. Dữ liệu lỗi được index vào collection riêng nhằm đo tác động của một thí nghiệm có kiểm soát; quality gate báo FAIL, nên không được xem collection này là dữ liệu production hợp lệ. Bước repair đọc lại `data/raw/crossref_records.json`, chạy lại cleaning, tạo collection `papers-repaired`, đánh giá trên cùng test set và đối chiếu ba trạng thái.

### Tính lặp và nhận dạng dữ liệu

Hàm corruption làm việc trên bản sao sâu của DataFrame, chọn vị trí lỗi theo thứ tự ngày xuất bản và ghi rõ số dòng/DOI bị tác động. Repair không vá từng dòng lỗi bằng tay: nó dựng lại dữ liệu từ raw. Trước khi so sánh, pipeline kiểm tra chữ ký gồm `paper_id` và `text_for_embedding` giữa baseline và dữ liệu dựng lại. Mỗi trạng thái có collection riêng nên không trộn vector sạch với vector lỗi; chạy lại không cộng thêm bản ghi vào collection hiện có.

### Contract với các module khác

| Thành phần | Contract sử dụng |
| :--- | :--- |
| Raw | `PaperRecord` từ `ingestion.crossref.load_raw_records()` |
| Clean | DataFrame có `paper_id`, `title`, `summary`, `published`, `age_days`, `authors_joined`, `categories_joined`, `text_for_embedding` |
| Test set | Mỗi câu có `question`, `ground_truth`, `ground_truth_doc_ids`; cùng file được dùng cho cả ba lần đánh giá |
| Metrics | `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score` |
| Quality | Kết quả GX và Freshness SLA ghi thành JSON, được truyền vào hàm tạo báo cáo |

## 5. Một quyết định kỹ thuật quan trọng

**Quyết định:** Phục hồi bằng cách làm sạch lại từ raw và tạo collection `papers-repaired` riêng.

Tôi cân nhắc (1) sửa trực tiếp các dòng bị tiêm lỗi trong DataFrame và (2) dựng lại toàn bộ từ raw snapshot. Cách thứ nhất phải biết chính xác mọi lỗi đã xảy ra và dễ bỏ sót bản ghi bị xóa. Tôi chọn cách thứ hai vì raw là nguồn đối chứng còn nguyên, cho phép kiểm tra nội dung phục hồi và chạy lại mà không tích lũy duplicate. Bằng chứng: collection baseline và repaired đều có 24 tài liệu; hai bộ metrics bằng nhau, trong khi collection corrupted có 21 tài liệu.

## 6. Một lỗi tích hợp đã xử lý

- **Triệu chứng:** Pha corruption lỗi `TypeError: Invalid value ... for dtype 'str'` khi cập nhật `published_date`.
- **Nguyên nhân:** DataFrame đọc lại từ clean JSON giữ cột ngày ở kiểu chuỗi; gán trực tiếp `pandas.Timestamp` vào cột chuỗi gây lỗi kiểu dữ liệu.
- **Cách xử lý:** Ghi ngày đã làm cũ thành chuỗi ISO `YYYY-MM-DD`, đồng thời cập nhật `age_days` và dựng lại `text_for_embedding` từ các trường sau corruption.
- **Xác minh:** `script/run_corruption_flow.py` chạy hết, freshness của corrupted là 52,38%, repaired trở về 0%; quality tương ứng FAIL rồi PASS.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được parse thành raw `PaperRecord`, sau đó cleaning tạo văn bản 5 phần để MiniLM nhúng và Chroma lưu vector cùng metadata.
2. `ground_truth_doc_ids` xác định retrieval có tìm được đúng DOI; `ground_truth` dùng để tính Token F1 và để LLM Judge chấm nội dung câu trả lời. API model chấm **Judge**; QA hiện tại chủ yếu trích xuất từ tài liệu theo quy tắc.
3. GX kiểm tra số dòng, null, DOI duy nhất và độ dài summary. Freshness kiểm tra tỷ lệ tài liệu có `age_days > 180`; dữ liệu có thể đúng schema nhưng đã cũ.
4. Ba trạng thái phải dùng cùng test set để thay đổi metric phản ánh thay đổi dữ liệu, thay vì thay đổi câu hỏi.
5. Repair thành công khi quality trở lại PASS, tập dữ liệu dựng lại khớp raw/baseline, và các metrics repaired trở về mức baseline.

## 8. Phân tích kết quả thực đo

Lần chạy cuối dùng API model `gpt-4o-mini` cho LLM Judge; Ragas chưa bật. Các giá trị dưới đây lấy từ ba file `data/results/*_metrics.json`.

| Metric/tín hiệu | Baseline | Corrupted | Repaired | Nhận xét |
| :--- | ---: | ---: | ---: | :--- |
| `retrieval_hit_rate` | 100% | 60% | 100% | Giảm 40 điểm phần trăm rồi phục hồi |
| `mean_token_f1` | 0,500 | 0,100 | 0,500 | Chất lượng câu trả lời giảm rõ rệt |
| `judge_accuracy` | 60% | 20% | 60% | LLM Judge xác nhận ít câu đúng hơn trên dữ liệu lỗi |
| `mean_judge_score` | 3,7/5 | 2,5/5 | 3,7/5 | Phục hồi về mức baseline |
| GX quality | PASS | FAIL | PASS | Dữ liệu lỗi vi phạm uniqueness và độ dài summary |
| Freshness stale ratio | 0% | 52,38% | 0% | Dữ liệu lỗi vượt ngưỡng cho phép 25% |

Sáu lỗi được tiêm đồng thời, nên kết quả chỉ chứng minh **tác động tổng hợp**; chưa thể quy mức giảm riêng cho một lỗi. Việc bỏ 5 bài mới làm mất trực tiếp một số DOI khỏi index; summary rỗng/noise và title bị cắt làm giảm thông tin dùng để tìm kiếm và trả lời. Sau khi dựng lại từ raw, Hit Rate, Token F1 và cả hai chỉ số Judge đều trở về đúng mức baseline đã đo.

**Giới hạn quan trọng:** Snapshot hiện tại có 0/24 bản ghi có `categories`; hai câu loại `category` trong test set có `ground_truth` rỗng. Vì vậy baseline Token F1 = 0,500 không thể được hiểu là chất lượng hoàn hảo của QA. Ngoài ra test set có câu `multi_hop` trong khi QA hiện tại thiên về trích xuất một tài liệu. Cần sửa dữ liệu nguồn/test set trước khi dùng các điểm số này để kết luận năng lực RAG tổng quát.

## 9. Điều học được và hướng cải thiện

- Một quality gate cần nằm **trước index** trong luồng bình thường; chỉ nhánh thí nghiệm mới được cố ý index dữ liệu FAIL để đo hậu quả.
- Tách collection giúp so sánh và repair có thể kiểm tra được, thay vì phụ thuộc vào trạng thái vector store dùng chung.
- Báo cáo phải lấy số liệu từ artifact cuối cùng và nêu giới hạn benchmark; không suy luận một lỗi đơn lẻ từ thí nghiệm tiêm nhiều lỗi cùng lúc.

Nếu có thêm thời gian, tôi sẽ tìm nguồn Crossref có `subject` thực, tạo lại hai câu `category` có ground truth và chạy lại cả ba trạng thái. Sau đó có thể thử từng lỗi riêng để ước lượng tác động của từng loại corruption.

## 10. Tự xác nhận trước khi nộp

- [x] Phần code và artifact mô tả ở trên đã được chạy, đối chiếu với kết quả thực tế.
- [x] Báo cáo không chứa API key hay nội dung `.env`.
- [ ] Tôi đã tự đọc lại và xác nhận mô tả phản ánh đúng đóng góp cá nhân của mình.
- [ ] Tôi có thể giải thích luồng end-to-end và kết quả khi bảo vệ bài.

**Họ và tên:** Nguyễn Thái Anh
**Ngày xác nhận:** 2026-09-25
