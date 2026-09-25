from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import build_agent, run_agent_question
    from .embeddings import MiniLMEmbeddings
    from .index import LocalEmbeddingIndex, SearchResult
    from .llm import build_llm
    from .qa import AnswerResult, answer_question

__all__ = [
    "AnswerResult",
    "LocalEmbeddingIndex",
    "MiniLMEmbeddings",
    "SearchResult",
    "answer_question",
    "build_agent",
    "build_llm",
    "run_agent_question",
]


def __getattr__(name: str):
    if name in {"build_agent", "run_agent_question"}:
        from . import agent

        return getattr(agent, name)
    if name in {"MiniLMEmbeddings"}:
        from . import embeddings

        return getattr(embeddings, name)
    if name in {"LocalEmbeddingIndex", "SearchResult"}:
        from . import index

        return getattr(index, name)
    if name in {"build_llm"}:
        from . import llm

        return getattr(llm, name)
    if name in {"AnswerResult", "answer_question"}:
        from . import qa

        return getattr(qa, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
