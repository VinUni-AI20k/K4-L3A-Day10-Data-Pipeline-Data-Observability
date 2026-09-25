from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    if len(df) < 4:
        raise ValueError(f"Need at least 4 documents, got {len(df)}")

    output_path = Path(output_path)
    if output_path.exists():
        import json
        return json.loads(output_path.read_text(encoding="utf-8"))

    # Pick 5 representative papers (spread across the dataframe)
    step = max(1, len(df) // 5)
    picks = [df.iloc[i * step] for i in range(5)]

    items: list[dict[str, Any]] = []

    # 3 summary questions
    for i, row in enumerate(picks[:3]):
        items.append({
            "id": f"q{i+1:02d}",
            "question_type": "summary",
            "question": f"What is '{row['title']}' about?",
            "ground_truth": first_sentence(row["summary"]),
            "ground_truth_doc_ids": [row["paper_id"]],
        })

    # 3 author questions
    for i, row in enumerate(picks[:3]):
        items.append({
            "id": f"q{i+4:02d}",
            "question_type": "authors",
            "question": f"Who authored '{row['title']}'?",
            "ground_truth": row["authors_joined"],
            "ground_truth_doc_ids": [row["paper_id"]],
        })

    # 2 date questions
    for i, row in enumerate(picks[3:5]):
        items.append({
            "id": f"q{i+7:02d}",
            "question_type": "date",
            "question": f"When was '{row['title']}' published?",
            "ground_truth": row["published"],
            "ground_truth_doc_ids": [row["paper_id"]],
        })

    # 2 category questions
    for i, row in enumerate(picks[3:5]):
        items.append({
            "id": f"q{i+9:02d}",
            "question_type": "categories",
            "question": f"What categories does '{row['title']}' belong to?",
            "ground_truth": row["categories_joined"],
            "ground_truth_doc_ids": [row["paper_id"]],
        })

    write_json(output_path, items)
    return items
