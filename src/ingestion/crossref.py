from __future__ import annotations
from dataclasses import dataclass
import dataclasses
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path

from core.config import Settings


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_JATS_TAG_RE = re.compile(r"</?[a-z][a-z0-9]*(?::[a-z][a-z0-9]*)?\s*>", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _strip_jats(text: str) -> str:
    """Remove JATS/XML tags and normalise whitespace."""
    if not text:
        return ""
    return _WS_RE.sub(" ", _JATS_TAG_RE.sub("", text)).strip()


def _parse_date_parts(date_field: dict | None) -> str:
    """Extract ISO date string from Crossref date-parts structure."""
    if not date_field:
        return ""
    parts = date_field.get("date-parts")
    if not parts or not parts[0]:
        return ""
    y, m, d = parts[0][0], parts[0][1] if len(parts[0]) > 1 else 1, parts[0][2] if len(parts[0]) > 2 else 1
    return f"{y:04d}-{m:02d}-{d:02d}"


# ---------------------------------------------------------------------------
# parse_crossref_payload
# ---------------------------------------------------------------------------

def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref API payload into a list of PaperRecord."""
    records: list[PaperRecord] = []
    items = payload.get("message", {}).get("items", [])

    for item in items:
        doi = (item.get("DOI") or "").strip().lower()
        if not doi:
            continue

        # Title — take first entry, normalise whitespace
        raw_titles: list[str] = item.get("title") or []
        title = _WS_RE.sub(" ", " ".join(raw_titles).replace("\n", " ")).strip()

        # Abstract — strip JATS / XML markup
        summary = _strip_jats(item.get("abstract") or "")

        # Authors — "Given Family" format
        authors: list[str] = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in item.get("author") or []
        ]

        # Categories (subject)
        categories: list[str] = item.get("subject") or []

        # Published date
        published = _parse_date_parts(item.get("published"))
        if not published:
            published = _parse_date_parts(item.get("created"))

        # Updated date — use created["date-time"]
        created_dt = item.get("created", {}).get("date-time") or ""
        updated = created_dt[:10] if created_dt else ""

        # URLs — Crossref snapshot provides abs URL only; pdf_url falls back to it
        abs_url = item.get("URL") or ""
        pdf_url = item.get("URL") or ""

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment="",
            )
        )

    return records


# ---------------------------------------------------------------------------
# fetch_source_records — Dual-Mode: online → fallback → offline snapshot
# ---------------------------------------------------------------------------

def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Call Crossref API, persist raw response, parse to PaperRecord.

    Retry loop:
      - HTTP 429  → wait and retry (up to 3 attempts)
      - HTTP 503  → wait and retry (up to 3 attempts)
      - Other HTTP error / network failure → immediately fall back to snapshot

    Falls back to the bundled snapshot at ``settings.paths.raw_api_response``
    (data/raw/crossref_response.json) so the pipeline can continue offline.
    """
    snapshot_path = settings.paths.raw_api_response
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    api_url = f"https://api.crossref.org/works?{query_string}"

    raw_payload: dict | None = None
    used_fallback = False

    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                api_url,
                headers={"User-Agent": "K4DataPipeline/1.0 (mailto:pipeline@example.com)"},
            )
            with urllib.request.urlopen(request, timeout=30) as resp:
                if resp.status == 200:
                    raw_payload = json.loads(resp.read())
                    break  # success
                if resp.status in (429, 503):
                    wait = 2 ** attempt  # 2, 4, 8 seconds
                    print(f"[crossref] HTTP {resp.status} on attempt {attempt}; "
                          f"waiting {wait}s before retry.")
                    time.sleep(wait)
                    continue
                # unexpected 4xx/5xx
                print(f"[crossref] HTTP {resp.status} on attempt {attempt}; "
                      "falling back to snapshot.")
                used_fallback = True
                break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            print(f"[crossref] Network error ({exc}) on attempt {attempt}; "
                  "falling back to snapshot.")
            used_fallback = True
            break

    # --- Dual-Mode fallback ---
    if raw_payload is None:
        if snapshot_path.exists():
            with open(snapshot_path, encoding="utf-8") as f:
                raw_payload = json.load(f)
            used_fallback = True
            n = len(raw_payload.get("message", {}).get("items", []))
            print(f"[crossref] Loaded {n} items from snapshot: {snapshot_path}")
        else:
            raise RuntimeError(
                f"[crossref] API unavailable and no snapshot found at {snapshot_path}"
            )

    # Persist (always overwrite with whatever we used)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, indent=2, ensure_ascii=False)

    # Parse and persist records
    records = parse_crossref_payload(raw_payload)
    records_path = settings.paths.raw_records_json
    records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2, ensure_ascii=False)

    n_items = len(raw_payload.get("message", {}).get("items", []))
    print(f"[crossref] {n_items} raw items → {len(records)} PaperRecord "
          f"({'fallback' if used_fallback else 'live API'}); "
          f"saved to {records_path}")
    return records


# ---------------------------------------------------------------------------
# load_raw_records
# ---------------------------------------------------------------------------

def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load a JSON snapshot and map it back to PaperRecord objects."""
    if not path.exists():
        raise FileNotFoundError(f"No records file at {path}")

    with open(path, encoding="utf-8") as f:
        raw: list[dict] = json.load(f)

    def _to_paper_record(d: dict) -> PaperRecord:
        return PaperRecord(
            paper_id=d["paper_id"],
            title=d["title"],
            summary=d["summary"],
            authors=d["authors"],
            categories=d["categories"],
            primary_category=d["primary_category"],
            published=d["published"],
            updated=d["updated"],
            abs_url=d["abs_url"],
            pdf_url=d["pdf_url"],
            comment=d["comment"],
        )

    return [_to_paper_record(d) for d in raw]
