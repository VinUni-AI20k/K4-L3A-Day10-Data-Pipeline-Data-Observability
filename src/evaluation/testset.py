from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json

# 10 questions across the 4 question types (3 + 3 + 2 + 2).
QUESTION_PLAN = ["summary", "authors", "date", "categories", "summary", "authors", "date", "categories", "summary", "authors"]

# Phrasing must stay in sync with `retrieval.qa._extract_answer`, which routes on these keywords,
# and the title must be wrapped in single quotes so `answer_question` can do an exact title lookup.
QUESTION_TEMPLATES = {
    "summary": "What is the summary of the paper '{title}'?",
    "authors": "Who authored the paper '{title}'?",
    "date": "When was the paper '{title}' published?",
    "categories": "What categories does the paper '{title}' belong to?",
}


def _joined(row: pd.Series, joined_column: str, list_column: str) -> str:
    if joined_column in row and isinstance(row[joined_column], str) and row[joined_column].strip():
        return normalize_whitespace(row[joined_column])
    value = row.get(list_column)
    if isinstance(value, (list, tuple)):
        return ", ".join(normalize_whitespace(str(item)) for item in value if str(item).strip())
    return normalize_whitespace(str(value or ""))


def _published(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        # DataFrame.to_json stores datetimes as epoch milliseconds.
        return pd.to_datetime(value, unit="ms").date().isoformat()
    return pd.Timestamp(value).date().isoformat()


def _ground_truth(row: pd.Series, question_type: str) -> str:
    if question_type == "summary":
        return first_sentence(str(row["summary"]))
    if question_type == "authors":
        return _joined(row, "authors_joined", "authors")
    if question_type == "date":
        return _published(row["published"])
    return _joined(row, "categories_joined", "categories")


def _select_papers(df: pd.DataFrame, count: int) -> pd.DataFrame:
    candidates = df.dropna(subset=["paper_id", "title", "summary"])
    candidates = candidates[~candidates["title"].astype(str).str.contains("'")]
    candidates = candidates.drop_duplicates(subset="paper_id").sort_values("paper_id").reset_index(drop=True)
    if len(candidates) < count:
        raise ValueError(f"Need at least {count} valid documents to build the test set, got {len(candidates)}.")
    # Spread picks evenly across the corpus so each question targets a different paper.
    positions = [round(i * (len(candidates) - 1) / (count - 1)) for i in range(count)]
    return candidates.iloc[positions].reset_index(drop=True)


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a 10-question evaluation set (summary/authors/date/categories) from the cleaned dataframe."""
    papers = _select_papers(df, len(QUESTION_PLAN))
    test_set: list[dict[str, Any]] = []
    for index, (question_type, (_, row)) in enumerate(zip(QUESTION_PLAN, papers.iterrows()), start=1):
        title = normalize_whitespace(str(row["title"]))
        test_set.append(
            {
                "id": f"eval_{index:03d}",
                "question_type": question_type,
                "question": QUESTION_TEMPLATES[question_type].format(title=title),
                "ground_truth": _ground_truth(row, question_type),
                "ground_truth_doc_ids": [str(row["paper_id"])],
            }
        )
    write_json(Path(output_path), test_set)
    return test_set
