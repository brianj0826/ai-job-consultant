import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.routers import career as career_router
from backend.routers import sessions as sessions_router
from backend.schemas.career import CareerSuggestionDecision, CareerSuggestionRevision
from backend.services import career, career_suggestions, migrations


def _draft(resource_type, payload, **extra):
    return {
        "resource_type": resource_type,
        "title": extra.pop("title", "AI 建议"),
        "reason": extra.pop("reason", "来自对话"),
        "payload": payload,
        **extra,
    }


@pytest.mark.parametrize(
    ("resource_type", "payload", "expected"),
    [
        (
            "resumes",
            {"title": "后端简历", "content": "content", "is_primary": True},
            {"is_primary": False},
        ),
        (
            "jobs",
            {"title": "工程师", "description": "JD", "status": "active"},
            {"status": "saved"},
        ),
        (
            "interviews",
            {"title": "一面", "status": "completed", "overall_score": 99},
            {"status": "planned", "overall_score": None},
        ),
        (
            "skills",
            {"skill": "Redis", "status": "completed", "progress": 100},
            {"status": "planned", "progress": 0},
        ),
    ],
)
def test_suggestion_validation_forces_safe_create_defaults(
    resource_type,
    payload,
    expected,
):
    normalized = career_suggestions.validate_suggestion_draft(
        _draft(resource_type, payload)
    )
    for key, value in expected.items():
        assert normalized["payload"][key] == value


def test_suggestion_validation_enforces_domain_values_and_report_schema():
    report = career_suggestions.validate_suggestion_draft(
        _draft(
            "reports",
            {
                "kind": "career_plan",
                "title": "Plan",
                "summary": "Concrete next steps",
                "payload": {"schema_version": 99, "priority": "high"},
            },
        )
    )
    assert report["payload"]["payload"] == {
        "schema_version": 1,
        "priority": "high",
    }

    with pytest.raises(career.CareerDataError, match="Invalid application stage"):
        career_suggestions.validate_suggestion_draft(
            _draft("applications", {"job_id": 3, "stage": "invented"})
        )
    with pytest.raises(career.CareerDataError, match="Invalid report kind"):
        career_suggestions.validate_suggestion_draft(
            _draft(
                "reports",
                {"kind": "invented", "title": "Bad", "summary": "Bad report"},
            )
        )
    with pytest.raises(career.CareerDataError, match="must be provided together"):
        career_suggestions.validate_suggestion_draft(
            _draft(
                "reports",
                {
                    "kind": "career_plan",
                    "title": "Bad relation",
                    "summary": "Missing relation id",
                    "entity_type": "job",
                },
            )
        )


def test_interview_question_suggestion_is_a_bounded_batch():
    normalized = career_suggestions.validate_suggestion_draft(
        _draft(
            "interview_questions",
            {
                "interview_id": 4,
                "questions": [
                    {
                        "question": "如何设计缓存？",
                        "reference_answer": "先明确一致性要求",
                        "coaching_notes": "说明取舍",
                    }
                ],
            },
        )
    )
    assert normalized["payload"]["interview_id"] == 4
    assert normalized["payload"]["questions"][0]["reference_answer"] == "先明确一致性要求"

    with pytest.raises(career.CareerDataError, match="Invalid career suggestion"):
        career_suggestions.validate_suggestion_draft(
            _draft(
                "interview_questions",
                {
                    "interview_id": 4,
                    "questions": [{"question": str(index)} for index in range(11)],
                },
            )
        )


def test_pending_relations_may_wait_for_the_user_to_choose():
    application = career_suggestions.validate_suggestion_draft(
        _draft("applications", {"stage": "applied", "notes": "Applied today"})
    )
    questions = career_suggestions.validate_suggestion_draft(
        _draft(
            "interview_questions",
            {"questions": [{"question": "Explain cache penetration"}]},
        )
    )

    assert application["payload"]["job_id"] is None
    assert questions["payload"]["interview_id"] is None


