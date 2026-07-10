from datetime import timedelta

import pytest

from backend.services import admin


def test_business_day_bounds_are_utc_naive_and_one_day_apart(monkeypatch):
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Asia/Shanghai")
    start, end = admin._business_day_utc_bounds()
    assert start.tzinfo is None
    assert end.tzinfo is None
    assert end - start == timedelta(days=1)


def test_invalid_business_timezone_is_rejected(monkeypatch):
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Not/A_Real_Zone")
    with pytest.raises(admin.AdminActionError):
        admin.validate_admin_configuration()


class _ResetCursor:
    def __init__(self):
        self.rowcount = 0
        self.executions = []
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if "FROM users WHERE id" in sql and "FOR UPDATE" in sql:
            self._result = {
                "id": 9,
                "username": "target",
                "role": "user",
                "status": "active",
                "must_change_password": False,
                "last_login_at": None,
                "created_at": None,
            }
        elif "UPDATE auth_sessions" in sql:
            self.rowcount = 2

    def fetchone(self):
        return self._result


class _ResetConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


def test_super_admin_reset_returns_temporary_password_and_never_audits_it(monkeypatch):
    cursor = _ResetCursor()
    connection = _ResetConnection(cursor)
    monkeypatch.setattr(admin, "get_connection", lambda: connection)
    monkeypatch.setattr(admin.secrets, "token_urlsafe", lambda size: "temporary-password")
    monkeypatch.setattr(admin, "hash_password", lambda password: "PASSWORD_HASH")
    result = admin.reset_user_password(
        {"id": 1, "role": "super_admin"},
        9,
        {"ip_address": "127.0.0.1", "user_agent": "pytest"},
    )
    assert result["temporary_password"] == "temporary-password"
    assert result["user"]["must_change_password"] is True
    assert connection.committed
    audit_params = [params for sql, params in cursor.executions if "admin_audit_logs" in sql][0]
    assert "temporary-password" not in repr(audit_params)


class _MutationCursor:
    def __init__(self, target, active_super_admins=None, revoked_sessions=0):
        self.target = dict(target)
        self.active_super_admins = active_super_admins or []
        self.revoked_sessions = revoked_sessions
        self.rowcount = 0
        self.executions = []
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        self.rowcount = 1
        if "FROM users WHERE id" in sql and "FOR UPDATE" in sql:
            self._result = self.target
        elif "SELECT id FROM users" in sql and "FOR UPDATE" in sql:
            self._result = list(self.active_super_admins)
        elif "UPDATE auth_sessions" in sql:
            self.rowcount = self.revoked_sessions

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result


class _MutationConnection(_ResetConnection):
    def __init__(self, cursor):
        super().__init__(cursor)
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


def _admin_user(**overrides):
    user = {
        "id": 9,
        "username": "target",
        "role": "user",
        "status": "active",
        "must_change_password": False,
        "last_login_at": None,
        "created_at": None,
    }
    user.update(overrides)
    return user


def test_disabling_a_user_revokes_all_active_sessions(monkeypatch):
    cursor = _MutationCursor(_admin_user(), revoked_sessions=3)
    connection = _MutationConnection(cursor)
    monkeypatch.setattr(admin, "get_connection", lambda: connection)

    result = admin.update_user_status(
        {"id": 1, "role": "admin"},
        9,
        "disabled",
    )

    assert result["status"] == "disabled"
    assert connection.committed is True
    assert any("UPDATE auth_sessions" in sql for sql, _ in cursor.executions)


@pytest.mark.parametrize("operation", ["status", "role"])
def test_final_active_super_admin_cannot_be_disabled_or_demoted(monkeypatch, operation):
    target = _admin_user(id=9, role="super_admin")
    cursor = _MutationCursor(target, active_super_admins=[{"id": 9}])
    connection = _MutationConnection(cursor)
    monkeypatch.setattr(admin, "get_connection", lambda: connection)
    actor = {"id": 1, "role": "super_admin"}

    with pytest.raises(admin.AdminActionError, match="final active super-admin"):
        if operation == "status":
            admin.update_user_status(actor, 9, "disabled")
        else:
            admin.update_user_role(actor, 9, "admin")

    assert connection.rolled_back is True
    assert not any("UPDATE users SET" in sql for sql, _ in cursor.executions)
