import hashlib
import os

import pytest
from fastapi import HTTPException
from fastapi import Response
from starlette.requests import Request

from backend.routers import auth as auth_router
from backend.services import auth
from backend.services.database import verify_password


def _request(client_host="127.0.0.1", headers=None):
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": raw_headers,
            "client": (client_host, 12345),
            "server": ("testserver", 80),
        }
    )


def test_blank_bootstrap_values_disable_bootstrap(monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_USERNAME", "")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    assert auth.bootstrap_first_admin_from_environment() is None


def test_unset_bootstrap_values_disable_bootstrap(monkeypatch):
    monkeypatch.delenv("ADMIN_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_PASSWORD", raising=False)
    assert auth.bootstrap_first_admin_from_environment() is None


def test_half_configured_bootstrap_is_rejected(monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_USERNAME", "root-admin")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "")
    with pytest.raises(auth.BootstrapConfigurationError):
        auth.bootstrap_first_admin_from_environment()


class _BootstrapCursor:
    def __init__(self, results):
        self.results = list(results)
        self.lastrowid = 42
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return self.results.pop(0)


class _BootstrapConnection:
    def __init__(self, results):
        self.cursor_instance = _BootstrapCursor(results)
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        return None

    def close(self):
        return None


def test_valid_bootstrap_creates_the_first_super_admin(monkeypatch):
    connection = _BootstrapConnection([None, None])
    monkeypatch.setenv("ADMIN_BOOTSTRAP_USERNAME", "root-admin")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "AdminPass123!")
    monkeypatch.setattr(auth, "get_connection", lambda: connection)

    result = auth.bootstrap_first_admin_from_environment()

    assert result == {"created": True, "id": 42, "username": "root-admin"}
    assert connection.committed is True
    assert any("INSERT INTO users" in statement for statement, _ in connection.cursor_instance.statements)


def test_existing_super_admin_prevents_a_second_bootstrap(monkeypatch):
    connection = _BootstrapConnection([{"id": 3, "username": "existing-root"}])
    monkeypatch.setenv("ADMIN_BOOTSTRAP_USERNAME", "root-admin")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "AdminPass123!")
    monkeypatch.setattr(auth, "get_connection", lambda: connection)

    result = auth.bootstrap_first_admin_from_environment()

    assert result == {"created": False, "username": "existing-root"}
    assert connection.committed is True
    assert not any("INSERT INTO users" in statement for statement, _ in connection.cursor_instance.statements)


def test_production_cookie_defaults_to_secure_when_compose_value_is_blank(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "")
    assert auth.session_cookie_secure() is True


def test_invalid_cookie_combination_fails_validation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "none")
    with pytest.raises(auth.AuthConfigurationError):
        auth.validate_auth_configuration()


def test_forwarded_ip_is_used_only_for_a_trusted_direct_peer(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "172.16.0.0/12")
    trusted = _request("172.18.0.4", {"X-Real-IP": "203.0.113.9"})
    untrusted = _request("198.51.100.4", {"X-Real-IP": "203.0.113.9"})
    assert auth.request_metadata(trusted)["ip_address"] == "203.0.113.9"
    assert auth.request_metadata(untrusted)["ip_address"] == "198.51.100.4"


def test_legacy_short_password_can_be_verified_but_is_not_a_valid_new_password():
    password = "abc"
    salt = b"0123456789abcdef"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    stored = f"{salt.hex()}:{digest.hex()}"
    assert auth.validate_login_password(password) == password
    assert verify_password(password, stored)
    with pytest.raises(ValueError):
        auth.validate_password(password)


def test_login_consumes_attempt_before_verification_and_success_clears_bucket(monkeypatch):
    events = []
    user = {
        "id": 7,
        "username": "alice",
        "role": "user",
        "status": "active",
        "must_change_password": False,
    }

    monkeypatch.setattr(
        auth_router,
        "consume_login_attempt",
        lambda ip_address, username: events.append("consume") or 0,
    )

    def authenticate(username, password):
        assert events == ["consume"]
        events.append("verify")
        return user

    monkeypatch.setattr(auth_router, "authenticate_user", authenticate)
    monkeypatch.setattr(
        auth_router,
        "clear_failed_logins",
        lambda ip_address, username: events.append("clear"),
    )
    monkeypatch.setattr(auth_router, "record_admin_auth_event", lambda *args: None)
    monkeypatch.setattr(auth_router, "_write_login_cookies", lambda *args: None)

    result = auth_router.login(
        auth_router.CredentialsRequest(username="alice", password="secret"),
        _request(),
        Response(),
    )

    assert result == {"user": user}
    assert events == ["consume", "verify", "clear"]


def test_forced_password_change_blocks_business_dependency(monkeypatch):
    user = auth.AuthenticatedUser(
        id=7,
        username="legacy",
        role="user",
        status="active",
        must_change_password=True,
        session_id=11,
        csrf_token_hash="hash",
    )
    monkeypatch.setattr(auth, "_request_auth_context", lambda request: user)
    with pytest.raises(HTTPException) as error:
        auth.require_current_user(_request())
    assert error.value.status_code == 428
    assert auth.require_authenticated_user(_request())["id"] == 7


def test_change_password_rotates_session_and_clears_flag(monkeypatch):
    changed_user = {
        "id": 7,
        "username": "legacy",
        "role": "user",
        "status": "active",
        "must_change_password": False,
    }
    calls = []
    monkeypatch.setattr(
        auth_router,
        "change_user_password",
        lambda user_id, current, new: changed_user,
    )
    monkeypatch.setattr(
        auth_router,
        "_write_login_cookies",
        lambda response, request, user_id: calls.append(user_id),
    )
    result = auth_router.change_password(
        auth_router.ChangePasswordRequest(
            current_password="legacy-pass",
            new_password="new-secure-pass",
        ),
        _request(),
        Response(),
        {"id": 7},
        None,
    )
    assert result == {"user": changed_user}
    assert calls == [7]


def test_change_password_rejects_reusing_the_current_password():
    with pytest.raises(HTTPException) as error:
        auth_router.change_password(
            auth_router.ChangePasswordRequest(
                current_password="same-password",
                new_password="same-password",
            ),
            _request(),
            Response(),
            {"id": 7},
            None,
        )
    assert error.value.status_code == 400
