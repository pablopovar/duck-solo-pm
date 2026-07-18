from __future__ import annotations

import json
import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit
from zoneinfo import ZoneInfo
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from pydantic import BaseModel

from app.engine.duck_settings import (
    DuckSettingsError,
    PROMPT_KEYS,
    PROJECT_QUALIFIER_KEYS,
    QUALIFIER_VOCABULARIES,
    SESSION_VALUE_KEYS,
    VOCABULARY_KEYS,
    load_project_settings,
    load_session_values,
    load_system_settings,
    save_project_settings,
    save_session_values,
    save_system_settings,
)

from app.engine.projects import (
    EditableFileNotAllowed,
    ProjectAlreadyConfigured,
    ProjectError,
    ProjectNotFound,
    editable_file_labels,
    initialize_project,
    is_configured,
    migrate_project_state,
    project_state_status,
    project_summaries,
    project_system_root,
    project_root,
    read_dashboard,
    read_project_resources,
    read_editable_markdown,
    touch_project,
    write_editable_markdown,
)
from app.engine import (
    project_chat,
    project_store,
    system_chat,
    system_store,
)


WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Duck")

app.mount(
    "/static",
    StaticFiles(directory=WEB_DIR / "static"),
    name="static",
)

templates = Jinja2Templates(
    directory=WEB_DIR / "templates",
)

markdown = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "linkify": False,
        "typographer": False,
    },
)

_FRONTMATTER = re.compile(
    r"\A---\s*\n.*?\n---\s*\n",
    re.DOTALL,
)

_BARE_URL = re.compile(
    r"(?<!\]\()https?://[^\s<]+"
)

_LINK = re.compile(
    r'<a href="([^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)

_LEGACY_FOLDER_LOCATION = re.compile(
    r"(?m)^(\s*\d+)\s+"
    r"(\$ROOT/projects/.+?)\s+"
    r"#\(click to open in file manager\)\s*$"
)


class MarkdownUpdate(BaseModel):
    frontmatter: str = ""
    body: str = ""
    has_frontmatter: bool = False


class StatusUpdate(BaseModel):
    update: str = ""


class QuickEntry(BaseModel):
    kind: str = ""
    title: str = ""
    text: str = ""


class ActivityPinUpdate(BaseModel):
    pinned: bool = True


class NoteFileConversion(BaseModel):
    path: str = ""


class ProjectAboutUpdate(BaseModel):
    what: str = ""
    why: str = ""
    class_name: str = ""


class ProjectChatRequest(BaseModel):
    message: str = ""
    model: str = ""


def _chat_message_payload(
    message: dict[str, object],
) -> dict[str, object]:
    payload = dict(message)

    if str(message.get("role", "")) == "assistant":
        payload["html"] = markdown.render(
            str(message.get("content", ""))
        )

    return payload


# DUCK SETTINGS SUBSYSTEM


class SessionValuesUpdate(BaseModel):
    current_state: str = ""
    next_action: str = ""
    unresolved_decisions: str = ""
    milestone_definition: str = ""


def render_dashboard(source: str) -> str:
    visible = _FRONTMATTER.sub(
        "",
        source,
        count=1,
    )

    # Support dashboards created before the copy: link syntax.
    # This changes only the rendered dashboard, not dashboard.md.
    visible = _LEGACY_FOLDER_LOCATION.sub(
        lambda match: (
            f"{match.group(1)} "
            f"[Project folder]"
            f"(<copy:{match.group(2)}>)"
        ),
        visible,
    )

    visible = _BARE_URL.sub(
        lambda match: (
            f"[{match.group(0)}]"
            f"({match.group(0)})"
        ),
        visible,
    )

    rendered = markdown.render(visible)

    def keep_external(
        match: re.Match[str],
    ) -> str:
        href = match.group(1)
        label = match.group(2)

        if href.startswith("copy:"):
            location = unquote(
                href.removeprefix("copy:")
            )

            return (
                '<a href="#" '
                'class="copy-location" '
                f'data-copy-location="'
                f'{escape(location, quote=True)}">'
                f"{label}</a>"
            )

        if href.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return (
                f'<a href="{href}" '
                f'target="_blank" '
                f'rel="noopener noreferrer">'
                f"{label}</a>"
            )

        return label

    return _LINK.sub(
        keep_external,
        rendered,
    )


def dashboard_project_title(
    source: str,
    fallback: str,
) -> str:
    frontmatter = _FRONTMATTER.match(source)

    if frontmatter is None:
        return fallback

    for line in frontmatter.group(0).splitlines():
        if not line.startswith("project:"):
            continue

        title = line.split(":", 1)[1].strip()

        if (
            len(title) >= 2
            and title[0] == title[-1]
            and title[0] in {'"', "'"}
        ):
            title = title[1:-1].strip()

        return title or fallback

    return fallback


def project_title(project: str) -> str:
    source = read_dashboard(project)

    if source is None:
        return project

    return dashboard_project_title(
        source,
        project,
    )



_MARKDOWN_TODO = re.compile(
    r"^\s*[-*]\s+\[(?P<done>[ xX])\]\s+(?P<title>.+?)\s*$"
)

_MARKDOWN_CONTINUATION = re.compile(
    r"^\s{2,}(?P<body>.*)$"
)

_QUICK_ENTRY_TITLE = re.compile(
    r"^\*\*(?P<timestamp>.+?)\*\*\s+[\u2014-]\s*(?P<body>.*)$"
)

_STATUS_ACTIVITY = re.compile(
    r"^\s*[-*]\s+\*\*(?P<timestamp>.+?)\*\*\s+[—-]\s+(?P<body>.+?)\s*$"
)

_LINK_INPUT_URL = re.compile(
    r"https?://[^\s<>\"']+"
)


def _decoded_frontmatter_value(
    frontmatter: str,
    key: str,
) -> str:
    pattern = re.compile(
        rf"^{re.escape(key)}:[ \t]*(.*)$",
        re.MULTILINE,
    )
    match = pattern.search(frontmatter)

    if match is None:
        return ""

    raw = match.group(1).strip()

    if not raw:
        return ""

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]

    if value is None:
        return ""

    return str(value).strip()


def _read_project_file_body(
    project: str,
    label: str,
) -> str:
    try:
        document = read_editable_markdown(
            project,
            label,
        )
    except ProjectError:
        return ""

    return str(document["body"])


