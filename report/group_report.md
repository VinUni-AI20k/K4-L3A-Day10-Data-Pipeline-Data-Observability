# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4-L3A |
| Tên nhóm | Invisible |
| Repository | https://github.com/MinMinhMin/K4-L3-DAY10-Invisible-DataPipeline |
| Ngày hoàn thành | 25/09/2026 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Vũ Quang Anh | 2A202602805 | Pipeline Integrator & Core Configuration | `src/core/config.py`, `src/core/utils.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `src/retrieval/llm.py`, `agent.py`; hai entrypoint trong `script/` |
| 2 | Vũ Đức Minh | 2A202602895 | Data Ingestion, Cleaning & Corruption | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`; dữ liệu `data/raw/`, `data/clean/` và `corruption_log.json` |
| 3 | Mai Phan Anh Tùng | 2A202602980 | Retrieval, Embedding & QA | `src/retrieval/embeddings.py`, `index.py`, `qa.py`; ChromaDB và embedding manifests |
| 4 | Nguyễn Ngọc Vĩnh | 2A202602833 | Data Observability, Evaluation & Reporting | `src/observability/quality.py`, `reporting.py`, `src/evaluation/testset.py`, `metrics.py`; quality, metrics và Markdown reports |

Báo cáo cá nhân:

- [Nguyễn Vũ Quang Anh](2A202602805_NguyenVuQuangAnh.md)
- [Vũ Đức Minh](2A202602895_VuDucMinh.md)
- [Mai Phan Anh Tùng](2A202602980_MaiPhanAnhTung.md)
- [Nguyễn Ngọc Vĩnh](2A202602833_NguyenNgocVinh.md)


## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm hoàn thiện pipeline end-to-end gồm thu thập Crossref, làm sạch dữ liệu, kiểm soát chất lượng bằng Great Expectations 1.x, lập chỉ mục ChromaDB, xây dựng benchmark 10 câu hỏi và đánh giá RAG. Baseline xử lý 24 bài báo, sinh raw/clean dataset, embedding manifest, Chroma collection, test set, các file quality, metrics và báo cáo Markdown. Kết quả đạt retrieval hit rate 100%, mean Token F1 0,9055, judge accuracy 90% và mean judge score 4,4/5; cả sáu expectation cùng freshness gate đều đạt.

Nhóm tiếp tục tiêm sáu lỗi gồm mất bản ghi mới, summary rỗng, nhiễu embedding, title bị cắt, ngày xuất bản lùi năm năm và bản ghi trùng. Tổ hợp lỗi làm retrieval hit rate giảm còn 70%, mean Token F1 còn 0,6775 và quality gate thất bại. Stale date tạo tín hiệu rõ nhất khi stale ratio tăng lên 47,62%; blank summary và duplicate rows làm hai expectation thất bại. Quy trình repair tái tạo dữ liệu từ raw snapshot, khôi phục 24 bản ghi, freshness về 4,17%, toàn bộ quality checks về PASS và metrics trở lại baseline.


## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API hoặc local snapshot
    -> raw response + PaperRecord
    -> cleaning, deduplication, age_days, text_for_embedding
    -> Great Expectations + freshness gate
    -> MiniLM embeddings + ChromaDB collection papers-baseline
    -> shared test_set.json + baseline evaluation/report
    -> sáu corruption scenarios
    -> quality FAIL + papers-corrupted + corrupted evaluation
    -> idempotent repair từ raw snapshot
    -> quality PASS + papers-repaired + repaired evaluation
    -> corruption_report.md
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` hoặc snapshot | Fetch, retry/backoff, offline fallback, parse và validate DOI | `data/raw/crossref_response.json`, `crossref_records.json` | Vũ Đức Minh |
| Cleaning | Danh sách `PaperRecord` | Chuẩn hóa text/list/date, loại bản ghi lỗi, deduplicate, tạo trường dẫn xuất | `data/clean/papers_clean.csv`, `papers_clean.json` | Vũ Đức Minh |
| Embedding/index | `text_for_embedding` | MiniLM chuẩn hóa vector, Chroma cosine, ba collection độc lập | `data/chroma/`, `data/embeddings/*.json` | Mai Phan Anh Tùng |
| Evaluation | Shared test set và ba index | Exact-title lookup, semantic search top-4, Hit Rate, Token F1, Judge | `data/eval/test_set.json`, `data/results/*metrics.json` | Nguyễn Ngọc Vĩnh |
| Observability | Baseline/corrupted/repaired DataFrame | Sáu GX expectations và freshness SLA | `data/quality/*quality_report.json`, `freshness_report.json` | Nguyễn Ngọc Vĩnh |
| Corruption/repair | Clean baseline và trusted raw snapshot | Tiêm sáu lỗi xác định; dựng lại dữ liệu sạch từ raw | Corrupted/repaired datasets, `corruption_log.json` | Vũ Đức Minh |
| Orchestration | Settings và toàn bộ module | Điều phối Phase 1/2, quản lý provider, dừng tại quality gate phù hợp | `phase1_report.md`, `corruption_report.md` | Nguyễn Vũ Quang Anh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `mock` cho lần tái hiện metrics; cấu hình mặc định hỗ trợ `gemini` |
| `LLM_MODEL` | `gemini-3.6-flash` khi dùng Gemini; không gọi model ngoài ở lần smoke test |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; stale ratio tối đa 25% |
| Random seed | Không dùng; test set và corruption chọn theo quy tắc xác định |

Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### Lệnh chạy

Thiết lập provider tái hiện và chạy baseline:

```powershell
$env:LLM_PROVIDER="mock"
python script/run_phase1.py
```

Corruption flow:

```powershell
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| `python script/run_phase1.py` | Thành công, exit code 0 | 25/09/2026 17:16 ICT | `baseline_metrics.json`, `baseline_quality_report.json`, `phase1_report.md` |
| `python script/run_corruption_flow.py` | Thành công, exit code 0 | 25/09/2026 17:10 ICT | `corruption_log.json`, corrupted/repaired metrics, `corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API: `https://api.crossref.org/works`; có local snapshot để chạy offline |
| Query/filter | `agentic retrieval augmented generation large language model`; `from-pub-date:2026-03-29,has-abstract:true` |
| Thời điểm snapshot được sử dụng | 25/09/2026 14:40 ICT |
| Số record nhận được | 24 API items → 24 `PaperRecord` → 24 clean records |
| Cơ chế retry/backoff | Tối đa 3 lần; timeout connect/read 5/30 giây; ưu tiên `Retry-After`, nếu thiếu dùng exponential backoff 0,5–1 giây; fallback snapshot khi API lỗi |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | DOI, khóa nghiệp vụ duy nhất | Loại bản ghi nếu rỗng; deduplicate không phân biệt hoa/thường |
| `title` | string | Có | Tiêu đề nghiên cứu | Bỏ HTML, chuẩn hóa khoảng trắng; loại nếu rỗng |
| `summary` | string | Có | Abstract/tóm tắt | Bỏ HTML, chuẩn hóa khoảng trắng; loại nếu rỗng |
| `authors` / `categories` | list[string] | Không | Tác giả và lĩnh vực | Khử trùng phần tử; dùng `Unknown` hoặc `Uncategorized` khi trống |
| `published` / `updated` | ISO date string | `published`: Có | Ngày công bố/cập nhật | Loại nếu published không hợp lệ; updated fallback về published |
| `abs_url` / `pdf_url` | string | Không | Liên kết abstract/PDF | URL DOI làm fallback |
| `authors_joined` / `categories_joined` | string | Dẫn xuất | Chuỗi metadata dùng cho QA/embedding | Tạo từ danh sách đã làm sạch |
| `summary_chars` | integer | Dẫn xuất | Độ dài summary | Tính lại sau cleaning |
| `age_days` | integer | Dẫn xuất | Tuổi dữ liệu tại ngày chạy | `(run_date - published).days` |
| `text_for_embedding` | string | Có | Nội dung chuẩn đưa vào MiniLM | Dựng lại từ năm trường có nhãn |

### Quy tắc cleaning

| Quy tắc | Quality dimension liên quan | Số record bị tác động | Cách xác minh |
| --- | --- | ---: | --- |
| Loại record thiếu DOI/title/summary/published | Completeness, validity | 0 trong snapshot hiện tại | 24 raw records và 24 clean records |
| Khử trùng lặp theo `paper_id` | Uniqueness | 0 trong baseline | `paper_id_unique` PASS, unexpected count 0 |
| Bỏ HTML, unescape và gom khoảng trắng | Validity, consistency | 24 record được kiểm tra | Không còn markup trong clean JSON |
| Chuẩn hóa authors/categories và tạo trường joined | Consistency | 24 | Schema trong `papers_clean.json` |
| Chuẩn hóa ngày và tính `age_days` | Validity, freshness | 24 | Không có age không hợp lệ; freshness report PASS |
| Tạo `text_for_embedding` theo template chung | Consistency | 24 | `text_for_embedding_not_null` PASS |

`text_for_embedding` được ghép theo thứ tự cố định: `Title`, `Authors`, `Published`, `Categories`, `Summary`, mỗi trường nằm trên một dòng có nhãn. Khóa nghiệp vụ là DOI trong `paper_id`; ID vật lý khi nạp Chroma có dạng `<paper_id>::<row_index>` để collection vẫn tiếp nhận được dữ liệu corruption có DOI trùng. Trường `paper_id` tiếp tục được lưu trong metadata để evaluation đối chiếu ground truth. `age_days` được tính bằng chênh lệch số ngày giữa thời điểm chạy UTC và ngày `published`.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10, gồm 2 câu cho mỗi loại |
| Các `question_type` | `summary`, `authors`, `date`, `category`, `multi_hop` |
| Ground-truth document ID | Lấy trực tiếp từ `paper_id` của clean DataFrame; multi-hop giữ hai DOI |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2`, vector được normalize |
| Vector store/collection | Chroma cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | Lần tái hiện dùng `mock` và heuristic judge fallback; cấu hình production là Gemini `gemini-3.6-flash` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

Một test set bất biến bảo đảm biến độc lập duy nhất giữa ba lượt đánh giá là trạng thái dữ liệu/index. Nếu tạo lại câu hỏi sau corruption, các tài liệu bị mất hoặc hỏng sẽ biến mất khỏi ground truth và che giấu suy giảm. Vì vậy cả ba collection đều được chấm bằng cùng câu hỏi, câu trả lời chuẩn và DOI chuẩn từ baseline.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/crossref_response.json`, `crossref_records.json` | Có | 24 bản ghi nguồn |
| Cleaned dataset | `data/clean/papers_clean.csv`, `papers_clean.json` | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | Collection `papers-baseline` |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu, 5 loại |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | Metrics trên shared test set |
| Quality/freshness | `data/quality/baseline_quality_report.json`, `freshness_report.json` | Có | GX và freshness đều PASS |
| Baseline report | `data/reports/phase1_report.md` | Có | Tổng hợp source, metrics và quality |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1,0000 (100%) | Cả 10 câu đều truy xuất được ít nhất một DOI ground truth trong top-4 |
| `mean_token_f1` | 0,9055 | Mức chồng lấp token trung bình cao giữa đáp án và ground truth |
| `judge_accuracy` | 0,9000 (90%) | 9/10 đáp án được trường judge đánh giá đạt; evaluator chủ yếu dùng heuristic fallback |
| `mean_judge_score` | 4,4000/5 | Điểm judge trung bình của 10 đáp án |
| Ragas | N/A | Chủ động bỏ qua; chỉ chạy khi đặt `RUN_RAGAS=1` vì cần thêm thời gian/provider |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| Row count | Volume | 5–5000 dòng | PASS: 24 | `baseline_quality_report.json` |
| `paper_id` not null | Completeness | 0 giá trị null/rỗng | PASS: 0 unexpected | Cùng quality report |
| `title` not null | Completeness | 0 giá trị null/rỗng | PASS: 0 unexpected | Cùng quality report |
| `text_for_embedding` not null | Completeness | 0 giá trị null/rỗng | PASS: 0 unexpected | Cùng quality report |
| `paper_id` unique | Uniqueness | 100% duy nhất | PASS: 0 unexpected | Cùng quality report |
| Summary length | Content validity | Tối thiểu 30 ký tự | PASS: 0 unexpected | Cùng quality report |

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | `age_days` của `data/clean/papers_clean.json` |
| Ngày công bố mới nhất / cũ nhất | 22/07/2026 / 28/03/2026 |
| Ngưỡng freshness | Một bài stale khi `age_days > 180`; toàn tập cho phép tối đa 25% stale |
| Trạng thái baseline | Fresh — PASS |
| Lý do | 1/24 bài stale, tương đương 4,17%; không có dòng có age không hợp lệ |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | ---: | --- | --- | --- |
| Drop latest records | Xóa 20% bài có `published` mới nhất | 5 | Latest date lùi, coverage giảm | Latest date từ 22/07 xuống 12/06/2026; toàn suite làm Hit Rate còn 70% | Dựng lại đủ record từ raw snapshot |
| Blank summary | Gán summary rỗng và `summary_chars=0` | 3 | Summary length FAIL | FAIL với 3 unexpected rows | Parse lại summary gốc |
| Inject text noise | Nối tám cụm ký tự rác vào vector text | 3 | Semantic relevance giảm; GX hiện tại không có check noise | Không có GX trực tiếp; toàn suite làm Token F1 giảm 0,2280 | Dựng lại `text_for_embedding` từ trường sạch |
| Truncate title | Cắt title còn tối đa 7 ký tự | 3 | Khả năng exact-title lookup giảm | `title_not_null` vẫn PASS; đây là khoảng trống của quality suite | Khôi phục title từ raw |
| Stale date | Lùi `published` đúng 5 năm và tăng `age_days` | 8 | Freshness FAIL | 10/21 dòng stale sau khi tính cả duplicate; ratio 47,62% | Tính lại ngày và age từ raw |
| Duplicate rows | Nối thêm bản sao giữ nguyên `paper_id` | 2 bản sao | Uniqueness FAIL | FAIL, GX ghi nhận 4 dòng thuộc các giá trị trùng | Cleaning deduplicate theo DOI |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đủ sáu loại, số lượng, danh sách DOI, tham số noise, title cũ, ngày cũ và số năm bị lùi. Dataset biến đổi từ 24 thành 21 dòng do xóa 5 rồi thêm 2 bản sao.

Repair không sửa trực tiếp từng ô corrupted và không xóa cảnh báo khỏi report. Pipeline nạp lại `data/raw/crossref_records.json`, dựng DataFrame mới qua cùng hàm `build_clean_dataframe()`, lưu artifact repaired riêng, rồi tạo collection `papers-repaired` mới. Sau đó hệ thống chạy lại toàn bộ GX, freshness và benchmark dùng chung. Việc repaired dataset trở về 24 DOI duy nhất, quality 6/6 PASS và metrics bằng baseline chứng minh dữ liệu đã được tái tạo từ nguồn tin cậy. Chạy repair nhiều lần cho cùng raw snapshot vẫn cho cùng tập bản ghi nên quy trình có tính idempotent.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 100% | 70% | 100% | −30 điểm % | +30 điểm %; 100% phần mất | Mất tài liệu/title làm ba câu không còn retrieval hit |
| `mean_token_f1` | 0,9055 | 0,6775 | 0,9055 | −0,2280 | +0,2280; 100% | Chất lượng đáp án giảm và được phục hồi hoàn toàn |
| `judge_accuracy` | 90% | 70% | 90% | −20 điểm % | +20 điểm %; 100% | Judge phản ánh cùng xu hướng |
| `mean_judge_score` | 4,4 | 3,4 | 4,4 | −1,0 | +1,0; 100% | Điểm trung bình trở lại baseline |
| Quality checks | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Mất 2 expectation | Khôi phục 2/2 | Summary length và uniqueness phát hiện lỗi |
| Freshness status | PASS, 4,17% | FAIL, 47,62% | PASS, 4,17% | +43,45 điểm % stale | −43,45 điểm %; 100% | Stale-date vượt ngưỡng 25% |

1. Việc xóa 5 bài mới nhất, phá nội dung vector và title làm coverage của index giảm → freshness/quality chuyển sang FAIL → retrieval hit rate giảm 30 điểm phần trăm và Token F1 giảm 0,2280 trên cùng test set.
2. Việc dựng lại dữ liệu từ raw snapshot khôi phục 24 DOI duy nhất và summary hợp lệ → GX trở về 6/6 PASS, stale ratio từ 47,62% về 4,17% → toàn bộ bốn metrics trở lại đúng mức baseline.
3. Title bị cắt và vector noise chưa bị các expectation hiện tại phát hiện trực tiếp, dù metrics suy giảm trong toàn suite. Vì các lỗi được tiêm đồng thời, báo cáo chỉ kết luận quan hệ nhân quả ở cấp suite; muốn quy trách nhiệm riêng từng lỗi cần chạy ablation từng scenario.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Lệnh kiểm tra vector store ban đầu báo `TypeError: LocalEmbeddingIndex.__init__() missing 2 required positional arguments: 'documents' and 'persist_path'`; trước đó evaluation cũng không chạy vì chưa có `papers_clean.json`.
- **Nguyên nhân:** Constructor starter yêu cầu hai chi tiết nội bộ không xuất hiện trong API lab, trong khi `phase1.py` chưa điều phối thứ tự tạo clean artifact trước khi build index.
- **Cách xử lý:** Cho `documents` và `persist_path` giá trị mặc định, bổ sung `build_from_clean()`, rồi triển khai orchestration theo thứ tự ingest → clean → quality gate → index → test set → evaluation → report. Phase 2 dùng collection và artifact riêng để tránh ghi đè baseline.
- **Cách xác minh:** `python script/run_phase1.py` và `python script/run_corruption_flow.py` đều exit code 0; semantic search trả kết quả, ba metrics file và hai Markdown report được sinh thành công.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Corpus chỉ có 24 bài và dùng snapshot | Metrics có thể cao do miền dữ liệu nhỏ, chưa đại diện production drift | Chạy nhiều snapshot theo tháng, tăng cỡ mẫu và báo confidence interval |
| Lần tái hiện dùng heuristic judge; Ragas bị tắt | Judge chưa đo đầy đủ ngữ nghĩa và faithfulness | Thêm timeout/retry rõ ràng, cố định model evaluator và chạy `RUN_RAGAS=1` trong job có API credential |
| GX chưa kiểm tra title quá ngắn và text noise | Hai corruption có thể qua quality gate nếu đứng độc lập | Thêm expectation độ dài title, regex/noise ratio và embedding-distribution drift; kiểm thử từng lỗi riêng |
| Sáu corruption được tiêm đồng thời | Không định lượng chính xác đóng góp của từng lỗi vào metric drop | Chạy ablation: một collection cho mỗi scenario và bảng effect size riêng |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Đã tạo báo cáo vai trò riêng cho mỗi thành viên.
- [x] Mỗi thành viên đã tự đọc và xác nhận phần cam kết trong báo cáo cá nhân.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
