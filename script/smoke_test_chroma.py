"""Smoke test: clean -> corrupt -> repair, nap ca 3 df vao Chroma va kiem tra 3 collection.

Mac dinh chay trong thu muc tam de khong de len artifact that cua pipeline.
Them `--persist` de ghi vao data/chroma, data/embeddings, data/results.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile

import chromadb
import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from retrieval.index import LocalEmbeddingIndex


def _redirect_outputs(settings: Settings, root: Path) -> Settings:
    paths = replace(
        settings.paths,
        chroma_dir=root / "chroma",
        embeddings_json=root / "embeddings" / "papers_embeddings.json",
        corrupted_embeddings_json=root / "embeddings" / "papers_embeddings_corrupted.json",
        repaired_embeddings_json=root / "embeddings" / "papers_embeddings_repaired.json",
        corruption_log=root / "results" / "corruption_log.json",
    )
    return replace(settings, paths=paths)


def _clean_from_raw(settings: Settings) -> pd.DataFrame:
    return build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), datetime.now(UTC))


def _check(failures: list[str], condition: bool, message: str) -> None:
    print(f"  [{'OK' if condition else 'FAIL'}] {message}")
    if not condition:
        failures.append(message)


def run(settings: Settings) -> list[str]:
    failures: list[str] = []
    baseline_df = _clean_from_raw(settings)
    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    repaired_df = _clean_from_raw(settings)  # repair = tai tao lai tu raw snapshot

    states = {
        "baseline": (baseline_df, settings.paths.embeddings_json, settings.baseline_collection_name),
        "corrupted": (corrupted_df, settings.paths.corrupted_embeddings_json, settings.corrupted_collection_name),
        "repaired": (repaired_df, settings.paths.repaired_embeddings_json, settings.repaired_collection_name),
    }

    print("1. Corruption log")
    log = read_json(settings.paths.corruption_log)
    expected_types = {"drop_latest_records", "blank_summary", "inject_noise", "truncate_title", "stale_date", "duplicate_rows"}
    _check(failures, set(log["corruption_types"]) == expected_types, f"du 6 loai loi: {log['corruption_types']}")
    _check(failures, all(entry["affected_rows"] > 0 for entry in log["corruptions"]), "moi loai loi tac dong >= 1 dong")
    _check(failures, len(baseline_df) == len(_clean_from_raw(settings)), "df dau vao khong bi sua (clean van giu nguyen)")
    rerun = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    _check(failures, rerun.equals(corrupted_df), "cung seed -> cung ket qua corruption")

    print("2. Build 3 Chroma collections")
    indexes: dict[str, LocalEmbeddingIndex] = {}
    for state, (df, manifest_path, expected_name) in states.items():
        index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=manifest_path)
        indexes[state] = index
        _check(failures, index.collection_name == expected_name, f"{state}: collection = {index.collection_name}")
        _check(failures, index.collection.count() == len(df), f"{state}: {index.collection.count()} vectors == {len(df)} rows")

    client = chromadb.PersistentClient(path=str(settings.paths.chroma_dir))
    existing = {collection.name for collection in client.list_collections()}
    _check(failures, {name for _, _, name in states.values()} <= existing, f"3 collection ton tai: {sorted(existing)}")

    print("3. Doi chieu noi dung")
    baseline_ids = set(indexes["baseline"].collection.get()["ids"])
    repaired_ids = set(indexes["repaired"].collection.get()["ids"])
    _check(failures, baseline_ids == repaired_ids, "repaired co cung record_id voi baseline")
    _check(failures, corrupted_df["paper_id"].duplicated().any(), "corrupted co paper_id trung lap")
    _check(failures, corrupted_df["paper_id"].nunique() < baseline_df["paper_id"].nunique(), "corrupted mat bot paper")

    rebuilt = LocalEmbeddingIndex.build(repaired_df, settings, embeddings_output_path=settings.paths.repaired_embeddings_json)
    _check(failures, rebuilt.collection.count() == len(repaired_df), "build lai repaired lan 2 khong nhan doi vector (idempotent)")
    indexes["repaired"] = rebuilt  # build() xoa collection cu -> handle cu khong con dung duoc

    loaded = LocalEmbeddingIndex.load(settings, settings.paths.corrupted_embeddings_json)
    _check(failures, loaded.collection_name == settings.corrupted_collection_name, "load() tu manifest mo dung collection corrupted")

    print("4. Retrieval theo title cua bai moi nhat (bi drop trong corrupted)")
    dropped_id = log["corruptions"][0]["affected_paper_ids"][0]
    query = baseline_df.loc[baseline_df["paper_id"] == dropped_id, "title"].iloc[0]
    print(f"  query: {query[:80]}")
    for state, index in indexes.items():
        results = index.search(query, top_k=settings.top_k)
        top = results[0] if results else None
        hit = any(result.paper_id == dropped_id for result in results)
        print(f"  {state:<10} top1={top.paper_id if top else '-'} score={top.score if top else 0:.3f} hit={hit}")
        expect_hit = state != "corrupted"
        _check(failures, hit == expect_hit, f"{state}: hit={hit} (mong doi {expect_hit})")

    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persist", action="store_true", help="Ghi vao data/ that thay vi thu muc tam.")
    args = parser.parse_args()

    settings = load_settings()
    if args.persist:
        failures = run(settings)
    else:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            print(f"(thu muc tam: {tmp})")
            failures = run(_redirect_outputs(settings, Path(tmp)))

    if failures:
        print(f"\nSMOKE TEST FAILED: {len(failures)} check(s)")
        sys.exit(1)
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
