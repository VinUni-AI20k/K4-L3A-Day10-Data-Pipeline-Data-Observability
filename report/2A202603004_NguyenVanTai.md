# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                 |
| ------------------ | ------------------------------------------------------------------------- |
| Họ và tên       | Nguyễn Văn Tài                                                          |
| MSSV               | 2A202603004                                                               |
| Khóa/Lớp         | K4 - L3A                                                                        |
| Tên nhóm         | SVSoppi                                                                   |
| Vai trò chính    | Thành viên 3 — Corruption & vector store owner                         |
| Repository         | https://github.com/hoangtrunghieu0025-lab/K4-L3-DAY10-SVSoppi-DataPipeline |
| Ngày hoàn thành | 2026-09-25                                                                |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Tiêm 6 loại lỗi dữ liệu | `src/ingestion/corruption.py` — `corrupt_clean_dataframe(df, output_log_path, seed=42)` | Clean dataframe từ `build_clean_dataframe` (24 dòng) | Corrupted dataframe (22 dòng) + `data/results/corruption_log.json` | Hoàn thành |
| Smoke test vector store 3 trạng thái | `script/smoke_test_chroma.py` | Raw records → clean → corrupted → repaired | Kiểm tra 3 collection `papers-baseline` / `papers-corrupted` / `papers-repaired` trong ChromaDB (22 check) | Hoàn thành |

Không thuộc phần của tôi: `retrieval/index.py` và `retrieval/embeddings.py` là code có sẵn trong starter repo (tôi chỉ dùng và kiểm tra, không sửa). `pipelines/corruption_flow.py` do trưởng nhóm (`hoangtrunghieu0025-lab`) viết, gọi hàm của tôi ở bước 2–3.

Quan hệ phụ thuộc:

- **Tôi phụ thuộc vào:** schema clean của thành viên 2 (`glacerjust`), đặc biệt format `text_for_embedding` và `published` dạng `YYYY-MM-DDTHH:MM:SSZ`.
- **Phụ thuộc vào tôi:** `corruption_flow.py` (Lead) và quality gate của thành viên 4 (`nguyenviethoanghai`). Dữ liệu lỗi phải đủ nặng để làm fail GX và freshness SLA.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ------------------------------ | -------- |
| Kiểm tra trước contract `LocalEmbeddingIndex.build/load` với 3 manifest path | Lead — `corruption_flow.py` | Báo cho Lead cách truyền `embeddings_output_path` để ra đúng collection, và lưu ý handle index cũ bị hỏng sau khi build lại (xem mục 6) |
| Xác nhận dữ liệu lỗi vượt ngưỡng quality gate trước khi GX được viết xong | Thành viên 4 — `quality.py` | Trên df lỗi: 3 summary < 30 ký tự, 3 `paper_id` trùng, stale ratio 0.41 > 0.25 |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Triển khai 6 kịch bản lỗi, có seed cố định | `src/ingestion/corruption.py` | `corruption_log.json`: 24 → 22 dòng, 19 `paper_id` duy nhất, đủ 6 loại | `python script/smoke_test_chroma.py` (mục 1) |
| Lan lỗi xuống tầng embedding | `_build_text_for_embedding` trong `corruption.py` | `text_for_embedding` và `summary_chars` được tính lại sau khi làm bẩn | So sánh vector: query title bài bị drop cho score 0.805 (baseline) và 0.396 (corrupted) |
| Kiểm tra 3 collection ChromaDB | `script/smoke_test_chroma.py` | 24 / 22 / 24 vector; repaired có cùng `record_id` với baseline; build lại lần 2 không bị nhân đôi | `SMOKE TEST PASSED` (22/22 check) |

Output cụ thể: `data/results/corruption_log.json` do `run_corruption_flow.py` sinh ra bằng hàm của tôi. Log ghi rõ `paper_id` bị ảnh hưởng theo từng loại lỗi, nhờ đó tôi truy được từng câu sai trong `corrupted_answers.json` về đúng loại lỗi gây ra nó (mục 8).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Nhóm cần chứng minh "silent failure": dữ liệu bẩn không làm pipeline báo lỗi, nhưng agent trả lời sai. Muốn đo được điều đó, lỗi phải:

