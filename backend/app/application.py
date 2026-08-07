"""Flask JSON API for the medical RAG chatbot."""

from __future__ import annotations

import os
from collections.abc import Iterable

from flask import Flask, jsonify, request

from .agents.orchestrator import Orchestrator
from .agents.orchestrator.router import Router
from .agents.rag_agent import RagAgent
from .agents.rag_agent.components.retriever import answer_question
from .api.schemas import RequestValidationError, parse_message_request


def _allowed_origins(raw_origins: str | None = None) -> frozenset[str]:
    """Parse the optional comma-separated frontend origin allowlist."""
    value = os.getenv("CORS_ALLOWED_ORIGINS", "") if raw_origins is None else raw_origins
    return frozenset(origin.strip() for origin in value.split(",") if origin.strip())


def create_app(
    *, allowed_origins: Iterable[str] | None = None, router: Router | None = None
) -> Flask:
    """Create the stateless API application."""
    app = Flask(__name__)
    origins = frozenset(allowed_origins) if allowed_origins is not None else _allowed_origins()
    orchestrator = Orchestrator(
        RagAgent(answer_fn=lambda prompt: answer_question(prompt)), router=router
    )

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    def _handle_message(*, legacy_response: bool):
        if request.method == "OPTIONS":
            return ("", 204)

        try:
            message = parse_message_request(request.get_json(silent=True))
        except RequestValidationError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            response = orchestrator.handle(message)
            return jsonify(response.as_legacy_dict() if legacy_response else response.as_dict())
        except Exception:
            app.logger.exception("Unable to process chat request")
            return jsonify({"error": "Unable to process your request."}), 500

    @app.route("/api/messages", methods=["POST", "OPTIONS"])
    def messages():
        """Versioned orchestration endpoint; uploads arrive in the OCR phase."""
        return _handle_message(legacy_response=False)

    @app.route("/api/chat", methods=["POST", "OPTIONS"])
    def chat():
        """Backward-compatible adapter for the original text-chat API."""
        return _handle_message(legacy_response=True)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
