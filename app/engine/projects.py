from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined


ENGINE_DIR = Path(__file__).resolve().parent
SKELETON_DIR = ENGINE_DIR.parent / "templates" / "init" / "skeleton"

PROJECTS_ROOT = Path(
    os.environ.get(
        "PROJECTS_ROOT",
        "/data/projects",
    )
).expanduser()

PROJECTS_HOST_PATH = Path(
    os.environ.get(
        "PROJECTS_HOST_PATH",
        "../../ai-observer/projects",
    )
).expanduser()

POCKET_HOST_APP_ROOT = Path(
    os.environ.get(
        "POCKET_HOST_APP_ROOT",
        ".",
    )
).expanduser()

POCKET_TIMEZONE = os.environ.get(
    "POCKET_TIMEZONE",
    "America/New_York",
)

EDITABLE_MARKDOWN_FILES: dict[str, Path] = {
    "config.md": Path(".duck/config.md"),
    "dashboard.md": Path(".duck/dashboard.md"),
    "inbox.md": Path("inbox.md"),
    "manifesto.md": Path(".duck/manifesto.md"),
    "status.md": Path(".duck/status.md"),
    "canvas.md": Path("canvas.md"),
}

PROJECT_SYSTEM_DIRECTORY = ".duck"
LEGACY_PROJECT_SYSTEM_DIRECTORY = ".pocket"

_FRONTMATTER = re.compile(
    r"\A---[ \t]*\n(?P<frontmatter>.*?)\n---[ \t]*(?:\n|\Z)(?P<body>.*)\Z",
    re.DOTALL,
)


class ProjectError(Exception):
    pass


class ProjectNotFound(ProjectError):
    pass


class ProjectAlreadyConfigured(ProjectError):
    pass


class EditableFileNotAllowed(ProjectError):
    pass


def projects_root() -> Path:
    root = PROJECTS_ROOT.resolve()

    if not root.exists() or not root.is_dir():
        raise ProjectError(
            f"PROJECTS_ROOT does not exist or is not a directory: {root}"
        )

    return root


def visible_projects() -> list[str]:
    root = projects_root()

    return [
        entry.name
        for entry in os.scandir(root)
        if entry.is_dir() and not entry.name.startswith(".")
    ]


def project_root(project: str) -> Path:
    if (
        not project
        or Path(project).name != project
        or project.startswith(".")
    ):
        raise ProjectNotFound(project)

    root = projects_root()
    candidate = (root / project).resolve()

    if candidate.parent != root or not candidate.is_dir():
        raise ProjectNotFound(project)

    return candidate


def canonical_project_system_root(project: str) -> Path:
    return project_root(project) / PROJECT_SYSTEM_DIRECTORY


def legacy_project_system_root(project: str) -> Path:
    return project_root(project) / LEGACY_PROJECT_SYSTEM_DIRECTORY


def project_system_root(project: str) -> Path:
    """Return canonical state, falling back to unmigrated legacy state."""
    canonical = canonical_project_system_root(project)
    legacy = legacy_project_system_root(project)

    if canonical.exists() or not legacy.exists():
        return canonical

    return legacy


def project_state_status(project: str) -> dict[str, object]:
    canonical = canonical_project_system_root(project)
    legacy = legacy_project_system_root(project)
    canonical_exists = canonical.exists()
    legacy_exists = legacy.exists()

    return {
        "directory": (
            PROJECT_SYSTEM_DIRECTORY
            if canonical_exists or not legacy_exists
            else LEGACY_PROJECT_SYSTEM_DIRECTORY
        ),
        "legacy": legacy_exists and not canonical_exists,
        "conflict": legacy_exists and canonical_exists,
        "legacy_is_symlink": legacy.is_symlink(),
    }


def migrate_project_state(project: str) -> Path:
    canonical = canonical_project_system_root(project)
    legacy = legacy_project_system_root(project)

    if canonical.exists():
        if legacy.exists() or legacy.is_symlink():
            raise ProjectError(
                "Both .duck and .pocket exist. Resolve the conflict manually."
            )
        return canonical

    if legacy.is_symlink():
        raise ProjectError(
            ".pocket is a symbolic link. Resolve it manually before migration."
        )

    if not legacy.is_dir():
        raise ProjectError("No legacy .pocket directory was found.")

    try:
        legacy.rename(canonical)
    except OSError as exc:
        raise ProjectError(
            f"Could not migrate .pocket to .duck: {exc}"
        ) from exc

    return canonical


