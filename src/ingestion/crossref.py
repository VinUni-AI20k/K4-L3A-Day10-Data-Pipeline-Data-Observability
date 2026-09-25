from __future__ import annotations

from dataclasses import asdict, dataclass
import html
import json
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_RETRY_STATUS_CODES = {429, 503}
_DOI_PREFIX = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)
_MARKUP = re.compile(r"<[^>]+>")


class CrossrefUnavailable(RuntimeError):
    """Crossref API is unreachable, rate-limited, or returned no usable items."""


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
    """Parse a Crossref works payload into normalized paper records."""
    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        record = _record_from_item(item)
        if record is None or record.paper_id in seen:
            continue
        seen.add(record.paper_id)
        records.append(record)
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref works, or read the local snapshot when refresh is off.

    The default path only reads ``data/raw/crossref_response.json`` and does not
    rewrite raw artifacts. ``REFRESH_SOURCE=1`` calls the API, retries 429/503,
    and falls back to that snapshot without replacing it when the call fails.
    """
    if not settings.refresh_source:
        return parse_crossref_payload(_read_snapshot(settings))

    try:
        raw_text = _fetch_crossref_text(settings)
    except CrossrefUnavailable:
        payload = _read_snapshot(settings)
    else:
        _write_verbatim(settings.paths.raw_api_response, raw_text)
        payload = json.loads(raw_text)

    records = parse_crossref_payload(payload)
    if not records:
        records = parse_crossref_payload(_read_snapshot(settings))
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a JSON list of paper records."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list of paper records: {path}")
    return [PaperRecord(**item) for item in payload]


def _fetch_crossref_text(settings: Settings) -> str:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "K4A-DAY10-DALAB/1.0 (mailto:lab@example.com)",
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params=params,
                headers=headers,
                timeout=15,
            )
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
            continue

        if response.status_code in _RETRY_STATUS_CODES:
            last_error = CrossrefUnavailable(f"Crossref HTTP {response.status_code}")
            time.sleep(0.5 * (attempt + 1))
            continue

        try:
            response.raise_for_status()
            raw_text = response.text
            payload = json.loads(raw_text)
        except (requests.RequestException, ValueError, AttributeError) as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
            continue

        items = payload.get("message", {}).get("items") if isinstance(payload, dict) else None
        if not items:
            raise CrossrefUnavailable("Crossref returned no works.")
        return raw_text

    raise CrossrefUnavailable(str(last_error) if last_error else "Crossref request failed.")


def _write_verbatim(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_snapshot(settings: Settings) -> dict:
    path = settings.paths.raw_api_response
    if not path.exists():
        raise CrossrefUnavailable(f"Offline snapshot not found: {path}")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise CrossrefUnavailable(f"Offline snapshot is not a Crossref payload: {path}")
    return payload


def _record_from_item(item: dict) -> PaperRecord | None:
    paper_id = _normalize_doi(str(item.get("DOI") or ""))
    title = _normalize_title(item.get("title"))
    summary = _strip_markup(str(item.get("abstract") or ""))
    if not paper_id or not title or not summary:
        return None

    authors = _authors(item.get("author"))
    categories = _categories(item.get("subject"))
    published = _published_date(item)
    updated = _updated_date(item) or published
    abs_url = normalize_whitespace(str(item.get("URL") or "")) or f"https://doi.org/{paper_id}"
    pdf_url = _pdf_url(item) or abs_url
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        summary=summary,
        authors=authors,
        categories=categories,
        primary_category=categories[0] if categories else "",
        published=published,
        updated=updated,
        abs_url=abs_url,
        pdf_url=pdf_url,
        comment=f"Crossref record {paper_id}",
    )


def _normalize_doi(value: str) -> str:
    doi = _DOI_PREFIX.sub("", normalize_whitespace(value))
    return doi.strip().strip(".")


def _normalize_title(value: object) -> str:
    if isinstance(value, list):
        if not value:
            return ""
        return normalize_whitespace(str(value[0]))
    if value is None:
        return ""
    return normalize_whitespace(str(value))


def _strip_markup(value: str) -> str:
    text = html.unescape(value or "")
    text = _MARKUP.sub(" ", text)
    return normalize_whitespace(text)


def _authors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for author in value:
        if isinstance(author, str):
            name = normalize_whitespace(author)
        elif isinstance(author, dict):
            literal = normalize_whitespace(str(author.get("name") or ""))
            given = normalize_whitespace(str(author.get("given") or ""))
            family = normalize_whitespace(str(author.get("family") or ""))
            name = literal or normalize_whitespace(f"{given} {family}")
        else:
            name = ""
        if name:
            names.append(name)
    return names


def _categories(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    categories: list[str] = []
    for category in value:
        text = normalize_whitespace(str(category))
        if text and text not in categories:
            categories.append(text)
    return categories


def _published_date(item: dict) -> str:
    for key in ("published", "published-print", "published-online", "issued", "created"):
        parsed = _date_from_crossref(item.get(key))
        if parsed:
            return parsed
    return ""


def _updated_date(item: dict) -> str:
    for key in ("updated", "indexed", "deposited", "created"):
        parsed = _date_from_crossref(item.get(key))
        if parsed:
            return parsed
    return ""


def _date_from_crossref(value: object) -> str:
    if isinstance(value, dict):
        date_parts = value.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            return _date_from_parts(date_parts[0])
        if value.get("date-time"):
            return _iso_date(value.get("date-time"))
        return ""
    return _iso_date(value)


def _date_from_parts(parts: list) -> str:
    numbers: list[int] = []
    for part in parts[:3]:
        if part is None or str(part).strip() == "":
            break
        numbers.append(int(part))
    if not numbers:
        return ""
    year = numbers[0]
    month = numbers[1] if len(numbers) > 1 else 1
    day = numbers[2] if len(numbers) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _iso_date(value: object) -> str:
    if value is None:
        return ""
    text = normalize_whitespace(str(value))
    if not text:
        return ""
    match = re.match(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", text)
    if not match:
        return ""
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _pdf_url(item: dict) -> str:
    links = item.get("link")
    if not isinstance(links, list):
        return ""
    fallback = ""
    for link in links:
        if not isinstance(link, dict):
            continue
        url = normalize_whitespace(str(link.get("URL") or ""))
        if not url:
            continue
        content_type = str(link.get("content-type") or "").lower()
        if "pdf" in content_type:
            return url
        fallback = fallback or url
    return fallback
