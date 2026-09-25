from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json

MIN_DOCUMENTS = 10
NUM_QUESTIONS = 10
QUESTION_TYPES = ["summary", "authors", "date", "category", "multi_hop"]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set tu cleaned dataframe.

    Pseudo-code:
    1. Kiem tra so luong document toi thieu.
    2. Chon mot so paper dai dien.
    3. Tao nhieu loai cau hoi:
       - summary
       - authors
       - date
       - categories
    4. Moi row can co:
       - id
       - question_type
       - question
       - ground_truth
       - ground_truth_doc_ids
    5. Ghi file JSON vao output_path.
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(f"Need at least {MIN_DOCUMENTS} documents to build a test set, got {len(df)}.")

    rows = df.sort_values("paper_id").to_dict(orient="records")
    # Chon cac paper dai dien rai deu trong corpus; moi cau hoi dung mot paper khac nhau.
    step = max(len(rows) // NUM_QUESTIONS, 1)
    picks = [rows[(i * step) % len(rows)] for i in range(NUM_QUESTIONS)]

    def published_of(row: dict[str, Any]) -> str:
        return pd.Timestamp(row["published"]).date().isoformat()

    def other_category(row: dict[str, Any]) -> dict[str, Any]:
        return next(
            (r for r in rows if r["primary_category"] != row["primary_category"]),
            next(r for r in rows if r["paper_id"] != row["paper_id"]),
        )

    def make(qtype: str, p: dict[str, Any]) -> tuple[str, str, str, list[str]]:
        title, doc_id = p["title"], p["paper_id"]
        if qtype == "summary":
            return qtype, f"What is the summary of the paper '{title}'?", first_sentence(p["summary"]), [doc_id]
        if qtype == "authors":
            return qtype, f"Who authored the paper '{title}'?", p["authors_joined"], [doc_id]
        if qtype == "date":
            return qtype, f"When was the paper '{title}' published?", published_of(p), [doc_id]
        if qtype == "category":
            return qtype, f"What categories does the paper '{title}' belong to?", p["categories_joined"], [doc_id]
        other = other_category(p)
        return (
            qtype,
            f"What categories do the papers '{title}' and '{other['title']}' belong to, respectively?",
            f"{p['categories_joined']}; {other['categories_joined']}",
            [doc_id, other["paper_id"]],
        )

    items = [make(QUESTION_TYPES[i % len(QUESTION_TYPES)], p) for i, p in enumerate(picks)]

    test_set = [
        {
            "id": f"eval_{i:03d}",
            "type": qtype,
            "question_type": qtype,
            "question": question,
            "ground_truth": truth,
            "ground_truth_doc_ids": doc_ids,
        }
        for i, (qtype, question, truth, doc_ids) in enumerate(items, start=1)
    ]
    write_json(output_path, test_set)
    return test_set


def load_or_create_test_set(
    df: pd.DataFrame, output_path: Path, refresh: bool = False
) -> list[dict[str, Any]]:
    """Doc test set da co; tao moi neu chua ton tai hoac `refresh=True`."""
    if not refresh and Path(output_path).exists():
        return read_json(Path(output_path))
    return build_test_set(df, output_path)
