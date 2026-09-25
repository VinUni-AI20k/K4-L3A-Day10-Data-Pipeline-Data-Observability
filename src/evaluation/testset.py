from __future__ import annotations

from typing import Any

import pandas as pd
from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """TODO(student): tao bo evaluation set tu cleaned dataframe.

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
    required = {"paper_id", "title", "summary", "authors_joined", "categories_joined", "published"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing benchmark columns: {sorted(missing)}")
    if len(df) < 10 or df.paper_id.duplicated().any():
        raise ValueError("Benchmark requires at least 10 unique papers.")
    # Sort by the stable document key so rebuilding the benchmark is idempotent.
    # Keep the same frozen file for baseline, corrupted and repaired evaluations.
    papers = df.sort_values("paper_id", kind="mergesort").head(10).copy()
    kinds = ["summary"] * 3 + ["authors"] * 3 + ["date"] * 2 + ["categories"] * 2
    questions = {
        "summary": "What is the summary of the paper '{title}'?",
        # qa.py dispatches on these exact phrases; changing them makes the
        # question fall through to the summary extractor.
        "authors": "Who authored '{title}'?",
        "date": "When was '{title}' published?",
        "categories": "What categories does '{title}' belong to?",
    }
    records = []
    for i, (kind, (_, paper)) in enumerate(zip(kinds, papers.iterrows()), 1):
        truth = {"summary": first_sentence(str(paper.summary)), "authors": str(paper.authors_joined),
                 "date": str(paper.published), "categories": str(paper.categories_joined)}
        records.append({"id": f"eval_{i:03d}", "question_type": kind,
                        "question": questions[kind].format(title=paper.title),
                        "ground_truth": truth[kind], "ground_truth_doc_ids": [paper.paper_id]})
    write_json(output_path, records)
    return records
