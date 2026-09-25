from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import compact_join, normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
REQUEST_TIMEOUT_SECONDS = 30
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0
MIN_SUMMARY_CHARS = 30

_MARKUP_TAG = re.compile(r"<[^>]+>")
_ABSTRACT_LABEL = re.compile(r"^\s*abstract[:\s]*", flags=re.IGNORECASE)


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
    """Bo cac the JATS/HTML (<jats:p>, <p>, ...) va chuan hoa khoang trang."""
    without_tags = _MARKUP_TAG.sub(" ", value or "")
    return normalize_whitespace(_ABSTRACT_LABEL.sub("", without_tags))


def _first_string(value: Any) -> str:
    if isinstance(value, list):
        return normalize_whitespace(str(value[0])) if value else ""
    return normalize_whitespace(str(value)) if value else ""


def _format_authors(raw_authors: Any) -> list[str]:
    authors: list[str] = []
    for author in raw_authors or []:
        if not isinstance(author, dict):
            continue
        full_name = author.get("name") or compact_join(
            [normalize_whitespace(str(author.get("given", ""))), normalize_whitespace(str(author.get("family", "")))],
            sep=" ",
        )
        full_name = normalize_whitespace(full_name)
        if full_name:
            authors.append(full_name)
    return authors


def _date_from_parts(node: Any) -> str:
    """Doi {'date-parts': [[2026, 5, 20]]} thanh chuoi ISO '2026-05-20'."""
    if not isinstance(node, dict):
        return ""
    parts = node.get("date-parts") or []
    if not parts or not isinstance(parts[0], list) or not parts[0]:
        return ""
    numbers = [int(value) for value in parts[0] if value is not None]
    year = numbers[0]
    month = numbers[1] if len(numbers) > 1 else 1
    day = numbers[2] if len(numbers) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _date_from_timestamp(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    date_time = node.get("date-time") or ""
    return date_time[:10] if len(date_time) >= 10 else _date_from_parts(node)


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse payload Crossref thanh list PaperRecord da chuan hoa.

    Bo qua cac ban ghi thieu DOI / title / abstract vi chung khong the nhung vector.
    """
    items = (payload or {}).get("message", {}).get("items", []) or []
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = normalize_whitespace(str(item.get("DOI", "")))
        title = _first_string(item.get("title"))
        summary = _strip_markup(str(item.get("abstract", "")))

        if not paper_id or not title or len(summary) < MIN_SUMMARY_CHARS:
            continue
        if paper_id in seen_ids:
            continue
        seen_ids.add(paper_id)

        authors = _format_authors(item.get("author"))
        categories = [normalize_whitespace(str(value)) for value in (item.get("subject") or []) if value]
        published = _date_from_parts(item.get("published")) or _date_from_timestamp(item.get("created"))
        updated = _date_from_timestamp(item.get("created")) or published
        url = normalize_whitespace(str(item.get("URL", ""))) or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {paper_id}",
            )
        )

    return records


def _request_crossref(settings: Settings) -> dict:
    """Goi Crossref REST API voi co che retry cho 429/5xx."""
    params = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    headers = {"User-Agent": "day10-data-observability-lab/1.0 (mailto:student@example.com)"}

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code in RETRY_STATUS_CODES:
                raise requests.HTTPError(f"Crossref returned {response.status_code}")
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - mang chap chon la truong hop binh thuong trong lab
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise RuntimeError(f"Crossref API khong phan hoi sau {MAX_ATTEMPTS} lan thu: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay du lieu nguon, luu raw artifact va tra ve list PaperRecord.

    Dual-mode:
    - Mac dinh (REFRESH_SOURCE khong bat): doc snapshot offline neu co san.
    - REFRESH_SOURCE=1: goi Crossref API that, tu dong fallback ve snapshot khi API loi.
    """
    snapshot_path = settings.paths.raw_api_response
    payload: dict | None = None

    if settings.refresh_source or not snapshot_path.exists():
        try:
            payload = _request_crossref(settings)
            write_json(snapshot_path, payload)
            print(f"[ingestion] Da lay du lieu truc tiep tu {settings.source_api}.")
        except Exception as exc:  # noqa: BLE001
            print(f"[ingestion] Live API that bai ({exc}). Chuyen sang snapshot offline.")
            payload = None

    if payload is None:
        if not snapshot_path.exists():
            raise FileNotFoundError(
                f"Khong co snapshot offline tai {snapshot_path} va cung khong goi duoc API."
            )
        payload = read_json(snapshot_path)
        print(f"[ingestion] Doc snapshot offline tu {snapshot_path}.")

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc file JSON snapshot va map thanh list PaperRecord (dung cho buoc repair)."""
    rows = read_json(Path(path))
    records: list[PaperRecord] = []
    for row in rows:
        records.append(
            PaperRecord(
                paper_id=str(row.get("paper_id", "")),
                title=str(row.get("title", "")),
                summary=str(row.get("summary", "")),
                authors=list(row.get("authors", []) or []),
                categories=list(row.get("categories", []) or []),
                primary_category=str(row.get("primary_category", "")),
                published=str(row.get("published", "")),
                updated=str(row.get("updated", "")),
                abs_url=str(row.get("abs_url", "")),
                pdf_url=str(row.get("pdf_url", "")),
                comment=str(row.get("comment", "")),
            )
        )
    return records
