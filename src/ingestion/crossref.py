from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re

import requests

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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref API payload response into a list of PaperRecord objects.

    Extracts:
    - paper_id: Normalized DOI
    - title: Whitespace-normalized title string
    - summary: Abstract text stripped of HTML/JATS XML tags (<jats:p>, etc.) and normalized
    - authors: List of full author names ("Given Family")
    - categories: List of subject/category strings
    - primary_category: First subject/category or empty string
    - published: ISO 8601 date string (YYYY-MM-DD)
    - updated: ISO 8601 date string (YYYY-MM-DD)
    - abs_url / pdf_url / comment
    """
    message = payload.get("message", {})
    items = message.get("items", []) if isinstance(message, dict) else []
    if not items and isinstance(payload, list):
        items = payload

    records: list[PaperRecord] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        # 1. paper_id (DOI)
        doi = item.get("DOI") or item.get("paper_id") or ""
        paper_id = str(doi).strip()
        if not paper_id:
            continue

        # 2. title
        raw_title = item.get("title", "")
        if isinstance(raw_title, list):
            raw_title = raw_title[0] if raw_title else ""
        title = re.sub(r"\s+", " ", str(raw_title)).strip()

        # 3. summary (remove HTML/JATS tags and normalize whitespace)
        raw_abstract = item.get("abstract") or item.get("summary") or ""
        summary_clean = re.sub(r"<[^>]+>", "", str(raw_abstract))
        summary = re.sub(r"\s+", " ", summary_clean).strip()

        # 4. authors
        authors: list[str] = []
        raw_authors = item.get("author") or item.get("authors") or []
        if isinstance(raw_authors, list):
            for a in raw_authors:
                if isinstance(a, dict):
                    given = str(a.get("given", "")).strip()
                    family = str(a.get("family", "")).strip()
                    full_name = f"{given} {family}".strip()
                    if full_name:
                        authors.append(full_name)
                elif isinstance(a, str) and a.strip():
                    authors.append(a.strip())

        # 5. categories & primary_category
        categories: list[str] = []
        raw_subjects = item.get("subject") or item.get("categories") or []
        if isinstance(raw_subjects, list):
            for subj in raw_subjects:
                subj_clean = re.sub(r"\s+", " ", str(subj)).strip()
                if subj_clean:
                    categories.append(subj_clean)
        primary_category = categories[0] if categories else ""

        # 6. published date (ISO 8601 YYYY-MM-DD)
        published_str = ""
        pub_dict = item.get("published", {})
        if isinstance(pub_dict, dict) and "date-parts" in pub_dict:
            date_parts = pub_dict.get("date-parts", [[]])
            if date_parts and date_parts[0]:
                dp = date_parts[0]
                if len(dp) >= 3:
                    published_str = f"{dp[0]:04d}-{dp[1]:02d}-{dp[2]:02d}"
                elif len(dp) == 2:
                    published_str = f"{dp[0]:04d}-{dp[1]:02d}-01"
                elif len(dp) == 1:
                    published_str = f"{dp[0]:04d}-01-01"
        elif isinstance(pub_dict, str):
            published_str = pub_dict.strip()

        if not published_str:
            created_dict = item.get("created", {})
            if isinstance(created_dict, dict) and "date-time" in created_dict:
                dt_str = str(created_dict["date-time"])
                published_str = dt_str.split("T")[0]
            elif isinstance(item.get("published"), str):
                published_str = str(item["published"]).strip()

        # 7. updated date
        updated_str = published_str
        created_dict = item.get("created", {})
        if isinstance(created_dict, dict) and "date-time" in created_dict:
            dt_str = str(created_dict["date-time"])
            updated_str = dt_str.split("T")[0]
        elif isinstance(item.get("updated"), str):
            updated_str = str(item["updated"]).strip()

        # 8. URLs and comments
        url = str(item.get("URL") or item.get("abs_url") or f"https://doi.org/{paper_id}").strip()
        pdf_url = str(item.get("pdf_url") or url).strip()
        comment = str(item.get("comment") or f"Crossref record {paper_id}").strip()

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published_str,
                updated=updated_str,
                abs_url=url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch source records from Crossref API with offline snapshot fallback (Dual-Mode).

    1. If API is reachable and refresh_source is True, query Crossref REST API.
    2. On network failure, HTTP 429/5xx, or when offline snapshot exists and refresh_source is False,
       fall back to reading data/raw/crossref_response.json.
    3. Save raw response and parsed records artifacts.
    """
    raw_api_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json

    payload: dict | None = None

    if settings.refresh_source:
        try:
            url = "https://api.crossref.org/works"
            params = {
                "query": settings.source_query,
                "filter": settings.source_filter,
                "rows": settings.max_results,
            }
            headers = {"User-Agent": "DataObservabilityLab/1.0 (mailto:lab@example.com)"}

            logger.info("Fetching Crossref records online: query=%s, filter=%s", settings.source_query, settings.source_filter)
            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                payload = response.json()
                raw_api_path.parent.mkdir(parents=True, exist_ok=True)
                with open(raw_api_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            else:
                logger.warning("Crossref API returned HTTP %d. Switching to dual-mode offline rescue.", response.status_code)
        except Exception as exc:
            logger.warning("Failed to reach Crossref API (%s). Switching to dual-mode offline rescue.", exc)

    if payload is None:
        if raw_api_path.exists():
            logger.info("Reading offline snapshot from %s", raw_api_path)
            with open(raw_api_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            raise FileNotFoundError(
                f"Cannot fetch live records and raw response snapshot is missing at {raw_api_path}"
            )

    records = parse_crossref_payload(payload)

    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_records_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Read JSON snapshot and map items to list[PaperRecord]."""
    if not path.exists():
        raise FileNotFoundError(f"Raw records file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [PaperRecord(**item) for item in data]

