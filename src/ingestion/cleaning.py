from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

MIN_SUMMARY_CHARS = 30
MIN_TITLE_CHARS = 8

_MARKUP_TAG = re.compile(r"<[^>]+>")

CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]


def clean_text(value: object) -> str:
    """Bo markup con sot, chuan hoa khoang trang."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return normalize_whitespace(_MARKUP_TAG.sub(" ", str(value)))


def parse_iso_date(value: object) -> date | None:
    """Parse ngay ISO mot cach an toan, tra ve None neu khong hop le."""
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def compose_text_for_embedding(
    title: str,
    authors_joined: str,
    published: str,
    categories_joined: str,
    summary: str,
) -> str:
    """Ghep 5 truong thanh mot doan ngu canh chuan cho mo hinh nhung vector."""
    return (
        f"Title: {title}\n"
        f"Authors: {authors_joined}\n"
        f"Published: {published}\n"
        f"Categories: {categories_joined}\n"
        f"Summary: {summary}"
    )


def compute_age_days(published: object, run_date: datetime) -> int:
    """age_days = (run_date - published).days. Tra ve -1 khi thieu ngay xuat ban."""
    published_date = parse_iso_date(published)
    if published_date is None:
        return -1
    return (run_date.date() - published_date).days


def rebuild_derived_columns(df: pd.DataFrame, run_date: datetime) -> pd.DataFrame:
    """Tinh lai cac cot phai sinh sau khi title/summary/published bi thay doi.

    Dung chung cho ca buoc cleaning lan buoc corruption de dam bao
    `text_for_embedding` luon dong bo voi du lieu goc.
    """
    work = df.copy()
    work["authors_joined"] = work["authors"].apply(
        lambda values: compact_join([str(item) for item in (values or [])])
    )
    work["categories_joined"] = work["categories"].apply(
        lambda values: compact_join([str(item) for item in (values or [])])
    )
    work["summary_chars"] = work["summary"].apply(lambda value: len(str(value or "")))
    work["age_days"] = work["published"].apply(lambda value: compute_age_days(value, run_date))
    work["text_for_embedding"] = work.apply(
        lambda row: compose_text_for_embedding(
            title=str(row["title"]),
            authors_joined=str(row["authors_joined"]),
            published=str(row["published"]),
            categories_joined=str(row["categories_joined"]),
            summary=str(row["summary"]),
        ),
        axis=1,
    )
    return work


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Chuan hoa raw records thanh dataframe san sang de embed.

    Buoc nay la idempotent: cung mot bo `records` va `run_date` luon cho ra
    cung mot dataframe, nen no duoc dung lai o pha repair.
    """
    rows: list[dict] = []
    for record in records:
        payload = asdict(record) if is_dataclass(record) else dict(record)

        title = clean_text(payload.get("title"))
        summary = clean_text(payload.get("summary"))
        paper_id = normalize_whitespace(str(payload.get("paper_id", "")))

        authors = [normalize_whitespace(str(item)) for item in (payload.get("authors") or []) if str(item).strip()]
        categories = [
            normalize_whitespace(str(item)) for item in (payload.get("categories") or []) if str(item).strip()
        ]

        published_date = parse_iso_date(payload.get("published"))
        updated_date = parse_iso_date(payload.get("updated")) or published_date

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(str(payload.get("primary_category", "")))
                or (categories[0] if categories else ""),
                "published": published_date.isoformat() if published_date else "",
                "updated": updated_date.isoformat() if updated_date else "",
                "abs_url": normalize_whitespace(str(payload.get("abs_url", ""))),
                "pdf_url": normalize_whitespace(str(payload.get("pdf_url", ""))),
                "comment": normalize_whitespace(str(payload.get("comment", ""))),
            }
        )

    if not rows:
        return pd.DataFrame(columns=CLEAN_COLUMNS)
    df = pd.DataFrame(rows)

    # Loai bo ban ghi khong du chat luong de nhung vector.
    df = df[df["paper_id"].str.len() > 0]
    df = df[df["title"].str.len() >= MIN_TITLE_CHARS]
    df = df[df["summary"].str.len() >= MIN_SUMMARY_CHARS]
    df = df[df["published"].str.len() > 0]

    # Khu trung lap theo khoa duy nhat paper_id.
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    df = rebuild_derived_columns(df, run_date)
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df[CLEAN_COLUMNS]
