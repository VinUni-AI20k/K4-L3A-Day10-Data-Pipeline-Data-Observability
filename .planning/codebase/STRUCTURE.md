---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
# Codebase Structure

**Analysis Date:** 2026-09-25

## Directory Layout

```
.
├── .agents/                 # GSD core workflows, templates, and runtime skills
├── .env.example             # Template for API keys and model configurations
├── .gitignore               # Git ignored patterns (.venv, .env, __pycache__, etc.)
├── pyproject.toml           # Project metadata, dependencies, build settings
├── requirements.txt         # Flat pip dependency list
├── uv.lock                  # UV package lockfile
├── README.md                # Main lab overview, architecture, and instructions
├── data/                    # Data artifacts storage directory
│   ├── chroma/              # Persistent ChromaDB vector databases
│   ├── clean/               # Cleaned tabular datasets (CSV/JSON)
│   ├── embeddings/          # Embedding manifests and metadata
│   ├── eval/                # Test sets for RAG benchmark
│   ├── quality/             # Great Expectations & freshness reports
│   ├── raw/                 # Immutable raw API responses and snapshots
│   ├── reports/             # Generated Markdown reports (Phase 1, Corruption)
│   └── results/             # Evaluation metrics and answer logs
├── docs/                    # Official lab documentation and rubrics
│   ├── CHECKPOINTS.md       # Milestones and checkpoints CP0 - CP6
│   ├── Guide.md             # Step-by-step technical guide
│   ├── RUBRIC.md            # Grading rubric (100 standard + 10 bonus)
│   ├── RULES.md             # Lab rules and academic integrity
│   ├── SUBMISSION.md        # Submission instructions and checklist
│   └── TEAM.md              # Team members and role assignments
├── report/                  # Student report templates
│   ├── group_report.md      # Group report submission template
│   ├── individual_report_sample.md # Individual contribution report template
│   └── README.md            # Guidelines for reporting
├── script/                  # CLI execution scripts
│   ├── run_phase1.py        # Baseline pipeline runner (CP3)
│   └── run_corruption_flow.py # Corruption, repair, and comparison runner (CP4-CP5)
└── src/                     # Core application source code
    ├── core/                # Configuration, paths, and shared utilities
    ├── evaluation/          # Evaluation testset generation and metrics scoring
    ├── ingestion/           # Crossref fetching, cleaning, and corruption simulation
    ├── observability/       # Great Expectations 1.x quality checks and reporting
    ├── pipelines/           # Phase 1 and corruption flow orchestration
    └── retrieval/           # Sentence transformers, ChromaDB index, LLM and QA agent
```

## Directory Purposes

**`src/core/`:**

- Purpose: Foundational settings, paths, environment configuration, and text/IO utilities
- Key files: `src/core/config.py`, `src/core/utils.py`

**`src/ingestion/`:**

- Purpose: External API integration, raw payload parsing, data cleaning, and data corruption modeling
- Key files: `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`

**`src/observability/`:**

- Purpose: Data quality gates (Great Expectations 1.x), Freshness SLA monitoring, and Markdown report generators
- Key files: `src/observability/quality.py`, `src/observability/reporting.py`

**`src/retrieval/`:**

- Purpose: Dense vector embedding generation, ChromaDB vector indexing/searching, LLM provider integration, and QA agent
- Key files: `src/retrieval/embeddings.py`, `src/retrieval/index.py`, `src/retrieval/llm.py`, `src/retrieval/qa.py`, `src/retrieval/agent.py`

**`src/evaluation/`:**

- Purpose: Question test set generation and retrieval/answer evaluation metrics (Hit Rate, Token F1, LLM Judge)
- Key files: `src/evaluation/testset.py`, `src/evaluation/metrics.py`

**`src/pipelines/`:**

- Purpose: Pipeline controllers coordinating end-to-end execution
- Key files: `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`

**`script/`:**

- Purpose: User-facing CLI entry points
- Key files: `script/run_phase1.py`, `script/run_corruption_flow.py`

**`data/`:**

