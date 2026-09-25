---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
<!-- refreshed: 2026-09-25 -->

# Architecture

**Analysis Date:** 2026-09-25

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                      Pipelines Layer                        │
│          `src/pipelines/phase1.py`                          │
│          `src/pipelines/corruption_flow.py`                 │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌─────────────────────────────┐
│       Ingestion Layer        │ │     Observability Layer     │
│  - `crossref.py` (fetch/parse) │  - `quality.py` (GX 1.x)    │
│  - `cleaning.py` (normalize) │ │  - `reporting.py` (Markdown)│
│  - `corruption.py` (inject)  │ │                             │
└──────────────┬───────────────┘ └─────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌─────────────────────────────┐
│       Retrieval Layer        │ │      Evaluation Layer       │
│  - `embeddings.py` (MiniLM)  │ │  - `testset.py` (generator) │
│  - `index.py` (ChromaDB)     │ │  - `metrics.py` (Hit/F1/LLM)│
│  - `qa.py` / `agent.py`      │ │                             │
└──────────────┬───────────────┘ └─────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                        Core Layer                           │
│          `src/core/config.py` - Paths & Settings            │
│          `src/core/utils.py`  - IO & Text Normalization     │
└─────────────────────────────────────────────────────────────┘
```

## Architecture Pattern

**Modular Data Pipeline & Observability Pattern:**
The system is organized into modular functional layers with unidirectional data flow. Each component has well-defined boundaries:

- Ingestion converts raw external academic payloads into typed records (`PaperRecord`).
- Data Cleaning transforms raw records into tabular representation with pre-computed embedding strings.
- Data Observability verifies data integrity through Great Expectations 1.x gates and Freshness SLA checks before vectorization.
- Retrieval embeds text and indexes records into ChromaDB vector collections.
- Evaluation assesses retrieval precision, lexical Token F1, and LLM judge quality.
- Pipelines orchestrate end-to-end execution, corruption injection, and idempotent recovery.

## Component Layers

### 1. Orchestration & Scripts

- Location: `script/run_phase1.py`, `script/run_corruption_flow.py`
- Role: Minimal entry point runners providing CLI invocation for students and grading evaluation.

### 2. Pipelines

- Location: `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`
- Role: High-level workflow orchestration coordinating ingestion, validation, vector store building, evaluation, and reporting.

### 3. Ingestion

- Location: `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`
- Role:
  - `crossref.py`: Dual-mode acquisition (Live Crossref REST API vs. local offline snapshot `crossref_response.json`), payload parsing, and raw preservation.
  - `cleaning.py`: XML/HTML tag stripping, whitespace normalization, `age_days` computation, deduplication by `paper_id`, and `text_for_embedding` synthesis.
  - `corruption.py`: Controlled synthetic corruption suite (dropping latest papers, blanking summaries, inserting noise, truncating titles, modifying dates, injecting duplicate rows).

### 4. Observability

- Location: `src/observability/quality.py`, `src/observability/reporting.py`
- Role:
  - `quality.py`: Ephemeral Great Expectations 1.x suite execution (row counts, non-null constraints, unique identifiers, summary length checks) and Freshness SLA monitoring (`age_days > 180`).
  - `reporting.py`: Markdown artifact generation (`phase1_report.md`, `corruption_report.md`).

### 5. Retrieval & Agent

- Location: `src/retrieval/embeddings.py`, `src/retrieval/index.py`, `src/retrieval/llm.py`, `src/retrieval/qa.py`, `src/retrieval/agent.py`
- Role:
  - `embeddings.py`: SentenceTransformer wrapper `MiniLMEmbeddings` for normalized dense vector generation (`all-MiniLM-L6-v2`).
  - `index.py`: `LocalEmbeddingIndex` managing ChromaDB persistent client, cosine distance HNSW collections, search, and exact title/ID lookup.
  - `llm.py`: Multi-provider LLM factory (`gemini`, `openai`, `anthropic`, `openrouter`, `ollama`, `custom`, `mock`).
  - `qa.py`: Deterministic question answering extraction from retrieved context.
  - `agent.py`: Tool-augmented LangChain agent equipped with semantic search and exact lookup tools.

### 6. Evaluation

- Location: `src/evaluation/testset.py`, `src/evaluation/metrics.py`
- Role:
  - `testset.py`: Systematic test question generation across 4 categories (`summary`, `authors`, `date`, `categories`).
  - `metrics.py`: Calculation of Retrieval Hit Rate, Token F1, LLM Judge Score (with heuristic fallback), and optional Ragas pass.

### 7. Core

- Location: `src/core/config.py`, `src/core/utils.py`
- Role: Centralized path management (`Paths`), configuration settings (`Settings`), file I/O helpers, and text cleaning utilities.

## Data Flow

### Baseline Flow (Phase 1)

```text
Crossref API / Snapshot
   │
   ▼
