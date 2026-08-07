"""LLM-backed responses for non-retrieval conversation routes."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ...agents.rag_agent.components.llm import load_llm
from .prompt import DIRECT_RESPONSE_SYSTEM_PROMPT


ConversationAction = Literal["none", "remember_name", "recall_name", "recall_history"]


class DirectResponse(BaseModel):
    """Validated text generated for a non-retrieval conversation route."""

    answer: str = Field(min_length=1, max_length=1_000)


class DirectResponder(Protocol):
    """Produces a conversational reply without retrieval."""

    def respond(
        self,
        *,
        messages: list[object],
        conversation_action: ConversationAction,
        display_name: str | None,
    ) -> str: ...


class MessageResponder:
    """Generate direct conversation replies from the current conversation state."""

    def __init__(self, llm_loader: Callable[..., object] = load_llm) -> None:
        self._llm_loader = llm_loader

    def respond(
        self,
        *,
        messages: list[object],
        conversation_action: ConversationAction,
        display_name: str | None,
    ) -> str:
        context = {
            "conversation_action": conversation_action,
            "display_name": display_name,
            "messages": [
                {"role": getattr(message, "type", "unknown"), "content": str(message.content)}
                for message in messages[-10:]
                if hasattr(message, "content")
            ],
        }
        llm = self._llm_loader(temperature=0.2, max_tokens=160)
        structured_llm = llm.with_structured_output(DirectResponse)
        result = structured_llm.invoke(
            [
                SystemMessage(content=DIRECT_RESPONSE_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(context)),
            ]
        )
        return DirectResponse.model_validate(result).answer
