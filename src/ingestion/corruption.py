from __future__ import annotations

import math
from pathlib import Path
import random
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json

DROP_LATEST_FRACTION = 0.20
BLANK_SUMMARY_FRACTION = 0.15
NOISE_FRACTION = 0.15
TRUNCATE_TITLE_FRACTION = 0.15
STALE_DATE_FRACTION = 0.40
DUPLICATE_FRACTION = 0.15

TRUNCATED_TITLE_LENGTH = 7
STALE_SHIFT_DAYS = 365
NOISE_TOKENS = ["#@!$%", "~~~", "lorem", "ipsum", "0xDEADBEEF", "<<null>>", "?????", "|||", "^^^", "asdfgh"]


def _pick_count(total: int, fraction: float) -> int:
    if total <= 0:
        return 0
    return min(total, max(1, round(total * fraction)))


def _inject_noise(text: str, rng: random.Random) -> str:
    words = text.split()
    noisy: list[str] = [rng.choice(NOISE_TOKENS), rng.choice(NOISE_TOKENS)]
    for position, word in enumerate(words):
        noisy.append(word)
        if position % 3 == 2:
            noisy.append(rng.choice(NOISE_TOKENS))
    return " ".join(noisy)


def _shift_published(value: str, days: int) -> str:
    shifted = pd.to_datetime(value, utc=True) - pd.Timedelta(days=days)
    return shifted.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_text_for_embedding(df: pd.DataFrame) -> pd.Series:
    published = pd.to_datetime(df["published"], utc=True).dt.strftime("%Y-%m-%d")
    return (
        "Title: " + df["title"] + "\n"
        + "Authors: " + df["authors_joined"] + "\n"
        + "Published: " + published + "\n"
        + "Categories: " + df["categories_joined"] + "\n"
        + "Summary: " + df["summary"]
    )


def _log_entry(corruption_type: str, description: str, paper_ids: list[str], **details: Any) -> dict[str, Any]:
    return {
        "type": corruption_type,
        "description": description,
        "affected_rows": len(paper_ids),
        "affected_paper_ids": paper_ids,
        **details,
    }


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path, seed: int = 42) -> pd.DataFrame:
    """Tiem 6 loai loi co kiem soat vao clean dataframe va ghi corruption log.

    Ham khong sua `df` dau vao; cung `seed` cho ra cung ket qua.
    """
    rng = random.Random(seed)
    corrupted = df.copy(deep=True).reset_index(drop=True)
    input_rows = len(corrupted)
    log_entries: list[dict[str, Any]] = []

    # 1. Drop latest records: mat 20% bai bao moi nhat (mo phong ingestion bo sot du lieu tuoi).
    published_dt = pd.to_datetime(corrupted["published"], utc=True)
    drop_count = math.ceil(input_rows * DROP_LATEST_FRACTION) if input_rows else 0
    drop_index = published_dt.sort_values(ascending=False).index[:drop_count]
    log_entries.append(
        _log_entry(
            "drop_latest_records",
            f"Drop {drop_count} ban ghi moi nhat ({DROP_LATEST_FRACTION:.0%}).",
            corrupted.loc[drop_index, "paper_id"].tolist(),
            dropped_published=corrupted.loc[drop_index, "published"].tolist(),
        )
    )
    corrupted = corrupted.drop(index=drop_index).reset_index(drop=True)

    # 2-4. Blank summary / inject noise / truncate title tren cac nhom dong rieng biet
    #      de moi loai loi co tac dong doc lap, de doi chieu.
    remaining = list(corrupted.index)
    rng.shuffle(remaining)
    blank_count = _pick_count(len(remaining), BLANK_SUMMARY_FRACTION)
    noise_count = _pick_count(len(remaining), NOISE_FRACTION)
    truncate_count = _pick_count(len(remaining), TRUNCATE_TITLE_FRACTION)
    blank_index = remaining[:blank_count]
    noise_index = remaining[blank_count : blank_count + noise_count]
    truncate_index = remaining[blank_count + noise_count : blank_count + noise_count + truncate_count]

    corrupted.loc[blank_index, "summary"] = ""
    log_entries.append(
        _log_entry(
            "blank_summary",
            f"Xoa trang summary cua {len(blank_index)} dong.",
            corrupted.loc[blank_index, "paper_id"].tolist(),
        )
    )

    for row in noise_index:
        corrupted.at[row, "summary"] = _inject_noise(corrupted.at[row, "summary"], rng)
    log_entries.append(
        _log_entry(
            "inject_noise",
            f"Chen ky tu rac vao summary cua {len(noise_index)} dong.",
            corrupted.loc[noise_index, "paper_id"].tolist(),
            noise_tokens=NOISE_TOKENS,
        )
    )

    original_titles = corrupted.loc[truncate_index, "title"].tolist()
    corrupted.loc[truncate_index, "title"] = corrupted.loc[truncate_index, "title"].str.slice(0, TRUNCATED_TITLE_LENGTH)
    log_entries.append(
        _log_entry(
            "truncate_title",
            f"Cat title cua {len(truncate_index)} dong xuong {TRUNCATED_TITLE_LENGTH} ky tu.",
            corrupted.loc[truncate_index, "paper_id"].tolist(),
            title_changes=[
                {"before": before, "after": after}
                for before, after in zip(original_titles, corrupted.loc[truncate_index, "title"], strict=True)
            ],
        )
    )

    # 5. Stale date: lui published ve 365 ngay truoc -> vuot nguong freshness 180 ngay.
    stale_index = sorted(rng.sample(list(corrupted.index), _pick_count(len(corrupted), STALE_DATE_FRACTION)))
    original_published = corrupted.loc[stale_index, "published"].tolist()
    corrupted.loc[stale_index, "published"] = [_shift_published(value, STALE_SHIFT_DAYS) for value in original_published]
    if "age_days" in corrupted.columns:
        corrupted.loc[stale_index, "age_days"] = corrupted.loc[stale_index, "age_days"] + STALE_SHIFT_DAYS
    log_entries.append(
        _log_entry(
            "stale_date",
            f"Lui published cua {len(stale_index)} dong ve {STALE_SHIFT_DAYS} ngay truoc.",
            corrupted.loc[stale_index, "paper_id"].tolist(),
            date_changes=[
                {"before": before, "after": after}
                for before, after in zip(original_published, corrupted.loc[stale_index, "published"], strict=True)
            ],
        )
    )

    # 6. Duplicate rows: nhan ban mot so dong (sau khi da bi lam ban) de pha unique paper_id.
    duplicate_index = sorted(rng.sample(list(corrupted.index), _pick_count(len(corrupted), DUPLICATE_FRACTION)))
    duplicates = corrupted.loc[duplicate_index].copy()
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    log_entries.append(
        _log_entry(
            "duplicate_rows",
            f"Nhan ban {len(duplicate_index)} dong.",
            duplicates["paper_id"].tolist(),
        )
    )

    # 7. Rebuild cac cot phu thuoc de loi "chay" xuong tan embedding.
    if "summary_chars" in corrupted.columns:
        corrupted["summary_chars"] = corrupted["summary"].str.len()
    corrupted["text_for_embedding"] = _build_text_for_embedding(corrupted)

    # 8. Ghi corruption log.
    write_json(
        Path(output_log_path),
        {
            "generated_at": now_utc().isoformat(),
            "seed": seed,
            "input_rows": input_rows,
            "output_rows": len(corrupted),
            "unique_paper_ids": int(corrupted["paper_id"].nunique()),
            "corruption_types": [entry["type"] for entry in log_entries],
            "corruptions": log_entries,
        },
    )
    return corrupted
