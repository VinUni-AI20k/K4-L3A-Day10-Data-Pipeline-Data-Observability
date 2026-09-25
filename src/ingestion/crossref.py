from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _format_date(date_data: Any) -> str:
    if not date_data:
        return "2026-01-01"
    if isinstance(date_data, dict):
        if "date-parts" in date_data and date_data["date-parts"]:
            parts = date_data["date-parts"][0]
            y = parts[0] if len(parts) > 0 else 2026
            m = parts[1] if len(parts) > 1 else 1
            d = parts[2] if len(parts) > 2 else 1
            return f"{y:04d}-{m:02d}-{d:02d}"
        if "date-time" in date_data:
            dt_str = str(date_data["date-time"])
            return dt_str[:10]
    return str(date_data)[:10]


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo qua record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        paper_id = item.get("DOI", "").strip()
        if not paper_id:
            continue

        raw_title = item.get("title", "")
        if isinstance(raw_title, list):
            raw_title = raw_title[0] if raw_title else ""
        title = normalize_whitespace(str(raw_title))

        raw_abstract = item.get("abstract", "") or ""
        clean_abstract = re.sub(r"<[^>]+>", " ", str(raw_abstract))
        summary = normalize_whitespace(clean_abstract)

        authors: list[str] = []
        for author in item.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            full_name = f"{given} {family}".strip() if (given or family) else author.get("name", "").strip()
            if full_name:
                authors.append(full_name)

        categories: list[str] = item.get("subject", []) or []
        primary_category = categories[0] if categories else "Uncategorized"

        published = _format_date(item.get("published"))
        updated = _format_date(item.get("created")) or published

        url = item.get("URL") or f"https://doi.org/{paper_id}"
        abs_url = url
        pdf_url = url
        comment = f"Crossref record {paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.
    Ho tro co che cuu ho Offline (Dual-Mode) khi 429 hoac loi mang.
    """
    payload: dict | None = None

    if settings.refresh_source:
        api_url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {
            "User-Agent": "Day10-DataObservabilityLab/1.0 (mailto:lab@example.com)"
        }
        try:
            resp = requests.get(api_url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                write_json(settings.paths.raw_api_response, payload)
        except Exception:
            payload = None

    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        elif settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        else:
            raise FileNotFoundError(
                f"Cannot fetch from Crossref API and local snapshot not found at {settings.paths.raw_api_response}"
            )

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    if not path.exists():
        return []
    data = read_json(path)
    if isinstance(data, dict) and "message" in data:
        return parse_crossref_payload(data)
    if isinstance(data, list):
        records: list[PaperRecord] = []
        for item in data:
            if isinstance(item, dict):
                records.append(PaperRecord(**item))
        return records
    return []
