from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from core.config import Settings
from core.utils import first_sentence
from retrieval.index import LocalEmbeddingIndex, SearchResult


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_contexts: list[str]
    retrieved_titles: list[str]


def _extract_answer(question: str, top_result: SearchResult) -> str:
    lowered = question.lower()
    metadata = top_result.metadata
    if "who authored" in lowered or "list the authors" in lowered:
        return metadata["authors_joined"]
    if any(phrase in lowered for phrase in ("when was", "publication date", "published on", "month and year")):
        try:
            return datetime.fromisoformat(metadata["published"]).strftime("%B %Y")
        except (TypeError, ValueError):
            return metadata["published"]
    if any(phrase in lowered for phrase in ("what categories", "which categor", "specialist field", "which field")):
        return metadata["categories_joined"] or "Crossref did not supply a specialist category."
    return first_sentence(metadata["summary"])


def answer_question(question: str, settings: Settings, index: LocalEmbeddingIndex, top_k: int | None = None) -> AnswerResult:
    quoted_values = [single or double for single, double in re.findall(r"'([^']+)'|\"([^\"]+)\"", question)]
    exact_documents = []
    seen_exact_ids = set()
    for value in quoted_values:
        document = index.lookup(value)
        if document and document["paper_id"] not in seen_exact_ids:
            exact_documents.append(document)
            seen_exact_ids.add(document["paper_id"])
    retrieved = index.search(question, top_k=top_k)
    if exact_documents:
        exact_results = [
            SearchResult(
                paper_id=document["paper_id"],
                title=document["title"],
                score=1.0,
                content=document["content"],
                metadata=document["metadata"],
            )
            for document in exact_documents
        ]
        exact_ids = {item.paper_id for item in exact_results}
        deduped = exact_results + [item for item in retrieved if item.paper_id not in exact_ids]
        retrieved = deduped[: (top_k or settings.top_k)]
    if not retrieved:
        answer = "I don't know from the indexed corpus."
    elif len(exact_documents) >= 2 and any(
        phrase in question.lower() for phrase in ("complement", "together", "across their fields", "compare")
    ):
        answer = " ".join(
            f"{document['title']} ({document['metadata']['categories_joined'] or 'Crossref did not supply a specialist category.'}): "
            f"{first_sentence(document['metadata']['summary'])}"
            for document in exact_documents
        )
    else:
        answer = _extract_answer(question, retrieved[0])
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )
