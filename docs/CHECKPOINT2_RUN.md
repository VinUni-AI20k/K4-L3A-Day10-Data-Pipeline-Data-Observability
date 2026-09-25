# Chạy kiểm tra Checkpoint 2

Mã nguồn chính: `src/evaluation/testset.py` và `src/retrieval/index.py`.

Môi trường `.venv-cp2` đã được dùng để kiểm tra với ChromaDB 1.5.9 và sentence-transformers 6.1.0. Mô hình là `sentence-transformers/all-MiniLM-L6-v2`; lần đầu cần tải trọng số, các lần sau có thể dùng cache.

```bash
PYTHONPATH=src .venv-cp2/bin/python script/smoke_checkpoint2.py
PYTHONPATH=src .venv-cp2/bin/python -m unittest discover -s tests -p test_checkpoint2.py
```

Smoke test kiểm tra đúng 5 câu hỏi, số tài liệu index bằng số DOI duy nhất trong dữ liệu sạch, build lại không tăng số bản ghi, nạp lại collection và tìm kiếm ngữ nghĩa. Collection baseline được lưu tại `data/chroma/`; manifest tại `data/embeddings/papers_embeddings.json`.

`load_or_create_test_set` giữ nguyên file benchmark hợp lệ đã có, kể cả khi DataFrame đầu vào thay đổi. File sai schema hoặc không đúng 5 câu sẽ báo `ValueError`, không tự thay thế. Dùng `build_test_set` khi chủ động muốn tạo lại benchmark. Bản benchmark trước CP2 được giữ tại `data/eval/test_set_before_cp2.json`.

Mỗi mẫu có `type` và alias `question_type` để tương thích evaluator. Nếu thiếu subject, đáp án category ghi rõ nguồn không cung cấp thông tin; không tự suy ra chuyên ngành. Câu multi-hop yêu cầu đối chiếu nội dung của hai bài báo.

Metadata Chroma dùng chuỗi cho authors/categories và giữ các alias `authors_joined`, `categories_joined` phục vụ QA. ID chính là DOI. Build đồng bộ toàn bộ collection với dữ liệu đầu vào bằng upsert và xóa ID không còn trong snapshot; không xóa collection khác. Luồng nhiều batch không phải giao dịch nguyên tử, có thể chạy lại nếu bị gián đoạn.

API tham khảo: [Chroma query](https://docs.trychroma.com/docs/querying-collections/query-and-get), [SentenceTransformer encode](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).
