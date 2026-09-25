# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Trường | Giá trị |
| --- | --- |
| Khóa/Lớp | K4 |
| Tên nhóm | `1Prompt4All` |
| Repository | [GitHub repository](https://github.com/D3vNguy3n/K4-L3A-Day10-Data-Pipeline-Data-Observability) |
| Ngày hoàn thành kỹ thuật | 2026-09-25 |

### Thành viên và phân công

| STT | Họ tên | MSSV | Vai trò | Phạm vi |
| ---: | --- | --- | --- | --- |
| 1 | Nguyễn Hoàng Lê Nguyên | `2A202602472` | Pipeline Integrator | `core/`, hai pipeline |
| 2 | Giang Thế Vũ | `2A202602478` | Data Foundation & Recovery | ingestion, cleaning, repair |
| 3 | Trần Đức Lộc | `2A202602431` | RAG & Vector Index | retrieval, embeddings, ChromaDB |
| 4 | Đặng Hữu Cương | `2A202602572` | Observability & Evaluation | GX, test set, reporting |

## 2. Tóm tắt kết quả

Pipeline đã chạy thành công ở cả hai pha trên snapshot Crossref gồm 24 bài báo. Baseline vượt quality gate và freshness SLA, đạt retrieval hit rate 100% và mean token F1 1.000 trên cùng test set 10 câu. Sáu kịch bản corruption làm quality/freshness cùng thất bại, giảm hit rate xuống 0% và token F1 xuống gần 0 trong lần chạy nghiệm thu gần nhất. Repair tái tạo dữ liệu trực tiếp từ raw lineage, đưa toàn bộ chỉ số về baseline; lần chạy repair thứ hai tạo checksum dữ liệu và metrics giống lần đầu.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API / offline snapshot
    -> parse và bảo toàn raw
    -> clean, deduplicate, age_days, text_for_embedding
    -> Great Expectations 1.x + freshness SLA
    -> MiniLM embeddings + ChromaDB
    -> fixed 10-question evaluation
    -> controlled six-scenario corruption
    -> isolated corrupted evaluation
    -> repair from raw lineage
    -> three-state comparison report
```

| Khối | Input | Xử lý chính | Output |
| --- | --- | --- | --- |
| Ingestion | Crossref payload/snapshot | Retry, offline fallback, JATS cleanup, date/author parsing | `data/raw/` |
| Cleaning | `PaperRecord` | Normalize, validate, deduplicate DOI, compute `age_days` | `data/clean/papers_clean.*` |
| Observability | Clean/corrupted dataframe | 6 GX expectation instances thuộc 4 loại bắt buộc + freshness SLA | `data/quality/` |
| Index | `text_for_embedding` | `all-MiniLM-L6-v2`, cosine HNSW, 3 collections tách biệt | `data/chroma/`, `data/embeddings/` |
| Evaluation | Fixed test set | Hit rate, token F1, judge score | `data/results/` |
| Repair | Preserved raw records | Re-run cleaning và indexing, không dùng corrupted artifact | repaired artifacts |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Tham số | Giá trị |
| --- | --- |
| Python | 3.12.14 |
| `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / `gemini-2.5-flash` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; tối đa 25% stale |
| Source mode nghiệm thu | Offline parsed snapshot |

```powershell
uv sync --python 3.12 --extra dev
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

| Lệnh | Trạng thái | Bằng chứng |
| --- | --- | --- |
| `python script/run_phase1.py` | Thành công, exit 0 | `data/reports/phase1_report.md` |
| `python script/run_corruption_flow.py` | Thành công, exit 0 | `data/reports/corruption_report.md` |
| Chạy repair lần hai | Thành công | SHA-256 clean repaired và metrics không đổi |

## 5. Ingestion, cleaning và data contract

Nguồn mặc định là snapshot `data/raw/crossref_response.json`; khi `REFRESH_SOURCE=true`, pipeline gọi Crossref Works API với tối đa ba lần thử và exponential backoff cho lỗi mạng/429/5xx. Nếu live fetch thất bại, pipeline quay lại snapshot mà không ghi đè raw source bằng response lỗi.

| Trường clean | Kiểu | Bắt buộc | Xử lý |
| --- | --- | --- | --- |
| `paper_id` | string DOI | Có | Lowercase, trim, deduplicate |
| `title` | string | Có | Strip markup/normalize whitespace |
| `summary` | string | Có | Strip JATS/HTML; tối thiểu 30 ký tự |
| `authors`, `categories` | list[string] | Không | Normalize và deduplicate nội bộ |
| `published`, `updated` | ISO date | Có/Không | Parse nhiều trường ngày Crossref |
| `age_days` | integer | Có | `run_date - published` |
| `text_for_embedding` | string | Có | Ghép title, authors, date, categories, summary |

Kết quả cleaning: 24/24 raw records hợp lệ, 24 DOI duy nhất, không có record bị loại trong snapshot nghiệm thu.

## 6. Evaluation setup

Test set cố định tại `data/eval/test_set.json` có 10 câu thuộc bốn loại `summary`, `authors`, `date`, `categories`. Mỗi mẫu có `id`, `question_type`, `question`, `ground_truth` và `ground_truth_doc_ids`. Cả baseline, corrupted và repaired dùng đúng file này.

Ragas bị tắt theo mặc định (`RUN_RAGAS` chưa bật) để giữ luồng lab nhanh và offline. Vì môi trường nghiệm thu không có credential LLM, LLM judge sử dụng fallback heuristic đã được ghi rõ trong từng answer artifact; retrieval hit rate và token F1 vẫn là phép đo trực tiếp.

## 7. Kết quả baseline

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.000 | Cả 10 câu lấy được ground-truth document |
| `mean_token_f1` | 1.000 | Câu trả lời trích xuất khớp ground truth |
| `judge_accuracy` | 1.000 | Heuristic judge đánh giá đúng cả 10 câu |
| `mean_judge_score` | 5.000 | Điểm trung bình tối đa |
| Ragas | Skipped | Chỉ chạy khi `RUN_RAGAS=1` |

Ba Chroma collections `papers-baseline`, `papers-corrupted`, `papers-repaired` đều tồn tại và chứa 24 documents trong lần nghiệm thu.

## 8. Data quality và freshness

| Check | Ngưỡng | Baseline | Artifact |
| --- | --- | --- | --- |
| Row count | 5–5000 | Pass: 24 | `baseline_quality_report.json` |
| Required fields not null | `paper_id`, `title`, `text_for_embedding` | Pass | `baseline_quality_report.json` |
| DOI unique | 100% unique | Pass | `baseline_quality_report.json` |
| Summary length | >= 30 | Pass | `baseline_quality_report.json` |
| Freshness | `age_days > 180` không quá 25% | Pass: 1/24 stale (4.2%) | `freshness_report.json` |

Publication range của baseline là 2026-03-28 đến 2026-07-22.

## 9. Corruption scenarios và repair

| Scenario | Rows tác động | Biểu hiện |
| --- | ---: | --- |
| Drop latest records | 5 | Mất 20% tài liệu mới nhất |
| Blank summary | 5 gốc (10 sau duplicate) | Vi phạm độ dài summary |
| Inject text noise | 19 | Làm sai lệch vector context |
| Truncate title | 5 | Tiêu đề còn 7 ký tự |
| Stale date | 19 | Lùi publication date 5 năm |
| Duplicate rows | 5 | Khôi phục row count nhưng phá uniqueness |

Corruption log có đúng sáu scenario tại `data/results/corruption_log.json`. Repair không chỉnh tay corrupted dataframe; nó đọc lại `crossref_records.json`, chạy lại cleaning, quality, embedding và evaluation. Cách này giữ document identity ổn định và idempotent.

## 10. So sánh baseline, corrupted và repaired

| Metric | Baseline | Corrupted | Repaired | Corrupted delta | Recovery |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.000 | 0.000 | 1.000 | -1.000 | 100% |
| `mean_token_f1` | 1.000 | 0.007 | 1.000 | -0.993 | 100% |
| `judge_accuracy` | 1.000 | 0.000 | 1.000 | -1.000 | 100% |
| `mean_judge_score` | 5.000 | 1.000 | 5.000 | -4.000 | 100% |
| Quality gate | Pass | Fail | Pass | 2 GX checks fail | Restored |
| Freshness | Pass (4.2% stale) | Fail (100% stale) | Pass (4.2% stale) | +95.8 pp stale | Restored |

Số liệu chứng minh chuỗi nhân quả: corruption làm dữ liệu mất/blank/nhiễu/trùng/stale, GX và freshness phát cảnh báo, đồng thời retrieval/answer metrics giảm mạnh. Rebuild từ raw lineage loại bỏ các lỗi và đưa metrics về đúng baseline.

## 11. Vấn đề tích hợp quan trọng

- Triệu chứng ban đầu: `.venv` dùng Python 3.14 nhưng extension NumPy được build cho CPython 3.12, gây lỗi import `_multiarray_umath`.
- Nguyên nhân: interpreter và wheel ABI không đồng nhất; Python 3.14 cũng nằm ngoài constraint `<3.14` của dự án.
- Cách xử lý: tái tạo `.venv` bằng `uv sync --python 3.12 --extra dev`.
- Xác minh: import ChromaDB/GX/Sentence Transformers thành công và cả hai entrypoint exit 0.

## 12. Giới hạn và hướng cải thiện

- Judge hiện dùng heuristic fallback vì không có LLM credential trong môi trường nghiệm thu; có thể cấu hình key hợp lệ để chạy LLM-as-a-judge.
- Ragas mặc định bị tắt; có thể bật `RUN_RAGAS=1` và ghi nhận thêm faithfulness/context metrics.
- Token F1 của trạng thái corrupted có thể dao động nhẹ khi ANN phải phân giải nhiều noisy near-ties; hit rate vẫn ổn định ở 0% vì năm ground-truth documents đã bị loại bỏ có chủ đích.
- Live Crossref mode chưa được dùng cho số liệu báo cáo để giữ bộ dữ liệu và benchmark tái lập được.

## 13. Checklist trước khi nộp

- [ ] Mỗi thành viên tạo báo cáo `<MSSV>_HoTen.md` từ mẫu cá nhân.
- [x] Baseline và corruption flow chạy exit 0.
- [x] Cùng một test set được dùng cho ba trạng thái.
- [x] Metrics trong báo cáo khớp artifact hiện tại.
- [x] Quality/freshness kết luận khớp `data/quality/`.
- [x] `.env` bị Git ignore và không được track.
