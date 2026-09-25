# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                    |
| ------------------ | ------------------------------------------- |
| Họ và tên       | Đỗ Thành Đạt                               |
| MSSV               | 2A202602874                                 |
| Khóa/Lớp         | K4-L3-DAY10                                |
| Tên nhóm         | GOHOME                                      |
| Vai trò chính    | Observability & Evaluation Engineer         |
| Repository         | https://github.com/Nam-phuong624/K4-L3A-Day10-Data-Pipeline-Data-Observability              |
| Ngày hoàn thành | 2026-09-25                                  |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable      | File/hàm phụ trách                       | Input nhận vào            | Output bàn giao                              | Trạng thái |
| ----------------------- | ------------------------------------------ | ------------------------- | -------------------------------------------- | ---------- |
| GX 1.x quality checks   | `src/observability/quality.py`            | clean DataFrame           | `baseline_quality_report.json` (6 checks)   | Hoàn thành |
| Freshness SLA           | `src/observability/quality.py`            | clean DataFrame           | `freshness_report.json`                      | Hoàn thành |
| Evaluation test set     | `src/evaluation/testset.py`               | clean DataFrame           | `data/eval/test_set.json` (10 câu)          | Hoàn thành |
| Evaluation metrics      | `src/evaluation/metrics.py`              | index, test_set_path      | `baseline_metrics.json`, `baseline_answers.json` | Hoàn thành |
| Reports generation      | `src/observability/reporting.py`          | metrics, quality, freshness | `phase1_report.md`, `corruption_report.md`  | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                      | Thành viên/module được hỗ trợ   | Kết quả                                                        |
| ------------------------------- | ------------------------------------ | -------------------------------------------------------------- |
| Kiểm tra GX syntax ephemeral   | quality.py (toàn nhóm)               | Xác nhận dùng `gx.get_context(mode="ephemeral")` đúng GX 1.x |
| Chuẩn hóa column display       | reporting.py → phase1_report.md      | GX results hiển thị tên column rõ ràng thay vì duplicate      |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                              | File/hàm/artifact liên quan            | Kết quả bàn giao                          | Cách xác minh                          |
| -------------------------------------------------- | ---------------------------------------- | ------------------------------------------ | --------------------------------------- |
| Thiết lập 6 GX expectations (ephemeral context)  | `quality.py:run_data_quality_checks`   | `baseline_quality_report.json`: 6/6 pass  | Kiểm tra `"success": true` trong JSON |
| Freshness SLA với ngưỡng 25% / 180 ngày          | `quality.py:build_freshness_report`    | `freshness_report.json`: `is_fresh=true`  | Kiểm tra `"stale_ratio": 0.0417`      |
| Test set 10 câu (3 loại question)                | `testset.py:build_test_set`            | `data/eval/test_set.json`                 | `wc -l data/eval/test_set.json`        |
| Bảng đối chiếu 3 trạng thái đầy đủ              | `reporting.py:generate_corruption_report` | `corruption_report.md` (✅/❌ per state) | Đọc `data/reports/corruption_report.md` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phát hiện data corruption **trước khi** nó ảnh hưởng đến người dùng cuối (Silent Failure). GX kiểm tra tính hợp lệ cấu trúc, Freshness kiểm tra tính mới của dữ liệu theo thời gian — cả hai phải trigger khi data bị corrupt.

### Cách triển khai

**GX 1.x (ephemeral context) — 6 expectations:**
```python
context = gx.get_context(mode="ephemeral")  # không cần file config
data_source = context.data_sources.add_pandas(name="papers_source")
data_asset = data_source.add_dataframe_asset(name="papers_asset")
batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
suite = context.suites.add(gx.ExpectationSuite(name="papers_suite"))
```
6 checks theo thứ tự: row count (5–5000), paper_id not null, title not null, text_for_embedding not null, paper_id unique, summary length ≥ 30.