def _project_config_values(
    project: str,
) -> dict[str, str]:
    try:
        document = read_editable_markdown(
            project,
            "config.md",
        )
    except ProjectError:
        return {}

    frontmatter = str(
        document["frontmatter"]
    )

    keys = (
        "project",
        "canonical",
        "url",
        "chatgpt",
        "local",
        "repo",
        "local_repo",
        "started",
    )

    return {
        key: _decoded_frontmatter_value(
            frontmatter,
            key,
        )
        for key in keys
    }


def _markdown_paragraphs(
    source: str,
    limit: int = 2,
) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []

    def finish() -> None:
        if not current:
            return

        text = " ".join(current).strip()
        current.clear()

        if text:
            paragraphs.append(text)

    for raw_line in source.splitlines():
        line = raw_line.strip()

        if not line:
            finish()

            if len(paragraphs) >= limit:
                break

            continue

        if line.startswith(("#", "---")):
            finish()
            continue

        if re.match(
            r"^[-*]\s+",
            line,
        ):
            finish()
            continue

        current.append(line)

    if len(paragraphs) < limit:
        finish()

    return paragraphs[:limit]


def _project_about(
    project: str,
) -> dict[str, str]:
    paragraphs = _markdown_paragraphs(
        _read_project_file_body(
            project,
            "manifesto.md",
        )
    )

    return {
        "what": (
            paragraphs[0]
            if paragraphs
            else "Not yet recorded."
        ),
        "why": (
            paragraphs[1]
            if len(paragraphs) > 1
            else "Not yet recorded."
        ),
    }


def _project_todos(
    project: str,
) -> list[dict[str, object]]:
    todos: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in _read_project_file_body(
        project,
        "inbox.md",
    ).splitlines():
        match = _MARKDOWN_TODO.match(line)

        if match is not None:
            if current is not None:
                todos.append(current)

            title = match.group("title")
            timestamp = ""
            quick_entry = _QUICK_ENTRY_TITLE.match(title)

            if quick_entry is not None:
                timestamp = quick_entry.group("timestamp")
                title = quick_entry.group("body")

            current = {
                "title": title,
                "completed": (
                    match.group("done")
                    .casefold()
                    == "x"
                ),
                "timestamp": timestamp,
            }
            continue

        if current is None:
            continue

        continuation = _MARKDOWN_CONTINUATION.match(line)

        if continuation is not None:
            current["title"] = (
                f'{current["title"]}\n'
                f'{continuation.group("body")}'
            )
            continue

        todos.append(current)
        current = None

    if current is not None:
        todos.append(current)

    return todos


def _project_quick_links(
    project: str,
    config: dict[str, str],
) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []

    def external(
        label: str,
        url: str,
        icon: str,
    ) -> None:
        if not url.startswith(
            ("https://", "http://")
        ):
            return

        links.append(
            {
                "label": label,
                "url": url,
                "icon": icon,
                "external": True,
            }
        )

    external(
        "ChatGPT",
        config.get("chatgpt", ""),
        "✺",
    )

    website = (
        config.get("url", "")
        or config.get("canonical", "")
    )
    external("Website", website, "◎")

    repository = config.get("repo", "")
    external("GitHub", repository, "◆")

    if config.get("local_repo", ""):
        links.append(
            {
                "label": "Local repo",
                "url": (
                    "pocket-open://local-repo"
                    f"?project={quote(project, safe='')}"
                ),
                "icon": "⌘",
                "external": False,
            }
        )

    links.append(
        {
            "label": "Project folder",
            "url": (
                "pocket-open://folder"
                f"?project={quote(project, safe='')}"
            ),
            "icon": "▱",
            "external": False,
        }
    )

    links.append(
        {
            "label": "Open Terminal",
            "url": (
                "pocket-open://terminal"
                f"?project={quote(project, safe='')}"
            ),
            "icon": ">_",
            "external": False,
        }
    )

    return links


def _activity_store_path(
    project: str,
) -> Path:
    return (
        project_system_root(project)
        / "activity.jsonl"
    )


def _activity_feed_items(
    project: str,
) -> list[dict[str, object]]:
    path = _activity_store_path(project)

    try:
        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except FileNotFoundError:
        return []
    except OSError:
        return []

    presentations = {
        "note": {
            "label": "Note",
            "title": "Note",
            "icon": "▤",
        },
        "link": {
            "label": "Link",
            "title": "Shared link",
            "icon": "↗",
        },
    }

    items: list[dict[str, object]] = []

    for raw_line in reversed(lines[-100:]):
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        if not isinstance(record, dict):
            continue

        kind = record.get("type")

        if (
            not isinstance(kind, str)
            or kind not in presentations
        ):
            continue

        body = record.get("body")

        if not isinstance(body, str) or not body.strip():
            continue

        url = record.get("url", "")

        if not isinstance(url, str):
            url = ""

        presentation = presentations[kind]

        items.append(
            {
                "type": kind,
                "id": str(record.get("id", "")),
                "label": presentation["label"],
                "title": presentation["title"],
                "body": body,
                "timestamp": str(
                    record.get("timestamp", "")
                ),
                "source": (
                    _activity_store_path(project)
                    .relative_to(project_root(project))
                    .as_posix()
                ),
                "icon": presentation["icon"],
                "url": url,
                "pinned": bool(
                    record.get("pinned", False)
                ),
            }
        )

    return items


def _pinned_activity_resources(
    project: str,
) -> list[dict[str, str]]:
    path = _activity_store_path(project)

    try:
        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except (FileNotFoundError, OSError):
        return []

    resources: list[dict[str, str]] = []

    for raw_line in reversed(lines):
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        if not isinstance(record, dict):
            continue

        kind = record.get("type")

        if (
            kind not in {"link", "file", "document"}
            or record.get("pinned") is not True
        ):
            continue

        body = record.get("body")
        url = record.get("url", "")

        if not isinstance(body, str) or not body.strip():
            continue

        if not isinstance(url, str):
            url = ""

        resources.append(
            {
                "id": str(record.get("id", "")),
                "type": str(kind),
                "label": body.strip(),
                "url": url,
                "icon": "\u2197" if kind == "link" else "\u25b1",
            }
        )

    return resources


