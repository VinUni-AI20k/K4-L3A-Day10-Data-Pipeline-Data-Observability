from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

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

def _clean_html(value: str) -> str:
    if not value:
        return ""

    value = re.sub(r"<[^>]+>", " ", value)
    return normalize_whitespace(unescape(value))


def _parse_date_parts(value: dict) -> str:
    parts = value.get("date-parts", [[]])

    if not parts or not parts[0]:
        return ""

    values = parts[0]

    year = values[0]
    month = values[1] if len(values) > 1 else 1
    day = values[2] if len(values) > 2 else 1

    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    items = payload.get("message", {}).get("items", [])

    records: list[PaperRecord] = []

    for item in items:
        doi = normalize_whitespace(str(item.get("DOI", "")))

        raw_title = item.get("title", [])
        if isinstance(raw_title, list):
            title = raw_title[0] if raw_title else ""
        else:
            title = str(raw_title)

        title = _clean_html(title)

        summary = _clean_html(str(item.get("abstract", "")))

        authors = []

        for author in item.get("author", []):
            given = str(author.get("given", ""))
            family = str(author.get("family", ""))

            name = normalize_whitespace(f"{given} {family}")

            if name:
                authors.append(name)

        categories = [
            normalize_whitespace(str(category))
            for category in item.get("subject", [])
            if normalize_whitespace(str(category))
        ]

        published_payload = (
            item.get("published")
            or item.get("published-online")
            or item.get("published-print")
            or {}
        )

        published = _parse_date_parts(published_payload)

        updated = (
            item.get("indexed", {}).get("date-time")
            or item.get("created", {}).get("date-time")
            or published
        )

        abs_url = str(item.get("URL", ""))

        pdf_url = ""

        for link in item.get("link", []):
            content_type = str(link.get("content-type", "")).lower()
            url = str(link.get("URL", ""))

            if "pdf" in content_type or url.lower().endswith(".pdf"):
                pdf_url = url
                break

        if not doi or not title:
            continue

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=str(updated),
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment="",
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    raw_response_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json

    if not settings.refresh_source and raw_response_path.exists():
        payload = read_json(raw_response_path)

    else:
        url = "https://api.crossref.org/works"

        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }

        headers = {
            "User-Agent": "VinUni-AI20K-Day10-Lab"
        }

        payload = None

        for attempt in range(3):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30,
                )

                if response.status_code in {429, 503}:
                    time.sleep(2 ** attempt)
                    continue

                response.raise_for_status()

                payload = response.json()

                write_json(raw_response_path, payload)

                break

            except requests.RequestException:
                if attempt == 2:
                    break

                time.sleep(2 ** attempt)

        if payload is None:
            if not raw_response_path.exists():
                raise RuntimeError(
                    "Crossref API failed and no local snapshot is available."
                )

            payload = read_json(raw_response_path)

    records = parse_crossref_payload(payload)

    write_json(
        raw_records_path,
        [asdict(record) for record in records],
    )

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    payload = read_json(path)

    return [PaperRecord(**item) for item in payload]