@pytest.mark.parametrize(
    "draft",
    [
        _draft("skills", {"skill": "Redis", "user_id": 999}),
        {
            **_draft("skills", {"skill": "Redis"}),
            "user_id": 999,
        },
        _draft(
            "interview_questions",
            {
                "interview_id": 4,
                "questions": [{"question": "Q", "answer": "forged"}],
            },
        ),
        _draft(
            "interview_questions",
            {
                "interview_id": 4,
                "questions": [{"question": "Q", "position": 500}],
            },
        ),
    ],
)
def test_suggestion_validation_rejects_unknown_and_identity_fields(draft):
    with pytest.raises(career.CareerDataError, match="unknown fields"):
        career_suggestions.validate_suggestion_draft(draft)


def test_suggestion_mutation_contract_rejects_unknown_top_level_fields():
    with pytest.raises(ValidationError):
        CareerSuggestionRevision(
            revision=1,
            payload={"skill": "Redis"},
            title="cannot edit title",
        )
    with pytest.raises(ValidationError):
        CareerSuggestionDecision(revision=1, user_id=999)


def test_accept_route_uses_authenticated_user_and_forwards_revision(monkeypatch):
    calls = []
    monkeypatch.setattr(
        career_router.suggestion_service,
        "accept_suggestion",
        lambda user_id, suggestion_id, revision: calls.append(
            (user_id, suggestion_id, revision)
        )
        or {"id": suggestion_id},
    )

    result = career_router.accept_suggestion(
        12,
        CareerSuggestionDecision(revision=3),
        {"id": 7},
    )

    assert calls == [(7, 12, 3)]
    assert result == {"id": 12}


class _InsertCursor:
    def __init__(self):
        self.result = None
        self.lastrowid = 0
        self.inserted = []

    def execute(self, sql, params=None):
        if "SELECT id FROM messages" in sql:
            self.result = {"id": params[0]}
        elif "INSERT INTO career_suggestions" in sql:
            self.lastrowid += 1
            self.inserted.append(params)
            self.result = None

    def fetchone(self):
        return self.result


def test_chat_transaction_inserter_discards_invalid_and_caps_candidates():
    cursor = _InsertCursor()
    valid = _draft("skills", {"skill": "Redis"})
    invalid = _draft("skills", {})

    ids = career_suggestions.insert_suggestions_with_cursor(
        cursor,
        7,
        3,
        42,
        [invalid, valid, valid, valid, valid],
    )

    # Only the first three model candidates are considered; one is invalid.
    assert ids == [1, 2]
    assert len(cursor.inserted) == 2


def test_invalid_suggestion_logs_never_include_payload(caplog):
    cursor = _InsertCursor()
    sensitive_marker = "PRIVATE_RESUME_SENTINEL"
    invalid = _draft("skills", {"skill": sensitive_marker * 30})

    career_suggestions.insert_suggestions_with_cursor(cursor, 7, 3, 42, [invalid])

    assert sensitive_marker not in caplog.text
    assert "resource=skills" in caplog.text
    assert "error=CareerDataError" in caplog.text


def test_suggestion_serialization_uses_result_resource_ids():
    row = {
        "id": 8,
        "revision": 2,
        "action": "create",
        "resource_type": "interview_questions",
        "title": "系统设计题",
        "reason": "准备面试",
        "payload": json.dumps({"interview_id": 3, "questions": []}),
        "relation_hints": "{}",
        "status": "accepted",
        "assistant_message_id": 99,
        "result_resource_type": "interview_questions",
        "result_resource_ids": "[11,12]",
        "created_at": datetime(2026, 7, 13, 9, 10, 11),
        "updated_at": datetime(2026, 7, 13, 9, 11, 12),
        "decided_at": datetime(2026, 7, 13, 9, 12, 13),
    }

    result = career_suggestions.serialize_suggestion_row(row)

    assert result["source_message_id"] == 99
    assert result["created_resource"] == {
        "resource_type": "interview_questions",
        "ids": [11, 12],
    }
    assert result["created_at"] == "2026-07-13T09:10:11Z"
    assert result["updated_at"] == "2026-07-13T09:11:12Z"
    assert result["decided_at"] == "2026-07-13T09:12:13Z"
    # Raw SSE uses json.dumps rather than FastAPI's jsonable_encoder.
    assert json.loads(json.dumps(result))["created_at"] == "2026-07-13T09:10:11Z"


