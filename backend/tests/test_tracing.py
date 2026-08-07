"""Tests for opt-in, privacy-preserving Langfuse configuration."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.common.tracing import _stable_identifier, load_langfuse_settings, state_thread_id


class LangfuseSettingsTests(unittest.TestCase):
    def test_tracing_is_disabled_without_both_keys(self) -> None:
        with TemporaryDirectory() as directory:
            settings = load_langfuse_settings(environ={}, dotenv_path=Path(directory) / ".env")

        self.assertFalse(settings.enabled)
        self.assertFalse(settings.trace_content)

    def test_tracing_reads_opt_in_configuration_without_exposing_identifiers(self) -> None:
        settings = load_langfuse_settings(
            environ={
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_BASE_URL": "https://example.test",
                "LANGFUSE_TRACING_ENVIRONMENT": "test",
                "LANGFUSE_TRACE_CONTENT": "true",
            },
            dotenv_path=Path("missing.env"),
        )

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.environment, "test")
        self.assertTrue(settings.trace_content)
        self.assertNotIn("user-123", _stable_identifier("user-123", "user"))
        self.assertEqual(_stable_identifier("user-123", "user"), _stable_identifier("user-123", "user"))
        self.assertNotIn("conversation-123", state_thread_id("conversation-123"))
        self.assertEqual(
            state_thread_id("conversation-123"), state_thread_id("conversation-123")
        )
