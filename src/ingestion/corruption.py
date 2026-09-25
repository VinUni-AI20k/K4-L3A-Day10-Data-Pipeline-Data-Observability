from __future__ import annotations

import pandas as pd
from datetime import date

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    corrupted = df.copy().sort_values("published", ascending=False).reset_index(drop=True)
    log = []

    # 1. Drop latest 20% records
    n_drop = max(1, len(corrupted) // 5)
    dropped_ids = corrupted.iloc[:n_drop]["paper_id"].tolist()
    corrupted = corrupted.iloc[n_drop:].reset_index(drop=True)
    log.append({"type": "drop_latest", "count": n_drop, "affected_ids": dropped_ids,
                "description": f"Dropped {n_drop} most-recent records (20%)."})

    # 2. Blank summary on first 3 rows
    blank_ids = corrupted.iloc[:3]["paper_id"].tolist()
    corrupted.loc[corrupted.index[:3], "summary"] = ""
    log.append({"type": "blank_summary", "count": 3, "affected_ids": blank_ids,
                "description": "Blanked summary field on 3 records."})

    # 3. Inject noise into summary of next 3 rows
    noise_ids = corrupted.iloc[3:6]["paper_id"].tolist()
    corrupted.loc[corrupted.index[3:6], "summary"] = (
        corrupted.loc[corrupted.index[3:6], "summary"].str[:50] + " ####NOISE#### "
        + corrupted.loc[corrupted.index[3:6], "summary"].str[50:]
    )
    log.append({"type": "inject_noise", "count": 3, "affected_ids": noise_ids,
                "description": "Injected ####NOISE#### into summary of 3 records."})

    # 4. Truncate title to < 8 chars on rows 6-8
    truncate_ids = corrupted.iloc[6:9]["paper_id"].tolist()
    corrupted.loc[corrupted.index[6:9], "title"] = corrupted.loc[corrupted.index[6:9], "title"].str[:7]
    log.append({"type": "truncate_title", "count": 3, "affected_ids": truncate_ids,
                "description": "Truncated title to 7 characters on 3 records."})

    # 5. Stale date — push back 3 years on rows 9-14 (6 records → >25% stale → is_fresh=False)
    stale_ids = corrupted.iloc[9:15]["paper_id"].tolist()
    def _stale(d: str) -> str:
        try:
            parsed = date.fromisoformat(d)
            return str(parsed.replace(year=parsed.year - 3))
        except ValueError:
            return d
    corrupted.loc[corrupted.index[9:15], "published"] = (
        corrupted.loc[corrupted.index[9:15], "published"].apply(_stale)
    )
    log.append({"type": "stale_date", "count": 6, "affected_ids": stale_ids,
                "description": "Set published date 3 years back on 6 records (triggers is_fresh=False)."})

    # 6. Duplicate first 3 rows
    dupe_ids = corrupted.iloc[:3]["paper_id"].tolist()
    dupes = corrupted.iloc[:3].copy()
    corrupted = pd.concat([corrupted, dupes], ignore_index=True)
    log.append({"type": "duplicate_rows", "count": 3, "affected_ids": dupe_ids,
                "description": "Duplicated 3 records — violates paper_id uniqueness."})

    # Rebuild derived columns (must match cleaning.py format exactly)
    from datetime import date as _date
    today = _date.today()
    def _age(pub: str) -> int:
        try:
            return (today - _date.fromisoformat(pub)).days
        except ValueError:
            return -1
    corrupted["age_days"] = corrupted["published"].apply(_age)
    corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["text_for_embedding"] = (
        "Title: " + corrupted["title"] + "\n"
        + "Authors: " + corrupted["authors_joined"] + "\n"
        + "Published: " + corrupted["published"] + "\n"
        + "Categories: " + corrupted["categories_joined"] + "\n"
        + "Summary: " + corrupted["summary"]
    )

    write_json(output_log_path, log)
    return corrupted
