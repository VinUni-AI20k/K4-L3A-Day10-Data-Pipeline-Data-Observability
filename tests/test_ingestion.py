from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json

import pytest
import requests

from core.utils import compact_join, first_sentence, normalize_whitespace, read_json, safe_slug, write_json
from ingestion.cleaning import build_clean_dataframe, compose_text_for_embedding
from ingestion.crossref import (
    CrossrefUnavailable,
    PaperRecord,
    fetch_source_records,
    load_raw_records,
    parse_crossref_payload,
)
from ingestion.repair import repair_from_raw


def _item(**overrides):
    item = {
        "DOI": "https://doi.org/10.1000/Example.",
        "title": ["  Hello   World  "],
        "abstract": "<jats:p>A &amp; B study of retrieval systems.</jats:p>",
        "author": [
            {"given": "Ada", "family": "Lovelace"},
            {"name": "Alan Turing"},
            "Grace Hopper",
            12,
            "",
        ],
        "subject": [" Machine Learning ", "Machine Learning", "", "Databases"],
        "published": {"date-parts": [[2026, 5]]},
        "updated": {"date-time": "2026-06-02T00:00:00Z"},
        "URL": " https://doi.org/10.1000/Example ",
        "link": [
            "skip",
            {"URL": ""},
            {"URL": " https://example.com/landing "},
            {"URL": "https://example.com/paper.pdf", "content-type": "application/pdf"},
        ],
    }
    item.update(overrides)
    return item


def test_parse_crossref_payload_normalizes_fields():
    records = parse_crossref_payload(
        {
            "message": {
                "items": [
                    _item(),
                    _item(),
                    "not-a-record",
                    {"title": ["Missing DOI"]},
                    {"DOI": "10.1000/only-year", "title": "Plain Title", "abstract": "Year only abstract is long enough.", "author": None, "subject": "IR"},
                    {
                        "DOI": "10.1000/created",
                        "title": ["Created Date", "Ignored Subtitle"],
                        "abstract": "<jats:p>Created abstract is long enough.</jats:p>",
                        "created": {"date-time": "2024-02-03T01:02:03Z"},
                        "link": [{"URL": "https://example.com/no-pdf"}],
                    },
                    {"DOI": "10.1000/no-abstract", "title": ["Missing Abstract"]},
                ]
            }
        }
    )

    assert [record.paper_id for record in records] == [
        "10.1000/Example",
        "10.1000/only-year",
        "10.1000/created",
    ]
    first = records[0]
    assert first.title == "Hello World"
    assert first.summary == "A & B study of retrieval systems."
    assert first.authors == ["Ada Lovelace", "Alan Turing", "Grace Hopper"]
    assert first.categories == ["Machine Learning", "Databases"]
    assert first.primary_category == "Machine Learning"
    assert first.published == "2026-05-01"
    assert first.updated == "2026-06-02"
    assert first.pdf_url == "https://example.com/paper.pdf"
    assert "<jats" not in first.summary

    created = records[2]
    assert created.title == "Created Date"
    assert created.published == "2024-02-03"
    assert created.abs_url == "https://doi.org/10.1000/created"
    assert created.pdf_url == "https://example.com/no-pdf"
    assert created.primary_category == ""


def test_parse_rejects_payloads_without_items():
    assert parse_crossref_payload({}) == []
    assert parse_crossref_payload({"message": {}}) == []
    assert parse_crossref_payload({"message": {"items": "nope"}}) == []


def test_load_raw_records_from_list(tmp_path):
    record = _record("10.1000/Loaded", "Loaded Title", "2026-01-02")
    records_path = tmp_path / "records.json"
    write_json(records_path, [asdict(record)])
    loaded = load_raw_records(records_path)
    assert loaded == [record]

    other = tmp_path / "other.json"
    write_json(other, {"message": {"items": []}})
    with pytest.raises(ValueError):
        load_raw_records(other)


def test_fetch_offline_reads_snapshot_without_rewriting_raw_files(settings, monkeypatch):
    raw_text = json.dumps({"message": {"items": [_item()]}}, indent=2)
    settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_api_response.write_text(raw_text, encoding="utf-8")

    def fail_get(*args, **kwargs):
        raise AssertionError("offline mode must not call the API")

    monkeypatch.setattr("ingestion.crossref.requests.get", fail_get)
    records = fetch_source_records(settings)
    assert records[0].paper_id == "10.1000/Example"
    assert settings.paths.raw_api_response.read_text(encoding="utf-8") == raw_text
    assert not settings.paths.raw_records_json.exists()


