"""Structured career-workspace persistence and ownership enforcement."""
from __future__ import annotations

from contextlib import contextmanager
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import pymysql

from backend.services.database import get_connection


logger = logging.getLogger("aiagent.career")
JOB_STATUSES = {"saved", "active", "archived"}
APPLICATION_STAGES = {
    "saved",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}
INTERVIEW_STATUSES = {"planned", "in_progress", "completed", "cancelled"}
REPORT_KINDS = {"resume_analysis", "job_match", "interview_review", "career_plan"}
REPORT_ENTITY_TYPES = {"resume", "job", "application", "interview", "skill"}
SKILL_STATUSES = {"planned", "in_progress", "completed", "paused"}
REPORT_PAYLOAD_MAX_BYTES = 256 * 1024


class CareerDataError(ValueError):
    """Raised when a structured career value is invalid."""


class CareerNotFoundError(LookupError):
    """Raised for missing resources and resources owned by another user."""


class CareerConflictError(RuntimeError):
    """Raised when a uniqueness constraint represents a user-facing conflict."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    result = dict(row)
    # Internal generated column used to enforce one primary resume per user.
    result.pop("primary_marker", None)
    for key, value in list(result.items()):
        if isinstance(value, Decimal):
            result[key] = float(value)
    if "is_primary" in result:
        result["is_primary"] = bool(result["is_primary"])
    payload = result.get("payload")
    if isinstance(payload, (str, bytes, bytearray)):
        try:
            result["payload"] = json.loads(payload)
        except (TypeError, ValueError):
            result["payload"] = {}
    return result


def _choice(value: str, allowed: set[str], label: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in allowed:
        raise CareerDataError(f"Invalid {label}: {value}")
    return normalized


def _require_non_null(changes: dict[str, Any], fields: set[str]) -> None:
    invalid = sorted(field for field in fields if field in changes and changes[field] is None)
    if invalid:
        raise CareerDataError(f"Fields cannot be null: {', '.join(invalid)}")


def _encode_report_payload(payload: Optional[dict[str, Any]]) -> str:
    encoded = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > REPORT_PAYLOAD_MAX_BYTES:
        raise CareerDataError(
            f"Report payload exceeds {REPORT_PAYLOAD_MAX_BYTES} UTF-8 bytes"
        )
    return encoded


@contextmanager
def career_data_guard(user_id: int, timeout_seconds: int = 30):
    """Serialize destructive privacy operations and knowledge-base writes.

    MySQL advisory locks are shared across application workers and instances.
    They cannot make MySQL and Chroma one transaction, but they prevent two
    cooperating request paths from mutating one user's stores concurrently.
    """
    connection = get_connection()
    lock_name = f"career-data-user-{int(user_id)}"
    acquired = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT GET_LOCK(%s, %s) AS acquired",
                (lock_name, max(0, min(int(timeout_seconds), 60))),
            )
            acquired = bool((cursor.fetchone() or {}).get("acquired"))
        if not acquired:
            raise CareerConflictError("Career data is busy; please retry")
        yield
    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
            except Exception:
                logger.exception("Failed to release career-data lock for user %s", user_id)
            finally:
                connection.close()
        else:
            connection.close()


def _owned_row(
    cursor,
    table: str,
    resource_id: int,
    user_id: int,
    *,
    columns: str = "*",
) -> dict[str, Any]:
    cursor.execute(
        f"SELECT {columns} FROM `{table}` WHERE id = %s AND user_id = %s LIMIT 1",
        (resource_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        raise CareerNotFoundError("Career resource not found")
    return row


def _lock_user(cursor, user_id: int) -> None:
    cursor.execute("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
    if not cursor.fetchone():
        raise CareerNotFoundError("User not found")


def _insert(cursor, table: str, values: dict[str, Any]) -> int:
    columns = ", ".join(f"`{name}`" for name in values)
    placeholders = ", ".join(["%s"] * len(values))
    cursor.execute(
        f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})",
        tuple(values.values()),
    )
    return int(cursor.lastrowid)


def _update(cursor, table: str, resource_id: int, user_id: int, changes: dict[str, Any]) -> None:
    if not changes:
        return
    assignments = ", ".join(f"`{name}` = %s" for name in changes)
    cursor.execute(
        f"UPDATE `{table}` SET {assignments} WHERE id = %s AND user_id = %s",
        (*changes.values(), resource_id, user_id),
    )


def _delete(table: str, resource_id: int, user_id: int) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, table, resource_id, user_id, columns="id")
            cursor.execute(
                f"DELETE FROM `{table}` WHERE id = %s AND user_id = %s",
                (resource_id, user_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _list_owned(table: str, user_id: int, limit: int, order_by: str = "updated_at DESC") -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) AS total FROM `{table}` WHERE user_id = %s", (user_id,))
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"SELECT * FROM `{table}` WHERE user_id = %s ORDER BY {order_by} LIMIT %s",
                (user_id, limit),
            )
            items = [_serialize(row) for row in cursor.fetchall()]
        return {"items": items, "total": total}
    finally:
        connection.close()


# Resumes -------------------------------------------------------------------


def list_resumes(user_id: int, limit: int = 100) -> dict:
    return _list_owned("career_resumes", user_id, limit, "is_primary DESC, updated_at DESC")


def get_resume(user_id: int, resume_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            return _serialize(_owned_row(cursor, "career_resumes", resume_id, user_id))
    finally:
        connection.close()


def create_resume(user_id: int, values: dict[str, Any]) -> dict:
    values = dict(values)
    values.setdefault("target_role", "")
    values.setdefault("source_name", None)
    values.setdefault("is_primary", False)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if values.get("is_primary"):
                _lock_user(cursor, user_id)
                cursor.execute("UPDATE career_resumes SET is_primary = FALSE WHERE user_id = %s", (user_id,))
            resume_id = _insert(cursor, "career_resumes", {"user_id": user_id, **values})
            result = _serialize(_owned_row(cursor, "career_resumes", resume_id, user_id))
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("A primary resume already exists") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_resume(user_id: int, resume_id: int, changes: dict[str, Any]) -> dict:
    _require_non_null(changes, {"title", "target_role", "content", "is_primary"})
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_resumes", resume_id, user_id, columns="id")
            if changes.get("is_primary"):
                _lock_user(cursor, user_id)
                cursor.execute(
                    "UPDATE career_resumes SET is_primary = FALSE WHERE user_id = %s AND id <> %s",
                    (user_id, resume_id),
                )
            _update(cursor, "career_resumes", resume_id, user_id, changes)
            result = _serialize(_owned_row(cursor, "career_resumes", resume_id, user_id))
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("A primary resume already exists") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_resume(user_id: int, resume_id: int) -> None:
    _delete("career_resumes", resume_id, user_id)


# Jobs ----------------------------------------------------------------------


def list_jobs(user_id: int, limit: int = 100) -> dict:
    return _list_owned("career_jobs", user_id, limit)


def get_job(user_id: int, job_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            return _serialize(_owned_row(cursor, "career_jobs", job_id, user_id))
    finally:
        connection.close()


def create_job(user_id: int, values: dict[str, Any]) -> dict:
    values = dict(values)
    values.setdefault("company", "")
    values.setdefault("source_url", None)
    values["status"] = _choice(values.get("status", "saved"), JOB_STATUSES, "job status")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            job_id = _insert(cursor, "career_jobs", {"user_id": user_id, **values})
            result = _serialize(_owned_row(cursor, "career_jobs", job_id, user_id))
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_job(user_id: int, job_id: int, changes: dict[str, Any]) -> dict:
    changes = dict(changes)
    _require_non_null(changes, {"title", "company", "description", "status"})
    if "status" in changes:
        changes["status"] = _choice(changes["status"], JOB_STATUSES, "job status")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_jobs", job_id, user_id, columns="id")
            _update(cursor, "career_jobs", job_id, user_id, changes)
            result = _serialize(_owned_row(cursor, "career_jobs", job_id, user_id))
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_job(user_id: int, job_id: int) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_jobs", job_id, user_id, columns="id")
            # Preserve interview history while satisfying the composite
            # ownership FK; applications still cascade with the job.
            cursor.execute(
                "UPDATE career_interviews SET job_id = NULL WHERE user_id = %s AND job_id = %s",
                (user_id, job_id),
            )
            cursor.execute(
                "DELETE FROM career_jobs WHERE id = %s AND user_id = %s",
                (job_id, user_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# Applications --------------------------------------------------------------


def _application_query(where: str) -> str:
    return f"""
        SELECT a.*, j.title AS job_title, j.company
        FROM career_applications AS a
        INNER JOIN career_jobs AS j ON j.id = a.job_id AND j.user_id = a.user_id
        WHERE {where}
    """


def _application_row(cursor, user_id: int, application_id: int) -> dict:
    cursor.execute(
        _application_query("a.id = %s AND a.user_id = %s") + " LIMIT 1",
        (application_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        raise CareerNotFoundError("Career resource not found")
    return _serialize(row)


def list_applications(user_id: int, limit: int = 100) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM career_applications WHERE user_id = %s", (user_id,))
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                _application_query("a.user_id = %s") + " ORDER BY a.updated_at DESC LIMIT %s",
                (user_id, limit),
            )
            return {"items": [_serialize(row) for row in cursor.fetchall()], "total": total}
    finally:
        connection.close()


def get_application(user_id: int, application_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            return _application_row(cursor, user_id, application_id)
    finally:
        connection.close()


def create_application(user_id: int, values: dict[str, Any]) -> dict:
    values = dict(values)
    values.setdefault("next_action", "")
    values.setdefault("deadline", None)
    values.setdefault("notes", "")
    values["stage"] = _choice(values.get("stage", "saved"), APPLICATION_STAGES, "application stage")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_jobs", int(values["job_id"]), user_id, columns="id")
            application_id = _insert(cursor, "career_applications", {"user_id": user_id, **values})
            result = _application_row(cursor, user_id, application_id)
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("This job already has an application") from error
        if error.args and error.args[0] == 1452:
            raise CareerNotFoundError("Career resource not found") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_application(user_id: int, application_id: int, changes: dict[str, Any]) -> dict:
    changes = dict(changes)
    _require_non_null(changes, {"job_id", "stage", "next_action", "notes"})
    if "stage" in changes:
        changes["stage"] = _choice(changes["stage"], APPLICATION_STAGES, "application stage")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_applications", application_id, user_id, columns="id")
            if "job_id" in changes:
                _owned_row(cursor, "career_jobs", int(changes["job_id"]), user_id, columns="id")
            _update(cursor, "career_applications", application_id, user_id, changes)
            result = _application_row(cursor, user_id, application_id)
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("This job already has an application") from error
        if error.args and error.args[0] == 1452:
            raise CareerNotFoundError("Career resource not found") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_application(user_id: int, application_id: int) -> None:
    _delete("career_applications", application_id, user_id)


# Interviews ----------------------------------------------------------------


def _interview_query(where: str) -> str:
    return f"""
        SELECT i.*, j.title AS job_title, j.company
        FROM career_interviews AS i
        LEFT JOIN career_jobs AS j ON j.id = i.job_id AND j.user_id = i.user_id
        WHERE {where}
    """


def _interview_detail(cursor, user_id: int, interview_id: int) -> dict:
    cursor.execute(
        _interview_query("i.id = %s AND i.user_id = %s") + " LIMIT 1",
        (interview_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        raise CareerNotFoundError("Career resource not found")
    cursor.execute(
        "SELECT * FROM career_interview_questions WHERE interview_id = %s ORDER BY position, id",
        (interview_id,),
    )
    result = _serialize(row)
    result["questions"] = [_serialize(item) for item in cursor.fetchall()]
    return result


def list_interviews(user_id: int, limit: int = 100) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM career_interviews WHERE user_id = %s", (user_id,))
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                _interview_query("i.user_id = %s") + " ORDER BY i.updated_at DESC LIMIT %s",
                (user_id, limit),
            )
            return {"items": [_serialize(row) for row in cursor.fetchall()], "total": total}
    finally:
        connection.close()


def get_interview(user_id: int, interview_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            return _interview_detail(cursor, user_id, interview_id)
    finally:
        connection.close()


def create_interview(user_id: int, values: dict[str, Any]) -> dict:
    values = dict(values)
    values.setdefault("job_id", None)
    values.setdefault("overall_score", None)
    values["status"] = _choice(values.get("status", "planned"), INTERVIEW_STATUSES, "interview status")
    values["completed_at"] = _utcnow() if values["status"] == "completed" else None
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if values.get("job_id") is not None:
                _owned_row(cursor, "career_jobs", int(values["job_id"]), user_id, columns="id")
            interview_id = _insert(cursor, "career_interviews", {"user_id": user_id, **values})
            result = _interview_detail(cursor, user_id, interview_id)
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1452:
            raise CareerNotFoundError("Career resource not found") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_interview(user_id: int, interview_id: int, changes: dict[str, Any]) -> dict:
    changes = dict(changes)
    _require_non_null(changes, {"title", "status"})
    if "status" in changes:
        changes["status"] = _choice(changes["status"], INTERVIEW_STATUSES, "interview status")
        changes["completed_at"] = _utcnow() if changes["status"] == "completed" else None
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_interviews", interview_id, user_id, columns="id")
            if changes.get("job_id") is not None:
                _owned_row(cursor, "career_jobs", int(changes["job_id"]), user_id, columns="id")
            _update(cursor, "career_interviews", interview_id, user_id, changes)
            result = _interview_detail(cursor, user_id, interview_id)
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1452:
            raise CareerNotFoundError("Career resource not found") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_interview(user_id: int, interview_id: int) -> None:
    _delete("career_interviews", interview_id, user_id)


def _refresh_interview_stats(cursor, interview_id: int, user_id: int) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN answer <> '' THEN 1 ELSE 0 END) AS answered,
               AVG(score) AS average_score
        FROM career_interview_questions
        WHERE interview_id = %s
        """,
        (interview_id,),
    )
    stats = cursor.fetchone()
    cursor.execute(
        """
        UPDATE career_interviews
        SET total_questions = %s, current_question = %s, overall_score = %s
        WHERE id = %s AND user_id = %s
        """,
        (
            int(stats["total"] or 0),
            int(stats["answered"] or 0),
            stats["average_score"],
            interview_id,
            user_id,
        ),
    )


