from __future__ import annotations

import os
import re
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
    project_summaries,
    read_dashboard,
    read_project_resources,
    read_editable_markdown,
    touch_project,
    write_editable_markdown,
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
    text: str = ""


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
            project_qualifiers = (
                load_project_settings(project)
            )
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
        context=context(request),
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

    try:
        current = read_editable_markdown(
            project,
            "status.md",
        )

        body = str(
            current["body"]
        )

        body = body.rstrip()

        if body:
            body += "\n\n"

        try:
            timezone = ZoneInfo(
                os.environ.get(
                    "POCKET_TIMEZONE",
                    "America/New_York",
                )
            )
        except Exception:
            timezone = ZoneInfo("UTC")

        timestamp = datetime.now(
            timezone
        ).strftime(
            "%m/%d/%Y %I:%M %p"
        )

        body += (
            f"- **{timestamp}** — "
            f"{line}\n"
        )

        write_editable_markdown(
            project,
            "status.md",
            frontmatter=str(
                current["frontmatter"]
            ),
            body=body,
            has_frontmatter=bool(
                current["has_frontmatter"]
            ),
        )
    except ProjectError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

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
    "/api/projects/{project}/quick-entry",
)
def add_quick_entry(
    project: str,
    entry: QuickEntry,
) -> dict[str, object]:
    ensure_project_configured(project)

    kind = entry.kind.strip().casefold()

    if kind == "status":
        file_label = "status.md"
    elif kind == "todo":
        file_label = "inbox.md"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unknown entry type",
        )

    formatted = _format_quick_entry(
        kind,
        entry.text,
    )

    try:
        current = read_editable_markdown(
            project,
            file_label,
        )

        body = str(
            current["body"]
        ).rstrip()

        if body:
            body += "\n\n"

        body += formatted

        write_editable_markdown(
            project,
            file_label,
            frontmatter=str(
                current["frontmatter"]
            ),
            body=body,
            has_frontmatter=bool(
                current["has_frontmatter"]
            ),
        )
    except ProjectError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "saved": True,
        "kind": kind,
        "file": file_label,
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

    current_settings = (
        load_project_settings(project)
    )

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

    try:
        save_project_settings(
            project,
            values,
        )
    except DuckSettingsError as exc:
        return templates.TemplateResponse(
            request=request,
            name="project_settings.html",
            context=(
                _duck_project_settings_context(
                    request,
                    project,
                    error=str(exc),
                )
            ),
            status_code=400,
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