**Freshness SLA:**
- Threshold: 180 ngày. Record `stale = age_days > 180`.
- `stale_ratio = stale_count / total`. Nếu `stale_ratio > 0.25` → `is_fresh=False`.
- Design choice: 25% threshold đảm bảo 1-2 bài stale vẫn acceptable (1/24 = 4.2%), nhưng corruption 6 bài (30.4%) sẽ trigger.

**Test set (10 câu, 3 loại):**
- 3 `summary` questions: "What is '...' about?" → ground-truth = first sentence of summary.
- 3 `authors` questions: "Who authored '...'?" → ground-truth = `authors_joined`.
- 2 `date` questions: "When was '...' published?" → ground-truth = `published`.
- 2 `categories` questions: "What categories does '...' belong to?" → ground-truth = `categories_joined`.
- Question patterns phải khớp chính xác với keywords trong `qa.py:_extract_answer` để extraction đúng.

### Input, output và contract

| Thành phần           | Mô tả                                                               |
| -------------------- | ------------------------------------------------------------------- |
| Input                | clean DataFrame từ `cleaning.py`                                   |
| Output               | 3 JSON reports trong `data/quality/`, 1 JSON test set, metrics JSON |
| Module phụ thuộc    | `core/config.py` (thresholds), `core/utils.py` (write_json)       |
| Module sử dụng output | `corruption_flow.py` (load baseline quality/freshness cho compare) |
| Điều kiện lỗi       | GX `ValidationResult` lấy statistics qua `getattr` defensive       |

### Cách xác minh

```bash
conda run -n vin python script/run_phase1.py
# Bước [7/7]: "GX success=True  is_fresh=True"
# Kiểm tra: cat data/quality/baseline_quality_report.json | python -m json.tool
```

