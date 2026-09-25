# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Trương Thị Lan Anh |
| MSSV | 2A202602451 |
| Khóa/Lớp | K4-L3A |
| Tên nhóm | TruongGiang |
| Vai trò chính | Pipeline Lead & Integrator; Data Foundation Owner |
| Repository | https://github.com/SxAinsworth/K4-L3A-Day10-TruongGiang |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Data foundation và ingestion | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref API hoặc snapshot `data/raw/crossref_response.json` | 24 `PaperRecord`, `crossref_records.json`; retry và offline fallback | Hoàn thành |
| Cleaning và data model | `src/ingestion/cleaning.py`: `build_clean_dataframe` | Danh sách `PaperRecord`, thời điểm chạy | DataFrame sạch, `age_days`, `text_for_embedding`, CSV/JSON | Hoàn thành |
| Quality gate và freshness | `src/observability/quality.py` | Clean/corrupted/repaired DataFrame | Báo cáo GX 1.x và Freshness SLA | Hoàn thành |
| Benchmark và vector retrieval | `src/evaluation/testset.py`, `src/retrieval/embeddings.py`, `src/retrieval/index.py`, `src/retrieval/qa.py` | Dữ liệu sạch, MiniLM | 10 câu benchmark, 24 vectors ChromaDB, API search/QA | Hoàn thành |
| Pipeline tích hợp | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | Cấu hình và artifacts ở từng giai đoạn | Hai luồng end-to-end có thể chạy lại bằng một lệnh | Hoàn thành |
| Corruption, repair và báo cáo | `src/ingestion/corruption.py`, `src/observability/reporting.py` | Baseline clean data và raw snapshot | 6 lỗi có log, repaired data, metrics và hai báo cáo Markdown | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Debug môi trường Windows | Embedding/evaluation stack | Tránh đường import `datasets → PyArrow` bị Application Control chặn; MiniLM inference chạy ổn định qua Transformers |
| Chuẩn hóa API checkpoint | `core.config`, `evaluation.testset`, `retrieval.index` | Bổ sung `test_set_json`, `BenchmarkTestSet.samples`, `build_from_clean()` và `semantic_search()` mà vẫn giữ API cũ |
| Tích hợp và xác minh artifacts | Toàn pipeline | Chạy thành công `run_phase1.py` và `run_corruption_flow.py`; đối chiếu file, số dòng, collection count và metrics |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Xây pipeline baseline | `src/pipelines/phase1.py` | 24 bản ghi sạch, 24 vectors, 10 câu benchmark, metrics và report | `python script/run_phase1.py` |
| Dựng Data Quality Gate | `src/observability/quality.py` | Baseline pass 6/6 expectations; freshness pass | `data/quality/baseline_quality_report.json` |
| Tiêm sáu lỗi dữ liệu | `src/ingestion/corruption.py` | 22 dòng corrupted, 3 DOI trùng, 6 summary rỗng tính cả bản sao, 3 vector nhiễu, 3 title ngắn, 45.45% stale | `data/results/corruption_log.json` |
| Đo Silent Failure | `data/results/corrupted_metrics.json` | Hit Rate 0.8; Token F1 0.6979; Judge Accuracy 0.8; Judge Score 3.6 | `python script/run_corruption_flow.py` |
| Repair idempotent | `src/pipelines/corruption_flow.py` | Rebuild từ raw snapshot; quality/freshness pass; metrics phục hồi về baseline | `data/results/repaired_metrics.json` |
| Sinh báo cáo | `src/observability/reporting.py` | `phase1_report.md` và `corruption_report.md` khớp artifacts | Đối chiếu `data/reports/` và `data/results/` |

Output tiêu biểu là `data/reports/corruption_report.md`. Báo cáo thể hiện cùng lúc suy giảm do dữ liệu bẩn và mức phục hồi sau repair: Retrieval Hit Rate `1.0 → 0.8 → 1.0`, Mean Token F1 `1.0 → 0.6979 → 1.0`, Quality Gate `True → False → True`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần thu thập dữ liệu Crossref không ổn định, chuẩn hóa thành schema dùng chung, chặn dữ liệu kém chất lượng trước khi index, xây vector store và benchmark, sau đó chứng minh dữ liệu bẩn có thể làm RAG suy giảm dù chương trình vẫn chạy. Cuối cùng, hệ thống phải phục hồi được từ raw snapshot theo cách có thể lặp lại.

### Cách triển khai

