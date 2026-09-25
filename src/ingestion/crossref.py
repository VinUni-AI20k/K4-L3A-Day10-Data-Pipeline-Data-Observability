from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

_CROSSREF_WORKS_ENDPOINT = "https://api.crossref.org/works"


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


class _TextExtractor(HTMLParser):
    """Extract readable text from Crossref's JATS abstract markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(part) for part in value if part is not None)
    raw = unescape(str(value))
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        raw = " ".join(parser.parts)
    except Exception:
        raw = re.sub(r"<[^>]*>", " ", raw)
    return normalize_whitespace(unescape(raw))


def _crossref_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        candidate = value.strip()
        try:
            return date.fromisoformat(candidate[:10]).isoformat()
        except ValueError:
            return ""
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts") or value.get("date_parts")
    if parts and isinstance(parts, list) and parts[0]:
        try:
            year, *rest = [int(part) for part in parts[0]]
            month = rest[0] if rest else 1
            day = rest[1] if len(rest) > 1 else 1
            return date(year, month, day).isoformat()
        except (TypeError, ValueError):
            pass
    date_time = value.get("date-time") or value.get("date_time")
    if date_time:
        try:
            return datetime.fromisoformat(str(date_time).replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return ""
    return ""


def _first_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return _text(value)


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref's message.items into normalized paper records."""
    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    items = message.get("items", []) if isinstance(message, dict) else []
    if not isinstance(items, list):
        raise ValueError("Crossref payload must contain a message.items list.")

    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        paper_id = _text(item.get("DOI") or item.get("doi") or item.get("paper_id")).lower()
        title = _first_text(item, "title")
        if not paper_id or not title or paper_id in seen:
            continue
        abstract = _text(item.get("abstract") or item.get("summary"))
        authors: list[str] = []
        for author in item.get("author", item.get("authors", [])) or []:
            if isinstance(author, str):
                name = _text(author)
            elif isinstance(author, dict):
                name = _text(" ".join(str(author.get(key, "")) for key in ("given", "family") if author.get(key)))
                name = name or _text(author.get("name"))
            else:
                name = ""
            if name:
                authors.append(name)
        categories = item.get("subject", item.get("categories", [])) or []
        if isinstance(categories, str):
            categories = [categories]
        normalized_categories = list(dict.fromkeys(filter(None, (_text(value) for value in categories))))
        published = ""
        for date_key in ("published-print", "published-online", "published", "issued", "created"):
            published = _crossref_date(item.get(date_key))
            if published:
                break
        updated = _crossref_date(item.get("updated")) or _crossref_date(item.get("deposited")) or published
        url = _text(item.get("URL") or item.get("url")) or f"https://doi.org/{paper_id}"
        primary_category = _text(item.get("primary_category")) or (normalized_categories[0] if normalized_categories else "General")
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=abstract,
                authors=authors,
                categories=normalized_categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=_text(item.get("abs_url")) or url,
                pdf_url=_text(item.get("pdf_url")) or url,
                comment=_text(item.get("comment")),
            )
        )
        seen.add(paper_id)
    return records


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Crossref offline snapshot not found: {path}")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Crossref response snapshot must be a JSON object: {path}")
    return payload


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref metadata when requested; otherwise use the bundled snapshot.

    Network failures fall back to the untouched offline response snapshot. Both
    paths write the parsed records artifact so later stages use one contract.
    """
    raw_path = settings.paths.raw_api_response
    payload: dict[str, Any]
    if settings.refresh_source:
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
            "select": "DOI,title,abstract,author,subject,published-print,published-online,published,issued,created,updated,deposited,URL",
        }
        try:
            response = None
            for attempt in range(3):
                response = requests.get(_CROSSREF_WORKS_ENDPOINT, params=params, timeout=30)
                if response.status_code not in {429, 503, 502, 504}:
                    break
                if attempt < 2:
                    time.sleep(2**attempt)
            assert response is not None
            response.raise_for_status()
            payload = response.json()
            write_json(raw_path, payload)
        except (requests.RequestException, ValueError, json.JSONDecodeError):
            payload = _load_payload(raw_path)
    else:
        payload = _load_payload(raw_path)

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("Crossref payload contained no usable paper records.")
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the parsed raw snapshot, accepting either records or API payload JSON."""
    payload = read_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("message"), dict):
        return parse_crossref_payload(payload)
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON list: {path}")
    records: list[PaperRecord] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        records.extend(parse_crossref_payload({"message": {"items": [row]}}))
    return records
