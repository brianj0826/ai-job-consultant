"""Queries and guarded write operations for the administrator console."""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from backend.services.database import (
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    STATUS_DISABLED,
    VALID_ROLES,
    VALID_STATUSES,
    get_connection,
)


class AdminActionError(Exception):
    """A user-facing, expected failure from an administrator action."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _pagination(page: int, page_size: int) -> tuple[int, int, int]:
    if page < 1:
        raise AdminActionError("page must be at least 1")
    if not 1 <= page_size <= 100:
        raise AdminActionError("page_size must be between 1 and 100")
    return page, page_size, (page - 1) * page_size


def _normalize_choice(value: str, valid_values: set[str], label: str) -> str:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    if normalized not in valid_values:
        choices = ", ".join(sorted(valid_values))
        raise AdminActionError(f"Invalid {label}; expected one of: {choices}")
    return normalized


def _audit(
    cursor,
    *,
    admin_user_id: int,
    action: str,
    target_type: str,
    target_id: Optional[int | str],
    details: dict[str, Any],
    metadata: Optional[Mapping[str, Optional[str]]],
) -> None:
    cursor.execute(
        """INSERT INTO admin_audit_logs
           (admin_user_id, action, target_type, target_id, details, ip_address, user_agent)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            admin_user_id,
            action,
            target_type,
            str(target_id) if target_id is not None else None,
            json.dumps(details, ensure_ascii=False, separators=(",", ":")),
            (metadata or {}).get("ip_address"),
            (metadata or {}).get("user_agent"),
        ),
    )


def _user_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "status": row["status"],
        "last_login_at": row.get("last_login_at"),
        "created_at": row.get("created_at"),
    }


def record_admin_auth_event(
    user: Mapping[str, Any],
    action: str,
    metadata: Optional[Mapping[str, Optional[str]]] = None,
) -> None:
    """Audit administrator sign-in/sign-out without storing credentials.

    Normal user authentication is intentionally not written to the admin audit
    stream.  This keeps the audit console focused on privileged activity.
    """
    if user.get("role") not in {ROLE_ADMIN, ROLE_SUPER_ADMIN}:
        return
    if action not in {"admin.login", "admin.logout"}:
        raise ValueError("invalid administrator authentication audit action")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _audit(
                cursor,
                admin_user_id=int(user["id"]),
                action=action,
                target_type="user",
                target_id=user["id"],
                details={"username": user.get("username"), "role": user.get("role")},
                metadata=metadata,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_overview() -> dict[str, Any]:
    """Return privacy-preserving aggregate counts for the admin dashboard."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT
                       COUNT(*) AS total_users,
                       COALESCE(SUM(CASE WHEN status = %s THEN 1 ELSE 0 END), 0) AS active_users,
                       COALESCE(SUM(CASE WHEN role IN (%s, %s) THEN 1 ELSE 0 END), 0) AS administrators,
                       COALESCE(SUM(CASE WHEN DATE(created_at) = UTC_DATE() THEN 1 ELSE 0 END), 0) AS new_users_today,
                       COALESCE(SUM(CASE WHEN DATE(last_login_at) = UTC_DATE() THEN 1 ELSE 0 END), 0) AS logins_today
                   FROM users""",
                (STATUS_ACTIVE, ROLE_ADMIN, ROLE_SUPER_ADMIN),
            )
            users = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) AS total_sessions FROM sessions")
            sessions = cursor.fetchone()
            cursor.execute(
                """SELECT
                       COUNT(*) AS total_messages,
                       COALESCE(SUM(CASE WHEN feedback = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                       COALESCE(SUM(CASE WHEN feedback = 'dislike' THEN 1 ELSE 0 END), 0) AS dislikes,
                       COALESCE(SUM(CASE WHEN feedback IS NOT NULL THEN 1 ELSE 0 END), 0) AS rated_messages
                   FROM messages"""
            )
            messages = cursor.fetchone()
            cursor.execute(
                """SELECT COUNT(*) AS active_auth_sessions
                   FROM auth_sessions
                   WHERE revoked_at IS NULL AND expires_at > UTC_TIMESTAMP()"""
            )
            auth_sessions = cursor.fetchone()
        return {
            "users": {
                "total": users["total_users"],
                "active": users["active_users"],
                "administrators": users["administrators"],
                "new_today": users["new_users_today"],
                "logins_today": users["logins_today"],
            },
            "conversations": {"total": sessions["total_sessions"]},
            "messages": {"total": messages["total_messages"]},
            "feedback": {
                "likes": messages["likes"],
                "dislikes": messages["dislikes"],
                "rated": messages["rated_messages"],
            },
            "auth_sessions": {"active": auth_sessions["active_auth_sessions"]},
        }
    finally:
        conn.close()


