from __future__ import annotations

from dataclasses import asdict, dataclass
<<<<<<< HEAD
from datetime import date
from html import unescape
import json
from pathlib import Path
=======
from datetime import date, datetime
from html import unescape
from pathlib import Path
from typing import Any
import logging
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
import re
import time

import requests

from core.config import Settings
<<<<<<< HEAD
from core.utils import normalize_whitespace, write_json
=======
from core.utils import normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)


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


<<<<<<< HEAD
def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref work-list payload into normalized paper records.
=======
def _text(value: Any) -> str:
    return normalize_whitespace(value) if isinstance(value, str) else ""
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)


def _iso_date(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list):
        components = parts[0]
        if 1 <= len(components) <= 3:
            try:
                return date(*(components + [1] * (3 - len(components)))).isoformat()
            except (ValueError, TypeError):
                pass
    timestamp = value.get("date-time")
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return ""


def parse_crossref_payload(item: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one Crossref work; missing DOI returns None.

    Missing month/day defaults to 01; invalid dates remain empty. Missing
    subject metadata is preserved as empty rather than inferred.
    """
<<<<<<< HEAD
    def text(value: object) -> str:
        if isinstance(value, list):
            value = value[0] if value else ""
        return normalize_whitespace(unescape(str(value or "")))

    def clean_markup(value: object) -> str:
        # Crossref abstracts commonly contain JATS tags.  Removing every tag also
        # handles ordinary HTML without adding another parsing dependency.
        return normalize_whitespace(unescape(re.sub(r"<[^>]+>", " ", str(value or ""))))

    def doi(value: object) -> str:
        normalized = text(value).lower()
        normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", normalized)
        return normalized.strip().rstrip(".,")

    def crossref_date(value: object) -> str:
        if isinstance(value, dict):
            raw = value.get("date-parts")
            if isinstance(raw, list) and raw and isinstance(raw[0], list) and raw[0]:
                parts = raw[0]
                try:
                    return date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1,
                                int(parts[2]) if len(parts) > 2 else 1).isoformat()
                except (TypeError, ValueError):
                    pass
            date_time = value.get("date-time")
            if date_time:
                return str(date_time)[:10]
        return ""

    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    items = message.get("items", []) if isinstance(message, dict) else []
    records: list[PaperRecord] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        paper_id = doi(item.get("DOI"))
        title = text(item.get("title"))
        summary = clean_markup(item.get("abstract"))
        published = crossref_date(
            item.get("published") or item.get("published-print") or item.get("published-online")
        )
        if not paper_id or not title or not published:
            continue

        authors = []
        for author in item.get("author", []) or []:
            if isinstance(author, dict):
                name = text(f"{author.get('given', '')} {author.get('family', '')}")
                if name:
                    authors.append(name)
        categories = [text(subject) for subject in (item.get("subject", []) or []) if text(subject)]
        updated = crossref_date(item.get("updated") or item.get("indexed") or item.get("created")) or published
        abs_url = text(item.get("URL")) or f"https://doi.org/{paper_id}"
        pdf_url = abs_url
        for link in item.get("link", []) or []:
            if isinstance(link, dict) and (
                link.get("content-type") == "application/pdf" or link.get("content-version") == "vor"
            ):
                pdf_url = text(link.get("URL")) or pdf_url
                if link.get("content-type") == "application/pdf":
                    break

        records.append(PaperRecord(
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
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records with retry, persistence, and offline fallback.
=======
    paper_id = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", _text(item.get("DOI")).lower()).strip()
    if not paper_id:
        return None
    titles = item.get("title") or []
    title = _text(titles[0] if isinstance(titles, list) and titles else titles)
    abstract = _text(item.get("abstract"))
    # Separate block elements while preserving inline words such as micro<i>RNA</i>.
    abstract = re.sub(r"</?(?:[\w-]+:)?(?:p|sec|section|div|br|title|li)\b[^>]*>", " ", abstract, flags=re.I)
    summary = normalize_whitespace(unescape(re.sub(r"<[^>]+>", "", abstract)))
    authors = []
    for author in item.get("author") or []:
        if isinstance(author, dict):
            name = _text(f"{_text(author.get('given'))} {_text(author.get('family'))}") or _text(author.get("name"))
            if name:
                authors.append(name)
    subjects = item.get("subject") or []
    if isinstance(subjects, str):
        subjects = [subjects]
    categories = [_text(subject) for subject in subjects if _text(subject)]
    published = next((parsed for key in ("published-print", "published-online", "issued", "published")
                      if (parsed := _iso_date(item.get(key)))), "")
    updated = next((parsed for key in ("indexed", "deposited", "created")
                    if (parsed := _iso_date(item.get(key)))), published)
    abs_url = _text(item.get("URL")) or f"https://doi.org/{paper_id}"
    pdf_url = next((_text(link.get("URL")) for link in item.get("link") or []
                    if isinstance(link, dict) and link.get("content-type") == "application/pdf"
                    and _text(link.get("URL"))), abs_url)
    return {
        "paper_id": paper_id, "title": title, "summary": summary,
        "authors": ", ".join(authors) or "Unknown", "categories": ", ".join(categories),
        "primary_category": categories[0] if categories else "",
        "published": published, "updated": updated,
        "abs_url": abs_url, "pdf_url": pdf_url, "comment": f"Crossref record {paper_id}",
    }


def _to_record(item: dict[str, Any]) -> PaperRecord:
    """Adapt normalized string fields and legacy list snapshots to PaperRecord."""
    def names(value: Any) -> list[str]:
        if isinstance(value, str):
            value = value.split(",")
        return [_text(part) for part in value or [] if _text(part)]

    categories = names(item.get("categories"))
    return PaperRecord(
        paper_id=_text(item.get("paper_id")).lower(), title=_text(item.get("title")),
        summary=_text(item.get("summary")), authors=names(item.get("authors")) or ["Unknown"],
        categories=categories, primary_category=_text(item.get("primary_category")) or (categories[0] if categories else ""),
        published=_text(item.get("published")), updated=_text(item.get("updated")),
        abs_url=_text(item.get("abs_url")), pdf_url=_text(item.get("pdf_url")),
        comment=_text(item.get("comment")),
    )


def parse_crossref_response(payload: dict[str, Any]) -> list[PaperRecord]:
    """Parse a full works response, retaining the existing pipeline contract."""
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("items"), list):
        raise ValueError("Crossref response must contain message.items as a list.")
    return [_to_record(parsed) for item in message["items"]
            if isinstance(item, dict) and (parsed := parse_crossref_payload(item)) is not None]


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Use the offline snapshot by default; refresh from API when requested.
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)

    Network errors and 429 fall back immediately to the snapshot. Temporary
    server failures retry with bounded backoff. Never replace a good snapshot
    with malformed/empty responses, and never overwrite it during fallback.
    """
<<<<<<< HEAD
    endpoint = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    payload: dict | None = None
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers={"User-Agent": "day10-data-observability-lab/0.1"},
                timeout=20,
            )
            if response.status_code in {429, 503}:
                raise requests.HTTPError(f"Crossref returned HTTP {response.status_code}")
            response.raise_for_status()
            candidate = response.json()
            candidate_records = parse_crossref_payload(candidate)
            if len(candidate_records) < settings.max_results:
                raise ValueError(
                    f"Crossref returned only {len(candidate_records)} valid records; "
                    f"expected {settings.max_results}"
                )
            payload = candidate
            write_json(settings.paths.raw_api_response, payload)
            break
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)

    if payload is None:
        snapshot = settings.paths.raw_api_response
        if not snapshot.exists():
            raise RuntimeError("Crossref is unavailable and the offline snapshot is missing") from last_error
        payload = json.loads(snapshot.read_text(encoding="utf-8"))

    records = parse_crossref_payload(payload)[: settings.max_results]
    if not records:
        raise ValueError("No valid Crossref records were found in the API response or snapshot")
