"""Cookie-session authentication and authorization dependencies.

The browser receives two random values at login:

* ``session_token`` is HttpOnly and is the credential used to load a session.
* ``csrf_token`` is readable by the frontend and must be echoed in the
  ``X-CSRF-Token`` header for state-changing authenticated requests.

Only SHA-256 digests of both values are stored in MySQL.  The raw session token
is never persisted or logged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Optional

import pymysql
from fastapi import HTTPException, Request, Response, status

from backend.services.database import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    STATUS_ACTIVE,
    get_connection,
    hash_password,
)


SESSION_COOKIE_NAME = "session_token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
USERNAME_MIN_LENGTH = 2
USERNAME_MAX_LENGTH = 64
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# A deliberately small in-process protection for password guessing.  It is
# keyed by the direct client IP and normalized username, configurable for
# deployments, and successful logins clear only that principal's failures.
_failed_login_attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_failed_login_attempts_lock = threading.Lock()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def session_ttl_seconds() -> int:
    """Return a bounded session lifetime (default: 7 days)."""
    hours = _bounded_int_env("SESSION_TTL_HOURS", 168, 1, 24 * 30)
    return hours * 60 * 60


def login_failure_limit() -> int:
    return _bounded_int_env("LOGIN_FAILURE_LIMIT", 5, 1, 50)


def login_failure_window_seconds() -> int:
    return _bounded_int_env("LOGIN_FAILURE_WINDOW_SECONDS", 900, 60, 86_400)


def _login_attempt_key(ip_address: Optional[str], username: str) -> tuple[str, str]:
    return ((ip_address or "unknown")[:45], username.casefold())


def _prune_attempts(attempts: deque[float], now: float, window: int) -> None:
    while attempts and now - attempts[0] >= window:
        attempts.popleft()


def login_retry_after(ip_address: Optional[str], username: str) -> int:
    """Return remaining seconds before another password attempt is accepted."""
    now = time.monotonic()
    window = login_failure_window_seconds()
    key = _login_attempt_key(ip_address, username)
    with _failed_login_attempts_lock:
        attempts = _failed_login_attempts.get(key)
        if not attempts:
            return 0
        _prune_attempts(attempts, now, window)
        if not attempts:
            _failed_login_attempts.pop(key, None)
            return 0
        if len(attempts) < login_failure_limit():
            return 0
        return max(1, int(window - (now - attempts[0])) + 1)


def record_failed_login(ip_address: Optional[str], username: str) -> None:
    """Record a failed password attempt after credentials have been checked."""
    now = time.monotonic()
    window = login_failure_window_seconds()
    key = _login_attempt_key(ip_address, username)
    with _failed_login_attempts_lock:
        attempts = _failed_login_attempts[key]
        _prune_attempts(attempts, now, window)
        attempts.append(now)


def clear_failed_logins(ip_address: Optional[str], username: str) -> None:
    """Clear only this IP+username failure bucket after a successful login."""
    with _failed_login_attempts_lock:
        _failed_login_attempts.pop(_login_attempt_key(ip_address, username), None)


def session_cookie_secure() -> bool:
    """Default to secure cookies outside explicitly local environments."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    default = app_env not in {"development", "dev", "local", "test"}
    return _bool_env("SESSION_COOKIE_SECURE", default)