def pocket_root(project: str) -> Path:
    """Compatibility name for older callers; returns active Duck state."""
    return project_system_root(project)


def project_score(project: str) -> int:
    path = pocket_root(project) / "config.md"

    if not path.is_file():
        return 0

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    match = re.search(
        r"(?m)^score:[ \t]*(\d{1,3})[ \t]*$",
        source,
    )

    if match is None:
        return 0

    score = int(match.group(1))

    if not 0 <= score <= 100:
        return 0

    return score


def project_last_opened(project: str) -> int:
    path = (
        pocket_root(project)
        / "runtime"
        / "last-opened"
    )

    try:
        # Milliseconds remain exactly representable in JavaScript.
        return path.stat().st_mtime_ns // 1_000_000
    except FileNotFoundError:
        return 0


def touch_project(project: str) -> None:
    path = (
        pocket_root(project)
        / "runtime"
        / "last-opened"
    )

    try:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.touch(
            exist_ok=True,
        )
    except OSError as exc:
        raise ProjectError(
            f"Could not update project recency: {project}"
        ) from exc


def project_summaries() -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "score": project_score(name),
            "last_opened": project_last_opened(name),
        }
        for name in visible_projects()
    ]


def is_configured(project: str) -> bool:
    return (pocket_root(project) / "config.md").is_file()


def dashboard_path(project: str) -> Path:
    return pocket_root(project) / "dashboard.md"


def read_dashboard(project: str) -> str | None:
    path = dashboard_path(project)

    if not path.is_file():
        return None

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _config_frontmatter_value(
    source: str,
    key: str,
) -> str:
    match = _FRONTMATTER.match(source)

    if match is None:
        return ""

    pattern = re.compile(
        rf"^{re.escape(key)}:[ \\t]*(.*)$",
        re.MULTILINE,
    )

    value_match = pattern.search(
        match.group("frontmatter")
    )

    if value_match is None:
        return ""

    raw = value_match.group(1).strip()

    if not raw:
        return ""

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        decoded = raw

        if (
            len(decoded) >= 2
            and decoded[0] == decoded[-1]
            and decoded[0] in {'"', "'"}
        ):
            decoded = decoded[1:-1]

    if not isinstance(decoded, str):
        return str(decoded)

    return decoded.strip()


def read_project_resources(
    project: str,
) -> dict[str, str]:
    path = pocket_root(project) / "config.md"

    if not path.is_file():
        return {
            "github_url": "",
            "local_repo": "",
        }

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    github_url = _config_frontmatter_value(
        source,
        "repo",
    )

    if not github_url.startswith(
        (
            "https://",
            "http://",
        )
    ):
        github_url = ""

    return {
        "github_url": github_url,
        "local_repo": _config_frontmatter_value(
            source,
            "local_repo",
        ),
    }


def editable_file_labels() -> list[str]:
    return list(EDITABLE_MARKDOWN_FILES)


def editable_markdown_path(
    project: str,
    label: str,
) -> Path:
    relative = EDITABLE_MARKDOWN_FILES.get(label)

    if relative is None:
        raise EditableFileNotAllowed(label)

    base = project_root(project)
    if relative.parts and relative.parts[0] == PROJECT_SYSTEM_DIRECTORY:
        candidate = (
            project_system_root(project)
            / Path(*relative.parts[1:])
        ).resolve()
    else:
        candidate = (base / relative).resolve()

    if not candidate.is_relative_to(base):
        raise EditableFileNotAllowed(label)

    return candidate


def split_markdown(source: str) -> tuple[str, str, bool]:
    match = _FRONTMATTER.match(source)

    if match is None:
        return "", source, False

    return (
        match.group("frontmatter"),
        match.group("body"),
        True,
    )


def read_editable_markdown(
    project: str,
    label: str,
) -> dict[str, object]:
    path = editable_markdown_path(project, label)

    if not path.is_file():
        raise ProjectError(
            f"Editable file is missing: {label}"
        )

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    frontmatter, body, has_frontmatter = split_markdown(source)

    return {
        "file": label,
        "frontmatter": frontmatter,
        "body": body,
        "has_frontmatter": has_frontmatter,
    }


