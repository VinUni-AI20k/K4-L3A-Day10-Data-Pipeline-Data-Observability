from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

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


def _strip_jats(text: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", text))


def _parse_date(date_parts: list) -> str:
    parts = date_parts[0] if date_parts else []
    year = parts[0] if len(parts) > 0 else 1970
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    records = []
    for item in payload.get("message", {}).get("items", []):
        doi = item.get("DOI", "").strip()
        if not doi:
            continue
        titles = item.get("title") or []
        title = _strip_jats(titles[0]) if titles else ""
        if not title:
            continue
        abstract = _strip_jats(item.get("abstract", ""))
        authors = [
            normalize_whitespace(f"{a.get('given', '')} {a.get('family', '')}").strip()
            for a in (item.get("author") or [])
        ]
        categories = [s for s in (item.get("subject") or []) if s]
        published = _parse_date(item.get("published", {}).get("date-parts", []))
        url = item.get("URL", f"https://doi.org/{doi}")
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=abstract,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=published,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {doi}",
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    raw_path = settings.paths.raw_api_response
    records_path = settings.paths.raw_records_json

    if not settings.refresh_source and records_path.exists():
        return load_raw_records(records_path)

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,created,URL",
    }
    payload = None
    for attempt in range(4):
        try:
            resp = requests.get(
                "https://api.crossref.org/works",
                params=params,
                timeout=30,
                headers={"User-Agent": "day10-lab/1.0"},
            )
            if resp.status_code in {429, 503}:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            payload = resp.json()
            break
        except requests.RequestException:
            if attempt == 3:
                break
            time.sleep(2 ** attempt)

    if payload is None and raw_path.exists():
        payload = read_json(raw_path)

    if payload is None:
        raise RuntimeError("Cannot fetch from Crossref API and no local snapshot found.")

    write_json(raw_path, payload)
    records = parse_crossref_payload(payload)
    write_json(records_path, [r.__dict__ for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    data = read_json(path)
    return [PaperRecord(**item) for item in data]
