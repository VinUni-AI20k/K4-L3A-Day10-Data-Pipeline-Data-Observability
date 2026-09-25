# Kế hoạch hoàn thiện bài theo `docs/Guide.md`

## Mục tiêu và nguyên tắc

- Đi tuần tự theo 8 bước trong `docs/Guide.md`; chỉ chuyển bước khi đạt tín hiệu hoàn thành.
- Pipeline đích: Crossref/raw → cleaning → Quality Gate & Freshness → test set → ChromaDB/RAG → evaluation → corruption → repair.
- Đạt đủ 100 điểm bắt buộc theo `docs/RUBRIC.md` trước khi làm bonus.
- Không sửa tay `metrics`, `reports` hoặc raw data; mọi artifact phải được sinh từ code.
- Không commit `.env`, API key/token hoặc đường dẫn tuyệt đối.
- Cả 4 thành viên phải có commit trên `main`, cập nhật `docs/TEAM.md`, báo cáo cá nhân và nộp link repository trên VLearn LMS.

## Phân công cố định

| Người | Vai trò | File/module chính |
|---|---|---|
| Người 1 | Pipeline Lead & Integrator | `src/core/`, `src/pipelines/`, `script/`, tích hợp cuối |
| Người 2 | Data Foundation & Recovery | `src/ingestion/crossref.py`, `cleaning.py`, `corruption.py` |
| Người 3 | RAG & Vector Specialist | `src/retrieval/`, ChromaDB, LLM providers |
| Người 4 | Observability & Evaluation | `src/observability/`, `src/evaluation/`, metrics/reports |

Điền tên, MSSV, branch và đóng góp vào `docs/TEAM.md` trước khi merge code.

## Bước 1 — Khởi tạo môi trường và cấu hình

**Phụ trách:** Người 1 chủ trì; cả nhóm xác nhận môi trường.

**Việc cần làm:**

- Đứng tại root project; kiểm tra Python 3.11–3.13.
- Chạy `uv sync` hoặc tạo `.venv` rồi `python -m pip install -e .`.
- Tạo `.env` từ `.env.example`; chỉ điền key cục bộ, không commit file này.
- Kiểm tra `core.config.load_settings()` và các path artifact không dùng absolute path.

**Kiểm tra:**

```powershell
uv run python --version
uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
```

**Tín hiệu hoàn thành:** Python hợp lệ và console in `Môi trường sẵn sàng`.

## Bước 2 — Thu thập dữ liệu và bảo toàn raw

**Phụ trách:** Người 2; Người 1 review contract.

**File:** `src/ingestion/crossref.py`.

**Việc cần làm:**

- Parse Crossref thành `PaperRecord` với `paper_id`, `title`, `summary`, `authors`, `categories`, `published`.
- Loại HTML/XML khỏi abstract và loại record thiếu DOI/title.
- Hỗ trợ live Crossref API, retry `429/5xx` và fallback snapshot offline.
- Lưu nguyên payload vào `data/raw/crossref_response.json`.
- Lưu record đã parse vào `data/raw/crossref_records.json`.

**Kiểm tra:**

```powershell
uv run python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

**Tín hiệu hoàn thành:** tải/đọc được 24 bài báo và tồn tại đủ 2 raw artifacts.

## Bước 3 — Làm sạch dữ liệu và chuẩn bị text embedding

**Phụ trách:** Người 2; Người 3 kiểm tra schema cho retrieval.

**File:** `src/ingestion/cleaning.py`.

**Việc cần làm:**

- Hoàn thiện `build_clean_dataframe()`.
- Chuẩn hóa whitespace và text; parse ngày `published`/`updated`.
- Tính `age_days = (run_date - published).days`.
- Dedupe theo `paper_id` và loại dòng không hợp lệ.
- Tạo `authors_joined`, `categories_joined`, `summary_chars`.
- Tạo `text_for_embedding` theo format:

```text
Title: <title>
Authors: <authors>
Published: <published>
Categories: <categories>
Summary: <summary>
```

- Xuất `data/clean/papers_clean.csv` và `data/clean/papers_clean.json`.

**Kiểm tra:**

```powershell
uv run python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
```

**Tín hiệu hoàn thành:** clean dataframe có 24 dòng, `paper_id` duy nhất và có `text_for_embedding`.

## Bước 4 — Dựng Quality Gate và Freshness SLA

**Phụ trách:** Người 4; Người 2 cung cấp các case dữ liệu lỗi để kiểm thử.

**File:** `src/observability/quality.py`.

**Việc cần làm:**

- Dùng đúng Great Expectations 1.x:
  `gx.get_context(mode="ephemeral")` → Pandas Data Source → dataframe batch.
- Tạo 4 expectations bắt buộc:
  - row count từ 5 đến 5000;
  - non-null `paper_id`, `title`, `text_for_embedding`;
  - unique `paper_id`;
  - `summary` dài tối thiểu 30 ký tự.
- Tính Freshness: `age_days > 180`; nếu tỷ lệ quá 25% thì `is_fresh=False`.
- Ghi `baseline_quality_report.json` và `freshness_report.json` vào `data/quality/`.
- Không dùng API cũ `context.sources.pandas_default`.

**Kiểm tra:**

```powershell
uv run python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Quality check status =', res['success'])"
```

**Tín hiệu hoàn thành:** dữ liệu sạch trả `Quality check status = True`.

## Bước 5 — Tạo benchmark test set và hoàn thiện RAG

**Phụ trách:** Người 4 làm test set; Người 3 làm embedding/index/QA song song.

**Người 4 — evaluation:**

- Hoàn thiện `src/evaluation/testset.py`.
- Tạo 10 câu hỏi, đủ 4 loại: `summary`, `authors`, `date`, `categories`.
- Mỗi item có `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`.
- Lưu `data/eval/test_set.json`.

**Người 3 — retrieval:**

- Hoàn thiện embedding `sentence-transformers/all-MiniLM-L6-v2`.
- Build ChromaDB collection `papers-baseline` với metadata đầy đủ.
- Kiểm tra `search`, `lookup`, QA context và provider `mock`.
- Giữ khả năng tạo các collection `papers-corrupted` và `papers-repaired`.

**Kiểm tra test set:**

```powershell
uv run python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

