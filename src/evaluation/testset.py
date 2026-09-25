from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: Path | str) -> list[dict[str, Any]]:
    """Tao bo evaluation set 10 cau hoi tu cleaned dataframe."""
    if len(df) < 10:
        raise ValueError(f"Cleaned DataFrame needs at least 10 papers, found {len(df)}")

    records = df.to_dict(orient="records")
    test_set: list[dict[str, Any]] = []

    # 1. 3 cau hoi summary (papers 0, 1, 2)
    for i in range(3):
        row = records[i]
        test_set.append(
            {
                "id": f"eval_{len(test_set) + 1:03d}",
                "question_type": "summary",
                "question": f"What is the summary of the paper '{row['title']}'?",
                "ground_truth": first_sentence(row["summary"]),
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    # 2. 3 cau hoi authors (papers 3, 4, 5)
    for i in range(3, 6):
        row = records[i]
        test_set.append(
            {
                "id": f"eval_{len(test_set) + 1:03d}",
                "question_type": "authors",
                "question": f"Who authored the paper '{row['title']}'?",
                "ground_truth": row["authors_joined"],
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    # 3. 2 cau hoi date (papers 6, 7)
    for i in range(6, 8):
        row = records[i]
        test_set.append(
            {
                "id": f"eval_{len(test_set) + 1:03d}",
                "question_type": "date",
                "question": f"When was the paper '{row['title']}' published?",
                "ground_truth": row["published"],
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    # 4. 2 cau hoi categories (papers 8, 9)
    for i in range(8, 10):
        row = records[i]
        test_set.append(
            {
                "id": f"eval_{len(test_set) + 1:03d}",
                "question_type": "categories",
                "question": f"What categories does the paper '{row['title']}' belong to?",
                "ground_truth": row["categories_joined"],
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    target_path = Path(output_path)
    write_json(target_path, test_set)
    return test_set

