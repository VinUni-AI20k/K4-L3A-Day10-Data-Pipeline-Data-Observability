from __future__ import annotations

from dataclasses import dataclass
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


QUOTED_TITLE = re.compile(r"'([^']+)'")
AUTHOR_HINTS = ("author", "who wrote")
DATE_HINTS = ("when was", "publication date", "published on", "date", "year")
CATEGORY_HINTS = ("categor", "field", "subject", "topic")


def _question_type(question: str) -> str:
    # Drop the quoted title first so words inside it (e.g. "Authorship") do not change the intent.
    lowered = QUOTED_TITLE.sub(" ", question).lower()
    if any(hint in lowered for hint in AUTHOR_HINTS):
        return "authors"
    if any(hint in lowered for hint in DATE_HINTS):
        return "date"
    if any(hint in lowered for hint in CATEGORY_HINTS):
        return "categories"
    return "summary"


def _extract_answer(question: str, top_result: SearchResult) -> str:
    metadata = top_result.metadata
    question_type = _question_type(question)
    if question_type == "authors":
        return metadata["authors_joined"]
    if question_type == "date":
        return metadata["published"]
    if question_type == "categories":
        return metadata["categories_joined"]
    return first_sentence(metadata["summary"])


def answer_question(question: str, settings: Settings, index: LocalEmbeddingIndex, top_k: int | None = None) -> AnswerResult:
    title_match = QUOTED_TITLE.search(question)
    exact = index.lookup(title_match.group(1)) if title_match else None
    retrieved = index.search(question, top_k=top_k)
    if exact:
        exact_result = SearchResult(
            paper_id=exact["paper_id"],
            title=exact["title"],
            score=1.0,
            content=exact["content"],
            metadata=exact["metadata"],
        )
        deduped = [exact_result] + [item for item in retrieved if item.paper_id != exact_result.paper_id]
        retrieved = deduped[: (top_k or settings.top_k)]
    if not retrieved:
        answer = "I don't know from the indexed corpus."
    else:
        answer = _extract_answer(question, retrieved[0])
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )
