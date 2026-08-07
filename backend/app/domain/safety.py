"""Deterministic safety routing for messages that need immediate care."""

from __future__ import annotations

from dataclasses import dataclass


_URGENT_PATTERNS = (
    "difficulty breathing",
    "trouble breathing",
    "can't breathe",
    "cannot breathe",
    "severe chest pain",
    "sudden chest pain",
    "suicidal",
    "want to kill myself",
    "overdose",
    "uncontrolled bleeding",
)
_URGENT_MESSAGE = (
    "Your message may describe an urgent medical or mental-health situation. "
    "Please contact local emergency services or seek immediate in-person care now."
)


@dataclass(frozen=True)
class SafetyDecision:
    route: str
    warning: str | None = None


def assess_message_safety(prompt: str) -> SafetyDecision:
    """Route explicit emergency signals before retrieval; this is not diagnosis."""
    normalized_prompt = " ".join(prompt.casefold().split())
    if any(pattern in normalized_prompt for pattern in _URGENT_PATTERNS):
        return SafetyDecision(route="urgent_escalation", warning=_URGENT_MESSAGE)
    return SafetyDecision(route="rag")
