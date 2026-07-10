"""Database access helpers and backwards-compatible schema migrations.

This project intentionally keeps its database layer small.  Schema changes are
made idempotently here because the application is currently deployed without a
migration runner.  New deployments get the complete schema and existing
deployments are upgraded without dropping user data.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Any, Optional

import pymysql


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root123"),
    "database": os.getenv("DB_NAME", "ai_assistant"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

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
                    last_login_at DATETIME NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            # Existing installations predate password hashes and roles.
            _ensure_column(cursor, "users", "password_hash", "VARCHAR(255) NOT NULL DEFAULT ''")
            _ensure_column(cursor, "users", "role", "VARCHAR(20) NOT NULL DEFAULT 'user'")
            _ensure_column(cursor, "users", "status", "VARCHAR(20) NOT NULL DEFAULT 'active'")
            _ensure_column(cursor, "users", "last_login_at", "DATETIME NULL DEFAULT NULL")
            cursor.execute(
                "UPDATE users SET role = %s WHERE role IS NULL OR role NOT IN (%s, %s, %s)",
                (ROLE_USER, ROLE_USER, ROLE_ADMIN, ROLE_SUPER_ADMIN),
            )
            cursor.execute(
                "UPDATE users SET status = %s WHERE status IS NULL OR status NOT IN (%s, %s)",
                (STATUS_ACTIVE, STATUS_ACTIVE, STATUS_DISABLED),
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
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            _ensure_index(cursor, "messages", "idx_messages_feedback_timestamp", "(`feedback`, `timestamp`)")
            _ensure_index(cursor, "messages", "idx_messages_user_timestamp", "(`user_id`, `timestamp`)")

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


# --- User operations -----------------------------------------------------

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
                """SELECT id, username, password_hash, role, status,
                          last_login_at, created_at
                   FROM users WHERE username = %s""",
                (username,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    """Fetch a public user record (never returns a password hash)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, role, status, last_login_at, created_at
                   FROM users WHERE id = %s""",
                (user_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[dict[str, Any]]:
    """Verify credentials, reject disabled accounts, and record successful login."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT id, username, password_hash, role, status,
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
            if password_needs_rehash(row["password_hash"]):
                updates.append("password_hash = %s")
                params.append(hash_password(password))
            params.append(row["id"])
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s", tuple(params)
            )
            cursor.execute(
                """SELECT id, username, role, status, last_login_at, created_at
                   FROM users WHERE id = %s""",
                (row["id"],),
            )
            authenticated = cursor.fetchone()
        conn.commit()
        return authenticated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def login_user(username: str, password: str) -> Optional[int]:
    """Compatibility wrapper for callers that only need the authenticated ID."""
    user = authenticate_user(username, password)
    return user["id"] if user else None


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


def save_message(user_id, session_id, role, content):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO messages (user_id, session_id, role, content)
                   VALUES (%s, %s, %s, %s)""",
                (user_id, session_id, role, content),
            )
            message_id = cursor.lastrowid
        conn.commit()
        return message_id
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
