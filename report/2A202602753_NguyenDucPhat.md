# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                             |
| ------------------ | ------------------------------------ |
| Họ và tên       | Nguyễn Đức Phát                     |
| MSSV               | 2A202602753                          |
| Khóa/Lớp         | K4-L3-DAY10                         |
| Tên nhóm         | GOHOME                               |
| Vai trò chính    | RAG & Vector Index Specialist        |
| Repository         | https://github.com/Nam-phuong624/K4-L3A-Day10-Data-Pipeline-Data-Observability        |
| Ngày hoàn thành | 2026-09-25                           |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable     | File/hàm phụ trách                      | Input nhận vào             | Output bàn giao                         | Trạng thái |
| ---------------------- | ----------------------------------------- | -------------------------- | --------------------------------------- | ---------- |
| Embedding model        | `src/retrieval/embeddings.py`            | list of texts              | numpy array of vectors                  | Hoàn thành |
| ChromaDB index         | `src/retrieval/index.py`                 | clean DataFrame, settings  | `LocalEmbeddingIndex`, embeddings JSON  | Hoàn thành |
| QA answer extraction   | `src/retrieval/qa.py`                    | question, retrieved docs   | `AnswerResult` (answer + source)        | Hoàn thành |
| LLM provider           | `src/retrieval/llm.py`                   | `.env` `LLM_PROVIDER`      | LLM callable                           | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                    | Thành viên/module được hỗ trợ | Kết quả                                      |
| ------------------------------ | ------------------------------------ | -------------------------------------------- |
| Fix eager import agent       | `src/retrieval/__init__.py`          | Remove `from .agent import` → tránh internet call lúc import |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                       | File/hàm/artifact liên quan           | Kết quả bàn giao                        | Cách xác minh                       |
| -------------------------------------------- | --------------------------------------- | ---------------------------------------- | ----------------------------------- |
| Encode 24 papers bằng MiniLM               | `embeddings.py:MiniLMEmbeddings`       | `data/embeddings/papers_embeddings.json` | File tồn tại sau run phase1        |
| Build 3 ChromaDB collections riêng biệt    | `index.py:LocalEmbeddingIndex.build`  | `data/chroma/` (3 subfolders)           | `ls data/chroma/`                   |
| Truy vấn semantic top-k và trả lời câu hỏi | `qa.py:answer_question`               | `data/results/baseline_answers.json`    | `python script/run_phase1.py` step [6/7] |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Biến dữ liệu text thành không gian vector để tìm kiếm semantic, đồng thời cô lập 3 trạng thái dữ liệu (baseline/corrupted/repaired) vào 3 collection ChromaDB riêng biệt để đảm bảo không có contamination khi so sánh.

### Cách triển khai

**Embeddings (`MiniLMEmbeddings`):**
- Model `sentence-transformers/all-MiniLM-L6-v2` — 384 dimensions, CPU-friendly.
- Encode `text_for_embedding` field (Title + Authors + Published + Categories + Summary) thay vì chỉ encode title/summary → richer semantic representation.

