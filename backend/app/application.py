"""Flask JSON API for the medical RAG chatbot."""

from __future__ import annotations

import os
from collections.abc import Iterable

from flask import Flask, jsonify, request

from .components.retriever import create_qa_chain


def _allowed_origins(raw_origins: str | None = None) -> frozenset[str]:
    """Parse the optional comma-separated frontend origin allowlist."""
    value = os.getenv("CORS_ALLOWED_ORIGINS", "") if raw_origins is None else raw_origins
    return frozenset(origin.strip() for origin in value.split(",") if origin.strip())


def create_app(*, allowed_origins: Iterable[str] | None = None) -> Flask:
    """Create the stateless API application."""
    app = Flask(__name__)
    origins = frozenset(allowed_origins) if allowed_origins is not None else _allowed_origins()

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

    @app.route("/api/chat", methods=["POST", "OPTIONS"])
    def chat():
        if request.method == "OPTIONS":
            return ("", 204)

        payload = request.get_json(silent=True)
        prompt = payload.get("prompt") if isinstance(payload, dict) else None
        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "prompt must be a non-blank string."}), 400

        try:
            response = create_qa_chain().invoke({"query": prompt.strip()})
            answer = response.get("result") if isinstance(response, dict) else None
            if not isinstance(answer, str) or not answer.strip():
                answer = "Sorry, I couldn't find an answer."
            return jsonify({"answer": answer})
        except Exception:
            app.logger.exception("Unable to process chat request")
            return jsonify({"error": "Unable to process your request."}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
