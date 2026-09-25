from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: Path | str) -> list[dict[str, Any]]:
    """Build evaluation test set covering summary, authors, date, categories."""
    if len(df) < 5:
        raise ValueError(f"Need at least 5 documents to build test set, found {len(df)}.")

    target_count = min(10, len(df))
    subset = df.head(target_count).copy()

    question_types = ["summary", "authors", "date", "categories"]
    test_set: list[dict[str, Any]] = []

    for index, (_, row) in enumerate(subset.iterrows()):
        q_type = question_types[index % len(question_types)]
        title = row["title"]
        paper_id = row["paper_id"]

        if q_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif q_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = str(row["authors_joined"])
        elif q_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = str(row["published"])
        elif q_type == "categories":
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = str(row["categories_joined"])
        else:
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))

        test_set.append(
            {
                "id": f"eval_{index + 1:03d}",
                "question_type": q_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    out_file = Path(output_path)
    write_json(out_file, test_set)
    return test_set
