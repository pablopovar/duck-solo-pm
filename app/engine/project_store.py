from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 3


def database_path(project_root: Path) -> Path:
    canonical_root = project_root / ".duck"
    legacy_root = project_root / ".pocket"

    if canonical_root.exists() or not legacy_root.exists():
        return canonical_root / "project.sqlite3"

    return legacy_root / "project.sqlite3"


@contextmanager
def connection(project_root: Path) -> Iterator[sqlite3.Connection]:
    path = database_path(project_root)
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


def ensure_schema(project_root: Path) -> None:
    with connection(project_root) as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS store_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_profile (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                what_text TEXT NOT NULL DEFAULT '',
                why_text TEXT NOT NULL DEFAULT '',
                class_name TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS project_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS activity (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL CHECK (
                    kind IN (
                        'note', 'todo', 'status', 'link',
                        'file', 'document', 'check-in', 'event'
                    )
                ),
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            );

            CREATE INDEX IF NOT EXISTS activity_visible_sequence
                ON activity(deleted_at, sequence DESC);

            CREATE INDEX IF NOT EXISTS activity_kind_visible
                ON activity(kind, deleted_at, sequence DESC);

            CREATE TABLE IF NOT EXISTS quick_links (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                url TEXT NOT NULL,
                icon TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS quick_links_sequence
                ON quick_links(sequence ASC);

            CREATE TABLE IF NOT EXISTS project_chat_messages (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS project_chat_sequence
                ON project_chat_messages(sequence DESC);
            """
        )
        database.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )


def initialize_project(
    project_root: Path,
    profile: dict[str, str],
    settings: dict[str, str],
) -> None:
    ensure_schema(project_root)

    with connection(project_root) as database:
        database.execute(
            """
            INSERT OR IGNORE INTO project_profile(
                singleton, what_text, why_text, class_name
            ) VALUES (1, ?, ?, ?)
            """,
            (
                profile.get("what", ""),
                profile.get("why", ""),
                profile.get("class", ""),
            ),
        )

        for key, value in settings.items():
            database.execute(
                """
                INSERT OR IGNORE INTO project_settings(key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )


def meta_value(project_root: Path, key: str) -> str | None:
    with connection(project_root) as database:
        row = database.execute(
            "SELECT value FROM store_meta WHERE key = ?",
            (key,),
        ).fetchone()

    return None if row is None else str(row["value"])


def set_meta(project_root: Path, key: str, value: str) -> None:
    with connection(project_root) as database:
        database.execute(
            """
            INSERT INTO store_meta(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def import_activity(
    project_root: Path,
    records: list[dict[str, object]],
) -> None:
    with connection(project_root) as database:
        for record in records:
            database.execute(
                """
                INSERT OR IGNORE INTO activity(
                    id, kind, title, body, url, completed,
                    pinned, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record["id"]),
                    str(record["kind"]),
                    str(record["title"]),
                    str(record.get("body", "")),
                    str(record.get("url", "")),
                    int(bool(record.get("completed", False))),
                    int(bool(record.get("pinned", False))),
                    str(record["created_at"]),
                    str(record["updated_at"]),
                ),
            )


def create_activity(
    project_root: Path,
    record: dict[str, object],
) -> None:
    import_activity(project_root, [record])


def list_activity(
    project_root: Path,
    *,
    limit: int = 100,
    kind: str | None = None,
) -> list[dict[str, object]]:
    where = "deleted_at IS NULL"
    parameters: list[object] = []

    if kind is not None:
        where += " AND kind = ?"
        parameters.append(kind)

    parameters.append(limit)

    with connection(project_root) as database:
        rows = database.execute(
            f"""
            SELECT id, kind, title, body, url, completed, pinned,
                   created_at, updated_at
            FROM activity
            WHERE {where}
            ORDER BY sequence DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def search_activity(
    project_root: Path,
    query: str,
    *,
    limit: int = 100,
    kind: str | None = None,
) -> list[dict[str, object]]:
    cleaned = query.strip()

    if not cleaned:
        return []

    where = "deleted_at IS NULL AND (title LIKE ? OR body LIKE ? OR url LIKE ?)"
    pattern = f"%{cleaned}%"
    parameters: list[object] = [pattern, pattern, pattern]

    if kind is not None:
        where += " AND kind = ?"
        parameters.append(kind)

    parameters.append(max(1, min(limit, 500)))

    with connection(project_root) as database:
        rows = database.execute(
            f"""
            SELECT id, kind, title, body, url, completed, pinned,
                   created_at, updated_at
            FROM activity
            WHERE {where}
            ORDER BY sequence DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def activity_item(
    project_root: Path,
    activity_id: str,
) -> dict[str, object] | None:
    with connection(project_root) as database:
        row = database.execute(
            """
            SELECT id, kind, title, body, url, completed, pinned,
                   created_at, updated_at
            FROM activity
            WHERE id = ? AND deleted_at IS NULL
            """,
            (activity_id,),
        ).fetchone()

    return None if row is None else dict(row)


def convert_note_to_file(
    project_root: Path,
    activity_id: str,
    relative_path: str,
    url: str,
    updated_at: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            """
            UPDATE activity
            SET kind = 'file', body = ?, url = ?,
                pinned = 0, updated_at = ?
            WHERE id = ?
              AND kind = 'note'
              AND deleted_at IS NULL
            """,
            (relative_path, url, updated_at, activity_id),
        )

    return cursor.rowcount == 1


def pinned_resources(project_root: Path) -> list[dict[str, object]]:
    with connection(project_root) as database:
        rows = database.execute(
            """
            SELECT id, kind, title, body, url
            FROM activity
            WHERE deleted_at IS NULL
              AND pinned = 1
              AND kind IN ('link', 'file', 'document')
            ORDER BY sequence DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def open_todos(
    project_root: Path,
    limit: int = 3,
) -> list[dict[str, object]]:
    with connection(project_root) as database:
        rows = database.execute(
            """
            SELECT id, kind, title, body, url, completed, pinned,
                   created_at, updated_at
            FROM activity
            WHERE deleted_at IS NULL
              AND kind = 'todo'
              AND completed = 0
            ORDER BY sequence DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def set_pinned(
    project_root: Path,
    activity_id: str,
    pinned: bool,
    updated_at: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            """
            UPDATE activity
            SET pinned = ?, updated_at = ?
            WHERE id = ?
              AND deleted_at IS NULL
              AND kind IN ('link', 'file', 'document')
            """,
            (int(pinned), updated_at, activity_id),
        )

    return cursor.rowcount == 1


def update_todo(
    project_root: Path,
    activity_id: str,
    title: str,
    body: str,
    updated_at: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            """
            UPDATE activity
            SET title = ?, body = ?, updated_at = ?
            WHERE id = ?
              AND kind = 'todo'
              AND deleted_at IS NULL
            """,
            (title, body, updated_at, activity_id),
        )

    return cursor.rowcount == 1


def set_todo_completed(
    project_root: Path,
    activity_id: str,
    completed: bool,
    updated_at: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            """
            UPDATE activity
            SET completed = ?, updated_at = ?
            WHERE id = ?
              AND kind = 'todo'
              AND deleted_at IS NULL
            """,
            (int(completed), updated_at, activity_id),
        )

    return cursor.rowcount == 1


def list_quick_links(project_root: Path) -> list[dict[str, object]]:
    with connection(project_root) as database:
        rows = database.execute(
            """
            SELECT id, label, url, icon, created_at, updated_at
            FROM quick_links
            ORDER BY sequence ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def create_quick_link(
    project_root: Path,
    record: dict[str, object],
) -> None:
    with connection(project_root) as database:
        database.execute(
            """
            INSERT INTO quick_links(
                id, label, url, icon, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(record["id"]),
                str(record["label"]),
                str(record["url"]),
                str(record.get("icon", "")),
                str(record["created_at"]),
                str(record["updated_at"]),
            ),
        )


def initialize_quick_links(
    project_root: Path,
    records: list[dict[str, object]],
) -> None:
    """Seed legacy/configured links once, in the same transaction as the marker."""
    with connection(project_root) as database:
        initialized = database.execute(
            "SELECT value FROM store_meta WHERE key = 'quick_links_initialized'"
        ).fetchone()

        if initialized is not None and str(initialized["value"]) == "1":
            return

        for record in records:
            database.execute(
                """
                INSERT INTO quick_links(
                    id, label, url, icon, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record["id"]),
                    str(record["label"]),
                    str(record["url"]),
                    str(record.get("icon", "")),
                    str(record["created_at"]),
                    str(record["updated_at"]),
                ),
            )

        database.execute(
            """
            INSERT INTO store_meta(key, value)
            VALUES ('quick_links_initialized', '1')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )


def update_quick_link(
    project_root: Path,
    link_id: str,
    label: str,
    url: str,
    icon: str,
    updated_at: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            """
            UPDATE quick_links
            SET label = ?, url = ?, icon = ?, updated_at = ?
            WHERE id = ?
            """,
            (label, url, icon, updated_at, link_id),
        )

    return cursor.rowcount == 1


def delete_quick_link(
    project_root: Path,
    link_id: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            "DELETE FROM quick_links WHERE id = ?",
            (link_id,),
        )

    return cursor.rowcount == 1


def soft_delete(
    project_root: Path,
    activity_id: str,
    deleted_at: str,
) -> bool:
    with connection(project_root) as database:
        cursor = database.execute(
            """
            UPDATE activity
            SET deleted_at = ?, updated_at = ?, pinned = 0
            WHERE id = ? AND deleted_at IS NULL
            """,
            (deleted_at, deleted_at, activity_id),
        )

    return cursor.rowcount == 1


def project_profile(project_root: Path) -> dict[str, str]:
    with connection(project_root) as database:
        row = database.execute(
            """
            SELECT what_text, why_text, class_name
            FROM project_profile WHERE singleton = 1
            """
        ).fetchone()

    if row is None:
        return {"what": "", "why": "", "class": ""}

    return {
        "what": str(row["what_text"]),
        "why": str(row["why_text"]),
        "class": str(row["class_name"]),
    }


def update_project_profile(
    project_root: Path,
    profile: dict[str, str],
    updated_at: str,
) -> None:
    with connection(project_root) as database:
        database.execute(
            """
            INSERT INTO project_profile(
                singleton, what_text, why_text, class_name, updated_at
            ) VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(singleton) DO UPDATE SET
                what_text = excluded.what_text,
                why_text = excluded.why_text,
                class_name = excluded.class_name,
                updated_at = excluded.updated_at
            """,
            (
                profile.get("what", ""),
                profile.get("why", ""),
                profile.get("class", ""),
                updated_at,
            ),
        )


def project_settings(project_root: Path) -> dict[str, str]:
    with connection(project_root) as database:
        rows = database.execute(
            "SELECT key, value FROM project_settings"
        ).fetchall()

    return {
        str(row["key"]): str(row["value"])
        for row in rows
    }


def update_project_settings(
    project_root: Path,
    values: dict[str, str],
    updated_at: str,
) -> None:
    with connection(project_root) as database:
        for key, value in values.items():
            database.execute(
                """
                INSERT INTO project_settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, updated_at),
            )


def add_chat_message(
    project_root: Path,
    message: dict[str, object],
) -> None:
    with connection(project_root) as database:
        database.execute(
            """
            INSERT INTO project_chat_messages(
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


def list_chat_messages(
    project_root: Path,
    *,
    limit: int = 100,
) -> list[dict[str, object]]:
    with connection(project_root) as database:
        rows = database.execute(
            """
            SELECT id, role, content, model, created_at
            FROM (
                SELECT sequence, id, role, content, model, created_at
                FROM project_chat_messages
                ORDER BY sequence DESC
                LIMIT ?
            )
            ORDER BY sequence ASC
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def clear_chat_messages(project_root: Path) -> int:
    with connection(project_root) as database:
        cursor = database.execute(
            "DELETE FROM project_chat_messages"
        )

    return cursor.rowcount
