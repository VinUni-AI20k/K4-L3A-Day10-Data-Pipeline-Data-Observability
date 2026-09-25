---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
# Coding Conventions

**Analysis Date:** 2026-09-25

## Naming Patterns

**Files:**

- Snake_case for Python source and script files: `crossref.py`, `corruption_flow.py`, `run_phase1.py`
- Markdown files in `docs/` and root use UPPERCASE: `README.md`, `CHECKPOINTS.md`, `RUBRIC.md`
- Data output artifacts use descriptive snake_case: `papers_clean.csv`, `baseline_metrics.json`, `corruption_log.json`

**Functions:**

- Snake_case with descriptive action verbs: `build_clean_dataframe`, `run_data_quality_checks`, `corrupt_clean_dataframe`, `evaluate_pipeline`
- Internal/private helper functions use leading underscore: `_token_f1`, `_judge_answer`, `_extract_answer`, `_derive_collection_name`, `_load_model`

**Variables:**

- Snake_case for local variables and parameters: `project_dir`, `raw_records`, `clean_df`, `query_embedding`
- Constants and environment variables in UPPER_SNAKE_CASE: `LLM_PROVIDER`, `GOOGLE_API_KEY`, `REFRESH_SOURCE`

**Types & Classes:**

- PascalCase for all classes, dataclasses, and Pydantic models: `PaperRecord`, `Paths`, `Settings`, `LocalEmbeddingIndex`, `JudgeVerdict`, `EvaluationBundle`

## Code Style

**Header Directive:**

- Every Python file MUST begin with:
  ```python
  from __future__ import annotations
  ```

**Type Annotations:**

- Modern Python 3.10+ union and container syntax: `str | None` (never `Optional[str]`), `list[str]`, `dict[str, Any]`
- Dataclasses should prefer immutability using `@dataclass(frozen=True)` for domain models and config:
  ```python
  @dataclass(frozen=True)
  class PaperRecord:
      paper_id: str
      title: str
  ```

**Formatting:**

- PEP 8 standard formatting (4 spaces indentation, no tabs)
- Maximum line length generally kept under 120 characters

## Import Organization

**Order:**

1. Future imports (`from __future__ import annotations`)
2. Python Standard Library (`dataclasses`, `datetime`, `pathlib`, `re`, `json`, `os`, `sys`, `typing`)
3. Third-party packages (`pandas`, `chromadb`, `great_expectations`, `sentence_transformers`, `langchain`, `pydantic`, `datasets`, `dotenv`)
4. Local package imports (import directly by module name: `from core.config import Settings`, `from retrieval.index import LocalEmbeddingIndex`)

**Path Resolution:**

- Packages inside `src/` are on `PYTHONPATH` via `pyproject.toml` (`package-dir = {"" = "src"}`).
- Local imports use absolute module imports from `src/` (e.g., `from core.config import ...`, `from ingestion.crossref import ...`).

## Error Handling

**Patterns:**

- Explicit domain exceptions: Raise `RuntimeError` with clear, actionable error messages when required configuration or API keys are missing:
  ```python
  if provider == "gemini" and not settings.google_api_key:
      raise RuntimeError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini.")
  ```
- Graceful degradation / Heuristic fallbacks: When external services or LLM APIs fail, provide deterministic fallback logic rather than crashing the entire pipeline:
  ```python
  try:
      llm = build_llm(settings=settings, temperature=0.0).with_structured_output(JudgeVerdict)
      return llm.invoke(prompt)
  except Exception:
      score = 5 if _token_f1(reference, prediction) >= 0.95 else 3 if _token_f1(reference, prediction) >= 0.5 else 1
      return JudgeVerdict(score=score, correct=score >= 3, reasoning="Fallback heuristic judge used.")
  ```
- Defensive collection deletion: When re-indexing ChromaDB, catch and suppress collection deletion exceptions if the collection does not yet exist.

## Logging & Output

**Framework:**

- Structured file logging via JSON and Markdown outputs in `data/results/`, `data/quality/`, and `data/reports/`
- User-facing status messages printed to console with clear stage headers and status counts (e.g., `Tín hiệu hoàn thành: Clean thành công 24 dòng`).

## Comments & Documentation

**Docstrings:**

- Concise module and function docstrings stating intent, parameters, and pseudo-code algorithm steps
- Preserve existing docstrings and `TODO(student)` guidance when implementing functionality

## Function Design

**Single Responsibility:**

- Ingestion modules fetch and parse; cleaning modules normalize; quality modules validate; retrieval modules search.
- Use pure or idempotent functions where feasible: given the same input records, `build_clean_dataframe` always returns an identical DataFrame.

## File & Path Operations

**Pathlib Exclusivity:**

- Always pass `pathlib.Path` objects. Never concatenate path strings with `/` or `+`.
- Use helper functions from `src/core/utils.py`:
  - `ensure_parent(path: Path)`: automatically creates parent directories
  - `write_json(path, payload)`, `read_json(path)`
  - `write_csv(df, path)`
  - `write_text(path, text)`

---

*Convention analysis: 2026-09-25*