def _set_activity_resource_pinned(
    project: str,
    activity_id: str,
    pinned: bool,
) -> None:
    path = _activity_store_path(project)

    try:
        lines = path.read_text(
            encoding="utf-8",
            errors="strict",
        ).splitlines()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Activity item not found",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not read project activity",
        ) from exc

    found = False
    updated_lines: list[str] = []

    for raw_line in lines:
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            updated_lines.append(raw_line)
            continue

        if (
            isinstance(record, dict)
            and record.get("id") == activity_id
            and record.get("type")
            in {"link", "file", "document"}
        ):
            record["pinned"] = pinned
            updated_lines.append(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )
            found = True
        else:
            updated_lines.append(raw_line)

    if not found:
        raise HTTPException(
            status_code=404,
            detail="Pinnable activity item not found",
        )

    temporary = path.with_name(
        f"{path.name}.{uuid4().hex}.tmp"
    )

    try:
        temporary.write_text(
            "\n".join(updated_lines) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not update project activity",
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _activity_entry_data(
    kind: str,
    text: str,
) -> tuple[str, str]:
    lines = _normalized_entry_lines(text)

    if not lines:
        raise HTTPException(
            status_code=400,
            detail="Entry cannot be empty",
        )

    content = "\n".join(lines).strip()

    if kind == "link" and len(content) > 20000:
        raise HTTPException(
            status_code=400,
            detail="Entry is too long",
        )

    if kind == "note":
        return content, ""

    match = _LINK_INPUT_URL.search(content)

    if match is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "A link entry needs an http:// or "
                "https:// URL"
            ),
        )

    raw_url = match.group(0)
    url = raw_url.rstrip(".,;")
    parsed = urlsplit(url)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        raise HTTPException(
            status_code=400,
            detail="The link URL is not valid",
        )

    label = (
        content[:match.start()]
        + content[match.end():]
    ).strip(" \t\r\n—-:")

    return label or url, url


def _append_activity_record(
    project: str,
    kind: str,
    text: str,
) -> dict[str, object]:
    body, url = _activity_entry_data(
        kind,
        text,
    )

    record = {
        "version": 1,
        "id": str(uuid4()),
        "type": kind,
        "body": body,
        "url": url,
        "timestamp": _quick_entry_timestamp(),
    }

    path = _activity_store_path(project)

    try:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save project activity",
        ) from exc

    return {
        "saved": True,
        "kind": kind,
        "file": (
            path.relative_to(project_root(project)).as_posix()
        ),
    }


def _legacy_activity_uuid(
    project: str,
    kind: str,
    position: int,
    content: str,
) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"duck:{project}:{kind}:{position}:{content}",
        )
    )


def _legacy_title_and_body(text: str) -> tuple[str, str]:
    lines = _normalized_entry_lines(text)

    if not lines:
        return "Untitled", ""

    first_line = lines[0].strip() or "Untitled"
    title = (
        first_line
        if len(first_line) <= 160
        else first_line[:157].rstrip() + "..."
    )
    body = "\n".join(lines).strip()
    return title, body


