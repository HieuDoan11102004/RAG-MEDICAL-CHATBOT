"""Opt-in, privacy-preserving Langfuse tracing for the medical chat workflow."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TRACE_TAGS = ["medical-chatbot", "langgraph", "multi-agent"]


@dataclass(frozen=True)
class LangfuseSettings:
    public_key: str | None
    secret_key: str | None
    base_url: str | None
    environment: str
    trace_content: bool

    @property
    def enabled(self) -> bool:
        return bool(self.public_key and self.secret_key)


def load_langfuse_settings(
    environ: Mapping[str, str] | None = None, dotenv_path: str | Path | None = None
) -> LangfuseSettings:
    """Read optional tracing configuration without adding values to process env."""
    source_environ = os.environ if environ is None else environ
    source_dotenv = dotenv_values(
        Path(dotenv_path) if dotenv_path is not None else _PROJECT_ROOT / ".env"
    )

    def value(name: str) -> str | None:
        candidate = source_environ.get(name, source_dotenv.get(name))
        return candidate.strip() if isinstance(candidate, str) and candidate.strip() else None

    return LangfuseSettings(
        public_key=value("LANGFUSE_PUBLIC_KEY"),
        secret_key=value("LANGFUSE_SECRET_KEY"),
        base_url=value("LANGFUSE_BASE_URL") or value("LANGFUSE_HOST"),
        environment=value("LANGFUSE_TRACING_ENVIRONMENT") or "development",
        trace_content=value("LANGFUSE_TRACE_CONTENT") == "true",
    )


def _stable_identifier(value: str, prefix: str) -> str:
    """Preserve grouping without exporting a raw user or conversation identifier."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def state_thread_id(conversation_id: str) -> str:
    """Return an opaque checkpoint key so callback metadata never gets the raw ID."""
    return _stable_identifier(conversation_id, "state")


def _mask_otel_spans(*, params: Any) -> Any:
    """Redact prompt and response attributes before Langfuse exports OpenTelemetry spans."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    markers = ("input", "output", "prompt", "completion", "message", "email")
    replacement = "[REDACTED: enable LANGFUSE_TRACE_CONTENT=true only after privacy review]"
    patches = {}
    for identifier, span in params.spans.items():
        attributes = {
            key: replacement
            for key in span.attributes
            if any(marker in key.casefold() for marker in markers)
        }
        if attributes:
            patches[identifier] = OtelSpanPatch(set_attributes=attributes)
    return MaskOtelSpansResult(span_patches=patches)


@lru_cache(maxsize=1)
def _langfuse_client(settings: LangfuseSettings):
    """Create a singleton client only when explicit tracing credentials exist."""
    from langfuse import Langfuse

    kwargs: dict[str, Any] = {
        "public_key": settings.public_key,
        "secret_key": settings.secret_key,
        "environment": settings.environment,
    }
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    if not settings.trace_content:
        kwargs["mask_otel_spans"] = _mask_otel_spans
    return Langfuse(**kwargs)


class TraceTurn:
    """Carries optional Langfuse callbacks and records a safe root summary."""

    def __init__(self, observation: Any | None, callback: Any | None) -> None:
        self._observation = observation
        self.callbacks = [callback] if callback is not None else []

    def complete(self, *, route: str, answer: str, citation_count: int, warning_count: int) -> None:
        if self._observation is not None:
            self._observation.update(
                output={
                    "route": route,
                    "answer_length": len(answer),
                    "citation_count": citation_count,
                    "warning_count": warning_count,
                },
                metadata={"route": route},
            )


@contextmanager
def trace_chat_turn(
    *, prompt: str, conversation_id: str, user_id: str
) -> Iterator[TraceTurn]:
    """Trace one chat turn with stable names, safe identifiers, and LangGraph callbacks."""
    settings = load_langfuse_settings()
    if not settings.enabled:
        yield TraceTurn(observation=None, callback=None)
        return

    from langfuse import propagate_attributes
    from langfuse.langchain import CallbackHandler

    client = _langfuse_client(settings)
    with client.start_as_current_observation(
        as_type="agent", name="orchestrate-medical-message"
    ) as observation:
        observation.update(input={"message_length": len(prompt)})
        with propagate_attributes(
            trace_name="medical-chat-turn",
            session_id=_stable_identifier(conversation_id, "session"),
            user_id=_stable_identifier(user_id, "user"),
            tags=_TRACE_TAGS,
            metadata={"feature": "medical-chat", "framework": "langgraph"},
            environment=settings.environment,
        ):
            yield TraceTurn(observation=observation, callback=CallbackHandler())


@contextmanager
def trace_retrieval(*, query: str) -> Iterator[Any | None]:
    """Create a nested retriever observation without exporting the medical query."""
    settings = load_langfuse_settings()
    if not settings.enabled:
        yield None
        return

    client = _langfuse_client(settings)
    with client.start_as_current_observation(
        as_type="retriever", name="retrieve-medical-evidence"
    ) as observation:
        observation.update(input={"query_length": len(query)})
        yield observation