Luồng baseline ưu tiên raw artifact đã lưu để bảo đảm tái lập; chỉ gọi Crossref khi cần refresh. Parser chuẩn hóa DOI, văn bản, JATS/XML, tác giả, chuyên ngành và ngày ISO. Cleaning khử trùng theo `paper_id`, tính `age_days`, sau đó ghép năm trường title/authors/published/categories/summary thành `text_for_embedding`.

Quality Gate dùng API Great Expectations 1.x với ephemeral context. Sáu lượt validation được tạo từ bốn loại expectation: row count, not-null trên ba cột, unique DOI và minimum summary length. Freshness được theo dõi riêng bằng tỷ lệ `age_days > 180`; tỷ lệ trên 25% làm `is_fresh=False` và khiến overall gate thất bại.

MiniLM sinh vector chuẩn hóa L2 và ChromaDB lưu ba collection tách biệt: baseline, corrupted, repaired. Benchmark gồm 10 câu thuộc năm loại, trong đó multi-hop tham chiếu hai DOI. Corruption được thực hiện xác định để demo có thể tái lập; sau đó repair luôn rebuild từ raw record, không sửa chắp vá trên corrupted data.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Crossref work-list JSON hoặc `crossref_records.json`; `Settings`; run time UTC |
| Output | Clean/corrupted/repaired DataFrame; Chroma collections; JSON metrics; Markdown reports |
| Module phụ thuộc | `core.config`, `core.utils`, pandas, Great Expectations 1.x, Transformers, ChromaDB |
| Module sử dụng output | Test-set builder, vector index, QA evaluator, quality/reporting pipelines |
| Điều kiện lỗi cần xử lý | Mất mạng/HTTP 429, API trả thiếu bản ghi, DOI/title/date thiếu, artifact chưa tồn tại, duplicate, summary ngắn, dữ liệu stale, PyArrow DLL bị chặn |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); idx=LocalEmbeddingIndex.load(s); print(idx.collection.count())"
```

- **Kết quả mong đợi:** baseline pass và đủ 24 vectors; corrupted suy giảm và bị quality gate chặn; repaired pass và phục hồi metric.
- **Kết quả thực tế:** baseline 24 records/24 vectors/10 questions; corrupted Hit Rate 0.8 và Quality Gate False; repaired Hit Rate 1.0 và Quality Gate True.
- **Artifact/log:** `data/results/*.json`, `data/quality/*.json`, `data/reports/*.md`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair có thể sửa trực tiếp corrupted DataFrame hoặc rebuild từ raw snapshot.
- **Các phương án đã cân nhắc:** (1) vá từng ô bị lỗi dựa trên corruption log; (2) tái tạo toàn bộ clean data từ `crossref_records.json` rồi xây collection mới.
- **Phương án đã chọn:** Rebuild từ raw snapshot và ghi vào artifacts/collection repaired riêng.
- **Lý do:** Cách này idempotent, tránh bỏ sót lỗi ẩn, không làm baseline bị nhiễm bẩn và cho phép chạy lại với cùng contract. Chi phí encode lại 24 tài liệu nhỏ hơn rủi ro sửa chắp vá sai.
- **Bằng chứng quyết định phù hợp:** Repaired Quality Gate chuyển từ `False` thành `True`; stale ratio từ `45.45%` về `0%`; Hit Rate và Token F1 đều phục hồi về `1.0`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ImportError: The pyarrow installation is not built with support for 'dataset' (DLL load failed while importing _json: An Application Control policy has blocked this file.)`
- **Lệnh tái hiện:** Import `sentence_transformers` hoặc `evaluation.metrics` trên máy lab khi package tự nạp `datasets/pyarrow`.
- **Nguyên nhân gốc:** SentenceTransformers 6 import training stack dù tác vụ chỉ cần inference; Windows Application Control chặn DLL `_json.pyd` của PyArrow.
- **Cách xử lý:** Chuyển `datasets` sang lazy import chỉ khi bật Ragas; dùng đúng trọng số `sentence-transformers/all-MiniLM-L6-v2` qua `AutoTokenizer`/`AutoModel`, mean pooling và L2 normalization; chuyển package exports sang lazy import.
- **Cách xác minh sau khi sửa:** Xây `papers-baseline` thành công với 24 vectors và đạt 10/10 retrieval hits trong top 4.
- **Điều học được:** Dependency tùy chọn của đường training không nên trở thành dependency bắt buộc của inference; lazy import giúp giảm failure surface trên môi trường bị quản trị.

## 7. Hiểu biết về luồng end-to-end

1. Crossref được gọi với query/filter/rows. Nếu mạng lỗi hoặc API quá tải, ingestion đọc snapshot local. Payload được parse thành `PaperRecord`, cleaning chuẩn hóa và tạo `text_for_embedding`, GX kiểm tra dữ liệu, rồi MiniLM biến từng document thành vector để nạp vào ChromaDB.
2. Mỗi benchmark item chứa câu hỏi, đáp án chuẩn và một hoặc hai `ground_truth_doc_ids`. Retrieval Hit Rate kiểm tra top-k có chứa DOI chuẩn hay không; Token F1 và LLM Judge so sánh câu trả lời với ground truth.
3. Quality checks kiểm tra cấu trúc và nội dung như số dòng, null, unique và summary length. Freshness monitoring kiểm tra tính thời gian bằng `age_days` và tỷ lệ stale. Một tập dữ liệu có thể đúng schema nhưng vẫn quá cũ.
4. Baseline, corrupted và repaired phải dùng cùng test set để metric chỉ phản ánh thay đổi dữ liệu/index. Nếu đổi câu hỏi giữa các lần chạy thì không thể quy sự thay đổi cho corruption hoặc repair.
5. Repair thành công khi repaired clean artifacts được tạo lại từ raw, Quality Gate/Freshness cùng pass, collection repaired đủ 24 documents và các metric trở về baseline. Trong thực nghiệm, Hit Rate và Token F1 đều phục hồi từ `0.8/0.6979` lên `1.0/1.0`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | Drop tài liệu và làm hỏng nội dung khiến 20% câu hỏi mất ground-truth hit; repair phục hồi hoàn toàn. |
| `mean_token_f1` | 1.0000 | 0.6979 | 1.0000 | Summary rỗng, title bị cắt và ngày stale làm đáp án sai dù hệ thống không crash. |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | LLM Judge xác nhận suy giảm chất lượng câu trả lời trên corrupted data. |
| `mean_judge_score` | 5.00 | 3.60 | 5.00 | Mức giảm 1.4 điểm thể hiện Silent Failure có ý nghĩa. |
| Quality checks | Pass, 6/6 | Fail, 4/6 | Pass, 6/6 | GX phát hiện duplicate và summary không đạt độ dài. |
| Freshness status | True, 0% stale | False, 45.45% stale | True, 0% stale | Freshness SLA phát hiện lỗi thời gian mà expectation cấu trúc không phản ánh đầy đủ. |

### Kết luận từ số liệu

1. Sáu loại data corruption → GX thất bại và stale ratio tăng từ `0%` lên `45.45%` → Hit Rate giảm còn `0.8`, Token F1 còn `0.6979`, Judge Score còn `3.6`.
2. Rebuild clean data/index từ raw snapshot → Quality Gate và Freshness trở lại `True` → Hit Rate, Token F1 và Judge Accuracy phục hồi về `1.0`.

Corruption ảnh hưởng rõ nhất là drop latest records kết hợp blank summary/truncate title. Drop làm ground-truth document biến mất hoàn toàn khỏi index, trong khi các lỗi nội dung làm document còn tồn tại nhưng embedding và đáp án bị sai. Đây chính là Silent Failure: chương trình vẫn trả lời nhưng chất lượng giảm.

Kết quả khác kỳ vọng ban đầu là số dòng sau corruption là 22 thay vì tăng so với 24, vì bỏ 5 bản ghi mới nhất rồi thêm lại 3 bản sao (`24 - 5 + 3 = 22`). Điều này được xác minh từ `corruption_log.json`; duplicate vẫn tồn tại dù tổng số dòng giảm.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw preservation, schema contract và idempotent processing quan trọng hơn việc chỉ làm cho pipeline chạy được một lần.
2. Data quality và freshness là hai trục observability khác nhau; cần giám sát cả hai trước khi index.
3. RAG phụ thuộc trực tiếp vào chất lượng dữ liệu: lỗi không gây exception vẫn có thể làm retrieval và câu trả lời suy giảm đáng kể.

### Nếu có thêm thời gian

Tôi sẽ bổ sung kiểm thử tự động cho từng corruption scenario và metric threshold trong CI, ví dụ baseline Hit Rate phải đạt ít nhất 0.9, corrupted gate bắt buộc fail, repaired metrics phải sai lệch không quá 0.01 so với baseline. Cải thiện được đo bằng tỷ lệ test ổn định qua nhiều lần chạy và thời gian phát hiện regression trước khi merge.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Trương Thị Lan Anh  
**Ngày xác nhận:** 2026-09-25
