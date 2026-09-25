"""
conftest.py — shared fixtures for Lan's tests.
clean_df được build trực tiếp từ crossref_records.json (không phụ thuộc cleaning.py).
"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Đường dẫn đến raw data
# ---------------------------------------------------------------------------
_RAW_RECORDS = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "crossref_records.json"
)

RUN_DATE = datetime(2026, 9, 25, 12, 0, 0)
_TODAY = RUN_DATE.date()


def _build_clean_df_from_json(path: Path) -> pd.DataFrame:
    """Build clean DataFrame trực tiếp từ crossref_records.json.
    Không phụ thuộc vào cleaning.py — Lan tự làm được độc lập.
    """
    records = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for r in records:
        published_str = r.get("published", "") or ""
        try:
            pub_date = date.fromisoformat(published_str)
            age_days = (_TODAY - pub_date).days
        except ValueError:
            pub_date = None
            age_days = 0

        authors = r.get("authors", [])
        categories = r.get("categories", [])
        summary = r.get("summary", "") or ""

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        title = r.get("title", "")

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published_str}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append({
            "paper_id": r.get("paper_id", ""),
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": r.get("primary_category", ""),
            "published": published_str,
            "updated": r.get("updated", ""),
            "abs_url": r.get("abs_url", ""),
            "pdf_url": r.get("pdf_url", ""),
            "comment": r.get("comment", ""),
            "age_days": age_days,
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "text_for_embedding": text_for_embedding,
        })

    df = pd.DataFrame(rows)
    # Bỏ duplicate paper_id
    df = df.drop_duplicates(subset="paper_id").reset_index(drop=True)
    # Sort theo published giảm dần
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    return df


@pytest.fixture(scope="session")
def clean_df() -> pd.DataFrame:
    """DataFrame sạch từ 24 bài báo — self-contained, không cần cleaning.py."""
    if not _RAW_RECORDS.exists():
        pytest.skip(f"File không tồn tại: {_RAW_RECORDS}")
    return _build_clean_df_from_json(_RAW_RECORDS)


@pytest.fixture
def real_records_path() -> Path:
    return _RAW_RECORDS
