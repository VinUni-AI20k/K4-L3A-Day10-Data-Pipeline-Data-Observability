# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin        | Nội dung |
| ---------------- | -------- |
| Họ và tên        | Hoàng Trung Hiếu |
| MSSV             | 2A202602945 |
| Khóa/Lớp         | K4 — K4-L3-DAY10 |
| Tên nhóm         | SVSoppi |
| Vai trò chính    | Trưởng nhóm — Pipeline integration & reporting |
| Repository       | https://github.com/hoangtrunghieu0025-lab/K4-L3-DAY10-SVSoppi-DataPipeline |
| Ngày hoàn thành  | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline orchestration | `src/pipelines/phase1.py` — `main()` | Raw records, các hàm của `ingestion/`, `observability/`, `evaluation/` | `data/clean/`, `data/eval/`, `data/chroma/` (`papers-baseline`), `baseline_metrics.json` | Hoàn thành |
| Corruption & repair flow | `src/pipelines/corruption_flow.py` — `main()`, `_check_repair_matches_baseline()` | Artifact pha 1, `corrupt_clean_dataframe()`, raw records | `corrupted_metrics.json`, `repaired_metrics.json`, `papers-corrupted`, `papers-repaired` | Hoàn thành |
| Helper dùng chung | `src/pipelines/common.py` — `save_clean_artifacts`, `run_observability`, `index_and_evaluate` | Dataframe ở bất kỳ trạng thái nào | CSV/JSON, quality report, metrics | Hoàn thành |
| Reporting | `src/observability/reporting.py` — `generate_phase1_report`, `generate_corruption_report` | Metrics, quality, freshness dict | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Hoàn thành |

