from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


TEST_SET_VERSION = 2


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a deterministic ten-question benchmark from clean records."""
    required = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Cannot build test set; missing columns: {', '.join(missing)}")
    candidates = df.drop_duplicates(subset=["paper_id"]).reset_index(drop=True)
    if len(candidates) < 10:
        raise ValueError("At least 10 clean documents are required to build the benchmark.")

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
    samples: list[dict[str, Any]] = []
    for index, question_type in enumerate(question_types):
        # Two questions per paper keep all four business question types while
        # making the benchmark explicitly sensitive to loss of the newest 20%.
        row = candidates.iloc[index % 5]
        title = str(row["title"])
        if question_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif question_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = str(row["authors_joined"])
        elif question_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = str(row["published"])
        else:
            question = f"What categories are assigned to the paper '{title}'?"
            ground_truth = str(row["categories_joined"])
        samples.append(
            {
                "id": f"eval_{index + 1:03d}",
                "benchmark_version": TEST_SET_VERSION,
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [str(row["paper_id"])],
            }
        )
    write_json(output_path, samples)
    return samples


def load_or_create_test_set(
    df: pd.DataFrame,
    output_path,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Load the fixed benchmark when present, otherwise create it."""
    if not refresh and output_path.exists():
        payload = read_json(output_path)
        if (
            isinstance(payload, list)
            and len(payload) == 10
            and all(item.get("benchmark_version") == TEST_SET_VERSION for item in payload)
        ):
            return payload
    return build_test_set(df, output_path)
