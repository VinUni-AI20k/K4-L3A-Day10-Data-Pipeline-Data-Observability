"""Smoke test cho retrieval/ (RAG specialist), khong can cleaning.py hay testset.py.

Dung dataframe tam tu data/raw/crossref_records.json, index vao ChromaDB o thu muc tam
(khong dong vao data/chroma cua nhom), roi kiem tra:
  1. Index du 24 docs + metadata.
  2. QA 4 loai cau hoi (co title trong dau nhay don).
  3. Semantic search thuan (khong co exact lookup) -> hit@1, hit@k.
  4. Cac truong hop bien: cau hoi khong co nhay, title co dau ', published la Timestamp.

Chay: python script/smoke_retrieval.py
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
import tempfile
from pathlib import Path

import pandas as pd

os.environ.setdefault("LLM_PROVIDER", "mock")  # QA khong goi LLM; tranh can API key

from core.config import load_settings
from core.utils import compact_join, first_sentence, normalize_whitespace
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def build_temp_dataframe(records_path: Path) -> pd.DataFrame:
    """Ban cleaning toi gian, chi de co dung schema ma index.py can."""
    rows = []
    for record in json.loads(records_path.read_text(encoding="utf-8")):
        title = normalize_whitespace(record["title"])
        summary = normalize_whitespace(record["summary"])
        authors = compact_join(record["authors"])
        categories = compact_join(record["categories"])
        published = str(record["published"])[:10]
        rows.append(
            {
                "paper_id": record["paper_id"],
                "title": title,
                "summary": summary,
                "published": published,
                "authors_joined": authors,
                "categories_joined": categories,
                "abs_url": record["abs_url"],
                "pdf_url": record["pdf_url"],
                "text_for_embedding": (
                    f"Title: {title}\nAuthors: {authors}\nPublished: {published}\n"
                    f"Categories: {categories}\nSummary: {summary}"
                ),
            }
        )
    return pd.DataFrame(rows)


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" -> {detail}" if detail else ""))
    return ok


def main() -> None:
    base = load_settings()
    tmp_dir = Path(tempfile.mkdtemp(prefix="smoke_chroma_"))
    settings = replace(base, paths=replace(base.paths, chroma_dir=tmp_dir / "chroma"))
    manifest = tmp_dir / "smoke_embeddings.json"
    results: list[bool] = []

    df = build_temp_dataframe(settings.paths.raw_records_json)
    print(f"== 1. Index ({len(df)} rows) -> {tmp_dir}")
    index = LocalEmbeddingIndex.build(df, settings, manifest)
    count = index.collection.count()
    results.append(check("collection count == rows", count == len(df), f"{index.collection_name}: {count}"))
    sample = index.collection.get(limit=1, include=["metadatas", "embeddings"])
    dim = len(sample["embeddings"][0])
    results.append(check("embedding dim == 384 (MiniLM)", dim == 384, str(dim)))
    meta_keys = sorted(sample["metadatas"][0].keys())
    results.append(check("metadata du 8 truong", len(meta_keys) == 8, ", ".join(meta_keys)))
    reloaded = LocalEmbeddingIndex.load(settings, manifest)
    results.append(check("load() tu manifest", reloaded.collection.count() == count))

    print("\n== 2. QA 4 loai cau hoi (exact title lookup)")
    row = df.iloc[0]
    t = row["title"]
    cases = [
        ("authors", f"Who authored '{t}'?", row["authors_joined"]),
        ("date", f"When was '{t}' published?", row["published"]),
        ("categories", f"What categories does '{t}' belong to?", row["categories_joined"]),
        ("summary", f"What is the summary of the paper '{t}'?", first_sentence(row["summary"])),
    ]
    for qtype, question, expected in cases:
        result = answer_question(question, settings=settings, index=index)
        hit = row["paper_id"] in result.retrieved_doc_ids
        results.append(check(f"{qtype}: answer dung", result.answer == expected, result.answer[:70]))
        results.append(check(f"{qtype}: retrieval hit", hit))

    print("\n== 3. Semantic search thuan (khong exact lookup), query = title")
    hit1 = hitk = 0
    confusions = []
    for _, r in df.iterrows():
        found = index.search(r["title"], top_k=settings.top_k)
        ids = [item.paper_id for item in found]
        hit1 += ids[:1] == [r["paper_id"]]
        hitk += r["paper_id"] in ids
        if ids[:1] != [r["paper_id"]]:
            confusions.append(f"{r['title'][:45]}... -> top1: {found[0].title[:45]}...")
    print(f"  hit@1 = {hit1}/{len(df)}   hit@{settings.top_k} = {hitk}/{len(df)}")
    for line in confusions:
        print(f"    nham: {line}")
    results.append(check(f"hit@{settings.top_k} == 100%", hitk == len(df)))

    print("\n== 4. Truong hop bien")
    no_quote = answer_question(f"Who authored {t}?", settings=settings, index=index)
    check(
        "cau hoi KHONG co nhay don (chi dua vao semantic search)",
        no_quote.retrieved_doc_ids[0] == row["paper_id"],
        f"top1 = {no_quote.retrieved_titles[0][:50]}",
    )
    apostrophe = "The Agent's Guide to Retrieval"
    match_q = f"Who authored '{apostrophe}'?"
    import re

    extracted = re.search(r"'([^']+)'", match_q).group(1)
    check(
        "title co dau ' bi regex cat sai (qa.py:1001)",
        extracted == apostrophe,
        f"regex lay duoc: {extracted!r}",
    )
    bad = df.head(2).copy()
    bad["published"] = pd.to_datetime(bad["published"])
    try:
        LocalEmbeddingIndex.build(bad, settings, tmp_dir / "bad_embeddings.json")
        check("published kieu Timestamp bi Chroma tu choi", False, "Chroma van nhan -> khong can rang buoc")
    except Exception as exc:  # noqa: BLE001
        check("published kieu Timestamp bi Chroma tu choi (=> phai la str)", True, type(exc).__name__)

    passed = sum(results)
    print(f"\n== Ket qua: {passed}/{len(results)} check chinh PASS")


if __name__ == "__main__":
    main()