def _legacy_activity_records(
    project: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    fallback_time = _quick_entry_timestamp()
    path = _activity_store_path(project)

    try:
        jsonl_lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except (FileNotFoundError, OSError):
        jsonl_lines = []

    for position, raw_line in enumerate(jsonl_lines):
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        if not isinstance(record, dict):
            continue

        kind = record.get("type")

        if kind not in {"note", "link"}:
            continue

        old_body = str(record.get("body", "")).strip()
        url = str(record.get("url", "")).strip()
        stored_title = str(record.get("title", "")).strip()

        if kind == "link":
            title = stored_title or old_body or url or "Link"
            body = url or old_body
        else:
            derived_title, _derived_body = _legacy_title_and_body(
                old_body
            )
            title = stored_title or derived_title
            body = old_body

        timestamp = str(
            record.get("timestamp", fallback_time)
        )

        records.append(
            {
                "id": str(record.get("id", ""))
                or _legacy_activity_uuid(
                    project,
                    str(kind),
                    position,
                    raw_line,
                ),
                "kind": str(kind),
                "title": title,
                "body": body,
                "url": url,
                "completed": False,
                "pinned": bool(record.get("pinned", False)),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

    for position, todo in enumerate(_project_todos(project)):
        full_text = str(todo.get("title", "")).strip()
        title, body = _legacy_title_and_body(full_text)
        timestamp = str(todo.get("timestamp", "")) or fallback_time
        records.append(
            {
                "id": _legacy_activity_uuid(
                    project,
                    "todo",
                    position,
                    full_text,
                ),
                "kind": "todo",
                "title": title,
                "body": body,
                "url": "",
                "completed": bool(todo.get("completed", False)),
                "pinned": False,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

    status_position = 0

    for line in _read_project_file_body(
        project,
        "status.md",
    ).splitlines():
        match = _STATUS_ACTIVITY.match(line)

        if match is None:
            continue

        content = match.group("body")
        title, body = _legacy_title_and_body(content)
        timestamp = match.group("timestamp")
        records.append(
            {
                "id": _legacy_activity_uuid(
                    project,
                    "status",
                    status_position,
                    line,
                ),
                "kind": "status",
                "title": title,
                "body": body,
                "url": "",
                "completed": False,
                "pinned": False,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        status_position += 1

    return records


def _ensure_project_store(project: str) -> Path:
    root = project_root(project)
    legacy_profile = _project_about(project)
    legacy_settings = _project_config_values(project)

    try:
        qualifiers = load_project_settings(project)
    except DuckSettingsError:
        qualifiers = {}

    profile = {
        "what": (
            ""
            if legacy_profile.get("what", "") == "Not yet recorded."
            else legacy_profile.get("what", "")
        ),
        "why": (
            ""
            if legacy_profile.get("why", "") == "Not yet recorded."
            else legacy_profile.get("why", "")
        ),
        "class": str(qualifiers.get("class", "")),
    }
    all_settings = dict(legacy_settings)
    all_settings.update(
        {
            key: str(value)
            for key, value in qualifiers.items()
        }
    )
    project_store.initialize_project(
        root,
        profile,
        all_settings,
    )

    if project_store.meta_value(
        root,
        "legacy_activity_imported",
    ) != "1":
        project_store.import_activity(
            root,
            _legacy_activity_records(project),
        )
        project_store.set_meta(
            root,
            "legacy_activity_imported",
            "1",
        )

    return root


def _stored_feed_items(
    root: Path,
) -> list[dict[str, object]]:
    presentations = {
        "note": ("Note", "\u25a4"),
        "todo": ("Todo", "\u2610"),
        "status": ("Status", "\u2713"),
        "link": ("Link", "\u2197"),
        "file": ("File", "\u2315"),
        "document": ("Document", "\u25b1"),
        "check-in": ("Check-in", "\u25c9"),
        "event": ("Event", "\u25c7"),
    }
    items: list[dict[str, object]] = []

    for record in project_store.list_activity(root, limit=100):
        kind = str(record["kind"])
        label, icon = presentations.get(
            kind,
            (kind.title(), "\u2022"),
        )
        items.append(
            {
                "id": str(record["id"]),
                "type": kind,
                "label": label,
                "title": str(record["title"]),
                "body": str(record["body"]),
                "timestamp": str(record["created_at"]),
                "source": (
                    project_store.database_path(root)
                    .relative_to(root)
                    .as_posix()
                ),
                "icon": icon,
                "url": str(record["url"]),
                "pinned": bool(record["pinned"]),
                "completed": bool(record["completed"]),
            }
        )

    return items


def project_feed_context(
    project: str,
) -> dict[str, object]:
    root = _ensure_project_store(project)
    profile = project_store.project_profile(root)
    settings = project_store.project_settings(root)
    todos = project_store.open_todos(root, limit=3)
    pinned = project_store.pinned_resources(root)

    return {
        "project_about": {
            "what": profile.get("what", ""),
            "why": profile.get("why", ""),
            "class": profile.get("class", ""),
        },
        "quick_links": _project_quick_links(
            project,
            settings,
        ),
        "pinned_resources": [
            {
                "id": str(resource["id"]),
                "type": str(resource["kind"]),
                "label": str(resource["title"]),
                "url": str(resource["url"]),
                "icon": (
                    "\u2197"
                    if resource["kind"] == "link"
                    else "\u25b1"
                ),
            }
            for resource in pinned
        ],
        "top_todos": [
            {
                "title": str(todo["title"]),
            }
            for todo in todos
        ],
        "feed_items": _stored_feed_items(root),
        "project_started": settings.get("started", ""),
    }

def _env_enabled(
    name: str,
    default: bool,
) -> bool:
    fallback = "true" if default else "false"

    return os.environ.get(
        name,
        fallback,
    ).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def reminder_settings() -> dict[str, object]:
    try:
        periodic_minutes = int(
            os.environ.get(
                "DUCK_PERIODIC_REMINDER_MINUTES",
                "60",
            )
        )
    except ValueError:
        periodic_minutes = 60

    return {
        "leave_enabled": _env_enabled(
            "DUCK_LEAVE_REMINDER_ENABLED",
            True,
        ),
        "leave_message": os.environ.get(
            "DUCK_LEAVE_REMINDER_MESSAGE",
            "Did you check?",
        ).strip(),
        "periodic_enabled": _env_enabled(
            "DUCK_PERIODIC_REMINDER_ENABLED",
            True,
        ),
        "periodic_minutes": max(
            1,
            periodic_minutes,
        ),
        "periodic_message": os.environ.get(
            "DUCK_PERIODIC_REMINDER_MESSAGE",
            "Time to update the status.",
        ).strip(),
    }


def duck_settings_context(
    project: str | None,
) -> dict[str, object]:
    try:
        system_settings = load_system_settings()

        if project:
            stored_settings = project_store.project_settings(
                _ensure_project_store(project)
            )
            project_qualifiers = {
                key: stored_settings.get(key, "")
                for key in PROJECT_QUALIFIER_KEYS
            }
            session_values = (
                load_session_values(project)
            )
        else:
            project_qualifiers = {}
            session_values = {}
    except DuckSettingsError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return {
        "system_settings": system_settings,
        "prompt_templates": system_settings[
            "prompts"
        ],
        "project_qualifiers": (
            project_qualifiers
        ),
        "session_values": session_values,
    }


def context(
    request: Request,
    *,
    project: str | None = None,
    project_title: str | None = None,
    state: str = "empty",
    dashboard_html: str | None = None,
    editor_files: list[str] | None = None,
    github_url: str = "",
    local_repo: str = "",
    error: str | None = None,
) -> dict[str, object]:
    try:
        projects = project_summaries()
    except ProjectError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return {
        "request": request,
        "projects": projects,
        "project": project,
        "project_title": project_title,
        "state": state,
        "dashboard_html": dashboard_html,
        "editor_files": editor_files or [],
        "github_url": github_url,
        "local_repo": local_repo,
        "reminders": reminder_settings(),
        "error": error,
        "project_state": (
            project_state_status(project)
            if project
            else {
                "directory": ".duck",
                "legacy": False,
                "conflict": False,
                "legacy_is_symlink": False,
            }
        ),
        **duck_settings_context(project),
        "quote": quote,
    }


def ensure_project_exists(
    project: str,
) -> None:
    try:
        is_configured(project)
    except ProjectNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ProjectError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


def ensure_project_configured(
    project: str,
) -> None:
    ensure_project_exists(project)

    if not is_configured(project):
        raise HTTPException(
            status_code=409,
            detail="Project is not configured",
        )


def _system_chat_catalog() -> list[system_chat.SystemProject]:
    summaries = project_summaries()
    names = [str(item["name"]) for item in summaries]
    system_store.sync_projects(names)
    registry = {
        str(item["id"]): item
        for item in system_store.registered_projects()
    }
    catalog: list[system_chat.SystemProject] = []

    for item in summaries:
        name = str(item["name"])
        configured = is_configured(name)
        root = (
            _ensure_project_store(name)
            if configured
            else project_root(name)
        )
        catalog.append(
            system_chat.SystemProject(
                name=name,
                title=project_title(name),
                root=root,
                configured=configured,
                score=int(item.get("score", 0)),
                last_opened=int(item.get("last_opened", 0)),
                pinned=bool(registry.get(name, {}).get("pinned", False)),
                profile=(
                    project_store.project_profile(root)
                    if configured
                    else {"what": "", "why": "", "class": ""}
                ),
                settings=(
                    project_store.project_settings(root)
                    if configured
                    else {}
                ),
            )
        )

    return catalog


@app.get(
    "/project/{project}/open",
)
def record_project_open(
    project: str,
) -> RedirectResponse:
    ensure_project_exists(project)

    try:
        touch_project(project)
    except ProjectError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=(
            f"/project/"
            f"{quote(project, safe='')}"
        ),
        status_code=303,
    )


@app.post("/project/{project}/migrate-to-duck")
def migrate_legacy_project_state(
    project: str,
) -> RedirectResponse:
    ensure_project_exists(project)

    try:
        migrate_project_state(project)
    except ProjectError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=f"/project/{quote(project, safe='')}",
        status_code=303,
    )


@app.get(
    "/",
    response_class=HTMLResponse,
)
def home(
    request: Request,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context(request, state="system_chat"),
    )


@app.get(
    "/project/{project}",
    response_class=HTMLResponse,
)
def open_project(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_exists(project)

    if not is_configured(project):
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=context(
                request,
                project=project,
                state="unconfigured",
            ),
        )

    source = read_dashboard(project)

    if source is None:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=context(
                request,
                project=project,
                state="missing_dashboard",
            ),
        )

    resources = read_project_resources(
        project
    )
    page_context = context(
        request,
        project=project,
        state="feed",
        project_title=dashboard_project_title(
            source,
            project,
        ),
        github_url=resources[
            "github_url"
        ],
        local_repo=resources[
            "local_repo"
        ],
    )
    page_context.update(
        project_feed_context(project)
    )

    return templates.TemplateResponse(
        request=request,
        name="project_feed.html",
        context=page_context,
    )


@app.get(
    "/project/{project}/legacy",
    response_class=HTMLResponse,
)
def open_project_legacy(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_configured(project)
    source = read_dashboard(project)

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Dashboard is missing",
        )

    resources = read_project_resources(
        project
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context(
            request,
            project=project,
            state="dashboard",
            project_title=dashboard_project_title(
                source,
                project,
            ),
            dashboard_html=render_dashboard(
                source
            ),
            github_url=resources[
                "github_url"
            ],
            local_repo=resources[
                "local_repo"
            ],
        ),
    )


@app.get(
    "/project/{project}/edit",
    response_class=HTMLResponse,
)
def edit_project(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_configured(project)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context(
            request,
            project=project,
            project_title=project_title(project),
            state="editor",
            editor_files=editable_file_labels(),
        ),
    )


@app.get(
    "/api/projects/{project}/markdown",
)
def get_markdown_file(
    project: str,
    file: str,
) -> dict[str, object]:
    ensure_project_configured(project)

    try:
        return read_editable_markdown(
            project,
            file,
        )
    except EditableFileNotAllowed as exc:
        raise HTTPException(
            status_code=400,
            detail="File is not editable in Pocket",
        ) from exc
    except ProjectError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.put(
    "/api/projects/{project}/markdown",
)
def put_markdown_file(
    project: str,
    file: str,
    update: MarkdownUpdate,
) -> dict[str, object]:
    ensure_project_configured(project)

    try:
        write_editable_markdown(
            project,
            file,
            frontmatter=update.frontmatter,
            body=update.body,
            has_frontmatter=update.has_frontmatter,
        )
    except EditableFileNotAllowed as exc:
        raise HTTPException(
            status_code=400,
            detail="File is not editable in Pocket",
        ) from exc
    except ProjectError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "saved": True,
        "file": file,
    }


@app.post(
    "/api/projects/{project}/status-update",
)
def append_status_update(
    project: str,
    update: StatusUpdate,
) -> dict[str, object]:
    ensure_project_configured(project)

    line = " ".join(
        part.strip()
        for part in update.update.splitlines()
        if part.strip()
    ).strip()

    if not line:
        return {
            "saved": False,
            "update": "",
        }

    timestamp = _quick_entry_timestamp()
    project_store.create_activity(
        _ensure_project_store(project),
        {
            "id": str(uuid4()),
            "kind": "status",
            "title": line,
            "body": "",
            "url": "",
            "completed": False,
            "pinned": False,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )

    return {
        "saved": True,
        "update": line,
    }


def _quick_entry_timestamp() -> str:
    try:
        timezone = ZoneInfo(
            os.environ.get(
                "POCKET_TIMEZONE",
                "America/New_York",
            )
        )
    except Exception:
        timezone = ZoneInfo("UTC")

    return datetime.now(
        timezone
    ).strftime(
        "%m/%d/%Y %I:%M %p"
    )


def _normalized_entry_lines(
    text: str,
) -> list[str]:
    normalized = text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    lines = [
        line.rstrip()
        for line in normalized.split("\n")
    ]

    while lines and not lines[0].strip():
        lines.pop(0)

    while lines and not lines[-1].strip():
        lines.pop()

    return lines


def _format_quick_entry(
    kind: str,
    text: str,
) -> str:
    lines = _normalized_entry_lines(
        text
    )

    if not lines:
        raise HTTPException(
            status_code=400,
            detail="Entry cannot be empty",
        )

    content = "\n".join(lines).strip()

    timestamp = _quick_entry_timestamp()

    if kind == "status":
        prefix = "-"
    elif kind == "todo":
        prefix = "- [ ]"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unknown entry type",
        )

    first = lines[0].strip()

    entry = (
        f"{prefix} **{timestamp}**"
    )

    if first:
        entry += f" — {first}"

    for line in lines[1:]:
        entry += f"\n  {line}"

    return f"{entry}\n"


@app.post(
    "/api/projects/{project}/activity/{activity_id}/pin",
)
def set_activity_resource_pin(
    project: str,
    activity_id: str,
    update: ActivityPinUpdate,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)
    saved = project_store.set_pinned(
        root,
        activity_id,
        update.pinned,
        _quick_entry_timestamp(),
    )

    if not saved:
        raise HTTPException(
            status_code=404,
            detail="Pinnable activity item not found",
        )

    return {
        "saved": True,
        "id": activity_id,
        "pinned": update.pinned,
    }


@app.post(
    "/api/projects/{project}/quick-entry",
)
def add_quick_entry(
    project: str,
    entry: QuickEntry,
) -> dict[str, object]:
    ensure_project_configured(project)

    kind = entry.kind.strip().casefold()
    title = entry.title.strip()
    lines = _normalized_entry_lines(entry.text)
    content = "\n".join(lines).strip()

    if kind not in {"note", "todo", "status", "link"}:
        raise HTTPException(
            status_code=400,
            detail="Unknown entry type",
        )

    if not title:
        raise HTTPException(
            status_code=400,
            detail="A title is required",
        )

    if len(title) > 200:
        raise HTTPException(
            status_code=400,
            detail="Titles are limited to 200 characters",
        )

    if kind in {"note", "link"} and not content:
        raise HTTPException(
            status_code=400,
            detail=(
                "A link URL is required"
                if kind == "link"
                else "Note text is required"
            ),
        )

    url = ""

    if kind == "link":
        _label, url = _activity_entry_data(
            kind,
            content,
        )
        content = url

    timestamp = _quick_entry_timestamp()
    activity_id = str(uuid4())
    root = _ensure_project_store(project)
    project_store.create_activity(
        root,
        {
            "id": activity_id,
            "kind": kind,
            "title": title,
            "body": content,
            "url": url,
            "completed": False,
            "pinned": False,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )

    return {
        "saved": True,
        "id": activity_id,
        "kind": kind,
        "file": (
            project_store.database_path(root)
            .relative_to(root)
            .as_posix()
        ),
    }


def _project_file_relative_path(
    raw_path: str,
    *,
    markdown: bool = False,
) -> Path:
    value = raw_path.strip().replace("\\", "/")

    if not value:
        raise HTTPException(
            status_code=400,
            detail="A project-relative path is required",
        )

    supplied = Path(value)

    if supplied.parts and supplied.parts[0].casefold() == "files":
        supplied = Path(*supplied.parts[1:])

    relative = Path("files") / supplied

    if supplied.is_absolute() or not supplied.parts or any(
        part in {"", ".", ".."}
        or any(ord(character) < 32 or ord(character) == 127 for character in part)
        for part in supplied.parts
    ):
        raise HTTPException(
            status_code=400,
            detail="Use a safe path inside the project Local Folder",
        )

    if markdown and relative.suffix.casefold() not in {
        ".md",
        ".markdown",
    }:
        relative = relative.with_name(relative.name + ".md")

    if len(relative.as_posix()) > 500:
        raise HTTPException(
            status_code=400,
            detail="Project-relative paths are limited to 500 characters",
        )

    return relative


def _available_project_file(
    root: Path,
    relative: Path,
) -> Path:
    candidate = root / relative
    resolved_root = root.resolve()

    try:
        candidate.resolve().relative_to(resolved_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="File path leaves the project Local Folder",
        ) from exc

    if not candidate.exists():
        return candidate

    suffix = relative.suffix
    stem = (
        relative.name[:-len(suffix)]
        if suffix
        else relative.name
    )
    number = 2

    while True:
        candidate = (
            root
            / relative.parent
            / f"{stem}-{number}{suffix}"
        )

        try:
            candidate.resolve().relative_to(resolved_root)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="File path leaves the project Local Folder",
            ) from exc

        if not candidate.exists():
            return candidate

        number += 1


def _project_file_path(
    root: Path,
    raw_path: str,
) -> Path:
    relative = _project_file_relative_path(raw_path)
    path = (root / relative).resolve()

    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="File path leaves the project Local Folder",
        ) from exc

    return path


@app.post("/api/projects/{project}/files")
async def add_project_file(
    project: str,
    request: Request,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)
    form = await request.form()
    mode = str(form.get("mode", "upload")).strip().casefold()
    title = str(form.get("title", "")).strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="A title is required",
        )

    if len(title) > 200:
        raise HTTPException(
            status_code=400,
            detail="Titles are limited to 200 characters",
        )

    if mode == "markdown":
        source = str(form.get("markdown", ""))
        relative = _project_file_relative_path(
            str(form.get("path", "")),
            markdown=True,
        )
        destination = _available_project_file(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{uuid4().hex}.upload"

        try:
            temporary.write_text(source, encoding="utf-8")
            os.replace(temporary, destination)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="The Markdown file could not be saved",
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)
    elif mode == "upload":
        upload = form.get("upload")
        upload_name = str(getattr(upload, "filename", "") or "")

        if upload is None or not upload_name or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=400,
                detail="Choose a file to upload",
            )

        path_override = str(form.get("path", "")).strip()
        relative = _project_file_relative_path(path_override or upload_name)
        destination = _available_project_file(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{uuid4().hex}.upload"

        try:
            with temporary.open("wb") as output:
                while True:
                    chunk = await upload.read(1024 * 1024)

                    if not chunk:
                        break

                    output.write(chunk)

            os.replace(temporary, destination)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="The uploaded file could not be saved",
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)
    else:
        raise HTTPException(
            status_code=400,
            detail="Unknown file input mode",
        )

    relative_path = destination.relative_to(root).as_posix()
    file_url = (
        f"/api/projects/{quote(project, safe='')}/files/"
        f"{quote(relative_path, safe='/')}"
    )
    timestamp = _quick_entry_timestamp()
    activity_id = str(uuid4())
    project_store.create_activity(
        root,
        {
            "id": activity_id,
            "kind": "file",
            "title": title,
            "body": relative_path,
            "url": file_url,
            "completed": False,
            "pinned": False,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )

    return {
        "saved": True,
        "id": activity_id,
        "kind": "file",
        "file": relative_path,
        "url": file_url,
    }


@app.get("/api/projects/{project}/files/{file_path:path}")
def download_project_file(
    project: str,
    file_path: str,
) -> FileResponse:
    ensure_project_configured(project)
    root = _ensure_project_store(project)
    path = _project_file_path(root, file_path)

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return FileResponse(path, filename=path.name)


@app.post(
    "/api/projects/{project}/activity/{activity_id}/convert-to-file",
)
def convert_note_to_file(
    project: str,
    activity_id: str,
    conversion: NoteFileConversion,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)
    item = project_store.activity_item(root, activity_id)

    if item is None or str(item.get("kind", "")) != "note":
        raise HTTPException(
            status_code=404,
            detail="Note not found",
        )

    relative = _project_file_relative_path(
        conversion.path,
        markdown=True,
    )
    destination = _available_project_file(root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{uuid4().hex}.upload"

    try:
        temporary.write_text(str(item.get("body", "")), encoding="utf-8")
        os.replace(temporary, destination)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="The Note could not be converted to a file",
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)

    relative_path = destination.relative_to(root).as_posix()
    file_url = (
        f"/api/projects/{quote(project, safe='')}/files/"
        f"{quote(relative_path, safe='/')}"
    )
    converted = project_store.convert_note_to_file(
        root,
        activity_id,
        relative_path,
        file_url,
        _quick_entry_timestamp(),
    )

    if not converted:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="The Note changed before it could be converted",
        )

    return {
        "saved": True,
        "id": activity_id,
        "kind": "file",
        "file": relative_path,
        "url": file_url,
    }


