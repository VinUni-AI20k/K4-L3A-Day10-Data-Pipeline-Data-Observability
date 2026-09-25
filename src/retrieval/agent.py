from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool

from core.config import Settings
from core.utils import write_json
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm

SYSTEM_PROMPT = (
    "You answer questions about the indexed scholarly paper corpus sourced from Crossref. "
    "Always call a tool before answering a factual question. "
    "When the question names a paper title or DOI, call lookup_paper first; "
    "if it finds no exact match, fall back to semantic_search_papers. "
    "Answer only from the tool results and cite the paper_id you used. "
    "If the tool results do not contain the answer, say clearly that it was not found "
    "in the indexed corpus instead of guessing."
)


def build_agent(settings: Settings, index: LocalEmbeddingIndex):
    @tool
    def semantic_search_papers(query: str, top_k: int = 4) -> str:
        """Search the local paper corpus with embeddings and return the most relevant papers."""
        results = index.search(query, top_k=top_k)
        lines = []
        for result in results:
            lines.append(
                f"paper_id: {result.paper_id}\n"
                f"title: {result.title}\n"
                f"score: {result.score:.4f}\n"
                f"{result.content}"
            )
        return "\n\n".join(lines)

    @tool
    def lookup_paper(paper_id_or_title: str) -> str:
        """Look up a paper by exact paper_id or exact title from the local corpus."""
        record = index.lookup(paper_id_or_title)
        if not record:
            return "No exact paper match found."
        return (
            f"paper_id: {record['paper_id']}\n"
            f"title: {record['title']}\n"
            f"{record['content']}"
        )

    llm = build_llm(settings=settings, temperature=0.0)
    return create_agent(
        model=llm,
        tools=[semantic_search_papers, lookup_paper],
        system_prompt=SYSTEM_PROMPT,
        name="paper_corpus_agent",
    )


def _invoke(agent: Any, question: str) -> list[Any]:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result.get("messages", [])


def _final_text(messages: list[Any]) -> str:
    if not messages:
        return ""
    content = getattr(messages[-1], "content", str(messages[-1]))
    if isinstance(content, list):
        # Some providers (e.g. Gemini, Anthropic) return content blocks instead of a plain string.
        return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
    return str(content)


def run_agent_question(agent: Any, question: str) -> str:
    return _final_text(_invoke(agent, question))


def run_agent_demo(
    settings: Settings,
    index: LocalEmbeddingIndex,
    questions: list[str | dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    """Ask the ReAct agent each question against one collection and save the transcript.

    `questions` may be plain strings or test-set items (their id/ground truth are kept
    so baseline, corrupted and repaired answers can be compared side by side).
    """
    agent = build_agent(settings, index)
    rows: list[dict[str, Any]] = []
    for item in questions:
        entry = {"question": item} if isinstance(item, str) else dict(item)
        question = entry["question"]
        top = index.search(question, top_k=1)
        row: dict[str, Any] = {
            "id": entry.get("id"),
            "question_type": entry.get("question_type"),
            "question": question,
            "ground_truth": entry.get("ground_truth"),
            "ground_truth_doc_ids": entry.get("ground_truth_doc_ids"),
            "collection": index.collection_name,
            "llm_provider": settings.llm_provider,
            "top_search_doc_id": top[0].paper_id if top else None,
            "top_search_score": round(top[0].score, 4) if top else None,
        }
        try:
            messages = _invoke(agent, question)
            row["tool_calls"] = [
                {"name": call["name"], "args": call["args"]}
                for message in messages
                for call in (getattr(message, "tool_calls", None) or [])
            ]
            row["answer"] = _final_text(messages)
        except Exception as exc:  # keep the pipeline alive on provider/rate-limit errors
            row["tool_calls"] = []
            row["answer"] = ""
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    write_json(output_path, rows)
    return rows
