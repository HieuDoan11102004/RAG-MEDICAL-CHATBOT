"""HTTP contract tests for the stateless Flask API."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.application import create_app


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(allowed_origins={"http://localhost:5173"})
        self.client = self.app.test_client()

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    @patch("app.application.answer_question")
    def test_chat_returns_rag_answer(self, create_chain) -> None:
        create_chain.return_value = {
            "answer": "Stay hydrated.",
            "citations": [{"id": "source-1", "title": "Gale", "page": 4}],
        }

        response = self.client.post("/api/chat", json={"prompt": "How do I recover?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), create_chain.return_value)
        create_chain.assert_called_once_with("How do I recover?")

    def test_chat_rejects_blank_or_non_json_prompt(self) -> None:
        for payload in ({}, {"prompt": "   "}, {"prompt": 4}):
            with self.subTest(payload=payload):
                response = self.client.post("/api/chat", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json(), {"error": "prompt must be a non-blank string."}
                )

        response = self.client.post("/api/chat", data="not-json", content_type="text/plain")
        self.assertEqual(response.status_code, 400)

    @patch("app.application.answer_question", side_effect=RuntimeError("service unavailable"))
    def test_chat_hides_rag_failure_details(self, _create_chain) -> None:
        response = self.client.post("/api/chat", json={"prompt": "Question"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Unable to process your request."})

    def test_cors_allows_only_configured_origins(self) -> None:
        allowed = self.client.options(
            "/api/chat", headers={"Origin": "http://localhost:5173"}
        )
        denied = self.client.options("/api/chat", headers={"Origin": "https://example.com"})

        self.assertEqual(allowed.status_code, 204)
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")
        self.assertEqual(allowed.headers.get("Access-Control-Allow-Methods"), "POST, OPTIONS")
        self.assertIsNone(denied.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
