# Báo cáo cá nhân — Nguyễn Vũ Quang Anh

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Vũ Quang Anh |
| MSSV | 2A202602805 |
| Lớp/Nhóm | K4-L3A / Invisible |
| Vai trò | Pipeline Integrator & Core Configuration |
| Repository | https://github.com/MinMinhMin/K4-L3-DAY10-Invisible-DataPipeline |

## 2. Vai trò và phạm vi

| Phần việc | File chính | Output | Trạng thái |
| --- | --- | --- | --- |
| Cấu hình và đường dẫn | `core/config.py`, `utils.py` | Settings/artifact paths thống nhất | Hoàn thành |
| Điều phối hai pipeline | `pipelines/phase1.py`, `corruption_flow.py` | Baseline, corrupted, repaired artifacts | Hoàn thành |
| LLM và entrypoint | `retrieval/llm.py`, `agent.py`, `script/` | Provider abstraction và lệnh chạy | Hoàn thành |

Tôi hỗ trợ các thành viên thống nhất data contract và chạy smoke test end-to-end.

## 3. Kết quả theo vai trò

- Phase 1 tạo 24 clean records, baseline quality PASS và đầy đủ metrics/report.
- Corruption flow tạo 21 corrupted records, sau đó repair về 24 records.
- Tách ba collection: `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- Hai entrypoint đều chạy exit code 0 bằng provider `mock`.

Artifact chính: `data/reports/phase1_report.md` và `corruption_report.md`.

## 4. Giải thích kỹ thuật

Phase 1 chạy theo thứ tự ingest → clean → quality gate → index → test set → evaluation → report. Baseline phải PASS trước khi index được phục vụ. Phase 2 vẫn tiếp tục khi corrupted quality FAIL để đo silent failure, sau đó dựng repaired data mới từ raw snapshot và yêu cầu repaired quality PASS.

| Contract | Nội dung |
| --- | --- |
| Input | Settings, raw snapshot, shared test set |
| Output | Ba datasets/indexes, metrics, quality và reports |
| Lỗi xử lý | Thiếu artifact, empty data, quality FAIL, provider unavailable |

```powershell
$env:LLM_PROVIDER="mock"
python script/run_phase1.py
python script/run_corruption_flow.py
```

Kết quả: 24 → 21 → 24 dòng; Hit Rate 100% → 70% → 100%.

## 5. Quyết định kỹ thuật

Tôi chọn policy khác nhau cho quality gate: baseline/repaired FAIL thì dừng, corrupted FAIL thì ghi nhận và tiếp tục evaluation. Cách này vừa bảo vệ serving path vừa tạo được bằng chứng định lượng về tác động dữ liệu lỗi.

## 6. Blocker đã xử lý

- **Lỗi:** `NotImplementedError: Student task: implement phase1 pipeline.`
- **Nguyên nhân:** Entrypoint tồn tại nhưng orchestration còn là skeleton.
- **Xử lý:** Kết nối đầy đủ module, kiểm tra prerequisite và persist artifact theo đúng thứ tự.
- **Xác minh:** Hai pipeline exit code 0; không còn `TODO(student)` hoặc `NotImplementedError` trong `src/`.

## 7. Hiểu biết end-to-end

Crossref được parse và làm sạch để tạo text embedding; MiniLM/Chroma tạo retrieval layer. Shared test set dùng DOI ground truth để chấm retrieval và answer quality. GX kiểm tra completeness/uniqueness/content, còn freshness kiểm tra `age_days`. Repair thành công khi dữ liệu trở về 24 DOI, GX 6/6 PASS và metrics bằng baseline.

## 8. Phân tích kết quả

| Signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Hit Rate | 100% | 70% | 100% |
| Token F1 | 0,9055 | 0,6775 | 0,9055 |
| Judge accuracy | 90% | 70% | 90% |
| Judge score | 4,4 | 3,4 | 4,4 |
| Quality | PASS 6/6 | FAIL 4/6 | PASS 6/6 |
| Stale ratio | 4,17% | 47,62% | 4,17% |

Corruption làm quality/freshness FAIL và Hit Rate giảm 30 điểm phần trăm. Rebuild từ raw khôi phục toàn bộ quality và metrics. Title truncation/text noise chưa bị GX bắt trực tiếp, nên quality suite vẫn cần mở rộng.

## 9. Điều học được

1. Orchestration phải định nghĩa dependency và failure policy rõ ràng.
2. Artifact/collection isolation giúp so sánh ba trạng thái đáng tin cậy.
3. Data lỗi có thể làm RAG suy giảm mà ứng dụng không phát sinh exception.

Hướng cải thiện: thêm run manifest chứa config hash, test-set hash và model version.

## 10. Cam kết

Thành viên tự đánh dấu sau khi đọc:

- [ ] Nội dung phản ánh đúng phần việc của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end.
- [ ] Kết luận có artifact/metric đối chiếu.
- [ ] Báo cáo không chứa secret.

**Họ và tên:** Nguyễn Vũ Quang Anh  
**Ngày xác nhận:** Chờ thành viên xác nhận