- **Kết quả mong đợi:** 6/6 expectations pass, `is_fresh=True`, `stale_ratio=0.0417`.
- **Kết quả thực tế:** Đúng như mong đợi.
- **Artifact/log:** `data/quality/baseline_quality_report.json`, `data/quality/freshness_report.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** GX 1.x thay đổi hoàn toàn API so với phiên bản cũ — `context.sources.pandas_default` và `context.run_checkpoint()` không còn tồn tại.
- **Các phương án:** (1) Dùng file-based context (cần `great_expectations.yml`). (2) Dùng ephemeral context (in-memory, không cần config file).
- **Phương án đã chọn:** Ephemeral context (`mode="ephemeral"`) — `gx.get_context(mode="ephemeral")`.
- **Lý do:** Pipeline phải reproducible và portable — không nên phụ thuộc vào file config GX nằm ngoài repo. Ephemeral context tự tạo và xóa trong cùng một run.
- **Bằng chứng:** Pipeline chạy sạch không cần `great_expectations/` directory trong repo.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Phase1 report hiển thị `expect_column_values_to_not_be_null` 3 lần liên tiếp không có thông tin column → người đọc không biết check nào là của column nào.
- **Nguyên nhân gốc:** `generate_phase1_report` chỉ lấy `r["expectation"]` nhưng không lấy `r["kwargs"]["column"]` để hiển thị cùng.
- **Cách xử lý:**
  ```python
  col = r.get("kwargs", {}).get("column", "")
  col_label = f" (column: {col})" if col else ""
  lines.append(f"  - [{status}] {r['expectation']}{col_label}")
  ```
- **Cách xác minh:** Đọc `data/reports/phase1_report.md` — 3 null checks phải hiển thị `(column: paper_id)`, `(column: title)`, `(column: text_for_embedding)`.
- **Điều học được:** Report không chỉ cần đúng về logic — cần đủ context để người đọc hiểu mà không cần tra file JSON gốc.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** Nhìn từ góc QA, data đi qua 3 checkpoint trước khi vào vector store: (1) parse lọc bỏ record thiếu DOI/title, (2) clean chuẩn hóa schema, (3) GX kiểm tra 6 expectations. Chỉ khi pass cả 3 thì data mới được phép index — đây là "quality gate" trong pipeline.
2. **Evaluation:** Có 3 lớp đo: `hit_rate` đo retrieval layer (có lấy đúng paper không), `token_f1` đo extraction layer (answer có đúng từ không), `judge_score` đo answer quality tổng thể. Ba lớp này độc lập — retrieval đúng chưa chắc extraction đúng, extraction đúng chưa chắc judge cho điểm cao.
3. **Quality vs Freshness:** GX là "unit test" — assert từng property cụ thể (null, unique, length). Freshness là "timeliness check" — assert relationship giữa data và đồng hồ thực tế. GX có thể pass toàn bộ nhưng freshness vẫn fail (data structurally correct nhưng outdated). Cần cả hai vì chúng catch lỗi ở hai chiều khác nhau.
4. **Cùng test set:** Nguyên tắc testing cơ bản — một test case chỉ thay đổi một variable tại một thời điểm. Đây là controlled experiment: data thay đổi, evaluation set cố định → metrics thay đổi chỉ có thể do data.
5. **Repair thành công dựa trên 3 signals đồng thời:** `repaired_metrics.json` khớp baseline (quantitative pass), GX `success=True` (structural pass), `is_fresh=True` (temporal pass). Thiếu một signal nào là repair chưa hoàn toàn.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét cá nhân                                          |
| ---------------------- | -------: | --------: | -------: | --------------------------------------------------------- |
| `retrieval_hit_rate`  |   1.0000 |    0.8000 |   1.0000 | GX gate báo fail trước — retrieval giảm là hệ quả, không phải nguyên nhân |
| `mean_token_f1`       |   1.0000 |    0.5882 |   1.0000 | 3 blank_summary → F1=0 kéo trung bình xuống mạnh hơn tỉ lệ thực              |
| `judge_accuracy`      |   1.0000 |    0.6000 |   1.0000 | 4 test case fail — đủ để kết luận corruption có tác động có hệ thống        |
| `mean_judge_score`    |        5 |    3.2000 |        5 | 3.2 là trung bình, không phải đều 3 — một số câu vẫn đúng hoàn toàn         |
| Quality checks         |     Pass |      Fail |     Pass | Đúng 2 expectations fail: uniqueness (duplicate) + length (blank)            |
| Freshness status       |     True |     False |     True | Freshness và GX fail độc lập — hai lớp phòng thủ hoạt động đúng thiết kế   |

### Kết luận từ số liệu

1. `blank_summary` → `expect_column_value_lengths_to_be_between` (column: summary) FAIL + `duplicate_rows` → `expect_column_values_to_be_unique` (column: paper_id) FAIL → GX `success=False` → đây là signal cảnh báo sớm trước khi check metrics.
2. Rebuild từ raw snapshot → GX 6/6 pass → mọi structural violations đã giải quyết → metrics phục hồi 1.0.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **GX 1.x ephemeral context là cách đúng:** File-based context tạo dependency vào config ngoài code — ephemeral reproducible hơn cho CI/CD.
2. **Test set phải được thiết kế cẩn thận:** Question patterns phải khớp chính xác với extraction logic — nếu "Who wrote" thay vì "Who authored" thì extraction không trigger đúng pattern.
3. **Quality Gate và Freshness là 2 lớp phòng thủ độc lập:** GX không thể detect temporal drift, Freshness không thể detect structural corruption — cần cả hai để coverage đầy đủ.

### Nếu có thêm thời gian

Thêm `expect_column_values_to_match_regex` cho `published` field (format YYYY-MM-DD) vào GX suite — hiện tại corruption `stale_date` không vi phạm length/null nhưng vi phạm format date logic, regex check sẽ catch được thêm.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đỗ Thành Đạt
**Ngày xác nhận:** 2026-09-25