**ChromaDB index (`LocalEmbeddingIndex`):**
- Mỗi lần `build()` tạo một collection mới với tên riêng (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
- `paper_id` là document ID trong ChromaDB → cho phép exact match khi đánh giá retrieval hit.
- `search()` trả về top-k `SearchResult` với `paper_id`, `score`, `text`.

**QA extraction (`answer_question`):**
- `_extract_answer()` dùng pattern matching trên câu hỏi để xác định loại (summary/authors/date/categories) và trích xuất từ metadata — không cần LLM cho closed-domain.
- LLM (mock/real) chỉ được dùng làm judge — cho điểm câu trả lời từ 1-5.

### Input, output và contract

| Thành phần           | Mô tả                                                      |
| -------------------- | ---------------------------------------------------------- |
| Input                | `text_for_embedding` từ clean DataFrame                   |
| Output               | ChromaDB collection + `SearchResult(paper_id, score, text)` |
| Module phụ thuộc    | `cleaning.py` (tạo text), `core/config.py` (paths)       |
| Module sử dụng output | `evaluation/metrics.py` (đo hit_rate), `qa.py` (trả lời) |
| Điều kiện lỗi       | Collection đã tồn tại → delete và rebuild (idempotent)    |

### Cách xác minh

```bash
conda run -n vin python script/run_phase1.py
# Bước [4/7]: "Indexed 24 documents"
# Bước [6/7]: "hit_rate=1.0000  token_f1=1.0000"
```

- **Kết quả mong đợi:** 24 documents indexed, hit_rate=1.0 trên baseline.
- **Kết quả thực tế:** Đạt đúng như mong đợi.
- **Artifact/log:** `data/chroma/`, `data/embeddings/papers_embeddings.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `src/retrieval/__init__.py` ban đầu import eagerly `from .agent import build_agent` → khi import module, LangChain agent cố gắng pull prompt từ `hub.langchain.com` → gây lỗi mạng.
- **Các phương án:** (1) Giữ nguyên, accept internet dependency. (2) Xóa eager import, chỉ import khi cần.
- **Phương án đã chọn:** Xóa `from .agent import` khỏi `__init__.py`.
- **Lý do:** Pipeline không cần agent ở Phase 1 và Phase 2 — chỉ cần `qa.py` cho extraction. Agent là optional feature.
- **Bằng chứng:** Pipeline chạy offline hoàn toàn với `LLM_PROVIDER=mock`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `ImportError: cannot import name 'create_agent' from 'langchain.agents'`.
- **Nguyên nhân gốc:** LangChain đổi tên API — `create_agent` không tồn tại, đúng tên là `create_react_agent`.
- **Cách xử lý:** Cập nhật `src/retrieval/agent.py`: `from langchain.agents import create_react_agent`, dùng prompt từ `hub.pull("hwchase17/react")`.
- **Cách xác minh:** Import thành công mà không raise ImportError.
- **Điều học được:** LangChain thay đổi API thường xuyên — luôn kiểm tra tên exact trong version đang dùng, không dựa vào memory từ tutorial cũ.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** Phần thú vị nhất là ở bước encode. `text_for_embedding` gộp Title + Authors + Published + Categories + Summary thành một chuỗi — MiniLM "đọc" chuỗi này và nén lại thành 384 con số đại diện cho ý nghĩa của bài báo đó. Hai bài cùng chủ đề sẽ có vector gần nhau trong không gian 384 chiều đó. ChromaDB lưu các vector lại và tìm kiếm bằng cosine similarity.
2. **Evaluation:** Khi hỏi một câu, MiniLM cũng encode câu hỏi đó thành vector. ChromaDB tìm k vectors "gần nhất" với vector câu hỏi. Hit = paper chứa câu trả lời có nằm trong top-k đó không. Bản chất là đo xem vector của câu hỏi và vector của bài báo đúng có đủ gần nhau không.
3. **Quality vs Freshness:** GX kiểm tra data về mặt cấu trúc — `blank_summary` hay `truncate_title` ảnh hưởng trực tiếp đến chất lượng vector (ít thông tin = vector yếu). Freshness thì khác — data về cấu trúc vẫn hoàn toàn đúng nhưng ngữ cảnh thời gian đã lỗi thời, GX không detect được.
4. **Cùng test set:** Trong ML, muốn so sánh hai model thì phải dùng cùng benchmark — ở đây cũng vậy. "Index corrupted" vs "Index baseline" là hai model khác nhau, test set phải giống nhau để phép so sánh có nghĩa.
5. **Repair thành công:** Rebuild index từ data sạch → `hit_rate` phục hồi về 1.0 chứng minh vấn đề nằm ở data, không phải ở model embedding hay ChromaDB. Đây là điều quan trọng nhất bài lab muốn chứng minh.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét                                          |
| ---------------------- | -------: | --------: | -------: | ------------------------------------------------- |
| `retrieval_hit_rate`  |   1.0000 |    0.8000 |   1.0000 | Blank+truncate làm vector "mờ" → câu hỏi không match được bài đúng |
| `mean_token_f1`       |   1.0000 |    0.5882 |   1.0000 | Summary rỗng = vector không encode đủ ngữ nghĩa → extraction fail  |
| `judge_accuracy`      |   1.0000 |    0.6000 |   1.0000 | 4 câu sai do vector retrieval miss hoặc context bị noise          |
| `mean_judge_score`    |        5 |    3.2000 |        5 | Score phản ánh mức độ "lạc hướng" của answer so với ground-truth   |
| Quality checks         |     Pass |      Fail |     Pass | GX detect structural corruption, không phải vector corruption      |
| Freshness status       |     True |     False |     True | Stale date không làm vector xấu hơn, nhưng data không còn đáng tin |

### Kết luận từ số liệu

1. `blank_summary` (3 rows) + `truncate_title` (3 rows) → `text_for_embedding` kém chất lượng → embedding không capture đủ semantic → `retrieval_hit_rate` giảm 0.2, `mean_token_f1` giảm 0.41.
2. Rebuild ChromaDB từ repaired DataFrame (đủ data, đúng format) → vectors chất lượng cao → retrieval phục hồi hoàn toàn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Vector quality = data quality:** Embedding chỉ tốt khi text đầu vào tốt — `blank_summary` làm mất 50% thông tin trong `text_for_embedding`.
2. **Isolation by collection:** 3 collections riêng biệt là thiết kế đúng — không bao giờ mix state trong cùng collection, không thể rollback nếu shared.
3. **CPU-only torch đủ cho inference:** `all-MiniLM-L6-v2` inference với batch nhỏ (24 papers) không cần GPU — CPU-only torch giảm size download từ 2.8GB xuống 250MB.

### Nếu có thêm thời gian

Thêm cosine similarity threshold cho `search()` — hiện tại chỉ dựa vào top-k, không filter theo quality of match. Nếu score < 0.3 thì không nên return làm context cho LLM.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đức Phát
**Ngày xác nhận:** 2026-09-25
