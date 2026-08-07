"""Shared hierarchical state and reducers for the medical-agent graph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, Optional

from langchain_core.messages import AnyMessage, ToolMessage
from langgraph.graph.message import add_messages
from pydantic import EmailStr
from typing_extensions import TypedDict


AgentName = Literal["orchestrator", "rag_agent", "ocr_agent", "ner_agent"]
DialogAgent = Literal["primary_assistant", "rag_agent", "ocr_agent", "ner_agent"]
AgentStatus = Literal["pending", "active", "complete", "skipped", "failed"]


class AgentExecutionState(TypedDict, total=False):
    """The latest bounded execution status for one agent."""

    status: AgentStatus
    summary: str


def update_dialog_stack(
    left: list[DialogAgent], right: list[DialogAgent] | DialogAgent | Literal["pop"] | None
) -> list[DialogAgent]:
    """Push a child agent or pop back to its parent without mutating state."""
    if right is None:
        return left
    if isinstance(right, list):
        return right
    if right == "pop":
        return left[:-1]
    return [*left, right]


def update_agent_states(
    left: Mapping[AgentName, AgentExecutionState] | None,
    right: Mapping[AgentName, AgentExecutionState] | None,
) -> dict[AgentName, AgentExecutionState]:
    """Merge independent agent updates while retaining other agents' latest state."""
    return {**(left or {}), **(right or {})}


class AgenticState(TypedDict, total=False):
    """Common state visible to every agent in the hierarchy."""

    messages: Annotated[list[AnyMessage], add_messages]
    dialog_state: Annotated[list[DialogAgent], update_dialog_stack]
    conversation_id: Annotated[str, "Conversation ID"]
    user_id: Annotated[str, "User ID"]
    email: Annotated[Optional[EmailStr], "Email from context (optional)"]
    display_name: Annotated[Optional[str], "User-provided name for this conversation"]
    conversation_action: Literal["none", "remember_name", "recall_name", "recall_history"]
    agent_states: Annotated[
        dict[AgentName, AgentExecutionState], update_agent_states
    ]
    route: Literal["direct_response", "rag", "urgent_escalation", "clarification"]
    response: dict[str, object]


def pop_dialog_state(state: AgenticState) -> dict[str, object]:
    """Pop a child agent and preserve a valid tool-call continuation when present."""
    messages: list[AnyMessage] = []
    previous_message = state.get("messages", [])[-1] if state.get("messages") else None
    tool_calls = getattr(previous_message, "tool_calls", None)
    if tool_calls:
        messages.append(
            ToolMessage(
                content=(
                    "Resuming dialog with the host assistant. Reflect on the prior "
                    "conversation and continue helping the user."
                ),
                tool_call_id=tool_calls[0]["id"],
            )
        )
    return {"dialog_state": "pop", "messages": messages}
