"""Database access helpers and backwards-compatible base-schema bootstrap.

Legacy tables are still upgraded idempotently here. New structured-domain
changes use the versioned runner in :mod:`backend.services.migrations`.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pymysql


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ai_assistant"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "init_command": "SET time_zone = '+00:00'",
}


class DatabaseConfigurationError(RuntimeError):
    """Raised when a production database configuration is incomplete or unsafe."""


def validate_database_configuration() -> None:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env in {"development", "dev", "local", "test"}:
        return
    required = {
        "DB_HOST": os.getenv("DB_HOST", "").strip(),
        "DB_USER": os.getenv("DB_USER", "").strip(),
        "DB_PASSWORD": os.getenv("DB_PASSWORD", ""),
        "DB_NAME": os.getenv("DB_NAME", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise DatabaseConfigurationError(
            f"Production database configuration is missing: {', '.join(missing)}"
        )
    if required["DB_USER"].casefold() == "root":
        raise DatabaseConfigurationError(
            "Production DB_USER must be a dedicated non-root application account"
        )

# New hashes carry their work factor.  The verifier below also understands the
# legacy ``salt:digest`` format that was already present in deployed databases.
def _configured_password_iterations() -> int:
    try:
        requested = int(os.getenv("PASSWORD_PBKDF2_ITERATIONS", "310000"))
    except ValueError:
        requested = 310000
    return max(100000, min(requested, 2_000_000))


PASSWORD_ITERATIONS = _configured_password_iterations()
LEGACY_PASSWORD_ITERATIONS = 100000
PASSWORD_ALGORITHM = "pbkdf2_sha256"
MIN_SECURE_PASSWORD_LENGTH = 8


class ChatRequestOwnershipError(RuntimeError):
    """Raised when a stale worker attempts to mutate a reclaimed chat request."""


def chat_request_lease_seconds() -> int:
    try:
        value = int(os.getenv("CHAT_REQUEST_LEASE_SECONDS", "300"))
    except ValueError:
        value = 300
    return max(30, min(value, 3600))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
VALID_ROLES = {ROLE_USER, ROLE_ADMIN, ROLE_SUPER_ADMIN}

STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
VALID_STATUSES = {STATUS_ACTIVE, STATUS_DISABLED}


def get_connection():
    """Return a non-autocommit MySQL connection with dictionary rows."""
    return pymysql.connect(**DB_CONFIG)


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """SELECT 1
           FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE()
             AND TABLE_NAME = %s
             AND COLUMN_NAME = %s
           LIMIT 1""",
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def _index_exists(cursor, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """SELECT 1
           FROM INFORMATION_SCHEMA.STATISTICS
           WHERE TABLE_SCHEMA = DATABASE()
             AND TABLE_NAME = %s
             AND INDEX_NAME = %s
           LIMIT 1""",
        (table_name, index_name),
    )
    return cursor.fetchone() is not None


def _ensure_column(cursor, table_name: str, column_name: str, definition: str) -> None:
    if not _column_exists(cursor, table_name, column_name):
        # Table and column names are fixed constants in this module.  Only the
        # data definition is interpolated, never user-controlled input.
        cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}")


def _ensure_index(cursor, table_name: str, index_name: str, columns: str) -> None:
    if not _index_exists(cursor, table_name, index_name):
        cursor.execute(f"CREATE INDEX `{index_name}` ON `{table_name}` {columns}")


def _ensure_unique_index(cursor, table_name: str, index_name: str, columns: str) -> None:
    if not _index_exists(cursor, table_name, index_name):
        cursor.execute(f"CREATE UNIQUE INDEX `{index_name}` ON `{table_name}` {columns}")


def init_database() -> None:
    """Create the application schema and safely upgrade the existing schema."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL DEFAULT '',
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
                    last_login_at DATETIME NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            # Existing installations predate password hashes and roles.
            _ensure_column(cursor, "users", "password_hash", "VARCHAR(255) NOT NULL DEFAULT ''")
            _ensure_column(cursor, "users", "role", "VARCHAR(20) NOT NULL DEFAULT 'user'")
            _ensure_column(cursor, "users", "status", "VARCHAR(20) NOT NULL DEFAULT 'active'")
            _ensure_column(
                cursor,
                "users",
                "must_change_password",
                "BOOLEAN NOT NULL DEFAULT FALSE",
            )
            _ensure_column(cursor, "users", "last_login_at", "DATETIME NULL DEFAULT NULL")
            cursor.execute(
                "UPDATE users SET role = %s WHERE role IS NULL OR role NOT IN (%s, %s, %s)",
                (ROLE_USER, ROLE_USER, ROLE_ADMIN, ROLE_SUPER_ADMIN),
            )
            cursor.execute(
                "UPDATE users SET status = %s WHERE status IS NULL OR status NOT IN (%s, %s)",
                (STATUS_ACTIVE, STATUS_ACTIVE, STATUS_DISABLED),
            )
            # Passwordless legacy accounts cannot authenticate safely. Mark
            # them explicitly so an administrator can issue a temporary secret.
            cursor.execute(
                "UPDATE users SET must_change_password = TRUE WHERE password_hash = ''"
            )
            _ensure_index(cursor, "users", "idx_users_role_status", "(`role`, `status`)")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    session_id INT,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    feedback VARCHAR(50) DEFAULT NULL,
                    client_request_id VARCHAR(128) NULL DEFAULT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            _ensure_column(
                cursor,
                "messages",
                "client_request_id",
                "VARCHAR(128) NULL DEFAULT NULL",
            )
            _ensure_index(cursor, "messages", "idx_messages_feedback_timestamp", "(`feedback`, `timestamp`)")
            _ensure_index(cursor, "messages", "idx_messages_user_timestamp", "(`user_id`, `timestamp`)")
            _ensure_unique_index(
                cursor,
                "messages",
                "uq_messages_chat_request_role",
                "(`user_id`, `session_id`, `role`, `client_request_id`)",
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_requests (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    session_id INT NOT NULL,
                    client_request_id VARCHAR(128) NOT NULL,
                    request_hash CHAR(64) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'processing',
                    owner_token CHAR(64) NOT NULL,
                    lease_expires_at DATETIME NOT NULL,
                    response_message_id INT NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_chat_requests_client (user_id, session_id, client_request_id),
                    KEY idx_chat_requests_lease (status, lease_expires_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (response_message_id) REFERENCES messages(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            # Browser authentication sessions never contain raw tokens.  A DB
            # leak therefore cannot be replayed as an authenticated browser.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    token_hash CHAR(64) NOT NULL,
                    csrf_token_hash CHAR(64) NOT NULL,
                    expires_at DATETIME NOT NULL,
                    revoked_at DATETIME NULL DEFAULT NULL,
                    last_seen_at DATETIME NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45) NULL DEFAULT NULL,
                    user_agent VARCHAR(512) NULL DEFAULT NULL,
                    UNIQUE KEY uq_auth_sessions_token_hash (token_hash),
                    KEY idx_auth_sessions_user_active (user_id, revoked_at, expires_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_audit_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    admin_user_id INT NULL DEFAULT NULL,
                    action VARCHAR(100) NOT NULL,
                    target_type VARCHAR(100) NOT NULL,
                    target_id VARCHAR(100) NULL DEFAULT NULL,
                    details TEXT NULL,
                    ip_address VARCHAR(45) NULL DEFAULT NULL,
                    user_agent VARCHAR(512) NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_admin_audit_logs_created_at (created_at),
                    KEY idx_admin_audit_logs_admin_created_at (admin_user_id, created_at),
                    FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_database_readiness() -> dict[str, str]:
    """Verify connectivity and the minimum schema required by authenticated APIs."""
    required_columns = {
        "users": {"id", "username", "password_hash", "role", "status", "must_change_password"},
        "sessions": {"id", "user_id"},
        "messages": {"id", "user_id", "session_id", "client_request_id"},
        "chat_requests": {
            "id",
            "user_id",
            "session_id",
            "client_request_id",
            "request_hash",
            "status",
            "owner_token",
            "lease_expires_at",
            "response_message_id",
        },
        "auth_sessions": {"id", "user_id", "token_hash", "csrf_token_hash", "expires_at"},
        "admin_audit_logs": {"id", "admin_user_id", "action"},
        "schema_migrations": {"version", "name", "checksum", "applied_at"},
        "career_resumes": {
            "id", "user_id", "title", "target_role", "content", "source_name",
            "is_primary", "primary_marker", "created_at", "updated_at",
        },
        "career_jobs": {
            "id", "user_id", "title", "company", "description", "source_url",
            "status", "created_at", "updated_at",
        },
        "career_applications": {
            "id", "user_id", "job_id", "stage", "next_action", "deadline",
            "notes", "created_at", "updated_at",
        },
        "career_interviews": {
            "id", "user_id", "job_id", "title", "status", "total_questions",
            "current_question", "overall_score", "completed_at", "created_at", "updated_at",
        },
        "career_interview_questions": {
            "id", "interview_id", "position", "question", "answer", "score",
            "feedback", "created_at", "updated_at",
        },
        "career_reports": {
            "id", "user_id", "kind", "title", "entity_type", "entity_id",
            "summary", "payload", "created_at",
        },
        "career_skills": {
            "id", "user_id", "skill", "target_level", "status", "progress",
            "due_date", "notes", "created_at", "updated_at",
        },
    }
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            placeholders = ", ".join(["%s"] * len(required_columns))
            cursor.execute(
                f"""SELECT TABLE_NAME, COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME IN ({placeholders})""",
                tuple(required_columns),
            )
            discovered = {table: set() for table in required_columns}
            for row in cursor.fetchall():
                discovered[row["TABLE_NAME"]].add(row["COLUMN_NAME"])
        missing = {
            table: sorted(columns - discovered[table])
            for table, columns in required_columns.items()
            if columns - discovered[table]
        }
        if missing:
            raise RuntimeError(f"Database schema is incomplete: {missing}")
        return {"database": "ok", "schema": "ok"}
    finally:
        conn.close()


def cleanup_expired_auth_sessions(retention_days: int = 30) -> int:
    """Delete expired sessions and old revoked-session audit residue."""
    retention_days = max(1, min(int(retention_days), 3650))
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """DELETE FROM auth_sessions
                   WHERE expires_at <= UTC_TIMESTAMP()
                      OR (revoked_at IS NOT NULL
                          AND revoked_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s DAY))""",
                (retention_days,),
            )
            removed = cursor.rowcount
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- User operations -----------------------------------------------------


def _normalize_user_row(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    normalized = dict(row)
    if "must_change_password" in normalized:
        normalized["must_change_password"] = bool(normalized["must_change_password"])
    return normalized

def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a per-user random salt."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _password_parts(stored: str) -> Optional[tuple[int, bytes, bytes]]:
    """Parse current and pre-auth-migration PBKDF2 encodings."""
    try:
        if stored.startswith(f"{PASSWORD_ALGORITHM}$"):
            algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
            if algorithm != PASSWORD_ALGORITHM:
                return None
            rounds = int(iterations)
        else:
            # Compatibility with the original format: ``salt_hex:digest_hex``.
            salt_hex, digest_hex = stored.split(":", 1)
            rounds = LEGACY_PASSWORD_ITERATIONS
        if not 10_000 <= rounds <= 2_000_000:
            return None
        return rounds, bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
    except (AttributeError, TypeError, ValueError):
        return None


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification for current and legacy password hashes."""
    parts = _password_parts(stored)
    if parts is None or not isinstance(password, str):
        return False
    rounds, salt, expected = parts
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(actual, expected)


def password_needs_rehash(stored: str) -> bool:
    """Return whether a legacy or weaker hash should be upgraded after login."""
    parts = _password_parts(stored)
    if parts is None:
        return True
    rounds, _, _ = parts
    return not stored.startswith(f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}$") or rounds != PASSWORD_ITERATIONS


# Keep the old internal names available for callers that may still import them.
_hash_password = hash_password
_verify_password = verify_password


def register_user(username: str, password: str, role: str = ROLE_USER) -> Optional[int]:
    """Create a user and return its ID, or ``None`` if the name already exists."""
    if role not in VALID_ROLES:
        raise ValueError("invalid role")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return None
            cursor.execute(
                """INSERT INTO users (username, password_hash, role, status)
                   VALUES (%s, %s, %s, %s)""",
                (username, hash_password(password), role, STATUS_ACTIVE),
            )
            user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except pymysql.err.IntegrityError:
        conn.rollback()
        return None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_auth_record(username: str) -> Optional[dict[str, Any]]:
    """Fetch the minimum user record needed to authenticate a login."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, password_hash, role, status, must_change_password,
                          last_login_at, created_at
                   FROM users WHERE username = %s""",
                (username,),
            )
            return _normalize_user_row(cursor.fetchone())
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    """Fetch a public user record (never returns a password hash)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, role, status, must_change_password,
                          last_login_at, created_at
                   FROM users WHERE id = %s""",
                (user_id,),
            )
            return _normalize_user_row(cursor.fetchone())
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[dict[str, Any]]:
    """Verify credentials, reject disabled accounts, and record successful login."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, password_hash, role, status, must_change_password,
                          last_login_at, created_at
                   FROM users WHERE username = %s""",
                (username,),
            )
            row = cursor.fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return None
            if row["status"] != STATUS_ACTIVE:
                return None

            updates = ["last_login_at = UTC_TIMESTAMP()"]
            params: list[Any] = []
            if len(password) < MIN_SECURE_PASSWORD_LENGTH and not row["must_change_password"]:
                updates.append("must_change_password = TRUE")
            if password_needs_rehash(row["password_hash"]):
                updates.append("password_hash = %s")
                params.append(hash_password(password))
            params.append(row["id"])
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s", tuple(params)
            )
            cursor.execute(
                """SELECT id, username, role, status, must_change_password,
                          last_login_at, created_at
                   FROM users WHERE id = %s""",
                (row["id"],),
            )
            authenticated = cursor.fetchone()
        conn.commit()
        return _normalize_user_row(authenticated)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def login_user(username: str, password: str) -> Optional[int]:
    """Compatibility wrapper for callers that only need the authenticated ID."""
    user = authenticate_user(username, password)
    return user["id"] if user else None


def change_user_password(
    user_id: int,
    current_password: str,
    new_password: str,
) -> Optional[dict[str, Any]]:
    """Change a password, clear the forced-change flag, and revoke old sessions."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, password_hash, status
                   FROM users WHERE id = %s FOR UPDATE""",
                (user_id,),
            )
            row = cursor.fetchone()
            if (
                not row
                or row["status"] != STATUS_ACTIVE
                or not verify_password(current_password, row["password_hash"])
            ):
                conn.rollback()
                return None
            cursor.execute(
                """UPDATE users
                   SET password_hash = %s, must_change_password = FALSE
                   WHERE id = %s""",
                (hash_password(new_password), user_id),
            )
            cursor.execute(
                """UPDATE auth_sessions
                   SET revoked_at = COALESCE(revoked_at, UTC_TIMESTAMP())
                   WHERE user_id = %s AND revoked_at IS NULL""",
                (user_id,),
            )
            cursor.execute(
                """SELECT id, username, role, status, must_change_password,
                          last_login_at, created_at
                   FROM users WHERE id = %s""",
                (user_id,),
            )
            user = cursor.fetchone()
        conn.commit()
        return _normalize_user_row(user)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_or_create_user(username: str):
    """Retired insecure compatibility hook.

    Passwordless identity provisioning was the former login fallback.  It is
    deliberately disabled so an old client cannot create or impersonate users
    by only knowing a username.
    """
    raise RuntimeError("Passwordless user provisioning is disabled; use /api/auth/login")


# --- Conversation operations (kept compatible with existing routes) -----

def create_session(user_id, name="New conversation"):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sessions (user_id, name) VALUES (%s, %s)",
                (user_id, name),
            )
            session_id = cursor.lastrowid
        conn.commit()
        return session_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_sessions(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, name, created_at FROM sessions
                   WHERE user_id = %s ORDER BY created_at DESC""",
                (user_id,),
            )
            sessions = cursor.fetchall()
        return [(row["id"], row["name"], row["created_at"]) for row in sessions]
    finally:
        conn.close()


def delete_session(session_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rename_session(session_id, new_name):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE sessions SET name = %s WHERE id = %s", (new_name, session_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_message(user_id, session_id, role, content, client_request_id: Optional[str] = None):
    """Persist a message; request IDs make user/assistant retries idempotent."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO messages
                   (user_id, session_id, role, content, client_request_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, session_id, role, content, client_request_id),
            )
            message_id = cursor.lastrowid
        conn.commit()
        return message_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_idempotent_chat_messages(
    user_id: int,
    session_id: int,
    client_request_id: str,
) -> dict[str, Optional[dict[str, Any]]]:
    """Return the prior user/assistant rows associated with a client request."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, role, content, timestamp
                   FROM messages
                   WHERE user_id = %s AND session_id = %s AND client_request_id = %s
                     AND role IN ('user', 'assistant')
                   ORDER BY id""",
                (user_id, session_id, client_request_id),
            )
            result: dict[str, Optional[dict[str, Any]]] = {
                "user": None,
                "assistant": None,
            }
            for row in cursor.fetchall():
                result[row["role"]] = row
            return result
    finally:
        conn.close()


def _chat_request_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _chat_response_row(cursor, row: dict[str, Any]) -> Optional[dict[str, Any]]:
    if row.get("response_message_id"):
        cursor.execute(
            """SELECT id, content, timestamp FROM messages
               WHERE id = %s AND user_id = %s AND session_id = %s
                 AND role = 'assistant' AND client_request_id = %s
               LIMIT 1""",
            (
                row["response_message_id"],
                row["user_id"],
                row["session_id"],
                row["client_request_id"],
            ),
        )
        response = cursor.fetchone()
        if response:
            return response
    cursor.execute(
        """SELECT id, content, timestamp
           FROM messages
           WHERE user_id = %s AND session_id = %s
             AND role = 'assistant' AND client_request_id = %s
           LIMIT 1""",
        (row["user_id"], row["session_id"], row["client_request_id"]),
    )
    return cursor.fetchone()


def _ensure_chat_user_message(
    cursor,
    user_id: int,
    session_id: int,
    content: str,
    client_request_id: str,
) -> tuple[bool, Optional[dict[str, Any]]]:
    """Ensure the durable user message exists; return mismatch/legacy assistant."""
    cursor.execute(
        """SELECT id, content FROM messages
           WHERE user_id = %s AND session_id = %s
             AND role = 'user' AND client_request_id = %s
           LIMIT 1""",
        (user_id, session_id, client_request_id),
    )
    existing_user = cursor.fetchone()
    if existing_user and existing_user["content"] != content:
        return False, None
    if not existing_user:
        cursor.execute(
            """INSERT INTO messages
               (user_id, session_id, role, content, client_request_id)
               VALUES (%s, %s, 'user', %s, %s)""",
            (user_id, session_id, content, client_request_id),
        )
    cursor.execute(
        """SELECT id, content, timestamp FROM messages
           WHERE user_id = %s AND session_id = %s
             AND role = 'assistant' AND client_request_id = %s
           LIMIT 1""",
        (user_id, session_id, client_request_id),
    )
    return True, cursor.fetchone()


def reserve_chat_request(
    user_id: int,
    session_id: int,
    content: str,
    client_request_id: str,
    *,
    lease_seconds: Optional[int] = None,
) -> tuple[str, Optional[str], Optional[dict[str, Any]]]:
    """Reserve, replay, or safely reclaim a durable idempotent chat request.

    Returns ``(state, owner_token, assistant_row)`` where state is one of
    ``reserved``, ``completed``, ``processing``, or ``mismatch``.
    """
    lease_seconds = lease_seconds or chat_request_lease_seconds()
    lease_seconds = max(1, min(int(lease_seconds), 3600))
    owner_token = secrets.token_hex(32)
    request_hash = _chat_request_hash(content)
    lease_expires_at = _utcnow() + timedelta(seconds=lease_seconds)
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    """INSERT INTO chat_requests
                       (user_id, session_id, client_request_id, request_hash,
                        status, owner_token, lease_expires_at)
                       VALUES (%s, %s, %s, %s, 'processing', %s, %s)""",
                    (
                        user_id,
                        session_id,
                        client_request_id,
                        request_hash,
                        owner_token,
                        lease_expires_at,
                    ),
                )
                matches, legacy_assistant = _ensure_chat_user_message(
                    cursor,
                    user_id,
                    session_id,
                    content,
                    client_request_id,
                )
                if not matches:
                    conn.rollback()
                    return "mismatch", None, None
                if legacy_assistant:
                    cursor.execute(
                        """UPDATE chat_requests
                           SET status = 'completed', response_message_id = %s
                           WHERE user_id = %s AND session_id = %s
                             AND client_request_id = %s AND owner_token = %s""",
                        (
                            legacy_assistant["id"],
                            user_id,
                            session_id,
                            client_request_id,
                            owner_token,
                        ),
                    )
                    conn.commit()
                    return "completed", None, legacy_assistant
                conn.commit()
                return "reserved", owner_token, None
            except pymysql.err.IntegrityError as duplicate_error:
                conn.rollback()
                cursor.execute(
                    """SELECT id, user_id, session_id, client_request_id,
                              request_hash, status, owner_token, lease_expires_at,
                              response_message_id
                       FROM chat_requests
                       WHERE user_id = %s AND session_id = %s
                         AND client_request_id = %s
                       FOR UPDATE""",
                    (user_id, session_id, client_request_id),
                )
                request_row = cursor.fetchone()
                if not request_row:
                    raise duplicate_error
                if request_row["request_hash"] != request_hash:
                    conn.commit()
                    return "mismatch", None, None
                if request_row["status"] == "completed":
                    response = _chat_response_row(cursor, request_row)
                    if response:
                        conn.commit()
                        return "completed", None, response
                    # Keep the FOR UPDATE lock while repairing a completed row
                    # whose referenced response has disappeared.
                if (
                    request_row["status"] == "processing"
                    and request_row["lease_expires_at"] > _utcnow()
                ):
                    conn.commit()
                    return "processing", None, None

                cursor.execute(
                    """UPDATE chat_requests
                       SET status = 'processing', owner_token = %s,
                           lease_expires_at = %s, response_message_id = NULL
                       WHERE id = %s""",
                    (owner_token, lease_expires_at, request_row["id"]),
                )
                matches, existing_assistant = _ensure_chat_user_message(
                    cursor,
                    user_id,
                    session_id,
                    content,
                    client_request_id,
                )
                if not matches:
                    conn.rollback()
                    return "mismatch", None, None
                if existing_assistant:
                    cursor.execute(
                        """UPDATE chat_requests
                           SET status = 'completed', response_message_id = %s
                           WHERE id = %s AND owner_token = %s""",
                        (existing_assistant["id"], request_row["id"], owner_token),
                    )
                    conn.commit()
                    return "completed", None, existing_assistant
                conn.commit()
                return "reserved", owner_token, None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def renew_chat_request_lease(
    user_id: int,
    session_id: int,
    client_request_id: str,
    owner_token: str,
    *,
    lease_seconds: Optional[int] = None,
) -> None:
    lease_seconds = lease_seconds or chat_request_lease_seconds()
    lease_expires_at = _utcnow() + timedelta(seconds=max(1, min(int(lease_seconds), 3600)))
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE chat_requests SET lease_expires_at = %s
                   WHERE user_id = %s AND session_id = %s
                     AND client_request_id = %s AND owner_token = %s
                     AND status = 'processing'""",
                (
                    lease_expires_at,
                    user_id,
                    session_id,
                    client_request_id,
                    owner_token,
                ),
            )
            if cursor.rowcount == 0:
                # MySQL reports changed rows by default.  An immediate renewal
                # can therefore return zero when DATETIME rounds both lease
                # values to the same second even though this worker still owns
                # the request.  Confirm ownership under the same transaction
                # before treating the no-op update as a lost lease.
                cursor.execute(
                    """SELECT id FROM chat_requests
                       WHERE user_id = %s AND session_id = %s
                         AND client_request_id = %s AND owner_token = %s
                         AND status = 'processing'
                       FOR UPDATE""",
                    (user_id, session_id, client_request_id, owner_token),
                )
                if not cursor.fetchone():
                    raise ChatRequestOwnershipError("Chat request lease is no longer owned")
            elif cursor.rowcount != 1:
                raise ChatRequestOwnershipError("Chat request lease is no longer owned")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_chat_request(
    user_id: int,
    session_id: int,
    client_request_id: str,
    owner_token: str,
    content: str,
) -> int:
    """Atomically save the assistant response if and only if this owner is current."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, status, owner_token, response_message_id
                   FROM chat_requests
                   WHERE user_id = %s AND session_id = %s
                     AND client_request_id = %s
                   FOR UPDATE""",
                (user_id, session_id, client_request_id),
            )
            request_row = cursor.fetchone()
            if (
                not request_row
                or request_row["owner_token"] != owner_token
                or request_row["status"] != "processing"
            ):
                raise ChatRequestOwnershipError("Chat request is owned by another worker")
            try:
                cursor.execute(
                    """INSERT INTO messages
                       (user_id, session_id, role, content, client_request_id)
                       VALUES (%s, %s, 'assistant', %s, %s)""",
                    (user_id, session_id, content, client_request_id),
                )
                message_id = cursor.lastrowid
            except pymysql.err.IntegrityError:
                cursor.execute(
                    """SELECT id FROM messages
                       WHERE user_id = %s AND session_id = %s
                         AND role = 'assistant' AND client_request_id = %s
                       LIMIT 1""",
                    (user_id, session_id, client_request_id),
                )
                existing = cursor.fetchone()
                if not existing:
                    raise
                message_id = existing["id"]
            cursor.execute(
                """UPDATE chat_requests
                   SET status = 'completed', response_message_id = %s,
                       lease_expires_at = UTC_TIMESTAMP()
                   WHERE id = %s AND owner_token = %s AND status = 'processing'""",
                (message_id, request_row["id"], owner_token),
            )
            if cursor.rowcount != 1:
                raise ChatRequestOwnershipError("Chat request completion lost ownership")
        conn.commit()
        return int(message_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def release_chat_request(
    user_id: int,
    session_id: int,
    client_request_id: str,
    owner_token: str,
) -> bool:
    """Release only the current owner's processing request and durable user message."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """DELETE FROM chat_requests
                   WHERE user_id = %s AND session_id = %s
                     AND client_request_id = %s AND owner_token = %s
                     AND status = 'processing'""",
                (user_id, session_id, client_request_id, owner_token),
            )
            released = cursor.rowcount == 1
            if released:
                cursor.execute(
                    """DELETE FROM messages
                       WHERE user_id = %s AND session_id = %s
                         AND role = 'user' AND client_request_id = %s
                         AND NOT EXISTS (
                             SELECT 1 FROM (
                                 SELECT id FROM messages
                                 WHERE user_id = %s AND session_id = %s
                                   AND role = 'assistant' AND client_request_id = %s
                             ) AS completed
                         )""",
                    (
                        user_id,
                        session_id,
                        client_request_id,
                        user_id,
                        session_id,
                        client_request_id,
                    ),
                )
        conn.commit()
        return released
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reserve_idempotent_user_message(
    user_id: int,
    session_id: int,
    content: str,
    client_request_id: str,
) -> tuple[str, Optional[dict[str, Any]]]:
    """Atomically reserve a request ID without duplicating the user message.

    Returns ``reserved``, ``completed``, ``processing``, or ``mismatch``.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    """INSERT INTO messages
                       (user_id, session_id, role, content, client_request_id)
                       VALUES (%s, %s, 'user', %s, %s)""",
                    (user_id, session_id, content, client_request_id),
                )
                conn.commit()
                return "reserved", None
            except pymysql.err.IntegrityError:
                conn.rollback()
                cursor.execute(
                    """SELECT content
                       FROM messages
                       WHERE user_id = %s AND session_id = %s
                         AND role = 'user' AND client_request_id = %s
                       LIMIT 1""",
                    (user_id, session_id, client_request_id),
                )
                existing_user = cursor.fetchone()
                if not existing_user or existing_user["content"] != content:
                    return "mismatch", None
                cursor.execute(
                    """SELECT id, content, timestamp
                       FROM messages
                       WHERE user_id = %s AND session_id = %s
                         AND role = 'assistant' AND client_request_id = %s
                       LIMIT 1""",
                    (user_id, session_id, client_request_id),
                )
                assistant = cursor.fetchone()
                if assistant:
                    return "completed", assistant
                return "processing", None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def release_idempotent_user_message(
    user_id: int,
    session_id: int,
    client_request_id: str,
) -> None:
    """Release a failed reservation so the same client request can be retried."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """DELETE FROM messages
                   WHERE user_id = %s AND session_id = %s
                     AND role = 'user' AND client_request_id = %s
                     AND NOT EXISTS (
                         SELECT 1 FROM (
                             SELECT id FROM messages
                             WHERE user_id = %s AND session_id = %s
                               AND role = 'assistant' AND client_request_id = %s
                         ) AS completed
                     )""",
                (
                    user_id,
                    session_id,
                    client_request_id,
                    user_id,
                    session_id,
                    client_request_id,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_session_messages(session_id, limit=50):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, role, content, feedback, timestamp
                   FROM messages WHERE session_id = %s
                   ORDER BY id DESC LIMIT %s""",
                (session_id, limit),
            )
            rows = cursor.fetchall()
        result = [
            (row["id"], row["role"], row["content"], row["feedback"], row["timestamp"])
            for row in rows
        ]
        return list(reversed(result))
    finally:
        conn.close()


def clear_session_messages(session_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_message_feedback(msg_id, feedback):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE messages SET feedback = %s WHERE id = %s", (feedback, msg_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
