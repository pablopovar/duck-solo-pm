from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from pydantic import BaseModel

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

app = FastAPI(title="Door to Pocket")

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
        "error": error,
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
