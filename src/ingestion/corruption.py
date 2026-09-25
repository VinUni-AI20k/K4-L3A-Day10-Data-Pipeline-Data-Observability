from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import random
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json

# Seed co dinh: moi lan chay lai phai tai tao dung cung mot tap loi, neu khong
# thi so lieu trong corruption_report.md se khong doi chieu duoc giua cac lan chay.
CORRUPTION_SEED = 20261010
MIN_ROWS = 5

DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_RATIO = 0.20
NOISE_RATIO = 0.25
TRUNCATE_TITLE_RATIO = 0.20
STALE_DATE_RATIO = 0.35
DUPLICATE_RATIO = 0.15

STALE_DATE_SHIFT_DAYS = 365
TRUNCATED_TITLE_LENGTH = 7  # < 8 ky tu theo yeu cau cua de bai
NOISE_SNIPPET = "%%% <<<garbled-ocr>>> ?????? zzzz 0x00 ### lorem-noise-42"


def _affected_count(ratio: float, total: int) -> int:
    """So dong bi tac dong, luon it nhat 1 dong va khong vuot qua total."""
    if total <= 0:
        return 0
    return max(1, min(total, int(round(ratio * total))))


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    """Ghep lai `text_for_embedding` theo dung format cua ingestion/cleaning.py.

    Phai rebuild sau khi lam ban, neu khong ChromaDB van index text sach va
    khong the quan sat duoc muc do suy giam cua retrieval.
    """
    return (
        "Title: "
        f"{row['title']}\n"
        "Authors: "
        f"{row['authors_joined']}\n"
        "Published: "
        f"{row['published']}\n"
        "Categories: "
        f"{row['categories_joined']}\n"
        "Summary: "
        f"{row['summary']}"
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Tiem 6 kich ban data corruption vao cleaned dataframe.

    Cac kich ban: drop latest records, blank summary, inject noise, truncate title,
    stale published date, duplicate rows. Tra ve dataframe da bi lam ban va ghi
    nhat ky chi tiet (tung scenario + paper_id bi tac dong) ra `output_log_path`.
    """
    if df is None or df.empty:
        raise ValueError("Cleaned dataframe is empty; nothing to corrupt.")
    if len(df) < MIN_ROWS:
        raise ValueError(f"Need at least {MIN_ROWS} rows to run the corruption suite, got {len(df)}.")

    working = df.copy().reset_index(drop=True)
    input_rows = len(working)
    scenarios: list[dict[str, Any]] = []

    # --- 1. Drop latest records: mo phong su co mat du lieu tuoi ---------------
    published = pd.to_datetime(working["published"], errors="coerce")
    newest_first = published.sort_values(ascending=False, kind="mergesort").index.tolist()
    drop_positions = newest_first[: _affected_count(DROP_LATEST_RATIO, input_rows)]
    dropped_ids = working.loc[drop_positions, "paper_id"].tolist()
    dropped_dates = working.loc[drop_positions, "published"].tolist()
    working = working.drop(index=drop_positions).reset_index(drop=True)
    scenarios.append(
        {
            "name": "drop_latest_records",
            "description": f"Xoa {len(dropped_ids)} ban ghi moi nhat (~{DROP_LATEST_RATIO:.0%} corpus).",
            "rows_affected": len(dropped_ids),
            "paper_ids": dropped_ids,
            "details": {"dropped_published_dates": dropped_dates},
        }
    )

    remaining = len(working)
    rng = random.Random(CORRUPTION_SEED)

    # Ba loi tren truong text duoc chia tach roi nhau de log doc duoc ro rang.
    text_pool = list(range(remaining))
    rng.shuffle(text_pool)

    def take(ratio: float) -> list[int]:
        count = min(_affected_count(ratio, remaining), len(text_pool))
        picked = [text_pool.pop() for _ in range(count)]
        return sorted(picked)

    blank_positions = take(BLANK_SUMMARY_RATIO)
    noise_positions = take(NOISE_RATIO)
    truncate_positions = take(TRUNCATE_TITLE_RATIO)
    # Stale date va duplicate tac dong len chieu khac (ngay thang / so dong)
    # nen duoc boc doc lap, co the trung voi cac loi text o tren.
    stale_positions = sorted(rng.sample(range(remaining), _affected_count(STALE_DATE_RATIO, remaining)))
    duplicate_positions = sorted(rng.sample(range(remaining), _affected_count(DUPLICATE_RATIO, remaining)))

    # --- 2. Blank summary: mo phong loi cao du lieu tra ve rong ---------------
    blanked_ids = working.loc[blank_positions, "paper_id"].tolist()
    working.loc[blank_positions, "summary"] = ""
    scenarios.append(
        {
            "name": "blank_summary",
            "description": f"Xoa trang summary cua {len(blank_positions)} dong (vi pham GX summary_length >= 30).",
            "rows_affected": len(blank_positions),
            "paper_ids": blanked_ids,
            "details": {"summary_chars_after": 0},
        }
    )

    # --- 3. Inject noise: nhieu ky tu rac, van qua duoc schema check ----------
    noise_ids = working.loc[noise_positions, "paper_id"].tolist()
    for position in noise_positions:
        working.at[position, "summary"] = f"{working.at[position, 'summary']} {NOISE_SNIPPET}"
    scenarios.append(
        {
            "name": "inject_noise",
            "description": (
                f"Chen chuoi rac vao summary cua {len(noise_positions)} dong. "
                "Day la silent failure: do dai van hop le nen GX khong bat duoc."
            ),
            "rows_affected": len(noise_positions),
            "paper_ids": noise_ids,
            "details": {"noise_snippet": NOISE_SNIPPET},
        }
    )

    # --- 4. Truncate title: tieu de cut ngan duoi 8 ky tu ---------------------
    truncated_ids = working.loc[truncate_positions, "paper_id"].tolist()
    truncated_titles: list[dict[str, str]] = []
    for position in truncate_positions:
        before = str(working.at[position, "title"])
        after = before[:TRUNCATED_TITLE_LENGTH].strip()
        working.at[position, "title"] = after
        truncated_titles.append({"paper_id": working.at[position, "paper_id"], "before": before, "after": after})
    scenarios.append(
        {
            "name": "truncate_title",
            "description": (
                f"Cat tieu de cua {len(truncate_positions)} dong xuong <{TRUNCATED_TITLE_LENGTH + 1} ky tu, "
                "pha vo buoc lookup theo title trong retrieval/qa.py."
            ),
            "rows_affected": len(truncate_positions),
            "paper_ids": truncated_ids,
            "details": {"titles": truncated_titles},
        }
    )

    # --- 5. Stale date: lui ngay xuat ban de pha Freshness SLA ----------------
    stale_ids = working.loc[stale_positions, "paper_id"].tolist()
    shifted_dates: list[dict[str, str]] = []
    for position in stale_positions:
        original = pd.to_datetime(working.at[position, "published"], errors="coerce")
        if pd.isna(original):
            continue
        shifted = (original - timedelta(days=STALE_DATE_SHIFT_DAYS)).strftime("%Y-%m-%d")
        shifted_dates.append(
            {
                "paper_id": working.at[position, "paper_id"],
                "before": str(working.at[position, "published"]),
                "after": shifted,
            }
        )
        working.at[position, "published"] = shifted
        if "age_days" in working.columns:
            working.at[position, "age_days"] = int(working.at[position, "age_days"]) + STALE_DATE_SHIFT_DAYS
    scenarios.append(
        {
            "name": "stale_date",
            "description": (
                f"Lui published cua {len(shifted_dates)} dong lai {STALE_DATE_SHIFT_DAYS} ngay "
                "de day stale_ratio vuot nguong Freshness SLA 25%."
            ),
            "rows_affected": len(shifted_dates),
            "paper_ids": stale_ids,
            "details": {"shift_days": STALE_DATE_SHIFT_DAYS, "dates": shifted_dates},
        }
    )

    # --- 6. Duplicate rows: pha rang buoc paper_id unique ---------------------
    duplicated_ids = working.loc[duplicate_positions, "paper_id"].tolist()
    duplicates = working.loc[duplicate_positions].copy()
    working = pd.concat([working, duplicates], ignore_index=True)
    scenarios.append(
        {
            "name": "duplicate_rows",
            "description": f"Nhan ban {len(duplicate_positions)} dong (vi pham GX paper_id_unique).",
            "rows_affected": len(duplicate_positions),
            "paper_ids": duplicated_ids,
            "details": {"rows_added": len(duplicate_positions)},
        }
    )

    # --- Dong bo lai cac cot phai sinh --------------------------------------
    if "summary_chars" in working.columns:
        working["summary_chars"] = working["summary"].astype(str).str.len()
    working["text_for_embedding"] = working.apply(_rebuild_text_for_embedding, axis=1)
    working = working.reset_index(drop=True)

    log = {
        "generated_at": now_utc().isoformat(),
        "seed": CORRUPTION_SEED,
        "input_rows": input_rows,
        "output_rows": len(working),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "totals": {
            "rows_dropped": len(dropped_ids),
            "rows_added": len(duplicate_positions),
            "unique_paper_ids": int(working["paper_id"].nunique()),
            "blank_summaries": int((working["summary"].astype(str).str.len() == 0).sum()),
            "duplicated_paper_ids": int(len(working) - working["paper_id"].nunique()),
        },
    }
    write_json(Path(output_log_path), log)
    return working
