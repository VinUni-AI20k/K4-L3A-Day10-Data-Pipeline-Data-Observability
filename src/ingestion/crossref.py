from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from dataclasses import dataclass, asdict
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


def _fallback_categories(item: dict) -> list[str]:
    # Crossref no longer returns `subject` for most works, which left every paper with no
    # categories (and unanswerable `categories` eval questions). Fall back to venue + work type.
    venue = " ".join((item.get("container-title") or [""])[0].split())
    return [value for value in (venue, item.get("type", "")) if value]


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    records = []
    items = payload.get("message", {}).get("items", [])
    for item in items:
        paper_id = item.get("DOI", "")
        if not paper_id:
            continue
            
        raw_title = item.get("title", [""])[0] if item.get("title") else ""
        title = " ".join(raw_title.split())
        
        raw_summary = item.get("abstract", "")
        summary = re.sub(r'<[^>]+>', '', raw_summary)
        summary = " ".join(summary.split())
        
        authors = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)
                
        categories = item.get("subject") or _fallback_categories(item)
        primary_category = categories[0] if categories else ""
        
        pub_date_parts = item.get("published", {}).get("date-parts", [[]])[0]
        try:
            if len(pub_date_parts) == 3:
                published = f"{pub_date_parts[0]:04d}-{pub_date_parts[1]:02d}-{pub_date_parts[2]:02d}T00:00:00Z"
            elif len(pub_date_parts) == 2:
                published = f"{pub_date_parts[0]:04d}-{pub_date_parts[1]:02d}-01T00:00:00Z"
            elif len(pub_date_parts) == 1:
                published = f"{pub_date_parts[0]:04d}-01-01T00:00:00Z"
            else:
                published = "1970-01-01T00:00:00Z"
        except Exception:
            published = "1970-01-01T00:00:00Z"
            
        updated = item.get("created", {}).get("date-time", published)
        abs_url = item.get("URL", "")
        pdf_url = ""
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL", "")
                break
                
        records.append(PaperRecord(
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
            comment=""
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    try:
        url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        
        settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
        with open(settings.paths.raw_api_response, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"Crossref API failed ({e}), falling back to offline snapshot.")
        if settings.paths.raw_api_response.exists():
            with open(settings.paths.raw_api_response, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = {}

    records = parse_crossref_payload(payload)
    
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.paths.raw_records_json, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2)
        
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [PaperRecord(**d) for d in data]
