from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from datetime import date
from html import unescape
import re
from pathlib import Path
import time

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

import requests


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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref work-list payload into normalized paper records."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = normalize_whitespace(str(item.get("DOI", ""))).lower()
        title = _first_text(item.get("title"))
        summary = _clean_abstract(str(item.get("abstract", "")))
        if not doi or not title or not summary:
            continue

        categories = [normalize_whitespace(str(value)) for value in item.get("subject", []) if str(value).strip()]
        published = _date_from_parts(item.get("published") or item.get("published-print") or item.get("published-online"))
        updated = _date_from_time(item.get("created", {}).get("date-time")) or published
        url = normalize_whitespace(str(item.get("URL") or f"https://doi.org/{doi}"))

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=_authors(item.get("author", [])),
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=_pdf_url(item, url),
                comment=f"Crossref record {doi}",
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records, falling back to the bundled offline snapshot."""
    payload: dict
    should_call_api = settings.refresh_source or not settings.paths.raw_api_response.exists()

    if should_call_api:
        try:
            payload = _fetch_crossref_payload(settings)
            write_json(settings.paths.raw_api_response, payload)
        except Exception:
            if not settings.paths.raw_api_response.exists():
                raise
            payload = read_json(settings.paths.raw_api_response)
    else:
        payload = read_json(settings.paths.raw_api_response)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load parsed raw records from a JSON snapshot."""
    payload = read_json(path)
    return [PaperRecord(**item) for item in payload]


def _fetch_crossref_payload(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": "DOI,title,abstract,author,subject,published,published-print,published-online,created,URL,link",
    }
    headers = {"User-Agent": "Day10DataPipelineLab/1.0 (mailto:student@example.com)"}
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(
                "https://api.crossref.org/works",
                params=params,
                headers=headers,
                timeout=20,
            )
            if response.status_code in {429, 503}:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(2**attempt)

    raise RuntimeError(f"Crossref fetch failed after retries: {last_error}")


def _first_text(value) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return normalize_whitespace(unescape(str(value)))


def _clean_abstract(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", unescape(value))
    return normalize_whitespace(without_tags)


def _authors(items) -> list[str]:
    authors: list[str] = []
    for item in items or []:
        given = normalize_whitespace(str(item.get("given", "")))
        family = normalize_whitespace(str(item.get("family", "")))
        name = normalize_whitespace(f"{given} {family}") or normalize_whitespace(str(item.get("name", "")))
        if name:
            authors.append(name)
    return authors


def _date_from_parts(value) -> str:
    parts = (value or {}).get("date-parts", [[]])[0]
    if not parts:
        return date.today().isoformat()
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    day = int(parts[2]) if len(parts) > 2 else 1
    return date(year, month, day).isoformat()


def _date_from_time(value) -> str | None:
    if not value:
        return None
    return str(value).split("T", maxsplit=1)[0]


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link", []) or []:
        content_type = str(link.get("content-type", "")).lower()
        if "pdf" in content_type and link.get("URL"):
            return normalize_whitespace(str(link["URL"]))
    return fallback