1. **Giống sự cố thật:** mất dữ liệu tươi, crawl rỗng, nhiễu ký tự, cắt trường, ngày sai, index trùng.
2. **Tái lập được:** chạy lại vẫn ra cùng một dữ liệu lỗi, để 3 trạng thái so sánh được với nhau.
3. **Truy vết được:** biết chính xác dòng nào bị lỗi gì.

### Cách triển khai

Hàm làm việc trên bản `df.copy(deep=True)`, không sửa input, và dùng một `random.Random(seed)` riêng. Thứ tự áp dụng:

| # | Lỗi | Quy tắc | Trên dữ liệu nhóm |
|---|-----|---------|-------------------|
| 1 | `drop_latest_records` | Sắp theo `published` giảm dần, bỏ `ceil(20%)` dòng đầu | −5 dòng (5 bài mới nhất) |
| 2 | `blank_summary` | `summary = ""` | 3 dòng |
| 3 | `inject_noise` | Chèn 2 token rác ở đầu và 1 token rác sau mỗi 3 từ (`#@!$%`, `?????`, `lorem`, …) | 3 dòng |
| 4 | `truncate_title` | `title[:7]` (< 8 ký tự) | 3 dòng |
| 5 | `stale_date` | `published` lùi 365 ngày, `age_days += 365` | 8 dòng (≈40%) |
| 6 | `duplicate_rows` | Nhân bản dòng **sau khi** đã làm bẩn, nối vào cuối | +3 dòng |

Chi tiết quan trọng:

- **Nhóm dòng riêng cho lỗi 2–4:** ba lỗi này chọn từ ba nhóm dòng không giao nhau, để mỗi câu sai chỉ quy về một nguyên nhân nội dung. Stale và duplicate chọn độc lập, vì hai lỗi này tác động lên chiều khác (thời gian, số lượng).
- **Tỉ lệ stale 40%:** chọn cố ý để vượt `max_stale_ratio = 0.25` ngay cả khi duplicate làm tăng tổng số dòng.
- **Tính lại cột phụ thuộc:** sau khi làm bẩn, `summary_chars` và `text_for_embedding` được tính lại theo đúng format của `cleaning.py` (`Title/Authors/Published/Categories/Summary`). Nếu không tính lại, vector vẫn nhúng text sạch và retrieval gần như không bị ảnh hưởng.

### Input, output và contract

| Thành phần | Mô tả |
| ------------------------------ | ------------------------------------------- |
| Input | Clean dataframe: `paper_id`, `title`, `summary`, `published` (ISO có `Z`), `authors_joined`, `categories_joined`, `age_days`, `summary_chars`, `text_for_embedding`; `output_log_path`; `seed` (mặc định 42) |
| Output | Dataframe cùng schema, index reset; JSON log gồm `seed`, `input_rows`, `output_rows`, `unique_paper_ids`, `corruption_types`, `corruptions[]` (mỗi lỗi có `affected_paper_ids`, `before/after` cho title và ngày) |
| Module phụ thuộc | `ingestion/cleaning.py` (schema), `core/utils.py` (`write_json`, `now_utc`) |
| Module sử dụng output | `pipelines/corruption_flow.py` → `observability/quality.py` (GX + freshness) → `retrieval/index.py` (collection `papers-corrupted`) → evaluation |
| Điều kiện lỗi cần xử lý | df rỗng (`_pick_count` trả 0); df thiếu `age_days`/`summary_chars` (bỏ qua cột đó); `published` có timezone (`pd.to_datetime(utc=True)`); `output_log_path` truyền dạng `str` (bọc `Path`) |

### Cách xác minh

```bash
python script/smoke_test_chroma.py            # chạy trong thư mục tạm
python script/run_corruption_flow.py          # Lead chạy, sinh artifact chính thức
```

