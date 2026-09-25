# Báo cáo cá nhân — Mai Phan Anh Tùng

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Mai Phan Anh Tùng |
| MSSV | 2A202602980 |
| Lớp/Nhóm | K4-L3A / Invisible |
| Vai trò | Retrieval, Embedding & QA |
| Repository | https://github.com/MinMinhMin/K4-L3-DAY10-Invisible-DataPipeline |

## 2. Vai trò và phạm vi

| Phần việc | File chính | Output | Trạng thái |
| --- | --- | --- | --- |
| Embedding adapter | `retrieval/embeddings.py` | Normalized MiniLM vectors | Hoàn thành |
| Chroma index | `retrieval/index.py` | Ba persistent collections/manifests | Hoàn thành |
| Retrieval QA | `retrieval/qa.py` | Answer và retrieved DOI/contexts | Hoàn thành |

Tôi hỗ trợ evaluation xác minh Hit Rate và ingestion thống nhất metadata contract.

## 3. Kết quả theo vai trò

- Model ưu tiên local cache, fallback tải mạng khi cần.
- Chroma dùng cosine space và rebuild sạch collection cùng tên.
- Physical ID `paper_id::row_index` cho phép quan sát duplicate nhưng vẫn giữ DOI trong metadata.
- QA kết hợp exact-title lookup với semantic top-k.

Artifact chính: ba manifests trong `data/embeddings/` và ChromaDB trong `data/chroma/`.

## 4. Giải thích kỹ thuật

MiniLM encode document/query và chuẩn hóa vector. Index lưu content cùng title, authors, categories, summary, dates và DOI. Mỗi lần build xóa collection cũ để không rò vector giữa các trạng thái. QA ưu tiên paper có title khớp chính xác, sau đó bổ sung semantic results và deduplicate DOI.

| Contract | Nội dung |
| --- | --- |
| Input | Clean DataFrame và query string |
| Output | Chroma collection, manifest, SearchResult/AnswerResult |
| Lỗi xử lý | Model cache/mạng, thiếu clean JSON, missing collection, empty search |

```powershell
python -c "from core.config import load_settings; from retrieval.index import LocalEmbeddingIndex; s=load_settings(); i=LocalEmbeddingIndex(s,'papers-baseline'); print(len(i.semantic_search('machine learning',top_k=2)))"
```

Kết quả: trả 2 tài liệu; baseline retrieval hit đạt 100%.

## 5. Quyết định kỹ thuật

Tôi tách business key (DOI) khỏi physical Chroma ID. Nếu dùng DOI trực tiếp, duplicate corruption sẽ bị Chroma từ chối hoặc bị deduplicate âm thầm. ID có row index giữ nguyên lỗi trong index, còn metadata DOI vẫn phục vụ evaluation.

## 6. Blocker đã xử lý

- **Lỗi:** `TypeError: LocalEmbeddingIndex.__init__() missing 'documents' and 'persist_path'`.
- **Nguyên nhân:** Constructor yêu cầu chi tiết nội bộ, không khớp command của lab.
- **Xử lý:** Thêm default từ settings, `build_from_clean()` và `semantic_search()`.
- **Xác minh:** Command build/search chạy được và trả đúng `top_k=2`.

## 7. Hiểu biết end-to-end

Clean text được MiniLM encode và nạp Chroma cùng DOI metadata. Evaluation dùng một test set để so DOI top-k và chấm answer. GX kiểm tra chất lượng DataFrame; freshness kiểm tra tuổi dữ liệu. Repair rebuild collection mới từ raw-derived clean data, nhờ đó không giữ vector corrupted và metrics có thể quay lại baseline.

## 8. Phân tích kết quả

| Signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Hit Rate | 100% | 70% | 100% |
| Token F1 | 0,9055 | 0,6775 | 0,9055 |
| Judge accuracy | 90% | 70% | 90% |
| Judge score | 4,4 | 3,4 | 4,4 |
| Quality | PASS 6/6 | FAIL 4/6 | PASS 6/6 |
| Stale ratio | 4,17% | 47,62% | 4,17% |

Drop/title/noise làm index mất hoặc méo representation, khiến Hit Rate giảm 30 điểm %. Re-embed corpus repaired vào collection mới khôi phục toàn bộ metrics. Noise không làm Chroma crash, minh họa silent failure thay vì operational failure.

## 9. Điều học được

1. Business identity và storage identity nên tách riêng.
2. Rebuild collection tránh leakage giữa các lần thử.
3. Vector store có thể hoạt động bình thường dù content quality đã giảm.

Hướng cải thiện: đo embedding drift/centroid shift cho từng corruption và đối chiếu với Hit Rate.

## 10. Cam kết

Thành viên tự đánh dấu sau khi đọc:

- [ ] Nội dung phản ánh đúng phần việc của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end.
- [ ] Kết luận có artifact/metric đối chiếu.
- [ ] Báo cáo không chứa secret.

**Họ và tên:** Mai Phan Anh Tùng  
**Ngày xác nhận:** Chờ thành viên xác nhận
