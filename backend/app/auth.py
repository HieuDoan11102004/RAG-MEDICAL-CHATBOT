"""Better-Auth compatible authentication for the medical RAG chatbot."""

from __future__ import annotations

import json
import secrets
import sqlite3
import string
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any

import bcrypt
from flask import Flask, Response, g, jsonify, request

# Path to SQLite database
# Use /tmp for Vercel serverless compatibility (ephemeral filesystem)
# In production with multiple instances, consider Turso or D1 instead
AUTH_DB_PATH = Path("/tmp/auth.db")
CONV_DB_PATH = Path("/tmp/conversations.db")


def get_db() -> sqlite3.Connection:
    """Get or create database connection."""
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(AUTH_DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def get_conv_db() -> sqlite3.Connection:
    """Get or create conversation database connection."""
    CONV_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CONV_DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_conv_db() -> None:
    """Initialize the conversation database."""
    conn = get_conv_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                messages TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
        """)
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the auth database with required tables."""
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                image TEXT,
                email_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                password TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        """)
        conn.commit()
    finally:
        conn.close()


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(24))
    return f"{prefix}{random_part}" if prefix else random_part


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_session(user_id: str, remember_me: bool = True) -> dict[str, Any]:
    """Create a new session for a user."""
    conn = get_db()
    try:
        session_id = generate_id("s_")
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + (
            timedelta(days=30) if remember_me else timedelta(hours=24)
        )

        conn.execute(
            """
            INSERT INTO sessions (id, user_id, token, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, token, expires_at, request.remote_addr, request.headers.get("User-Agent"))
        )
        conn.commit()

        return {
            "id": session_id,
            "token": token,
            "expires_at": expires_at.isoformat(),
            "user_id": user_id,
        }
    finally:
        conn.close()


