from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import read_json, write_json


QUESTION_TYPES = ("summary", "authors", "date", "category", "multi_hop")
REQUIRED_COLUMNS = {
    "paper_id", "title", "summary", "authors_joined", "published", "categories_joined"
}


@dataclass(frozen=True)
class BenchmarkTestSet:
    samples: list[dict[str, Any]]


def _clean_papers(df: pd.DataFrame) -> list[dict[str, Any]]:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing clean-data columns: {', '.join(sorted(missing))}")
    papers = df.drop_duplicates(subset="paper_id").to_dict(orient="records")
    papers = [
        paper for paper in papers
        if all(isinstance(paper[field], str) and paper[field].strip() for field in REQUIRED_COLUMNS)
    ]
    if len(papers) < 5:
        raise ValueError("At least five complete, distinct papers are needed for the benchmark.")
    return papers


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Build one grounded question of each requested type from cleaned papers."""
    papers = _clean_papers(df)
    summary, authors, date, category = papers[:4]
    summary_field = summary.get("primary_category") or summary["categories_joined"]
    bridge = next(
        (paper for paper in papers[4:] if (paper.get("primary_category") or paper["categories_joined"]) != summary_field),
        papers[4],
    )

    def sample(number: int, kind: str, question: str, answer: str, ids: list[str]) -> dict[str, Any]:
        return {
            "id": f"benchmark-{number:02d}-{kind}",
            "type": kind,
            "question_type": kind,  # Existing evaluation.metrics consumer.
            "question": question,
            "ground_truth": answer,
            "ground_truth_doc_ids": ids,
        }

    samples = [
        sample(1, "summary", f"What is the main research contribution of '{summary['title']}'?", summary["summary"], [summary["paper_id"]]),
        sample(2, "authors", f"Who authored the study '{authors['title']}'?", authors["authors_joined"], [authors["paper_id"]]),
        sample(3, "date", f"When was '{date['title']}' published?", date["published"], [date["paper_id"]]),
        sample(4, "category", f"What categories does the work '{category['title']}' belong to?", category["categories_joined"], [category["paper_id"]]),
        sample(
            5,
            "multi_hop",
            f"How do the contributions of '{summary['title']}' and '{bridge['title']}' complement each other in a retrieval pipeline?",
            f"'{summary['title']}': {summary['summary']} '{bridge['title']}': {bridge['summary']}",
            [summary["paper_id"], bridge["paper_id"]],
        ),
    ]
    write_json(Path(output_path), samples)
    return samples


def load_or_create_test_set(df: pd.DataFrame, output_path: Path) -> BenchmarkTestSet:
    """Reuse a valid benchmark only while its cited documents remain present."""
    path = Path(output_path)
    if path.exists():
        saved = read_json(path)
        known_ids = set(df["paper_id"].astype(str)) if "paper_id" in df else set()
        required = {"id", "type", "question", "ground_truth", "ground_truth_doc_ids", "question_type"}
        if (
            isinstance(saved, list)
            and len(saved) == 5
            and [item.get("type") for item in saved if isinstance(item, dict)] == list(QUESTION_TYPES)
            and all(
                required <= item.keys()
                and isinstance(item["ground_truth_doc_ids"], list)
                and item["ground_truth_doc_ids"]
                and set(item["ground_truth_doc_ids"]) <= known_ids
                for item in saved
            )
        ):
            return BenchmarkTestSet(samples=saved)
    return BenchmarkTestSet(samples=build_test_set(df, path))