def session_cookie_samesite() -> str:
    value = os.getenv("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    if value not in {"lax", "strict", "none"}:
        return "lax"
    return value


def session_cookie_domain() -> Optional[str]:
    value = os.getenv("SESSION_COOKIE_DOMAIN", "").strip()
    return value or None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValueError("Username must be a string")
    normalized = username.strip()
    if not USERNAME_MIN_LENGTH <= len(normalized) <= USERNAME_MAX_LENGTH:
        raise ValueError(
            f"Username must contain {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} characters"
        )
    if any(ord(character) < 32 for character in normalized):
        raise ValueError("Username cannot contain control characters")
    return normalized


def validate_password(password: str) -> str:
    if not isinstance(password, str):
        raise ValueError("Password must be a string")
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must contain {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters"
        )
    return password


@dataclass(frozen=True)
class AuthenticatedUser:
    """Current user and the authenticated server-side session."""

    id: int
    username: str
    role: str
    status: str
    session_id: int
    csrf_token_hash: str
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @property
    def is_admin(self) -> bool:
        return self.role in {ROLE_ADMIN, ROLE_SUPER_ADMIN}

    @property
    def is_super_admin(self) -> bool:
        return self.role == ROLE_SUPER_ADMIN

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "status": self.status,
            "last_login_at": self.last_login_at,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SessionCredentials:
    """Raw values that exist only long enough to be written as cookies."""

    session_token: str
    csrf_token: str
    expires_at: datetime


class BootstrapConfigurationError(RuntimeError):
    """Raised for an unsafe or incomplete first-super-admin configuration."""


def request_metadata(request: Request) -> dict[str, Optional[str]]:
    """Collect only direct request metadata suitable for audit records."""
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return {
        "ip_address": client_host[:45] if client_host else None,
        "user_agent": user_agent[:512] if user_agent else None,
    }


def create_auth_session(
    user_id: int,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> SessionCredentials:
    """Create a server-side session and return raw cookie values once.

    Token collisions are astronomically unlikely, but retrying makes the unique
    database constraint the final authority without leaking a database error.
    """
    expires_at = _utcnow() + timedelta(seconds=session_ttl_seconds())
    for _ in range(3):
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO auth_sessions
                       (user_id, token_hash, csrf_token_hash, expires_at,
                        last_seen_at, ip_address, user_agent)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id,
                        _token_hash(session_token),
                        _token_hash(csrf_token),
                        expires_at,
                        _utcnow(),
                        ip_address[:45] if ip_address else None,
                        user_agent[:512] if user_agent else None,
                    ),
                )
            conn.commit()
            return SessionCredentials(session_token, csrf_token, expires_at)
        except pymysql.err.IntegrityError:
            conn.rollback()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    raise RuntimeError("Unable to create a unique authentication session")


