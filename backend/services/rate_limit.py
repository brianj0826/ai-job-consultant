"""Shared Redis-backed rate limits with an explicit local/test fallback."""
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import os
import secrets
import threading
import time
from typing import Optional

import redis


class RateLimitConfigurationError(RuntimeError):
    pass


class RateLimitBackendError(RuntimeError):
    pass


_LOCAL_ENVIRONMENTS = {"development", "dev", "local", "test"}
_backend_lock = threading.Lock()
_redis_client: Optional[redis.Redis] = None
_backend_mode: Optional[str] = None

_memory_lock = threading.Lock()
_memory_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_memory_request_attempts: dict[str, deque[float]] = defaultdict(deque)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RateLimitConfigurationError(f"{name} must be a boolean value")


def _is_local_environment() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in _LOCAL_ENVIRONMENTS


def _memory_fallback_allowed() -> bool:
    return _is_local_environment() and _bool_env(
        "RATE_LIMIT_ALLOW_MEMORY_FALLBACK",
        True,
    )


def _key_prefix() -> str:
    value = os.getenv("RATE_LIMIT_KEY_PREFIX", "ai-job-consultant").strip()
    if not value or any(character.isspace() for character in value):
        raise RateLimitConfigurationError(
            "RATE_LIMIT_KEY_PREFIX must be non-empty and contain no whitespace"
        )
    return value[:64]


def _redis_from_environment() -> redis.Redis:
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise RateLimitConfigurationError("REDIS_URL is required")
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )


def configure_rate_limit_backend(*, force: bool = False) -> str:
    """Select and verify Redis, or an explicitly allowed local memory backend."""
    global _backend_mode, _redis_client
    with _backend_lock:
        if _backend_mode and not force:
            return _backend_mode
        _backend_mode = None
        _redis_client = None
        url = os.getenv("REDIS_URL", "").strip()
        if not url:
            if _memory_fallback_allowed():
                _backend_mode = "memory"
                return _backend_mode
            raise RateLimitConfigurationError(
                "REDIS_URL is required unless local/test memory fallback is enabled"
            )
        client = _redis_from_environment()
        try:
            client.ping()
        except redis.RedisError as exc:
            if _memory_fallback_allowed():
                _backend_mode = "memory"
                return _backend_mode
            raise RateLimitBackendError("Redis rate-limit backend is unavailable") from exc
        _redis_client = client
        _backend_mode = "redis"
        return _backend_mode


def validate_rate_limit_configuration() -> str:
    return configure_rate_limit_backend(force=True)


def rate_limit_backend_name() -> str:
    return configure_rate_limit_backend()


def check_rate_limit_readiness() -> str:
    """Verify the selected shared backend remains usable for readiness checks."""
    mode = configure_rate_limit_backend()
    if mode == "memory":
        return mode
    assert _redis_client is not None
    try:
        _redis_client.ping()
    except redis.RedisError as exc:
        return _switch_to_memory_or_raise(exc)
    return mode


def _switch_to_memory_or_raise(exc: Exception) -> str:
    global _backend_mode, _redis_client
    if not _memory_fallback_allowed():
        raise RateLimitBackendError("Redis rate-limit backend is unavailable") from exc
    with _backend_lock:
        _backend_mode = "memory"
        _redis_client = None
    return "memory"


