from contextlib import nullcontext
import re
import sys
from types import ModuleType

import pytest
from pydantic import ValidationError

from backend.routers import career as career_router
from backend.services import career, migrations


def test_career_enums_reject_unknown_values():
    try:
        career._choice("unknown", career.APPLICATION_STAGES, "application stage")
    except career.CareerDataError as error:
        assert "application stage" in str(error)
    else:
        raise AssertionError("unknown application stage was accepted")


def test_career_models_enforce_bounded_scores_and_progress():
    try:
        career_router.QuestionCreate(question="Tell me about yourself", score=101)
    except ValidationError:
        pass
    else:
        raise AssertionError("question score above 100 was accepted")

    try:
        career_router.SkillCreate(skill="Python", progress=-1)
    except ValidationError:
        pass
    else:
        raise AssertionError("negative skill progress was accepted")


def test_create_job_uses_authenticated_principal_not_request_user_id(monkeypatch):
    captured = {}

    def fake_create(user_id, values):
        captured["user_id"] = user_id
        captured["values"] = values
        return {"id": 11, **values}

    monkeypatch.setattr(career_router.career_service, "create_job", fake_create)
    payload = career_router.JobCreate(title="Backend Engineer", description="Build APIs")
    result = career_router.create_job(payload, {"id": 7})

    assert captured["user_id"] == 7
    assert "user_id" not in captured["values"]
    assert result["id"] == 11


def test_create_includes_validated_defaults_while_patch_uses_only_explicit_fields(
    monkeypatch,
):
    calls = []

    def fake_create(user_id, values):
        calls.append(("create", user_id, values))
        return {"id": 31, **values}

    def fake_update(user_id, job_id, changes):
        calls.append(("update", user_id, job_id, changes))
        return {"id": job_id, **changes}

    monkeypatch.setattr(career_router.career_service, "create_job", fake_create)
    monkeypatch.setattr(career_router.career_service, "update_job", fake_update)

    career_router.create_job(
        career_router.JobCreate(title="Platform Engineer", description="Build services"),
        {"id": 7},
    )
    career_router.update_job(
        31,
        career_router.JobUpdate(status="active"),
        {"id": 7},
    )

    assert calls[0] == (
        "create",
        7,
        {
            "title": "Platform Engineer",
            "company": "",
            "description": "Build services",
            "source_url": None,
            "status": "saved",
        },
    )
    assert calls[1] == ("update", 7, 31, {"status": "active"})


def test_every_career_write_route_requires_csrf_and_user_data_guard():
    write_routes = [
        route
        for route in career_router.router.routes
        if set(getattr(route, "methods", set())) & {"POST", "PATCH", "DELETE"}
    ]

    assert write_routes, "career router unexpectedly has no write routes"
    missing_csrf = []
    missing_guard = []
    for route in write_routes:
        dependency_calls = {
            getattr(dependency, "dependency", None)
            for dependency in getattr(route, "dependencies", [])
        }
        if career_router.require_business_csrf not in dependency_calls:
            missing_csrf.append((route.path, sorted(route.methods)))
        if career_router.require_career_data_guard not in dependency_calls:
            missing_guard.append((route.path, sorted(route.methods)))

    assert missing_csrf == []
    assert missing_guard == []


class _ReportEntityCursor:
    def __init__(self, row):
        self.row = row
        self.executions = []

    def execute(self, sql, params=None):
        self.executions.append((sql, params))

    def fetchone(self):
        return self.row


@pytest.mark.parametrize(
    ("entity_type", "entity_id"),
    (("job", None), (None, 42)),
)
def test_report_entity_type_and_id_must_be_provided_together(entity_type, entity_id):
    cursor = _ReportEntityCursor({"id": 42})

    with pytest.raises(career.CareerDataError, match="provided together"):
        career._validate_report_entity(cursor, 7, entity_type, entity_id)

    assert cursor.executions == []


