"""Deterministic coordinator for the incremental multi-agent workflow."""

from __future__ import annotations

from typing import cast

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ...common.tracing import state_thread_id, trace_chat_turn
from ...domain.models import MessageRequest, MessageResponse, Route
from ..state import AgenticState, pop_dialog_state
from ..rag_agent import RagAgent
from .prompt import ORCHESTRATOR_SYSTEM_PROMPT
from .responder import DirectResponder, MessageResponder
from .router import ROUTING_CONFIDENCE_THRESHOLD, MessageRouter, Router


class Orchestrator:
    """Coordinates bounded agents through a shared, checkpointed state graph."""

    prompt = ORCHESTRATOR_SYSTEM_PROMPT

    def __init__(
        self,
        rag_agent: RagAgent,
        router: Router | None = None,
        direct_responder: DirectResponder | None = None,
    ) -> None:
        self._rag_agent = rag_agent
        self._router = router or MessageRouter()
        self._direct_responder = direct_responder or MessageResponder()
        builder = StateGraph(AgenticState)
        builder.add_node("primary_assistant", self._primary_assistant)
        builder.add_node("direct_response", self._direct_response)
        builder.add_node("rag_agent", self._run_rag_agent)
        builder.add_node("urgent_escalation", self._urgent_escalation)
        builder.add_node("clarification", self._clarification)
        builder.add_edge(START, "primary_assistant")
        builder.add_conditional_edges(
            "primary_assistant",
            self._next_agent,
            {
                "direct_response": "direct_response",
                "rag_agent": "rag_agent",
                "urgent_escalation": "urgent_escalation",
                "clarification": "clarification",
            },
        )
        builder.add_edge("direct_response", END)
        builder.add_edge("rag_agent", END)
        builder.add_edge("urgent_escalation", END)
        builder.add_edge("clarification", END)
        self._graph = builder.compile(checkpointer=MemorySaver())

    def handle(self, message: MessageRequest) -> MessageResponse:
        config = {"configurable": {"thread_id": state_thread_id(message.conversation_id)}}
        initial_state: dict[str, object] = {
            "messages": [HumanMessage(content=message.prompt)],
            "conversation_id": message.conversation_id,
            "user_id": message.user_id,
            "email": message.email,
            "agent_states": {"orchestrator": {"status": "active"}},
        }
        if not self._graph.get_state(config).values.get("dialog_state"):
            initial_state["dialog_state"] = ["primary_assistant"]
        with trace_chat_turn(
            prompt=message.prompt,
            conversation_id=message.conversation_id,
            user_id=message.user_id,
        ) as trace:
            result = self._graph.invoke(
                initial_state,
                config={**config, "callbacks": trace.callbacks, "run_name": "handle-medical-message"},
            )
            raw_response = result.get("response")
            if isinstance(raw_response, dict):
                raw_answer = raw_response.get("answer")
                raw_citations = raw_response.get("citations")
                raw_warnings = raw_response.get("warnings")
                raw_route = raw_response.get("route")
                if (
                    isinstance(raw_answer, str)
                    and isinstance(raw_citations, list)
                    and isinstance(raw_warnings, list)
                    and isinstance(raw_route, str)
                ):
                    trace.complete(
                        route=raw_route,
                        answer=raw_answer,
                        citation_count=len(raw_citations),
                        warning_count=len(raw_warnings),
                    )
        response = result.get("response")
        if not isinstance(response, dict):
            raise ValueError("The orchestration graph returned no response.")
        answer = response.get("answer")
        citations = response.get("citations")
        warnings = response.get("warnings")
        route = response.get("route")
        if (
            not isinstance(answer, str)
            or not isinstance(citations, list)
            or not isinstance(warnings, list)
            or route not in {"direct_response", "rag", "urgent_escalation", "clarification"}
        ):
            raise ValueError("The orchestration graph returned an invalid response.")
        message_response = MessageResponse(
            answer=answer,
            citations=citations,
            warnings=warnings,
            route=cast(Route, route),
        )
        return message_response

    def get_state(self, conversation_id: str) -> AgenticState:
        """Expose a snapshot for tests and future authenticated conversation APIs."""
        snapshot = self._graph.get_state(
            config={"configurable": {"thread_id": state_thread_id(conversation_id)}}
        )
        return cast(AgenticState, snapshot.values)

    def _primary_assistant(self, state: AgenticState) -> dict[str, object]:
        prompt = str(state["messages"][-1].content)
        decision = self._router.decide(prompt)
        if decision.route == "urgent_escalation":
            return {
                "route": "urgent_escalation",
                "urgent_message": decision.urgent_message,
                "agent_states": {
                    "orchestrator": {"status": "complete", "summary": "Urgent route selected."},
                    "rag_agent": {"status": "skipped", "summary": "Safety route selected."},
                },
            }
        display_name = self._display_name_for(decision.display_name)
        if decision.conversation_action != "none" or decision.route == "basic_talk":
            updates: dict[str, object] = {
                "route": "direct_response",
                "conversation_action": decision.conversation_action,
                "agent_states": {
                    "orchestrator": {"status": "complete", "summary": "Conversation route selected."},
                    "rag_agent": {"status": "skipped", "summary": "No retrieval required."},
                },
            }
            if decision.conversation_action == "remember_name" and display_name:
                updates["display_name"] = display_name
            return updates
        if decision.route == "clarification" and decision.confidence >= ROUTING_CONFIDENCE_THRESHOLD:
            return {
                "route": "clarification",
                "agent_states": {
                    "orchestrator": {
                        "status": "complete",
                        "summary": "Clarification is needed before safe retrieval.",
                    },
                    "rag_agent": {"status": "skipped", "summary": "Clarification route selected."},
                },
            }
        if decision.route != "rag_agent" or decision.confidence < ROUTING_CONFIDENCE_THRESHOLD:
            return {
                "route": "direct_response",
                "conversation_action": "none",
                "agent_states": {
                    "orchestrator": {
                        "status": "complete",
                        "summary": "No enabled specialist matched with high confidence.",
                    },
                    "rag_agent": {"status": "skipped", "summary": "No retrieval required."},
                },
            }
        return {
            "route": "rag",
            "dialog_state": "rag_agent",
            "agent_states": {
                "orchestrator": {"status": "complete", "summary": "RAG route selected."},
                "rag_agent": {"status": "active"},
            },
        }

    @staticmethod
    def _next_agent(state: AgenticState) -> str:
        if state["route"] == "urgent_escalation":
            return "urgent_escalation"
        if state["route"] == "direct_response":
            return "direct_response"
        if state["route"] == "clarification":
            return "clarification"
        return "rag_agent"

    def _direct_response(self, state: AgenticState) -> dict[str, object]:
        action = state.get("conversation_action", "none")
        display_name = state.get("display_name")
        answer = self._direct_responder.respond(
            messages=state["messages"],
            conversation_action=action,
            display_name=display_name,
        )
        response = MessageResponse(
            answer=answer,
            citations=[],
            warnings=[],
            route="direct_response",
        )
        return {
            "messages": [AIMessage(content=answer)],
            "response": {**response.as_dict(), "route": "direct_response"},
        }

    @staticmethod
    def _display_name_for(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = " ".join(value.split())
        return normalized[:64] or None

    def _run_rag_agent(self, state: AgenticState) -> dict[str, object]:
        # Build conversation context from recent messages for better retrieval
        messages = state["messages"]
        recent_user_messages = []
        for msg in messages[:-1]:  # Exclude current message
            if hasattr(msg, "type") and msg.type == "human":
                recent_user_messages.append(msg.content)
        
        # Prepend recent context if available (helps with pronoun resolution like "nó")
        current_question = str(state["messages"][-1].content)
        if recent_user_messages:
            context = f"Previous conversation:\n" + "\n".join(f"- {m}" for m in recent_user_messages[-3:])
            retrieval_question = f"{context}\n\nCurrent question: {current_question}"
        else:
            retrieval_question = current_question
        
        rag_result = self._rag_agent.run(retrieval_question)
        pop_update = pop_dialog_state(state)
        response = MessageResponse(
            answer=rag_result.answer,
            citations=rag_result.citations,
            warnings=[],
            route="rag",
        )
        return {
            "messages": [AIMessage(content=rag_result.answer), *pop_update["messages"]],
            "response": {**response.as_dict(), "route": "rag"},
            "agent_states": {"rag_agent": {"status": "complete", "summary": "Retrieved cited evidence."}},
            "dialog_state": pop_update["dialog_state"],
        }

    def _urgent_escalation(self, state: AgenticState) -> dict[str, object]:
        warning = state["urgent_message"]
        if not warning:
            raise ValueError("Urgent escalation requires router-provided guidance.")
        response = MessageResponse(
            answer=warning,
            citations=[],
            warnings=[warning],
            route="urgent_escalation",
        )
        return {
            "messages": [AIMessage(content=warning)],
            "response": {**response.as_dict(), "route": "urgent_escalation"},
        }

    @staticmethod
    def _clarification(state: AgenticState) -> dict[str, object]:
        # Detect user's language from the last message
        user_message = str(state["messages"][-1].content) if state["messages"] else ""
        vietnamese_chars = set("ạăắằẳẵặâấầẩẫậđêếềểễệơớờởỡợôốồổỗộưứừửữựảẳẩẫẻỉĩịủũụỉỏọổộứừửẳ")
        vietnamese_words = ["là", "của", "và", "có", "không", "tôi", "bạn", "nên", "thế", "nào", "gì", "tôi bị", "làm gì", "như thế"]
        has_vietnamese = any(c in user_message.lower() for c in vietnamese_chars) or any(f" {w} " in f" {user_message.lower()} " for w in vietnamese_words)
        
        if has_vietnamese:
            answer = "Bạn có thể cho tôi biết thêm về chủ đề sức khỏe bạn muốn hỏi không?"
        else:
            answer = "Could you share a little more about the health topic you would like to ask about?"
        
        response = MessageResponse(
            answer=answer,
            citations=[],
            warnings=[],
            route="clarification",
        )
        return {
            "messages": [AIMessage(content=answer)],
            "response": {**response.as_dict(), "route": "clarification"},
        }