=======
    snapshot = Path(settings.paths.raw_api_response)
    if snapshot.exists() and not settings.refresh_source:
        records = parse_crossref_response(read_json(snapshot))
    else:
        params = {"query": settings.source_query, "rows": settings.max_results}
        if settings.source_filter:
            params["filter"] = settings.source_filter
        try:
            for attempt in range(3):
                response = requests.get(
                    "https://api.crossref.org/works", params=params,
                    headers={"User-Agent": "day10-data-observability/1.0", "Accept": "application/json"},
                    timeout=30,
                )
                if response.status_code in {500, 502, 503, 504} and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                break
            payload = response.json()
            records = parse_crossref_response(payload)
            if not records:
                raise ValueError("Crossref returned no usable DOI records.")
        except (requests.RequestException, ValueError) as exc:
            if not snapshot.exists():
                raise RuntimeError(f"Crossref unavailable and offline snapshot missing: {snapshot}") from exc
            logger.warning("Crossref refresh failed (%s); using offline snapshot %s", type(exc).__name__, snapshot)
            records = parse_crossref_response(read_json(snapshot))
        else:
            write_json(snapshot, payload)
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
<<<<<<< HEAD
    """Load a normalized JSON snapshot into ``PaperRecord`` objects."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of records in {path}")
    records: list[PaperRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        values = dict(item)
        values["authors"] = list(values.get("authors") or [])
        values["categories"] = list(values.get("categories") or [])
        records.append(PaperRecord(**values))
    return records
=======
    """Load normalized record snapshots with string or legacy list fields."""
    payload = read_json(Path(path))
    if not isinstance(payload, list):
        raise ValueError("Raw records JSON must contain a top-level list.")
    return [_to_record(item) for item in payload if isinstance(item, dict)
            and _text(item.get("paper_id")) and _text(item.get("title"))]
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
