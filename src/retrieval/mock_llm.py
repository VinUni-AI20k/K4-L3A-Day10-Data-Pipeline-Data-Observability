from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from core.utils import first_sentence
from retrieval.qa import QUOTED_TITLE, _question_type

FIELD_PREFIXES = {
    "authors": "Authors:",
    "date": "Published:",
    "categories": "Categories:",
    "summary": "Summary:",
}


def _field(block: str, prefix: str) -> str:
    for line in block.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


class MockToolCallingChatModel(BaseChatModel):
    """Offline ReAct stand-in: calls the corpus tools, then answers from the first tool hit.

    Lets the agent run end to end without an API key, so the demo still shows how
    corrupted collections change what the agent says.
    """

    @property
    def _llm_type(self) -> str:
        return "mock-tool-calling"

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> "MockToolCallingChatModel":
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any):
        # metrics._judge_answer relies on this failing to switch to its heuristic judge.
        raise NotImplementedError("The mock provider does not support structured output.")

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next_message(messages))])

    @staticmethod
    def _tool_call(name: str, args: dict[str, str], step: int) -> AIMessage:
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"mock_call_{step}", "type": "tool_call"}])

    def _next_message(self, messages: list[BaseMessage]) -> AIMessage:
        turn_start = max(i for i, message in enumerate(messages) if isinstance(message, HumanMessage))
        question = str(messages[turn_start].content)
        tool_results = [message for message in messages[turn_start + 1 :] if isinstance(message, ToolMessage)]

        if not tool_results:
            title_match = QUOTED_TITLE.search(question)
            if title_match:
                return self._tool_call("lookup_paper", {"paper_id_or_title": title_match.group(1)}, 1)
            return self._tool_call("semantic_search_papers", {"query": question}, 1)

        last = tool_results[-1]
        content = str(last.content).strip()
        if last.name == "lookup_paper" and content.startswith("No exact paper match"):
            return self._tool_call("semantic_search_papers", {"query": question}, len(tool_results) + 1)
        if not content:
            return AIMessage(content="I could not find this in the indexed corpus.")

        top_block = content.split("\n\n")[0]
        paper_id = _field(top_block, "paper_id:")
        question_type = _question_type(question)
        value = _field(top_block, FIELD_PREFIXES[question_type])
        if question_type == "summary":
            value = first_sentence(value) if value else ""
        if not value:
            return AIMessage(content=f"The indexed record {paper_id} has no {question_type} information.")
        return AIMessage(content=f"{value} (source: {paper_id})")
