import pymysql
import pytest
from datetime import datetime, timedelta

from backend.services import database
from backend.services import career_suggestions


class _FakeCursor:
    def __init__(self, existing_content, assistant=None):
        self.existing_content = existing_content
        self.assistant = assistant
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        if "INSERT INTO messages" in sql:
            raise pymysql.err.IntegrityError(1062, "duplicate request")
        if "role = 'user'" in sql:
            self._result = {"content": self.existing_content}
        elif "role = 'assistant'" in sql:
            self._result = self.assistant

    def fetchone(self):
        return self._result


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_same_request_id_with_different_content_is_a_mismatch(monkeypatch):
    connection = _FakeConnection(_FakeCursor("first message"))
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    state, prior = database.reserve_idempotent_user_message(1, 2, "changed", "req-1")
    assert state == "mismatch"
    assert prior is None
    assert connection.rollbacks == 1
    assert connection.closed


def test_completed_request_returns_the_existing_assistant(monkeypatch):
    assistant = {"id": 9, "content": "cached answer"}
    connection = _FakeConnection(_FakeCursor("same", assistant))
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    state, prior = database.reserve_idempotent_user_message(1, 2, "same", "req-2")
    assert state == "completed"
    assert prior == assistant


class _ReadinessCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.rows


def test_readiness_rejects_an_incomplete_schema(monkeypatch):
    connection = _FakeConnection(
        _ReadinessCursor([{"TABLE_NAME": "users", "COLUMN_NAME": "id"}])
    )
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    try:
        database.check_database_readiness()
    except RuntimeError as error:
        assert "Database schema is incomplete" in str(error)
    else:
        raise AssertionError("incomplete schema unexpectedly passed readiness")
    assert connection.closed


class _LeaseCursor:
    def __init__(self, request_row=None, user_content="same"):
        self.request_row = request_row
        self.user_content = user_content
        self._result = None
        self.rowcount = 0
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "INSERT INTO chat_requests" in sql:
            raise pymysql.err.IntegrityError(1062, "duplicate request")
        if "FROM chat_requests" in sql and "FOR UPDATE" in sql:
            self._result = self.request_row
        elif "SELECT id, content FROM messages" in sql:
            self._result = {"id": 10, "content": self.user_content}
        elif "role = 'assistant'" in sql:
            self._result = None
        elif "UPDATE chat_requests" in sql:
            self.rowcount = 1
        elif "DELETE FROM chat_requests" in sql:
            self.rowcount = 0

    def fetchone(self):
        return self._result


def test_expired_chat_lease_is_reclaimed_with_a_new_owner(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0, 0)
    request_row = {
        "id": 4,
        "user_id": 1,
        "session_id": 2,
        "client_request_id": "request-lease",
        "request_hash": database._chat_request_hash("same"),
        "status": "processing",
        "owner_token": "old-owner",
        "lease_expires_at": now - timedelta(seconds=1),
        "response_message_id": None,
    }
    cursor = _LeaseCursor(request_row)
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    monkeypatch.setattr(database, "_utcnow", lambda: now)
    monkeypatch.setattr(database.secrets, "token_hex", lambda size: "new-owner")
    state, owner, response = database.reserve_chat_request(
        1,
        2,
        "same",
        "request-lease",
        lease_seconds=60,
    )
    assert (state, owner, response) == ("reserved", "new-owner", None)


def test_stale_owner_cannot_complete_reclaimed_request(monkeypatch):
    cursor = _LeaseCursor(
        {
            "id": 4,
            "status": "processing",
            "owner_token": "new-owner",
            "response_message_id": None,
        }
    )
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    with pytest.raises(database.ChatRequestOwnershipError):
        database.complete_chat_request(1, 2, "request-lease", "old-owner", "answer")


