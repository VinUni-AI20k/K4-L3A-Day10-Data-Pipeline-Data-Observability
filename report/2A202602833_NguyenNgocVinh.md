# Báo cáo cá nhân — Nguyễn Ngọc Vĩnh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Ngọc Vĩnh |
| MSSV | 2A202602833 |
| Lớp/Nhóm | K4-L3A / Invisible |
| Vai trò | Data Observability, Evaluation & Reporting |
| Repository | https://github.com/MinMinhMin/K4-L3-DAY10-Invisible-DataPipeline |

## 2. Vai trò và phạm vi

| Phần việc | File chính | Output | Trạng thái |
| --- | --- | --- | --- |
| Quality/freshness | `observability/quality.py` | GX và freshness reports | Hoàn thành |
| Test set/metrics | `evaluation/testset.py`, `metrics.py` | 10 câu, answers và metrics | Hoàn thành |
| Reporting | `observability/reporting.py` | Hai Markdown reports | Hoàn thành |

Tôi hỗ trợ ingestion chốt required columns và pipeline đối chiếu report với artifact.

## 3. Kết quả theo vai trò

- GX 1.x ephemeral chạy sáu expectations, không sinh project rác.
- Freshness SLA: stale khi trên 180 ngày, toàn tập cho phép tối đa 25%.
- Test set có 10 câu thuộc 5 loại và DOI ground truth.
- Báo cáo so sánh trực tiếp baseline/corrupted/repaired.

Artifact chính: `data/quality/*quality_report.json`, `data/results/*metrics.json` và `data/reports/`.

## 4. Giải thích kỹ thuật

Trước GX, required blanks được đổi thành null; summary thiếu thành chuỗi rỗng để length expectation không bỏ qua. Freshness đếm invalid/stale ages và tính stale ratio. Test set chọn đại diện xác định từ baseline, còn evaluator tính retrieval hit, Token F1 và Judge; khi LLM ngoài không sẵn sàng, heuristic fallback được ghi rõ trong answers.

| Contract | Nội dung |
| --- | --- |
| Input | DataFrame, Chroma index, shared test set |
| Output | Quality/freshness, answers/metrics và reports |
| Lỗi xử lý | Missing columns, blanks, duplicate DOI, invalid age, unavailable LLM |

```powershell
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); q=run_data_quality_checks(pd.read_json(s.paths.clean_json),s,'test'); print(q['success'],q['statistics'])"
```

Kết quả: baseline `True`, 6 successful và 0 unsuccessful expectations.

## 5. Quyết định kỹ thuật

Tôi chuẩn hóa summary null thành `""` trước khi dùng minimum-length expectation. Nếu giữ null, GX có thể bỏ qua giá trị đó; cách hiện tại bắt đúng ba blank summaries trong corrupted data.

## 6. Blocker đã xử lý

- **Lỗi:** `ImportError: cannot import name 'load_or_create_test_set'`.
- **Nguyên nhân:** Module chưa có API object-style mà command yêu cầu.
- **Xử lý:** Hoàn thiện builder cho 5 question types, thêm `TestSet` và validation khi load.
- **Xác minh:** Command trả 10 samples; mỗi mẫu có id, type, question, ground truth và DOI.

## 7. Hiểu biết end-to-end

Crossref được làm sạch rồi index bằng MiniLM/Chroma. Shared test set so DOI top-k và answer với ground truth. Quality checks đo completeness, uniqueness, content validity; freshness đo tuổi dữ liệu theo SLA. Test set cố định giúp metric delta phản ánh corruption. Repair thành công khi GX/freshness PASS và retrieval/answer metrics bằng baseline.

## 8. Phân tích kết quả

| Signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Hit Rate | 100% | 70% | 100% |
| Token F1 | 0,9055 | 0,6775 | 0,9055 |
| Judge accuracy | 90% | 70% | 90% |
| Judge score | 4,4 | 3,4 | 4,4 |
| Quality | PASS 6/6 | FAIL 4/6 | PASS 6/6 |
| Stale ratio | 4,17% | 47,62% | 4,17% |

Blank/duplicate/stale làm quality và freshness FAIL; đồng thời Hit Rate còn 70% và Token F1 còn 0,6775. Repair đưa unexpected counts về 0, stale ratio về 4,17% và metrics về baseline. Truncate/noise chưa có check trực tiếp nên là khoảng trống cần bổ sung.

## 9. Điều học được

1. Benchmark phải cố định trước corruption.
2. Quality và freshness là hai nhóm tín hiệu bổ sung nhau.
3. Semantic corruption có thể lọt qua checks cấu trúc.

Hướng cải thiện: thêm title-length, noise-ratio và embedding-drift checks; mỗi scenario riêng phải kích hoạt ít nhất một cảnh báo.

## 10. Cam kết

Thành viên tự đánh dấu sau khi đọc:

- [ ] Nội dung phản ánh đúng phần việc của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end.
- [ ] Kết luận có artifact/metric đối chiếu.
- [ ] Báo cáo không chứa secret.

**Họ và tên:** Nguyễn Ngọc Vĩnh  
**Ngày xác nhận:** Chờ thành viên xác nhận
