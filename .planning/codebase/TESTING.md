---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
# Testing Patterns

**Analysis Date:** 2026-09-25

## Test Framework

**Runner:**

- `pytest` (>=8.3.2) specified in `pyproject.toml` under `[project.optional-dependencies] dev`
- Execution: via python virtual environment (`.venv`)

**Assertion Library:**

- Standard Python `assert` statements

**Run Commands:**

```bash
pytest                                       # Run all unit/integration tests
pytest -v -s                                 # Verbose test run with stdout output
pytest tests/test_ingestion.py               # Test specific module
pytest -k "quality"                          # Run tests matching pattern
```

## Smoke Test Commands (Guide.md Checkpoints)

Each checkpoint in `docs/Guide.md` defines an inline Python smoke test:

**Environment verification (Step 1):**

```bash
python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
```

**Ingestion verification (Step 2):**

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

**Cleaning verification (Step 3):**

```bash
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
```

**Quality gate verification (Step 4):**

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
```

**Test set builder verification (Step 5):**

```bash
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

**Full Baseline Pipeline (Step 6):**

```bash
python script/run_phase1.py
```

**Corruption Suite (Step 7):**

```bash
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```

**Corruption, Repair & Comparison Flow (Step 8):**

```bash
python script/run_corruption_flow.py
```

## Test File Organization

**Location:**

- Dedicated `tests/` directory at the project root:
  - `tests/test_ingestion.py`: tests Crossref parsing, raw preservation, and cleaning
  - `tests/test_quality.py`: tests Great Expectations 1.x suites and Freshness checks
  - `tests/test_retrieval.py`: tests ChromaDB indexing, embeddings, and QA lookup
  - `tests/test_pipelines.py`: tests end-to-end baseline and corruption flows

## Benchmark Evaluation Suite (`src/evaluation/`)

The repository includes a domain-specific evaluation system for RAG accuracy:

**Test Set Generation:**

- File: `src/evaluation/testset.py`
- Produces: 10 structured questions in `data/eval/test_set.json`
- Question categories:
  - `summary`: evaluates semantic content retrieval and summarization
  - `authors`: evaluates exact author extraction
  - `date`: evaluates publication date precision
  - `categories`: evaluates subject categorization

**Metrics Computed (`src/evaluation/metrics.py`):**

1. `retrieval_hit_rate`: Fraction of questions where the ground truth paper ID is in the top-k retrieved documents.
2. `mean_token_f1`: Harmonic mean of precision and recall over word tokens between model answer and reference.
3. `judge_accuracy`: Binary correctness assessed by LLM judge (or token F1 fallback heuristic).
4. `mean_judge_score`: 1-5 scale rating assessed by LLM judge.
5. `ragas` metrics (optional with `RUN_RAGAS=1`): `answer_relevancy`, `context_precision`, `context_recall`, `faithfulness`.

## Mocking & Offline Testing

**Mock LLM Provider:**

- Set `LLM_PROVIDER=mock` in `.env`
- Uses `FakeListChatModel` in `src/retrieval/llm.py` to test pipelines without external API costs or latency.

**Offline Ingestion:**

- Uses pre-captured snapshot at `data/raw/crossref_response.json` when internet connectivity is down or API returns HTTP 429/503.

---

*Testing analysis: 2026-09-25*