@app.delete(
    "/api/projects/{project}/activity/{activity_id}",
)
def delete_activity_item(
    project: str,
    activity_id: str,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)
    deleted = project_store.soft_delete(
        root,
        activity_id,
        _quick_entry_timestamp(),
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Activity item not found",
        )

    return {
        "saved": True,
        "deleted": True,
        "id": activity_id,
    }


@app.post(
    "/api/projects/{project}/about",
)
def update_project_about(
    project: str,
    update: ProjectAboutUpdate,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)
    profile = {
        "what": update.what.strip(),
        "why": update.why.strip(),
        "class": update.class_name.strip(),
    }
    project_store.update_project_profile(
        root,
        profile,
        _quick_entry_timestamp(),
    )
    project_store.update_project_settings(
        root,
        {"class": profile["class"]},
        _quick_entry_timestamp(),
    )

    return {
        "saved": True,
        "profile": profile,
    }


@app.get("/api/system/chat/models")
def system_chat_models() -> dict[str, object]:
    try:
        models = project_chat.available_models()
    except project_chat.ModelServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    configured = project_chat.configured_model()

    if configured and configured not in models:
        models.insert(0, configured)

    return {
        "models": models,
        "default": configured or (models[0] if models else ""),
    }


@app.get("/api/system/chat/messages")
def system_chat_messages() -> dict[str, object]:
    return {
        "messages": [
            _chat_message_payload(message)
            for message in system_store.list_chat_messages(limit=100)
        ],
    }


