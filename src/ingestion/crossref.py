from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from html import unescape
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


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
    """Parse a Crossref response into stable, pipeline-ready raw records."""
    if not isinstance(payload, dict):
        raise ValueError("Crossref payload must be a JSON object.")
    message = payload.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise ValueError("Crossref payload must contain message.items as a list.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        paper_id = _clean_text(item.get("DOI")).lower()
        title = _first_text(item.get("title"))
        if not paper_id or not title or paper_id in seen_ids:
            continue
        published = _publication_date(item)
        categories = _categories(item)
        doi_url = f"https://doi.org/{paper_id}"
        abs_url = _clean_text(item.get("URL")) or doi_url
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=_clean_text(item.get("abstract")),
                authors=_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=_updated_date(item, published),
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )
        seen_ids.add(paper_id)
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Load offline data, or refresh from Crossref with retry and fallback."""
    if not settings.refresh_source:
        return _records_from_snapshot(settings)

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": (
            "DOI,title,abstract,author,subject,published,published-print,"
            "published-online,issued,created,indexed,deposited,URL,link"
        ),
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "VinUni-Day10-Data-Observability-Lab/1.0 (educational use)",
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL, params=params, headers=headers, timeout=(5, 30)
            )
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise requests.HTTPError(
                    f"Crossref returned retryable status {response.status_code}", response=response
                )
            response.raise_for_status()
            payload = response.json()
            records = parse_crossref_payload(payload)
            if not records:
                raise ValueError("Crossref returned no valid records.")
            # Persist only after validation, so a bad response cannot destroy the snapshot.
            write_json(settings.paths.raw_api_response, payload)
            _save_records(settings.paths.raw_records_json, records)
            return records
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                retry_after = None
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    retry_after = exc.response.headers.get("Retry-After")
                try:
                    delay = min(float(retry_after), 10.0) if retry_after else 2**attempt
                except ValueError:
                    delay = 2**attempt
                time.sleep(delay)

    try:
        return _records_from_snapshot(settings)
    except (FileNotFoundError, ValueError) as fallback_error:
        raise RuntimeError(
            f"Crossref fetch failed ({last_error}) and the offline snapshot is unavailable or invalid."
        ) from fallback_error


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load and validate serialized ``PaperRecord`` objects from JSON."""
    if not path.exists():
        raise FileNotFoundError(f"Raw records file does not exist: {path}")
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON array: {path}")

    required_fields = {field.name for field in fields(PaperRecord)}
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} must be a JSON object.")
        missing = required_fields - item.keys()
        if missing:
            raise ValueError(f"Raw record at index {index} is missing fields: {sorted(missing)}")
        if not isinstance(item["authors"], list) or not isinstance(item["categories"], list):
            raise ValueError(f"Raw record at index {index} has invalid authors/categories fields.")

        values = {name: item[name] for name in required_fields}
        paper_id = _clean_text(values["paper_id"]).lower()
        title = _clean_text(values["title"])
        if not paper_id or not title:
            raise ValueError(f"Raw record at index {index} must have a non-empty paper_id and title.")
        if paper_id in seen_ids:
            raise ValueError(f"Duplicate paper_id in raw records: {paper_id}")
        values["paper_id"] = paper_id
        values["title"] = title
        values["authors"] = [_clean_text(value) for value in values["authors"] if _clean_text(value)]
        values["categories"] = [
            _clean_text(value) for value in values["categories"] if _clean_text(value)
        ]
        records.append(PaperRecord(**values))
        seen_ids.add(paper_id)
    return records


def _clean_text(value: Any) -> str:
    """Convert a Crossref text field to plain, normalized text."""
    if not isinstance(value, str):
        return ""
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", unescape(value)))


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        return _clean_text(value[0]) if value else ""
    return _clean_text(value)


def _date_from_parts(value: Any) -> str:
    try:
        parts = value["date-parts"][0]
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (KeyError, IndexError, TypeError, ValueError):
        return ""


def _date_from_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def _publication_date(item: dict[str, Any]) -> str:
    for key in ("published", "published-print", "published-online", "issued", "created"):
        value = item.get(key)
        parsed = _date_from_parts(value)
        if parsed:
            return parsed
        if isinstance(value, dict):
            parsed = _date_from_timestamp(value.get("date-time"))
            if parsed:
                return parsed
    return ""


def _updated_date(item: dict[str, Any], published: str) -> str:
    for key in ("indexed", "deposited", "created"):
        value = item.get(key)
        if isinstance(value, dict):
            parsed = _date_from_timestamp(value.get("date-time")) or _date_from_parts(value)
            if parsed:
                return parsed
    return published


def _authors(item: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(
            " ".join(
                part
                for part in (_clean_text(author.get("given")), _clean_text(author.get("family")))
                if part
            )
        )
        name = name or _clean_text(author.get("name"))
        if name and name not in result:
            result.append(name)
    return result


def _categories(item: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for subject in item.get("subject") or []:
        cleaned = _clean_text(subject)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _pdf_url(item: dict[str, Any], fallback: str) -> str:
    for link in item.get("link") or []:
        if not isinstance(link, dict):
            continue
        url = _clean_text(link.get("URL"))
        content_type = str(link.get("content-type", "")).lower()
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url
    return fallback


def _save_records(path: Path, records: list[PaperRecord]) -> None:
    write_json(path, [asdict(record) for record in records])


def _records_from_snapshot(settings: Settings) -> list[PaperRecord]:
    response_path = settings.paths.raw_api_response
    if response_path.exists():
        records = parse_crossref_payload(read_json(response_path))
        if not records:
            raise ValueError(f"Snapshot contains no valid Crossref records: {response_path}")
        _save_records(settings.paths.raw_records_json, records)
        return records
    if settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)
    raise FileNotFoundError(
        f"No Crossref snapshot exists at {response_path} or {settings.paths.raw_records_json}."
    )
