from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


QUESTION_TYPES = ["summary", "authors", "date", "categories"]


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return normalize_whitespace(str(value or ""))


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a deterministic 10-question benchmark from the cleaned papers."""
    required = {"paper_id", "title", "summary", "authors_joined", "categories_joined", "published"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Cannot build test set. Missing columns: {missing}")
    usable = df.dropna(subset=["paper_id", "title", "summary"]).copy()
    usable = usable[usable["summary"].astype(str).str.strip().str.len() >= 30]
    if len(usable) < 10:
        raise ValueError("Need at least 10 usable papers to build the evaluation set.")

    usable = usable.sort_values(["published", "paper_id"], ascending=[False, True]).head(10).reset_index(drop=True)
    test_set: list[dict[str, Any]] = []

    for idx, row in usable.iterrows():
        qtype = QUESTION_TYPES[idx % len(QUESTION_TYPES)]
        title = _as_text(row["title"])
        paper_id = _as_text(row["paper_id"])
        if qtype == "summary":
            question = f"What is the main summary of the paper '{title}'?"
            ground_truth = first_sentence(_as_text(row["summary"]))
        elif qtype == "authors":
            question = f"Who are the authors of the paper '{title}'?"
            ground_truth = _as_text(row["authors_joined"])
        elif qtype == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = _as_text(row["published"])
        else:
            question = f"What categories are assigned to the paper '{title}'?"
            ground_truth = _as_text(row["categories_joined"])

        test_set.append(
            {
                "id": f"eval_{idx + 1:03d}",
                "question_type": qtype,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(output_path, test_set)
    return test_set