def write_editable_markdown(
    project: str,
    label: str,
    *,
    frontmatter: str,
    body: str,
    has_frontmatter: bool,
) -> None:
    path = editable_markdown_path(project, label)

    if not path.is_file():
        raise ProjectError(
            f"Editable file is missing: {label}"
        )

    normalized_body = body

    if normalized_body and not normalized_body.endswith("\n"):
        normalized_body += "\n"

    normalized_frontmatter = frontmatter.strip("\n")

    if label == "canvas.md":
        has_frontmatter = False
        normalized_frontmatter = ""

    if has_frontmatter:
        frontmatter_block = "---\n"

        if normalized_frontmatter:
            frontmatter_block += f"{normalized_frontmatter}\n"

        source = (
            f"{frontmatter_block}"
            "---\n\n"
            f"{normalized_body}"
        )
    else:
        source = normalized_body

    path.write_text(
        source,
        encoding="utf-8",
    )


def _host_projects_root() -> Path:
    path = PROJECTS_HOST_PATH

    if not path.is_absolute():
        path = POCKET_HOST_APP_ROOT / path

    return path.resolve(strict=False)


def _started_date() -> str:
    try:
        timezone = ZoneInfo(POCKET_TIMEZONE)
    except Exception:
        timezone = ZoneInfo("UTC")

    return datetime.now(timezone).strftime("%m/%d/%Y")


def _template_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(SKELETON_DIR)),
        autoescape=False,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def initialize_project(
    folder: str,
    *,
    project: str,
    score: str | int,
    canonical: str,
    url: str,
    chatgpt_url: str,
    repo_url: str,
    local_repo: str,
    custom_1_title: str,
    custom_1_content: str,
    custom_2_title: str,
    custom_2_content: str,
    custom_3_title: str,
    custom_3_content: str,
) -> list[str]:
    base = project_root(folder)

    config_path = base / ".duck" / "config.md"
    legacy_config_path = base / ".pocket" / "config.md"

    if config_path.exists() or legacy_config_path.exists():
        raise ProjectAlreadyConfigured(folder)

    try:
        score_value = int(score or 0)
    except (TypeError, ValueError) as exc:
        raise ProjectError(
            "Score must be an integer from 0 to 100"
        ) from exc

    if not 0 <= score_value <= 100:
        raise ProjectError(
            "Score must be an integer from 0 to 100"
        )

    values = {
        "folder": folder,
        "project": project.strip() or folder,
        "score": score_value,
        "root": f"/projects/{folder}",
        "project_folder_reference": f"$ROOT/projects/{folder}",
        "local_path": str(_host_projects_root() / folder),
        "canonical": canonical.strip(),
        "url": url.strip(),
        "chatgpt_url": chatgpt_url.strip(),
        "repo_url": repo_url.strip(),
        "local_repo": local_repo.strip(),
        "custom_1_title": custom_1_title.strip(),
        "custom_1_content": custom_1_content.strip(),
        "custom_2_title": custom_2_title.strip(),
        "custom_2_content": custom_2_content.strip(),
        "custom_3_title": custom_3_title.strip(),
        "custom_3_content": custom_3_content.strip(),
        "started": _started_date(),
        "manifesto": ".duck/manifesto.md",
    }

    environment = _template_environment()

    template_names = [
        ".pocket/dashboard.md",
        ".pocket/decisions.md",
        "inbox.md",
        ".pocket/manifesto.md",
        ".pocket/status.md",
        ".pocket/stream.md",
        "canvas.md",
        ".pocket/config.md",
    ]

    rendered = {
        template_name: environment
        .get_template(template_name)
        .render(**values)
        .replace(".pocket/", ".duck/")
        for template_name in template_names
    }

    created: list[str] = []

    # .duck/config.md is written last so an incomplete
    # initialization does not appear configured.
    for template_name in template_names:
        destination_name = template_name.replace(
            ".pocket/",
            ".duck/",
            1,
        )
        destination = base / destination_name

        if destination.exists():
            continue

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination.write_text(
            rendered[template_name],
            encoding="utf-8",
        )

        created.append(destination_name)

    return created
