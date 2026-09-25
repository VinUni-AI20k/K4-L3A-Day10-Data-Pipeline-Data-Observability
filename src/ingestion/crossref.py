from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date
from html import unescape
import json
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings


_CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


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


def _normalize_text(value: Any, *, strip_markup: bool = False) -> str:
    """Convert a Crossref value to normalized, single-line text."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(part) for part in value if part is not None)
    else:
        value = str(value)
    if strip_markup:
        value = _TAG_RE.sub(" ", value)
    return _SPACE_RE.sub(" ", unescape(value)).strip()


def _date_from_parts(value: Any) -> str:
    """Return an ISO date from a Crossref ``date-parts`` object."""
    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not date_parts[0]:
        return ""

    parts = date_parts[0]
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def _date_from_datetime(value: Any) -> str:
    """Extract the YYYY-MM-DD portion of a Crossref date-time object."""
    if not isinstance(value, dict):
        return ""
    raw = _normalize_text(value.get("date-time"))
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    if not match:
        return ""
    try:
        return date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        return ""


def _first_date(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        parsed = _date_from_parts(value) or _date_from_datetime(value)
        if parsed:
            return parsed
    return ""


def _authors(item: dict[str, Any]) -> list[str]:
    result: list[str] = []
    raw_authors = item.get("author", [])
    if not isinstance(raw_authors, list):
        return result

    for author in raw_authors:
        if not isinstance(author, dict):
            continue
        name = _normalize_text([author.get("given"), author.get("family")])
        if not name:
            name = _normalize_text(author.get("name"))
        if name and name not in result:
            result.append(name)
    return result


def _categories(item: dict[str, Any]) -> list[str]:
    raw_categories = item.get("subject", [])
    if isinstance(raw_categories, str):
        raw_categories = [raw_categories]
    if not isinstance(raw_categories, list):
        return []

    result: list[str] = []
    for value in raw_categories:
        category = _normalize_text(value)
        if category and category not in result:
            result.append(category)
    return result


def _pdf_url(item: dict[str, Any], fallback: str) -> str:
    links = item.get("link", [])
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            content_type = _normalize_text(link.get("content-type")).lower()
            url = _normalize_text(link.get("URL"))
            if url and (content_type == "application/pdf" or url.lower().endswith(".pdf")):
                return url
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref work-list payload into validated ``PaperRecord`` objects.

    Records without a DOI, title, abstract, or publication date are ignored.
    Duplicate DOI values are collapsed while preserving API order.
    """
    if not isinstance(payload, dict):
        raise TypeError("Crossref payload must be a JSON object.")

    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref payload is missing the 'message' object.")
    items = message.get("items")
    if not isinstance(items, list):
        raise ValueError("Crossref payload is missing the 'message.items' list.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = _normalize_text(item.get("DOI"))
        title = _normalize_text(item.get("title"), strip_markup=True)
        summary = _normalize_text(item.get("abstract"), strip_markup=True)
        published = _first_date(
            item,
            ("published", "published-online", "published-print", "issued", "created"),
        )
        identity = paper_id.casefold()
        if not paper_id or not title or not summary or not published or identity in seen_ids:
            continue

        updated = _first_date(item, ("updated", "indexed", "deposited", "created")) or published
        categories = _categories(item)
        abs_url = _normalize_text(item.get("URL")) or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )
        seen_ids.add(identity)

    return records


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON snapshot does not exist: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    """Write JSON atomically so an interrupted run cannot corrupt the snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _download_payload(settings: Settings, attempts: int = 3) -> dict[str, Any]:
    params = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "day10-data-observability-lab/0.1",
    }
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            response = requests.get(
                _CROSSREF_WORKS_URL,
                params=params,
                headers=headers,
                timeout=(5, 30),
            )
        except requests.RequestException as exc:
            last_error = exc
            retry_after = ""
        else:
            if response.status_code in _RETRYABLE_STATUS_CODES:
                last_error = requests.HTTPError(
                    f"Crossref returned retryable HTTP {response.status_code}.",
                    response=response,
                )
                retry_after = response.headers.get("Retry-After", "")
            else:
                # Client errors such as 400/404 are not transient and should not
                # consume the retry budget.
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    last_error = exc
                    retry_after = ""
                else:
                    if not isinstance(payload, dict):
                        raise ValueError("Crossref returned JSON that is not an object.")
                    return payload

        if attempt + 1 < attempts:
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = 0.5 * (2**attempt)
            time.sleep(min(max(delay, 0.0), 5.0))

    assert last_error is not None
    raise last_error


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref works, falling back to the local raw response snapshot.

    The default development mode (``refresh_source=False``) reads the checked-in
    snapshot without touching the network. Live mode retries transient failures;
    if all attempts fail, the same snapshot is used as an offline fallback.
    """
    snapshot_path = settings.paths.raw_api_response
    payload: dict[str, Any]

    if not settings.refresh_source and snapshot_path.exists():
        payload = _read_json(snapshot_path)
        if not isinstance(payload, dict):
            raise ValueError(f"Crossref snapshot must contain a JSON object: {snapshot_path}")
    else:
        try:
            payload = _download_payload(settings)
            _write_json(snapshot_path, payload)
        except (requests.RequestException, ValueError) as exc:
            if not snapshot_path.exists():
                raise RuntimeError(
                    "Could not fetch Crossref data and no local response snapshot is available."
                ) from exc
            payload = _read_json(snapshot_path)
            if not isinstance(payload, dict):
                raise ValueError(f"Crossref snapshot must contain a JSON object: {snapshot_path}") from exc

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("Crossref payload did not contain any valid paper records.")

    _write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a parsed record snapshot and validate its ``PaperRecord`` schema."""
    raw = _read_json(path)
    if isinstance(raw, dict):
        return parse_crossref_payload(raw)
    if not isinstance(raw, list):
        raise ValueError(f"Raw records snapshot must contain a JSON list: {path}")

    field_names = {field.name for field in fields(PaperRecord)}
    records: list[PaperRecord] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Record {index} in {path} is not a JSON object.")
        missing = field_names.difference(item)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"Record {index} in {path} is missing fields: {names}.")

        values = {name: item[name] for name in field_names}
        if not isinstance(values["authors"], list) or not isinstance(values["categories"], list):
            raise ValueError(f"Record {index} in {path} has invalid authors/categories fields.")
        values["authors"] = list(filter(None, map(_normalize_text, values["authors"])))
        values["categories"] = [
            _normalize_text(value) for value in values["categories"] if _normalize_text(value)
        ]
        for name in field_names.difference({"authors", "categories"}):
            values[name] = _normalize_text(values[name])

        records.append(PaperRecord(**values))
    return records
