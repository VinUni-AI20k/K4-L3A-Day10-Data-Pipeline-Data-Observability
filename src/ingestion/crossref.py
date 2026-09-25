from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import html
import json
from pathlib import Path
import re

import requests

from core.config import Settings


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
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    records: list[PaperRecord] = []
    items = payload.get("message", {}).get("items", [])
    for item in items:
        paper_id = str(item.get("DOI", "")).strip()
        title = _clean_text((item.get("title") or [""])[0])
        summary = _clean_text(item.get("abstract", ""))
        if not paper_id or not title or not summary:
            continue

        authors = [
            _clean_text(" ".join(filter(None, (author.get("given"), author.get("family")))))
            for author in item.get("author", [])
        ]
        authors = [author for author in authors if author]
        categories = [_clean_text(value) for value in item.get("subject", [])]
        categories = [category for category in categories if category]
        published = _crossref_date(item.get("published"))
        updated = _crossref_date(item.get("updated")) or _crossref_date(item.get("created"))
        abs_url = str(item.get("URL") or f"https://doi.org/{paper_id}").strip()
        pdf_url = next(
            (
                str(link.get("URL")).strip()
                for link in item.get("link", [])
                if link.get("URL") and link.get("content-type") == "application/pdf"
            ),
            abs_url,
        )
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated or published,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    response_path = settings.paths.raw_api_response
    response_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict
    try:
        response = requests.get(
            "https://api.crossref.org/works",
            params={
                "query": settings.source_query,
                "filter": settings.source_filter,
                "rows": settings.max_results,
            },
            headers={"User-Agent": "day10-data-pipeline/0.1 (mailto:lab@example.com)"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        response_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except (requests.RequestException, ValueError):
        if not response_path.exists():
            raise
        payload = json.loads(response_path.read_text(encoding="utf-8"))

    records = parse_crossref_payload(payload)
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_records_json.write_text(
        json.dumps([record.__dict__ for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """TODO(student): doc JSON snapshot va map thanh `PaperRecord`."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [PaperRecord(**record) for record in payload]


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _crossref_date(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts", [[]])[0]
    if not parts:
        return ""
    try:
        year, month, day = (list(parts) + [1, 1])[:3]
        return date(int(year), int(month), int(day)).isoformat()
    except (TypeError, ValueError):
        return ""