- Purpose: Persistent state and data lineage artifacts across baseline, corrupted, and repaired states
- Contains:
  - `data/raw/`: `crossref_response.json`, `crossref_records.json`
  - `data/clean/`: `papers_clean.csv`, `papers_clean.json`, `papers_clean_corrupted.*`, `papers_clean_repaired.*`
  - `data/chroma/`: ChromaDB persistent SQLite & vector files
  - `data/eval/`: `test_set.json`
  - `data/quality/`: `baseline_quality_report.json`, `corrupted_quality_report.json`, `freshness_report.json`
  - `data/results/`: `baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_log.json`
  - `data/reports/`: `phase1_report.md`, `corruption_report.md`

## Key File Locations

**Entry Points:**

- `script/run_phase1.py`: Baseline End-to-End pipeline (Phase 1)
- `script/run_corruption_flow.py`: Controlled corruption, repair, and 3-state comparison (Phase 2)

**Configuration:**

- `src/core/config.py`: `Paths` and `Settings` dataclasses, environment variable resolution
- `.env.example`: Template for API keys and provider endpoints

**Core Logic:**

- Ingestion: `src/ingestion/crossref.py` (`fetch_source_records`, `parse_crossref_payload`, `load_raw_records`)
- Cleaning: `src/ingestion/cleaning.py` (`build_clean_dataframe`)
- Quality Gate: `src/observability/quality.py` (`run_data_quality_checks`, `build_freshness_report`)
- Vector Store: `src/retrieval/index.py` (`LocalEmbeddingIndex.build`, `search`, `lookup`)
- Benchmarking: `src/evaluation/testset.py` (`build_test_set`), `src/evaluation/metrics.py` (`evaluate_pipeline`)

**Testing:**

- Unit & integration test files belong in `tests/` directory (e.g., `tests/test_ingestion.py`, `tests/test_quality.py`)

## Naming Conventions

**Files:**

- Snake_case for Python modules: `crossref.py`, `run_phase1.py`, `corruption_flow.py`
- UPPERCASE for documentation/rubric files: `README.md`, `CHECKPOINTS.md`, `RUBRIC.md`, `RULES.md`, `SUBMISSION.md`, `TEAM.md`
- Lowercase/snake_case for artifacts: `papers_clean.csv`, `baseline_metrics.json`

**Directories:**

- Flat lowercase directory names: `data`, `docs`, `script`, `src`, `tests`, `report`

**Classes:**

- PascalCase for data classes and models: `PaperRecord`, `Paths`, `Settings`, `LocalEmbeddingIndex`, `JudgeVerdict`

**Functions:**

- Snake_case with descriptive verbs: `build_clean_dataframe`, `run_data_quality_checks`, `corrupt_clean_dataframe`

## Where to Add New Code

**New Ingestion Source or Format:**

- Implementation: `src/ingestion/` (e.g., `arxiv.py` or `pubmed.py`)
- Dataclass updates: `PaperRecord` in `src/ingestion/crossref.py`

**New Quality Check / Expectation:**

- Implementation: `src/observability/quality.py` within `run_data_quality_checks`

**New Metrics or Evaluation Method:**

- Implementation: `src/evaluation/metrics.py` (e.g., adding MRR, NDCG, or custom Ragas scorers)

**New Pipeline or Orchestration Mode:**

- Implementation: `src/pipelines/` (e.g., `src/pipelines/auto_repair.py`)
- Entry point: `script/` (e.g., `script/run_auto_repair.py`)

**Unit & Integration Tests:**

- Test files: `tests/test_*.py` using `pytest`

**Utilities & Helpers:**

- Shared file/string operations: `src/core/utils.py`

## Special Directories

**`data/chroma/`:**

- Purpose: SQLite database and vector storage created by ChromaDB
- Generated: Yes
- Committed: No (in `.gitignore`)

**`data/clean/`, `data/results/`, `data/reports/`, `data/quality/`:**

- Purpose: Generated pipeline artifacts and verification evidence
- Generated: Yes
- Committed: Evidence files tracked as required by assignment submission

**`.venv/`:**

- Purpose: Isolated Python virtual environment
- Generated: Yes
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-09-25*
