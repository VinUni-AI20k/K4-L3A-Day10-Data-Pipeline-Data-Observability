from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import html
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_URL = "https://api.crossref.org/works"
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
TAG_RE = re.compile(r"<[^>]+>")


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


def _strip_markup(value: str) -> str:
    """Bo the HTML/JATS XML (vd <jats:p>) va giai ma entity."""
    return normalize_whitespace(html.unescape(TAG_RE.sub(" ", value or "")))


def _normalize_doi(value: str) -> str:
    doi = normalize_whitespace(value or "").lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi)


def _parse_date(item: dict) -> str:
    """Tra ve ngay ISO 8601 (YYYY-MM-DD); date-parts thieu thang/ngay -> mac dinh 1."""
    for key in ("published", "issued", "published-online", "published-print", "created"):
        node = item.get(key) or {}
        parts = (node.get("date-parts") or [[]])[0]
        if parts and parts[0]:
            year, month, day = (list(parts) + [1, 1])[:3]
            try:
                return date(int(year), int(month or 1), int(day or 1)).isoformat()
            except (TypeError, ValueError):
                continue
        stamp = node.get("date-time")
        if stamp:
            return str(stamp)[:10]
    return ""


def _parse_authors(item: dict) -> list[str]:
    authors = []
    for author in item.get("author") or []:
        name = normalize_whitespace(
            author.get("name") or f"{author.get('given', '')} {author.get('family', '')}"
        )
        if name:
            authors.append(name)
    return authors


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    records: list[PaperRecord] = []
    for item in (payload.get("message") or {}).get("items") or []:
        paper_id = _normalize_doi(item.get("DOI", ""))
        titles = item.get("title") or [""]
        title = normalize_whitespace(titles[0] if isinstance(titles, list) else titles)
        summary = _strip_markup(item.get("abstract", ""))
        published = _parse_date(item)
        if not (paper_id and title and summary and published):
            continue

        categories = [normalize_whitespace(s) for s in item.get("subject") or [] if normalize_whitespace(s)]
        url = item.get("URL") or f"https://doi.org/{paper_id}"
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=_parse_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=published,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def _request_with_retry(params: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(CROSSREF_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code == 200:
                return response.json()
            last_error = RuntimeError(f"Crossref returned HTTP {response.status_code}")
            if response.status_code not in RETRY_STATUS:
                break
        if attempt < MAX_ATTEMPTS:
            time.sleep(2**attempt)
    raise RuntimeError(f"Crossref request failed: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    paths = settings.paths
    payload: dict | None = None

    if settings.refresh_source or not paths.raw_api_response.exists():
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
            "select": "DOI,title,abstract,author,subject,published,created,URL",
        }
        try:
            payload = _request_with_retry(params)
            write_json(paths.raw_api_response, payload)
        except RuntimeError as exc:
            print(f"[crossref] {exc}; falling back to snapshot {paths.raw_api_response}")

    if payload is None:
        if not paths.raw_api_response.exists():
            raise RuntimeError("Crossref API unavailable and no offline snapshot found.")
        payload = read_json(paths.raw_api_response)

    records = parse_crossref_payload(payload)
    write_json(paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    return [PaperRecord(**row) for row in read_json(path)]
