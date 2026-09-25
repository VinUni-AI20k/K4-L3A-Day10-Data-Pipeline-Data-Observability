from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd

from core.config import Settings
from core.utils import read_json, safe_slug, write_json
from retrieval.embeddings import MiniLMEmbeddings


@dataclass(frozen=True)
class SearchResult:
    paper_id: str
    title: str
    score: float
    content: str
    metadata: dict[str, Any]


class LocalEmbeddingIndex:
<<<<<<< HEAD
    def __init__(
        self,
        settings: Settings,
        collection_name: str,
        documents: list[dict[str, Any]] | None = None,
        persist_path: Path | None = None,
    ):
        self.settings = settings
        self.collection_name = collection_name
        self.documents = documents or []
        self.persist_path = persist_path or settings.paths.chroma_dir
        self.embedding_backend = "chroma"
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        try:
            self.collection = self.client.get_collection(name=collection_name)
        except Exception:
            self.collection = None
        self._refresh_lookup_maps()

    def _refresh_lookup_maps(self) -> None:
        self.documents_by_paper_id = {document["paper_id"].lower(): document for document in self.documents}
        self.documents_by_title = {document["title"].lower(): document for document in self.documents}

    def build_from_clean(self) -> "LocalEmbeddingIndex":
        """Checkpoint-friendly facade: build this collection from clean JSON."""
        df = pd.read_json(self.settings.paths.clean_json)
        manifest_path = self.settings.paths.embeddings_json
        expected_name = self._derive_collection_name(self.settings, manifest_path)
        if self.collection_name != expected_name:
            # A custom collection needs a custom manifest name so classmethod
            # build derives and persists the requested collection independently.
            manifest_path = self.settings.paths.embeddings_json.with_name(f"{self.collection_name}.json")
        built = type(self).build(df, self.settings, manifest_path)
        if built.collection_name != self.collection_name:
            # The baseline checkpoint explicitly names papers-baseline.
            built.collection_name = self.collection_name
        self.documents = built.documents
        self.persist_path = built.persist_path
        self.embedding_backend = built.embedding_backend
        self.embedding_model = built.embedding_model
        self.client = built.client
        self.collection = built.collection
        self._refresh_lookup_maps()
        return self

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        records = df.to_dict(orient="records")
        documents: list[dict[str, Any]] = []
        for index, row in enumerate(records):
            published = pd.to_datetime(row["published"], utc=True, errors="coerce")
            documents.append(
                {
                    "record_id": f"{row['paper_id']}::{index}",
                    "paper_id": row["paper_id"],
                    "title": row["title"],
                    "content": row["text_for_embedding"],
                    "metadata": {
                        "paper_id": row["paper_id"],
                        "title": row["title"],
                        "published": published.date().isoformat() if not pd.isna(published) else "",
                        "authors_joined": str(row["authors_joined"]),
                        "categories_joined": str(row["categories_joined"]),
                        "summary": str(row["summary"]),
                        "abs_url": str(row["abs_url"]),
                        "pdf_url": str(row["pdf_url"]),
                    },
                }
            )