def add_interview_question(user_id: int, interview_id: int, values: dict[str, Any]) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_interviews", interview_id, user_id, columns="id")
            values = dict(values)
            values.setdefault("answer", "")
            values.setdefault("score", None)
            values.setdefault("feedback", "")
            if values.get("position") is None:
                cursor.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM career_interview_questions WHERE interview_id = %s",
                    (interview_id,),
                )
                values["position"] = int(cursor.fetchone()["next_position"])
            question_id = _insert(cursor, "career_interview_questions", {"interview_id": interview_id, **values})
            _refresh_interview_stats(cursor, interview_id, user_id)
            cursor.execute("SELECT * FROM career_interview_questions WHERE id = %s", (question_id,))
            result = _serialize(cursor.fetchone())
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("Question position already exists") from error
        if error.args and error.args[0] == 1452:
            raise CareerNotFoundError("Career resource not found") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_interview_question(
    user_id: int,
    interview_id: int,
    question_id: int,
    changes: dict[str, Any],
) -> dict:
    _require_non_null(changes, {"position", "question", "answer", "feedback"})
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_interviews", interview_id, user_id, columns="id")
            cursor.execute(
                "SELECT id FROM career_interview_questions WHERE id = %s AND interview_id = %s LIMIT 1",
                (question_id, interview_id),
            )
            if not cursor.fetchone():
                raise CareerNotFoundError("Interview question not found")
            if changes:
                assignments = ", ".join(f"`{name}` = %s" for name in changes)
                cursor.execute(
                    f"UPDATE career_interview_questions SET {assignments} WHERE id = %s AND interview_id = %s",
                    (*changes.values(), question_id, interview_id),
                )
            _refresh_interview_stats(cursor, interview_id, user_id)
            cursor.execute("SELECT * FROM career_interview_questions WHERE id = %s", (question_id,))
            result = _serialize(cursor.fetchone())
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("Question position already exists") from error
        if error.args and error.args[0] == 1452:
            raise CareerNotFoundError("Career resource not found") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_interview_question(user_id: int, interview_id: int, question_id: int) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_interviews", interview_id, user_id, columns="id")
            cursor.execute(
                "DELETE FROM career_interview_questions WHERE id = %s AND interview_id = %s",
                (question_id, interview_id),
            )
            if cursor.rowcount != 1:
                raise CareerNotFoundError("Interview question not found")
            _refresh_interview_stats(cursor, interview_id, user_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# Reports -------------------------------------------------------------------


_REPORT_ENTITY_TABLES = {
    "resume": "career_resumes",
    "job": "career_jobs",
    "application": "career_applications",
    "interview": "career_interviews",
    "skill": "career_skills",
}


def _validate_report_entity(
    cursor,
    user_id: int,
    entity_type: Optional[str],
    entity_id: Optional[int],
) -> tuple[Optional[str], Optional[int]]:
    if entity_type is None and entity_id is None:
        return None, None
    if not entity_type or entity_id is None:
        raise CareerDataError("entity_type and entity_id must be provided together")
    entity_type = _choice(entity_type, REPORT_ENTITY_TYPES, "report entity type")
    _owned_row(
        cursor,
        _REPORT_ENTITY_TABLES[entity_type],
        int(entity_id),
        user_id,
        columns="id",
    )
    return entity_type, int(entity_id)


def list_reports(user_id: int, limit: int = 100, kind: Optional[str] = None) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            params: list[Any] = [user_id]
            where = "user_id = %s"
            if kind:
                kind = _choice(kind, REPORT_KINDS, "report kind")
                where += " AND kind = %s"
                params.append(kind)
            cursor.execute(f"SELECT COUNT(*) AS total FROM career_reports WHERE {where}", tuple(params))
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                f"SELECT * FROM career_reports WHERE {where} ORDER BY created_at DESC LIMIT %s",
                (*params, limit),
            )
            return {"items": [_serialize(row) for row in cursor.fetchall()], "total": total}
    finally:
        connection.close()


