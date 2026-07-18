from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.engine import projects


SCHEMA_VERSION = 1


def database_path() -> Path:
    return projects.projects_root() / ".duck" / "system.sqlite3"


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path, timeout=5.0)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    database.execute("PRAGMA busy_timeout = 5000")
    database.execute("PRAGMA journal_mode = DELETE")

    try:
        yield database
        database.commit()
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()


def ensure_schema() -> None:
    with connection() as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_chat_messages (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS system_chat_sequence
                ON system_chat_messages(sequence DESC);
            """
        )
        database.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )


def sync_projects(project_names: list[str]) -> None:
    ensure_schema()
    timestamp = datetime.now(timezone.utc).isoformat()

    with connection() as database:
        database.execute("UPDATE projects SET active = 0")

        for name in project_names:
            root = projects.project_root(name)
            database.execute(
                """
                INSERT INTO projects(
                    id, root_path, pinned, active,
                    first_seen_at, last_seen_at
                ) VALUES (?, ?, 0, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    root_path = excluded.root_path,
                    active = 1,
                    last_seen_at = excluded.last_seen_at
                """,
                (name, str(root), timestamp, timestamp),
            )


def registered_projects() -> list[dict[str, object]]:
    ensure_schema()

    with connection() as database:
        rows = database.execute(
            """
            SELECT id, root_path, pinned, active,
                   first_seen_at, last_seen_at
            FROM projects
            WHERE active = 1
            ORDER BY pinned DESC, id COLLATE NOCASE
            """
        ).fetchall()

    return [dict(row) for row in rows]


def add_chat_message(message: dict[str, object]) -> None:
    ensure_schema()

    with connection() as database:
        database.execute(
            """
            INSERT INTO system_chat_messages(
                id, role, content, model, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(message["id"]),
                str(message["role"]),
                str(message["content"]),
                str(message.get("model", "")),
                str(message["created_at"]),
            ),
        )


def list_chat_messages(*, limit: int = 100) -> list[dict[str, object]]:
    ensure_schema()

    with connection() as database:
        rows = database.execute(
            """
            SELECT id, role, content, model, created_at
            FROM (
                SELECT sequence, id, role, content, model, created_at
                FROM system_chat_messages
                ORDER BY sequence DESC
                LIMIT ?
            )
            ORDER BY sequence ASC
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_chat_messages() -> int:
    ensure_schema()

    with connection() as database:
        cursor = database.execute("DELETE FROM system_chat_messages")

    return cursor.rowcount