class _CompleteCursor:
    def __init__(self):
        self._result = None
        self.rowcount = 0
        self.lastrowid = 41
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "FROM chat_requests" in sql and "FOR UPDATE" in sql:
            self._result = {
                "id": 4,
                "status": "processing",
                "owner_token": "current-owner",
                "response_message_id": None,
            }
        elif "INSERT INTO messages" in sql:
            self._result = None
        elif "UPDATE chat_requests" in sql:
            self.rowcount = 1
            self._result = None

    def fetchone(self):
        return self._result


def test_complete_chat_request_saves_suggestions_in_the_completion_transaction(
    monkeypatch,
):
    cursor = _CompleteCursor()
    connection = _FakeConnection(cursor)
    commits = []
    connection.commit = lambda: commits.append("commit")
    inserted = []
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    monkeypatch.setattr(
        career_suggestions,
        "insert_suggestions_with_cursor",
        lambda used_cursor, user_id, session_id, message_id, drafts: inserted.append(
            (used_cursor, user_id, session_id, message_id, drafts)
        ),
    )
    drafts = [{"resource_type": "skills", "payload": {"skill": "Redis"}}]

    message_id = database.complete_chat_request(
        1,
        2,
        "request-lease",
        "current-owner",
        "answer",
        suggestions=drafts,
    )

    assert message_id == 41
    assert inserted == [(cursor, 1, 2, 41, drafts)]
    assert commits == ["commit"]
    insert_index = next(
        index for index, (sql, _) in enumerate(cursor.executions)
        if "INSERT INTO messages" in sql
    )
    completion_index = next(
        index for index, (sql, _) in enumerate(cursor.executions)
        if "UPDATE chat_requests" in sql
    )
    assert insert_index < completion_index


def test_stale_owner_release_does_not_delete_new_owner_messages(monkeypatch):
    cursor = _LeaseCursor()
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    assert database.release_chat_request(1, 2, "request-lease", "old-owner") is False
    assert not any("DELETE FROM messages" in sql for sql, _ in cursor.executions)


class _RenewLeaseCursor:
    def __init__(self, ownership_row, update_rowcount=0):
        self.ownership_row = ownership_row
        self.update_rowcount = update_rowcount
        self._result = None
        self.rowcount = 0
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "UPDATE chat_requests SET lease_expires_at" in sql:
            # MySQL returns zero changed rows when a DATETIME renewal rounds to
            # the value already stored for the current second.
            self.rowcount = self.update_rowcount
            self._result = None
        elif "SELECT id FROM chat_requests" in sql and "owner_token" in sql:
            self._result = self.ownership_row

    def fetchone(self):
        return self._result


def test_renew_chat_lease_accepts_noop_update_for_the_current_owner(monkeypatch):
    cursor = _RenewLeaseCursor({"id": 4})
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)

    database.renew_chat_request_lease(1, 2, "request-lease", "current-owner")

    assert connection.rollbacks == 0
    assert connection.closed
    fallback_sql, fallback_params = next(
        (sql, params)
        for sql, params in cursor.executions
        if "SELECT id FROM chat_requests" in sql
    )
    assert "status = 'processing'" in fallback_sql
    assert "FOR UPDATE" in fallback_sql
    assert fallback_params == (1, 2, "request-lease", "current-owner")


def test_renew_chat_lease_rejects_a_missing_owner_after_noop_update(monkeypatch):
    cursor = _RenewLeaseCursor(None)
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)

    with pytest.raises(database.ChatRequestOwnershipError):
        database.renew_chat_request_lease(1, 2, "request-lease", "stale-owner")

    assert connection.rollbacks == 1
    assert connection.closed


def test_renew_chat_lease_fast_path_does_not_query_ownership(monkeypatch):
    cursor = _RenewLeaseCursor(None, update_rowcount=1)
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)

    database.renew_chat_request_lease(1, 2, "request-lease", "current-owner")

    assert connection.rollbacks == 0
    assert connection.closed
    assert not any("SELECT id FROM chat_requests" in sql for sql, _ in cursor.executions)
