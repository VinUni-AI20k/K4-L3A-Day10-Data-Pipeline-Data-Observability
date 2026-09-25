from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a structured DataFrame ready for embedding & observability checks.

    Steps:
    1. Convert records to dictionary list & create initial DataFrame.
    2. Deduplicate records by paper_id.
    3. Filter out invalid rows (missing paper_id or title).
    4. Construct helper columns:
       - authors_joined
       - categories_joined
       - summary_chars
    5. Calculate age_days = (run_date - published).days.
    6. Construct text_for_embedding format (5 lines: Title, Authors, Published, Categories, Summary).
    7. Reset index and return clean DataFrame.
    """
    if not records:
        return pd.DataFrame()

    raw_dicts = [asdict(r) if isinstance(r, PaperRecord) else dict(r) for r in records]
    df = pd.DataFrame(raw_dicts)

    # 1. Khử trùng lặp bản ghi theo khóa duy nhất paper_id
    if "paper_id" in df.columns:
        df = df.drop_duplicates(subset=["paper_id"], keep="first")
        df = df[df["paper_id"].notna() & (df["paper_id"].astype(str).str.strip() != "")]

    if "title" in df.columns:
        df = df[df["title"].notna() & (df["title"].astype(str).str.strip() != "")]

    if df.empty:
        return df

    # Cot helper authors_joined va categories_joined
    def join_list(val: Any) -> str:
        if isinstance(val, list):
            return ", ".join([str(x).strip() for x in val if str(x).strip()])
        if isinstance(val, str):
            return val.strip()
        return ""

    df["authors_joined"] = df["authors"].apply(join_list)
    df["categories_joined"] = df["categories"].apply(join_list)
    df["summary_chars"] = df["summary"].apply(lambda s: len(str(s)) if pd.notna(s) else 0)

    # 2. Tính toán độ tươi của dữ liệu: age_days = (run_date - published).days
    run_date_val = run_date.date() if isinstance(run_date, datetime) else run_date

    def calc_age_days(pub_val: Any) -> int:
        if not pub_val or pd.isna(pub_val):
            return 0
        try:
            pub_dt = pd.to_datetime(pub_val)
            pub_date = pub_dt.date()
            return (run_date_val - pub_date).days
        except Exception:
            return 0

    df["age_days"] = df["published"].apply(calc_age_days).astype(int)

    # 3. Xây dựng trường nội dung tổng hợp cho Vector Database text_for_embedding
    def build_text_for_embedding(row: pd.Series) -> str:
        t = str(row.get("title", "")).strip()
        a = str(row.get("authors_joined", "")).strip()
        p = str(row.get("published", "")).strip()
        c = str(row.get("categories_joined", "")).strip()
        s = str(row.get("summary", "")).strip()
        return f"Title: {t}\nAuthors: {a}\nPublished: {p}\nCategories: {c}\nSummary: {s}"

    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1)

    df = df.reset_index(drop=True)
    return df