=======
    def __init__(self, settings: Settings, collection_name: str = 'papers-baseline',
                 documents: list[dict[str, Any]] | None = None, persist_path: Path | None = None):
        self.settings = settings
        self.collection_name = collection_name
        self.persist_path = Path(persist_path or settings.paths.chroma_dir)
        self.embedding_backend = 'chroma'
        self.embedding_model = MiniLMEmbeddings(settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(self.persist_path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name, embedding_function=None,
            metadata={'hnsw:space': 'cosine', 'embedding_model': settings.embedding_model},
        )
        stored_model = (self.collection.metadata or {}).get('embedding_model')
        if stored_model and stored_model != settings.embedding_model:
            raise ValueError(f'Collection uses a different embedding model: {stored_model}')
        self._refresh_documents()

    def _refresh_documents(self) -> None:
        stored = self.collection.get(include=['documents', 'metadatas'])
        self.documents = [
            {'record_id': paper_id, 'paper_id': paper_id, 'title': metadata.get('title', ''),
             'content': content, 'metadata': metadata}
            for paper_id, content, metadata in zip(stored['ids'], stored['documents'], stored['metadatas'])
        ]
        self.documents_by_paper_id = {d['paper_id'].lower(): d for d in self.documents}
        self.documents_by_title = {d['title'].lower(): d for d in self.documents}

    @staticmethod
    def _build_documents(df: pd.DataFrame) -> list[dict[str, Any]]:
        required = {'paper_id', 'title', 'text_for_embedding'}
        if missing := required - set(df.columns):
            raise ValueError(f'Missing index columns: {sorted(missing)}')

        def text(value: Any) -> str:
            if isinstance(value, (list, tuple)):
                return ', '.join(filter(None, (text(part) for part in value)))
            return value.strip() if isinstance(value, str) else ''

        documents, seen = [], set()
        for row in df.to_dict(orient='records'):
            paper_id, title, content = (text(row.get(key)) for key in ('paper_id', 'title', 'text_for_embedding'))
            if not all((paper_id, title, content)):
                raise ValueError('Index rows require nonempty paper_id, title and text_for_embedding.')
            if paper_id in seen:
                continue
            seen.add(paper_id)
            authors = text(row.get('authors_joined')) or text(row.get('authors'))
            categories = text(row.get('categories_joined')) or text(row.get('categories'))
            metadata = {key: text(row.get(key)) for key in ('published', 'summary', 'abs_url', 'pdf_url')}
            metadata.update(paper_id=paper_id, title=title, authors=authors, categories=categories,
                            authors_joined=authors, categories_joined=categories)
            documents.append({'record_id': paper_id, 'paper_id': paper_id, 'title': title,
                              'content': content, 'metadata': metadata})
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
        return documents

    def _replace_from_dataframe(self, df: pd.DataFrame) -> int:
        documents = self._build_documents(df)
        # Encode everything before mutating the persisted collection.
        embeddings = self.embedding_model.embed_documents([d['content'] for d in documents]) if documents else []
        batch_size = min(500, self.client.get_max_batch_size())
        for start in range(0, len(documents), batch_size):
            batch = documents[start:start + batch_size]
            self.collection.upsert(ids=[d['paper_id'] for d in batch],
                                   documents=[d['content'] for d in batch],
                                   metadatas=[d['metadata'] for d in batch],
                                   embeddings=embeddings[start:start + batch_size])
        # Synchronize the whole clean snapshot, removing documents no longer present.
        ids = {d['paper_id'] for d in documents}
        obsolete = [key for key in self.collection.get(include=[])['ids'] if key not in ids]
        for start in range(0, len(obsolete), batch_size):
            self.collection.delete(ids=obsolete[start:start + batch_size])
        self._refresh_documents()
        return len(documents)

    def _write_manifest(self, path: Path) -> None:
        write_json(Path(path), {'backend': 'chroma', 'embedding_model': self.settings.embedding_model,
                               'persist_path': str(self.persist_path.resolve()),
                               'collection_name': self.collection_name, 'documents': self.documents})

    def build_from_clean(self) -> int:
        path = Path(self.settings.paths.clean_json)
        df = pd.DataFrame(read_json(path)) if path.exists() else pd.read_csv(self.settings.paths.clean_csv, keep_default_na=False)
        count = self._replace_from_dataframe(df)
        if self.collection_name == self.settings.baseline_collection_name:
            self._write_manifest(self.settings.paths.embeddings_json)
        return count

    @staticmethod
    def _derive_collection_name(settings: Settings, embeddings_output_path: Path | None) -> str:
        if embeddings_output_path is None:
            return settings.baseline_collection_name
        names = {settings.paths.embeddings_json.resolve(): settings.baseline_collection_name,
                 settings.paths.corrupted_embeddings_json.resolve(): settings.corrupted_collection_name,
                 settings.paths.repaired_embeddings_json.resolve(): settings.repaired_collection_name}
        return names.get(Path(embeddings_output_path).resolve(), safe_slug(Path(embeddings_output_path).stem))

    @classmethod
    def build(cls, df: pd.DataFrame, settings: Settings, embeddings_output_path: Path | None = None) -> 'LocalEmbeddingIndex':
        index = cls(settings, cls._derive_collection_name(settings, embeddings_output_path))
        index._replace_from_dataframe(df)
        index._write_manifest(embeddings_output_path or settings.paths.embeddings_json)
        return index

    @classmethod
    def load(cls, settings: Settings, embeddings_path: Path | None = None) -> 'LocalEmbeddingIndex':
        payload = read_json(embeddings_path or settings.paths.embeddings_json)
        index = cls(settings, payload['collection_name'], persist_path=Path(payload['persist_path']))
        if not index.collection.count() and payload.get('documents'):
            raise ValueError('Persisted collection is empty; rebuild the vector index.')
        return index

    def semantic_search(self, query: str, top_k: int = 2) -> list[dict[str, Any]]:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError('top_k must be a positive integer.')
        if not isinstance(query, str) or not query.strip():
            raise ValueError('query must be nonempty text.')
        count = self.collection.count()
        if not count:
            return []
        results = self.collection.query(query_embeddings=[self.embedding_model.embed_query(query)],
                                        n_results=min(top_k, count), include=['documents', 'metadatas', 'distances'])
        return [{'paper_id': paper_id, 'document': document, 'metadata': metadata,
                 'distance': float(distance), 'score': 1.0 - float(distance)}
                for paper_id, document, metadata, distance in zip(
                    results['ids'][0], results['documents'][0], results['metadatas'][0], results['distances'][0])]

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
<<<<<<< HEAD
        if self.collection is None:
            raise RuntimeError("Chroma collection is not built; call build_from_clean() or load() first")
        query_embedding = self.embedding_model.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k or self.settings.top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        scored: list[SearchResult] = []
        for record_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            if not record_id or not metadata or not content:
                continue
            scored.append(
                SearchResult(
                    paper_id=str(metadata["paper_id"]),
                    title=str(metadata["title"]),
                    score=max(0.0, 1.0 - float(distance or 0.0)),
                    content=str(content),
                    metadata=dict(metadata),
                )
            )
        return scored
=======
        return [SearchResult(paper_id=r['paper_id'], title=r['metadata']['title'], score=r['score'],
                             content=r['document'], metadata=r['metadata'])
                for r in self.semantic_search(query, self.settings.top_k if top_k is None else top_k)]
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)

    def semantic_search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        """Compatibility alias used by the Checkpoint 2 smoke-test command."""
        return self.search(query, top_k=top_k)

    def lookup(self, value: str) -> dict[str, Any] | None:
        needle = value.strip().lower()
        return self.documents_by_paper_id.get(needle) or self.documents_by_title.get(needle)
