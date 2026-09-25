---
last_mapped_commit: 77a0fdaca68e157737853e68b35c08bd49d79cfd
last_mapped_at: 2026-09-25
---
# External Integrations

**Analysis Date:** 2026-09-25

## APIs & External Services

**Scholarly Metadata:**

- Crossref REST API - Academic paper metadata querying (works search by query and date/abstract filters)
  - SDK/Client: `requests.Session` / `requests.get` in `src/ingestion/crossref.py`
  - Auth: None required (polite pool via headers optional, status code retry for 429/503)
  - Offline Fallback: `data/raw/crossref_response.json` (Dual-Mode architecture)

**LLM Model Providers:**

- Google Gemini - Default LLM judge and agent reasoning provider (`gemini-2.5-flash`)
  - SDK/Client: `langchain-google-genai` (`ChatGoogleGenerativeAI`) in `src/retrieval/llm.py`
  - Auth: `GOOGLE_API_KEY`
- OpenAI - Alternative LLM provider
  - SDK/Client: `langchain-openai` (`ChatOpenAI`) in `src/retrieval/llm.py`
  - Auth: `OPENAI_API_KEY`
- Anthropic Claude - Alternative LLM provider
  - SDK/Client: `langchain-anthropic` (`ChatAnthropic`) in `src/retrieval/llm.py`
  - Auth: `ANTHROPIC_API_KEY`
- OpenRouter - Multi-model API gateway
  - SDK/Client: `langchain-openai` (`ChatOpenAI` with custom `base_url`) in `src/retrieval/llm.py`
  - Auth: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`
- Ollama - Local offline LLM runner
  - SDK/Client: `langchain-ollama` (`ChatOllama`) in `src/retrieval/llm.py`
  - Auth: None, connects to `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- Custom / Mock - Testing and mock evaluation
  - SDK/Client: `FakeListChatModel` or custom endpoint in `src/retrieval/llm.py`
  - Auth: `CUSTOM_LLM_API_KEY`, `CUSTOM_LLM_BASE_URL`

## Data Storage

**Databases:**

- ChromaDB (Local Embedded Persistent Vector Store)
  - Connection: Local directory path `data/chroma/` configured in `src/core/config.py`
  - Client: `chromadb.PersistentClient` in `src/retrieval/index.py`
  - Collections:
    - `papers-baseline`: baseline clean vector index
    - `papers-corrupted`: corrupted experimental vector index
    - `papers-repaired`: repaired recovered vector index
  - Distance Metric: Cosine similarity via HNSW (`configuration={"hnsw": {"space": "cosine"}}`)

**File Storage:**

- Local filesystem only:
  - `data/raw/`: raw snapshot archives (`crossref_response.json`, `crossref_records.json`)
  - `data/clean/`: cleaned dataset exports (`papers_clean.csv`, `papers_clean.json`)
  - `data/embeddings/`: embedding index manifests (`papers_embeddings.json`)
  - `data/eval/`: benchmark question test set (`test_set.json`)
  - `data/quality/`: data quality reports (`baseline_quality_report.json`, `freshness_report.json`)
  - `data/results/`: metrics and answers (`baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_log.json`)
  - `data/reports/`: generated Markdown reports (`phase1_report.md`, `corruption_report.md`)

**Caching:**

- In-memory model cache: `@lru_cache(maxsize=4)` for `SentenceTransformer` instances in `src/retrieval/embeddings.py`

## Authentication & Identity

**Auth Provider:**

- Custom API key-based authentication via environment variables
  - Implementation: Loaded via `python-dotenv` in `src/core/config.py` (`load_settings`, `require_llm_credentials`)

## Monitoring & Observability

**Error Tracking:**

- Local execution logs and validation failures captured by Great Expectations `run_data_quality_checks` in `src/observability/quality.py`

**Logs:**

- File-based JSON logs:
  - Data corruption log: `data/results/corruption_log.json`
  - Quality check results: `data/quality/baseline_quality_report.json`, `data/quality/corrupted_quality_report.json`
  - Freshness check results: `data/quality/freshness_report.json`
  - Evaluation results: `data/results/baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`

## CI/CD & Deployment

**Hosting:**

- Local student machine / laboratory workstation

**CI Pipeline:**

- Script-based automation: `script/run_phase1.py` and `script/run_corruption_flow.py`
- Extensible to GitHub Actions CI (`pytest` automated test suite)

## Environment Configuration

**Required env vars:**

- `.env` file present (contains environment configuration, template in `.env.example`)
- `GOOGLE_API_KEY` (if using default Gemini provider) or equivalent provider API key

**Secrets location:**

- `.env` in project root or workspace parent root (git-ignored via `.gitignore`)

## Webhooks & Callbacks

**Incoming:**

- None

**Outgoing:**

- None (synchronous request-response to Crossref and LLM APIs)

---

*Integration audit: 2026-09-25*
