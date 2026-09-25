---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
# Technology Stack

**Analysis Date:** 2026-09-25

## Languages

**Primary:**

- Python (>=3.11, <3.14) - Core pipelines, ingestion, retrieval, data quality, and evaluation (`pyproject.toml`, `requirements.txt`, `src/`)

**Secondary:**

- Markdown - Lab documentation, operational guides, rubrics, and generated markdown reports (`docs/*.md`, `data/reports/*.md`)
- JSON - Configuration, metadata, test sets, evaluation logs, raw snapshots (`data/**/*.json`)

## Runtime

**Environment:**

- Python 3.11+ virtual environment (`.venv`)

**Package Manager:**

- `uv` (recommended in `README.md`, `uv.lock` present) / `pip`
- Lockfile: present (`uv.lock` ~720KB)

## Frameworks

**Core:**

- LangChain (`langchain>=1.0.0`) - Multi-provider LLM orchestration and tool-calling agent framework (`src/retrieval/agent.py`, `src/retrieval/llm.py`)
- ChromaDB (`chromadb>=1.0.12`) - Persistent local vector database using HNSW cosine index (`src/retrieval/index.py`)
- Great Expectations (`great-expectations>=1.16.1`) - Data observability, schema validation, and Data Quality Gate GX 1.x ephemeral context (`src/observability/quality.py`)
- Sentence-Transformers (`sentence-transformers>=5.0.0`) - Dense vector embeddings using `sentence-transformers/all-MiniLM-L6-v2` (`src/retrieval/embeddings.py`)
- Pandas (`pandas>=2.2.2`) - Tabular transformation, data cleaning, corruption injection, and dataset serialization (`src/ingestion/cleaning.py`, `src/ingestion/corruption.py`)
- Datasets (`datasets>=4.0.0`) - Dataset structures for evaluation (`src/evaluation/metrics.py`)
- Ragas (`ragas>=0.3.0`) - Optional RAG metrics pass (`src/evaluation/metrics.py`)

**Testing:**

- Pytest (`pytest>=8.3.2` declared in `[project.optional-dependencies] dev` in `pyproject.toml`)
- Pydantic (`pydantic.BaseModel`) - Structured validation for LLM judge evaluation verdicts (`src/evaluation/metrics.py`)

**Build/Dev:**

- Setuptools (`setuptools>=80.0.0`) - Configured build backend in `pyproject.toml`
- Python-dotenv (`python-dotenv>=1.0.1`) - Environment variable management from `.env` (`src/core/config.py`)
- Requests (`requests>=2.32.3`) - HTTP client for Crossref REST API calls (`src/ingestion/crossref.py`)

## Key Dependencies

**Critical:**

- `chromadb` (>=1.0.12) - Vector store persistency across baseline (`papers-baseline`), corrupted (`papers-corrupted`), and repaired (`papers-repaired`) collections (`src/retrieval/index.py`)
- `great-expectations` (>=1.16.1) - Ingestion quality gate enforcement ensuring dirty data does not corrupt vector indices (`src/observability/quality.py`)
- `sentence-transformers` (>=5.0.0) - Local normalized dense vector embeddings model `all-MiniLM-L6-v2` (`src/retrieval/embeddings.py`)
- `langchain` (>=1.0.0) & provider bindings (`langchain-google-genai`, `langchain-openai`, `langchain-anthropic`, `langchain-ollama`) - Multi-provider LLM interface (`src/retrieval/llm.py`)

**Infrastructure:**

- `requests` (>=2.32.3) - Academic API querying with retry logic (`src/ingestion/crossref.py`)
- `pandas` (>=2.2.2) - In-memory DataFrame operations and CSV/JSON serialization (`src/ingestion/cleaning.py`)

## Configuration

**Environment:**

- Configured via `.env` loaded with `python-dotenv` (`src/core/config.py`)
- Template provided in `.env.example`
- Key configs required:
  - `LLM_PROVIDER`: default `gemini`, supports `gemini`, `openai`, `anthropic`, `openrouter`, `ollama`, `custom`, `mock`
  - `LLM_MODEL`: default `gemini-2.5-flash`
  - `GOOGLE_API_KEY`: API key for Gemini models
  - Optional provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `CUSTOM_LLM_API_KEY`
  - Optional URLs: `OPENROUTER_BASE_URL`, `OLLAMA_BASE_URL`, `CUSTOM_LLM_BASE_URL`
  - Pipeline control flags: `REFRESH_SOURCE` (bool), `REFRESH_TEST_SET` (bool), `RUN_RAGAS` (bool)

**Build:**

- `pyproject.toml` - Defines dependencies, python compatibility (`>=3.11,<3.14`), setuptools build backend, package discovery in `src`
- `requirements.txt` - Flat pip dependency list mirror

## Platform Requirements

**Development:**

- Python 3.11, 3.12, or 3.13 on Windows (PowerShell), macOS, or Linux
- Virtual environment (`.venv`) initialized via `uv sync` or `pip install -e .`
- Network access for live Crossref API & LLM calls (or offline snapshot mode via `data/raw/crossref_response.json`)

**Production:**

- MLOps data pipeline runner (batch CLI scripts `script/run_phase1.py` and `script/run_corruption_flow.py`)
- Local disk storage for persistent ChromaDB vectors (`data/chroma/`) and reports (`data/reports/`)

---

*Stack analysis: 2026-09-25*
