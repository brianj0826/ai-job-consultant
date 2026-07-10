"""Authorization helpers for application-owned resources.

Authentication answers *who* made a request.  These helpers answer whether
that authenticated user owns the session or message they are trying to use.
Keeping the checks here makes it much harder for a route to accidentally trust
an ID sent by the browser.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, status

from backend.services.database import get_connection


def current_user_id(current_user: Mapping[str, Any] | Any) -> int:
    """Return a validated user id from the auth dependency result.

    ``require_current_user`` deliberately returns a small public user record.
    Accept attribute-style objects too so this module remains usable if that
    record becomes a Pydantic model later.
    """
    if isinstance(current_user, Mapping):
        value = current_user.get("id")
    else:
        value = getattr(current_user, "id", None)

    try:
        user_id = int(value)
    except (TypeError, ValueError):
        user_id = 0

    if user_id <= 0:
        # This should only be reachable if the authentication dependency was
        # used incorrectly; do not let a malformed principal become user 0.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的登录身份",
        )
    return user_id


def get_owned_session(session_id: int, user_id: int) -> dict[str, Any]:
    """Fetch a session only when it belongs to ``user_id``.

    A not-found response is intentional for both missing and foreign sessions,
    so callers cannot enumerate another user's conversation IDs.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, name, created_at
                   FROM sessions
                   WHERE id = %s AND user_id = %s
                   LIMIT 1""",
                (session_id, user_id),
            )
            session = cursor.fetchone()
    finally:
        conn.close()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    return session


def require_owned_session(session_id: int, current_user: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Validate the current user's ownership of a conversation session."""
    return get_owned_session(session_id, current_user_id(current_user))


def get_owned_message(message_id: int, user_id: int) -> dict[str, Any]:
    """Fetch a message only when both it and its session belong to ``user_id``."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT m.id, m.user_id, m.session_id, m.role, m.feedback
                   FROM messages AS m
                   INNER JOIN sessions AS s ON s.id = m.session_id
                   WHERE m.id = %s
                     AND m.user_id = %s
                     AND s.user_id = %s
                   LIMIT 1""",
                (message_id, user_id, user_id),
            )
            message = cursor.fetchone()
    finally:
        conn.close()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在",
        )
    return message


def require_owned_message(message_id: int, current_user: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Validate the current user's ownership of a message."""
    return get_owned_message(message_id, current_user_id(current_user))