@app.post("/api/system/chat/messages")
def send_system_chat_message(
    request: ProjectChatRequest,
) -> dict[str, object]:
    message = request.message.strip()
    model = request.model.strip() or project_chat.configured_model()

    if not message:
        raise HTTPException(status_code=400, detail="Enter a message")

    if len(message) > 12_000:
        raise HTTPException(
            status_code=400,
            detail="Messages are limited to 12,000 characters",
        )

    try:
        history = system_store.list_chat_messages(limit=23)
        history.append({"role": "user", "content": message})
        chat_result = system_chat.complete_system_chat(
            model,
            history,
            _system_chat_catalog(),
        )
    except (ProjectError, DuckSettingsError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except project_chat.ModelServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    timestamp = _quick_entry_timestamp()
    user_message = {
        "id": str(uuid4()),
        "role": "user",
        "content": message,
        "model": model,
        "created_at": timestamp,
    }
    assistant_message = {
        "id": str(uuid4()),
        "role": "assistant",
        "content": chat_result.content,
        "model": model,
        "created_at": timestamp,
    }
    system_store.add_chat_message(user_message)
    system_store.add_chat_message(assistant_message)

    return {
        "user_message": _chat_message_payload(user_message),
        "assistant_message": _chat_message_payload(assistant_message),
        "context": {
            "project_count": chat_result.project_count,
            "tool_calls": chat_result.tool_calls,
            "accessed_projects": list(chat_result.accessed_projects),
        },
    }


@app.delete("/api/system/chat/messages")
def clear_system_chat() -> dict[str, object]:
    return {"deleted": system_store.clear_chat_messages()}


@app.get(
    "/api/projects/{project}/chat/models",
)
def project_chat_models(
    project: str,
) -> dict[str, object]:
    ensure_project_configured(project)

    try:
        models = project_chat.available_models()
    except project_chat.ModelServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    configured = project_chat.configured_model()

    if configured and configured not in models:
        models.insert(0, configured)

    return {
        "models": models,
        "default": configured or (models[0] if models else ""),
    }


@app.get(
    "/api/projects/{project}/chat/messages",
)
def project_chat_messages(
    project: str,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)

    return {
        "messages": [
            _chat_message_payload(message)
            for message in project_store.list_chat_messages(
                root,
                limit=100,
            )
        ],
    }


@app.post(
    "/api/projects/{project}/chat/messages",
)
def send_project_chat_message(
    project: str,
    request: ProjectChatRequest,
) -> dict[str, object]:
    ensure_project_configured(project)
    message = request.message.strip()
    model = request.model.strip() or project_chat.configured_model()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Enter a message",
        )

    if len(message) > 12_000:
        raise HTTPException(
            status_code=400,
            detail="Messages are limited to 12,000 characters",
        )

    root = _ensure_project_store(project)

    try:
        history = project_store.list_chat_messages(
            root,
            limit=23,
        )
        history.append(
            {
                "role": "user",
                "content": message,
            }
        )
        chat_result = project_chat.complete_project_chat(
            model,
            history,
            root,
        )
    except project_chat.ModelServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    timestamp = _quick_entry_timestamp()
    user_message = {
        "id": str(uuid4()),
        "role": "user",
        "content": message,
        "model": model,
        "created_at": timestamp,
    }
    assistant_message = {
        "id": str(uuid4()),
        "role": "assistant",
        "content": chat_result.content,
        "model": model,
        "created_at": timestamp,
    }
    project_store.add_chat_message(root, user_message)
    project_store.add_chat_message(root, assistant_message)

    return {
        "user_message": _chat_message_payload(user_message),
        "assistant_message": _chat_message_payload(assistant_message),
        "context": {
            "available_files": chat_result.available_files,
            "skipped_files": chat_result.skipped_files,
            "readable_characters": chat_result.readable_characters,
            "tool_calls": chat_result.tool_calls,
            "accessed_files": list(chat_result.accessed_files),
        },
    }


