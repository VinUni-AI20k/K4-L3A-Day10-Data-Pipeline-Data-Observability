from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Any
import requests

from core.config import Settings
from core.utils import ensure_parent, normalize_whitespace, read_json, write_json


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


def _format_date_parts(date_parts: list[Any]) -> str:
    if not date_parts or not isinstance(date_parts, list):
        return "2026-01-01"
    first = date_parts[0]
    if not isinstance(first, list) or not first:
        return "2026-01-01"
    year = int(first[0]) if len(first) >= 1 else 2026
    month = int(first[1]) if len(first) >= 2 else 1
    day = int(first[2]) if len(first) >= 3 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text (loai bo tag HTML/JATS XML nhu <jats:p>) va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    items = payload.get("message", {}).get("items", [])
    if not items and "items" in payload:
        items = payload.get("items", [])

    records: list[PaperRecord] = []
    for item in items:
        doi = str(item.get("DOI", "")).strip()
        if not doi:
            continue

        raw_title = item.get("title", [])
        if isinstance(raw_title, list):
            title = raw_title[0] if raw_title else ""
        else:
            title = str(raw_title or "")
        title = normalize_whitespace(title)
        if not title:
            continue

        raw_abstract = item.get("abstract", "") or ""
        # Loai bo tat ca the XML/HTML nhu <jats:p>, </jats:p>, <jats:title>, etc.
        cleaned_abstract = re.sub(r"<[^>]+>", " ", raw_abstract)
        summary = normalize_whitespace(cleaned_abstract)
        if not summary:
            summary = title

        authors: list[str] = []
        for author in item.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            name = author.get("name", "").strip()
            full_name = f"{given} {family}".strip() if (given or family) else name
            if full_name:
                authors.append(normalize_whitespace(full_name))
        if not authors:
            authors = ["Anonymous Researcher"]

        subjects = item.get("subject", [])
        categories = [normalize_whitespace(s) for s in subjects if s] if isinstance(subjects, list) else []
        if not categories:
            categories = ["Artificial Intelligence"]
        primary_category = categories[0]

        pub_parts = item.get("published", {}).get("date-parts", [])
        published = _format_date_parts(pub_parts)

        created_dt = item.get("created", {}).get("date-time", "")
        updated = created_dt[:10] if created_dt else published

        url = item.get("URL", f"https://doi.org/{doi}")

        record = PaperRecord(
            paper_id=doi,
            title=title,
            summary=summary,
            authors=authors,
            categories=categories,
            primary_category=primary_category,
            published=published,
            updated=updated,
            abs_url=url,
            pdf_url=url,
            comment=f"Crossref record {doi}",
        )
        records.append(record)

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API (hoac fallback snapshot), luu raw response, parse thanh records.

    1. Neu settings.refresh_source = True, goi Crossref API voi query va filter.
    2. Neu API that bai (429, timeout, offline) hoac refresh_source = False, fallback doc snapshot data/raw/crossref_response.json.
    3. Luu raw response vao settings.paths.raw_api_response.
    4. Parse payload thanh list PaperRecord.
    5. Luu records vao settings.paths.raw_records_json.
    """
    payload: dict[str, Any] | None = None

    if settings.refresh_source:
        try:
            url = "https://api.crossref.org/works"
            params = {
                "query": settings.source_query,
                "filter": settings.source_filter,
                "rows": settings.max_results,
            }
            headers = {"User-Agent": "VinAI-Day10-RAG-Lab/1.0 (mailto:student@vinuni.edu.vn)"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                payload = response.json()
                write_json(settings.paths.raw_api_response, payload)
        except Exception:
            payload = None

    # Fallback doc snapshot local neu chua co payload
    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        elif settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        else:
            raise FileNotFoundError(f"Neither live API nor snapshot found at {settings.paths.raw_api_response}")

    records = parse_crossref_payload(payload)
    if not records and settings.paths.raw_records_json.exists():
        records = load_raw_records(settings.paths.raw_records_json)

    # Luu records json
    write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh list `PaperRecord`."""
    data = read_json(path)
    records = []
    for item in data:
        records.append(
            PaperRecord(
                paper_id=item["paper_id"],
                title=item["title"],
                summary=item["summary"],
                authors=item.get("authors", []),
                categories=item.get("categories", []),
                primary_category=item.get("primary_category", "General"),
                published=item.get("published", "2026-01-01"),
                updated=item.get("updated", "2026-01-01"),
                abs_url=item.get("abs_url", ""),
                pdf_url=item.get("pdf_url", ""),
                comment=item.get("comment", ""),
            )
        )
    return records

