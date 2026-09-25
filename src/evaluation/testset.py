from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


@dataclass(frozen=True)
class TestSet:
    """Serializable benchmark samples used to evaluate retrieval and QA."""

    samples: list[dict[str, Any]]


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "published",
    "categories_joined",
}


def _value(row: pd.Series, column: str) -> str:
    value = row[column]
    if pd.isna(value):
        raise ValueError(f"Cleaned paper '{row['paper_id']}' has no value for '{column}'.")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Cleaned paper '{row['paper_id']}' has an empty value for '{column}'.")
    return text


def _sample(sample_id: str, question_type: str, question: str, ground_truth: str, doc_ids: list[str]) -> dict[str, Any]:
    """Create a sample compatible with both the current and legacy evaluators."""
    return {
        "id": sample_id,
        "type": question_type,
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": doc_ids,
    }


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Build five deterministic benchmark questions from actual cleaned papers."""
    missing_columns = _REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Cleaned dataframe is missing required columns: {sorted(missing_columns)}")
    if len(df) < 2:
        raise ValueError("At least two cleaned papers are required to create the multi-hop benchmark.")

    papers = df.reset_index(drop=True)
    summary_paper = papers.iloc[0]
    authors_paper = papers.iloc[1 % len(papers)]
    date_paper = papers.iloc[2 % len(papers)]
    category_paper = papers.iloc[3 % len(papers)]
    first_hop_paper = papers.iloc[0]
    second_hop_paper = papers.iloc[1 % len(papers)]

    summary_title = _value(summary_paper, "title")
    authors_title = _value(authors_paper, "title")
    date_title = _value(date_paper, "title")
    category_title = _value(category_paper, "title")
    first_hop_title = _value(first_hop_paper, "title")
    second_hop_title = _value(second_hop_paper, "title")

    samples = [
        _sample(
            "eval_001",
            "summary",
            f"What is the main research summary of the paper '{summary_title}'?",
            first_sentence(_value(summary_paper, "summary")),
            [_value(summary_paper, "paper_id")],
        ),
        _sample(
            "eval_002",
            "authors",
            f"Who authored the research paper '{authors_title}'?",
            _value(authors_paper, "authors_joined"),
            [_value(authors_paper, "paper_id")],
        ),
        _sample(
            "eval_003",
            "date",
            f"When was the paper '{date_title}' published?",
            _value(date_paper, "published"),
            [_value(date_paper, "paper_id")],
        ),
        _sample(
            "eval_004",
            "category",
            f"What categories does the paper '{category_title}' belong to?",
            _value(category_paper, "categories_joined"),
            [_value(category_paper, "paper_id")],
        ),
        _sample(
            "eval_005",
            "multi_hop",
            f"How do the research topics in '{first_hop_title}' and '{second_hop_title}' relate to each other?",
            f"'{first_hop_title}' studies {first_sentence(_value(first_hop_paper, 'summary'))} "
            f"'{second_hop_title}' studies {first_sentence(_value(second_hop_paper, 'summary'))}",
            [_value(first_hop_paper, "paper_id"), _value(second_hop_paper, "paper_id")],
        ),
    ]
    write_json(Path(output_path), samples)
    return samples


def load_or_create_test_set(df: pd.DataFrame, output_path: Path) -> TestSet:
    """Load an existing valid benchmark or create it from the supplied clean data."""
    path = Path(output_path)
    if path.exists():
        samples = read_json(path)
        if isinstance(samples, list) and len(samples) == 5:
            required_fields = {"id", "type", "question", "ground_truth", "ground_truth_doc_ids"}
            if all(required_fields <= set(sample) for sample in samples if isinstance(sample, dict)):
                return TestSet(samples=samples)
    return TestSet(samples=build_test_set(df, path))
