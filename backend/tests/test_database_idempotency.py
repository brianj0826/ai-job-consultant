import pymysql
import pytest
from datetime import datetime, timedelta

from backend.services import database


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


def test_stale_owner_release_does_not_delete_new_owner_messages(monkeypatch):
    cursor = _LeaseCursor()
    connection = _FakeConnection(cursor)
    monkeypatch.setattr(database, "get_connection", lambda: connection)
    assert database.release_chat_request(1, 2, "request-lease", "old-owner") is False
    assert not any("DELETE FROM messages" in sql for sql, _ in cursor.executions)
