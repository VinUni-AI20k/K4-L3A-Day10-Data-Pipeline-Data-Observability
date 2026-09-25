# Member Role Report — Day 10: Data Pipeline & Data Observability

> NHÁP: đổi tên file thành `<MSSV>_HoTen.md`. Các mục còn `[ ]` chỉ điền sau khi chạy thật `run_phase1.py` và `run_corruption_flow.py`. Mục 7, 9, 10 phải viết bằng lời của chính bạn.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | [Họ và tên]             |
| MSSV               | [MSSV]                     |
| Khóa/Lớp         | K4                         |
| Tên nhóm         | [Tên hoặc mã nhóm]     |
| Vai trò chính    | Pipeline Lead & Integrator |
| Repository         | [Đường dẫn repository] |
| Ngày hoàn thành | [YYYY-MM-DD]               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline pipeline | `src/pipelines/phase1.py::main`, `script/run_phase1.py` | raw records, hàm của Người 2/3/4 | clean, index `papers-baseline`, `baseline_metrics.json`, `phase1_report.md` | Code xong, [chưa chạy end-to-end] |
| Corruption/repair flow | `src/pipelines/corruption_flow.py::main`, `script/run_corruption_flow.py` | artifact của Phase 1 | `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` | Code xong, [chưa chạy end-to-end] |
| Tiện ích lưu dữ liệu | `src/core/utils.py::write_dataframe` | DataFrame | CSV + JSON cùng lúc | Hoàn thành |
| Tích hợp & bàn giao | review, merge `main`, `docs/TEAM.md`, `report/group_report.md` | PR của Người 2/3/4 | repo nộp bài | [Đang làm] |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| [Debug/tích hợp] | [Tên hoặc module] | [Kết quả và bằng chứng] |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Nối luồng baseline | `phase1.py` | [artifact Phase 1] | `python script/run_phase1.py` |
| Nối luồng corrupt → repair → so sánh | `corruption_flow.py` | [artifact Phase 2] | `python script/run_corruption_flow.py` |

Output cụ thể: [Dán bảng 3 trạng thái in ra console sau khi chạy thật.]

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module (ingestion, quality, retrieval, evaluation) do 3 người khác nhau viết. Cần một điểm điều phối duy nhất để chạy đúng thứ tự, lưu đúng artifact ở đúng đường dẫn trong `core/config.py`, và chứng minh được Silent Failure cùng khả năng repair.

### Cách triển khai

- **Quality Gate chạy trước khi index** (`phase1.py`): nếu dữ liệu baseline fail thì pipeline dừng, dữ liệu xấu không vào ChromaDB.
- **Test set cố định**: chỉ sinh lần đầu (hoặc `REFRESH_TEST_SET=1`); baseline, corrupted, repaired đều đo trên cùng `test_set.json` nên phép so sánh có ý nghĩa.
- **Mỗi trạng thái một collection** (`papers-baseline`, `papers-corrupted`, `papers-repaired`) bằng cách truyền đúng đường dẫn embeddings vào `LocalEmbeddingIndex.build`, để không ghi đè lẫn nhau.
- **Corrupted vẫn được index dù gate fail**: trong production sẽ chặn ở gate, nhưng lab cần đo mức suy giảm nên chỉ in cảnh báo.
- **Idempotent Repair**: repaired data luôn được dựng lại từ `data/raw/crossref_records.json` bằng chính `build_clean_dataframe`, không vá dữ liệu hỏng, nên chạy lại bao nhiêu lần vẫn cho cùng kết quả. Nếu repaired vẫn fail gate thì dừng thay vì báo repair thành công.
- **Demo agent không làm sập pipeline**: lỗi provider/thiếu key chỉ được ghi vào `agent_demo_answers.json`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `data/raw/crossref_records.json`, biến môi trường `.env` |
| Output | `data/clean/`, `data/chroma/`, `data/eval/test_set.json`, `data/quality/`, `data/results/`, `data/reports/` |
| Module phụ thuộc | `ingestion.*`, `observability.*`, `evaluation.*`, `retrieval.index` |
| Module sử dụng output | `corruption_flow.py` dùng `baseline_metrics.json`, `papers_clean.json`, `test_set.json` của Phase 1 |
| Điều kiện lỗi cần xử lý | Thiếu artifact Phase 1 (báo rõ file nào thiếu); baseline fail gate; repaired fail gate |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** exit code 0, đủ artifact, corrupted giảm so với baseline, repaired phục hồi.
- **Kết quả thực tế:** [Điền sau khi chạy.]
- **Artifact/log:** [Đường dẫn.]

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Có nên dừng pipeline khi Quality Gate của dữ liệu corrupted fail?
- **Các phương án đã cân nhắc:** (a) dừng ngay như production; (b) vẫn index và đo để lấy số liệu suy giảm.
- **Phương án đã chọn:** (b) cho corrupted; (a) cho baseline và repaired.
- **Lý do:** Bài lab cần số liệu Silent Failure; baseline và repaired là dữ liệu phải tin cậy nên fail thì dừng.
- **Bằng chứng quyết định phù hợp:** [Số liệu corrupted vs baseline sau khi chạy.]

## 6. Một lỗi hoặc blocker đã xử lý

[Điền lỗi thật gặp khi ghép module. Không viết nếu chưa xảy ra.]

## 7. Hiểu biết về luồng end-to-end

[Tự viết bằng lời của bạn, trả lời 5 câu hỏi của mẫu gốc.]

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | [ ] | [ ] | [ ] | |
| `mean_token_f1` | [ ] | [ ] | [ ] | |
| `judge_accuracy` | [ ] | [ ] | [ ] | |
| `mean_judge_score` | [ ] | [ ] | [ ] | |
| Quality checks | [ ] | [ ] | [ ] | |
| Freshness status | [ ] | [ ] | [ ] | |

## 9. Điều học được và hướng cải thiện

[Tự viết.]

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** [Họ và tên]
**Ngày xác nhận:** [YYYY-MM-DD]
