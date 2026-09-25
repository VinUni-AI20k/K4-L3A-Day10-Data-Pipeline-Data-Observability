from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
import json
from pathlib import Path
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Extract usable paper metadata without modifying the preserved API response."""
    items = payload.get("message", {}).get("items", [])
    if not isinstance(items, list):
        raise ValueError("Crossref payload has no message.items list.")

    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in items:
        doi = normalize_whitespace(str(item.get("DOI") or "")).lower()
        title_values = item.get("title") or []
        title = _plain_text(title_values[0] if title_values else "")
        summary = _plain_text(item.get("abstract") or "")
        authors = []
        for author in item.get("author") or []:
            personal_name = " ".join(
                str(author.get(key) or "") for key in ("given", "family")
            ).strip()
            name = normalize_whitespace(
                personal_name or str(author.get("name") or "")
            )
            if name:
                authors.append(name)

        published = _crossref_date(item.get("published") or item.get("published-online") or item.get("issued"))
        if not doi or doi in seen or not title or len(summary) < 30 or not authors or not published:
            continue

        subjects = [_plain_text(value) for value in item.get("subject") or []]
        subjects = list(dict.fromkeys(value for value in subjects if value))
        categories = subjects or _infer_categories(title, summary)
        deposited = item.get("deposited") or {}
        updated = str(deposited.get("date-time") or "")[:10] or published
        pdf_url = next(
            (
                str(link.get("URL") or "")
                for link in item.get("link") or []
                if "pdf" in str(link.get("content-type") or "").lower()
            ),
            "",
        )
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0],
                published=published,
                updated=updated,
                abs_url=str(item.get("URL") or f"https://doi.org/{doi}"),
                pdf_url=pdf_url,
                comment="categories:Crossref subject" if subjects else "categories:inferred from title/abstract",
            )
        )
        seen.add(doi)
    return records


def _plain_text(value: str) -> str:
    # Crossref abstracts often contain JATS XML and HTML entities.
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", unescape(str(value))))


def _crossref_date(value: dict | None) -> str:
    parts = (value or {}).get("date-parts") or []
    if not parts or not parts[0]:
        return ""
    year, *rest = parts[0]
    month = rest[0] if rest else 1
    day = rest[1] if len(rest) > 1 else 1
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _infer_categories(title: str, summary: str) -> list[str]:
    text = f"{title} {summary}".lower()
    rules = (
        ("Scenario generation", ("scenario generation", "generating scenario", "generated scenario", "generative")),
        ("Scenario-based testing", ("scenario-based", "scenario based", "safety testing", "test scenario")),
        ("Operational design domain", ("operational design domain", "odd")),
        ("Traffic interactions", ("cut-in", "motorcycle", "mixed traffic", "multi-vehicle", "interaction")),
        ("Simulation and validation", ("carla", "openscenario", "simulation", "simulator", "virtual testing")),
        ("Safety-critical cases", ("safety-critical", "hazard", "collision", "risk-driven", "rare traffic")),
        ("Perception", ("perception", "sensor", "lidar", "visual")),
        ("Data and knowledge", ("dataset", "database", "knowledge graph", "data-driven")),
    )
    categories = [label for label, keywords in rules if any(keyword in text for keyword in keywords)]
    return categories or ["Autonomous driving"]


def _selected_dois(settings: Settings) -> list[str]:
    manifest_path = settings.paths.raw_api_response.with_name("adas_selected_dois.json")
    manifest = read_json(manifest_path)
    dois = [entry["doi"].strip().lower() for entry in manifest["selection"]]
    if len(dois) != settings.max_results or len(set(dois)) != len(dois):
        raise ValueError(f"Expected {settings.max_results} unique DOIs in {manifest_path}.")
    return dois


def _records_from_snapshot(path: Path, selected: set[str]) -> list[PaperRecord]:
    if not path.is_file():
        return []
    try:
        payload = read_json(path)
        records = parse_crossref_payload(payload)
    except (OSError, ValueError, TypeError, KeyError):
        return []
    if {record.paper_id for record in records} != selected:
        return []
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch the 24 curated DOIs or use the matching offline Crossref snapshot.

    The API response is written byte-for-byte only after all selected records
    pass validation. A failed refresh leaves the last valid snapshot intact.
    """
    dois = _selected_dois(settings)
    selected = set(dois)
    raw_path = settings.paths.raw_api_response
    if not settings.refresh_source:
        snapshot = _records_from_snapshot(raw_path, selected)
        if snapshot:
            write_json(settings.paths.raw_records_json, [asdict(record) for record in snapshot])
            return snapshot

    retry = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET"},
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    try:
        response = session.get(
            "https://api.crossref.org/works",
            params={"filter": ",".join(f"doi:{doi}" for doi in dois), "rows": len(dois)},
            headers={"User-Agent": "Day10DataPipeline/1.0 (academic metadata research)"},
            timeout=45,
        )
        response.raise_for_status()
        records = parse_crossref_payload(response.json())
        if {record.paper_id for record in records} != selected:
            raise ValueError("Crossref response is incomplete for the selected 24 DOIs.")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(response.content)
        write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
        return records
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        snapshot = _records_from_snapshot(raw_path, selected)
        if not snapshot:
            raise RuntimeError("Crossref unavailable and no valid 24-paper ADAS snapshot exists.") from exc
        write_json(settings.paths.raw_records_json, [asdict(record) for record in snapshot])
        return snapshot
    finally:
        session.close()


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the parsed raw artifact without network access."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of PaperRecord objects in {path}.")
    return [PaperRecord(**item) for item in payload]
