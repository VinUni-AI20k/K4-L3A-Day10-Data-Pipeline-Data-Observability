from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.config import Settings
from core.utils import write_csv
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records


def repair_from_raw(settings: Settings, run_date: datetime) -> pd.DataFrame:
    """Rebuild the clean dataframe from raw records and write repaired artifacts.

    The same ``run_date`` rewrites ``repaired_clean_csv`` and ``repaired_clean_json``
    with identical bytes. Corrupted clean files are not read.
    """
    frame = build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), run_date)
    write_csv(frame, settings.paths.repaired_clean_csv)
    settings.paths.repaired_clean_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.repaired_clean_json.write_text(
        frame.to_json(orient="records", force_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return frame
