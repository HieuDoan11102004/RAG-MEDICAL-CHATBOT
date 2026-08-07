"""Structured LLM routing for non-urgent MedChat messages."""

from __future__ import annotations

from typing import Callable, Literal, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ...agents.rag_agent.components.llm import load_llm
from ...common.logger import get_logger
from .prompt import ROUTER_SYSTEM_PROMPT


logger = get_logger(__name__)
RouterRoute = Literal["basic_talk", "rag_agent", "clarification"]
ConversationAction = Literal["none", "remember_name", "recall_name", "recall_history"]
ROUTING_CONFIDENCE_THRESHOLD = 0.75


class RoutingDecision(BaseModel):
    """Validated, bounded output from the routing model."""

    route: RouterRoute
    confidence: float = Field(ge=0, le=1)
    conversation_action: ConversationAction
    display_name: str | None


class Router(Protocol):
    """Boundary used by the orchestrator to classify a non-urgent message."""

    def decide(self, prompt: str) -> RoutingDecision: ...


class MessageRouter:
    """Use a low-temperature structured-output model for agent selection."""

    def __init__(self, llm_loader: Callable[..., object] = load_llm) -> None:
        self._llm_loader = llm_loader

    def decide(self, prompt: str) -> RoutingDecision:
        try:
            llm = self._llm_loader(temperature=0.0, max_tokens=96)
            structured_llm = llm.with_structured_output(RoutingDecision)
            result = structured_llm.invoke(
                [SystemMessage(content=ROUTER_SYSTEM_PROMPT), HumanMessage(content=prompt)]
            )
            return RoutingDecision.model_validate(result)
        except Exception as exc:
            logger.warning("Structured route selection failed; using safe direct fallback: %s", exc)
            return RoutingDecision(
                route="basic_talk",
                confidence=0.0,
                conversation_action="none",
                display_name=None,
            )