def test_report_entity_reference_is_scoped_to_current_user():
    owned_cursor = _ReportEntityCursor({"id": 42})

    assert career._validate_report_entity(owned_cursor, 7, "JOB", 42) == ("job", 42)
    sql, params = owned_cursor.executions[-1]
    assert "FROM `career_jobs`" in sql
    assert params == (42, 7)

    other_users_cursor = _ReportEntityCursor(None)
    with pytest.raises(career.CareerNotFoundError, match="not found"):
        career._validate_report_entity(other_users_cursor, 7, "job", 42)
    assert other_users_cursor.executions[-1][1] == (42, 7)


def test_report_payload_larger_than_utf8_limit_is_rejected():
    oversized = {"content": "\u804c" * (career.REPORT_PAYLOAD_MAX_BYTES + 1)}

    with pytest.raises(career.CareerDataError, match="payload exceeds"):
        career._encode_report_payload(oversized)


class _GuardCursor:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.result = None
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "GET_LOCK" in sql:
            self.result = {"acquired": int(self.acquired)}
        elif "RELEASE_LOCK" in sql:
            self.result = {"released": 1}

    def fetchone(self):
        return self.result


class _GuardConnection:
    def __init__(self, acquired=True):
        self.cursor_instance = _GuardCursor(acquired)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_career_data_guard_uses_a_user_scoped_advisory_lock(monkeypatch):
    connection = _GuardConnection()
    monkeypatch.setattr(career, "get_connection", lambda: connection)

    with career.career_data_guard(7):
        assert connection.closed is False

    assert connection.closed is True
    assert connection.cursor_instance.executions == [
        ("SELECT GET_LOCK(%s, %s) AS acquired", ("career-data-user-7", 30)),
        ("SELECT RELEASE_LOCK(%s)", ("career-data-user-7",)),
    ]


def test_career_data_guard_reports_busy_user(monkeypatch):
    connection = _GuardConnection(acquired=False)
    monkeypatch.setattr(career, "get_connection", lambda: connection)

    with pytest.raises(career.CareerConflictError, match="busy"):
        with career.career_data_guard(7, timeout_seconds=0):
            pass

    assert connection.closed is True


def _install_fake_rag(monkeypatch, delete_user_collection):
    fake_rag = ModuleType("backend.services.rag")
    fake_rag.delete_user_collection = delete_user_collection
    monkeypatch.setitem(sys.modules, "backend.services.rag", fake_rag)


def _disable_real_career_data_guard(monkeypatch):
    if hasattr(career_router.career_service, "career_data_guard"):
        monkeypatch.setattr(
            career_router.career_service,
            "career_data_guard",
            lambda user_id: nullcontext(),
        )
    if hasattr(career_router, "career_data_guard"):
        monkeypatch.setattr(career_router, "career_data_guard", lambda user_id: nullcontext())


def test_delete_data_stops_before_sql_when_chroma_delete_fails(monkeypatch):
    sql_calls = []

    def fail_chroma(_user_id):
        raise RuntimeError("chroma unavailable")

    def fake_delete_sql(user_id):
        sql_calls.append(user_id)
        return {}

    _install_fake_rag(monkeypatch, fail_chroma)
    _disable_real_career_data_guard(monkeypatch)
    monkeypatch.setattr(career_router.career_service, "delete_career_data", fake_delete_sql)

    with pytest.raises(RuntimeError, match="chroma unavailable"):
        career_router.delete_data(
            career_router.DeleteCareerDataRequest(confirmation="DELETE"),
            {"id": 7},
        )

    assert sql_calls == []


def test_delete_data_can_be_retried_after_sql_failure(monkeypatch):
    vector_calls = []
    sql_calls = []

    def fake_delete_vector(user_id):
        vector_calls.append(user_id)
        # Deleting an already absent Chroma collection is an expected retry.
        return len(vector_calls) == 1

    def flaky_delete_sql(user_id):
        sql_calls.append(user_id)
        if len(sql_calls) == 1:
            raise RuntimeError("mysql unavailable")
        return {"jobs": 2}

    _install_fake_rag(monkeypatch, fake_delete_vector)
    _disable_real_career_data_guard(monkeypatch)
    monkeypatch.setattr(career_router.career_service, "delete_career_data", flaky_delete_sql)
    request = career_router.DeleteCareerDataRequest(confirmation="DELETE")

    with pytest.raises(RuntimeError, match="mysql unavailable"):
        career_router.delete_data(request, {"id": 7})

    result = career_router.delete_data(request, {"id": 7})

    assert vector_calls == [7, 7]
    assert sql_calls == [7, 7]
    assert result == {
        "ok": True,
        "deleted": {"jobs": 2},
        "vector_collection_deleted": False,
    }


