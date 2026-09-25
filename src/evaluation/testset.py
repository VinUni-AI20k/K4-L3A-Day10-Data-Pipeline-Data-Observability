from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

TARGET_QUESTIONS = 10
MIN_DOCUMENTS = 4

# Thu tu luan phien 4 dang cau hoi nghiep vu.
QUESTION_TYPES = ["summary", "authors", "date", "categories"]

# Cach dat cau phai khop voi bo nhan dang y dinh trong `retrieval/qa.py`:
#   "who authored" -> authors_joined, "when was" -> published, "what categories" -> categories_joined
# Tieu de luon nam trong dau nhay don de `answer_question` lookup chinh xac.
QUESTION_TEMPLATES = {
    "summary": "What is the summary of the paper '{title}'?",
    "authors": "Who authored the paper '{title}'?",
    "date": "When was the paper '{title}' published?",
    "categories": "What categories are assigned to the paper '{title}'?",
}


def _ground_truth(question_type: str, row: pd.Series) -> str:
    if question_type == "authors":
        return str(row["authors_joined"])
    if question_type == "date":
        return str(row["published"])
    if question_type == "categories":
        return str(row["categories_joined"])
    return first_sentence(str(row["summary"]))


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Sinh bo de thi chuan (ground truth) tu dataframe da lam sach.

    Bo de duoc sinh deterministic: cung mot dataframe luon cho ra cung mot
    bo cau hoi, de so sanh baseline / corrupted / repaired la cong bang.
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(
            f"Can it nhat {MIN_DOCUMENTS} tai lieu de sinh test set, hien chi co {len(df)}."
        )

    # Uu tien cac bai bao co tom tat day du de ground truth co y nghia.
    candidates = df[df["summary"].astype(str).str.len() >= 30]
    if len(candidates) < MIN_DOCUMENTS:
        candidates = df
    candidates = candidates.reset_index(drop=True)

    test_set: list[dict[str, Any]] = []
    for position in range(TARGET_QUESTIONS):
        row = candidates.iloc[position % len(candidates)]
        question_type = QUESTION_TYPES[position % len(QUESTION_TYPES)]
        ground_truth = _ground_truth(question_type, row)
        if not ground_truth:
            ground_truth = first_sentence(str(row["summary"]))

        test_set.append(
            {
                "id": f"eval_{position + 1:03d}",
                "question_type": question_type,
                "question": QUESTION_TEMPLATES[question_type].format(title=str(row["title"])),
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [str(row["paper_id"])],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set