def _digest_key(namespace: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{_key_prefix()}:{namespace}:{digest}"


def _prune_memory(attempts: deque[float], now: float, window_seconds: int) -> None:
    while attempts and now - attempts[0] >= window_seconds:
        attempts.popleft()


def _memory_retry_after(key: str, limit: int, window_seconds: int) -> int:
    now = time.monotonic()
    with _memory_lock:
        attempts = _memory_login_attempts.get(key)
        if not attempts:
            return 0
        _prune_memory(attempts, now, window_seconds)
        if not attempts:
            _memory_login_attempts.pop(key, None)
            return 0
        if len(attempts) < limit:
            return 0
        return max(1, int(window_seconds - (now - attempts[0])) + 1)


def _memory_record_login(key: str, window_seconds: int) -> None:
    now = time.monotonic()
    with _memory_lock:
        attempts = _memory_login_attempts[key]
        _prune_memory(attempts, now, window_seconds)
        attempts.append(now)


def _memory_consume_login(key: str, limit: int, window_seconds: int) -> int:
    now = time.monotonic()
    with _memory_lock:
        attempts = _memory_login_attempts[key]
        _prune_memory(attempts, now, window_seconds)
        if len(attempts) >= limit:
            return max(1, int(window_seconds - (now - attempts[0])) + 1)
        attempts.append(now)
        return 0


_LOGIN_CONSUME_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local member = ARGV[5]
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  local earliest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local wait_ms = ttl * 1000
  if earliest[2] then
    wait_ms = math.max(1, math.floor((tonumber(earliest[2]) + ttl - now) * 1000))
  end
  redis.call('EXPIRE', key, ttl)
  return wait_ms
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)
return 0
"""


def consume_login_attempt(key_material: str, limit: int, window_seconds: int) -> int:
    """Atomically reserve one login attempt; return retry-after seconds if denied."""
    key = _digest_key("login", key_material)
    if configure_rate_limit_backend() == "memory":
        return _memory_consume_login(key, limit, window_seconds)
    assert _redis_client is not None
    now = time.time()
    member = f"{now:.6f}:{secrets.token_hex(8)}"
    try:
        wait_ms = _redis_client.eval(
            _LOGIN_CONSUME_SCRIPT,
            1,
            key,
            now,
            now - window_seconds,
            limit,
            window_seconds,
            member,
        )
    except redis.RedisError as exc:
        _switch_to_memory_or_raise(exc)
        return _memory_consume_login(key, limit, window_seconds)
    wait_ms = int(wait_ms)
    return 0 if wait_ms <= 0 else max(1, (wait_ms + 999) // 1000)


def login_retry_after(key_material: str, limit: int, window_seconds: int) -> int:
    key = _digest_key("login", key_material)
    if configure_rate_limit_backend() == "memory":
        return _memory_retry_after(key, limit, window_seconds)
    assert _redis_client is not None
    now = time.time()
    try:
        pipe = _redis_client.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        pipe.expire(key, window_seconds)
        _, count, earliest, _ = pipe.execute()
    except redis.RedisError as exc:
        _switch_to_memory_or_raise(exc)
        return _memory_retry_after(key, limit, window_seconds)
    if int(count) < limit or not earliest:
        return 0
    return max(1, int(window_seconds - (now - float(earliest[0][1]))) + 1)


def record_failed_login(key_material: str, window_seconds: int) -> None:
    key = _digest_key("login", key_material)
    if configure_rate_limit_backend() == "memory":
        _memory_record_login(key, window_seconds)
        return
    assert _redis_client is not None
    now = time.time()
    member = f"{now:.6f}:{secrets.token_hex(8)}"
    try:
        pipe = _redis_client.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {member: now})
        pipe.expire(key, window_seconds)
        pipe.execute()
    except redis.RedisError as exc:
        _switch_to_memory_or_raise(exc)
        _memory_record_login(key, window_seconds)


def clear_failed_logins(key_material: str) -> None:
    key = _digest_key("login", key_material)
    if configure_rate_limit_backend() == "memory":
        with _memory_lock:
            _memory_login_attempts.pop(key, None)
        return
    assert _redis_client is not None
    try:
        _redis_client.delete(key)
    except redis.RedisError as exc:
        _switch_to_memory_or_raise(exc)
        with _memory_lock:
            _memory_login_attempts.pop(key, None)


_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local member = ARGV[5]
redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
local count = redis.call('ZCARD', key)
if count >= limit then
  local earliest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local wait_ms = ttl * 1000
  if earliest[2] then
    wait_ms = math.max(1, math.floor((tonumber(earliest[2]) + ttl - now) * 1000))
  end
  redis.call('EXPIRE', key, ttl)
  return {0, wait_ms}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, ttl)
return {1, 0}
"""


def _memory_check_request(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = time.monotonic()
    with _memory_lock:
        attempts = _memory_request_attempts[key]
        _prune_memory(attempts, now, window_seconds)
        if len(attempts) >= limit:
            wait = int(window_seconds - (now - attempts[0])) + 1
            return False, max(wait, 1)
        attempts.append(now)
        return True, 0


def check_request_limit(
    principal: str,
    limit: int,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    key = _digest_key("request", principal)
    if configure_rate_limit_backend() == "memory":
        return _memory_check_request(key, limit, window_seconds)
    assert _redis_client is not None
    now = time.time()
    member = f"{now:.6f}:{secrets.token_hex(8)}"
    try:
        result = _redis_client.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            key,
            now,
            now - window_seconds,
            limit,
            window_seconds,
            member,
        )
    except redis.RedisError as exc:
        _switch_to_memory_or_raise(exc)
        return _memory_check_request(key, limit, window_seconds)
    allowed = bool(int(result[0]))
    wait_seconds = 0 if allowed else max(1, (int(result[1]) + 999) // 1000)
    return allowed, wait_seconds


def reset_rate_limit_state_for_tests() -> None:
    """Clear process-local state; intended only for isolated unit tests."""
    global _backend_mode, _redis_client
    with _backend_lock, _memory_lock:
        _backend_mode = None
        _redis_client = None
        _memory_login_attempts.clear()
        _memory_request_attempts.clear()
