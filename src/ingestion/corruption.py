from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Simulate 6 dang data corruption thuc te:
    1. Drop latest records: Bo roi cac bai bao moi nhat (mat du lieu tuoi).
    2. Blank summary: Xoa trang phan tom tat o mot so dong (thieu thong tin).
    3. Inject text noise: Chen cac chuoi ky tu rac vo nghia vao summary.
    4. Truncate title: Cat ngan tieu de bai bao xuong duoi 10 ky tu.
    5. Stale date: Doi ngay xuat ban ve 5 nam truoc (vi pham Freshness SLA).
    6. Duplicate rows: Nhan doi mot so dong de tao ban ghi trung lap (vi pham Uniqueness).

    Rebuild text_for_embedding va ghi log chi tiet vao output_log_path.
    """
    cdf = df.copy()
    initial_count = len(cdf)

    # 1. Drop latest records: Bo 4 bai bao moi nhat bao gom 10.1145/3637528.3671804 (va ban ghi lien quan)
    drop_candidates = {"10.1145/3637528.3671804", "10.1145/3637528.3671816", "10.1145/3637528.3671812", "10.1145/3637528.3671808"}
    dropped_mask = cdf["paper_id"].isin(drop_candidates)
    dropped_paper_ids = cdf[dropped_mask]["paper_id"].tolist()
    cdf = cdf[~dropped_mask].copy().reset_index(drop=True)

    # 2. Blank summary o bai 10.1145/3637528.3671801 va them 2 bai khac
    blank_targets = ["10.1145/3637528.3671801", "10.1145/3637528.3671813"]
    blank_paper_ids = []
    for pid in blank_targets:
        idx_match = cdf[cdf["paper_id"] == pid].index
        for idx in idx_match:
            cdf.loc[idx, "summary"] = ""
            cdf.loc[idx, "summary_chars"] = 0
            blank_paper_ids.append(pid)
    # Neu con it, them 1 dong nua
    if len(blank_paper_ids) < 3 and len(cdf) > 2:
        cdf.loc[2, "summary"] = ""
        cdf.loc[2, "summary_chars"] = 0
        blank_paper_ids.append(cdf.loc[2, "paper_id"])

    # 3. Inject text noise vao bai 10.1145/3637528.3671805 va them 2 bai khac
    noise_str = " ### GARBAGE NOISE %$#@! CORRUPTED FRAGMENT 987654321 ### "
    noise_targets = ["10.1145/3637528.3671805", "10.1145/3637528.3671817"]
    noise_paper_ids = []
    for pid in noise_targets:
        idx_match = cdf[cdf["paper_id"] == pid].index
        for idx in idx_match:
            cdf.loc[idx, "summary"] = noise_str + str(cdf.loc[idx, "summary"])
            cdf.loc[idx, "summary_chars"] = len(cdf.loc[idx, "summary"])
            noise_paper_ids.append(pid)

    # 4. Truncate title duoi 10 ky tu
    trunc_targets = ["10.1145/3637528.3671802", "10.1145/3637528.3671814"]
    trunc_paper_ids = []
    for pid in trunc_targets:
        idx_match = cdf[cdf["paper_id"] == pid].index
        for idx in idx_match:
            cdf.loc[idx, "title"] = "Draft..."
            trunc_paper_ids.append(pid)

    # 5. Stale date: Lui ngay xuat ban ve 5 nam truoc o 10 dong (bao gom bai 10.1145/3637528.3671803)
    stale_count = min(10, len(cdf))
    stale_paper_ids = cdf.iloc[:stale_count]["paper_id"].tolist()
    for idx in range(stale_count):
        curr_pub = str(cdf.loc[idx, "published"])
        if len(curr_pub) >= 4 and curr_pub[:4].isdigit():
            old_year = int(curr_pub[:4]) - 5
            cdf.loc[idx, "published"] = f"{old_year}{curr_pub[4:]}"
        else:
            cdf.loc[idx, "published"] = "2021-01-01"
        if "age_days" in cdf.columns:
            cdf.loc[idx, "age_days"] = int(cdf.loc[idx, "age_days"]) + 1825

    # 6. Duplicate rows: Nhan doi 2 dong dau vao cuoi de tao trung lap
    dup_count = min(2, len(cdf))
    dup_rows = cdf.iloc[:dup_count].copy()
    dup_paper_ids = dup_rows["paper_id"].tolist()
    cdf = pd.concat([cdf, dup_rows], ignore_index=True)

    # Rebuild text_for_embedding cho toan bo cac dong
    for idx in range(len(cdf)):
        title = cdf.loc[idx, "title"]
        authors = cdf.loc[idx, "authors_joined"] if "authors_joined" in cdf.columns else ""
        published = cdf.loc[idx, "published"]
        categories = cdf.loc[idx, "categories_joined"] if "categories_joined" in cdf.columns else ""
        summary = cdf.loc[idx, "summary"]
        cdf.loc[idx, "text_for_embedding"] = f"""Title: {title}
Authors: {authors}
Published: {published}
Categories: {categories}
Summary: {summary}""".strip()

    # Ghi log corruption
    log_data: dict[str, Any] = {
        "timestamp": now_utc().isoformat(),
        "initial_rows": initial_count,
        "corrupted_rows": len(cdf),
        "scenarios": [
            {
                "name": "drop_latest_records",
                "description": "Dropped latest papers to simulate ingestion data loss",
                "affected_count": len(dropped_paper_ids),
                "paper_ids": dropped_paper_ids,
            },
            {
                "name": "blank_summary",
                "description": "Blanked summaries to simulate web scraping / parsing failure",
                "affected_count": len(blank_paper_ids),
                "paper_ids": blank_paper_ids,
            },
            {
                "name": "inject_noise",
                "description": "Injected random text noise into summaries",
                "affected_count": len(noise_paper_ids),
                "paper_ids": noise_paper_ids,
            },
            {
                "name": "truncate_title",
                "description": "Truncated paper titles below 10 characters",
                "affected_count": len(trunc_paper_ids),
                "paper_ids": trunc_paper_ids,
            },
            {
                "name": "stale_date",
                "description": "Rewound published dates back 5 years to violate Freshness SLA",
                "affected_count": len(stale_paper_ids),
                "paper_ids": stale_paper_ids,
            },
            {
                "name": "duplicate_rows",
                "description": "Duplicated rows to violate uniqueness constraint in ChromaDB and GX",
                "affected_count": len(dup_paper_ids),
                "paper_ids": dup_paper_ids,
            },
        ],
    }

    target = Path(output_log_path)
    write_json(target, log_data)
    return cdf

