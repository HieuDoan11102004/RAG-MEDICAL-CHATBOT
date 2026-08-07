"""Validation for the versioned medical-message API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError

from ..domain.models import MessageRequest


MAX_PROMPT_CHARACTERS = 4_000


class RequestValidationError(ValueError):
    """Raised when a message request cannot safely enter the workflow."""


def parse_message_request(payload: Any) -> MessageRequest:
    """Validate the text-only phase-one contract for POST /api/messages."""
    if not isinstance(payload, Mapping):
        raise RequestValidationError("Request body must be a JSON object.")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RequestValidationError("prompt must be a non-blank string.")
    normalized_prompt = prompt.strip()
    if len(normalized_prompt) > MAX_PROMPT_CHARACTERS:
        raise RequestValidationError(
            f"prompt must be at most {MAX_PROMPT_CHARACTERS} characters."
        )
    conversation_id = _optional_identifier(payload.get("conversation_id"), "conversation_id")
    user_id = _optional_identifier(payload.get("user_id"), "user_id")
    email = _optional_email(payload.get("email"))
    return MessageRequest(
        prompt=normalized_prompt,
        conversation_id=conversation_id or str(uuid4()),
        user_id=user_id or "anonymous",
        email=email,
    )


def _optional_identifier(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128:
        raise RequestValidationError(f"{field_name} must be a non-blank string up to 128 characters.")
    return value.strip()


def _optional_email(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequestValidationError("email must be a valid email address.")
    try:
        return str(TypeAdapter(EmailStr).validate_python(value))
    except ValidationError as exc:
        raise RequestValidationError("email must be a valid email address.") from exc