Cả 4 thành viên đều phụ thuộc vào phần của tôi ở điểm tích hợp: pipeline gọi đúng chữ ký hàm của Ngô Kỳ Anh (ingestion/cleaning), Nguyễn Văn Tài (corruption) và Nguyễn Việt Hoàng Hải (quality/testset).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chốt data contract (danh sách cột của clean dataframe) và gửi cho nhóm trước khi làm song song | Cả nhóm | Các module ghép lại không lỗi `KeyError` |
| Sửa fallback categories khi Crossref thiếu `subject` (có sự đồng ý của nhóm) | `ingestion/crossref.py` (Ngô Kỳ Anh) | Hết ground truth rỗng; baseline Token F1 0.80 → 1.00 (PR #4) |
| Review và merge Pull Request | Cả nhóm | PR #1–#5 merge vào `main`, không squash để giữ Contributors |
| Viết báo cáo nhóm | `report/group_report.md` | PR #5 |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Pipeline baseline end-to-end | `pipelines/phase1.py` | 24 dòng sạch, 10 câu test, hit rate 1.00 | `python script/run_phase1.py` (exit 0) |
| Flow corruption → repair | `pipelines/corruption_flow.py` | Bảng 3 trạng thái trên console và trong report | `python script/run_corruption_flow.py` (exit 0) |
| Kiểm chứng idempotent | `_check_repair_matches_baseline()` | Log `idempotent: 24 rows identical to baseline` | Console của corruption flow |
| Báo cáo đối chiếu | `observability/reporting.py` | `corruption_report.md` gồm 3 cột, delta, danh sách expectation fail, phân tích sinh từ số liệu | `data/reports/corruption_report.md` |

Output cụ thể: `data/reports/corruption_report.md`. Bảng Baseline / Corrupted / Repaired cho hit rate 1.00 / 0.60 / 1.00, Token F1 1.00 / 0.50 / 1.00. Report liệt kê 3 expectation fail: `paper_id` trùng (6), `title` ngắn (4), `summary` ngắn (3). Freshness chuyển từ Fresh sang Stale (40.9%) rồi về lại Fresh.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module do 3 người khác viết song song phải được nối thành 2 flow chạy lặp lại được, và phải trả lời được câu hỏi của bài lab: *dữ liệu lỗi ảnh hưởng tới agent thế nào, observability có phát hiện được không, và repair có thực sự khôi phục được không.*

### Cách triển khai

- **Gate trước index:** `phase1.py` chạy GX ngay sau cleaning. Nếu `success = False` thì dừng bằng `SystemExit` trước bước ghi vào Chroma. Freshness chỉ cảnh báo, vì dữ liệu cũ nhưng hợp lệ không nên chặn phục vụ.
- **Nguồn tái lập được:** mặc định đọc raw snapshot đã lưu; chỉ gọi API khi `REFRESH_SOURCE=1` hoặc chưa có raw. Nhờ vậy mọi lần chạy đều bắt đầu từ cùng một bản raw.
- **Test set cố định:** chỉ sinh khi chưa có hoặc khi `REFRESH_TEST_SET=1`, và luôn sinh từ dữ liệu sạch.
- **Mô phỏng thiếu gate:** trong corruption flow, dữ liệu lỗi vẫn được index vào `papers-corrupted`, dù gate đã báo `DATA INCIDENT`, để đo agent sẽ trả lời sai tới đâu nếu không có gate. Code có comment ghi rõ trong production bước này bị chặn.
- **Repair = rebuild:** bỏ dataframe hỏng, chạy lại `build_clean_dataframe(load_raw_records(raw))`, so với baseline trên mọi cột trừ `age_days`, rồi bắt dữ liệu qua lại gate trước khi index `papers-repaired`.
- **Report không khẳng định vượt quá số liệu:** phần phân tích được sinh từ số (dropped / did not drop, fully / partially recovered), nên báo cáo không thể tự nhận "sụt giảm" khi số liệu không giảm.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `data/raw/crossref_records.json`; `Settings` từ `core/config.py` (mọi đường dẫn lấy qua `settings.paths`, không hardcode) |
| Output | Clean/corrupted/repaired CSV+JSON, 3 Chroma collection, 3 bộ metrics + answers, quality/freshness reports, 2 file Markdown |
| Module phụ thuộc | `ingestion/crossref.py`, `ingestion/cleaning.py`, `ingestion/corruption.py`, `observability/quality.py`, `evaluation/testset.py`, `retrieval/index.py`, `evaluation/metrics.py` |
| Module sử dụng output | `script/run_phase1.py`, `script/run_corruption_flow.py`; người chấm đọc `data/reports/` |
| Điều kiện lỗi cần xử lý | Thiếu artifact pha 1 khi chạy corruption flow → dừng và nhắc chạy pha 1; gate fail ở baseline hoặc repaired → không index; provider `mock` không gọi được tool → bỏ qua agent demo; `published` kiểu datetime → dùng `df.to_json(date_format="iso")` |

### Cách xác minh

```bash
.venv\Scripts\python script/run_phase1.py
.venv\Scripts\python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Cả hai exit 0; chỉ số corrupted thấp hơn baseline; repaired bằng baseline; gate FAIL trên corrupted và PASS trên repaired.
- **Kết quả thực tế:** Đúng như mong đợi (xem mục 8).
- **Artifact/log:** `data/results/*.json`, `data/quality/*.json`, `data/reports/*.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair phải đưa dữ liệu về trạng thái đúng, và phải chứng minh được rằng nó đúng.
- **Các phương án đã cân nhắc:** (1) Vá từng dòng lỗi theo `corruption_log.json`: xóa dòng trùng, khôi phục title, ngày. (2) Bỏ toàn bộ dữ liệu hỏng và rebuild từ raw snapshot đã bảo toàn.
- **Phương án đã chọn:** (2) Rebuild từ raw, kèm kiểm chứng tự động so với baseline.
- **Lý do:** Phương án (1) chỉ sửa được lỗi *đã biết* (nằm trong log). Ngoài đời, không ai ghi log cho lỗi, và `drop_latest_records` làm mất hẳn dữ liệu nên không có gì để vá. Rebuild từ raw chỉ phụ thuộc vào nguồn đáng tin cậy, nên chạy lại bao nhiêu lần cũng ra cùng kết quả (idempotent). Đổi lại, cách này tốn thời gian tính lại toàn bộ, nhưng với 24 record thì không đáng kể.
- **Bằng chứng quyết định phù hợp:** Log `idempotent: 24 rows identical to baseline (ignoring ['age_days'])`; `repaired_metrics.json` trùng khớp `baseline_metrics.json` trên cả 4 chỉ số.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Chạy thử toàn bộ nhánh đã ghép thì `corruption_report.md` vừa ghi `Quality Gate (GX 1.x) | ❌ FAIL` vừa ghi `None — the quality gate did NOT catch the corruption`. Hai kết luận trái ngược nhau trong cùng một báo cáo.
- **Lệnh tái hiện:** Merge `main` + `HoangHai` + `feat/lead-pipelines` vào một worktree tạm, chạy `run_corruption_flow.py` với `LLM_PROVIDER=mock`.
- **Nguyên nhân gốc:** Lệch contract. `reporting.py` (tôi viết trước khi có `quality.py`) đọc `quality["results"]` và `item["column"]`, trong khi `quality.py` trả về `quality["checks"]`, với tên cột nằm trong `kwargs.column`. `.get("results")` trả rỗng một cách âm thầm, không báo lỗi.
- **Cách xử lý:** Sửa `reporting.py` đọc `checks` và `kwargs.column`, hiển thị `unexpected_count` (commit `3a93285`).
- **Cách xác minh sau khi sửa:** Chạy lại cả hai flow; báo cáo liệt kê đúng 3 expectation fail kèm số dòng vi phạm, và bảng GX trong `phase1_report.md` hiện đủ 8 dòng.
- **Điều học được:** Code phòng thủ (`.get(..., [])`) giúp tránh crash nhưng lại che mất lỗi tích hợp. Đây chính là một silent failure ngay trong code của mình. Phải chạy thử end-to-end sớm trên code thật của nhau, không chỉ test bằng dữ liệu giả.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** `crossref.py` gọi `/works` và lưu nguyên response vào `crossref_response.json`, rồi bóc thành `PaperRecord` trong `crossref_records.json` (bỏ thẻ JATS). `cleaning.py` tính `age_days`, ghép `text_for_embedding` 5 phần và dedup theo `paper_id`. Dataframe qua quality gate xong mới được MiniLM embed và ghi vào Chroma collection (cosine).
2. **Evaluation:** mỗi câu hỏi mang `ground_truth_doc_ids` là `paper_id` của bài được hỏi. `retrieval_hit` đúng khi `paper_id` đó nằm trong top-4 truy xuất, còn Token F1 so câu trả lời với `ground_truth` lấy từ dữ liệu sạch. Hai chỉ số này tách được hai loại lỗi: tìm sai tài liệu, và tìm đúng tài liệu nhưng nội dung đã hỏng.
3. **Quality khác freshness:** quality checks (GX) kiểm tra tính *hợp lệ* của từng bản ghi (null, unique, độ dài), trả lời câu "dữ liệu có hỏng không". Freshness đo *độ mới* của cả tập (tỷ lệ bài quá 180 ngày), trả lời câu "dữ liệu còn đúng với hiện tại không". Dữ liệu có thể hoàn toàn hợp lệ mà vẫn cũ, như lỗi `stale_date`: GX không bắt được, chỉ freshness bắt được.
4. **Cùng test set:** nếu sinh lại câu hỏi từ dữ liệu lỗi, ground truth cũng mang chính lỗi đó (ngày bị lùi, title bị cắt), và agent sẽ được chấm "đúng" trên dữ liệu sai. Chỉ khi giữ nguyên câu hỏi và đáp án từ dữ liệu sạch thì chênh lệch chỉ số mới phản ánh tác động của dữ liệu.
5. **Repair thành công dựa trên:** (a) log idempotent 24/24 dòng khớp baseline; (b) `repaired_quality_report.json` có `success = true` và freshness `is_fresh = true`; (c) `repaired_metrics.json` bằng `baseline_metrics.json`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.00 | 0.60 | 1.00 | Toàn bộ mức giảm đến từ `drop_latest_records` |
| `mean_token_f1` | 1.00 | 0.50 | 1.00 | Giảm sâu hơn hit rate: có lỗi làm hỏng câu trả lời dù truy xuất vẫn đúng |
| `judge_accuracy` | 1.00 | 0.50 | 1.00 | Heuristic judge (`mock`), bám theo F1, không phải đánh giá độc lập |
| `mean_judge_score` | 5.00 | 3.00 | 5.00 | Như trên |
| Quality checks | 8/8 PASS | 5/8 → FAIL | 8/8 PASS | Bắt được duplicate, blank summary, truncate title |
| Freshness status | Fresh (0%) | Stale (40.9%) | Fresh (0%) | Bắt được `stale_date` |

### Kết luận từ số liệu

1. `stale_date` lùi `published` 365 ngày ở 8 dòng → freshness chuyển Stale (9/22 = 40.9% > 25%) → eval_003 vẫn truy xuất **đúng** tài liệu nhưng trả lời `2025-08-01` thay vì `2026-08-01` (F1 = 0).
2. Repair rebuild từ raw → gate 8/8 PASS và freshness Fresh → hit rate và Token F1 trở về 1.00, vì dữ liệu trùng khớp 24/24 dòng với baseline.

**Corruption ảnh hưởng rõ nhất:** `drop_latest_records` gây thiệt hại lớn nhất về số (4/10 câu mất tài liệu đích), và **gate hiện tại không phát hiện được**, vì 22 dòng vẫn nằm trong ngưỡng 5–5000. Nguy hiểm nhất về bản chất là `stale_date`: agent trả lời trôi chảy và tự tin nhưng sai sự thật, đúng kịch bản "chính sách hoàn tiền cũ" trong đề bài.

**Khác kỳ vọng:** eval_004 (`categories`) truy xuất sai tài liệu nhưng Token F1 vẫn bằng 1.0. Kiểm tra `corrupted_answers.json` thì thấy bài đích không có `container-title`, nên categories chỉ còn `posted-content`, và một bài khác cùng loại tình cờ trùng chữ. Như vậy Token F1 có false positive với các câu trả lời ngắn và chung chung, nên phải đọc nó cùng với `retrieval_hit`.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** Bảo toàn raw là điều kiện để repair idempotent. Không có `crossref_records.json` gốc thì không thể khôi phục các bài đã bị drop, vì không có gì để vá.
2. **Về observability:** Gate chỉ mạnh bằng bộ expectation của nó. GX bắt được 3/6 loại lỗi, freshness bắt thêm 1; `drop_latest_records` và `inject_noise` lọt qua dù làm hit rate giảm 0.40. "Gate PASS" không có nghĩa là "dữ liệu tốt".
3. **Về ảnh hưởng tới RAG agent:** Dữ liệu lỗi không làm agent báo lỗi mà làm nó trả lời sai một cách tự tin. Retrieval có thể đúng 100% mà câu trả lời vẫn sai, vì vậy cần đo cả retrieval lẫn answer quality.

### Nếu có thêm thời gian

Bổ sung expectation so sánh số dòng với lần chạy trước (cảnh báo khi giảm hơn 10%) để bắt `drop_latest_records`, và kiểm tra tỷ lệ ký tự không phải chữ trong `summary` để bắt `inject_noise`. Cách đo: chạy lại `run_corruption_flow.py`; kỳ vọng `corrupted_quality_report.json` liệt kê thêm 2 expectation fail, tức gate bắt được 5/6 loại lỗi thay vì 3/6. Ngoài ra, chạy lại với `LLM_PROVIDER=gemini` để có LLM judge thật.

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hoàng Trung Hiếu
**Ngày xác nhận:** [YYYY-MM-DD]