- **Kết quả mong đợi:** đủ 6 loại lỗi; input không bị sửa; cùng seed thì ra cùng kết quả; 3 collection có số vector đúng bằng số dòng; repaired trùng baseline; bài bị drop không truy xuất được trong corrupted.
- **Kết quả thực tế:** `SMOKE TEST PASSED`. Chạy lại ngày 2026-09-25 trên `main` @ `4a7be45`.
- **Artifact/log:** `data/results/corruption_log.json`, `data/clean/papers_clean_corrupted.json`, `data/quality/corrupted_quality_report.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn dòng để tiêm lỗi sao cho kết quả so sánh 3 trạng thái vừa có ý nghĩa vừa giải thích được.
- **Các phương án đã cân nhắc:**
  1. Mỗi lỗi chọn ngẫu nhiên độc lập, không seed. Đơn giản, nhưng mỗi lần chạy ra số liệu khác và các lỗi chồng lên nhau trên cùng dòng.
  2. Làm bẩn toàn bộ dòng. Chắc chắn gây fail, nhưng metric rơi về 0 và không cho biết loại lỗi nào nguy hiểm hơn.
  3. **Seed cố định, lỗi nội dung (blank/noise/truncate) nằm trên nhóm dòng không giao nhau, tỉ lệ vừa phải.**
- **Phương án đã chọn:** phương án 3.
- **Lý do:** tái lập được (quan trọng khi Lead chạy lại flow nhiều lần), và mỗi câu sai quy về đúng một loại lỗi. Đổi lại, dữ liệu kém "tự nhiên" hơn sự cố thật, nơi các lỗi thường chồng lên nhau.
- **Bằng chứng:** smoke test check "cùng seed → cùng kết quả" pass. Nhờ log, tôi lập được bảng truy vết 10/10 câu ở mục 8 và thấy `drop_latest_records` chịu trách nhiệm cả 4 câu retrieval miss.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  chromadb.errors.InternalError: Error executing plan: Internal error: Error creating hnsw segment reader: Nothing found on disk
  ```
  Lỗi xuất hiện ở `index.search(...)` cho collection `papers-repaired`, trong lần chạy smoke test đầu tiên.
- **Lệnh tái hiện:** gọi `LocalEmbeddingIndex.build(repaired_df, ...)` hai lần để kiểm tra tính idempotent, sau đó `search()` bằng object trả về từ lần build **thứ nhất**.
- **Nguyên nhân gốc:** `LocalEmbeddingIndex.build()` gọi `client.delete_collection()` rồi `create_collection()` mới. Object index cũ vẫn giữ handle tới collection đã bị xoá, nên segment HNSW trên đĩa không còn. Đây không phải lỗi của Chroma hay dữ liệu, mà do dùng lại handle cũ.
- **Cách xử lý:** sau khi build lại, thay object cũ bằng object mới (`indexes["repaired"] = rebuilt`), kèm comment giải thích.
- **Cách xác minh sau khi sửa:** chạy lại `python script/smoke_test_chroma.py`, cả 3 trạng thái search thành công, kết quả `SMOKE TEST PASSED`.
- **Điều học được:** "rebuild idempotent" ở tầng vector store có nghĩa là mọi reference cũ đều mất hiệu lực. Tôi đã báo cho Lead để `corruption_flow.py` luôn dùng object trả về từ `build()` mới nhất, không cache index qua các lần build.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** `crossref.py` gọi API (hoặc fallback snapshot), lưu nguyên response vào `crossref_response.json` và bản đã parse vào `crossref_records.json`. `cleaning.py` chuẩn hoá, tính `age_days`, ghép `text_for_embedding`, dedupe theo `paper_id`. `index.py` nhúng `text_for_embedding` bằng `all-MiniLM-L6-v2` (normalize, cosine) và nạp vào collection Chroma, `record_id = paper_id::row_index`, kèm metadata để agent trích câu trả lời.
2. **Evaluation set:** 10 câu thuộc 4 loại (summary/authors/date/categories), mỗi câu có `ground_truth` và `ground_truth_doc_ids`. `retrieval_hit_rate` đo xem DOI đúng có nằm trong top-k không. `token_f1` so câu trả lời với ground truth. Hai tầng này tách được lỗi "không tìm thấy tài liệu" khỏi lỗi "tìm thấy nhưng nội dung sai". Ví dụ eval_003 và eval_009 vẫn hit nhưng F1 = 0.
3. **Quality checks và freshness:** GX kiểm **hình dạng** của từng dòng và cả bảng (row count, not-null, unique `paper_id`, độ dài `title`/`summary`). Freshness kiểm **tuổi** của dữ liệu so với SLA (tỉ lệ `age_days > 180` không vượt 25%). Dữ liệu có thể đúng hình dạng mà vẫn cũ, và ngược lại. Trong bài này, `stale_date` chỉ freshness bắt được, còn trùng lặp thì chỉ GX bắt được.
4. **Cùng test set:** nếu mỗi trạng thái có đề riêng thì chênh lệch metric có thể do đề khác nhau chứ không phải do dữ liệu. Giữ cố định `test_set.json` (và cố định seed corruption) thì biến duy nhất thay đổi là dữ liệu trong collection.
5. **Repair thành công** khi: `repaired_quality_report.json` có `success: true` (8/8 check); `repaired_freshness_report.json` có `is_fresh: true`; `repaired_metrics.json` bằng `baseline_metrics.json` trên cùng test set; và `_check_repair_matches_baseline` xác nhận dữ liệu repair giống hệt baseline (trừ `age_days` phụ thuộc ngày chạy). Smoke test của tôi kiểm thêm ở tầng vector: `record_id` của `papers-repaired` trùng với `papers-baseline`.

