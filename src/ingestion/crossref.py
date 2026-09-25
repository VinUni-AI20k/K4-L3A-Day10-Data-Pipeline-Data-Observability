from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
import html
import json
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, write_json


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
    """Parse a Crossref API payload into normalized paper records.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in payload.get("message", {}).get("items", []):
        doi = normalize_whitespace(str(item.get("DOI", ""))).lower()
        titles = item.get("title") or []
        title = normalize_whitespace(str(titles[0] if isinstance(titles, list) and titles else titles))
        if not doi or not title or doi in seen:
            continue

        abstract = html.unescape(str(item.get("abstract") or ""))
        abstract = re.sub(r"<[^>]+>", " ", abstract)
        summary = normalize_whitespace(abstract)
        authors = []
        for author in item.get("author") or []:
            full_name = normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
            if full_name:
                authors.append(full_name)
        categories = [normalize_whitespace(str(value)) for value in item.get("subject") or []]
        categories = [value for value in categories if value]

        def extract_date(value: object) -> str:
            if not isinstance(value, dict):
                return ""
            parts = value.get("date-parts")
            if parts and parts[0]:
                date = list(parts[0]) + [1, 1]
                try:
                    return f"{int(date[0]):04d}-{int(date[1]):02d}-{int(date[2]):02d}"
                except (TypeError, ValueError):
                    return ""
            date_time = value.get("date-time")
            return str(date_time)[:10] if date_time else ""

        published = extract_date(item.get("published") or item.get("published-print") or item.get("created"))
        updated = extract_date(item.get("updated") or item.get("created")) or published
        url = normalize_whitespace(str(item.get("URL") or f"https://doi.org/{doi}"))
        pdf_url = url
        for link in item.get("link") or []:
            if "pdf" in str(link.get("content-type", "")).lower() and link.get("URL"):
                pdf_url = str(link["URL"])
                break
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=pdf_url,
                comment=f"Crossref record {doi}",
            )
        )
        seen.add(doi)
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records with retries and an offline snapshot fallback.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    snapshot = settings.paths.raw_api_response
    payload: dict | None = None
    if settings.refresh_source or not snapshot.exists():
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
            "select": "DOI,title,abstract,author,subject,published,created,URL,link",
        }
        for attempt in range(3):
            try:
                response = requests.get(
                    "https://api.crossref.org/works",
                    params=params,
                    headers={"User-Agent": "day10-data-observability-lab/1.0"},
                    timeout=20,
                )
                response.raise_for_status()
                payload = response.json()
                write_json(snapshot, payload)
                break
            except (requests.RequestException, ValueError):
                if attempt < 2:
                    time.sleep(2**attempt)
    if payload is None:
        if not snapshot.exists():
            raise RuntimeError("Crossref API failed and no offline snapshot is available.")
        payload = json.loads(snapshot.read_text(encoding="utf-8"))

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("Crossref payload did not contain any valid paper records.")
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load normalized records or parse a raw Crossref snapshot."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "message" in payload:
        return parse_crossref_payload(payload)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of raw records in {path}")
    return [PaperRecord(**item) for item in payload]
