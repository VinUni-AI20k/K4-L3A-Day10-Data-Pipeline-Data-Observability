# Phase 1 Report - Baseline Pipeline (Du Lieu Sach)

_Sinh tu dong luc 2026-09-25T09:33:39+00:00._

## 1. Nguon Du Lieu & Cau Hinh

| Hang muc | Gia tri |
| --- | --- |
| Nguon du lieu | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | from-pub-date:2026-03-29,has-abstract:true |
| So ban ghi raw | 24 |
| So dong sau cleaning | 24 |
| So dong bi loai khi cleaning | 0 |
| ChromaDB collection | papers-baseline |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| LLM provider | openai |
| LLM model | gemini-2.5-flash |
| Top-K retrieval | 4 |
| Kich thuoc test set | 10 |
| Thoi diem chay | 2026-09-25T09:33:39+00:00 |

## 2. Ket Qua Danh Gia RAG (Baseline)

| Chi so | Gia tri |
| --- | --- |
| So cau hoi danh gia | 10 |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 0.8000 |
| LLM Judge Accuracy | 0.8000 |
| Mean Judge Score (1-5) | 4.2000 |

### Ragas

| Metric | Gia tri |
| --- | --- |
| `skipped` | Set RUN_RAGAS=1 to enable the slower Ragas pass. |

## 3. Data Quality (Great Expectations 1.x)

**Trang thai tong the:** PASS

| Expectation | Ket qua | Chi tiet |
| --- | --- | --- |
| `row_count_between_5_and_5000` | PASS | observed=24 |
| `paper_id_not_null` | PASS | unexpected=0 |
| `title_not_null` | PASS | unexpected=0 |
| `text_for_embedding_not_null` | PASS | unexpected=0 |
| `paper_id_unique` | PASS | unexpected=0 |
| `summary_length_at_least_30` | PASS | unexpected=0 |
| `freshness_threshold_check` | PASS | stale_rows=0; total_rows=24; threshold_percent=0.2500 |

## 4. Freshness SLA

| Hang muc | Gia tri |
| --- | --- |
| Bai moi nhat | 2026-09-15 |
| Bai cu nhat | 2026-04-01 |
| So dong qua han | 0 |
| Tong so dong | 24 |
| Ty le qua han | 0.0000 |
| Nguong tuoi (ngay) | 180 |
| Dat Freshness SLA | PASS |

## 5. Nhan Xet

- Data quality gate: **PASS**
- Freshness SLA: **PASS** (0/24 dong qua 180 ngay).
- Baseline RAG: Hit Rate 1.0000, Token F1 0.8000 tren 10 cau hoi. Day la moc de doi chieu o Phase 2.