def get_session_from_token(token: str) -> dict[str, Any] | None:
    """Get session data from a token."""
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT s.id, s.token, s.expires_at, s.created_at,
                   u.id as uid, u.email, u.name, u.image, u.email_verified, u.created_at as user_created, u.updated_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, datetime.now(timezone.utc))
        ).fetchone()

        if not row:
            return None

        return {
            "session": {
                "id": row["id"],
                "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                "user_id": row["uid"],
                "token": row["token"],
            },
            "user": {
                "id": row["uid"],
                "email": row["email"],
                "name": row["name"],
                "image": row["image"],
                "email_verified": bool(row["email_verified"]),
                "created_at": row["user_created"].isoformat() if row["user_created"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
        }
    finally:
        conn.close()


def delete_session(token: str) -> None:
    """Delete a session by token."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return jsonify({"type": "error", "code": "UNAUTHORIZED", "message": "Unauthorized"}), 401

        session_data = get_session_from_token(token)
        if not session_data:
            return jsonify({"type": "error", "code": "SESSION_EXPIRED", "message": "Session expired or invalid"}), 401

        g.session = session_data["session"]
        g.user = session_data["user"]
        return f(*args, **kwargs)
    return decorated


def create_auth_blueprint(base_url: str = "/api/auth") -> tuple[Flask, list[tuple[str, str, callable]]]:
    """Create Flask routes for better-auth compatible API."""
    init_db()

    # We'll use a simple approach - define routes inline
    routes: list[tuple[str, str, callable]] = []

    def sign_up_email():
        """Handle sign-up with email and password."""
        body = request.get_json() or {}

        email = body.get("email", "").lower().strip()
        password = body.get("password", "")
        name = body.get("name", "")
        callback_url = body.get("callbackURL")

        # Validate input
        if not email or "@" not in email:
            return jsonify({
                "type": "error",
                "code": "INVALID_EMAIL",
                "message": "Invalid email address"
            }), 400

        if not password or len(password) < 8:
            return jsonify({
                "type": "error",
                "code": "PASSWORD_TOO_SHORT",
                "message": "Password must be at least 8 characters"
            }), 400

        if not name:
            return jsonify({
                "type": "error",
                "code": "INVALID_NAME",
                "message": "Name is required"
            }), 400

        conn = get_db()
        try:
            # Check if user exists
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()

            if existing:
                return jsonify({
                    "type": "error",
                    "code": "USER_ALREADY_EXISTS",
                    "message": "An account with this email already exists"
                }), 422

            # Create user
            user_id = generate_id("u_")
            now = datetime.now(timezone.utc)

            conn.execute(
                """
                INSERT INTO users (id, email, name, email_verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, name, 1, now, now)
            )

            # Create credentials account
            account_id = generate_id("a_")
            hashed_password = hash_password(password)

            conn.execute(
                """
                INSERT INTO accounts (id, user_id, provider_id, account_id, password)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account_id, user_id, "credential", user_id, hashed_password)
            )

            conn.commit()

            # Auto sign-in after signup
            session = create_session(user_id, body.get("rememberMe", True))

            response = jsonify({
                "token": session["token"],
                "user": {
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "image": None,
                    "email_verified": True,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            })
            response.set_cookie(
                "better-auth.session_token",
                session["token"],
                httponly=True,
                samesite="none",
                secure=True,
                max_age=30 * 24 * 60 * 60  # 30 days
            )
            return response

        finally:
            conn.close()

    def sign_in_email():
        """Handle sign-in with email and password."""
        body = request.get_json() or {}

        email = body.get("email", "").lower().strip()
        password = body.get("password", "")

        if not email or "@" not in email:
            return jsonify({
                "type": "error",
                "code": "INVALID_EMAIL",
                "message": "Invalid email address"
            }), 400

        if not password:
            return jsonify({
                "type": "error",
                "code": "INVALID_PASSWORD",
                "message": "Password is required"
            }), 400

        conn = get_db()
        try:
            # Find user
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

            if not user:
                # Hash password anyway to prevent timing attacks
                hash_password(password)
                return jsonify({
                    "type": "error",
                    "code": "INVALID_EMAIL_OR_PASSWORD",
                    "message": "Invalid email or password"
                }), 401

            # Find credentials account
            account = conn.execute(
                "SELECT * FROM accounts WHERE user_id = ? AND provider_id = 'credential'",
                (user["id"],)
            ).fetchone()

            if not account or not account["password"]:
                hash_password(password)
                return jsonify({
                    "type": "error",
                    "code": "INVALID_EMAIL_OR_PASSWORD",
                    "message": "Invalid email or password"
                }), 401

            if not verify_password(password, account["password"]):
                return jsonify({
                    "type": "error",
                    "code": "INVALID_EMAIL_OR_PASSWORD",
                    "message": "Invalid email or password"
                }), 401

            # Create session
            remember_me = body.get("rememberMe", True)
            session = create_session(user["id"], remember_me)

            response = jsonify({
                "redirect": False,
                "token": session["token"],
                "url": None,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "image": user["image"],
                    "email_verified": bool(user["email_verified"]),
                    "created_at": user["created_at"].isoformat() if user["created_at"] else None,
                    "updated_at": user["updated_at"].isoformat() if user["updated_at"] else None,
                }
            })

            max_age = 30 * 24 * 60 * 60 if remember_me else 24 * 60 * 60
            response.set_cookie(
                "better-auth.session_token",
                session["token"],
                httponly=True,
                samesite="none",
                secure=True,
                max_age=max_age
            )
            return response

        finally:
            conn.close()

    def sign_out():
        """Handle sign-out."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if token:
            delete_session(token)

        response = jsonify({"status": True})
        response.delete_cookie(
            "better-auth.session_token",
            samesite="none",
            secure=True
        )
        return response

    def get_session():
        """Get current session."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return jsonify({
                "type": "error",
                "code": "UNAUTHORIZED",
                "message": "Not authenticated"
            }), 401

        session_data = get_session_from_token(token)
        if not session_data:
            return jsonify({
                "type": "error",
                "code": "SESSION_EXPIRED",
                "message": "Session expired or invalid"
            }), 401

        return jsonify({
            "session": session_data["session"],
            "user": session_data["user"]
        })

    def list_sessions():
        """List all sessions for the current user."""
        @require_auth
        def handler():
            conn = get_db()
            try:
                sessions = conn.execute(
                    """
                    SELECT id, expires_at, created_at, ip_address, user_agent
                    FROM sessions
                    WHERE user_id = ? AND expires_at > ?
                    ORDER BY created_at DESC
                    """,
                    (g.user["id"], datetime.now(timezone.utc))
                ).fetchall()

                return jsonify({
                    "sessions": [
                        {
                            "id": s["id"],
                            "expires_at": s["expires_at"].isoformat() if s["expires_at"] else None,
                            "created_at": s["created_at"].isoformat() if s["created_at"] else None,
                            "ip_address": s["ip_address"],
                            "user_agent": s["user_agent"],
                            "is_current": s["id"] == g.session["id"]
                        }
                        for s in sessions
                    ]
                })
            finally:
                conn.close()

        return handler()

    def revoke_session():
        """Revoke a specific session."""
        body = request.get_json() or {}
        session_id = body.get("session_id")

        if not session_id:
            return jsonify({
                "type": "error",
                "code": "INVALID_REQUEST",
                "message": "Session ID required"
            }), 400

        conn = get_db()
        try:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return jsonify({"status": True})
        finally:
            conn.close()

    def delete_user():
        """Delete the current user account."""
        @require_auth
        def handler():
            user_id = g.user["id"]
            conn = get_db()
            try:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                return jsonify({"status": True})
            finally:
                conn.close()

        return handler()

    def change_password():
        """Change user password."""
        body = request.get_json() or {}
        current_password = body.get("current_password", "")
        new_password = body.get("new_password", "")

        @require_auth
        def handler():
            if len(new_password) < 8:
                return jsonify({
                    "type": "error",
                    "code": "PASSWORD_TOO_SHORT",
                    "message": "Password must be at least 8 characters"
                }), 400

            conn = get_db()
            try:
                account = conn.execute(
                    "SELECT * FROM accounts WHERE user_id = ? AND provider_id = 'credential'",
                    (g.user["id"],)
                ).fetchone()

                if not account or not account["password"]:
                    return jsonify({
                        "type": "error",
                        "code": "INVALID_PASSWORD",
                        "message": "No password set"
                    }), 400

                if not verify_password(current_password, account["password"]):
                    return jsonify({
                        "type": "error",
                        "code": "INVALID_PASSWORD",
                        "message": "Current password is incorrect"
                    }), 400

                hashed = hash_password(new_password)
                conn.execute(
                    "UPDATE accounts SET password = ? WHERE user_id = ? AND provider_id = 'credential'",
                    (hashed, g.user["id"])
                )
                conn.commit()
                return jsonify({"status": True})
            finally:
                conn.close()

        return handler()

    def list_conversations():
        """List all conversations for the current user."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return jsonify({
                "type": "error",
                "code": "UNAUTHORIZED",
                "message": "Not authenticated"
            }), 401

        session_data = get_session_from_token(token)
        if not session_data:
            return jsonify({
                "type": "error",
                "code": "SESSION_EXPIRED",
                "message": "Session expired or invalid"
            }), 401

        conn = get_conv_db()
        try:
            conversations = conn.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (session_data["user"]["id"],)
            ).fetchall()

            return jsonify({
                "conversations": [
                    {
                        "id": c["id"],
                        "title": c["title"],
                        "created_at": c["created_at"].isoformat() if c["created_at"] else None,
                        "updated_at": c["updated_at"].isoformat() if c["updated_at"] else None,
                    }
                    for c in conversations
                ]
            })
        finally:
            conn.close()

    def get_conversation():
        """Get a specific conversation with all messages."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return jsonify({
                "type": "error",
                "code": "UNAUTHORIZED",
                "message": "Not authenticated"
            }), 401

        session_data = get_session_from_token(token)
        if not session_data:
            return jsonify({
                "type": "error",
                "code": "SESSION_EXPIRED",
                "message": "Session expired or invalid"
            }), 401

        conv_id = request.args.get("id")
        if not conv_id:
            return jsonify({
                "type": "error",
                "code": "INVALID_REQUEST",
                "message": "Conversation ID required"
            }), 400

        conn = get_conv_db()
        try:
            conv = conn.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, session_data["user"]["id"])
            ).fetchone()

            if not conv:
                return jsonify({
                    "type": "error",
                    "code": "NOT_FOUND",
                    "message": "Conversation not found"
                }), 404

            import json
            messages = json.loads(conv["messages"]) if conv["messages"] else []

            return jsonify({
                "id": conv["id"],
                "title": conv["title"],
                "messages": messages,
                "created_at": conv["created_at"].isoformat() if conv["created_at"] else None,
                "updated_at": conv["updated_at"].isoformat() if conv["updated_at"] else None,
            })
        finally:
            conn.close()

    def save_conversation():
        """Save or update a conversation."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return jsonify({
                "type": "error",
                "code": "UNAUTHORIZED",
                "message": "Not authenticated"
            }), 401

        session_data = get_session_from_token(token)
        if not session_data:
            return jsonify({
                "type": "error",
                "code": "SESSION_EXPIRED",
                "message": "Session expired or invalid"
            }), 401

        body = request.get_json() or {}
        conv_id = body.get("id")
        title = body.get("title", "")
        messages = body.get("messages", [])

        if not title:
            # Use first user message as title
            for msg in messages:
                if msg.get("role") == "user":
                    title = msg.get("content", "")[:50]
                    break
            if not title:
                title = "New conversation"

        conn = get_conv_db()
        try:
            now = datetime.now(timezone.utc)

            if conv_id:
                # Update existing
                import json
                conn.execute(
                    """
                    UPDATE conversations
                    SET title = ?, messages = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (title, json.dumps(messages), now, conv_id, session_data["user"]["id"])
                )
            else:
                # Create new
                conv_id = generate_id("c_")
                import json
                conn.execute(
                    """
                    INSERT INTO conversations (id, user_id, title, messages, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (conv_id, session_data["user"]["id"], title, json.dumps(messages), now, now)
                )

            conn.commit()

            return jsonify({
                "id": conv_id,
                "title": title,
            })
        finally:
            conn.close()

    def delete_conversation():
        """Delete a conversation."""
        token = request.cookies.get("better-auth.session_token")
        if not token:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return jsonify({
                "type": "error",
                "code": "UNAUTHORIZED",
                "message": "Not authenticated"
            }), 401

        session_data = get_session_from_token(token)
        if not session_data:
            return jsonify({
                "type": "error",
                "code": "SESSION_EXPIRED",
                "message": "Session expired or invalid"
            }), 401

        body = request.get_json() or {}
        conv_id = body.get("id")

        if not conv_id:
            return jsonify({
                "type": "error",
                "code": "INVALID_REQUEST",
                "message": "Conversation ID required"
            }), 400

        conn = get_conv_db()
        try:
            conn.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, session_data["user"]["id"])
            )
            conn.commit()
            return jsonify({"status": True})
        finally:
            conn.close()

    # Initialize conversation DB
    init_conv_db()

    # Return route handlers
    return None, [
        ("POST", f"{base_url}/sign-up/email", sign_up_email),
        ("POST", f"{base_url}/sign-in/email", sign_in_email),
        ("POST", f"{base_url}/sign-out", sign_out),
        ("GET", f"{base_url}/session", get_session),
        ("GET", f"{base_url}/sessions", list_sessions),
        ("POST", f"{base_url}/session/revoke", revoke_session),
        ("DELETE", f"{base_url}/account", delete_user),
        ("POST", f"{base_url}/change-password", change_password),
        # Conversation endpoints
        ("GET", f"{base_url}/conversations", list_conversations),
        ("GET", f"{base_url}/conversation", get_conversation),
        ("POST", f"{base_url}/conversation", save_conversation),
        ("DELETE", f"{base_url}/conversation", delete_conversation),
    ]