@app.delete(
    "/api/projects/{project}/chat/messages",
)
def clear_project_chat(
    project: str,
) -> dict[str, object]:
    ensure_project_configured(project)
    root = _ensure_project_store(project)

    return {
        "deleted": project_store.clear_chat_messages(root),
    }


@app.get(
    "/project/{project}/configure",
    response_class=HTMLResponse,
)
def configure_form(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_exists(project)

    if is_configured(project):
        return RedirectResponse(
            url=(
                f"/project/"
                f"{quote(project, safe='')}"
            ),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context(
            request,
            project=project,
            state="configure",
        ),
    )


@app.post(
    "/project/{project}/configure",
    response_class=HTMLResponse,
)
async def configure_project(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_exists(project)

    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="replace",
    )

    parsed = parse_qs(
        body,
        keep_blank_values=True,
    )

    def field(
        name: str,
    ) -> str:
        values = parsed.get(
            name,
            [""],
        )

        return values[-1].strip()

    try:
        initialize_project(
            project,
            project=field(
                "project_name"
            ),
            score=field(
                "score"
            ),
            canonical=field(
                "canonical"
            ),
            url=field(
                "url"
            ),
            chatgpt_url=field(
                "chatgpt_url"
            ),
            repo_url=field(
                "repo_url"
            ),
            local_repo=field(
                "local_repo"
            ),
            custom_1_title=field(
                "custom_1_title"
            ),
            custom_1_content=field(
                "custom_1_content"
            ),
            custom_2_title=field(
                "custom_2_title"
            ),
            custom_2_content=field(
                "custom_2_content"
            ),
            custom_3_title=field(
                "custom_3_title"
            ),
            custom_3_content=field(
                "custom_3_content"
            ),
        )
    except ProjectAlreadyConfigured:
        return RedirectResponse(
            url=(
                f"/project/"
                f"{quote(project, safe='')}"
            ),
            status_code=303,
        )
    except ProjectError as exc:
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context=context(
                request,
                project=project,
                state="configure",
                error=str(exc),
            ),
            status_code=400,
        )

    return RedirectResponse(
        url=(
            f"/project/"
            f"{quote(project, safe='')}"
        ),
        status_code=303,
    )