def list_users(page: int, page_size: int, search: Optional[str] = None) -> dict[str, Any]:
    """List users with only the aggregate usage data needed for management."""
    page, page_size, offset = _pagination(page, page_size)
    where_parts: list[str] = []
    params: list[Any] = []
    if search and search.strip():
        where_parts.append("u.username LIKE %s")
        params.append(f"%{search.strip()}%")
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) AS total FROM users AS u {where_clause}", tuple(params))
            total = cursor.fetchone()["total"]
            cursor.execute(
                f"""SELECT u.id, u.username, u.role, u.status, u.last_login_at, u.created_at,
                           COUNT(DISTINCT s.id) AS session_count,
                           COUNT(DISTINCT m.id) AS message_count
                    FROM users AS u
                    LEFT JOIN sessions AS s ON s.user_id = u.id
                    LEFT JOIN messages AS m ON m.user_id = u.id
                    {where_clause}
                    GROUP BY u.id, u.username, u.role, u.status, u.last_login_at, u.created_at
                    ORDER BY u.id DESC
                    LIMIT %s OFFSET %s""",
                tuple(params + [page_size, offset]),
            )
            rows = cursor.fetchall()
        return {
            "items": [
                {
                    **_user_summary(row),
                    "session_count": row["session_count"],
                    "message_count": row["message_count"],
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    finally:
        conn.close()


def _locked_user(cursor, user_id: int) -> Optional[dict[str, Any]]:
    cursor.execute(
        """SELECT id, username, role, status, last_login_at, created_at
           FROM users WHERE id = %s FOR UPDATE""",
        (user_id,),
    )
    return cursor.fetchone()


def _active_super_admin_count(cursor) -> int:
    # Lock the rows, not merely a count, so two concurrent changes cannot both
    # remove the final active super-admin.
    cursor.execute(
        """SELECT id FROM users
           WHERE role = %s AND status = %s FOR UPDATE""",
        (ROLE_SUPER_ADMIN, STATUS_ACTIVE),
    )
    return len(cursor.fetchall())


def update_user_status(
    actor: Mapping[str, Any],
    user_id: int,
    new_status: str,
    metadata: Optional[Mapping[str, Optional[str]]] = None,
) -> dict[str, Any]:
    """Enable/disable an account, revoke sessions when disabling, and audit it."""
    new_status = _normalize_choice(new_status, VALID_STATUSES, "status")
    actor_id = int(actor["id"])
    actor_role = actor["role"]
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            target = _locked_user(cursor, user_id)
            if not target:
                raise AdminActionError("User not found", 404)
            if target["id"] == actor_id and new_status != target["status"]:
                raise AdminActionError("You cannot change your own account status")
            if target["role"] != ROLE_USER and actor_role != ROLE_SUPER_ADMIN:
                raise AdminActionError("Only a super-admin can change a privileged account", 403)
            if target["status"] == new_status:
                conn.commit()
                return _user_summary(target)
            if (
                target["role"] == ROLE_SUPER_ADMIN
                and target["status"] == STATUS_ACTIVE
                and new_status == STATUS_DISABLED
                and _active_super_admin_count(cursor) <= 1
            ):
                raise AdminActionError("The final active super-admin cannot be disabled")

            cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
            revoked_sessions = 0
            if new_status == STATUS_DISABLED:
                cursor.execute(
                    """UPDATE auth_sessions SET revoked_at = UTC_TIMESTAMP()
                       WHERE user_id = %s AND revoked_at IS NULL""",
                    (user_id,),
                )
                revoked_sessions = cursor.rowcount
            _audit(
                cursor,
                admin_user_id=actor_id,
                action="user.status_updated",
                target_type="user",
                target_id=user_id,
                details={
                    "username": target["username"],
                    "previous_status": target["status"],
                    "new_status": new_status,
                    "revoked_sessions": revoked_sessions,
                },
                metadata=metadata,
            )
            target["status"] = new_status
        conn.commit()
        return _user_summary(target)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_user_role(
    actor: Mapping[str, Any],
    user_id: int,
    new_role: str,
    metadata: Optional[Mapping[str, Optional[str]]] = None,
) -> dict[str, Any]:
    """Change a role with super-admin and last-super-admin safeguards."""
    new_role = _normalize_choice(new_role, VALID_ROLES, "role")
    actor_id = int(actor["id"])
    if actor["role"] != ROLE_SUPER_ADMIN:
        raise AdminActionError("Only a super-admin can assign roles", 403)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            target = _locked_user(cursor, user_id)
            if not target:
                raise AdminActionError("User not found", 404)
            if target["id"] == actor_id and new_role != target["role"]:
                raise AdminActionError("You cannot change your own role")
            if target["role"] == new_role:
                conn.commit()
                return _user_summary(target)
            if (
                target["role"] == ROLE_SUPER_ADMIN
                and target["status"] == STATUS_ACTIVE
                and new_role != ROLE_SUPER_ADMIN
                and _active_super_admin_count(cursor) <= 1
            ):
                raise AdminActionError("The final active super-admin cannot be demoted")

            cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
            _audit(
                cursor,
                admin_user_id=actor_id,
                action="user.role_updated",
                target_type="user",
                target_id=user_id,
                details={
                    "username": target["username"],
                    "previous_role": target["role"],
                    "new_role": new_role,
                },
                metadata=metadata,
            )
            target["role"] = new_role
        conn.commit()
        return _user_summary(target)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_feedback(
    page: int,
    page_size: int,
    feedback: Optional[str] = None,
) -> dict[str, Any]:
    """List rated assistant answers for the quality-review screen."""
    page, page_size, offset = _pagination(page, page_size)
    where_parts = ["m.role = 'assistant'", "m.feedback IS NOT NULL"]
    params: list[Any] = []
    if feedback is not None:
        feedback = _normalize_choice(feedback, {"like", "dislike"}, "feedback")
        where_parts.append("m.feedback = %s")
        params.append(feedback)
    where_clause = " AND ".join(where_parts)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM messages AS m WHERE {where_clause}",
                tuple(params),
            )
            total = cursor.fetchone()["total"]
            cursor.execute(
                f"""SELECT m.id, m.user_id, u.username, m.session_id, m.feedback,
                           LEFT(m.content, 2000) AS content, m.timestamp
                    FROM messages AS m
                    LEFT JOIN users AS u ON u.id = m.user_id
                    WHERE {where_clause}
                    ORDER BY m.timestamp DESC, m.id DESC
                    LIMIT %s OFFSET %s""",
                tuple(params + [page_size, offset]),
            )
            rows = cursor.fetchall()
        return {
            "items": [
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "session_id": row["session_id"],
                    "feedback": row["feedback"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    finally:
        conn.close()


def list_audit_logs(
    page: int,
    page_size: int,
    action: Optional[str] = None,
) -> dict[str, Any]:
    """List administrator write records in reverse chronological order."""
    page, page_size, offset = _pagination(page, page_size)
    where_clause = ""
    params: list[Any] = []
    if action and action.strip():
        where_clause = "WHERE l.action = %s"
        params.append(action.strip())

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM admin_audit_logs AS l {where_clause}",
                tuple(params),
            )
            total = cursor.fetchone()["total"]
            cursor.execute(
                f"""SELECT l.id, l.admin_user_id, u.username AS admin_username,
                           l.action, l.target_type, l.target_id, l.details,
                           l.ip_address, l.user_agent, l.created_at
                    FROM admin_audit_logs AS l
                    LEFT JOIN users AS u ON u.id = l.admin_user_id
                    {where_clause}
                    ORDER BY l.id DESC
                    LIMIT %s OFFSET %s""",
                tuple(params + [page_size, offset]),
            )
            rows = cursor.fetchall()
        items = []
        for row in rows:
            try:
                details = json.loads(row["details"]) if row["details"] else None
            except (TypeError, json.JSONDecodeError):
                details = row["details"]
            items.append(
                {
                    "id": row["id"],
                    "admin_user_id": row["admin_user_id"],
                    "admin_username": row["admin_username"],
                    "action": row["action"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "details": details,
                    "ip_address": row["ip_address"],
                    "user_agent": row["user_agent"],
                    "created_at": row["created_at"],
                }
            )
        return {"items": items, "page": page, "page_size": page_size, "total": total}
    finally:
        conn.close()
