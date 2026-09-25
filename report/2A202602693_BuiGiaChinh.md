# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                     |
|-----------------|--------------------------------------------------------------|
| Họ và tên       | Bùi Gia Chính                                                |
| MSSV            | 2A202602693                                                  |
| Khóa/Lớp        | K4-L3-DAY10                                                  |
| Tên nhóm        | DCCC                                                         |
| Vai trò chính   | Data Foundation & Recovery                                   |
| Repository      | https://github.com/mysorf-9239/K4-L3-DAY10-DCCC-DataPipeline |
| Ngày hoàn thành | 2026-09-25                                                   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable  | File/hàm phụ trách | Input nhận vào        | Output bàn giao                 | Trạng thái |
|---------------------|--------------------|-----------------------|---------------------------------|------------|
| Crossref ingestion  | `crossref.py`      | API/snapshot payload  | 24 normalized raw records       | Hoàn thành |
| Cleaning/data model | `cleaning.py`      | `PaperRecord` list    | Clean CSV/JSON                  | Hoàn thành |
| Corruption suite    | `corruption.py`    | Clean dataframe       | Corrupted data + 6-scenario log | Hoàn thành |
| Repair input        | Raw records        | Immutable source data | Rebuild-ready records           | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động               | Thành viên/module được hỗ trợ | Kết quả                       |
|-------------------------|-------------------------------|-------------------------------|
| Thống nhất clean schema | Retrieval/Observability       | Stable fields cho index và GX |
| Kiểm tra repaired data  | Pipeline Lead                 | Repaired JSON bằng baseline   |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao            | Cách xác minh              |
|-----------------------|-----------------------------|-----------------------------|----------------------------|
| Parse DOI/JATS/date   | `parse_crossref_payload`    | 24 valid papers             | Fetch smoke command        |
| Clean/deduplicate     | `build_clean_dataframe`     | 24 unique rows              | Clean smoke command        |
| Tiêm lỗi có kiểm soát | `corrupt_clean_dataframe`   | 6 scenarios, output 24 rows | `corruption_log.json`      |
| Hỗ trợ repair         | `crossref_records.json`     | Source of truth ổn định     | Baseline/repaired equality |

Output tiêu biểu là `data/results/corruption_log.json`, ghi rõ loại lỗi, số record tác động, DOI liên
quan và replacement date để truy vết thay đổi.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref payload có nested fields, JATS markup và ngày không đồng nhất. Data phải được chuẩn hóa trước
khi quality/index sử dụng, đồng thời raw source phải đủ tin cậy để repair sau corruption.

### Cách triển khai

Parser lowercase DOI, normalize whitespace, unescape/remove XML tags, ghép author names và chọn ISO
date. Fetcher retry ba lần với exponential backoff rồi fallback local. Cleaning parse UTC, tính
`age_days`, joined fields, summary length và embedding text; cuối cùng deduplicate theo DOI. Corruption
deterministically drop, blank, noise, truncate, stale và duplicate để kết quả có thể tái hiện.

### Input, output và contract

| Thành phần              | Mô tả                                                         |
|-------------------------|---------------------------------------------------------------|
| Input                   | Crossref payload hoặc normalized raw JSON                     |
| Output                  | `PaperRecord` list; clean/corrupted dataframe; corruption log |
| Module phụ thuộc        | `core.config`, `core.utils`, pandas                           |
| Module sử dụng output   | Quality, retrieval, evaluation, pipelines                     |
| Điều kiện lỗi cần xử lý | HTTP 429/503, JSON lỗi, thiếu DOI/title/date, duplicate DOI   |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); print(len(fetch_source_records(s)))"
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); print(len(build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc))))"
```

- **Kết quả mong đợi:** Hai lệnh đều in `24`.
- **Kết quả thực tế:** 24 raw và 24 clean unique records.
- **Artifact/log:** `data/raw/`, `data/clean/`, `data/results/corruption_log.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair có thể vá corrupted dataframe hoặc rebuild từ raw.
- **Các phương án đã cân nhắc:** Patch từng lỗi; copy baseline; rebuild raw.
- **Phương án đã chọn:** Rebuild raw qua chính cleaning contract.
- **Lý do:** Không che lỗi, deterministic và không tích lũy duplicate.
- **Bằng chứng quyết định phù hợp:** Repaired data bằng baseline; unique DOI và summary checks PASS.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Crossref có thể timeout hoặc trả status lỗi trong phòng lab.
- **Lệnh hoặc bước tái hiện:** Chạy fetch khi mạng không khả dụng.
- **Nguyên nhân gốc:** Nguồn API bên ngoài không đảm bảo availability.
- **Cách xử lý:** Retry/backoff và fallback `crossref_response.json`.
- **Cách xác minh sau khi sửa:** Fetch vẫn trả 24 papers khi dùng snapshot.
- **Điều học được:** Raw preservation vừa phục vụ lineage vừa là cơ chế resilience.

## 7. Hiểu biết về luồng end-to-end

1. Crossref được lưu raw, parse, clean rồi đưa vào MiniLM/Chroma.
2. DOI ổn định nối clean records với ground-truth document IDs để tính Hit Rate.
3. GX kiểm completeness/uniqueness; freshness đo tỷ lệ records quá 180 ngày.
4. Cùng test set giữ phép so sánh không đổi giữa ba data states.
5. Repair thành công khi clean equality, quality/freshness và metrics đều phục hồi.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal        | Baseline | Corrupted | Repaired | Nhận xét của cá nhân                        |
|----------------------|---------:|----------:|---------:|---------------------------------------------|
| `retrieval_hit_rate` |    1.000 |     0.000 |    1.000 | Drop target documents gây tác động lớn nhất |
| `mean_token_f1`      |    0.963 |     0.451 |    0.963 | Blank/noise làm câu trả lời kém             |
| `judge_accuracy`     |    1.000 |     0.500 |    1.000 | Phục hồi hoàn toàn                          |
| `mean_judge_score`   |    4.800 |     2.600 |    4.800 | Phục hồi hoàn toàn                          |
| Quality checks       |     PASS |      FAIL |     PASS | Duplicate và summary rỗng bị bắt            |
| Freshness status     |     PASS |      FAIL |     PASS | Stale ratio tăng lên 66.67%                 |

### Kết luận từ số liệu

1. Drop latest + duplicate bù row count → uniqueness/freshness FAIL → Hit Rate về 0 dù vẫn có 24 rows.
2. Rebuild raw → 24 unique clean rows → quality và RAG metrics trở lại baseline.

Corruption ảnh hưởng rõ nhất là drop latest records. Kết quả khác trực giác là row count vẫn bằng 24;
corruption log và uniqueness report chứng minh records mới đã bị thay bằng duplicates.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw layer phải bất biến để làm lineage và recovery source.
2. Deduplication cần stable business key là DOI.
3. Data volume không thay thế được completeness/uniqueness checks.

### Nếu có thêm thời gian

Thêm schema validation cho từng Crossref field và property-based tests với payload thiếu/nested date lạ;
đo cải thiện bằng coverage parser và số edge cases được xử lý.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.
