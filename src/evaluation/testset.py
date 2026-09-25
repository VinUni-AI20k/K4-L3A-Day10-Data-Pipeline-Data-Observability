from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


def build_test_set(df: pd.DataFrame, output_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Build standardized 5-question benchmark evaluation set from cleaned dataframe."""
    if len(df) < 5:
        raise ValueError(f"Clean dataframe requires at least 5 documents, got {len(df)}")

    # 1. Summary question: Tóm tắt nội dung nghiên cứu chính
    summary_match = df[df["title"].str.contains("Data Observability", case=False, na=False)]
    p_sum = summary_match.iloc[0] if not summary_match.empty else df.iloc[0]

    # 2. Authors question: Ai là tác giả của nghiên cứu về chủ đề X?
    authors_match = df[df["title"].str.contains("Fact Verification|Multi-Agent", case=False, na=False)]
    p_auth = authors_match.iloc[0] if not authors_match.empty else df.iloc[1]

    # 3. Date question: Nghiên cứu Y được công bố vào năm/tháng nào?
    date_match = df[df["title"].str.contains("Freshness", case=False, na=False)]
    p_date = date_match.iloc[0] if not date_match.empty else df.iloc[2]

    # 4. Category question: Công trình này thuộc lĩnh vực chuyên môn nào?
    cat_match = df[df["title"].str.contains("Continuous Benchmark", case=False, na=False)]
    p_cat = cat_match.iloc[0] if not cat_match.empty else df.iloc[3]

    # 5. Multi-hop question: Câu hỏi kết hợp liên ngành giữa hai chủ đề
    multi_match = df[df["title"].str.contains("Synthetic Corruption", case=False, na=False)]
    p_multi = multi_match.iloc[0] if not multi_match.empty else df.iloc[4]

    test_set: list[dict[str, Any]] = [
        {
            "id": "test-001",
            "type": "summary",
            "question_type": "summary",
            "question": f"What is the summary of the paper '{p_sum['title']}'?",
            "ground_truth": first_sentence(p_sum["summary"]),
            "ground_truth_doc_ids": [str(p_sum["paper_id"])],
        },
        {
            "id": "test-002",
            "type": "authors",
            "question_type": "authors",
            "question": f"Who authored the research on topic '{p_auth['title']}'?",
            "ground_truth": str(p_auth["authors_joined"]),
            "ground_truth_doc_ids": [str(p_auth["paper_id"])],
        },
        {
            "id": "test-003",
            "type": "date",
            "question_type": "date",
            "question": f"When was the research '{p_date['title']}' published on?",
            "ground_truth": str(p_date["published"]),
            "ground_truth_doc_ids": [str(p_date["paper_id"])],
        },
        {
            "id": "test-004",
            "type": "category",
            "question_type": "category",
            "question": f"What categories does the work '{p_cat['title']}' belong to?",
            "ground_truth": str(p_cat["categories_joined"]),
            "ground_truth_doc_ids": [str(p_cat["paper_id"])],
        },
        {
            "id": "test-005",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": f"How does synthetic corruption testing stress-test vector search robustness in '{p_multi['title']}' for production RAG observability?",
            "ground_truth": first_sentence(p_multi["summary"]),
            "ground_truth_doc_ids": [str(p_multi["paper_id"]), str(p_sum["paper_id"])],
        },
    ]

    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, test_set)

    return test_set


def load_or_create_test_set(
    df: pd.DataFrame | None = None,
    output_path: Path | str | None = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Load existing benchmark test set or create a new one if missing."""
    target = Path(output_path) if output_path is not None else None
    if target is not None and target.exists() and not force_refresh:
        try:
            existing = read_json(target)
            if isinstance(existing, list) and len(existing) == 5:
                return existing
        except Exception:
            pass

    if df is None:
        raise ValueError("A clean DataFrame must be provided to create a test set.")
    return build_test_set(df, output_path=target)
