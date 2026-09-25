# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
|---|---|
| Khóa/Lớp | K4-L3A |
| Tên nhóm | TruongGiang |
| Repository | https://github.com/SxAinsworth/K4-L3A-Day10-TruongGiang |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
|---:|---|---|---|---|
| 1 | Trương Thị Lan Anh | 2A202602451 | Pipeline Lead & Integrator; Data Foundation Owner | `ingestion/crossref.py`, `ingestion/cleaning.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`; raw/clean artifacts và orchestration |
| 2 | Đinh Thị Minh Tâm | 2A202602433 | Observability & Evaluation Lead | `observability/quality.py`, `observability/reporting.py`, `evaluation/testset.py`, `evaluation/metrics.py`; quality, benchmark, metrics và reports |
| 3 | Tạ Quang Dũng | 2A202602588 | RAG & Agent Specialist | `retrieval/embeddings.py`, `retrieval/index.py`, `retrieval/qa.py`, `retrieval/agent.py`; MiniLM, ChromaDB và QA Agent |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thiện pipeline dữ liệu end-to-end từ Crossref đến RAG evaluation, bao gồm cơ chế offline fallback, cleaning, Great Expectations 1.x Quality Gate, Freshness SLA, MiniLM embedding, ChromaDB, benchmark 10 câu hỏi, corruption suite và idempotent repair. Baseline tạo đủ raw/clean artifacts, collection `papers-baseline` gồm 24 vectors, test set cố định, metrics JSON và báo cáo Markdown. Trên dữ liệu sạch, Retrieval Hit Rate, Mean Token F1 và Judge Accuracy đều đạt `1.0`, Mean Judge Score đạt `5.0/5`; Quality Gate và Freshness đều pass.

Sáu kịch bản corruption gồm drop latest, blank summary, text noise, truncate title, stale date và duplicate rows. Tác động rõ nhất đến agent đến từ việc mất document kết hợp hỏng nội dung: Hit Rate giảm còn `0.8`, Token F1 còn `0.6979`, Judge Score còn `3.6`. Freshness chuyển sang fail với 10/22 dòng stale (`45.45%`) và GX phát hiện duplicate/summary không đạt chuẩn. Repair rebuild dữ liệu và vector index từ raw snapshot đáng tin cậy, đưa toàn bộ metrics về mức baseline và Quality Gate/Freshness về pass. Giới hạn chính là dữ liệu Crossref live có thể thiếu `subject`, còn Ragas bị tắt mặc định do PyArrow DLL bị Windows Application Control chặn; các metric cốt lõi vẫn được chạy đầy đủ.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API
    -> retry/backoff hoặc offline snapshot
    -> raw response + normalized PaperRecord
    -> cleaning, deduplication, age_days, text_for_embedding
    -> GX 1.x Quality Gate + Freshness SLA
    -> MiniLM embedding + ChromaDB papers-baseline
    -> benchmark evaluation + baseline report
    -> deterministic six-scenario corruption
    -> GX/freshness + papers-corrupted + re-evaluation
    -> rebuild từ preserved raw records
    -> GX/freshness + papers-repaired + re-evaluation
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
|---|---|---|---|---|
| Ingestion | Crossref API/snapshot | Fetch, retry, parse DOI/JATS/date, fallback offline | `data/raw/crossref_response.json`, `crossref_records.json` | Trương Thị Lan Anh |
| Cleaning | `PaperRecord` | Normalize, deduplicate DOI, tính age, tạo embedding text | `data/clean/papers_clean.csv/json` | Trương Thị Lan Anh |
| Embedding/index | Clean DataFrame | Mean pooling MiniLM, L2 normalize, cosine Chroma index | `data/chroma/`, `data/embeddings/*.json` | Tạ Quang Dũng |
| Evaluation | Index + fixed test set | Top-k hit, Token F1, LLM Judge | `data/results/*metrics.json`, `*answers.json` | Đinh Thị Minh Tâm |
| Observability | DataFrame mỗi trạng thái | GX expectations và freshness ratio | `data/quality/*.json` | Đinh Thị Minh Tâm |
| Corruption/repair | Baseline clean + raw records | Tiêm 6 lỗi; rebuild clean/index từ raw | Corruption log, corrupted/repaired artifacts | Trương Thị Lan Anh |
| Orchestration | Settings và artifacts | Điều phối thứ tự, fail gate, báo cáo | `data/reports/phase1_report.md`, `corruption_report.md` | Trương Thị Lan Anh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
|---|---|
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-2.5-flash` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; fail nếu stale ratio > 25% |
| Random seed | Không dùng; sampling và corruption là deterministic |

### Lệnh cài đặt

```bash
python -m pip install -e .
```

### Lệnh chạy

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
|---|---|---|---|
| Baseline pipeline | Thành công | 2026-09-25 | `baseline_metrics.json`, `phase1_report.md`, Chroma collection 24 docs |
| Corruption flow | Thành công | 2026-09-25 | `corruption_log.json`, corrupted/repaired metrics, `corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
|---|---|
| Source | `https://api.crossref.org/works` và local snapshot fallback |
| Query/filter | `agentic retrieval augmented generation large language model`; `from-pub-date:2026-03-29,has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-09-25 |
| Số record nhận được | 24 |
| Cơ chế retry/backoff | Tối đa 3 lần, timeout 20 giây, exponential delay 1/2 giây; fallback snapshot khi network/HTTP 429/503/payload không đủ |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
|---|---|---|---|---|
| `paper_id` | string | Có | DOI chuẩn hóa, khóa document | Bỏ record nếu rỗng; lowercase; deduplicate |
| `title` | string | Có | Tiêu đề bài báo | Normalize whitespace; bỏ record nếu rỗng |
| `summary` | string | Có cho quality | Abstract phục vụ retrieval/QA | Bỏ JATS/HTML; GX yêu cầu tối thiểu 30 ký tự |
| `authors` | list[string] | Không | Danh sách tác giả | Ghép thành `authors_joined`; cho phép rỗng |
| `categories` | list[string] | Không | Subject của Crossref | Ghép thành `categories_joined`; ghi rõ khi Crossref không cung cấp |
| `published` | datetime UTC | Có | Ngày công bố | Parse ISO/date-parts; bỏ record nếu không hợp lệ |
| `age_days` | integer | Có | Tuổi dữ liệu tại ngày chạy | Tính `(run_date - published).days` |
| `text_for_embedding` | string | Có | Nội dung cấu trúc đưa vào MiniLM | Rebuild từ năm trường clean |

### Quy tắc cleaning

| Quy tắc | Quality dimension | Số record bị tác động | Cách xác minh |
|---|---|---:|---|
| Loại record thiếu DOI/title/published | Completeness/Validity | 0 trong snapshot hiện tại | Clean row count = 24 |
| Chuẩn hóa whitespace và loại JATS/XML | Validity/Consistency | 24 | Không còn `<jats:...>` trong clean summary |
| Khử trùng theo `paper_id` | Uniqueness | 0 trong baseline | `paper_id.is_unique == True` |
| Parse ngày và tính `age_days` | Validity/Freshness | 24 | `freshness_report.json` |
| Tạo `text_for_embedding` | Consistency | 24 | GX not-null và clean JSON |

`text_for_embedding` gồm năm dòng `Title`, `Authors`, `Published`, `Categories`, `Summary`. Document ID trong Chroma có dạng `<paper_id>::<row_index>`, còn DOI trong metadata giữ vai trò identity dùng đối chiếu benchmark. `age_days` được tính theo ngày UTC tại thời điểm chạy.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
|---|---|
| Số câu hỏi | 10 |
| Các `question_type` | `summary`, `authors`, `date`, `category`, `multi_hop` — mỗi loại 2 câu |
| Ground-truth document ID | DOI từ clean rows; multi-hop dùng hai DOI |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2`, mean pooling, L2 normalization |
| Vector store/collection | ChromaDB cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | Gemini / `gemini-2.5-flash`; heuristic judge fallback nếu LLM không khả dụng |
| Test set dùng chung | `data/eval/test_set.json` |