class _SuggestionCursor:
    def __init__(self, row):
        self.row = row
        self.result = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        if "SELECT * FROM career_suggestions" in sql:
            requested_user = params[1]
            self.result = dict(self.row) if requested_user == self.row["user_id"] else None
            self.rowcount = 0
        elif "UPDATE career_suggestions" in sql and "status = 'accepted'" in sql:
            self.row["status"] = "accepted"
            self.row["result_resource_type"] = params[0]
            self.row["result_resource_ids"] = params[1]
            self.row["revision"] += 1
            self.rowcount = 1
            self.result = None
        elif "UPDATE career_suggestions" in sql and "SET status = %s" in sql:
            self.row["status"] = params[0]
            self.row["decided_at"] = None if params[0] == "pending" else "now"
            self.row["revision"] += 1
            self.rowcount = 1
            self.result = None
        elif "SET payload = %s" in sql:
            self.row["payload"] = params[0]
            self.row["payload_hash"] = params[1]
            self.row["revision"] += 1
            self.rowcount = 1
            self.result = None

    def fetchone(self):
        return self.result


class _SuggestionConnection:
    def __init__(self, row):
        self.cursor_instance = _SuggestionCursor(row)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _pending_skill_row():
    return {
        "id": 5,
        "user_id": 7,
        "session_id": 3,
        "assistant_message_id": 42,
        "action": "create",
        "resource_type": "skills",
        "title": "学习 Redis",
        "reason": "岗位差距",
        "payload": json.dumps({"skill": "Redis"}),
        "relation_hints": "{}",
        "payload_hash": "x" * 64,
        "revision": 2,
        "status": "pending",
        "result_resource_type": None,
        "result_resource_ids": None,
        "created_at": None,
        "updated_at": None,
        "decided_at": None,
    }


def test_accept_is_atomic_and_repeated_accept_replays_result(monkeypatch):
    row = _pending_skill_row()
    connection = _SuggestionConnection(row)
    creations = []
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)
    monkeypatch.setattr(
        career_suggestions.career,
        "create_suggested_resource_with_cursor",
        lambda cursor, user_id, resource_type, payload: creations.append(payload)
        or {"id": 77},
    )

    first = career_suggestions.accept_suggestion(7, 5, 2)
    second = career_suggestions.accept_suggestion(7, 5, 2)

    assert creations == [
        {
            "skill": "Redis",
            "target_level": "",
            "status": "planned",
            "progress": 0,
            "due_date": None,
            "notes": "",
        }
    ]
    assert first["created_resource"]["ids"] == [77]
    assert second["created_resource"]["id"] == 77
    assert first["revision"] == second["revision"] == 3
    assert connection.rollbacks == 0


def test_accept_rejects_stale_revision_before_creation(monkeypatch):
    connection = _SuggestionConnection(_pending_skill_row())
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)

    with pytest.raises(career.CareerConflictError, match="revision is stale"):
        career_suggestions.accept_suggestion(7, 5, 1)

    assert connection.rollbacks == 1


def test_accept_requires_the_user_to_finish_a_pending_relation(monkeypatch):
    row = _pending_skill_row()
    row.update(
        resource_type="applications",
        payload=json.dumps({"job_id": None, "stage": "applied"}),
    )
    connection = _SuggestionConnection(row)
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)

    with pytest.raises(career.CareerConflictError, match="Choose an owned job"):
        career_suggestions.accept_suggestion(7, 5, 2)

    assert connection.rollbacks == 1


def test_revise_uses_optimistic_revision_and_forces_defaults(monkeypatch):
    row = _pending_skill_row()
    connection = _SuggestionConnection(row)
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)

    updated = career_suggestions.revise_suggestion(
        7,
        5,
        2,
        {"skill": "Redis Cluster", "status": "completed", "progress": 80},
    )

    assert updated["revision"] == 3
    assert updated["payload"]["skill"] == "Redis Cluster"
    assert updated["payload"]["status"] == "planned"
    assert updated["payload"]["progress"] == 0
    with pytest.raises(career.CareerConflictError, match="revision is stale"):
        career_suggestions.revise_suggestion(7, 5, 2, {"skill": "stale"})


