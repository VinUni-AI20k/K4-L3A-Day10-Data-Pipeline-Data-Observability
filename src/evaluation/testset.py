from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a deterministic 10-question benchmark set from the cleaned corpus."""
    if len(df) < 10:
        raise ValueError("At least 10 cleaned papers are required to build the evaluation set.")

    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "published",
        "categories_joined",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing)}")

    selected = df.sort_values(["published", "paper_id"], ascending=[False, True]).head(10).to_dict(orient="records")
    question_types = [
        "summary",
        "authors",
        "date",
        "categories",
        "summary",
        "authors",
        "date",
        "categories",
        "summary",
        "authors",
    ]
    test_set = [_build_item(index + 1, question_type, row) for index, (question_type, row) in enumerate(zip(question_types, selected, strict=True))]
    write_json(output_path, test_set)
    return test_set


def _build_item(index: int, question_type: str, row: dict[str, Any]) -> dict[str, Any]:
    title = row["title"]
    if question_type == "summary":
        question = f"What is the summary of the paper '{title}'?"
        ground_truth = first_sentence(row["summary"])
    elif question_type == "authors":
        question = f"Who authored the paper '{title}'?"
        ground_truth = row["authors_joined"]
    elif question_type == "date":
        question = f"When was the paper '{title}' published?"
        ground_truth = row["published"]
    elif question_type == "categories":
        question = f"What categories are assigned to the paper '{title}'?"
        ground_truth = row["categories_joined"]
    else:
        raise ValueError(f"Unsupported question type: {question_type}")

    return {
        "id": f"eval_{index:03d}",
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": [row["paper_id"]],
    }
