from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


class BenchmarkTestSet(list):
    """Wrapper class representing the benchmark evaluation test set."""

    def __init__(self, samples: list[dict[str, Any]]) -> None:
        super().__init__(samples)
        self.samples = samples

    def to_dict(self) -> list[dict[str, Any]]:
        return self.samples


def _find_row(df: pd.DataFrame, title_substring: str, fallback_idx: int) -> pd.Series:
    mask = df["title"].astype(str).str.contains(title_substring, case=False, na=False)
    if mask.any():
        matches = df[mask]
        exact = matches[matches["title"].astype(str).str.startswith(title_substring)]
        if not exact.empty:
            return exact.iloc[0]
        return matches.iloc[0]
    return df.iloc[fallback_idx % len(df)]


def build_test_set(
    df: pd.DataFrame,
    output_path: str | Path | None = None,
    num_samples: int | None = None,
) -> BenchmarkTestSet:
    """Build a benchmark test set containing 10 questions across 5 core evaluation question types:
    1. summary (2 câu): Tóm tắt nội dung nghiên cứu chính.
    2. authors (2 câu): Ai là tác giả của nghiên cứu về chủ đề X?
    3. date (2 câu): Nghiên cứu Y được công bố vào năm/tháng nào?
    4. category (2 câu): Công trình này thuộc lĩnh vực chuyên môn nào?
    5. multi_hop (2 câu): Câu hỏi kết hợp liên ngành giữa hai chủ đề.
    """
    if df.empty:
        raise ValueError("DataFrame cannot be empty when creating benchmark test set.")

    r1 = _find_row(df, "Continuous Benchmark Evaluation", 0)
    r2 = _find_row(df, "Multi-Agent Consensus", 1)
    r3 = _find_row(df, "Freshness SLAs", 2)
    r4 = _find_row(df, "Automated Data Quality Profiling", 3)
    r5a = _find_row(df, "Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks", 4)
    r5b = _find_row(df, "Data Observability and Quality Gates for Production RAG Systems", 5)

    r6 = _find_row(df, "Data Observability and Quality Gates for Production RAG Systems", 5)
    r7 = _find_row(df, "Hybrid Search Architectures", 6)
    r8 = _find_row(df, "Chunking Strategies for Technical Documentation Retrieval", 8)
    r9 = _find_row(df, "Mitigating Ghost Vectors in Dense Retrieval via Idempotent Indexing", 15)
    r10a = _find_row(df, "Continuous Benchmark Evaluation for Enterprise Retrieval Pipelines", 0)
    r10b = _find_row(df, "Automated Data Quality Profiling with Great Expectations in CI/CD", 10)

    samples: list[dict[str, Any]] = [
        {
            "id": "eval_001",
            "type": "summary",
            "question_type": "summary",
            "question": f"Tóm tắt nội dung nghiên cứu chính của bài báo '{r1['title']}'?",
            "ground_truth": first_sentence(str(r1["summary"])),
            "ground_truth_doc_ids": [str(r1["paper_id"])],
        },
        {
            "id": "eval_002",
            "type": "authors",
            "question_type": "authors",
            "question": f"Ai là tác giả của nghiên cứu về chủ đề '{r2['title']}'?",
            "ground_truth": str(r2.get("authors_joined") or "; ".join(r2.get("authors", []))),
            "ground_truth_doc_ids": [str(r2["paper_id"])],
        },
        {
            "id": "eval_003",
            "type": "date",
            "question_type": "date",
            "question": f"Nghiên cứu '{r3['title']}' được công bố vào năm/tháng nào?",
            "ground_truth": str(r3.get("published") or r3.get("published_date", "")).split("T")[0],
            "ground_truth_doc_ids": [str(r3["paper_id"])],
        },
        {
            "id": "eval_004",
            "type": "category",
            "question_type": "category",
            "question": f"Công trình '{r4['title']}' thuộc lĩnh vực chuyên môn nào?",
            "ground_truth": str(r4.get("categories_joined") or "; ".join(r4.get("categories", []))),
            "ground_truth_doc_ids": [str(r4["paper_id"])],
        },
        {
            "id": "eval_005",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": (
                f"Câu hỏi kết hợp liên ngành giữa hai chủ đề: '{r5a['title']}' và '{r5b['title']}' "
                "đề cập đến giải pháp gì?"
            ),
            "ground_truth": (
                "Kết hợp cơ chế định tuyến suy luận agentic multi-hop reasoning với các cổng kiểm soát "
                "chất lượng dữ liệu tự động Great Expectations 1.x để ngăn ngừa silent data corruption trong hệ thống RAG."
            ),
            "ground_truth_doc_ids": [str(r5a["paper_id"]), str(r5b["paper_id"])],
        },
        {
            "id": "eval_006",
            "type": "summary",
            "question_type": "summary",
            "question": f"Tóm tắt nội dung chính của nghiên cứu '{r6['title']}'?",
            "ground_truth": first_sentence(str(r6["summary"])),
            "ground_truth_doc_ids": [str(r6["paper_id"])],
        },
        {
            "id": "eval_007",
            "type": "authors",
            "question_type": "authors",
            "question": f"Ai là tác giả của công trình '{r7['title']}'?",
            "ground_truth": str(r7.get("authors_joined") or "; ".join(r7.get("authors", []))),
            "ground_truth_doc_ids": [str(r7["paper_id"])],
        },
        {
            "id": "eval_008",
            "type": "date",
            "question_type": "date",
            "question": f"Thời điểm xuất bản của bài báo '{r8['title']}' là ngày nào?",
            "ground_truth": str(r8.get("published") or r8.get("published_date", "")).split("T")[0],
            "ground_truth_doc_ids": [str(r8["paper_id"])],
        },
        {
            "id": "eval_009",
            "type": "category",
            "question_type": "category",
            "question": f"Bài báo '{r9['title']}' được phân loại vào những lĩnh vực nào?",
            "ground_truth": str(r9.get("categories_joined") or "; ".join(r9.get("categories", []))),
            "ground_truth_doc_ids": [str(r9["paper_id"])],
        },
        {
            "id": "eval_010",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": (
                f"Sự phối hợp giữa '{r10a['title']}' và '{r10b['title']}' "
                "mang lại lợi ích gì cho việc quản trị dữ liệu retrieval?"
            ),
            "ground_truth": (
                "Thiết lập bộ test benchmark tự động kết hợp với profiling kiểm soát chất lượng dữ liệu "
                "trong CI/CD để phát hiện sớm schema drift trước khi đưa vào embedding pipeline."
            ),
            "ground_truth_doc_ids": [str(r10a["paper_id"]), str(r10b["paper_id"])],
        },
    ]

    if num_samples is not None and num_samples > 0:
        samples = samples[:num_samples]

    test_set = BenchmarkTestSet(samples)

    if output_path is not None:
        target_path = Path(output_path)
        write_json(target_path, samples)

    return test_set


def load_or_create_test_set(
    df: pd.DataFrame,
    output_path: str | Path | None = None,
    refresh: bool = False,
    num_samples: int | None = None,
) -> BenchmarkTestSet:
    """Load existing benchmark test set or create a new one from cleaned data."""
    if output_path is not None:
        target_path = Path(output_path)
        if target_path.exists() and not refresh:
            try:
                data = read_json(target_path)
                if isinstance(data, list) and len(data) > 0:
                    if num_samples is None or len(data) == num_samples:
                        return BenchmarkTestSet(data)
                if isinstance(data, dict) and "samples" in data and len(data["samples"]) > 0:
                    if num_samples is None or len(data["samples"]) == num_samples:
                        return BenchmarkTestSet(data["samples"])
            except Exception:
                pass

    return build_test_set(df, output_path=output_path, num_samples=num_samples)
