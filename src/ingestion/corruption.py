from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import parse_iso_date, rebuild_derived_columns

DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_ROWS = 2
NOISE_ROWS = 2
TRUNCATE_TITLE_ROWS = 2
STALE_DATE_ROWS = 3
DUPLICATE_ROWS = 2
STALE_SHIFT_DAYS = 365
NOISE_TOKEN = " ###@@@!!! %%% ��� corrupted-payload ###@@@!!!"


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Tiem 6 dang loi du lieu thuc te vao dataframe da lam sach.

    Ham chay deterministic (khong dung random) de moi lan chay deu tai hien
    cung mot muc do suy giam, phuc vu viec doi chieu 3 trang thai.
    """
    run_date = now_utc()
    work = df.copy().reset_index(drop=True)
    events: list[dict[str, Any]] = []
    rows_before = int(len(work))

    # --- 1. Drop latest records: mat du lieu moi nhat (stale ingestion) ---
    work = work.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    drop_count = max(1, round(len(work) * DROP_LATEST_RATIO))
    dropped_ids = work.head(drop_count)["paper_id"].tolist()
    work = work.iloc[drop_count:].reset_index(drop=True)
    events.append(
        {
            "step": 1,
            "corruption_type": "drop_latest_records",
            "description": f"Bo {drop_count} bai bao moi nhat ({DROP_LATEST_RATIO:.0%} corpus).",
            "affected_rows": drop_count,
            "affected_paper_ids": dropped_ids,
        }
    )

    # --- 2. Blank summary: cao du lieu ve rong ---
    blank_index = list(range(min(BLANK_SUMMARY_ROWS, len(work))))
    work.loc[blank_index, "summary"] = ""
    events.append(
        {
            "step": 2,
            "corruption_type": "blank_summary",
            "description": "Xoa trang truong summary.",
            "affected_rows": len(blank_index),
            "affected_paper_ids": work.loc[blank_index, "paper_id"].tolist(),
        }
    )

    # --- 3. Inject noise: chen ky tu rac vao tom tat ---
    noise_index = [i for i in range(len(work)) if i not in blank_index][:NOISE_ROWS]
    for position in noise_index:
        work.at[position, "summary"] = str(work.at[position, "summary"]) + NOISE_TOKEN
    events.append(
        {
            "step": 3,
            "corruption_type": "inject_noise",
            "description": "Chen chuoi ky tu rac vao summary.",
            "affected_rows": len(noise_index),
            "affected_paper_ids": work.loc[noise_index, "paper_id"].tolist(),
        }
    )

    # --- 4. Truncate title: tieu de bi cat con duoi 8 ky tu ---
    truncate_index = list(range(min(TRUNCATE_TITLE_ROWS, len(work))))
    for position in truncate_index:
        work.at[position, "title"] = str(work.at[position, "title"])[:7].strip()
    events.append(
        {
            "step": 4,
            "corruption_type": "truncate_title",
            "description": "Cat tieu de xuong duoi 8 ky tu.",
            "affected_rows": len(truncate_index),
            "affected_paper_ids": work.loc[truncate_index, "paper_id"].tolist(),
        }
    )

    # --- 5. Stale date: lui ngay xuat ban 365 ngay ---
    stale_index = list(range(min(STALE_DATE_ROWS, len(work))))
    for position in stale_index:
        published_date = parse_iso_date(work.at[position, "published"])
        if published_date is None:
            continue
        work.at[position, "published"] = (published_date - timedelta(days=STALE_SHIFT_DAYS)).isoformat()
    events.append(
        {
            "step": 5,
            "corruption_type": "stale_date",
            "description": f"Lui ngay xuat ban {STALE_SHIFT_DAYS} ngay.",
            "affected_rows": len(stale_index),
            "affected_paper_ids": work.loc[stale_index, "paper_id"].tolist(),
        }
    )

    # --- 6. Duplicate rows: nhan ban dong lam loang ngu canh ---
    duplicate_count = min(DUPLICATE_ROWS, len(work))
    duplicated = work.head(duplicate_count).copy()
    work = pd.concat([work, duplicated], ignore_index=True)
    events.append(
        {
            "step": 6,
            "corruption_type": "duplicate_rows",
            "description": "Nhan ban dong tao du lieu trung lap.",
            "affected_rows": duplicate_count,
            "affected_paper_ids": duplicated["paper_id"].tolist(),
        }
    )

    # --- 7. Dung lai text_for_embedding / age_days / summary_chars theo du lieu da bi lam ban ---
    work = rebuild_derived_columns(work, run_date)

    log = {
        "generated_at": run_date.isoformat(),
        "rows_before": rows_before,
        "rows_after": int(len(work)),
        "duplicate_paper_ids": int(work["paper_id"].duplicated().sum()),
        "blank_summary_rows": int((work["summary_chars"] == 0).sum()),
        "corruptions_applied": len(events),
        "events": events,
    }
    write_json(Path(output_log_path), log)
    return work.reset_index(drop=True)
