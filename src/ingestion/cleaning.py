from __future__ import annotations

from datetime import datetime
from dataclasses import asdict

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    df = pd.DataFrame([asdict(r) for r in records])
    if df.empty:
        return df
    
    df["published_dt"] = pd.to_datetime(df["published"])
    if df["published_dt"].dt.tz is None:
        df["published_dt"] = df["published_dt"].dt.tz_localize("UTC")
    else:
        df["published_dt"] = df["published_dt"].dt.tz_convert("UTC")
        
    run_date_utc = pd.to_datetime(run_date)
    if run_date_utc.tz is None:
        run_date_utc = run_date_utc.tz_localize("UTC")
    else:
        run_date_utc = run_date_utc.tz_convert("UTC")
        
    df["age_days"] = (run_date_utc - df["published_dt"]).dt.days
    
    df["authors_joined"] = df["authors"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    df["categories_joined"] = df["categories"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
    df["summary_chars"] = df["summary"].str.len()
    
    df["text_for_embedding"] = (
        "Title: " + df["title"] + "\n" +
        "Authors: " + df["authors_joined"] + "\n" +
        "Published: " + df["published_dt"].dt.strftime("%Y-%m-%d") + "\n" +
        "Categories: " + df["categories_joined"] + "\n" +
        "Summary: " + df["summary"]
    )
    
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df[df["title"].str.strip() != ""]
    df = df[df["summary"].str.strip() != ""]
    
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    df = df.drop(columns=["published_dt"])
    
    return df
