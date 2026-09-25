# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Hoàng Lê Nguyên |
| MSSV | `2A202602472` |
| Khóa/Lớp | K4 — L3A |
| Nhóm | `1Prompt4All` — K4-L3-DAY10 |
| Vai trò chính | Trưởng nhóm / Pipeline Integrator |
| Repository | [GitHub repository](https://github.com/D3vNguy3n/K4-L3A-Day10-Data-Pipeline-Data-Observability) |
| Ngày hoàn thành kỹ thuật | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cấu hình pipeline | `src/core/config.py`, `load_settings()` | `.env`, project root | Toàn bộ đường dẫn artifact và runtime settings | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py`, `main()` | Raw records/snapshot | Clean data, quality report, baseline index, metrics và report | Hoàn thành |
| Corruption/repair orchestration | `src/pipelines/corruption_flow.py`, `main()` | Baseline artifacts và fixed test set | Corrupted/repaired datasets, metrics và comparison report | Hoàn thành |
| Entrypoint và nghiệm thu | `script/run_phase1.py`, `script/run_corruption_flow.py` | Môi trường Python 3.12 | Hai flow exit code 0 và bộ artifact đầy đủ | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất data contract | Ingestion, retrieval và observability | Các module dùng chung `paper_id`, `text_for_embedding` và artifact paths |
| Kiểm tra Chroma lifecycle | RAG & Vector Index | Ba collection độc lập, mỗi collection 24 documents; chạy lặp không tăng số segment |
| Đối chiếu báo cáo với artifact | Observability & Evaluation | Số liệu Markdown khớp các JSON metrics/quality reports |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép baseline flow | `src/pipelines/phase1.py` | 24 clean records, quality/freshness pass, baseline metrics | `python script/run_phase1.py` |
| Ghép corruption và repair flow | `src/pipelines/corruption_flow.py` | Bảng so sánh đủ ba trạng thái | `python script/run_corruption_flow.py` |
| Kiểm tra repair idempotent | `papers_clean_repaired.json`, `repaired_metrics.json` | SHA-256 không đổi qua hai lần chạy | Chạy corruption flow hai lần và so checksum |
| Kiểm tra artifact contract | `data/` và ba Chroma collections | Đủ artifacts; mỗi collection có 24 documents | Đọc JSON và kiểm tra Chroma client |

Output tiêu biểu là `data/reports/corruption_report.md`: báo cáo cho thấy baseline đạt hit rate 100%, corrupted giảm về 0% và repaired phục hồi về 100%, đồng thời quality/freshness chuyển trạng thái `PASSED → FAILED → PASSED`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module ingestion, cleaning, observability, retrieval và evaluation tạo ra nhiều artifact phụ thuộc lẫn nhau. Vai trò Pipeline Integrator phải bảo đảm chúng chạy đúng thứ tự, chỉ index dữ liệu baseline sau khi quality gate đã pass, dùng cùng một test set cho cả ba trạng thái và repair từ raw lineage thay vì từ dữ liệu đã bị corruption.

### Cách triển khai

Baseline flow thực hiện: load/fetch raw records → cleaning → ghi clean CSV/JSON → chạy GX và freshness → tạo/load fixed benchmark → build collection `papers-baseline` → evaluate → sinh báo cáo.

Corruption flow thực hiện: đọc clean baseline → tiêm sáu loại lỗi → ghi corruption log → chạy quality/freshness trên dữ liệu lỗi → build collection `papers-corrupted` → evaluate → tái tạo clean data từ `crossref_records.json` → chạy lại quality → build `papers-repaired` → evaluate cùng benchmark → sinh báo cáo đối chiếu.

Pipeline dừng bằng exception nếu baseline hoặc repaired data không vượt quality/freshness gate. Corrupted data vẫn được index trong collection cô lập vì mục tiêu thí nghiệm là đo silent failure mà không làm bẩn baseline collection.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `data/raw/crossref_records.json`, settings và fixed `data/eval/test_set.json` |
| Output | Clean/corrupted/repaired artifacts, ba Chroma collections, metrics và Markdown reports |
| Module phụ thuộc | `ingestion`, `observability`, `retrieval`, `evaluation` |
| Module sử dụng output | Reporting, demo retrieval và quy trình nghiệm thu |
| Điều kiện lỗi | Raw artifact thiếu, quality gate fail ở baseline/repair, collection rỗng hoặc contract cột sai |

### Cách xác minh

```powershell
uv sync --python 3.12 --extra dev
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Hai lệnh exit code 0; baseline và repaired pass, corrupted fail; metrics repaired trở về baseline.
- **Kết quả thực tế:** Baseline hit rate/F1 = `1.000/1.000`; corrupted = `0.000/0.007`; repaired = `1.000/1.000`.
- **Artifact/log:** `data/results/`, `data/quality/`, `data/reports/`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Nếu build corrupted data vào cùng collection baseline thì kết quả ba trạng thái bị lẫn và không thể so sánh công bằng.
- **Các phương án đã cân nhắc:** Ghi đè một collection duy nhất rồi build lại; hoặc dùng ba collection riêng biệt.
- **Phương án đã chọn:** Dùng `papers-baseline`, `papers-corrupted`, `papers-repaired` độc lập nhưng cùng embedding model và test set.
- **Lý do:** Cô lập trạng thái, tránh contamination, dễ audit và vẫn giữ phép so sánh cùng cấu hình.
- **Bằng chứng:** ChromaDB có đúng ba collection, mỗi collection 24 documents; baseline/repaired metrics giống nhau trong khi corrupted metrics giảm rõ rệt.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Import NumPy/ChromaDB thất bại với lỗi `No module named 'numpy._core._multiarray_umath'`.
- **Bước tái hiện:** Chạy import dependencies bằng `.venv\Scripts\python.exe` trong môi trường ban đầu.
- **Nguyên nhân gốc:** `.venv` dùng Python 3.14 nhưng các native wheels được cài cho CPython 3.12; Python 3.14 cũng nằm ngoài constraint `<3.14` của dự án.
- **Cách xử lý:** Tái tạo virtual environment bằng `uv sync --python 3.12 --extra dev`.
- **Cách xác minh:** Import ChromaDB, Great Expectations và Sentence Transformers thành công; hai entrypoint chạy exit code 0.
- **Điều học được:** Với dependency có native extension, phiên bản interpreter và ABI của wheel phải đồng nhất; lockfile không thay thế việc chọn đúng Python runtime.

## 7. Hiểu biết về luồng end-to-end

1. Crossref payload được parse và bảo toàn thành raw artifacts. Cleaning chuẩn hóa text/date, tính `age_days`, deduplicate DOI và tạo `text_for_embedding`. Quality/freshness được kiểm tra trước khi MiniLM tạo vector và ChromaDB lưu document.
2. Mỗi câu benchmark có `ground_truth` và `ground_truth_doc_ids`. Hit rate đo xem retrieval có lấy được đúng document; token F1 đo mức trùng token giữa câu trả lời và đáp án; judge metric bổ sung đánh giá correctness.
3. Quality checks kiểm tra contract nội tại như row count, null, uniqueness và summary length. Freshness monitoring kiểm tra tính thời gian: tỷ lệ records có `age_days > 180` không được vượt 25%.
4. Ba trạng thái phải dùng cùng test set để biến độc lập duy nhất là chất lượng dữ liệu/index. Nếu đổi câu hỏi thì delta metrics không còn chứng minh tác động của corruption và repair.
5. Repair thành công khi repaired clean artifact tái tạo từ raw, quality/freshness cùng pass, collection repaired đủ 24 documents và metrics trở về đúng baseline. Chạy lại repair phải cho cùng clean data và repaired metrics.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.000 | 1.000 | Mất các ground-truth documents làm retrieval thất bại hoàn toàn |
| `mean_token_f1` | 1.000 | 0.007 | 1.000 | Câu trả lời trên dữ liệu lỗi gần như không còn trùng đáp án |
| `judge_accuracy` | 1.000 | 0.000 | 1.000 | Correctness giảm theo retrieval quality |
| `mean_judge_score` | 5.000 | 1.000 | 5.000 | Corrupted chỉ đạt mức tối thiểu |
| Quality checks | PASSED | FAILED | PASSED | Corrupted vi phạm summary length và uniqueness |
| Freshness status | PASSED | FAILED | PASSED | Stale ratio đổi từ 4.2% lên 100%, sau repair về 4.2% |

### Kết luận từ số liệu

1. Drop latest records, blank summaries, vector noise, truncated titles, stale dates và duplicates → GX thất bại, stale ratio tăng lên 100% → hit rate giảm từ 100% xuống 0% và token F1 gần 0.
2. Repair từ preserved raw records → quality/freshness phục hồi → hit rate, token F1 và judge metrics trở về đúng baseline.

Corruption ảnh hưởng rõ nhất là drop latest records vì benchmark chủ động bám vào năm tài liệu mới nhất; khi các ground-truth documents này bị loại khỏi corrupted index, hit rate chắc chắn về 0%. Noise, blank summary và duplicate tiếp tục làm giảm chất lượng câu trả lời cũng như kích hoạt quality gate.

Điểm khác kỳ vọng ban đầu là ANN có thể phân giải các noisy near-ties khác nhau giữa những lần chạy, làm corrupted token F1 dao động rất nhỏ. Nhóm kiểm tra bằng cách neo benchmark vào các document bị drop; nhờ vậy retrieval hit rate vẫn ổn định ở 0%, còn kết luận suy giảm/phục hồi không thay đổi.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Pipeline đáng tin cậy cần raw lineage và artifact contract rõ ràng; repair không nên phụ thuộc vào dữ liệu đã bị lỗi.
2. Data quality và freshness bổ sung cho nhau: dữ liệu có thể đúng schema nhưng vẫn quá cũ để phục vụ RAG.
3. Agent vẫn có thể trả lời trôi chảy khi retrieval sai, nên chất lượng dữ liệu phải được đo bằng metric và gate thay vì cảm nhận từ demo.

### Nếu có thêm thời gian

Nhóm có thể bổ sung câu hỏi `multi_hop` để đồng thời thỏa nội dung trong `day10.txt`, bật `RUN_RAGAS=1`, cấu hình LLM judge bằng credential hợp lệ và chạy nhiều seed để báo cáo phân phối metrics thay vì một lần chạy.

## 10. Cam kết của thành viên

Nguyễn Hoàng Lê Nguyên xác nhận:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hoàng Lê Nguyên
**Ngày xác nhận:** 2026-09-25
