from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import html
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 30

# Thu tu uu tien khi lay ngay xuat ban tu Crossref.
PUBLISHED_DATE_FIELDS = ("published", "published-print", "published-online", "issued", "created")
UPDATED_DATE_FIELDS = ("deposited", "indexed", "created")


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


def _strip_markup(text: str) -> str:
    """Bo the HTML/JATS XML (vd `<jats:p>`) va giai ma HTML entities."""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(html.unescape(without_tags))


def _parse_date_parts(item: dict, fields: tuple[str, ...]) -> str:
    """Tra ve ngay dang ISO `YYYY-MM-DD` tu truong `date-parts` dau tien hop le."""
    for field in fields:
        parts = (item.get(field) or {}).get("date-parts") or []
        if not parts or not parts[0] or parts[0][0] is None:
            continue
        year, month, day = (list(parts[0]) + [1, 1])[:3]
        return f"{int(year):04d}-{int(month or 1):02d}-{int(day or 1):02d}"
    return ""


def _parse_authors(item: dict) -> list[str]:
    authors: list[str] = []
    for author in item.get("author") or []:
        full_name = normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
        name = full_name or normalize_whitespace(author.get("name", ""))
        if name:
            authors.append(name)
    return authors


def _parse_pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if link.get("content-type") == "application/pdf" and link.get("URL"):
            return link["URL"]
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list `PaperRecord`, bo qua record thieu DOI/title/abstract."""
    records: list[PaperRecord] = []
    for item in (payload.get("message") or {}).get("items") or []:
        doi = normalize_whitespace(item.get("DOI", "")).lower()
        titles = item.get("title") or []
        title = _strip_markup(titles[0]) if titles else ""
        summary = _strip_markup(item.get("abstract", ""))
        published = _parse_date_parts(item, PUBLISHED_DATE_FIELDS)
        if not doi or not title or not summary or not published:
            continue

        categories = [normalize_whitespace(subject) for subject in item.get("subject") or [] if subject]
        abs_url = item.get("URL") or f"https://doi.org/{doi}"
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=_parse_authors(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=_parse_date_parts(item, UPDATED_DATE_FIELDS) or published,
                abs_url=abs_url,
                pdf_url=_parse_pdf_url(item, abs_url),
                comment=f"Crossref record {doi}",
            )
        )
    return records


def _request_crossref(settings: Settings) -> dict:
    """Goi Crossref API, retry voi exponential backoff khi gap 429/5xx."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(CROSSREF_WORKS_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise requests.HTTPError(f"Crossref returned {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Crossref API unavailable after {MAX_RETRIES} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay du lieu nguon theo co che Dual-Mode.

    - Offline (mac dinh): doc snapshot `data/raw/crossref_response.json`.
    - Live (`REFRESH_SOURCE=1`): goi Crossref API; neu loi mang/429 thi tu dong
      quay ve snapshot offline de pipeline khong bi gian doan.
    """
    snapshot_path = settings.paths.raw_api_response
    payload: dict | None = None

    if settings.refresh_source:
        try:
            payload = _request_crossref(settings)
            write_json(snapshot_path, payload)
            print(f"[ingestion] Live mode: fetched Crossref API -> {snapshot_path}")
        except RuntimeError as exc:
            print(f"[ingestion] {exc}. Falling back to offline snapshot.")

    if payload is None:
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Offline snapshot not found: {snapshot_path}")
        payload = read_json(snapshot_path)
        print(f"[ingestion] Offline mode: loaded snapshot {snapshot_path}")

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot da parse va map thanh `PaperRecord`."""
    return [PaperRecord(**row) for row in read_json(path)]
