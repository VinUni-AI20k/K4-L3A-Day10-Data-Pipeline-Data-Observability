from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date
from html import unescape
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_MARKUP_RE = re.compile(r"<[^>]+>")


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
    """Parse a Crossref response into the stable raw-record contract.

    Crossref fields are intentionally defensive here: live records frequently omit
    abstracts, contain JATS markup, or use one of several date fields.
    """

    def text(value: Any) -> str:
        if isinstance(value, list):
            value = value[0] if value else ""
        return normalize_whitespace(unescape(_MARKUP_RE.sub(" ", str(value or ""))))

    def crossref_date(item: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = item.get(key)
            if not isinstance(value, dict):
                continue
            parts = value.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                year = int(parts[0][0])
                month = int(parts[0][1]) if len(parts[0]) > 1 else 1
                day = int(parts[0][2]) if len(parts[0]) > 2 else 1
                try:
                    return date(year, month, day).isoformat()
                except ValueError:
                    continue
            timestamp = value.get("date-time")
            if timestamp:
                return str(timestamp)[:10]
        return ""

    items = payload.get("message", {}).get("items", [])
    if not isinstance(items, list):
        raise ValueError("Invalid Crossref payload: message.items must be a list.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        paper_id = text(item.get("DOI")).lower()
        title = text(item.get("title"))
        summary = text(item.get("abstract"))
        if not paper_id or not title or not summary or paper_id in seen_ids:
            continue

        authors: list[str] = []
        for author in item.get("author") or []:
            if not isinstance(author, dict):
                continue
            name = normalize_whitespace(
                " ".join(str(author.get(part) or "") for part in ("given", "family"))
            )
            if name:
                authors.append(name)

        categories = [text(subject) for subject in item.get("subject") or []]
        categories = list(dict.fromkeys(category for category in categories if category))
        published = crossref_date(
            item,
            "published",
            "published-online",
            "published-print",
            "issued",
            "created",
        )
        updated = crossref_date(item, "updated", "indexed", "deposited", "created") or published
        if not published:
            continue

        abs_url = text(item.get("URL")) or f"https://doi.org/{paper_id}"
        pdf_url = ""
        for link in item.get("link") or []:
            if not isinstance(link, dict):
                continue
            if "pdf" in str(link.get("content-type", "")).lower():
                pdf_url = text(link.get("URL"))
                break
        pdf_url = pdf_url or abs_url

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=f"Crossref record {paper_id}",
            )
        )
        seen_ids.add(paper_id)
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Load Crossref data in live or offline mode and preserve raw artifacts.

    Offline mode is the default for a reproducible lab run.  When live refresh is
    requested, transient HTTP/network failures fall back to the bundled snapshot.
    """
    payload: dict[str, Any] | None = None
    last_error: Exception | None = None

    if settings.refresh_source:
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
            "sort": "published",
            "order": "desc",
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "VinUni-Day10-Data-Observability-Lab/1.0",
        }
        for attempt in range(3):
            try:
                response = requests.get(
                    CROSSREF_WORKS_URL,
                    params=params,
                    headers=headers,
                    timeout=(5, 30),
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(
                        f"Crossref returned retryable status {response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                candidate = response.json()
                records = parse_crossref_payload(candidate)
                if not records:
                    raise ValueError("Crossref returned no usable records.")
                payload = candidate
                break
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)

    if payload is None:
        if not settings.paths.raw_api_response.exists():
            reason = f" Last live error: {last_error}" if last_error else ""
            raise FileNotFoundError(
                f"Offline Crossref snapshot not found at {settings.paths.raw_api_response}.{reason}"
            )
        payload = read_json(settings.paths.raw_api_response)

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("The Crossref source contains no usable records.")
    if settings.refresh_source:
        write_json(settings.paths.raw_api_response, payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a parsed-record snapshot and validate its top-level shape."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Raw record snapshot must contain a JSON list: {path}")
    allowed = {field.name for field in fields(PaperRecord)}
    records: list[PaperRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} is not an object.")
        values = {key: item.get(key) for key in allowed}
        values["authors"] = list(values.get("authors") or [])
        values["categories"] = list(values.get("categories") or [])
        for key in allowed - {"authors", "categories"}:
            values[key] = str(values.get(key) or "")
        records.append(PaperRecord(**values))
    return records
