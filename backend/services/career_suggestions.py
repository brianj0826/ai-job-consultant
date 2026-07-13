"""Durable, user-confirmed AI suggestions for structured career resources."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any, Iterable

import pymysql
from pydantic import ValidationError

from backend.schemas.career import (
    ApplicationSuggestionCreate,
    CareerSuggestionDraft,
    InterviewCreate,
    InterviewQuestionsSuggestionCreate,
    JobCreate,
    ReportCreate,
    ResumeCreate,
    SkillCreate,
)
from backend.services import career
from backend.services.database import get_connection


logger = logging.getLogger("aiagent.career_suggestions")
MAX_SUGGESTIONS_PER_MESSAGE = 3
MAX_JSON_BYTES = 256 * 1024
PENDING = "pending"
ACCEPTED = "accepted"
DISMISSED = "dismissed"

_PAYLOAD_MODELS = {
    "resumes": ResumeCreate,
    "jobs": JobCreate,
    "applications": ApplicationSuggestionCreate,
    "interviews": InterviewCreate,
    "reports": ReportCreate,
    "skills": SkillCreate,
    "interview_questions": InterviewQuestionsSuggestionCreate,
}


def _model_values(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _parse_model(model_type, value: Any):
    if hasattr(model_type, "model_validate"):
        return model_type.model_validate(value)
    return model_type.parse_obj(value)


def _model_field_names(model_type) -> set[str]:
    fields = getattr(model_type, "model_fields", None)
    if fields is None:
        fields = getattr(model_type, "__fields__", {})
    return set(fields)


def _reject_unknown_fields(value: Any, allowed: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise career.CareerDataError(f"Invalid {label}: expected an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise career.CareerDataError(
            f"Invalid {label}: unknown fields: {', '.join(unknown)}"
        )


def _json_default(value: Any):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _encode_json(value: Any, *, label: str) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise career.CareerDataError(f"{label} exceeds {MAX_JSON_BYTES} UTF-8 bytes")
    return encoded


def _decode_json(value: Any, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _public_timestamp(value: Any):
    """Return JSON-safe UTC timestamps for HTTP, history, and raw SSE payloads."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def validate_suggestion_draft(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate untrusted model output and return canonical JSON-safe values."""
    try:
        _reject_unknown_fields(
            raw,
            {"resource_type", "title", "reason", "payload", "relation_hints"},
            "career suggestion",
        )
        draft = _parse_model(CareerSuggestionDraft, raw)
        resource_type = draft.resource_type
        payload_type = _PAYLOAD_MODELS[resource_type]
        _reject_unknown_fields(
            raw.get("payload"),
            _model_field_names(payload_type),
            f"{resource_type} suggestion payload",
        )
        if resource_type == "interview_questions":
            questions = raw["payload"].get("questions")
            if isinstance(questions, list):
                allowed_question_fields = {
                    "question",
                    "reference_answer",
                    "coaching_notes",
                }
                for index, question in enumerate(questions):
                    _reject_unknown_fields(
                        question,
                        allowed_question_fields,
                        f"interview question {index + 1}",
                    )
        payload_model = _parse_model(payload_type, draft.payload)
    except (ValidationError, KeyError, TypeError, ValueError) as error:
        raise career.CareerDataError(f"Invalid career suggestion: {error}") from error
    values = _model_values(draft)
    values["payload"] = _model_values(payload_model)
    # Suggestions are deliberately conservative create drafts. The model and
    # subsequent browser edits cannot silently change lifecycle/default state.
    if resource_type == "resumes":
        values["payload"]["is_primary"] = False
    elif resource_type == "jobs":
        values["payload"]["status"] = "saved"
    elif resource_type == "applications":
        stage = (values["payload"].get("stage") or "saved").strip().lower()
        if stage not in career.APPLICATION_STAGES:
            raise career.CareerDataError(f"Invalid application stage: {stage}")
        values["payload"]["stage"] = stage
    elif resource_type == "interviews":
        values["payload"]["status"] = "planned"
        values["payload"]["overall_score"] = None
    elif resource_type == "reports":
        kind = (values["payload"].get("kind") or "").strip().lower()
        if kind not in career.REPORT_KINDS:
            raise career.CareerDataError(f"Invalid report kind: {kind}")
        entity_type = values["payload"].get("entity_type")
        entity_id = values["payload"].get("entity_id")
        if (entity_type is None) != (entity_id is None):
            raise career.CareerDataError(
                "Report entity_type and entity_id must be provided together"
            )
        if entity_type is not None and entity_type not in career.REPORT_ENTITY_TYPES:
            raise career.CareerDataError(f"Invalid report entity type: {entity_type}")
        values["payload"]["kind"] = kind
        values["payload"]["payload"] = {
            **values["payload"].get("payload", {}),
            "schema_version": 1,
        }
    elif resource_type == "skills":
        values["payload"]["status"] = "planned"
        values["payload"]["progress"] = 0
    # Relation hints are display-only. They are never used to authorize or
    # choose a record during acceptance.
    if not isinstance(values.get("relation_hints"), dict):
        values["relation_hints"] = {}
    _encode_json(values["payload"], label="Suggestion payload")
    _encode_json(values["relation_hints"], label="Suggestion relation hints")
    return values


