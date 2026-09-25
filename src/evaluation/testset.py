from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


_REQUIRED_COLUMNS = {"paper_id", "title", "summary", "published"}
_QUESTION_TYPES = ("summary", "authors", "date", "category", "multi_hop")
_SAMPLES_PER_TYPE = 2
_MIN_DOCUMENTS = 5


@dataclass(frozen=True)
class TestSet:
    samples: list[dict[str, Any]]


def _text(value: Any) -> str:
    if value is None or (not isinstance(value, (list, tuple, set)) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _joined_value(row: pd.Series, list_column: str, joined_column: str, fallback: str) -> str:
    joined = _text(row.get(joined_column))
    if joined:
        return joined

    values = row.get(list_column)
    if isinstance(values, str):
        # CSV round-trips may turn list columns into strings; the canonical
        # ``*_joined`` column is preferred whenever it is available.
        return _text(values) or fallback
    if isinstance(values, (list, tuple, set)):
        cleaned = [_text(value) for value in values]
        return ", ".join(value for value in cleaned if value) or fallback
    return fallback


def _normalized_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    missing = _REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Clean dataframe is missing required columns: {names}.")

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for _, source in df.iterrows():
        paper_id = _text(source.get("paper_id"))
        title = _text(source.get("title"))
        summary = _text(source.get("summary"))
        published = _text(source.get("published"))
        identity = paper_id.casefold()
        if not paper_id or not title or not summary or not published or identity in seen_ids:
            continue

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "published": published,
                "authors": _joined_value(source, "authors", "authors_joined", "Unknown"),
                "categories": _joined_value(
                    source,
                    "categories",
                    "categories_joined",
                    "Uncategorized",
                ),
            }
        )
        seen_ids.add(identity)

    rows.sort(key=lambda row: row["paper_id"].casefold())
    return rows


def _evenly_spaced(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Choose deterministic representatives across the full corpus."""
    if count <= 0:
        return []
    if len(rows) <= count:
        return [rows[index % len(rows)] for index in range(count)]

    return [
        rows[round(index * (len(rows) - 1) / (count - 1))]
        for index in range(count)
    ]


def _category_set(row: dict[str, Any]) -> set[str]:
    return {
        category.strip().casefold()
        for category in row["categories"].split(",")
        if category.strip() and category.strip().casefold() != "uncategorized"
    }


def _multihop_pairs(
    rows: list[dict[str, Any]],
    count: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Prefer pairs spanning different categories and avoid reusing documents."""
    candidates = []
    for left, right in combinations(rows, 2):
        left_categories = _category_set(left)
        right_categories = _category_set(right)
        overlap = len(left_categories & right_categories)
        breadth = len(left_categories | right_categories)
        candidates.append((overlap, -breadth, left["paper_id"], right["paper_id"], left, right))
    candidates.sort(key=lambda candidate: candidate[:4])

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    used_ids: set[str] = set()
    for _, _, _, _, left, right in candidates:
        if left["paper_id"] in used_ids or right["paper_id"] in used_ids:
            continue
        selected.append((left, right))
        used_ids.update((left["paper_id"], right["paper_id"]))
        if len(selected) == count:
            return selected

    # The minimum corpus size normally makes this unnecessary, but retaining a
    # deterministic fallback keeps the function usable for unusual small inputs.
    for _, _, _, _, left, right in candidates:
        pair = (left, right)
        if pair not in selected:
            selected.append(pair)
        if len(selected) == count:
            break
    return selected


def _sample(
    sample_id: int,
    question_type: str,
    question: str,
    ground_truth: str,
    doc_ids: list[str],
) -> dict[str, Any]:
    return {
        "id": f"eval_{sample_id:03d}",
        "type": question_type,
        # Compatibility alias used by the existing evaluation runner.
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": doc_ids,
    }


def build_test_set(df: pd.DataFrame, output_path: str | Path) -> list[dict[str, Any]]:
    """Build a deterministic ten-question benchmark from cleaned paper data.

    Two questions are generated for each required type: summary, authors, date,
    category, and multi-hop. Every answer and document identifier comes directly
    from the supplied dataframe rather than from hard-coded paper metadata.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    rows = _normalized_rows(df)
    if len(rows) < _MIN_DOCUMENTS:
        raise ValueError(
            f"At least {_MIN_DOCUMENTS} valid, unique documents are required; got {len(rows)}."
        )

    representatives = _evenly_spaced(rows, 4 * _SAMPLES_PER_TYPE)
    samples: list[dict[str, Any]] = []

    for row in representatives[0:2]:
        samples.append(
            _sample(
                len(samples) + 1,
                "summary",
                f"What is the main research contribution of the paper '{row['title']}'?",
                first_sentence(row["summary"]),
                [row["paper_id"]],
            )
        )

    for row in representatives[2:4]:
        samples.append(
            _sample(
                len(samples) + 1,
                "authors",
                f"Who authored the study '{row['title']}'?",
                row["authors"],
                [row["paper_id"]],
            )
        )

    for row in representatives[4:6]:
        samples.append(
            _sample(
                len(samples) + 1,
                "date",
                f"When was the study '{row['title']}' published?",
                row["published"],
                [row["paper_id"]],
            )
        )

    for row in representatives[6:8]:
        samples.append(
            _sample(
                len(samples) + 1,
                "category",
                f"What categories does the paper '{row['title']}' belong to?",
                row["categories"],
                [row["paper_id"]],
            )
        )

    for left, right in _multihop_pairs(rows, _SAMPLES_PER_TYPE):
        question = (
            f"How do the studies '{left['title']}' and '{right['title']}' connect "
            f"the fields of {left['categories']} and {right['categories']}? "
            "Summarize the main contribution of each study."
        )
        ground_truth = (
            f"{left['title']}: {first_sentence(left['summary'])} "
            f"{right['title']}: {first_sentence(right['summary'])}"
        )
        samples.append(
            _sample(
                len(samples) + 1,
                "multi_hop",
                question,
                ground_truth,
                [left["paper_id"], right["paper_id"]],
            )
        )

    expected_count = len(_QUESTION_TYPES) * _SAMPLES_PER_TYPE
    if len(samples) != expected_count:
        raise RuntimeError(f"Expected {expected_count} benchmark samples, generated {len(samples)}.")

    write_json(Path(output_path), samples)
    return samples


def load_or_create_test_set(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    refresh: bool = False,
) -> TestSet:
    """Load an existing benchmark or create it when missing/requested.

    ``TestSet.samples`` provides the object-style API used by the lab command,
    while ``build_test_set`` remains available to existing pipeline code.
    """
    path = Path(output_path)
    if path.exists() and not refresh:
        raw_samples = read_json(path)
        if not isinstance(raw_samples, list):
            raise ValueError(f"Test set must contain a JSON list: {path}")

        required = {"id", "type", "question", "ground_truth", "ground_truth_doc_ids"}
        samples: list[dict[str, Any]] = []
        for index, item in enumerate(raw_samples):
            if not isinstance(item, dict):
                raise ValueError(f"Test sample {index} in {path} is not a JSON object.")
            missing = required.difference(item)
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"Test sample {index} in {path} is missing fields: {names}.")
            if not isinstance(item["ground_truth_doc_ids"], list):
                raise ValueError(
                    f"Test sample {index} in {path} has invalid ground_truth_doc_ids."
                )
            samples.append(item)
    else:
        samples = build_test_set(df, path)

    return TestSet(samples=samples)
