"""Tests for core/config.py and core/utils.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.config import load_settings
from core.utils import (
    first_sentence,
    normalize_whitespace,
    read_json,
    safe_slug,
    write_json,
    write_text,
)


# ── utils ────────────────────────────────────────────────────────────────────

def test_normalize_whitespace_collapses_spaces():
    assert normalize_whitespace("hello   world") == "hello world"


def test_normalize_whitespace_strips():
    assert normalize_whitespace("  hi  ") == "hi"


def test_normalize_whitespace_newlines():
    assert normalize_whitespace("a\nb\tc") == "a b c"


def test_first_sentence_period():
    assert first_sentence("Hello world. Second sentence.") == "Hello world."


def test_first_sentence_no_period():
    text = "No period here"
    assert first_sentence(text) == text


def test_first_sentence_empty():
    assert first_sentence("") == ""


def test_write_and_read_json(tmp_path):
    data = {"key": "value", "num": 42}
    path = tmp_path / "test.json"
    write_json(path, data)
    loaded = read_json(path)
    assert loaded == data


def test_write_text(tmp_path):
    path = tmp_path / "test.txt"
    write_text(path, "hello\nworld")
    assert path.read_text() == "hello\nworld"


def test_safe_slug_removes_special_chars():
    slug = safe_slug("Hello World! Test/Paper")
    assert " " not in slug
    assert "!" not in slug
    assert "/" not in slug


def test_safe_slug_lowercase():
    assert safe_slug("ABC") == safe_slug("ABC").lower()


def test_read_json_missing_file_raises(tmp_path):
    with pytest.raises(Exception):
        read_json(tmp_path / "nonexistent.json")


# ── config ───────────────────────────────────────────────────────────────────

def test_load_settings_returns_settings():
    settings = load_settings()
    assert settings is not None
    assert hasattr(settings, "llm_provider")
    assert hasattr(settings, "paths")
    assert hasattr(settings, "top_k")
    assert hasattr(settings, "freshness_threshold_days")


def test_load_settings_paths_exist_or_are_paths():
    settings = load_settings()
    assert isinstance(settings.paths.clean_json, Path)
    assert isinstance(settings.paths.quality_dir, Path)
    assert isinstance(settings.paths.baseline_metrics, Path)


def test_load_settings_default_freshness_threshold():
    settings = load_settings()
    assert settings.freshness_threshold_days == 180


def test_load_settings_default_top_k():
    settings = load_settings()
    assert settings.top_k > 0


def test_load_settings_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    settings = load_settings()
    assert settings.llm_provider == "mock"