**Tín hiệu hoàn thành:** test set có 10 câu; ChromaDB index được 24 documents.

## Bước 6 — Chạy baseline pipeline

**Phụ trách:** Người 1 tích hợp; Người 3–4 hỗ trợ debug retrieval/metrics.

**File:** `src/pipelines/phase1.py`, `script/run_phase1.py`.

**Việc cần làm:** nối đúng luồng:

```text
load/fetch raw → clean → quality gate → test set → ChromaDB → evaluate → phase1 report
```

**Chạy:**

```powershell
uv run python script/run_phase1.py
```

**Artifact bắt buộc:**

- `data/clean/papers_clean.csv` và `papers_clean.json`
- `data/chroma/`
- `data/eval/test_set.json`
- `data/results/baseline_metrics.json`
- `data/reports/phase1_report.md`

**Tín hiệu hoàn thành:** baseline có `retrieval_hit_rate`, `mean_token_f1`, answer artifacts và report Markdown được sinh từ kết quả thật.

## Bước 7 — Tiêm 6 dạng lỗi dữ liệu

**Phụ trách:** Người 2 triển khai; Người 4 kiểm tra Quality Gate; Người 3 rebuild index corrupted.

**File:** `src/ingestion/corruption.py`.

Triển khai đủ:

1. Drop latest records — bỏ 20% bài mới nhất.
2. Blank summary — làm rỗng summary.
3. Inject noise — chèn ký tự rác.
4. Truncate title — cắt title dưới 8 ký tự.
5. Stale date — lùi ngày 365 ngày.
6. Duplicate rows — nhân bản dòng.

**Kiểm tra:**

```powershell
uv run python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Corrupted {len(c)} dòng')"
```

**Tín hiệu hoàn thành:** `data/results/corruption_log.json` ghi đủ 6 lỗi và dữ liệu corrupted làm Quality Gate phát hiện lỗi tương ứng.

## Bước 8 — Đo suy giảm, repair và đối chiếu 3 trạng thái

**Phụ trách:** Người 1 điều phối; Người 2 repair từ raw; Người 3 index/evaluate; Người 4 report.

**File:** `src/pipelines/corruption_flow.py`, `script/run_corruption_flow.py`.

**Luồng bắt buộc:**

```text
clean baseline → corrupt → quality fail → corrupted evaluation
→ rebuild từ data/raw → repaired quality → repaired index/evaluation
→ Baseline vs Corrupted vs Repaired report
```

**Chạy:**

```powershell
uv run python script/run_corruption_flow.py
```

**Artifact bắt buộc:**

- `data/quality/corrupted_quality_report.json`
- `data/results/corrupted_metrics.json`
- `data/results/repaired_metrics.json`
- `data/reports/corruption_report.md`

**Tín hiệu hoàn thành:** console và report có đủ 3 trạng thái; corrupted giảm chất lượng; repaired được tái tạo từ raw và phục hồi theo số liệu thực tế.

## Quy trình bàn giao giữa các bước

1. Người 2 bàn giao raw records và clean DataFrame cho Người 4/3/1.
2. Người 4 chỉ chạy Quality Gate sau khi schema của Người 2 ổn định.
3. Người 3 chỉ build baseline index sau khi clean data pass Quality Gate.
4. Người 4 chỉ đánh giá baseline sau khi test set và QA index sẵn sàng.
5. Người 1 chỉ merge pipeline khi từng bước có tín hiệu hoàn thành tương ứng.
6. Sau mỗi bước, chạy `git diff`, ghi kết quả vào báo cáo cá nhân và commit phần việc của mình.

## Checklist cuối bài

- [ ] Hai lệnh `run_phase1.py` và `run_corruption_flow.py` exit code 0.
- [ ] Đủ raw, clean, ChromaDB, eval, quality, result và report artifacts.
- [ ] `phase1_report.md` và `corruption_report.md` dùng số liệu sinh từ pipeline.
- [ ] `docs/TEAM.md`, `report/group_report.md` và 4 báo cáo cá nhân đã hoàn thiện.
- [ ] Không có `.env`, API key, token hoặc absolute path trong Git.
- [ ] Cả 4 thành viên xuất hiện trong GitHub Insights → Contributors trên `main`.
- [ ] Cả 4 thành viên đã nộp link repository trên VLearn LMS.

## Bonus sau khi đạt 100 điểm bắt buộc

- B1 Dashboard/Drift monitor: Người 4 phụ trách, Người 1 tích hợp.
- B2 Auto-repair: Người 2 xây logic, Người 1 đưa vào pipeline.
- B3 Pytest/CI coverage >80%: Người 2 test ingestion, Người 3 test retrieval, Người 4 test quality/metrics, Người 1 tích hợp CI.
