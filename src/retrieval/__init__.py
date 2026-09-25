<<<<<<< HEAD
from .embeddings import MiniLMEmbeddings
from .index import LocalEmbeddingIndex, SearchResult

__all__ = [
    "MiniLMEmbeddings", "LocalEmbeddingIndex", "SearchResult", "build_agent",
    "run_agent_question", "build_llm", "AnswerResult", "answer_question",
]


def __getattr__(name):
    if name in {"build_agent", "run_agent_question"}:
        from . import agent

        return getattr(agent, name)
    if name == "build_llm":
        from . import llm

        return llm.build_llm
    if name in {"AnswerResult", "answer_question"}:
        from . import qa

        return getattr(qa, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
=======
"""Load public exports lazily so indexing does not require LLM providers."""

from importlib import import_module

_EXPORTS = {'build_agent': 'agent', 'run_agent_question': 'agent', 'MiniLMEmbeddings': 'embeddings', 'LocalEmbeddingIndex': 'index', 'SearchResult': 'index', 'build_llm': 'llm', 'AnswerResult': 'qa', 'answer_question': 'qa'}
__all__ = list(_EXPORTS)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