data/raw/crossref_response.json ──► parse_crossref_payload() ──► data/raw/crossref_records.json
                                                                       │
                                                                       ▼
                                                             build_clean_dataframe()
                                                                       │
                                                                       ▼
                                                             data/clean/papers_clean.csv
                                                                       │
                                 ┌─────────────────────────────────────┴────────────────────────────────────┐
                                 ▼                                                                          ▼
                     run_data_quality_checks()                                              LocalEmbeddingIndex.build()
                     build_freshness_report()                                                               │
                                 │                                                                          ▼
                                 ▼                                                              data/chroma/ (papers-baseline)
                     data/quality/*.json                                                                    │
                                 │                                                                          ▼
                                 │                                                                evaluate_pipeline()
                                 │                                                                          │
                                 ▼                                                                          ▼
                                 └───────────────────────────────┬──────────────────────────────────────────┘
                                                                 ▼
                                                    data/reports/phase1_report.md
```

### Corruption & Idempotent Repair Flow (Phase 2)

```text
data/clean/papers_clean.csv
   │
   ▼
corrupt_clean_dataframe() ──► data/clean/papers_clean_corrupted.csv & data/results/corruption_log.json
   │
   ▼
LocalEmbeddingIndex.build() (papers-corrupted) ──► evaluate_pipeline() ──► corrupted_metrics.json (Silent Failure demo)
   │
   ▼
run_data_quality_checks() ──► Alert triggered (GX Quality Gate fails, Freshness alarm)
   │
   ▼
IDEMPOTENT REPAIR: load_raw_records(data/raw/crossref_records.json) ──► build_clean_dataframe()
   │
   ▼
LocalEmbeddingIndex.build() (papers-repaired) ──► evaluate_pipeline() ──► repaired_metrics.json (100% Recovery)
   │
   ▼
generate_corruption_report() ──► data/reports/corruption_report.md (3-State Comparison)
```

## Key Abstractions

**`Settings` & `Paths`:**

- Purpose: Central configuration and typed filesystem locator
- Location: `src/core/config.py`
- Pattern: Frozen dataclass initialized from `.env` and defaults

**`PaperRecord`:**

- Purpose: Standardized internal representation of an academic paper
- Location: `src/ingestion/crossref.py`
- Pattern: Frozen dataclass with metadata fields

**`LocalEmbeddingIndex`:**

- Purpose: Vector storage abstraction over ChromaDB
- Location: `src/retrieval/index.py`
- Pattern: Factory pattern with `.build()` and `.load()`, providing `.search()` and `.lookup()`

**`JudgeVerdict`:**

- Purpose: Structured output schema for LLM evaluation
- Location: `src/evaluation/metrics.py`
- Pattern: Pydantic `BaseModel` with score, correctness boolean, and rationale

## Entry Points

**Baseline Pipeline Runner:**

- Location: `script/run_phase1.py`
- Triggers: CLI execution (`python script/run_phase1.py`)
- Responsibilities: Runs Phase 1 end-to-end (ingest -> clean -> quality check -> index -> evaluate -> report).

**Corruption Flow Runner:**

- Location: `script/run_corruption_flow.py`
- Triggers: CLI execution (`python script/run_corruption_flow.py`)
- Responsibilities: Runs Phase 2 (corrupt -> evaluate degraded -> repair from raw -> evaluate recovered -> generate 3-way comparison report).

## Architectural Constraints

- **Dual-Mode Guarantee:** If live API access fails or offline flag is set, pipeline must gracefully fall back to `data/raw/crossref_response.json` without failing.
- **Great Expectations 1.x Standard:** Must use `gx.get_context(mode="ephemeral")` and Fluent Datasources/BatchDefinitions; legacy v0.18 syntax is strictly prohibited.
- **Pure Relative Paths:** Paths must resolve relative to project root (`src/core/config.py`); no hardcoded absolute machine paths.
- **Idempotency:** Re-running pipelines or repair routines must yield identical, clean artifacts without state corruption.

## Anti-Patterns & Pitfalls

### Silent Failure (The Core Problem Solved by this Architecture)

**What happens:** Corrupted or stale data is indexed directly into the vector database. The LLM produces plausible-sounding hallucinations without runtime errors.
**Why it's wrong:** Users receive false information while engineering dashboards show healthy HTTP 200s.
**Do this instead:** Validate through Great Expectations 1.x and Freshness SLA gates (`src/observability/quality.py`) before building vector indices.

### Modifying Raw Preserved Data

**What happens:** Ingestion or repair code edits `data/raw/crossref_records.json` in place.
**Why it's wrong:** Destroys data lineage and eliminates the recovery baseline.
**Do this instead:** Treat `data/raw/` as append-only or immutable ground truth; write all transformations to `data/clean/`.

## Error Handling

**Strategy:** Defensive validation at boundaries with graceful fallbacks.
**Patterns:**

- HTTP status retry for transient 429/503 errors when contacting Crossref API; fallback to local snapshot.
- Structured LLM evaluation fallback in `_judge_answer` (`src/evaluation/metrics.py`): if LLM API call fails or key is missing, falls back to lexical Token F1 heuristic rather than crashing the evaluation.
- ChromaDB collection recreate: delete and recreate collection on rebuild to avoid stale vector pollution.

## Cross-Cutting Concerns

**Logging & Artifact Output:** Structured JSON manifests and Markdown summaries saved to `data/` subdirectories.
**Validation:** Schema conformity and range verification using Great Expectations 1.x.
**Authentication:** Environment variable isolation via `.env` and `python-dotenv`.

---

*Architecture analysis: 2026-09-25*
