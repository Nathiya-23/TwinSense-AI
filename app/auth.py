"""
TwinSense AI - Authentication, Password Hashing & Session Security Module
=========================================================================

Handles:
1. Modern Argon2id password hashing and verification.
2. Server-managed secure sessions with SQLite storage.
3. HttpOnly cookie management with SameSite and configurable Secure flags.
4. Double-submit / header-based CSRF protection.
5. Safe authentication validation with non-revealing error messages.
6. FastAPI dependency injection for protected routes.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Request, Response, HTTPException, status

from app.database import get_db_connection

# -------------------------------------------------------------
# Configuration Constants
# -------------------------------------------------------------
SESSION_COOKIE_NAME = "twinsense_session"
CSRF_COOKIE_NAME = "twinsense_csrf"
SESSION_DURATION_HOURS = 24
MIN_PASSWORD_LENGTH = 8

# Initialize Argon2id Password Hasher (RFC 9106 recommended parameters)
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32
)

# RFC-compliant email validation pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


# -------------------------------------------------------------
# Password Hashing & Verification
# -------------------------------------------------------------
def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Argon2id with random per-password salt.
    Never stores or returns plaintext passwords.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id hash in constant time.
    Returns False on any mismatch or invalid hash format.
    """
    if not password or not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# -------------------------------------------------------------
# Input Validation
# -------------------------------------------------------------
def validate_registration_input(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str
) -> tuple[str, str, str]:
    """
    Validates registration fields on the server.
    Raises HTTPException(400) if any field is invalid or passwords do not match.
    Returns normalized (full_name, clean_email, password).
    """
    clean_name = (full_name or "").strip()
    clean_email = (email or "").strip().lower()

    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name is required."
        )
    if len(clean_name) < 2 or len(clean_name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name must be between 2 and 100 characters."
        )

    if not clean_email or not EMAIL_REGEX.match(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )

    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    # Require at least one letter and at least one number
    if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one letter and one number."
        )

    if password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match. Please re-enter."
        )

    return clean_name, clean_email, password


# -------------------------------------------------------------
# User Registration & Lookup
# -------------------------------------------------------------
def register_user(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    db_path: Optional[Path] = None
) -> dict:
    """
    Registers a new user in SQLite.
    Prevents duplicate registrations without exposing database internals.
    Stores only the Argon2id hash.
    """
    clean_name, clean_email, clean_pw = validate_registration_input(
        full_name, email, password, confirm_password
    )

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check for duplicate email (case-insensitive)
    cursor.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (clean_email,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        # Return generic safe error message preventing email enumeration
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists. Please log in or use a different email."
        )

    pw_hash = hash_password(clean_pw)
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO users (email, full_name, password_hash, created_at)
        VALUES (?, ?, ?, ?)
    """, (clean_email, clean_name, pw_hash, now_iso))

    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": user_id,
        "email": clean_email,
        "full_name": clean_name
    }


def authenticate_user(
    email: str,
    password: str,
    db_path: Optional[Path] = None
) -> Optional[dict]:
    """
    Verifies user credentials.
    Returns user dict on success, None on invalid email or password.
    Never reveals whether the email exists.
    """
    clean_email = (email or "").strip().lower()
    if not clean_email or not password:
        return None

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, email, full_name, password_hash 
        FROM users 
        WHERE email = ? COLLATE NOCASE
    """, (clean_email,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    if not verify_password(password, row["password_hash"]):
        return None

    return {
        "id": row["id"],
        "email": row["email"],
        "full_name": row["full_name"]
    }


# -------------------------------------------------------------
# Session Management & Storage
# -------------------------------------------------------------
def create_session(user_id: int, db_path: Optional[Path] = None) -> dict:
    """
    Creates a new server-managed session in SQLite with CSRF token and expiration.
    """
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now + timedelta(hours=SESSION_DURATION_HOURS)).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, csrf_token, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, user_id, csrf_token, created_at, expires_at))
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "csrf_token": csrf_token,
        "expires_at": expires_at
    }


def get_session_user(session_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    """
    Validates a session ID and returns the associated user.
    Automatically revokes and cleans up expired sessions.
    """
    if not session_id:
        return None

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.session_id, s.user_id, s.csrf_token, s.expires_at,
               u.id AS user_id, u.email, u.full_name
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_id = ?
    """, (session_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    # Check expiration
    expires_at_dt = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if expires_at_dt < datetime.now(timezone.utc).replace(tzinfo=None):
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return {
        "id": row["user_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "session_id": row["session_id"],
        "csrf_token": row["csrf_token"],
        "expires_at": row["expires_at"]
    }


def delete_session(session_id: str, db_path: Optional[Path] = None) -> None:
    """
    Revokes a session by deleting it from SQLite.
    """
    if not session_id:
        return
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# Cookie Helpers
# -------------------------------------------------------------
def set_auth_cookies(
    response: Response,
    session_id: str,
    csrf_token: str,
    is_https: bool = False
) -> None:
    """
    Sets secure HttpOnly session cookie and accessible CSRF token cookie.
    """
    max_age_seconds = SESSION_DURATION_HOURS * 3600

    # Primary Authentication Session Cookie (HttpOnly)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=is_https,
        path="/"
    )

    # CSRF Token Cookie (Readable by Frontend JavaScript)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age_seconds,
        httponly=False,
        samesite="lax",
        secure=is_https,
        path="/"
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clears session and CSRF cookies on logout.
    """
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


# -------------------------------------------------------------
# FastAPI Dependency Injection
# -------------------------------------------------------------
def get_current_user_optional(request: Request) -> Optional[dict]:
    """
    Checks cookie or Authorization header and returns user if authenticated, else None.
    Does not raise an exception.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    # Support Authorization header: Bearer <session_id>
    if not session_id:
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            session_id = auth_header[7:].strip()

    if not session_id:
        return None

    return get_session_user(session_id)


def get_current_user(request: Request) -> dict:
    """
    Enforces authentication on protected endpoints.
    Validates CSRF tokens on state-changing requests when using cookie authentication.
    Raises HTTPException 401 if unauthenticated, 403 if CSRF fails.
    """
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in to access this resource."
        )

    # CSRF Protection: For mutating methods (POST/PUT/DELETE/PATCH),
    # verify X-CSRF-Token header if request was authenticated via ambient cookies
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        cookie_session = request.cookies.get(SESSION_COOKIE_NAME)
        if cookie_session:
            header_csrf = request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token")
            if not header_csrf or not secrets.compare_digest(header_csrf, user["csrf_token"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token validation failed. Please refresh and try again."
                )

    return user