Test set được giữ nguyên cho cả ba trạng thái để biến độc lập duy nhất là chất lượng dữ liệu/index. Nếu thay câu hỏi hoặc ground-truth giữa các lượt chạy, chênh lệch metric không còn chứng minh được tác động của corruption và repair.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
|---|---|---|---|
| Raw response/records | `data/raw/` | Có | API response và 24 normalized records |
| Cleaned dataset | `data/clean/papers_clean.csv/json` | Có | 24 dòng sạch |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | Collection baseline 24 docs |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu, 5 loại |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | 10 samples |
| Quality/freshness | `data/quality/` | Có | GX pass và freshness pass |
| Baseline report | `data/reports/phase1_report.md` | Có | Khớp metrics/artifacts |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
|---|---:|---|
| `retrieval_hit_rate` | 1.0000 | Cả 10 câu có ít nhất một DOI ground truth trong top 4 |
| `mean_token_f1` | 1.0000 | Câu trả lời khớp đầy đủ ground truth benchmark |
| `judge_accuracy` | 1.0000 | 10/10 câu được judge đánh giá đúng |
| `mean_judge_score` | 5.00 | Điểm judge trung bình tối đa |
| Ragas | N/A | Tắt mặc định; PyArrow DLL bị Application Control chặn, không ảnh hưởng metrics bắt buộc |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
|---|---|---|---|---|
| Row count | Volume | 5–5000 | Pass: 24 | `baseline_quality_report.json` |
| Not null | Completeness | `paper_id`, `title`, `text_for_embedding` không null | Pass | Cùng artifact |
| Unique DOI | Uniqueness | 100% unique | Pass: 24/24 unique | Cùng artifact |
| Summary length | Completeness | Tối thiểu 30 ký tự | Pass | Cùng artifact |

### Freshness

