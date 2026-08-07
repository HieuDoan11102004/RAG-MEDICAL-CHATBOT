"""Unit tests for bounded agents and deterministic orchestration."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from app.agents.orchestrator import Orchestrator
from app.agents.orchestrator.prompt import ORCHESTRATOR_SYSTEM_PROMPT
from app.agents.orchestrator.router import MessageRouter, RoutingDecision
from app.agents.rag_agent import RagAgent
from app.agents.rag_agent.prompt import RAG_SYSTEM_PROMPT, build_rag_prompt
from app.agents.state import update_dialog_stack
from app.domain.models import MessageRequest


class FixedRouter:
    def __init__(
        self,
        route: str,
        confidence: float = 0.95,
        conversation_action: str = "none",
        display_name: str | None = None,
    ) -> None:
        self._decision = RoutingDecision(
            route=route,
            confidence=confidence,
            conversation_action=conversation_action,
            display_name=display_name,
        )

    def decide(self, _prompt: str) -> RoutingDecision:
        return self._decision


class ScriptedRouter:
    def __init__(self, decisions: dict[str, RoutingDecision]) -> None:
        self._decisions = decisions

    def decide(self, prompt: str) -> RoutingDecision:
        return self._decisions[prompt]


class RagAgentTests(unittest.TestCase):
    def test_delegates_to_existing_retriever(self) -> None:
        calls: list[str] = []

        def answer(question: str):
            calls.append(question)
            return {"answer": "Cited answer.", "citations": [{"id": "source-1"}]}

        result = RagAgent(answer).run("Question")

        self.assertEqual(calls, ["Question"])
        self.assertEqual(result.answer, "Cited answer.")
        self.assertEqual(result.citations, [{"id": "source-1"}])


class OrchestratorTests(unittest.TestCase):
    def test_greeting_does_not_call_rag(self) -> None:
        def unexpected_rag(_question: str):
            raise AssertionError("RAG must not run for a greeting")

        response = Orchestrator(RagAgent(unexpected_rag), router=FixedRouter("basic_talk")).handle(
            MessageRequest(
                prompt="Hi",
                conversation_id="greeting-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(response.route, "direct_response")
        self.assertEqual(response.citations, [])

    def test_introduction_does_not_call_rag_and_is_retained_for_the_conversation(self) -> None:
        def unexpected_rag(_question: str):
            raise AssertionError("RAG must not run for a user introduction")

        orchestrator = Orchestrator(
            RagAgent(unexpected_rag),
            router=ScriptedRouter(
                {
                    "i am hieu": RoutingDecision(
                        route="basic_talk",
                        confidence=0.95,
                        conversation_action="remember_name",
                        display_name="Hieu",
                    ),
                    "Hi": RoutingDecision(
                        route="basic_talk",
                        confidence=0.95,
                        conversation_action="none",
                        display_name=None,
                    ),
                    "What is my name?": RoutingDecision(
                        route="basic_talk",
                        confidence=0.95,
                        conversation_action="recall_name",
                        display_name=None,
                    ),
                    "What I have asked?": RoutingDecision(
                        route="basic_talk",
                        confidence=0.95,
                        conversation_action="recall_history",
                        display_name=None,
                    ),
                }
            ),
        )
        response = orchestrator.handle(
            MessageRequest(
                prompt="i am hieu",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(response.route, "direct_response")
        self.assertIn("Nice to meet you, Hieu", response.answer)
        self.assertEqual(orchestrator.get_state("introduction-conversation")["display_name"], "Hieu")

        greeting = orchestrator.handle(
            MessageRequest(
                prompt="Hi",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertIn("Hi, Hieu", greeting.answer)

        name_recall = orchestrator.handle(
            MessageRequest(
                prompt="What is my name?",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(name_recall.answer, "Your name is Hieu.")

        history_recall = orchestrator.handle(
            MessageRequest(
                prompt="What I have asked?",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(history_recall.route, "direct_response")
        self.assertIn("i am hieu", history_recall.answer.casefold())
        self.assertIn("What is my name?", history_recall.answer)

    def test_basic_talk_without_an_eligible_agent_does_not_call_rag(self) -> None:
        def unexpected_rag(_question: str):
            raise AssertionError("RAG must not run for basic talk")

        response = Orchestrator(
            RagAgent(unexpected_rag), router=FixedRouter("basic_talk")
        ).handle(
            MessageRequest(
                prompt="How are you today?",
                conversation_id="basic-talk-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(response.route, "direct_response")
        self.assertEqual(response.citations, [])
        self.assertIn("medical-reference assistant", response.answer)

    def test_medical_information_request_still_uses_rag(self) -> None:
        calls: list[str] = []

        def answer(question: str):
            calls.append(question)
            return {"answer": "Cited answer.", "citations": [{"id": "source-1"}]}

        response = Orchestrator(RagAgent(answer), router=FixedRouter("rag_agent")).handle(
            MessageRequest(
                prompt="What are the symptoms of dehydration?",
                conversation_id="medical-question-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(calls, ["What are the symptoms of dehydration?"])
        self.assertEqual(response.route, "rag")

    def test_urgent_message_does_not_call_rag(self) -> None:
        def unexpected_rag(_question: str):
            raise AssertionError("RAG must not run for urgent routing")

        response = Orchestrator(RagAgent(unexpected_rag)).handle(
            MessageRequest(
                prompt="I have difficulty breathing",
                conversation_id="urgent-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(response.route, "urgent_escalation")
        self.assertEqual(response.citations, [])
        self.assertTrue(response.warnings)

    def test_shared_state_retains_messages_and_agent_statuses(self) -> None:
        orchestrator = Orchestrator(
            RagAgent(lambda question: {"answer": f"Cited: {question}", "citations": []}),
            router=FixedRouter("rag_agent"),
        )
        orchestrator.handle(
            MessageRequest(
                prompt="What is dehydration?",
                conversation_id="stateful-conversation",
                user_id="test-user",
            )
        )
        orchestrator.handle(
            MessageRequest(
                prompt="What are the symptoms?",
                conversation_id="stateful-conversation",
                user_id="test-user",
            )
        )

        state = orchestrator.get_state("stateful-conversation")

        self.assertEqual(
            [message.content for message in state["messages"]],
            [
                "What is dehydration?",
                "Cited: What is dehydration?",
                "What are the symptoms?",
                "Cited: What are the symptoms?",
            ],
        )
        self.assertEqual(state["dialog_state"], ["primary_assistant"])
        self.assertEqual(state["agent_states"]["rag_agent"]["status"], "complete")


class DialogStateTests(unittest.TestCase):
    def test_push_and_pop_dialog_state(self) -> None:
        state = ["primary_assistant"]

        state = update_dialog_stack(state, "rag_agent")

        self.assertEqual(state, ["primary_assistant", "rag_agent"])
        self.assertEqual(update_dialog_stack(state, "pop"), ["primary_assistant"])


class AgentPromptTests(unittest.TestCase):
    def test_each_implemented_agent_owns_a_non_empty_prompt(self) -> None:
        self.assertTrue(ORCHESTRATOR_SYSTEM_PROMPT.strip())
        self.assertIn("warm, trustworthy medical-reference assistant", ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn("not a doctor", ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertIn("calm, respectful, clear, and non-judgmental", ORCHESTRATOR_SYSTEM_PROMPT)
        self.assertTrue(RAG_SYSTEM_PROMPT.strip())
        self.assertIn("Evidence:\ncontext", build_rag_prompt("question", "context"))


class MessageRouterTests(unittest.TestCase):
    def test_uses_structured_output_and_validates_the_decision(self) -> None:
        structured_llm = Mock()
        structured_llm.invoke.return_value = {
            "route": "rag_agent",
            "confidence": 0.91,
            "conversation_action": "none",
            "display_name": None,
        }
        llm = Mock()
        llm.with_structured_output.return_value = structured_llm
        loader = Mock(return_value=llm)

        decision = MessageRouter(llm_loader=loader).decide("How do I treat a headache?")

        self.assertEqual(
            decision,
            RoutingDecision(
                route="rag_agent",
                confidence=0.91,
                conversation_action="none",
                display_name=None,
            ),
        )
        loader.assert_called_once_with(temperature=0.0, max_tokens=96)
        llm.with_structured_output.assert_called_once_with(RoutingDecision)

    def test_falls_back_to_basic_talk_when_model_routing_fails(self) -> None:
        decision = MessageRouter(llm_loader=Mock(side_effect=RuntimeError("unavailable"))).decide(
            "How do I treat a headache?"
        )

        self.assertEqual(
            decision,
            RoutingDecision(
                route="basic_talk",
                confidence=0.0,
                conversation_action="none",
                display_name=None,
            ),
        )


if __name__ == "__main__":
    unittest.main()