# ============================================================
# DUCK SETTINGS SUBSYSTEM ROUTES
# ============================================================

_DUCK_VOCABULARY_FIELDS = (
    {
        "key": "statuses",
        "label": "Available Statuses",
    },
    {
        "key": "categories",
        "label": "Available Categories",
    },
    {
        "key": "priorities",
        "label": "Available Priorities",
    },
    {
        "key": "classes",
        "label": "Available Classes",
    },
    {
        "key": "types",
        "label": "Available Types",
    },
)

_DUCK_PROMPT_FIELDS = (
    {
        "key": "current_state",
        "label": "Current State Prompt",
    },
    {
        "key": "next_action",
        "label": "Next Action Prompt",
    },
    {
        "key": "unresolved_decisions",
        "label": "Unresolved Decisions Prompt",
    },
    {
        "key": "milestone_definition",
        "label": "Milestone Definition Prompt",
    },
)

_DUCK_PROJECT_FIELD_LABELS = {
    "status": "Status",
    "category": "Category",
    "priority": "Priority",
    "class": "Class",
    "type": "Type",
}


def _duck_form_field(
    parsed: dict[str, list[str]],
    name: str,
) -> str:
    values = parsed.get(
        name,
        [""],
    )

    return values[-1]


def _duck_form_lines(
    parsed: dict[str, list[str]],
    name: str,
) -> list[str]:
    value = _duck_form_field(
        parsed,
        name,
    )

    return value.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).split(
        "\n"
    )


def _duck_system_settings_context(
    request: Request,
    *,
    error: str | None = None,
) -> dict[str, object]:
    return {
        "request": request,
        "settings": load_system_settings(),
        "vocabulary_fields": (
            _DUCK_VOCABULARY_FIELDS
        ),
        "prompt_fields": (
            _DUCK_PROMPT_FIELDS
        ),
        "saved": (
            request.query_params.get(
                "saved"
            )
            == "1"
        ),
        "error": error,
    }


@app.get(
    "/settings",
    response_class=HTMLResponse,
)
def duck_system_settings_page(
    request: Request,
) -> HTMLResponse:
    try:
        page_context = (
            _duck_system_settings_context(
                request
            )
        )
    except DuckSettingsError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context=page_context,
    )


@app.post(
    "/settings",
    response_class=HTMLResponse,
)
async def save_duck_system_settings(
    request: Request,
) -> HTMLResponse:
    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="replace",
    )

    parsed = parse_qs(
        body,
        keep_blank_values=True,
    )

    vocabularies = {
        key: _duck_form_lines(
            parsed,
            f"vocabulary_{key}",
        )
        for key in VOCABULARY_KEYS
    }

    prompts = {
        key: _duck_form_field(
            parsed,
            f"prompt_{key}",
        )
        for key in PROMPT_KEYS
    }

    try:
        save_system_settings(
            vocabularies=vocabularies,
            prompts=prompts,
        )
    except DuckSettingsError as exc:
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context=(
                _duck_system_settings_context(
                    request,
                    error=str(exc),
                )
            ),
            status_code=400,
        )

    return RedirectResponse(
        url="/settings?saved=1",
        status_code=303,
    )


def _duck_project_settings_context(
    request: Request,
    project: str,
    *,
    error: str | None = None,
) -> dict[str, object]:
    system_settings = (
        load_system_settings()
    )

    stored_settings = project_store.project_settings(
        _ensure_project_store(project)
    )
    current_settings = {
        key: stored_settings.get(key, "")
        for key in PROJECT_QUALIFIER_KEYS
    }

    project_fields: list[
        dict[str, object]
    ] = []

    for key in PROJECT_QUALIFIER_KEYS:
        vocabulary_key = (
            QUALIFIER_VOCABULARIES[key]
        )

        options = list(
            system_settings[
                "vocabularies"
            ][vocabulary_key]
        )

        current = current_settings.get(
            key,
            "",
        )

        if current and current not in options:
            options.insert(
                0,
                current,
            )

        project_fields.append(
            {
                "key": key,
                "label": (
                    _DUCK_PROJECT_FIELD_LABELS[
                        key
                    ]
                ),
                "current": current,
                "options": options,
            }
        )

    return {
        "request": request,
        "project": project,
        "project_title": (
            project_title(project)
        ),
        "project_fields": project_fields,
        "saved": (
            request.query_params.get(
                "saved"
            )
            == "1"
        ),
        "error": error,
        "quote": quote,
    }


@app.get(
    "/project/{project}/settings",
    response_class=HTMLResponse,
)
def duck_project_settings_page(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_configured(project)

    try:
        page_context = (
            _duck_project_settings_context(
                request,
                project,
            )
        )
    except DuckSettingsError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="project_settings.html",
        context=page_context,
    )


@app.post(
    "/project/{project}/settings",
    response_class=HTMLResponse,
)
async def save_duck_project_settings(
    request: Request,
    project: str,
) -> HTMLResponse:
    ensure_project_configured(project)

    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="replace",
    )

    parsed = parse_qs(
        body,
        keep_blank_values=True,
    )

    values = {
        key: _duck_form_field(
            parsed,
            key,
        )
        for key in PROJECT_QUALIFIER_KEYS
    }

    root = _ensure_project_store(project)
    timestamp = _quick_entry_timestamp()
    project_store.update_project_settings(
        root,
        values,
        timestamp,
    )

    if "class" in values:
        profile = project_store.project_profile(root)
        profile["class"] = values["class"]
        project_store.update_project_profile(
            root,
            profile,
            timestamp,
        )

    return RedirectResponse(
        url=(
            f"/project/"
            f"{quote(project, safe='')}"
            f"/settings?saved=1"
        ),
        status_code=303,
    )


@app.put(
    "/api/projects/{project}/session-values",
)
def update_duck_session_values(
    project: str,
    update: SessionValuesUpdate,
) -> dict[str, object]:
    ensure_project_configured(project)

    try:
        values = save_session_values(
            project,
            {
                key: getattr(
                    update,
                    key,
                )
                for key in SESSION_VALUE_KEYS
            },
        )
    except DuckSettingsError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "saved": True,
        "values": values,
    }
