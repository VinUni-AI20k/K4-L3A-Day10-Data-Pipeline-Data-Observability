from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import write_json

QUESTION_TYPES = ("summary", "authors", "date", "categories")
MIN_DOCUMENTS = 5
TEST_SET_SIZE = 10


def _build_question(question_type: str, row: pd.Series) -> tuple[str, str]:
    title = row["title"]
    if question_type == "summary":
        return f"Bai bao '{title}' viet ve noi dung gi?", row["summary"]
    if question_type == "authors":
        return f"Ai la tac gia cua bai bao '{title}'?", row["authors_joined"]
    if question_type == "date":
        return f"Bai bao '{title}' duoc xuat ban khi nao?", str(row["published"])
    if question_type == "categories":
        return f"Bai bao '{title}' thuoc linh vuc / chuyen nganh nao?", row["categories_joined"]
    raise ValueError(f"Unknown question_type: {question_type}")


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Sinh bo 10 cau hoi benchmark, rai deu tren 4 loai: summary, authors, date, categories.

    Moi item: id, question_type, question, ground_truth, ground_truth_doc_ids.
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(f"Can toi thieu {MIN_DOCUMENTS} document de sinh test set, chi co {len(df)}.")

    sample_size = min(TEST_SET_SIZE, len(df))
    sample = df.sort_values("paper_id").reset_index(drop=True).head(sample_size)

    test_set: list[dict[str, Any]] = []
    for i, row in sample.iterrows():
        question_type = QUESTION_TYPES[i % len(QUESTION_TYPES)]
        question, ground_truth = _build_question(question_type, row)
        test_set.append(
            {
                "id": f"q{i + 1}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(output_path, test_set)
    return test_set
