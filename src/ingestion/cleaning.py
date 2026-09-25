from __future__ import annotations

from datetime import date, datetime
import unicodedata
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import compact_join, normalize_whitespace, write_csv, write_json
from ingestion.crossref import PaperRecord, load_raw_records


def _normalize(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return normalize_whitespace(unicodedata.normalize("NFKC", str(value)))


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _record_dict(record: PaperRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, dict):
        return record
    return {
        "paper_id": record.paper_id,
        "title": record.title,
        "summary": record.summary,
        "authors": record.authors,
        "categories": record.categories,
        "primary_category": record.primary_category,
        "published": record.published,
        "updated": record.updated,
        "abs_url": record.abs_url,
        "pdf_url": record.pdf_url,
        "comment": record.comment,
    }


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw Crossref records into the tabular embedding contract."""
    run_day = pd.Timestamp(run_date).date()
    cleaned: list[dict[str, Any]] = []
    for record in records:
        row = _record_dict(record)
        paper_id = _normalize(row.get("paper_id") or row.get("DOI")).lower()
        title = _normalize(row.get("title"))
        summary = _normalize(row.get("summary") or row.get("abstract"))
        published_day = _as_date(row.get("published"))

        authors_value = row.get("authors") or row.get("author") or []
        if isinstance(authors_value, str):
            authors_value = [authors_value]
        authors = [_normalize(author) for author in authors_value if _normalize(author)]
        categories_value = row.get("categories") or row.get("subject") or []
        if isinstance(categories_value, str):
            categories_value = [categories_value]
        categories = [_normalize(category) for category in categories_value if _normalize(category)]
        authors_joined = compact_join(authors) or "Unknown"
        categories_joined = compact_join(categories) or "General"
        primary_category = _normalize(row.get("primary_category")) or (categories[0] if categories else "General")

        # A usable paper needs an identity, a publication date, a meaningful title,
        # and enough abstract text to support retrieval and answer evaluation.
        if not paper_id or not published_day or len(title) < 10 or len(summary) < 10:
            continue
        published = published_day.isoformat()
        updated_day = _as_date(row.get("updated")) or published_day
        text_for_embedding = "\n".join(
            (
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Published: {published}",
                f"Categories: {categories_joined}",
                f"Summary: {summary}",
            )
        )
        cleaned.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated_day.isoformat(),
                "age_days": (run_day - published_day).days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "abs_url": _normalize(row.get("abs_url")) or f"https://doi.org/{paper_id}",
                "pdf_url": _normalize(row.get("pdf_url")) or f"https://doi.org/{paper_id}",
                "comment": _normalize(row.get("comment")),
                "text_for_embedding": text_for_embedding,
            }
        )

    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "age_days", "authors_joined", "categories_joined",
        "summary_chars", "abs_url", "pdf_url", "comment", "text_for_embedding",
    ]
    df = pd.DataFrame(cleaned, columns=columns)
    if df.empty:
        return df
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(["published", "paper_id"], ascending=[False, True], kind="stable").reset_index(drop=True)
    return df


def repair_clean_from_raw(settings: Settings, run_date: datetime) -> pd.DataFrame:
    """Rebuild repaired clean artifacts from the authoritative raw snapshot.

    The corrupted clean artifact is never used as input, so repeating this call
    with the same raw snapshot and run_date produces the same repaired dataset.
    """
    raw_path = settings.paths.raw_records_json
    if not raw_path.exists():
        raw_path = settings.paths.raw_api_response
    repaired = build_clean_dataframe(load_raw_records(raw_path), run_date)
    write_csv(repaired, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired.to_dict(orient="records"))
    return repaired
