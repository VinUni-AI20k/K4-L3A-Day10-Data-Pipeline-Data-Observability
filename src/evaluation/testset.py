from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Tao bo evaluation set (10 cau hoi) tu cleaned dataframe.

    Bao gom 4 nhom cau hoi:
    - summary: 3 cau
    - authors: 3 cau
    - date: 2 cau
    - categories: 2 cau

    Moi row co format:
    - id
    - question_type
    - question
    - ground_truth
    - ground_truth_doc_ids
    """
    if len(df) < 10:
        raise ValueError("Cleaned dataframe must contain at least 10 records to build evaluation set.")

    test_set: list[dict[str, Any]] = []

    for i in range(10):
        row = df.iloc[i]
        paper_id = str(row["paper_id"])
        title = str(row["title"])

        if i < 3:
            q_type = "summary"
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif i < 6:
            q_type = "authors"
            question = f"Who authored the paper '{title}'?"
            ground_truth = str(row["authors_joined"])
        elif i < 8:
            q_type = "date"
            question = f"When was the paper '{title}' published?"
            ground_truth = str(row["published"])
        else:
            q_type = "categories"
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = str(row["categories_joined"])

        test_set.append({
            "id": f"eval_{i + 1:03d}",
            "question_type": q_type,
            "question": question,
            "ground_truth": ground_truth,
            "ground_truth_doc_ids": [paper_id],
        })

    if output_path is not None:
        write_json(Path(output_path), test_set)

    return test_set