def test_fetch_falls_back_to_snapshot_on_429(settings, monkeypatch):
    write_json(settings.paths.raw_api_response, {"message": {"items": [_item()]}})
    calls = {"count": 0}

    class Response:
        status_code = 429

        def raise_for_status(self):
            raise requests.HTTPError("429")

        def json(self):
            return {}

    def get(*args, **kwargs):
        calls["count"] += 1
        return Response()

    monkeypatch.setattr("ingestion.crossref.requests.get", get)
    monkeypatch.setattr("ingestion.crossref.time.sleep", lambda *_args, **_kwargs: None)
    refreshed = replace(settings, refresh_source=True)
    records = fetch_source_records(refreshed)
    assert calls["count"] == 3
    assert records[0].paper_id == "10.1000/Example"
    assert load_raw_records(settings.paths.raw_records_json)[0].paper_id == "10.1000/Example"


def test_fetch_saves_live_payload_and_retries_transport_errors(settings, monkeypatch):
    payload = {"message": {"items": [_item(DOI="10.1000/live", title=["Live Paper"])]}}
    calls = {"count": 0}

    class Response:
        status_code = 200
        text = json.dumps(payload)

        def raise_for_status(self):
            return None

    def get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.ConnectionError("offline")
        return Response()

    monkeypatch.setattr("ingestion.crossref.requests.get", get)
    monkeypatch.setattr("ingestion.crossref.time.sleep", lambda *_args, **_kwargs: None)
    records = fetch_source_records(replace(settings, refresh_source=True))
    assert records[0].paper_id == "10.1000/live"
    saved = read_json(settings.paths.raw_api_response)
    assert saved["message"]["items"][0]["DOI"] == "10.1000/live"


def test_fetch_uses_snapshot_when_live_payload_is_empty_or_invalid(settings, monkeypatch):
    write_json(settings.paths.raw_api_response, {"message": {"items": [_item()]}})

    class EmptyResponse:
        status_code = 200
        text = '{"message": {"items": []}}'

        def raise_for_status(self):
            return None

    monkeypatch.setattr("ingestion.crossref.requests.get", lambda *args, **kwargs: EmptyResponse())
    records = fetch_source_records(replace(settings, refresh_source=True))
    assert records[0].paper_id == "10.1000/Example"

    class BadJson:
        status_code = 200
        text = "not-json"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("ingestion.crossref.requests.get", lambda *args, **kwargs: BadJson())
    monkeypatch.setattr("ingestion.crossref.time.sleep", lambda *_args, **_kwargs: None)
    records = fetch_source_records(replace(settings, refresh_source=True))
    assert records[0].paper_id == "10.1000/Example"


def test_fetch_raises_when_api_and_snapshot_are_unavailable(settings, monkeypatch):
    monkeypatch.setattr(
        "ingestion.crossref.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError("down")),
    )
    monkeypatch.setattr("ingestion.crossref.time.sleep", lambda *_args, **_kwargs: None)
    with pytest.raises(CrossrefUnavailable):
        fetch_source_records(replace(settings, refresh_source=True))

    write_json(settings.paths.raw_api_response, ["not", "a", "payload"])
    monkeypatch.setattr(
        "ingestion.crossref._fetch_crossref_text",
        lambda _settings: (_ for _ in ()).throw(CrossrefUnavailable("429")),
    )
    with pytest.raises(CrossrefUnavailable):
        fetch_source_records(replace(settings, refresh_source=True))


def test_checked_in_snapshot_parses_to_24_records():
    from core.config import load_settings

    project = load_settings()
    records = parse_crossref_payload(read_json(project.paths.raw_api_response))
    assert len(records) == 24
    assert all(record.paper_id and record.title and record.summary for record in records)


