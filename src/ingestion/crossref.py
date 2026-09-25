from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
import time
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


def _clean_abstract(raw: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", raw)
    return normalize_whitespace(cleaned)


def _parse_date(item: dict[str, Any]) -> str:
    published = item.get("published", {})
    if isinstance(published, dict):
        date_parts = published.get("date-parts", [])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            if len(parts) == 2:
                return f"{parts[0]:04d}-{parts[1]:02d}-01"
            if len(parts) == 1:
                return f"{parts[0]:04d}-01-01"

    created = item.get("created", {})
    if isinstance(created, dict) and "date-time" in created:
        return created["date-time"][:10]

    issued = item.get("issued", {})
    if isinstance(issued, dict):
        date_parts = issued.get("date-parts", [])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            if len(parts) == 2:
                return f"{parts[0]:04d}-{parts[1]:02d}-01"
            if len(parts) == 1:
                return f"{parts[0]:04d}-01-01"

    return datetime.now(UTC).strftime("%Y-%m-%d")


def _parse_authors(item: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    for a in item.get("author", []):
        if not isinstance(a, dict):
            continue
        given = a.get("given", "").strip()
        family = a.get("family", "").strip()
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)
        elif a.get("name"):
            authors.append(a["name"].strip())
    return authors


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload into list of PaperRecord."""
    message = payload.get("message", {})
    items = message.get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = item.get("DOI", "").strip()
        if not doi:
            continue

        raw_title = item.get("title", "")
        if isinstance(raw_title, list):
            title = " ".join(raw_title)
        else:
            title = str(raw_title)
        title = normalize_whitespace(title)

        raw_abstract = item.get("abstract", "")
        summary = _clean_abstract(str(raw_abstract)) if raw_abstract else ""

        authors = _parse_authors(item)

        categories = item.get("subject", [])
        if not isinstance(categories, list):
            categories = [str(categories)] if categories else []
        categories = [normalize_whitespace(str(c)) for c in categories if c]
        primary_category = categories[0] if categories else "General"

        published = _parse_date(item)

        created = item.get("created", {})
        if isinstance(created, dict) and "date-time" in created:
            updated = created["date-time"][:10]
        else:
            updated = published

        url = item.get("URL", f"https://doi.org/{doi}").strip()
        abs_url = url
        pdf_url = url

        for link in item.get("link", []):
            if isinstance(link, dict) and "pdf" in link.get("content-type", "").lower():
                pdf_url = link.get("URL", url).strip()
                break

        comment = f"Crossref record {doi}"

        records.append(
            PaperRecord(
                paper_id=doi,
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
    """Fetch records from Crossref API or load offline snapshot if unavailable."""
    records: list[PaperRecord] = []
    payload = None

    if settings.refresh_source or not settings.paths.raw_api_response.exists():
        url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {
            "User-Agent": "Day10-DataObservabilityLab/1.0 (mailto:student@lab.edu)"
        }
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=15)
                if response.status_code == 200:
                    payload = response.json()
                    write_json(settings.paths.raw_api_response, payload)
                    break
                if response.status_code in {429, 503}:
                    time.sleep(1.0 * (attempt + 1))
            except Exception:
                time.sleep(1.0)

    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        elif settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        else:
            raise RuntimeError(
                "Unable to fetch Crossref records and no raw snapshot found at data/raw/crossref_response.json."
            )

    records = parse_crossref_payload(payload)

    record_dicts = [asdict(r) for r in records]
    write_json(settings.paths.raw_records_json, record_dicts)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Read JSON snapshot and map each dict to `PaperRecord`."""
    data = read_json(path)
    if isinstance(data, dict) and "message" in data:
        return parse_crossref_payload(data)
    records: list[PaperRecord] = []
    for item in data:
        records.append(
            PaperRecord(
                paper_id=item["paper_id"],
                title=item["title"],
                summary=item["summary"],
                authors=item.get("authors", []),
                categories=item.get("categories", []),
                primary_category=item.get("primary_category", "General"),
                published=item["published"],
                updated=item.get("updated", item["published"]),
                abs_url=item.get("abs_url", ""),
                pdf_url=item.get("pdf_url", ""),
                comment=item.get("comment", ""),
            )
        )
    return records
