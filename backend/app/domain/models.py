"""Stable request, response, and agent-result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Route = Literal["direct_response", "rag", "urgent_escalation", "clarification"]


@dataclass(frozen=True)
class MessageRequest:
    """Validated text input. Attachments are added in the OCR delivery phase."""

    prompt: str
    conversation_id: str
    user_id: str
    email: str | None = None


@dataclass(frozen=True)
class RagResult:
    """The cited answer returned by the RAG agent."""

    answer: str
    citations: list[dict[str, Any]]


@dataclass(frozen=True)
class MessageResponse:
    """API response after orchestration, without retaining user input."""

    answer: str
    citations: list[dict[str, Any]]
    warnings: list[str]
    route: Route

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "warnings": self.warnings,
            "processing": {"route": self.route},
        }

    def as_legacy_dict(self) -> dict[str, Any]:
        """Preserve the original /api/chat response shape during migration."""
        return {"answer": self.answer, "citations": self.citations}
