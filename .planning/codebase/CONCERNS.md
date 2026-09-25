---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
# Codebase Concerns

**Analysis Date:** 2026-09-25

## Tech Debt

**Student Implementation Stubs:**

- Issue: 24 `TODO(student)` / `raise NotImplementedError` blocks currently present across core ingestion, cleaning, corruption, observability, evaluation, and pipeline modules.
- Files:
  - `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records`
  - `src/ingestion/cleaning.py`: `build_clean_dataframe`
  - `src/ingestion/corruption.py`: `corrupt_clean_dataframe`
  - `src/observability/quality.py`: `run_data_quality_checks`, `build_freshness_report`
  - `src/observability/reporting.py`: `generate_phase1_report`, `generate_corruption_report`
  - `src/evaluation/testset.py`: `build_test_set`
  - `src/pipelines/phase1.py`: `main`
  - `src/pipelines/corruption_flow.py`: `main`
- Impact: Running pipeline scripts immediately raises `NotImplementedError` until implemented.
- Fix approach: Implement modules sequentially following `docs/Guide.md` checkpoints CP1 through CP5.

## Fragile Areas

**Great Expectations 1.x API Compliance:**

- Files: `src/observability/quality.py`
- Why fragile: Great Expectations has undergone major API refactoring in version 1.x. Calling legacy v0.18 methods (such as `context.sources.pandas_default`) throws deprecated attribute errors or crashes.
- Safe modification: Strictly use the ephemeral Fluent Datasource API specified in `docs/Guide.md`:
  ```python
  context = gx.get_context(mode="ephemeral")
  data_source = context.data_sources.add_pandas(name="papers_source")
  data_asset = data_source.add_dataframe_asset(name="papers_asset")
  batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
  batch = batch_def.get_batch(batch_parameters={"dataframe": df})
  ```
- Test coverage: Verify with step 4 smoke test after implementation.

**Crossref Public REST API Instability:**

- Files: `src/ingestion/crossref.py`
- Why fragile: The public unauthenticated Crossref API frequently encounters HTTP 429 Too Many Requests and HTTP 503 during classroom network congestion.
- Safe modification: Implement exponential backoff retry and automatically fall back to the offline snapshot `data/raw/crossref_response.json` when the network is unreachable or returns 429/503.

**ChromaDB Collection Conflict on Rebuild:**

- Files: `src/retrieval/index.py`
- Why fragile: When switching between baseline, corrupted, and repaired states, existing collections in `data/chroma/` must be safely deleted and recreated without leaving residual locks or stale vectors.
- Safe modification: Keep the `client.delete_collection(...)` inside a `try...except` block as already implemented in `LocalEmbeddingIndex.build`.

## Security Considerations

**API Key Credential Exposure:**

- Risk: Committing `.env` or hardcoding API keys into code or generated markdown reports violates academic integrity (-20 points penalty in `docs/RUBRIC.md`).
- Files: `.env`, `.env.example`, `src/core/config.py`, `data/reports/*.md`
- Current mitigation: `.env` is listed in `.gitignore`.
- Recommendations: Ensure all logging and report generation strictly omits environment variables and API keys.

## Performance Bottlenecks

**Ragas Evaluation Overhead:**

- Problem: Running full Ragas pass (`RUN_RAGAS=1`) sequentially queries external LLMs for multiple metrics (`faithfulness`, `answer_relevancy`, etc.) across all 10 test samples, which can take 3-5 minutes and risk rate limits.
- Files: `src/evaluation/metrics.py`
- Cause: Synchronous serial LLM evaluation.
- Improvement path: Keep `RUN_RAGAS` disabled by default and rely on the lightweight, fast `_token_f1` and structured `JudgeVerdict` evaluator for standard runs.

## Scaling Limits

**Local Embedded Vector Store:**

- Current capacity: Tested for 24-100 paper records using in-memory HNSW cosine index.
- Limit: File-based SQLite and single-process Python limitations.
- Scaling path: For larger enterprise corpuses (>50,000 documents), migrate from embedded ChromaDB to client-server ChromaDB or Qdrant/Pinecone.

## Dependencies at Risk

**LangChain Community Dynamic VertexAI Shim:**

- Files: `src/evaluation/metrics.py` (lines 77-80)
- Risk: Workaround shim for `langchain_community.chat_models.vertexai` needed by older Ragas versions.
- Impact: Potential import side-effects if Ragas or LangChain versions change.
- Migration plan: Standardize on official LangChain Google GenAI provider (`langchain-google-genai`).

## Test Coverage Gaps

**Missing Automated Unit Tests:**

- What's not tested: No automated test files currently exist in the repository (`tests/` directory is empty).
- Files: All modules in `src/`
- Risk: Regressions in cleaning logic or schema changes can go unnoticed without manual script execution.
- Priority: High (and qualifies for +5 points bonus under criterion B3 in `docs/RUBRIC.md`).

---

*Concerns audit: 2026-09-25*