def get_report(user_id: int, report_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            return _serialize(_owned_row(cursor, "career_reports", report_id, user_id))
    finally:
        connection.close()


def create_report(user_id: int, values: dict[str, Any]) -> dict:
    values = dict(values)
    values.setdefault("entity_type", None)
    values.setdefault("entity_id", None)
    values["kind"] = _choice(values["kind"], REPORT_KINDS, "report kind")
    values["payload"] = _encode_report_payload(values.get("payload"))
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            entity_type, entity_id = _validate_report_entity(
                cursor,
                user_id,
                values.get("entity_type"),
                values.get("entity_id"),
            )
            values["entity_type"] = entity_type
            values["entity_id"] = entity_id
            report_id = _insert(cursor, "career_reports", {"user_id": user_id, **values})
            result = _serialize(_owned_row(cursor, "career_reports", report_id, user_id))
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_report(user_id: int, report_id: int, changes: dict[str, Any]) -> dict:
    changes = dict(changes)
    _require_non_null(changes, {"kind", "title", "summary"})
    if "kind" in changes:
        changes["kind"] = _choice(changes["kind"], REPORT_KINDS, "report kind")
    if "payload" in changes:
        changes["payload"] = _encode_report_payload(changes["payload"])
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            existing = _owned_row(
                cursor,
                "career_reports",
                report_id,
                user_id,
                columns="id, entity_type, entity_id",
            )
            if "entity_type" in changes or "entity_id" in changes:
                entity_type, entity_id = _validate_report_entity(
                    cursor,
                    user_id,
                    changes.get("entity_type", existing.get("entity_type")),
                    changes.get("entity_id", existing.get("entity_id")),
                )
                changes["entity_type"] = entity_type
                changes["entity_id"] = entity_id
            _update(cursor, "career_reports", report_id, user_id, changes)
            result = _serialize(_owned_row(cursor, "career_reports", report_id, user_id))
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_report(user_id: int, report_id: int) -> None:
    _delete("career_reports", report_id, user_id)


# Skills --------------------------------------------------------------------


def list_skills(user_id: int, limit: int = 100) -> dict:
    return _list_owned("career_skills", user_id, limit, "status, due_date, updated_at DESC")


def get_skill(user_id: int, skill_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            return _serialize(_owned_row(cursor, "career_skills", skill_id, user_id))
    finally:
        connection.close()


def create_skill(user_id: int, values: dict[str, Any]) -> dict:
    values = dict(values)
    values.setdefault("target_level", "")
    values.setdefault("progress", 0)
    values.setdefault("due_date", None)
    values.setdefault("notes", "")
    values["status"] = _choice(values.get("status", "planned"), SKILL_STATUSES, "skill status")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            skill_id = _insert(cursor, "career_skills", {"user_id": user_id, **values})
            result = _serialize(_owned_row(cursor, "career_skills", skill_id, user_id))
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("This skill already exists") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_skill(user_id: int, skill_id: int, changes: dict[str, Any]) -> dict:
    changes = dict(changes)
    _require_non_null(changes, {"skill", "target_level", "status", "progress", "notes"})
    if "status" in changes:
        changes["status"] = _choice(changes["status"], SKILL_STATUSES, "skill status")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            _owned_row(cursor, "career_skills", skill_id, user_id, columns="id")
            _update(cursor, "career_skills", skill_id, user_id, changes)
            result = _serialize(_owned_row(cursor, "career_skills", skill_id, user_id))
        connection.commit()
        return result
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise CareerConflictError("This skill already exists") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_skill(user_id: int, skill_id: int) -> None:
    _delete("career_skills", skill_id, user_id)


def create_suggested_resource_with_cursor(
    cursor,
    user_id: int,
    resource_type: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Create one validated suggestion target inside the caller's transaction.

    Suggestion acceptance must update its state and create the career resource
    atomically.  This cursor-level entry point mirrors the public create
    operations without opening or committing a second connection.
    """
    values = dict(values)
    if resource_type == "resumes":
        values.setdefault("target_role", "")
        values.setdefault("source_name", None)
        values["is_primary"] = False
        resource_id = _insert(cursor, "career_resumes", {"user_id": user_id, **values})
        return _serialize(_owned_row(cursor, "career_resumes", resource_id, user_id))

    if resource_type == "jobs":
        values.setdefault("company", "")
        values.setdefault("source_url", None)
        values["status"] = "saved"
        resource_id = _insert(cursor, "career_jobs", {"user_id": user_id, **values})
        return _serialize(_owned_row(cursor, "career_jobs", resource_id, user_id))

    if resource_type == "applications":
        values.setdefault("next_action", "")
        values.setdefault("deadline", None)
        values.setdefault("notes", "")
        values["stage"] = _choice(
            values.get("stage", "saved"),
            APPLICATION_STAGES,
            "application stage",
        )
        _owned_row(cursor, "career_jobs", int(values["job_id"]), user_id, columns="id")
        resource_id = _insert(
            cursor,
            "career_applications",
            {"user_id": user_id, **values},
        )
        return _application_row(cursor, user_id, resource_id)

    if resource_type == "interviews":
        values.setdefault("job_id", None)
        values["overall_score"] = None
        values["status"] = "planned"
        values["completed_at"] = None
        if values.get("job_id") is not None:
            _owned_row(cursor, "career_jobs", int(values["job_id"]), user_id, columns="id")
        resource_id = _insert(cursor, "career_interviews", {"user_id": user_id, **values})
        return _interview_detail(cursor, user_id, resource_id)

    if resource_type == "reports":
        values.setdefault("entity_type", None)
        values.setdefault("entity_id", None)
        values["kind"] = _choice(values["kind"], REPORT_KINDS, "report kind")
        values["payload"] = _encode_report_payload(values.get("payload"))
        entity_type, entity_id = _validate_report_entity(
            cursor,
            user_id,
            values.get("entity_type"),
            values.get("entity_id"),
        )
        values["entity_type"] = entity_type
        values["entity_id"] = entity_id
        resource_id = _insert(cursor, "career_reports", {"user_id": user_id, **values})
        return _serialize(_owned_row(cursor, "career_reports", resource_id, user_id))

    if resource_type == "skills":
        values.setdefault("target_level", "")
        values["progress"] = 0
        values.setdefault("due_date", None)
        values.setdefault("notes", "")
        values["status"] = "planned"
        resource_id = _insert(cursor, "career_skills", {"user_id": user_id, **values})
        return _serialize(_owned_row(cursor, "career_skills", resource_id, user_id))

    raise CareerDataError(f"Unsupported suggestion resource type: {resource_type}")


def create_suggested_interview_questions_with_cursor(
    cursor,
    user_id: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Create an entire suggested question batch or roll it back as one unit."""
    interview_id = int(values["interview_id"])
    _owned_row(cursor, "career_interviews", interview_id, user_id, columns="id")
    cursor.execute(
        "SELECT position FROM career_interview_questions WHERE interview_id = %s FOR UPDATE",
        (interview_id,),
    )
    used_positions = {int(row["position"]) for row in cursor.fetchall()}
    next_position = max(used_positions, default=0) + 1
    created: list[dict[str, Any]] = []
    for question in values["questions"]:
        question = dict(question)
        requested_position = question.pop("position", None)
        if requested_position is None:
            while next_position in used_positions:
                next_position += 1
            position = next_position
            next_position += 1
        else:
            position = int(requested_position)
        if position in used_positions:
            raise CareerConflictError(
                f"Interview question position {position} already exists"
            )
        used_positions.add(position)
        row = {
            "interview_id": interview_id,
            "position": position,
            "question": question["question"],
            "answer": "",
            "score": None,
            "feedback": "",
            "reference_answer": question.get("reference_answer", ""),
            "coaching_notes": question.get("coaching_notes", ""),
        }
        question_id = _insert(cursor, "career_interview_questions", row)
        cursor.execute(
            "SELECT * FROM career_interview_questions WHERE id = %s",
            (question_id,),
        )
        created.append(_serialize(cursor.fetchone()))
    _refresh_interview_stats(cursor, interview_id, user_id)
    return {"interview_id": interview_id, "questions": created}


def export_career_data(user_id: int) -> dict[str, Any]:
    """Return all structured career data for a portable user export."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM career_resumes WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,),
            )
            resumes = [_serialize(row) for row in cursor.fetchall()]

            cursor.execute(
                "SELECT * FROM career_jobs WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,),
            )
            jobs = [_serialize(row) for row in cursor.fetchall()]

            cursor.execute(
                _application_query("a.user_id = %s") + " ORDER BY a.updated_at DESC",
                (user_id,),
            )
            applications = [_serialize(row) for row in cursor.fetchall()]

            cursor.execute(
                _interview_query("i.user_id = %s") + " ORDER BY i.updated_at DESC",
                (user_id,),
            )
            interviews = [_serialize(row) for row in cursor.fetchall()]
            interview_ids = [int(item["id"]) for item in interviews]
            questions_by_interview: dict[int, list[dict[str, Any]]] = {
                interview_id: [] for interview_id in interview_ids
            }
            if interview_ids:
                placeholders = ", ".join(["%s"] * len(interview_ids))
                cursor.execute(
                    f"""SELECT * FROM career_interview_questions
                        WHERE interview_id IN ({placeholders})
                        ORDER BY interview_id, position, id""",
                    tuple(interview_ids),
                )
                for row in cursor.fetchall():
                    serialized = _serialize(row)
                    questions_by_interview[int(serialized["interview_id"])].append(serialized)
            for interview in interviews:
                interview["questions"] = questions_by_interview[int(interview["id"])]

            cursor.execute(
                "SELECT * FROM career_reports WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            reports = [_serialize(row) for row in cursor.fetchall()]

            cursor.execute(
                "SELECT * FROM career_skills WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,),
            )
            skills = [_serialize(row) for row in cursor.fetchall()]
            cursor.execute(
                "SELECT * FROM career_suggestions WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            from backend.services.career_suggestions import serialize_suggestion_row

            suggestions = [serialize_suggestion_row(row) for row in cursor.fetchall()]
        return {
            "exported_at": _utcnow(),
            "resumes": resumes,
            "jobs": jobs,
            "applications": applications,
            "interviews": interviews,
            "reports": reports,
            "skills": skills,
            "suggestions": suggestions,
        }
    finally:
        connection.close()


def delete_career_data(user_id: int) -> dict[str, int]:
    """Delete structured career data while retaining the account itself."""
    connection = get_connection()
    counts: dict[str, int] = {}
    tables = (
        "career_suggestions",
        "career_reports",
        "career_skills",
        "career_resumes",
        "career_interviews",
        "career_applications",
        "career_jobs",
    )
    try:
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f"DELETE FROM `{table}` WHERE user_id = %s", (user_id,))
                counts[table.removeprefix("career_")] = int(cursor.rowcount)
        connection.commit()
        return counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