def insert_suggestions_with_cursor(
    cursor,
    user_id: int,
    session_id: int,
    assistant_message_id: int,
    drafts: Iterable[dict[str, Any]],
) -> list[int]:
    """Insert validated suggestions using the caller's chat transaction."""
    cursor.execute(
        """SELECT id FROM messages
           WHERE id = %s AND user_id = %s AND session_id = %s
             AND role = 'assistant' LIMIT 1""",
        (assistant_message_id, user_id, session_id),
    )
    if not cursor.fetchone():
        raise career.CareerNotFoundError("Assistant message not found")

    inserted_ids: list[int] = []
    for raw in list(drafts or [])[:MAX_SUGGESTIONS_PER_MESSAGE]:
        try:
            draft = validate_suggestion_draft(raw)
        except career.CareerDataError as error:
            logger.warning(
                "Discarded invalid AI career suggestion resource=%s error=%s",
                raw.get("resource_type") if isinstance(raw, dict) else "unknown",
                type(error).__name__,
            )
            continue
        payload_json = _encode_json(draft["payload"], label="Suggestion payload")
        hints_json = _encode_json(
            draft.get("relation_hints", {}),
            label="Suggestion relation hints",
        )
        payload_hash = hashlib.sha256(
            f"{draft['resource_type']}\n{payload_json}".encode("utf-8")
        ).hexdigest()
        cursor.execute(
            """INSERT INTO career_suggestions
               (user_id, session_id, assistant_message_id, action,
                resource_type, title, reason, payload, relation_hints,
                payload_hash, revision, status)
               VALUES (%s, %s, %s, 'create', %s, %s, %s, %s, %s, %s, 1, 'pending')
               ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)""",
            (
                user_id,
                session_id,
                assistant_message_id,
                draft["resource_type"],
                draft["title"],
                draft.get("reason", ""),
                payload_json,
                hints_json,
                payload_hash,
            ),
        )
        inserted_ids.append(int(cursor.lastrowid))
    return inserted_ids