def _load_authenticated_user(raw_session_token: str) -> Optional[AuthenticatedUser]:
    if not raw_session_token or len(raw_session_token) > 512:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT s.id AS session_id, s.user_id, s.csrf_token_hash,
                          u.username, u.role, u.status, u.last_login_at, u.created_at
                   FROM auth_sessions AS s
                   INNER JOIN users AS u ON u.id = s.user_id
                   WHERE s.token_hash = %s
                     AND s.revoked_at IS NULL
                     AND s.expires_at > UTC_TIMESTAMP()
                     AND u.status = %s
                   LIMIT 1""",
                (_token_hash(raw_session_token), STATUS_ACTIVE),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "UPDATE auth_sessions SET last_seen_at = UTC_TIMESTAMP() WHERE id = %s",
                (row["session_id"],),
            )
        conn.commit()
        return AuthenticatedUser(
            id=row["user_id"],
            username=row["username"],
            role=row["role"],
            status=row["status"],
            session_id=row["session_id"],
            csrf_token_hash=row["csrf_token_hash"],
            last_login_at=row["last_login_at"],
            created_at=row["created_at"],
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _request_auth_context(request: Request) -> AuthenticatedUser:
    """Load once per request and keep private session material off route data."""
    cached = getattr(request.state, "_auth_context", None)
    if cached is not None:
        return cached
    current_user = _load_authenticated_user(request.cookies.get(SESSION_COOKIE_NAME, ""))
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    request.state._auth_context = current_user
    return current_user


def require_current_user(request: Request) -> dict:
    """Return the active user as a mapping for direct route use or ``Depends``.

    It deliberately omits the session ID and CSRF digest.  Existing routes can
    safely use ``current_user[\"id\"]`` without gaining access to credential
    material, while :func:`require_csrf` uses the request-private context.
    """
    return _request_auth_context(request).public_dict()


def require_admin(request: Request) -> dict:
    """Require an ``admin`` or ``super_admin`` account."""
    current_user = require_current_user(request)
    if current_user["role"] not in {ROLE_ADMIN, ROLE_SUPER_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return current_user


def require_super_admin(request: Request) -> dict:
    """Require the highest privilege level for role assignment."""
    current_user = require_current_user(request)
    if current_user["role"] != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-admin access required")
    return current_user


def require_csrf(request: Request) -> None:
    """Require a double-submit CSRF token bound to the current session.

    The ``None`` return value makes this convenient both as ``Depends`` and as
    an explicit guard in the existing synchronous route functions.
    """
    current_user = _request_auth_context(request)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get(CSRF_HEADER_NAME, "")
    if not cookie_token or not header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token required")
    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    if not hmac.compare_digest(_token_hash(cookie_token), current_user.csrf_token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def require_admin_csrf(request: Request) -> dict:
    """Convenience dependency for state-changing administrator endpoints."""
    current_user = require_admin(request)
    require_csrf(request)
    return current_user


def current_session_id(request: Request) -> int:
    """Return the authenticated session ID after a normal auth guard has run."""
    return _request_auth_context(request).session_id


def revoke_auth_session(session_id: int, user_id: int) -> None:
    """Revoke exactly the current user's session; logout is idempotent."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE auth_sessions
                   SET revoked_at = COALESCE(revoked_at, UTC_TIMESTAMP())
                   WHERE id = %s AND user_id = %s""",
                (session_id, user_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_auth_cookies(response: Response, credentials: SessionCredentials) -> None:
    """Set the HttpOnly session cookie and the readable CSRF cookie."""
    secure = session_cookie_secure()
    samesite = session_cookie_samesite()
    domain = session_cookie_domain()
    max_age = max(1, int((credentials.expires_at - _utcnow()).total_seconds()))
    common = {
        "max_age": max_age,
        "path": "/",
        "domain": domain,
        "secure": secure,
        "samesite": samesite,
    }
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=credentials.session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=credentials.csrf_token,
        httponly=False,
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear both cookies using the same scope with which they were issued."""
    kwargs = {
        "path": "/",
        "domain": session_cookie_domain(),
        "secure": session_cookie_secure(),
        "httponly": True,
        "samesite": session_cookie_samesite(),
    }
    response.delete_cookie(SESSION_COOKIE_NAME, **kwargs)
    response.delete_cookie(CSRF_COOKIE_NAME, **{**kwargs, "httponly": False})


def bootstrap_first_admin_from_environment() -> Optional[dict]:
    """Create the first super-admin from explicit environment credentials.

    If an administrator already exists the environment values are ignored.  If
    the requested bootstrap username was pre-created as a normal user, startup
    fails rather than silently escalating an account that could be attacker
    controlled.
    """
    supplied_username = os.getenv("ADMIN_BOOTSTRAP_USERNAME")
    supplied_password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if supplied_username is None and supplied_password is None:
        return None
    if not supplied_username or not supplied_password:
        raise BootstrapConfigurationError(
            "ADMIN_BOOTSTRAP_USERNAME and ADMIN_BOOTSTRAP_PASSWORD must be set together"
        )

    try:
        username = normalize_username(supplied_username)
        password = validate_password(supplied_password)
    except ValueError as exc:
        raise BootstrapConfigurationError(str(exc)) from exc

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Lock existing super-admin rows during this bootstrap decision so
            # simultaneous application starts cannot both create a first admin.
            cursor.execute(
                "SELECT id, username FROM users WHERE role = %s LIMIT 1 FOR UPDATE",
                (ROLE_SUPER_ADMIN,),
            )
            existing_admin = cursor.fetchone()
            if existing_admin:
                conn.commit()
                return {"created": False, "username": existing_admin["username"]}

            cursor.execute("SELECT id FROM users WHERE username = %s FOR UPDATE", (username,))
            if cursor.fetchone():
                raise BootstrapConfigurationError(
                    "Bootstrap username already exists and is not a super-admin; refusing escalation"
                )

            cursor.execute(
                """INSERT INTO users (username, password_hash, role, status)
                   VALUES (%s, %s, %s, %s)""",
                (username, hash_password(password), ROLE_SUPER_ADMIN, STATUS_ACTIVE),
            )
            user_id = cursor.lastrowid
        conn.commit()
        return {"created": True, "id": user_id, "username": username}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