| Thuộc tính | Giá trị |
|---|---|
| Freshness được đo tại | Clean DataFrame và `data/quality/freshness_report.json` |
| Timestamp mới nhất | 2026-09-15 |
| Timestamp cũ nhất | 2026-04-01 |
| Ngưỡng freshness | `age_days > 180`; cảnh báo nếu stale ratio > 25% |
| Trạng thái baseline | Fresh (`is_fresh=True`) |
| Lý do | 0/24 bản ghi stale, tỷ lệ 0% |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
|---|---|---:|---|---|---|
| Drop latest records | Bỏ 20% bài mới nhất | 5 | Giảm coverage/freshness | Final rows còn 22; Hit Rate giảm | Rebuild từ raw 24 records |
| Blank summary | Gán summary rỗng | 3 gốc; 6 dòng tính duplicate | Summary-length fail | GX fail | Reparse raw abstract |
| Inject text noise | Thêm token rác vào embedding text | 3 | Retrieval relevance giảm | Token F1/retrieval suy giảm tổng thể | Rebuild embedding text |
| Truncate title | Cắt còn tối đa 7 ký tự | 3 | Semantic identity kém | Exact-title QA/retrieval bị ảnh hưởng | Khôi phục title từ raw |
| Stale date | Lùi published 5 năm | 7 gốc; 10 dòng tính duplicate | Freshness fail | 45.45% stale, `is_fresh=False` | Parse lại published và age |
| Duplicate rows | Append bản sao giữ nguyên DOI | 3 | Unique fail | GX unique expectation fail | Clean rebuild + deduplicate |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đủ sáu scenario, số record, DOI bị tác động, noise token và original title/date cần đối chiếu.

Repair không chỉnh metric hoặc xóa riêng các dòng gây lỗi. Pipeline đọc lại `data/raw/crossref_records.json`, chạy toàn bộ `build_clean_dataframe`, GX/freshness, MiniLM và Chroma collection `papers-repaired`. Vì nguồn repair độc lập với corrupted DataFrame nên kết quả có thể chạy lặp lại và tránh che lỗi còn sót.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
|---|---:|---:|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | -0.2000 | 100% | Mất ground-truth docs làm 2/10 câu miss; repair phục hồi đủ |
| `mean_token_f1` | 1.0000 | 0.6979 | 1.0000 | -0.3021 | 100% | Nội dung/date/title hỏng làm đáp án sai |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | -0.2000 | 100% | Judge xác nhận Silent Failure |
| `mean_judge_score` | 5.00 | 3.60 | 5.00 | -1.40 | 100% | Chất lượng câu trả lời giảm rõ rệt |
| Quality checks | Pass 6/6 | Fail 4/6 | Pass 6/6 | 2 checks fail | 100% | Duplicate và summary bị phát hiện |
| Freshness status | True, 0% | False, 45.45% | True, 0% | Fresh → stale | 100% | Repair đưa stale rows từ 10 về 0 |

1. Drop/blank/noise/truncate/stale/duplicate → GX fail và stale ratio tăng lên `45.45%` → Hit Rate giảm còn `0.8`, Token F1 còn `0.6979`, Judge Score còn `3.6`.
2. Rebuild từ raw snapshot → Quality Gate/Freshness trở lại pass → toàn bộ agent metrics phục hồi về baseline.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `ImportError: The pyarrow installation is not built with support for 'dataset' (DLL load failed while importing _json: An Application Control policy has blocked this file.)`
- **Nguyên nhân:** SentenceTransformers 6 và package evaluation eager-import training stack `datasets/PyArrow` dù pipeline chỉ cần inference; Windows policy chặn DLL PyArrow.
- **Cách xử lý:** Lazy-import `datasets` chỉ khi bật Ragas; dùng đúng trọng số MiniLM qua `AutoTokenizer`/`AutoModel`, mean pooling và L2 normalization; package exports cũng được lazy-load.
- **Cách xác minh:** Hai pipeline chạy thành công; ba Chroma collections được tạo; baseline/repaired có 24 vectors; top-4 retrieval benchmark đạt 10/10 hit ở baseline.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
|---|---|---|
| Crossref live có thể thiếu `subject` | Một số câu category chỉ xác nhận nguồn không cung cấp category | Bổ sung taxonomy từ venue/type hoặc nguồn thứ hai; đo tỷ lệ category coverage |
| Benchmark chỉ có 10 câu và 24 tài liệu | Metric có thể lạc quan, chưa đại diện production | Mở rộng ≥100 câu, chia train-free validation, báo confidence interval |
| Ragas tắt mặc định do PyArrow policy | Chưa có context precision/recall/faithfulness từ Ragas | Chạy trong container/CI cho phép PyArrow và đối chiếu với metrics hiện tại |
| Corruption deterministic một cấu hình | Chưa đo độ nhạy theo mức độ lỗi | Chạy nhiều severity/seed, vẽ degradation curve và đặt alert threshold |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng — hiện mới xác minh báo cáo của Trương Thị Lan Anh.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
