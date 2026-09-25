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


def parse_crossref_payload(payload: dict[str, Any]) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        paper_id = str(item.get("DOI") or "").strip()
        raw_title = item.get("title", [])
        if isinstance(raw_title, list):
            title = raw_title[0] if raw_title else ""
        else:
            title = str(raw_title or "")
        title = normalize_whitespace(re.sub(r"<[^>]+>", "", title))

        raw_abstract = str(item.get("abstract") or "")
        summary = normalize_whitespace(re.sub(r"<[^>]+>", "", raw_abstract))

        authors: list[str] = []
        for author_item in item.get("author", []):
            given = str(author_item.get("given", "")).strip()
            family = str(author_item.get("family", "")).strip()
            name = f"{given} {family}".strip() or str(author_item.get("name", "")).strip()
            if name:
                authors.append(name)

        categories = [str(s).strip() for s in item.get("subject", []) if str(s).strip()]
        primary_category = categories[0] if categories else "General"

        pub_dates = item.get("published", {}).get("date-parts", [[]])
        if not pub_dates or not pub_dates[0]:
            pub_dates = item.get("published-print", {}).get("date-parts", [[]])
        if not pub_dates or not pub_dates[0]:
            pub_dates = item.get("published-online", {}).get("date-parts", [[]])

        if pub_dates and pub_dates[0]:
            parts = pub_dates[0]
            year = int(parts[0]) if len(parts) >= 1 else 2026
            month = int(parts[1]) if len(parts) >= 2 else 1
            day = int(parts[2]) if len(parts) >= 3 else 1
            published = f"{year:04d}-{month:02d}-{day:02d}"
        else:
            created_dt = str(item.get("created", {}).get("date-time", ""))
            published = created_dt[:10] if len(created_dt) >= 10 else "2026-01-01"

        updated_dt = str(item.get("created", {}).get("date-time", ""))
        updated = updated_dt[:10] if len(updated_dt) >= 10 else published

        url = str(item.get("URL") or f"https://doi.org/{paper_id}")
        abs_url = url
        pdf_url = url
        comment = f"Crossref record {paper_id}"

        if not paper_id or not title:
            continue

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
    """Goi source API, luu raw response, parse thanh records co co che fallback offline."""
    if not settings.refresh_source and settings.paths.raw_records_json.exists():
        records = load_raw_records(settings.paths.raw_records_json)
        if records:
            return records

    url = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    try:
        if settings.refresh_source:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                write_json(settings.paths.raw_api_response, payload)
                records = parse_crossref_payload(payload)
                write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
                return records
    except Exception:
        pass

    # Offline fallback
    if settings.paths.raw_api_response.exists():
        payload = read_json(settings.paths.raw_api_response)
        records = parse_crossref_payload(payload)
        write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
        return records

    if settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)

    raise RuntimeError("Unable to load Crossref records from network or local snapshot.")


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh PaperRecord."""
    payload = read_json(path)
    if isinstance(payload, list):
        return [PaperRecord(**item) for item in payload]
    if isinstance(payload, dict):
        return parse_crossref_payload(payload)
    return []

