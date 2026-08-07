"""Adapter that makes the existing cited retriever a bounded RAG agent."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ...domain.models import RagResult
from .components.retriever import answer_question


class RagAgent:
    """Runs one existing, citation-grounded retrieval-and-answer operation."""

    def __init__(self, answer_fn: Callable[[str], Mapping[str, Any]] = answer_question) -> None:
        self._answer_fn = answer_fn

    def run(self, question: str) -> RagResult:
        response = self._answer_fn(question)
        answer = response.get("answer") if isinstance(response, Mapping) else None
        citations = response.get("citations") if isinstance(response, Mapping) else None
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("RAG agent returned no answer.")
        if not isinstance(citations, list):
            raise ValueError("RAG agent returned invalid citations.")
        return RagResult(answer=answer.strip(), citations=citations)