class _MigrationCursor:
    def __init__(self, ledger=None):
        self.ledger = ledger if ledger is not None else []
        self._result = None
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "GET_LOCK" in sql:
            self._result = {"acquired": 1}
        elif "SELECT" in sql and "FROM schema_migrations" in sql:
            self._result = [dict(row) for row in self.ledger]
        elif "INSERT INTO schema_migrations" in sql:
            columns_match = re.search(
                r"INSERT\s+INTO\s+schema_migrations\s*\(([^)]+)\)",
                sql,
                flags=re.IGNORECASE,
            )
            assert columns_match is not None
            columns = [column.strip().strip("`") for column in columns_match.group(1).split(",")]
            self.ledger.append(dict(zip(columns, params or ())))
            self._result = None
        elif "RELEASE_LOCK" in sql:
            self._result = {"released": 1}
        else:
            self._result = None

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result or []


class _MigrationConnection:
    def __init__(self, ledger=None):
        self.cursor_instance = _MigrationCursor(ledger)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_versioned_migration_records_structured_workspace(monkeypatch):
    connection = _MigrationConnection()
    monkeypatch.setattr(migrations, "get_connection", lambda: connection)

    applied = migrations.run_migrations()

    assert applied == [1]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed
    sql = "\n".join(statement for statement, _ in connection.cursor_instance.executions)
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in sql
    assert "CREATE TABLE IF NOT EXISTS career_resumes" in sql
    assert "CREATE TABLE IF NOT EXISTS career_interviews" in sql
    assert "INSERT INTO schema_migrations" in sql


def test_migration_is_idempotent_when_recorded_checksum_matches(monkeypatch):
    ledger = []
    connections = []

    def connection_factory():
        connection = _MigrationConnection(ledger)
        connections.append(connection)
        return connection

    monkeypatch.setattr(migrations, "get_connection", connection_factory)

    assert migrations.run_migrations() == [1]
    assert migrations.run_migrations() == []

    assert len(ledger) == 1
    second_sql = "\n".join(
        statement for statement, _ in connections[1].cursor_instance.executions
    )
    assert "CREATE TABLE IF NOT EXISTS career_resumes" not in second_sql
    assert "INSERT INTO schema_migrations" not in second_sql
    assert connections[1].closed


def test_migration_rejects_checksum_mismatch(monkeypatch):
    ledger = []
    connections = []

    def connection_factory():
        connection = _MigrationConnection(ledger)
        connections.append(connection)
        return connection

    monkeypatch.setattr(migrations, "get_connection", connection_factory)
    assert migrations.run_migrations() == [1]
    assert "checksum" in ledger[0], "migration ledger must record a checksum"
    ledger[0]["checksum"] = "0" * 64

    with pytest.raises(migrations.MigrationError, match="checksum"):
        migrations.run_migrations()

    assert connections[-1].rollbacks == 1
    assert connections[-1].closed


def _career_schema_statement(table: str) -> str:
    statement = next(
        sql
        for sql in migrations.CAREER_SCHEMA_V1
        if f"CREATE TABLE IF NOT EXISTS {table}" in sql
    )
    return re.sub(r"\s+", " ", statement).strip().lower()


def test_schema_enforces_one_primary_resume_and_same_user_job_relations():
    resumes = _career_schema_statement("career_resumes")
    jobs = _career_schema_statement("career_jobs")
    applications = _career_schema_statement("career_applications")
    interviews = _career_schema_statement("career_interviews")

    assert "primary_user_id" in resumes
    assert "generated always as" in resumes
    assert re.search(r"unique key [^(]+ \(primary_user_id\)", resumes)

    assert re.search(r"unique key [^(]+ \(user_id, id\)", jobs)
    composite_job_reference = re.compile(
        r"foreign key \(user_id, job_id\) references career_jobs\s*\(user_id, id\)"
    )
    assert composite_job_reference.search(applications)
    assert composite_job_reference.search(interviews)
