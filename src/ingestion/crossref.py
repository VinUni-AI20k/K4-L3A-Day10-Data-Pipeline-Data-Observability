from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
import json
from pathlib import Path
import re
import time

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
    """Convert a Crossref ``work-list`` response into normalized records.

    Crossref fields are optional and differ slightly between publishers, so this
    parser deliberately treats missing metadata as an empty value.  A DOI and a
    title are the only fields required to make a useful, stable record.
    """

    if not isinstance(payload, dict):
        return []

    message = payload.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []

    def clean_text(value: object) -> str:
        """Remove JATS/HTML markup, decode entities, and collapse whitespace."""
        if not isinstance(value, str):
            return ""
        # Crossref abstracts are commonly JATS fragments (for example
        # ``<jats:p>...</jats:p>``), not plain text.
        value = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", unescape(value)).strip()

    def first_text(value: object) -> str:
        if isinstance(value, str):
            return clean_text(value)
        if isinstance(value, list):
            for candidate in value:
                text = clean_text(candidate)
                if text:
                    return text
        return ""

    def date_from(value: object) -> str:
        """Return the first Crossref date as ISO ``YYYY-MM-DD`` when present."""
        if isinstance(value, dict):
            parts = value.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list):
                values = parts[0]
                if values and isinstance(values[0], int):
                    year = f"{values[0]:04d}"
                    month = f"-{values[1]:02d}" if len(values) > 1 and isinstance(values[1], int) else ""
                    day = f"-{values[2]:02d}" if len(values) > 2 and isinstance(values[2], int) else ""
                    return f"{year}{month}{day}"
            for key in ("date-time", "timestamp"):
                text = value.get(key)
                if isinstance(text, str) and text:
                    return text[:10]
        return ""

    records: list[PaperRecord] = []
    seen_dois: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        doi = clean_text(item.get("DOI")).lower()
        title = first_text(item.get("title"))
        if not doi or not title or doi in seen_dois:
            continue

        authors: list[str] = []
        raw_authors = item.get("author")
        if isinstance(raw_authors, list):
            for author in raw_authors:
                if not isinstance(author, dict):
                    continue
                name = " ".join(
                    part
                    for part in (clean_text(author.get("given")), clean_text(author.get("family")))
                    if part
                ) or clean_text(author.get("name"))
                if name:
                    authors.append(name)

        raw_subjects = item.get("subject")
        categories = (
            [text for subject in raw_subjects if (text := clean_text(subject))]
            if isinstance(raw_subjects, list)
            else []
        )

        doi_url = item.get("URL")
        abs_url = clean_text(doi_url) or f"https://doi.org/{doi}"
        pdf_url = ""
        links = item.get("link")
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue
                content_type = clean_text(link.get("content-type")).lower()
                url = clean_text(link.get("URL"))
                if url and (content_type == "application/pdf" or not pdf_url):
                    pdf_url = url
                    if content_type == "application/pdf":
                        break

        published = next(
            (
                date_from(item.get(field))
                for field in ("published", "published-print", "published-online", "issued", "created")
                if date_from(item.get(field))
            ),
            "",
        )
        updated = next(
            (
                date_from(item.get(field))
                for field in ("updated", "created", "indexed", "published")
                if date_from(item.get(field))
            ),
            published,
        )

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=clean_text(item.get("abstract")),
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url or abs_url,
                comment=f"Crossref record {doi}",
            )
        )
        seen_dois.add(doi)

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref records, falling back to the preserved local response.

    The default, offline-friendly mode reuses the snapshot unless
    ``REFRESH_SOURCE`` is enabled.  A failed live request never destroys that
    snapshot, so the pipeline remains reproducible when Crossref rate-limits
    requests or the network is unavailable.
    """

    response_path = settings.paths.raw_api_response
    records_path = settings.paths.raw_records_json

    def read_payload(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as raw_file:
            payload = json.load(raw_file)
        if not isinstance(payload, dict):
            raise ValueError(f"Crossref payload in {path} must be a JSON object.")
        return payload

    payload: dict | None = None
    live_error: Exception | None = None

    if not settings.refresh_source and response_path.exists():
        payload = read_payload(response_path)
    else:
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": max(1, settings.max_results),
        }
        retryable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(3):
            try:
                response = requests.get(
                    "https://api.crossref.org/works",
                    params=params,
                    headers={"User-Agent": "DoubleMint-data-pipeline/1.0 (mailto:example@example.com)"},
                    timeout=20,
                )
                if response.status_code in retryable_statuses:
                    raise requests.HTTPError(f"Crossref returned HTTP {response.status_code}")
                response.raise_for_status()
                candidate = response.json()
                if not isinstance(candidate, dict):
                    raise ValueError("Crossref API did not return a JSON object.")
                payload = candidate
                break
            except (requests.RequestException, ValueError) as exc:
                live_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)

        if payload is not None:
            response_path.parent.mkdir(parents=True, exist_ok=True)
            response_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif response_path.exists():
            payload = read_payload(response_path)
        else:
            raise RuntimeError("Could not fetch Crossref and no local snapshot is available.") from live_error

    records = parse_crossref_payload(payload)
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text(
        json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the normalized raw-record artifact produced by ``fetch_source_records``."""
    with path.open("r", encoding="utf-8") as raw_file:
        data = json.load(raw_file)
    if not isinstance(data, list):
        raise ValueError(f"Raw records in {path} must be a JSON array.")

    fields = set(PaperRecord.__dataclass_fields__)
    records: list[PaperRecord] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} in {path} must be a JSON object.")
        missing = fields - item.keys()
        if missing:
            raise ValueError(f"Raw record at index {index} in {path} is missing: {', '.join(sorted(missing))}.")
        records.append(PaperRecord(**{field: item[field] for field in fields}))
    return records
