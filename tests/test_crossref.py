"""Tests for ingestion/crossref.py — parse & date helpers."""
from __future__ import annotations

import pytest

from ingestion.crossref import PaperRecord, _parse_date, _strip_jats, parse_crossref_payload


def test_strip_jats_removes_tags():
    raw = "<jats:p>Hello <jats:bold>world</jats:bold></jats:p>"
    assert "<" not in _strip_jats(raw)
    assert "Hello" in _strip_jats(raw)
    assert "world" in _strip_jats(raw)


def test_strip_jats_collapses_whitespace():
    result = _strip_jats("  foo   bar  ")
    assert result == "foo bar"


def test_parse_date_full():
    assert _parse_date([[2026, 3, 15]]) == "2026-03-15"


def test_parse_date_year_month_only():
    assert _parse_date([[2025, 7]]) == "2025-07-01"


def test_parse_date_year_only():
    assert _parse_date([[2024]]) == "2024-01-01"


def test_parse_date_empty():
    assert _parse_date([]) == "1970-01-01"


def _wrap(item: dict) -> dict:
    """Crossref API wraps items under message.items."""
    return {"message": {"items": [item]}}


def test_parse_crossref_payload_skips_no_doi():
    item = {
        "title": ["A Paper"],
        "abstract": "Some abstract text.",
        "author": [],
        "published": {"date-parts": [[2026, 1, 1]]},
        "subject": [],
    }
    assert parse_crossref_payload(_wrap(item)) == []


def test_parse_crossref_payload_skips_no_title():
    item = {
        "DOI": "10.1000/x",
        "abstract": "Some abstract text.",
        "author": [],
        "published": {"date-parts": [[2026, 1, 1]]},
        "subject": [],
    }
    assert parse_crossref_payload(_wrap(item)) == []


def test_parse_crossref_payload_valid():
    item = {
        "DOI": "10.1000/valid",
        "title": ["Valid Paper Title"],
        "abstract": "<jats:p>Valid abstract content here.</jats:p>",
        "author": [{"given": "John", "family": "Doe"}],
        "published": {"date-parts": [[2026, 6, 1]]},
        "subject": ["Computer Science"],
    }
    result = parse_crossref_payload(_wrap(item))
    assert len(result) == 1
    assert result[0].paper_id == "10.1000/valid"
    assert "<" not in result[0].summary
    assert result[0].published == "2026-06-01"
    assert "John Doe" in result[0].authors


def test_paper_record_is_frozen():
    rec = PaperRecord(
        paper_id="10.1/x", title="T", summary="S", authors=[], categories=[],
        primary_category="", published="2026-01-01", updated="2026-01-01",
        abs_url="", pdf_url="", comment="",
    )
    with pytest.raises((AttributeError, TypeError)):
        rec.paper_id = "changed"  # type: ignore[misc]