def test_dismiss_restore_and_accepted_terminal_state(monkeypatch):
    row = _pending_skill_row()
    connection = _SuggestionConnection(row)
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)

    dismissed = career_suggestions.dismiss_suggestion(7, 5, 2)
    assert dismissed["status"] == "dismissed"
    assert dismissed["revision"] == 3
    # Retry with the pre-transition revision replays the same dismissed state.
    assert career_suggestions.dismiss_suggestion(7, 5, 2)["revision"] == 3
    restored = career_suggestions.restore_suggestion(7, 5, 3)
    assert restored["status"] == "pending"
    assert restored["revision"] == 4

    row["status"] = "accepted"
    row["result_resource_type"] = "skills"
    row["result_resource_ids"] = "[77]"
    with pytest.raises(career.CareerConflictError, match="cannot be changed"):
        career_suggestions.dismiss_suggestion(7, 5, 4)


def test_cross_user_is_hidden_and_missing_relation_is_conflict(monkeypatch):
    row = _pending_skill_row()
    connection = _SuggestionConnection(row)
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)

    with pytest.raises(career.CareerNotFoundError, match="not found"):
        career_suggestions.accept_suggestion(8, 5, 2)

    monkeypatch.setattr(
        career_suggestions.career,
        "create_suggested_resource_with_cursor",
        lambda *args: (_ for _ in ()).throw(career.CareerNotFoundError("gone")),
    )
    with pytest.raises(career.CareerConflictError, match="no longer exists"):
        career_suggestions.accept_suggestion(7, 5, 2)
    assert row["status"] == "pending"


def test_question_batch_failure_rolls_back_suggestion_accept(monkeypatch):
    row = _pending_skill_row()
    row.update(
        {
            "resource_type": "interview_questions",
            "payload": json.dumps(
                {
                    "interview_id": 3,
                    "questions": [
                        {"question": "Q1"},
                        {"question": "Q2"},
                    ],
                }
            ),
        }
    )
    connection = _SuggestionConnection(row)
    monkeypatch.setattr(career_suggestions, "get_connection", lambda: connection)
    monkeypatch.setattr(
        career_suggestions.career,
        "create_suggested_interview_questions_with_cursor",
        lambda *args: (_ for _ in ()).throw(RuntimeError("second insert failed")),
    )

    with pytest.raises(RuntimeError, match="second insert failed"):
        career_suggestions.accept_suggestion(7, 5, 2)

    assert connection.rollbacks == 1
    assert row["status"] == "pending"


def test_session_message_history_batches_suggestion_lookup(monkeypatch):
    calls = []
    monkeypatch.setattr(sessions_router, "require_owned_session", lambda *args: None)
    monkeypatch.setattr(
        sessions_router,
        "get_session_messages",
        lambda *args: [
            (1, "user", "hello", None, None),
            (2, "assistant", "answer", None, None),
            (3, "assistant", "more", None, None),
        ],
    )
    monkeypatch.setattr(
        sessions_router,
        "get_suggestions_for_messages",
        lambda user_id, ids: calls.append((user_id, ids)) or {2: [{"id": 9}]},
    )

    messages = sessions_router.get_messages(3, 50, {"id": 7})

    assert calls == [(7, [2, 3])]
    assert messages[1]["suggestions"] == [{"id": 9}]
    assert messages[2]["suggestions"] == []


class _ColumnCursor:
    def __init__(self, present):
        self.present = present
        self.result = None
        self.executions = []

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "INFORMATION_SCHEMA.COLUMNS" in sql:
            self.result = {"present": 1} if self.present else None

    def fetchone(self):
        return self.result


def test_add_column_migration_can_resume_after_implicit_ddl_commit():
    statement = migrations.CAREER_SUGGESTIONS_V2[0]
    already_applied = _ColumnCursor(present=True)
    migrations._execute_migration_statement(already_applied, statement)
    assert len(already_applied.executions) == 1

    pending = _ColumnCursor(present=False)
    migrations._execute_migration_statement(pending, statement)
    assert len(pending.executions) == 2
    assert "ADD COLUMN reference_answer" in pending.executions[-1][0]


def test_suggestion_migration_uses_polymorphic_result_id_array():
    sql = "\n".join(migrations.CAREER_SUGGESTIONS_V2)
    assert "result_resource_type" in sql
    assert "result_resource_ids JSON" in sql
    assert "result_resource_id BIGINT" not in sql
    assert "result_data JSON" not in sql
