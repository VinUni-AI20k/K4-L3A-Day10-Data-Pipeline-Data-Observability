from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json

MIN_DOCUMENTS = 4

# 10 cau hoi chia deu cho 4 nhom nghiep vu (summary / authors / date / categories).
QUESTION_PLAN: tuple[tuple[str, int], ...] = (
    ("summary", 3),
    ("authors", 3),
    ("date", 2),
    ("categories", 2),
)
TOTAL_QUESTIONS = sum(count for _, count in QUESTION_PLAN)

# Cach dat cau hoi phai khop voi cac tu khoa ma retrieval/qa.py dung de trich dap an.
QUESTION_TEMPLATES: dict[str, str] = {
    "summary": "What is the summary of the paper '{title}'?",
    "authors": "Who authored the paper '{title}'?",
    "date": "When was the paper '{title}' published?",
    "categories": "What categories does the paper '{title}' belong to?",
}

# Cot chua ground truth tuong ung voi tung loai cau hoi (thu lan luot tu trai sang phai).
ANSWER_COLUMNS: dict[str, tuple[str, ...]] = {
    "summary": ("summary",),
    "authors": ("authors_joined",),
    "date": ("published",),
    # Crossref khong phai luc nao cung tra ve `subject`, nen fallback sang primary_category.
    "categories": ("categories_joined", "primary_category"),
}

REQUIRED_COLUMNS = ("paper_id", "title", "summary", "authors_joined", "categories_joined", "published")


def _candidate_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Chi giu lai cac paper co the dung lam de thi (title tra cuu duoc, khong trung)."""
    rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    seen_ids: set[str] = set()

    for record in df.to_dict(orient="records"):
        paper_id = normalize_whitespace(str(record.get("paper_id") or ""))
        title = normalize_whitespace(str(record.get("title") or ""))
        if not paper_id or not title or paper_id in seen_ids:
            continue
        # Title co dau nhay don se pha vo buoc lookup theo regex "'([^']+)'" trong qa.py.
        if "'" in title or title.lower() in seen_titles:
            continue

        seen_ids.add(paper_id)
        seen_titles.add(title.lower())
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": normalize_whitespace(str(record.get("summary") or "")),
                "authors_joined": normalize_whitespace(str(record.get("authors_joined") or "")),
                "categories_joined": normalize_whitespace(str(record.get("categories_joined") or "")),
                "primary_category": normalize_whitespace(str(record.get("primary_category") or "")),
                "published": normalize_whitespace(str(record.get("published") or "")),
            }
        )
    return rows


def _representative_pool(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Lay mau trai deu tren toan bo corpus (df da sort theo published giam dan)."""
    if len(rows) <= limit:
        return list(rows)
    step = len(rows) / limit
    return [rows[int(index * step)] for index in range(limit)]


def _answer_value(row: dict[str, Any], question_type: str) -> str:
    for column in ANSWER_COLUMNS[question_type]:
        value = row.get(column, "")
        if value:
            return value
    return ""


def _pick_row(
    pool: list[dict[str, Any]],
    cursor: int,
    question_type: str,
    used_ids: set[str],
) -> tuple[dict[str, Any] | None, int]:
    """Chon paper ke tiep co du lieu tra loi duoc, uu tien paper chua dung."""
    size = len(pool)
    for allow_reuse in (False, True):
        for offset in range(size):
            position = (cursor + offset) % size
            row = pool[position]
            if not _answer_value(row, question_type):
                continue
            if not allow_reuse and row["paper_id"] in used_ids:
                continue
            return row, (position + 1) % size
    return None, cursor


def _ground_truth(row: dict[str, Any], question_type: str) -> str:
    value = _answer_value(row, question_type)
    if question_type == "summary":
        # qa.py tra ve first_sentence(summary) nen ground truth phai cung dang.
        return first_sentence(value)
    return value


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set (10 cau hoi, 4 nhom) tu cleaned dataframe va ghi ra JSON.

    Moi row gom: id, question_type, question, ground_truth, ground_truth_doc_ids.
    """
    if df is None or df.empty:
        raise ValueError("Cleaned dataframe is empty; cannot build an evaluation set.")

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Cleaned dataframe is missing required columns: {', '.join(missing)}")

    candidates = _candidate_rows(df)
    if len(candidates) < MIN_DOCUMENTS:
        raise ValueError(
            f"Need at least {MIN_DOCUMENTS} usable documents to build the evaluation set, got {len(candidates)}."
        )

    pool = _representative_pool(candidates, TOTAL_QUESTIONS)
    used_ids: set[str] = set()
    cursor = 0
    test_set: list[dict[str, Any]] = []

    for question_type, count in QUESTION_PLAN:
        for _ in range(count):
            row, cursor = _pick_row(pool, cursor, question_type, used_ids)
            if row is None:
                raise ValueError(f"No document carries data for question type '{question_type}'.")

            used_ids.add(row["paper_id"])
            test_set.append(
                {
                    "id": f"eval_{len(test_set) + 1:03d}",
                    "question_type": question_type,
                    "question": QUESTION_TEMPLATES[question_type].format(title=row["title"]),
                    "ground_truth": _ground_truth(row, question_type),
                    "ground_truth_doc_ids": [row["paper_id"]],
                }
            )

    write_json(Path(output_path), test_set)
    return test_set
