# Phase 1 Baseline Report

## Source

- **source_api:** Crossref REST API
- **source_query:** agentic retrieval augmented generation large language model
- **source_filter:** from-pub-date:2026-03-29,has-abstract:true
- **raw_mode:** loaded from crossref_records.json
- **raw_records:** 24
- **clean_rows:** 24
- **run_date:** 2026-09-25T09:28:57.672104+00:00
- **embedding_model:** sentence-transformers/all-MiniLM-L6-v2
- **collection_name:** papers-baseline
- **llm_provider:** gemini
- **llm_model:** gemini-2.5-flash

## Metrics

- **samples:** 10
- **retrieval_hit_rate:** 1.0
- **mean_token_f1:** 0.611838562815307
- **judge_accuracy:** 0.6
- **mean_judge_score:** 3.2
- **ragas:** {'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}

## Quality

- **Success:** True
- **Checks:** {'row_count_5_to_5000': True, 'paper_id_non_null': True, 'title_non_null': True, 'text_for_embedding_non_null': True, 'paper_id_unique': True, 'summary_min_30_chars': True}

## Freshness

- **Fresh:** True
- **Stale rows:** 0/24