def _record(paper_id: str, title: str, published: str, **kwargs) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        summary=kwargs.get("summary", "A sufficiently long summary about retrieval augmented generation."),
        authors=kwargs.get("authors", ["Ada Lovelace"]),
        categories=kwargs.get("categories", ["Artificial Intelligence"]),
        primary_category=kwargs.get("primary_category", "Artificial Intelligence"),
        published=published,
        updated=kwargs.get("updated", published),
        abs_url=kwargs.get("abs_url", f"https://doi.org/{paper_id}"),
        pdf_url=kwargs.get("pdf_url", f"https://doi.org/{paper_id}"),
        comment=kwargs.get("comment", f"Crossref record {paper_id}"),
    )


def test_build_clean_dataframe_matches_schema(run_date):
    frame = build_clean_dataframe(
        [
            _record("10.1000/b", "  Older   Title ", "2026-01-01", summary="  <jats:p>Older summary stays long enough.</jats:p>  "),
            _record("10.1000/a", "Newer Title", "2026-06-01"),
            _record("10.1000/a", "Duplicate Title", "2026-06-01"),
            _record("10.1000/c", "Same Day B", "2026-06-01"),
            _record("", "Missing Id", "2026-06-01"),
            _record("10.1000/d", "   ", "2026-06-01"),
            _record("10.1000/e", "Missing Date", ""),
        ],
        run_date,
    )
    assert list(frame["paper_id"]) == ["10.1000/a", "10.1000/c", "10.1000/b"]
    assert frame.iloc[0]["title"] == "Newer Title"
    assert frame.iloc[2]["summary"] == "Older summary stays long enough."
    assert frame.iloc[2]["age_days"] == (run_date.date() - datetime(2026, 1, 1).date()).days
    assert frame.iloc[0]["text_for_embedding"] == compose_text_for_embedding(frame.iloc[0].to_dict())
    assert frame.iloc[0]["text_for_embedding"].splitlines() == [
        "Title: Newer Title",
        "Authors: Ada Lovelace",
        "Published: 2026-06-01",
        "Categories: Artificial Intelligence",
        "Summary: A sufficiently long summary about retrieval augmented generation.",
    ]
    assert frame["summary_chars"].tolist()[0] == len(frame.iloc[0]["summary"])


def test_build_clean_dataframe_is_empty_without_usable_rows(run_date):
    frame = build_clean_dataframe([_record("10.1000/x", "", "2026-01-01")], run_date)
    assert frame.empty


def test_compose_text_for_embedding_fills_missing_fields():
    text = compose_text_for_embedding({})
    assert text == "Title: \nAuthors: \nPublished: \nCategories: \nSummary: "


def test_repair_from_raw_is_idempotent_and_ignores_clean_edits(settings, run_date):
    write_json(
        settings.paths.raw_records_json,
        [
            asdict(_record("10.1000/raw", "Raw Title", "2026-03-01")),
            asdict(_record("10.1000/newer", "Newer Raw", "2026-08-01")),
        ],
    )
    settings.paths.clean_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.clean_json.write_text('[{"paper_id": "corrupted"}]', encoding="utf-8")

    first = repair_from_raw(settings, run_date)
    csv_hash = hashlib.sha256(settings.paths.repaired_clean_csv.read_bytes()).hexdigest()
    json_hash = hashlib.sha256(settings.paths.repaired_clean_json.read_bytes()).hexdigest()
    second = repair_from_raw(settings, run_date)
    baseline = build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), run_date)
    assert first["paper_id"].tolist() == ["10.1000/newer", "10.1000/raw"]
    assert first.equals(second)
    assert first.equals(baseline)
    assert hashlib.sha256(settings.paths.repaired_clean_csv.read_bytes()).hexdigest() == csv_hash
    assert hashlib.sha256(settings.paths.repaired_clean_json.read_bytes()).hexdigest() == json_hash
    assert "corrupted" not in set(first["paper_id"])
    assert "corrupted" not in settings.paths.repaired_clean_json.read_text(encoding="utf-8")


def test_repair_from_raw_requires_raw_records(settings, run_date):
    with pytest.raises(FileNotFoundError):
        repair_from_raw(settings, run_date)


def test_text_helpers_used_by_ingestion():
    assert normalize_whitespace("  a \n b\t") == "a b"
    assert safe_slug("Hello, World!") == "hello-world"
    assert safe_slug("***") == "item"
    assert compact_join(["A", "", "B"]) == "A, B"
    assert first_sentence("First. Second.") == "First."
    assert first_sentence("") == ""
