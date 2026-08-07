"""HTTP contract tests for the stateless Flask API."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.application import create_app
from app.agents.orchestrator.router import RoutingDecision


class _ApiRouter:
    def decide(self, prompt: str) -> RoutingDecision:
        if prompt.casefold() == "hi":
            return RoutingDecision(
                route="basic_talk",
                confidence=0.95,
                conversation_action="none",
                display_name=None,
            )
        return RoutingDecision(
            route="rag_agent",
            confidence=0.95,
            conversation_action="none",
            display_name=None,
        )


class _FixedApiRouter:
    def __init__(self, route: str, urgent_message: str | None = None) -> None:
        self._decision = RoutingDecision(
            route=route,
            confidence=0.95,
            conversation_action="none",
            display_name=None,
            urgent_message=urgent_message,
        )

    def decide(self, _prompt: str) -> RoutingDecision:
        return self._decision


class _FixedDirectResponder:
    def respond(self, **_kwargs: object) -> str:
        return "Generated direct response."


class ChatApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            allowed_origins={"http://localhost:5173"},
            router=_ApiRouter(),
            direct_responder=_FixedDirectResponder(),
        )
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

    @patch("app.application.answer_question")
    def test_messages_returns_orchestrated_response(self, create_chain) -> None:
        create_chain.return_value = {"answer": "Stay hydrated.", "citations": []}

        response = self.client.post("/api/messages", json={"prompt": "How do I recover?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "answer": "Stay hydrated.",
                "citations": [],
                "warnings": [],
                "processing": {"route": "rag"},
            },
        )

    @patch("app.application.answer_question")
    def test_messages_routes_llm_selected_urgent_message_without_rag(self, create_chain) -> None:
        app = create_app(
            allowed_origins={"http://localhost:5173"},
            router=_FixedApiRouter(
                "urgent_escalation",
                urgent_message="Please seek immediate in-person care.",
            ),
            direct_responder=_FixedDirectResponder(),
        )
        response = app.test_client().post("/api/messages", json={"prompt": "I need help now."})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["processing"], {"route": "urgent_escalation"})
        self.assertEqual(payload["citations"], [])
        self.assertTrue(payload["warnings"])
        create_chain.assert_not_called()

    @patch("app.application.answer_question")
    def test_messages_answers_a_greeting_without_rag(self, create_chain) -> None:
        response = self.client.post("/api/messages", json={"prompt": "hi"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["processing"], {"route": "direct_response"})
        self.assertEqual(response.get_json()["citations"], [])
        self.assertEqual(response.get_json()["answer"], "Generated direct response.")
        create_chain.assert_not_called()

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

    def test_messages_rejects_too_long_prompt(self) -> None:
        response = self.client.post("/api/messages", json={"prompt": "a" * 4_001})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "prompt must be at most 4000 characters."})

    def test_messages_rejects_an_invalid_email_context_value(self) -> None:
        response = self.client.post(
            "/api/messages", json={"prompt": "Question", "email": "not-an-email"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "email must be a valid email address."})

    @patch("app.application.answer_question", side_effect=RuntimeError("service unavailable"))
    def test_chat_hides_rag_failure_details(self, _create_chain) -> None:
        response = self.client.post(
            "/api/chat", json={"prompt": "What causes dehydration?"}
        )

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
