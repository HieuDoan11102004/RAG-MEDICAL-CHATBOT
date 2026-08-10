"""Unit tests for bounded agents and deterministic orchestration."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from app.agents.orchestrator import Orchestrator
from app.agents.orchestrator.prompt import ORCHESTRATOR_SYSTEM_PROMPT
from app.agents.orchestrator.responder import DirectResponse, MessageResponder
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
        urgent_message: str | None = None,
    ) -> None:
        self._decision = RoutingDecision(
            route=route,
            confidence=confidence,
            conversation_action=conversation_action,
            display_name=display_name,
            urgent_message=urgent_message,
        )

    def decide(self, _prompt: str) -> RoutingDecision:
        return self._decision


class ScriptedRouter:
    def __init__(self, decisions: dict[str, RoutingDecision]) -> None:
        self._decisions = decisions

    def decide(self, prompt: str) -> RoutingDecision:
        return self._decisions[prompt]


class FixedDirectResponder:
    def __init__(self, answer: str = "Generated direct response.") -> None:
        self.answer = answer
        self.calls: list[dict[str, object]] = []

    def respond(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return self.answer


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

        response = Orchestrator(
            RagAgent(unexpected_rag),
            router=FixedRouter("basic_talk"),
            direct_responder=FixedDirectResponder(),
        ).handle(
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

        direct_responder = FixedDirectResponder()
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
            direct_responder=direct_responder,
        )
        response = orchestrator.handle(
            MessageRequest(
                prompt="i am hieu",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(response.route, "direct_response")
        self.assertEqual(response.answer, "Generated direct response.")
        self.assertEqual(orchestrator.get_state("introduction-conversation")["display_name"], "Hieu")

        greeting = orchestrator.handle(
            MessageRequest(
                prompt="Hi",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(greeting.answer, "Generated direct response.")

        name_recall = orchestrator.handle(
            MessageRequest(
                prompt="What is my name?",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(name_recall.answer, "Generated direct response.")

        history_recall = orchestrator.handle(
            MessageRequest(
                prompt="What I have asked?",
                conversation_id="introduction-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(history_recall.route, "direct_response")
        self.assertEqual(history_recall.answer, "Generated direct response.")
        self.assertEqual(direct_responder.calls[-1]["conversation_action"], "recall_history")

    def test_basic_talk_without_an_eligible_agent_does_not_call_rag(self) -> None:
        def unexpected_rag(_question: str):
            raise AssertionError("RAG must not run for basic talk")

        response = Orchestrator(
            RagAgent(unexpected_rag),
            router=FixedRouter("basic_talk"),
            direct_responder=FixedDirectResponder(),
        ).handle(
            MessageRequest(
                prompt="How are you today?",
                conversation_id="basic-talk-conversation",
                user_id="test-user",
            )
        )

        self.assertEqual(response.route, "direct_response")
        self.assertEqual(response.citations, [])
        self.assertEqual(response.answer, "Generated direct response.")

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

    def test_llm_selected_urgent_message_does_not_call_rag(self) -> None:
        def unexpected_rag(_question: str):
            raise AssertionError("RAG must not run for urgent routing")

        response = Orchestrator(
            RagAgent(unexpected_rag),
            router=FixedRouter(
                "urgent_escalation",
                urgent_message="Please seek immediate in-person care.",
            ),
        ).handle(
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

        # Second message now includes conversation context for retrieval
        messages = [message.content for message in state["messages"]]
        self.assertEqual(messages[0], "What is dehydration?")
        self.assertEqual(messages[1], "Cited: What is dehydration?")
        self.assertEqual(messages[2], "What are the symptoms?")
        # Third message includes context
        self.assertIn("Previous conversation:", messages[3])
        self.assertIn("What is dehydration?", messages[3])
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
            "urgent_message": None,
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
                urgent_message=None,
            ),
        )
        loader.assert_called_once_with(temperature=0.0, max_tokens=96)
        llm.with_structured_output.assert_called_once_with(RoutingDecision)

    def test_accepts_an_llm_selected_urgent_route(self) -> None:
        structured_llm = Mock()
        structured_llm.invoke.return_value = {
            "route": "urgent_escalation",
            "confidence": 0.96,
            "conversation_action": "none",
            "display_name": None,
            "urgent_message": "Please seek immediate in-person care.",
        }
        llm = Mock()
        llm.with_structured_output.return_value = structured_llm

        decision = MessageRouter(llm_loader=Mock(return_value=llm)).decide("I need help now")

        self.assertEqual(decision.route, "urgent_escalation")


class MessageResponderTests(unittest.TestCase):
    def test_uses_structured_output_for_direct_responses(self) -> None:
        structured_llm = Mock()
        structured_llm.invoke.return_value = {"answer": "Hello from MedChat."}
        llm = Mock()
        llm.with_structured_output.return_value = structured_llm

        answer = MessageResponder(llm_loader=Mock(return_value=llm)).respond(
            messages=[], conversation_action="none", display_name=None
        )

        self.assertEqual(answer, "Hello from MedChat.")
        llm.with_structured_output.assert_called_once_with(DirectResponse)

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
