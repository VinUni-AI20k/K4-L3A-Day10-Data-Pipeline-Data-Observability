from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any
import httpx

from core.config import Settings

logger = logging.getLogger(__name__)


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


def _clean_text(text: str) -> str:
    """Normalize text by stripping XML/HTML tags and collapsing extra whitespaces."""
    if not text:
        return ""
    # Remove HTML / JATS XML tags such as <jats:p>, </jats:p>, <jats:title>, etc.
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple whitespace characters into a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_crossref_payload(payload: dict[str, Any]) -> list[PaperRecord]:
    """Parse Crossref API payload into a list of PaperRecord objects."""
    items = []
    if isinstance(payload, dict):
        if "message" in payload and isinstance(payload["message"], dict):
            items = payload["message"].get("items", [])
        elif "items" in payload:
            items = payload.get("items", [])
    elif isinstance(payload, list):
        items = payload

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = str(item.get("DOI") or item.get("paper_id") or "").strip()
        if not paper_id:
            continue

        # Extract and normalize title
        raw_title = item.get("title", "")
        if isinstance(raw_title, list):
            raw_title = raw_title[0] if raw_title else ""
        title = _clean_text(str(raw_title))

        # Extract and normalize summary / abstract
        raw_abstract = item.get("abstract") or item.get("summary") or ""
        summary = _clean_text(str(raw_abstract))

        # Extract authors
        authors: list[str] = []
        raw_authors = item.get("author") or item.get("authors") or []
        for a in raw_authors:
            if isinstance(a, dict):
                given = a.get("given", "").strip()
                family = a.get("family", "").strip()
                full_name = f"{given} {family}".strip() if (given or family) else a.get("name", "").strip()
                if full_name:
                    authors.append(full_name)
            elif isinstance(a, str) and a.strip():
                authors.append(a.strip())

        # Extract categories / subjects
        raw_categories = item.get("subject") or item.get("categories") or []
        categories = [str(c).strip() for c in raw_categories if str(c).strip()]
        primary_category = (
            item.get("primary_category")
            or (categories[0] if categories else "Computer Science")
        )

        # Extract published date (ISO 8601 YYYY-MM-DD)
        published = ""
        date_parts = (
            item.get("published", {}).get("date-parts", [[]])[0]
            if isinstance(item.get("published"), dict)
            else []
        )
        if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
            year = date_parts[0]
            month = date_parts[1] if len(date_parts) > 1 else 1
            day = date_parts[2] if len(date_parts) > 2 else 1
            published = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        elif item.get("published") and isinstance(item.get("published"), str):
            published = item.get("published")[:10]
        elif item.get("created", {}).get("date-time"):
            published = item.get("created", {}).get("date-time")[:10]
        else:
            published = "2026-01-01"

        updated = item.get("updated") or published
        abs_url = str(item.get("URL") or item.get("abs_url") or f"https://doi.org/{paper_id}")
        pdf_url = str(item.get("pdf_url") or abs_url)
        comment = str(item.get("comment") or f"Crossref record {paper_id}")

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch metadata from Crossref API with dual-mode fallback to local snapshot."""
    raw_response_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json

    # Mode 1: Live API Ingestion if refresh_source is explicitly requested
    if settings.refresh_source:
        api_url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {
            "User-Agent": "K4-Day10-DataPipeline/1.0 (mailto:student@vinuni.edu.vn)"
        }
        try:
            logger.info("Connecting to live Crossref API...")
            with httpx.Client(timeout=15.0) as client:
                response = client.get(api_url, params=params, headers=headers)
                if response.status_code == 200:
                    payload = response.json()
                    # Preserve raw response for data lineage
                    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(raw_response_path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2, ensure_ascii=False)

                    records = parse_crossref_payload(payload)
                    # Preserve parsed raw records
                    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(raw_records_path, "w", encoding="utf-8") as f:
                        json.dump([asdict(r) for r in records], f, indent=2, ensure_ascii=False)
                    return records
                else:
                    logger.warning(
                        f"Crossref API returned status {response.status_code}. Fallback to offline snapshot."
                    )
        except Exception as e:
            logger.warning(
                f"Failed to fetch from live API ({e}). Fallback to offline snapshot."
            )

    # Mode 2: Offline Snapshot / Dev Fallback
    if raw_records_path.exists():
        logger.info(f"Loading raw records from snapshot: {raw_records_path}")
        return load_raw_records(raw_records_path)

    if raw_response_path.exists():
        logger.info(f"Parsing raw response snapshot from: {raw_response_path}")
        with open(raw_response_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        records = parse_crossref_payload(payload)
        raw_records_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_records_path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in records], f, indent=2, ensure_ascii=False)
        return records

    raise FileNotFoundError(
        f"Neither live API nor offline snapshots were found at {raw_response_path} or {raw_records_path}"
    )


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Read JSON snapshot and deserialize into a list of PaperRecord objects."""
    if not path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected a list of paper records in JSON at {path}")

    return [PaperRecord(**item) for item in data]
