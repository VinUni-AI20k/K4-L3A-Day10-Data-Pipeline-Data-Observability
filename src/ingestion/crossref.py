from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


from core.config import Settings


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


def _clean_html(text: str) -> str:
    """Helper method: Xóa các thẻ HTML/XML (VD: <jats:p>)."""
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def _parse_crossref_date(date_obj: dict | None) -> str:
    """Helper method: Trích xuất ngày từ cấu trúc date-parts của Crossref."""
    if not date_obj or "date-parts" not in date_obj:
        return ""
    parts = date_obj["date-parts"][0]
    # Format thành YYYY-MM-DD
    return "-".join(f"{p:02d}" for p in parts)


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thành list PaperRecord."""
    records = []
    items = payload.get("message", {}).get("items", [])

    for item in items:
        # Bỏ qua nếu thiếu ID (DOI) hoặc Tiêu đề
        paper_id = item.get("DOI")
        title_list = item.get("title", [])
        if not paper_id or not title_list:
            continue
            
        title = title_list[0]
        summary = _clean_html(item.get("abstract", ""))
        
        # Xử lý Authors
        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            full_name = f"{given} {family}".strip()
            if full_name:
                authors.append(full_name)
                
        # Xử lý Categories
        categories = item.get("subject", [])
        primary_category = categories[0] if categories else ""
        
        # Xử lý Dates
        published = _parse_crossref_date(item.get("published-print") or item.get("created"))
        updated = _parse_crossref_date(item.get("deposited") or item.get("indexed"))
        
        # Xử lý URLs
        abs_url = item.get("URL", "")
        pdf_url = ""
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL", "")
                break
                
        comment = item.get("publisher", "")

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
            comment=comment
        ))
        
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Gọi source API, lưu raw response, parse thành records."""
    
    # 1. Tạo session với cơ chế Retry cho các mã lỗi 429, 500, 502, 503, 504
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=2, # Thời gian chờ: 2, 4, 8 giây
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Cấu hình API Request
    url = "https://api.crossref.org/works"
    params = {
        "query": settings.source_query,
        "rows": getattr(settings, "max_results", 100),
    }
    if hasattr(settings, "source_filter") and settings.source_filter:
        params["filter"] = settings.source_filter

    headers = {"User-Agent": "MyPaperDataPipeline/1.0"}

    # 2. Gọi API
    print(f"Fetching data from Crossref API...")
    response = session.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    payload = response.json()

    # 3. Lưu raw response vào settings.paths.raw_api_response
    raw_api_path = Path(settings.paths.raw_api_response)
    raw_api_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_api_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 4. Parse payload
    records = parse_crossref_payload(payload)

    # 5. Lưu records vào settings.paths.raw_records_json
    raw_records_path = Path(settings.paths.raw_records_json)
    raw_records_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Biến đổi list dataclass thành list dict trước khi lưu
    records_dict = [asdict(record) for record in records]
    with open(raw_records_path, "w", encoding="utf-8") as f:
        json.dump(records_dict, f, ensure_ascii=False, indent=2)

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Đọc JSON snapshot và map thành PaperRecord."""
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file snapshot tại: {path}")
        
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Chuyển đổi từng dict thành instance của PaperRecord
    return [PaperRecord(**record) for record in data]