def create_suggestions(
    user_id: int,
    session_id: int,
    assistant_message_id: int,
    drafts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist suggestions for an already committed assistant message."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            insert_suggestions_with_cursor(
                cursor,
                user_id,
                session_id,
                assistant_message_id,
                drafts,
            )
        connection.commit()
        return get_message_suggestions(user_id, assistant_message_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def serialize_suggestion_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["payload"] = _decode_json(result.get("payload"), {})
    result["relation_hints"] = _decode_json(result.get("relation_hints"), {})
    result_ids = _decode_json(result.get("result_resource_ids"), [])
    created_resource = None
    if result.get("status") == ACCEPTED and result.get("result_resource_type"):
        created_resource = {
            "resource_type": result["result_resource_type"],
            "ids": [int(value) for value in result_ids],
        }
        if len(created_resource["ids"]) == 1:
            created_resource["id"] = created_resource["ids"][0]
    public = {
        "id": int(result["id"]),
        "revision": int(result.get("revision") or 1),
        "action": result.get("action") or "create",
        "resource_type": result["resource_type"],
        "title": result["title"],
        "reason": result.get("reason") or "",
        "payload": result["payload"],
        "relation_hints": result["relation_hints"],
        "status": result["status"],
        "source_message_id": int(result["assistant_message_id"]),
        "created_at": _public_timestamp(result.get("created_at")),
        "updated_at": _public_timestamp(result.get("updated_at")),
        "decided_at": _public_timestamp(result.get("decided_at")),
        "created_resource": created_resource,
    }
    return public


def get_suggestions_for_messages(
    user_id: int,
    message_ids: Iterable[int],
) -> dict[int, list[dict[str, Any]]]:
    normalized_ids = list(dict.fromkeys(int(value) for value in message_ids))
    grouped = {message_id: [] for message_id in normalized_ids}
    if not normalized_ids:
        return grouped
    placeholders = ", ".join(["%s"] * len(normalized_ids))
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT * FROM career_suggestions
                    WHERE user_id = %s
                      AND assistant_message_id IN ({placeholders})
                    ORDER BY assistant_message_id, id""",
                (user_id, *normalized_ids),
            )
            for row in cursor.fetchall():
                grouped[int(row["assistant_message_id"])].append(
                    serialize_suggestion_row(row)
                )
        return grouped
    finally:
        connection.close()


def get_message_suggestions(user_id: int, message_id: int) -> list[dict[str, Any]]:
    return get_suggestions_for_messages(user_id, [message_id]).get(int(message_id), [])


def _owned_suggestion(cursor, user_id: int, suggestion_id: int, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        f"SELECT * FROM career_suggestions WHERE id = %s AND user_id = %s LIMIT 1{suffix}",
        (suggestion_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        raise career.CareerNotFoundError("Career suggestion not found")
    return row


def _integrity_error(error: pymysql.err.IntegrityError):
    code = error.args[0] if error.args else None
    if code == 1062:
        return career.CareerConflictError("Career resource already exists")
    if code == 1452:
        return career.CareerConflictError(
            "Suggestion references a career resource that no longer exists"
        )
    return error


def accept_suggestion(
    user_id: int,
    suggestion_id: int,
    expected_revision: int,
) -> dict[str, Any]:
    connection = get_connection()
    suggestion_loaded = False
    try:
        with connection.cursor() as cursor:
            row = _owned_suggestion(cursor, user_id, suggestion_id, lock=True)
            suggestion_loaded = True
            if row["status"] == ACCEPTED:
                # A retried POST may carry the pre-transition revision because
                # the first 200 response was lost. Replay that accepted result
                # without creating another resource.
                if int(expected_revision) not in {
                    int(row["revision"]),
                    int(row["revision"]) - 1,
                }:
                    raise career.CareerConflictError("Suggestion revision is stale")
                connection.commit()
                return serialize_suggestion_row(row)
            if int(row["revision"]) != int(expected_revision):
                raise career.CareerConflictError("Suggestion revision is stale")
            if row["status"] != PENDING:
                raise career.CareerConflictError("Dismissed suggestion must be restored first")
            career._lock_user(cursor, user_id)
            resource_type = row["resource_type"]
            validated = validate_suggestion_draft(
                {
                    "resource_type": resource_type,
                    "title": row["title"],
                    "reason": row.get("reason") or "",
                    "payload": _decode_json(row.get("payload"), {}),
                    "relation_hints": _decode_json(row.get("relation_hints"), {}),
                }
            )
            payload = validated["payload"]
            if resource_type == "applications" and payload.get("job_id") is None:
                raise career.CareerConflictError(
                    "Choose an owned job before accepting this application suggestion"
                )
            if resource_type == "interview_questions" and payload.get("interview_id") is None:
                raise career.CareerConflictError(
                    "Choose an owned interview before accepting this question batch"
                )
            if resource_type == "interview_questions":
                result = career.create_suggested_interview_questions_with_cursor(
                    cursor,
                    user_id,
                    payload,
                )
                result_resource_ids = [
                    int(question["id"]) for question in result["questions"]
                ]
            else:
                result = career.create_suggested_resource_with_cursor(
                    cursor,
                    user_id,
                    resource_type,
                    payload,
                )
                result_resource_ids = [int(result["id"])]
            cursor.execute(
                """UPDATE career_suggestions
                   SET status = 'accepted', result_resource_type = %s,
                       result_resource_ids = %s,
                       decided_at = UTC_TIMESTAMP(), revision = revision + 1
                   WHERE id = %s AND user_id = %s AND status = 'pending'""",
                (
                    resource_type,
                    _encode_json(result_resource_ids, label="Suggestion result IDs"),
                    suggestion_id,
                    user_id,
                ),
            )
            if cursor.rowcount != 1:
                raise career.CareerConflictError("Career suggestion state changed")
            accepted = _owned_suggestion(cursor, user_id, suggestion_id)
        connection.commit()
        return serialize_suggestion_row(accepted)
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        translated = _integrity_error(error)
        if translated is error:
            raise
        raise translated from error
    except career.CareerNotFoundError as error:
        connection.rollback()
        if not suggestion_loaded:
            raise
        raise career.CareerConflictError(
            "Suggestion references a career resource that no longer exists"
        ) from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def dismiss_suggestion(
    user_id: int,
    suggestion_id: int,
    expected_revision: int,
) -> dict[str, Any]:
    return _transition_suggestion(user_id, suggestion_id, expected_revision, DISMISSED)


def restore_suggestion(
    user_id: int,
    suggestion_id: int,
    expected_revision: int,
) -> dict[str, Any]:
    return _transition_suggestion(user_id, suggestion_id, expected_revision, PENDING)


def _transition_suggestion(
    user_id: int,
    suggestion_id: int,
    expected_revision: int,
    target_status: str,
) -> dict[str, Any]:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            row = _owned_suggestion(cursor, user_id, suggestion_id, lock=True)
            status = row["status"]
            if status == ACCEPTED:
                raise career.CareerConflictError("Accepted suggestion cannot be changed")
            if status == target_status:
                if int(expected_revision) not in {
                    int(row["revision"]),
                    int(row["revision"]) - 1,
                }:
                    raise career.CareerConflictError("Suggestion revision is stale")
                connection.commit()
                return serialize_suggestion_row(row)
            if int(row["revision"]) != int(expected_revision):
                raise career.CareerConflictError("Suggestion revision is stale")
            career._lock_user(cursor, user_id)
            expected = PENDING if target_status == DISMISSED else DISMISSED
            if status != expected:
                raise career.CareerConflictError("Career suggestion state changed")
            decided_sql = "UTC_TIMESTAMP()" if target_status == DISMISSED else "NULL"
            cursor.execute(
                f"""UPDATE career_suggestions
                    SET status = %s, decided_at = {decided_sql}, revision = revision + 1
                    WHERE id = %s AND user_id = %s AND status = %s""",
                (target_status, suggestion_id, user_id, expected),
            )
            updated = _owned_suggestion(cursor, user_id, suggestion_id)
        connection.commit()
        return serialize_suggestion_row(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def revise_suggestion(
    user_id: int,
    suggestion_id: int,
    expected_revision: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            row = _owned_suggestion(cursor, user_id, suggestion_id, lock=True)
            if row["status"] != PENDING:
                raise career.CareerConflictError("Only pending suggestions can be edited")
            career._lock_user(cursor, user_id)
            if int(row["revision"]) != int(expected_revision):
                raise career.CareerConflictError("Suggestion revision is stale")
            draft = validate_suggestion_draft(
                {
                    "resource_type": row["resource_type"],
                    "title": row["title"],
                    "reason": row.get("reason") or "",
                    "payload": payload,
                    "relation_hints": _decode_json(row.get("relation_hints"), {}),
                }
            )
            payload_json = _encode_json(draft["payload"], label="Suggestion payload")
            payload_hash = hashlib.sha256(
                f"{row['resource_type']}\n{payload_json}".encode("utf-8")
            ).hexdigest()
            cursor.execute(
                """UPDATE career_suggestions
                   SET payload = %s, payload_hash = %s,
                       revision = revision + 1
                   WHERE id = %s AND user_id = %s AND status = 'pending'
                     AND revision = %s""",
                (
                    payload_json,
                    payload_hash,
                    suggestion_id,
                    user_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise career.CareerConflictError("Suggestion revision is stale")
            updated = _owned_suggestion(cursor, user_id, suggestion_id)
        connection.commit()
        return serialize_suggestion_row(updated)
    except pymysql.err.IntegrityError as error:
        connection.rollback()
        if error.args and error.args[0] == 1062:
            raise career.CareerConflictError("An identical suggestion already exists") from error
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
