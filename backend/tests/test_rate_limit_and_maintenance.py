import threading

import pytest
import redis

from backend.services import rate_limit
from backend.services.maintenance import PeriodicSessionCleanup


@pytest.fixture(autouse=True)
def _reset_rate_limit(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("RATE_LIMIT_ALLOW_MEMORY_FALLBACK", "true")
    rate_limit.reset_rate_limit_state_for_tests()
    yield
    rate_limit.reset_rate_limit_state_for_tests()


def test_local_memory_request_limit_is_explicit_and_enforced():
    assert rate_limit.validate_rate_limit_configuration() == "memory"
    assert rate_limit.check_request_limit("user-1", 2, 60) == (True, 0)
    assert rate_limit.check_request_limit("user-1", 2, 60) == (True, 0)
    allowed, wait = rate_limit.check_request_limit("user-1", 2, 60)
    assert allowed is False
    assert wait > 0


def test_shared_login_failure_contract_works_with_memory_fallback():
    material = "127.0.0.1\0alice"
    rate_limit.record_failed_login(material, 60)
    assert rate_limit.login_retry_after(material, 2, 60) == 0
    rate_limit.record_failed_login(material, 60)
    assert rate_limit.login_retry_after(material, 2, 60) > 0
    rate_limit.clear_failed_logins(material)
    assert rate_limit.login_retry_after(material, 2, 60) == 0


def test_login_attempt_is_atomically_consumed_before_verification():
    material = "127.0.0.1\0parallel-user"
    assert rate_limit.consume_login_attempt(material, 2, 60) == 0
    assert rate_limit.consume_login_attempt(material, 2, 60) == 0
    assert rate_limit.consume_login_attempt(material, 2, 60) > 0
    rate_limit.clear_failed_logins(material)
    assert rate_limit.consume_login_attempt(material, 2, 60) == 0


def test_production_without_redis_fails_fast(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("RATE_LIMIT_ALLOW_MEMORY_FALLBACK", "true")
    with pytest.raises(rate_limit.RateLimitConfigurationError):
        rate_limit.validate_rate_limit_configuration()


def test_production_with_unavailable_redis_fails_fast(monkeypatch):
    class BrokenRedis:
        def ping(self):
            raise redis.ConnectionError("unavailable")

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REDIS_URL", "redis://unavailable:6379/0")
    monkeypatch.setattr(rate_limit, "_redis_from_environment", lambda: BrokenRedis())
    with pytest.raises(rate_limit.RateLimitBackendError):
        rate_limit.validate_rate_limit_configuration()


def test_request_limit_uses_the_verified_redis_backend(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.eval_calls = []

        def ping(self):
            return True

        def eval(self, *args):
            self.eval_calls.append(args)
            return [1, 0]

    fake = FakeRedis()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setattr(rate_limit, "_redis_from_environment", lambda: fake)
    assert rate_limit.validate_rate_limit_configuration() == "redis"
    assert rate_limit.check_request_limit("user-9", 30, 60) == (True, 0)
    assert len(fake.eval_calls) == 1


def test_periodic_session_cleanup_runs_and_stops():
    called = threading.Event()
    invocations = []

    def cleanup(retention_days):
        invocations.append(retention_days)
        called.set()
        return 0

    worker = PeriodicSessionCleanup(0.01, 30, cleanup=cleanup)
    worker.start()
    assert called.wait(1.0)
    worker.stop()
    assert invocations
    assert invocations[0] == 30
    assert worker.running is False
