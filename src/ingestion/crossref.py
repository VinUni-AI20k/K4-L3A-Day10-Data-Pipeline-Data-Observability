from __future__ import annotations

from dataclasses import asdict, dataclass
import html
import json
import logging
from pathlib import Path
import re
import time
from typing import Any
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


def clean_xml_and_whitespace(text: str) -> str:
    """Clean XML/HTML tags, unescape entities, and normalize whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def standardize_summary(text: str) -> str:
    """Automated summary standardization:
    - Strips XML/HTML tags and unescapes entities.
    - Automatically detects bilingual abstracts (e.g. Cyrillic + English) and extracts the English text.
    - Strips common boilerplate prefixes ('Abstract:', 'Summary:', 'Abstract - ').
    """
    cleaned = clean_xml_and_whitespace(text)
    if not cleaned:
        return ""

    # Tu dong phat hien doan tom tat song ngu (VD: tieng Nga + tieng Anh) de lay phan tieng Anh cho mo hinh embedding
    if re.search(r"[\u0400-\u04FF]", cleaned):
        english_match = re.search(
            r"(\b(?:The article|This paper|In this paper|This study|This review|We examine|We propose)\b[\s\S]+)",
            cleaned,
            re.IGNORECASE,
        )
        if english_match and len(english_match.group(1).strip()) >= 50:
            cleaned = english_match.group(1).strip()

    # Loai bo cac boilerplate prefix pho bien o dau tom tat
    cleaned = re.sub(r"^(?:Abstract\s*[:\-–—]\s*|Summary\s*[:\-–—]\s*)", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def standardize_author_name(name: str) -> str:
    """Clean and normalize author name (remove trailing hyphens, extraneous punctuation)."""
    cleaned = clean_xml_and_whitespace(name)
    cleaned = re.sub(r"[\s\-–—]+$", "", cleaned).strip()
    return cleaned


def infer_and_standardize_categories(title: str, summary: str, raw_subjects: list[str]) -> list[str]:
    """Automated rule-based domain taxonomy inference for papers with missing or unstandardized categories.
    Scales automatically to hundreds or thousands of papers without manual curation.
    """
    valid_subjects: list[str] = []
    for s in raw_subjects:
        cs = clean_xml_and_whitespace(str(s))
        if cs:
            valid_subjects.append(cs)

    if valid_subjects:
        return valid_subjects

    combined = f"{title} {summary}".lower()
    inferred: list[str] = []

    if any(k in combined for k in ["retrieval", "rag", "search", "ranking", "bm25", "index", "vector"]):
        inferred.append("Information Retrieval")

    if any(k in combined for k in ["agent", "agentic", "autonomous", "multi-agent", "reinforcement learning"]):
        inferred.append("Artificial Intelligence")

    if any(k in combined for k in ["language model", "llm", "nlp", "text generation", "transformer", "prompt"]):
        if "Artificial Intelligence" not in inferred:
            inferred.append("Artificial Intelligence")
        inferred.append("Natural Language Processing")

    if any(k in combined for k in ["observability", "data quality", "governance", "database", "pipeline", "compliance", "software"]):
        inferred.append("Data Systems")

    if any(k in combined for k in ["medical", "clinical", "health", "doctor"]):
        inferred.append("Medical Informatics")

    if not inferred:
        inferred = ["Artificial Intelligence", "Computer Science"]

    return inferred


def _extract_date(date_dict: Any) -> str:
    """Extract YYYY-MM-DD from Crossref date structure."""
    if not date_dict:
        return ""
    if isinstance(date_dict, str):
        match = re.search(r"\d{4}-\d{2}-\d{2}", date_dict)
        if match:
            return match.group(0)
        return date_dict.strip()
    if isinstance(date_dict, dict):
        date_parts = date_dict.get("date-parts", [])
        if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
            parts = date_parts[0]
            if isinstance(parts, list) and len(parts) > 0:
                year = parts[0]
                month = parts[1] if len(parts) > 1 else 1
                day = parts[2] if len(parts) > 2 else 1
                try:
                    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                except (ValueError, TypeError):
                    pass
        date_time = date_dict.get("date-time", "")
        if date_time and isinstance(date_time, str):
            return date_time.split("T")[0]
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord voi quy trinh chuan hoa tu dong."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        msg = payload.get("message", {})
        if isinstance(msg, dict):
            items = msg.get("items", [])
        elif "items" in payload:
            items = payload.get("items", [])
        else:
            items = []
    else:
        items = []

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = str(item.get("DOI", "")).strip()
        if not paper_id:
            continue

        # De-duplicate by DOI
        if paper_id.lower() in seen_ids:
            continue
        seen_ids.add(paper_id.lower())

        # Title
        raw_title = item.get("title", [])
        if isinstance(raw_title, list):
            title_str = raw_title[0] if raw_title else ""
        else:
            title_str = str(raw_title or "")
        title = clean_xml_and_whitespace(title_str)
        if not title:
            continue

        # Summary / Abstract (automated standardization)
        abstract_raw = item.get("abstract", "") or item.get("summary", "")
        summary = standardize_summary(str(abstract_raw))
        if not summary:
            continue

        # Authors (automated standardization)
        authors: list[str] = []
        raw_authors = item.get("author", [])
        if isinstance(raw_authors, list):
            for a in raw_authors:
                if isinstance(a, dict):
                    given = str(a.get("given", "")).strip()
                    family = str(a.get("family", "")).strip()
                    name = f"{given} {family}".strip() or str(a.get("name", "")).strip()
                    if name:
                        authors.append(standardize_author_name(name))
                elif isinstance(a, str) and a.strip():
                    authors.append(standardize_author_name(a))

        # Categories / Subjects (automated inference if missing)
        raw_subjects = item.get("subject", []) or item.get("categories", [])
        if not isinstance(raw_subjects, list):
            raw_subjects = []
        categories = infer_and_standardize_categories(title, summary, raw_subjects)
        primary_category = categories[0] if categories else "General"

        # Published date
        published = (
            _extract_date(item.get("published"))
            or _extract_date(item.get("created"))
            or _extract_date(item.get("issued"))
        )
        if not published:
            published = time.strftime("%Y-%m-%d")

        # Updated date
        created_dt = item.get("created", {})
        if isinstance(created_dt, dict) and "date-time" in created_dt:
            updated = str(created_dt["date-time"]).split("T")[0]
        else:
            updated = _extract_date(item.get("updated")) or published

        # URLs
        url = str(item.get("URL", "")).strip() or f"https://doi.org/{paper_id}"
        abs_url = url
        pdf_url = url

        comment = f"Crossref record {paper_id}"

        record = PaperRecord(
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
        records.append(record)

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.

    Co che Dual-Mode (Live API hoac Snapshot Offline):
    - Neu refresh_source=True hoac file raw chua ton tai: goi Crossref REST API truc tiep.
    - Neu gap su co mang / 429: tu dong fallback ve snapshot offline data/raw/crossref_response.json.
    - Luu raw response vao settings.paths.raw_api_response.
    - Parse payload va luu records vao settings.paths.raw_records_json.
    """
    raw_api_path = settings.paths.raw_api_response
    raw_records_path = settings.paths.raw_records_json

    raw_api_path.parent.mkdir(parents=True, exist_ok=True)
    raw_records_path.parent.mkdir(parents=True, exist_ok=True)

    payload: dict | None = None

    # 1. Che do Offline / Dev: load tu snapshot da co neu khong yeu cau refresh
    if not settings.refresh_source and raw_api_path.exists():
        try:
            with open(raw_api_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            logger.info("Loaded Crossref payload from local snapshot: %s", raw_api_path)
        except Exception as e:
            logger.warning("Failed to load local snapshot: %s. Falling back to live API.", e)
            payload = None

    # 2. Che do Live API: goi truc tiep Crossref REST API
    if payload is None:
        api_url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {
            "User-Agent": "DataPipelineLab/1.0 (mailto:lab@vinuni.edu.vn)",
            "Accept": "application/json",
        }

        max_retries = 3
        backoff_sec = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "Fetching papers from Crossref API (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    api_url,
                )
                response = requests.get(api_url, params=params, headers=headers, timeout=15)
                if response.status_code == 200:
                    payload = response.json()
                    with open(raw_api_path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2, ensure_ascii=False)
                    logger.info("Successfully fetched and saved raw response to %s", raw_api_path)
                    break
                elif response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Crossref API returned status %d. Retrying in %.1fs...",
                        response.status_code,
                        backoff_sec,
                    )
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                else:
                    logger.error(
                        "Crossref API returned unexpected status %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    break
            except Exception as exc:
                logger.warning("Error connecting to Crossref API: %s. Retrying in %.1fs...", exc, backoff_sec)
                time.sleep(backoff_sec)
                backoff_sec *= 2

        # 3. Fallback neu Live API khong thanh cong
        if payload is None:
            if raw_api_path.exists():
                logger.warning("Live API failed. Falling back to existing offline snapshot: %s", raw_api_path)
                with open(raw_api_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            else:
                backup_snapshot = raw_api_path.parent / "backup" / "crossref_response.json"
                if backup_snapshot.exists():
                    logger.warning("Falling back to backup snapshot: %s", backup_snapshot)
                    with open(backup_snapshot, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    with open(raw_api_path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2, ensure_ascii=False)
                else:
                    raise RuntimeError("Failed to fetch from Crossref API and no offline snapshot found.")

    records = parse_crossref_payload(payload)

    # Ghi de / luu danh sach records vao raw_records_json
    with open(raw_records_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2, ensure_ascii=False)
    logger.info("Saved %d parsed records to %s", len(records), raw_records_path)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    if not path.exists():
        raise FileNotFoundError(f"Raw records file not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [PaperRecord(**item) for item in data]
    elif isinstance(data, dict):
        return parse_crossref_payload(data)
    else:
        raise ValueError(f"Unsupported format in {path}: expected list or dict.")
