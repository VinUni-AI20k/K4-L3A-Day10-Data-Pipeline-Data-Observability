from __future__ import annotations

import json
import random
import re
import string
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from core.utils import ensure_parent


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    """Rebuild text_for_embedding from the 5-line format used in cleaning."""
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row.get('authors_joined', '')}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row.get('categories_joined', '')}\n"
        f"Summary: {row['summary']}"
    )


def _inject_noise(text: str, rng: random.Random, num_chars: int = 8) -> str:
    """Inject random garbage characters into a text string."""
    noise = "".join(rng.choices(string.punctuation + "▓▒░█▌▐■□", k=num_chars))
    pos = rng.randint(0, max(0, len(text) - 1))
    return text[:pos] + noise + text[pos:]


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate 6 dang data corruption tren clean dataframe.

    1. Drop latest records (~20% bài mới nhất)
    2. Blank summary (gán "", không gán None)
    3. Inject noise vào summary (ký tự rác)
    4. Truncate title (< 8 ký tự)
    5. Stale date (lùi published > 180 ngày + cập nhật age_days)
    6. Duplicate rows
    Sau đó rebuild text_for_embedding và ghi corruption_log.json.
    Không sửa df gốc (dùng df.copy()).
    """
    rng = random.Random(42)
    result = df.copy()

    # Chuẩn bị run_date để tính age_days
    run_date = datetime.now().date()

    log: list[dict] = []

    # ── 1. Drop latest records (~20% bài mới nhất) ──────────────────────────
    n_drop = max(1, int(len(result) * 0.20))
    # Sort theo published giảm dần, lấy n_drop bài đầu (mới nhất)
    sorted_idx = result.sort_values("published", ascending=False).index.tolist()
    drop_ids = sorted_idx[:n_drop]
    dropped_paper_ids = result.loc[drop_ids, "paper_id"].tolist()
    result = result.drop(index=drop_ids).reset_index(drop=True)
    log.append({
        "type": "drop_latest",
        "num_rows": n_drop,
        "paper_ids": dropped_paper_ids,
    })

    # ── 2. Blank summary ─────────────────────────────────────────────────────
    n_blank = max(1, int(len(result) * 0.15))
    blank_idx = rng.sample(range(len(result)), n_blank)
    blank_paper_ids = result.iloc[blank_idx]["paper_id"].tolist()
    result.loc[blank_idx, "summary"] = ""
    result.loc[blank_idx, "summary_chars"] = 0
    log.append({
        "type": "blank_summary",
        "num_rows": n_blank,
        "paper_ids": blank_paper_ids,
    })

    # ── 3. Inject noise into summary ─────────────────────────────────────────
    remaining_idx = [i for i in range(len(result)) if result.iloc[i]["summary"] != ""]
    n_noise = max(1, int(len(remaining_idx) * 0.20))
    noise_idx = rng.sample(remaining_idx, min(n_noise, len(remaining_idx)))
    noise_paper_ids = result.iloc[noise_idx]["paper_id"].tolist()
    for i in noise_idx:
        result.at[i, "summary"] = _inject_noise(result.at[i, "summary"], rng)
    log.append({
        "type": "inject_noise",
        "num_rows": len(noise_idx),
        "paper_ids": noise_paper_ids,
    })

    # ── 4. Truncate title (< 8 ký tự) ────────────────────────────────────────
    n_trunc = max(1, int(len(result) * 0.15))
    trunc_candidates = list(range(len(result)))
    trunc_idx = rng.sample(trunc_candidates, min(n_trunc, len(trunc_candidates)))
    trunc_paper_ids = result.iloc[trunc_idx]["paper_id"].tolist()
    for i in trunc_idx:
        result.at[i, "title"] = result.at[i, "title"][:rng.randint(3, 7)]
    log.append({
        "type": "truncate_title",
        "num_rows": len(trunc_idx),
        "paper_ids": trunc_paper_ids,
    })

    # ── 5. Stale date (lùi published > 180 ngày) ─────────────────────────────
    n_stale = max(1, int(len(result) * 0.20))
    stale_idx = rng.sample(range(len(result)), min(n_stale, len(result)))
    stale_paper_ids = result.iloc[stale_idx]["paper_id"].tolist()
    for i in stale_idx:
        try:
            pub = datetime.strptime(result.at[i, "published"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pub = run_date
        stale_pub = pub - timedelta(days=rng.randint(181, 365))
        result.at[i, "published"] = stale_pub.strftime("%Y-%m-%d")
        result.at[i, "age_days"] = (run_date - stale_pub).days
    log.append({
        "type": "stale_date",
        "num_rows": len(stale_idx),
        "paper_ids": stale_paper_ids,
    })

    # ── 6. Duplicate rows ────────────────────────────────────────────────────
    n_dup = max(1, int(len(result) * 0.10))
    dup_idx = rng.sample(range(len(result)), min(n_dup, len(result)))
    dup_rows = result.iloc[dup_idx].copy()
    dup_paper_ids = dup_rows["paper_id"].tolist()
    result = pd.concat([result, dup_rows], ignore_index=True)
    log.append({
        "type": "duplicate_rows",
        "num_rows": len(dup_idx),
        "paper_ids": dup_paper_ids,
    })

    # ── 7. Rebuild text_for_embedding ────────────────────────────────────────
    result["text_for_embedding"] = result.apply(_rebuild_text_for_embedding, axis=1)

    # ── 8. Ghi corruption log ────────────────────────────────────────────────
    output_log_path = Path(output_log_path)
    ensure_parent(output_log_path)
    output_log_path.write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    total_corrupted = sum(e["num_rows"] for e in log)
    print(f"Corrupted {total_corrupted} dòng")

    return result