## 8. Phân tích kết quả

Nguồn: `data/results/*_metrics.json`, `data/quality/*_quality_report.json`, `data/quality/*freshness_report.json`, do `run_corruption_flow.py` sinh lúc 2026-09-25T08:37Z.

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` | 1.00 | 0.60 | 1.00 | 4/4 câu miss đều do `drop_latest_records`: tài liệu đúng không còn trong index |
| `mean_token_f1` | 1.00 | 0.50 | 1.00 | 5 câu F1 = 0: 3 do drop, 1 do `inject_noise`, 1 do `stale_date` |
| `judge_accuracy` | 1.00 | 0.50 | 1.00 | Judge là heuristic dựa trên F1 (log: *"Fallback heuristic judge used because the LLM evaluator was unavailable"*), nên không độc lập với F1 |
| `mean_judge_score` | 5 | 3 | 5 | Như trên |
| Quality checks (GX) | PASS 8/8 | FAIL 5/8 | PASS 8/8 | Fail: unique `paper_id` (6 giá trị), độ dài `title` (4), độ dài `summary` (3) |
| Freshness status | fresh (stale 0.00) | **stale** (0.41, 9/22) | fresh (0.00) | Do `stale_date`; `latest_published` cũng lùi từ 2026-09-15 về 2026-08-27 do drop |

### Truy vết từng câu trên trạng thái corrupted

| Câu | Loại | Lỗi trên tài liệu đúng | Hit | F1 | Hiện tượng |
|-----|------|--------------------------|-----|----|-----------|
| eval_003 | date | `stale_date` (+noise, dup) | ✅ | 0 | Trả `2025-08-01` thay vì `2026-08-01`: tìm đúng bài, nhưng tự tin trả ngày sai |
| eval_004 | categories | `drop_latest_records` | ❌ | 1.0 | Đúng **nhờ may mắn**: bài khác có cùng categories. Top-4 bị một bản duplicate chiếm 1 slot |
| eval_005 | summary | `drop_latest_records` | ❌ | 0 | Top-1 là bài bị `blank_summary`, nên câu trả lời rỗng |
| eval_007 | date | `drop_latest_records` | ❌ | 0 | Trả ngày của bài khác (`2026-06-30`) |
| eval_009 | summary | `inject_noise` | ✅ | 0 | Trả `?????`: câu đầu của summary nhiễu |
| eval_010 | authors | `drop_latest_records` | ❌ | 0 | Trả tác giả của bài khác (top-1 lại là bài bị blank summary) |
| eval_001, 002, 006, 008 | — | truncate/stale/noise/blank trên trường không được hỏi | ✅ | 1.0 | Không bị ảnh hưởng |

### Kết luận từ số liệu

1. **Corruption → signal → metric:** 6 lỗi được tiêm → GX fail 3/8 check (trùng `paper_id`, `title` < 8, `summary` < 30) và freshness chuyển `is_fresh=false` (stale ratio 0.41 > 0.25) → `retrieval_hit_rate` 1.00 → 0.60, `mean_token_f1` 1.00 → 0.50. Pipeline không throw exception nào; agent vẫn trả lời tự tin cả 10 câu. Đó chính là silent failure.
2. **Repair → signal → metric:** rebuild từ `crossref_records.json` (không vá từng dòng lỗi) → GX 8/8, `is_fresh=true`, stale 0.00 → cả 4 metric về đúng bằng baseline (Δ = 0). Smoke test xác nhận thêm `papers-repaired` có cùng `record_id` với `papers-baseline`, và build lại lần 2 vẫn giữ 24 vector.

**Corruption ảnh hưởng rõ nhất: `drop_latest_records`.** Lỗi này chỉ bỏ 20% dòng nhưng gây ra 4/10 câu miss retrieval và 3/5 câu F1 = 0, vì test set có 4/10 câu hỏi về 5 bài mới nhất. Đây đúng là kịch bản trong đề: dữ liệu mới không vào kho, agent trả lời bằng tài liệu khác mà không báo lỗi. Ngoài ra, `drop` còn kết hợp với `blank_summary`: bài bị xoá summary có vector "trống ngữ nghĩa", nên trở thành top-1 cho các query không còn tài liệu đúng (eval_005, eval_010, và query DOLPHIN trong smoke test: score 0.396).

**Kết quả khác kỳ vọng:**

- **Lỗi nặng nhất không bị check nào bắt trực tiếp.** `expect_table_row_count_to_be_between(5, 5000)` vẫn pass với 22 dòng, nên mất 5 bài mới nhất không làm fail GX. Freshness fail là nhờ `stale_date`, không phải nhờ drop. Tôi kiểm tra bằng cách đối chiếu `corrupted_quality_report.json` (row count: `success: true`) với bảng truy vết ở trên. Nếu chỉ có lỗi drop, gate sẽ **pass** và agent vẫn trả lời sai 4/10 câu.
- **`inject_noise` cũng lọt qua GX.** Summary nhiễu vẫn dài hơn 30 ký tự; lỗi chỉ lộ ra khi agent trả `?????`.
- **`truncate_title` không làm giảm retrieval** (eval_001 vẫn hit, F1 1.0). Exact-title lookup trong `qa.py` fail, nhưng vector search vẫn tìm ra nhờ phần authors/summary trong `text_for_embedding`, với corpus chỉ 24 bài. Trên corpus lớn hơn, tác động có thể khác.
- **eval_004 đúng nhờ may mắn** dù retrieval miss. Token F1 đơn lẻ có thể đánh giá quá cao chất lượng trên dữ liệu lỗi, nên cần đọc cùng `retrieval_hit_rate`.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** repair đúng là *rebuild từ raw đã lưu*, không phải vá dữ liệu hỏng. Vì raw được giữ nguyên và cleaning có tính quyết định, repaired trùng baseline tới từng `record_id`. Nhưng rebuild cũng xoá collection cũ, nên mọi handle cũ phải bỏ (mục 6).
2. **Data quality/observability:** một gate chỉ bắt được những gì nó kiểm. GX bắt tốt lỗi về hình dạng (trùng, rỗng, ngắn), freshness bắt lỗi về tuổi, nhưng lỗi **mất dữ liệu có chọn lọc** (drop latest) và **nhiễu nội dung** (noise) lọt qua cả hai, dù đó lại là lỗi gây hại nhiều nhất.
3. **Ảnh hưởng tới RAG agent:** agent không bao giờ nói "tôi không biết" trong trạng thái corrupted. Khi thiếu tài liệu đúng, nó lấy tài liệu gần nhất (thường là bài bị blank summary) và trả lời tự tin: ngày sai, tác giả sai, câu trả lời rỗng hoặc `?????`.

### Nếu có thêm thời gian

Tôi sẽ thêm hai check để bắt đúng hai lỗi đang lọt qua gate:

- **Volume/recency anomaly:** so `row_count` và `latest_published` với lần chạy trước (hoặc với raw snapshot). Cảnh báo khi số dòng giảm hơn 10% hoặc bài mới nhất lùi hơn N ngày.
- **Tỉ lệ token rác trong `summary`:** dùng `ExpectColumnValuesToNotMatchRegex` hoặc một custom check: fail khi hơn 5% token không phải chữ/số.

Cách đo: chạy lại `run_corruption_flow.py` với từng loại lỗi bật riêng lẻ (thêm tham số chọn loại lỗi cho `corrupt_clean_dataframe`), rồi lập ma trận *loại lỗi × check nào bắt được*. Mục tiêu là cả 6 loại lỗi đều bị ít nhất một check bắt, đặc biệt `drop_latest_records` phải làm fail gate ngay cả khi chạy một mình.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Văn Tài
**Ngày xác nhận:** 2026-09-25
