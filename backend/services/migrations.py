"""Versioned database migrations for structured career-domain data.

The legacy bootstrap in :mod:`backend.services.database` remains responsible
for installations created before a migration ledger existed.  All new domain
schema changes are recorded here so they are applied once, in order, and are
safe when more than one application instance starts at the same time.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import logging
from collections.abc import Iterable

from backend.services.database import get_connection


logger = logging.getLogger("aiagent.migrations")
MIGRATION_LOCK_NAME = "ai_job_consultant_schema_migrations"


CAREER_SCHEMA_V1 = (
    """
    CREATE TABLE IF NOT EXISTS career_resumes (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        target_role VARCHAR(255) NOT NULL DEFAULT '',
        content MEDIUMTEXT NOT NULL,
        source_name VARCHAR(512) NULL DEFAULT NULL,
        is_primary BOOLEAN NOT NULL DEFAULT FALSE,
        primary_marker TINYINT GENERATED ALWAYS AS (
            CASE WHEN is_primary THEN 1 ELSE NULL END
        ) STORED,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_career_resumes_primary_user (user_id, primary_marker),
        KEY idx_career_resumes_user_updated (user_id, updated_at),
        CONSTRAINT fk_career_resumes_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS career_jobs (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        company VARCHAR(255) NOT NULL DEFAULT '',
        description MEDIUMTEXT NOT NULL,
        source_url VARCHAR(2048) NULL DEFAULT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'saved',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_career_jobs_user_id (user_id, id),
        KEY idx_career_jobs_user_status_updated (user_id, status, updated_at),
        CONSTRAINT fk_career_jobs_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS career_applications (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        job_id BIGINT NOT NULL,
        stage VARCHAR(32) NOT NULL DEFAULT 'saved',
        next_action VARCHAR(500) NOT NULL DEFAULT '',
        deadline DATE NULL DEFAULT NULL,
        notes MEDIUMTEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_career_applications_user_job (user_id, job_id),
        KEY idx_career_applications_user_stage_deadline (user_id, stage, deadline),
        CONSTRAINT fk_career_applications_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_career_applications_job
            FOREIGN KEY (user_id, job_id)
            REFERENCES career_jobs(user_id, id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS career_interviews (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        job_id BIGINT NULL DEFAULT NULL,
        title VARCHAR(255) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'planned',
        total_questions INT NOT NULL DEFAULT 0,
        current_question INT NOT NULL DEFAULT 0,
        overall_score DECIMAL(5,2) NULL DEFAULT NULL,
        completed_at DATETIME NULL DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_career_interviews_user_status_updated (user_id, status, updated_at),
        CONSTRAINT fk_career_interviews_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_career_interviews_job
            FOREIGN KEY (user_id, job_id)
            REFERENCES career_jobs(user_id, id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS career_interview_questions (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        interview_id BIGINT NOT NULL,
        position INT NOT NULL,
        question TEXT NOT NULL,
        answer MEDIUMTEXT NOT NULL,
        score DECIMAL(5,2) NULL DEFAULT NULL,
        feedback MEDIUMTEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_career_interview_question_position (interview_id, position),
        CONSTRAINT fk_career_interview_questions_interview
            FOREIGN KEY (interview_id) REFERENCES career_interviews(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS career_reports (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        kind VARCHAR(32) NOT NULL,
        title VARCHAR(255) NOT NULL,
        entity_type VARCHAR(32) NULL DEFAULT NULL,
        entity_id BIGINT NULL DEFAULT NULL,
        summary MEDIUMTEXT NOT NULL,
        payload JSON NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY idx_career_reports_user_kind_created (user_id, kind, created_at),
        CONSTRAINT fk_career_reports_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS career_skills (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        skill VARCHAR(255) NOT NULL,
        target_level VARCHAR(255) NOT NULL DEFAULT '',
        status VARCHAR(32) NOT NULL DEFAULT 'planned',
        progress TINYINT UNSIGNED NOT NULL DEFAULT 0,
        due_date DATE NULL DEFAULT NULL,
        notes MEDIUMTEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_career_skills_user_skill (user_id, skill),
        KEY idx_career_skills_user_status_due (user_id, status, due_date),
        CONSTRAINT fk_career_skills_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


MIGRATIONS: tuple[tuple[int, str, Iterable[str]], ...] = (
    (1, "structured-career-workspace", CAREER_SCHEMA_V1),
)


class MigrationError(RuntimeError):
    """Raised when the migration ledger cannot be acquired or updated."""


def migration_checksum(statements: Iterable[str]) -> str:
    normalized = "\n-- statement --\n".join(
        "\n".join(line.rstrip() for line in statement.strip().splitlines())
        for statement in statements
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@contextmanager
def schema_migration_lock(timeout_seconds: int = 30):
    """Serialize legacy bootstrap and versioned migrations across instances."""
    connection = get_connection()
    acquired = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT GET_LOCK(%s, %s) AS acquired",
                (MIGRATION_LOCK_NAME, max(0, min(int(timeout_seconds), 120))),
            )
            acquired = bool((cursor.fetchone() or {}).get("acquired"))
        if not acquired:
            raise MigrationError("Timed out waiting for the database migration lock")
        yield
    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK_NAME,))
            except Exception:
                logger.exception("Failed to release the database migration lock")
        connection.close()


def run_migrations(*, acquire_lock: bool = True) -> list[int]:
    """Apply pending migrations and return the versions applied this run."""
    connection = get_connection()
    acquired = False
    applied_now: list[int] = []
    try:
        with connection.cursor() as cursor:
            if acquire_lock:
                cursor.execute("SELECT GET_LOCK(%s, 30) AS acquired", (MIGRATION_LOCK_NAME,))
                row = cursor.fetchone() or {}
                acquired = bool(row.get("acquired"))
                if not acquired:
                    raise MigrationError("Timed out waiting for the database migration lock")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    checksum CHAR(64) NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cursor.execute("SELECT version, name, checksum FROM schema_migrations ORDER BY version")
            applied = {int(item["version"]): item for item in cursor.fetchall()}

            for version, name, statements in MIGRATIONS:
                checksum = migration_checksum(statements)
                if version in applied:
                    recorded = applied[version]
                    if recorded.get("name") != name or recorded.get("checksum") != checksum:
                        raise MigrationError(
                            f"Migration {version} does not match its recorded name/checksum"
                        )
                    continue
                logger.info("Applying database migration %s: %s", version, name)
                for statement in statements:
                    cursor.execute(statement)
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                    (version, name, checksum),
                )
                connection.commit()
                applied_now.append(version)
    except Exception:
        connection.rollback()
        raise
    finally:
        if acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK_NAME,))
            except Exception:
                logger.exception("Failed to release the database migration lock")
        connection.close()
    return applied_now
