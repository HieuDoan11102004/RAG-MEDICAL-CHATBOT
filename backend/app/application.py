"""Flask JSON API for the medical RAG chatbot."""

from __future__ import annotations

import os
from collections.abc import Iterable

from flask import Flask, jsonify, request


def _load_env():
    """Load .env file when not in testing mode."""
    if os.getenv("FLASK_ENV") != "testing":
        from pathlib import Path
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")


# Load .env before other imports that might need it
_load_env()

from .agents.orchestrator import Orchestrator
from .agents.orchestrator.responder import DirectResponder
from .agents.orchestrator.router import Router
from .agents.rag_agent import RagAgent
from .agents.rag_agent.components.retriever import answer_question
from .api.schemas import RequestValidationError, parse_message_request
from .auth import create_auth_blueprint, get_session_from_token
from .domain.models import MessageRequest


def _allowed_origins(raw_origins: str | None = None) -> frozenset[str]:
    """Parse the optional comma-separated frontend origin allowlist."""
    value = os.getenv("CORS_ALLOWED_ORIGINS", "") if raw_origins is None else raw_origins
    origins = frozenset(origin.strip() for origin in value.split(",") if origin.strip())
    # If no origins configured, allow all for development
    if not origins:
        origins = frozenset(["http://localhost:5173", "http://localhost:3000"])
    return origins


def _get_request_origin() -> str | None:
    """Get the origin from the request, handling Vercel headers."""
    # Check standard Origin header first
    origin = request.headers.get("Origin")
    if origin:
        return origin
    # Vercel/serverless: check x-forwarded-host or referer
    origin = request.headers.get("X-Forwarded-Host")
    if origin:
        proto = request.headers.get("X-Forwarded-Proto", "https")
        return f"{proto}://{origin}"
    referer = request.headers.get("Referer")
    if referer:
        # Extract origin from referer
        if referer.startswith("http"):
            parts = referer.split("/")
            return f"{parts[0]}//{parts[2]}"
    return None


def create_app(
    *,
    allowed_origins: Iterable[str] | None = None,
    router: Router | None = None,
    direct_responder: DirectResponder | None = None,
) -> Flask:
    """Create the stateless API application."""
    app = Flask(__name__)
    origins = frozenset(allowed_origins) if allowed_origins is not None else _allowed_origins()

    # Register auth routes
    _, auth_routes = create_auth_blueprint()
    for method, path, handler in auth_routes:
        methods = [method, "OPTIONS"]
        if method == "GET":
            app.add_url_rule(path, handler.__name__, handler, methods=methods)
        elif method == "POST":
            app.add_url_rule(path, handler.__name__, handler, methods=methods)
        elif method == "DELETE":
            app.add_url_rule(path, handler.__name__, handler, methods=methods)

    # Handle OPTIONS preflight before route handlers run
    @app.before_request
    def handle_options_preflight():
        if request.method == "OPTIONS":
            return ("", 204)

    orchestrator = Orchestrator(
        RagAgent(answer_fn=lambda prompt: answer_question(prompt)),
        router=router,
        direct_responder=direct_responder,
    )

    @app.after_request
    def add_cors_headers(response):
        origin = _get_request_origin()
        # Always add CORS headers for allowed origins (including OPTIONS preflight)
        if origin and origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    def _get_user_id() -> str:
        """Get user ID from auth session or return anonymous."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            session_data = get_session_from_token(token)
            if session_data:
                return session_data["user"]["id"]
        return "anonymous"

    def _handle_message(*, legacy_response: bool):
        if request.method == "OPTIONS":
            return ("", 204)

        try:
            message = parse_message_request(request.get_json(silent=True))
        except RequestValidationError as exc:
            return jsonify({"error": str(exc)}), 400

        # Use authenticated user ID if available
        user_id = _get_user_id()
        message = MessageRequest(
            prompt=message.prompt,
            conversation_id=message.conversation_id,
            user_id=user_id,
            email=message.email,
        )

        try:
            response = orchestrator.handle(message)
            result = response.as_legacy_dict() if legacy_response else response.as_dict()
            # Include user info in response for authenticated users
            if user_id != "anonymous":
                result["user"] = {"id": user_id}
            return jsonify(result)
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
