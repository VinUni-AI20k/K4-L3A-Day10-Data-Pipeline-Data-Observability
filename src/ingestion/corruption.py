from __future__ import annotations

import numpy as np
import pandas as pd

from core.utils import write_json

SEED = 42
DROP_RATIO = 0.2
NOISE_TOKENS = ["#@!$%^&*", "xQzv9__zz", "~~||##", "%%ERR%%", "@@??@@", "0xDEADBEEF"]
TITLE_MAX_CHARS = 8
STALE_YEARS = 5


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate nhieu dang data corruption.

    Pseudo-code:
    1. Drop mot so latest records.
    2. Blank summary o mot so dong.
    3. Inject noise vao text.
    4. Lam title bi truncate.
    5. Lam published date cu di.
    6. Add duplicate rows.
    7. Rebuild `text_for_embedding`.
    8. Ghi corruption log vao output_log_path.
    """
    rng = np.random.default_rng(SEED)
    out = df.copy().reset_index(drop=True)
    out["published"] = pd.to_datetime(out["published"], utc=True).dt.strftime("%Y-%m-%d")
    rows_before = len(out)
    log: list[dict] = []

    def pick(frame: pd.DataFrame, ratio: float) -> list[int]:
        count = max(1, round(len(frame) * ratio))
        return sorted(int(i) for i in rng.choice(frame.index.to_numpy(), size=count, replace=False))

    def record(name: str, description: str, ids: list[str]) -> None:
        log.append({"corruption": name, "description": description, "affected_rows": len(ids), "paper_ids": ids})

    # 1. Drop cac bai bao moi nhat.
    n_drop = max(1, round(len(out) * DROP_RATIO))
    latest = out.sort_values(["published", "paper_id"], ascending=[False, True]).head(n_drop)
    record("drop_latest_records", f"Dropped the {n_drop} most recent papers.", latest["paper_id"].tolist())
    out = out.drop(index=latest.index).reset_index(drop=True)

    # 2. Blank summary.
    idx = pick(out, 0.3)
    record("blank_summary", "Cleared summary text.", out.loc[idx, "paper_id"].tolist())
    out.loc[idx, "summary"] = ""
    out.loc[idx, "summary_chars"] = 0

    # 3. Inject noise.
    idx = pick(out, 0.3)
    record("inject_text_noise", "Appended garbage tokens to summary/embedding text.", out.loc[idx, "paper_id"].tolist())
    for i in idx:
        noise = " ".join(rng.choice(NOISE_TOKENS, size=8))
        out.loc[i, "summary"] = f"{out.loc[i, 'summary']} {noise}".strip()
        out.loc[i, "summary_chars"] = len(out.loc[i, "summary"])

    # 4. Truncate title.
    idx = pick(out, 0.4)
    record("truncate_title", f"Cut titles to {TITLE_MAX_CHARS} characters.", out.loc[idx, "paper_id"].tolist())
    out.loc[idx, "title"] = out.loc[idx, "title"].str.slice(0, TITLE_MAX_CHARS)

    # 5. Stale date.
    idx = pick(out, 0.3)
    record("stale_date", f"Moved published date back {STALE_YEARS} years.", out.loc[idx, "paper_id"].tolist())
    shifted = pd.to_datetime(out.loc[idx, "published"]) - pd.DateOffset(years=STALE_YEARS)
    if "age_days" in out:
        out.loc[idx, "age_days"] = out.loc[idx, "age_days"] + (
            pd.to_datetime(out.loc[idx, "published"]) - shifted
        ).dt.days
    out.loc[idx, "published"] = shifted.dt.strftime("%Y-%m-%d")
    if "updated" in out:
        out.loc[idx, "updated"] = out.loc[idx, "published"]

    # 6. Duplicate rows (bang so dong da drop de giu nguyen kich thuoc bang).
    idx = sorted(int(i) for i in rng.choice(out.index.to_numpy(), size=n_drop, replace=False))
    record("duplicate_rows", "Appended exact duplicate rows.", out.loc[idx, "paper_id"].tolist())
    out = pd.concat([out, out.loc[idx]], ignore_index=True)

    # 7. Rebuild text_for_embedding tu cac cot da bi hong.
    out["text_for_embedding"] = (
        "Title: " + out["title"]
        + "\nAuthors: " + out["authors_joined"]
        + "\nPublished: " + out["published"].astype(str)
        + "\nCategories: " + out["categories_joined"]
        + "\nSummary: " + out["summary"]
    )

    write_json(
        output_log_path,
        {"seed": SEED, "rows_before": rows_before, "rows_after": len(out), "corruptions": log},
    )
    return out
