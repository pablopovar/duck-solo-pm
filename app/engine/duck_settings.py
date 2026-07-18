from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.engine import projects as project_engine


VOCABULARY_KEYS = (
    "statuses",
    "categories",
    "priorities",
    "classes",
    "types",
)

PROMPT_KEYS = (
    "current_state",
    "next_action",
    "unresolved_decisions",
    "milestone_definition",
)

PROJECT_QUALIFIER_KEYS = (
    "status",
    "category",
    "priority",
    "class",
    "type",
)

SESSION_VALUE_KEYS = (
    "current_state",
    "next_action",
    "unresolved_decisions",
    "milestone_definition",
)

QUALIFIER_VOCABULARIES = {
    "status": "statuses",
    "category": "categories",
    "priority": "priorities",
    "class": "classes",
    "type": "types",
}


class DuckSettingsError(Exception):
    pass


def _default_system_settings() -> dict[str, Any]:
    return {
        "version": 1,
        "vocabularies": {
            key: []
            for key in VOCABULARY_KEYS
        },
        "prompts": {
            key: ""
            for key in PROMPT_KEYS
        },
    }


def _default_project_settings() -> dict[str, str]:
    return {
        key: ""
        for key in PROJECT_QUALIFIER_KEYS
    }


def _default_session_values() -> dict[str, str]:
    return {
        key: ""
        for key in SESSION_VALUE_KEYS
    }


def system_settings_path() -> Path:
    return (
        project_engine.projects_root()
        / ".duck"
        / "settings.json"
    )


def project_settings_path(
    project: str,
) -> Path:
    return (
        project_engine.project_system_root(project)
        / "project-settings.json"
    )


def session_values_path(
    project: str,
) -> Path:
    return (
        project_engine.project_system_root(project)
        / "session-values.json"
    )


def _read_json(
    path: Path,
) -> dict[str, Any]:
    try:
        raw = path.read_text(
            encoding="utf-8"
        )
        result = json.loads(raw)
    except FileNotFoundError:
        return {}
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise DuckSettingsError(
            f"Could not read {path}: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise DuckSettingsError(
            f"Expected a JSON object in {path}"
        )

    return result


def _atomic_write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f".{path.name}.tmp"
    )

    payload = json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    try:
        temporary.write_text(
            payload,
            encoding="utf-8",
        )
        os.replace(
            temporary,
            path,
        )
    except OSError as exc:
        try:
            temporary.unlink(
                missing_ok=True
            )
        except OSError:
            pass

        raise DuckSettingsError(
            f"Could not write {path}: {exc}"
        ) from exc


def normalize_options(
    values: list[str],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = value.strip()

        if not cleaned:
            continue

        identity = cleaned.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        normalized.append(cleaned)

    return normalized


def load_system_settings() -> dict[str, Any]:
    defaults = _default_system_settings()
    stored = _read_json(
        system_settings_path()
    )

    vocabularies = stored.get(
        "vocabularies",
        {},
    )

    if not isinstance(
        vocabularies,
        dict,
    ):
        vocabularies = {}

    prompts = stored.get(
        "prompts",
        {},
    )

    if not isinstance(
        prompts,
        dict,
    ):
        prompts = {}

    result = _default_system_settings()

    for key in VOCABULARY_KEYS:
        values = vocabularies.get(
            key,
            [],
        )

        if not isinstance(values, list):
            values = []

        result["vocabularies"][key] = (
            normalize_options(
                [
                    value
                    for value in values
                    if isinstance(value, str)
                ]
            )
        )

    for key in PROMPT_KEYS:
        value = prompts.get(
            key,
            "",
        )

        result["prompts"][key] = (
            value
            if isinstance(value, str)
            else ""
        )

    return result


def save_system_settings(
    *,
    vocabularies: dict[str, list[str]],
    prompts: dict[str, str],
) -> dict[str, Any]:
    result = _default_system_settings()

    for key in VOCABULARY_KEYS:
        result["vocabularies"][key] = (
            normalize_options(
                vocabularies.get(
                    key,
                    [],
                )
            )
        )

    for key in PROMPT_KEYS:
        value = prompts.get(
            key,
            "",
        )

        result["prompts"][key] = (
            value
            if isinstance(value, str)
            else ""
        )

    _atomic_write_json(
        system_settings_path(),
        result,
    )

    return result


def load_project_settings(
    project: str,
) -> dict[str, str]:
    result = _default_project_settings()
    stored = _read_json(
        project_settings_path(project)
    )

    for key in PROJECT_QUALIFIER_KEYS:
        value = stored.get(
            key,
            "",
        )

        if isinstance(value, str):
            result[key] = value.strip()

    return result


def save_project_settings(
    project: str,
    values: dict[str, str],
) -> dict[str, str]:
    system = load_system_settings()
    result = _default_project_settings()

    for key in PROJECT_QUALIFIER_KEYS:
        value = values.get(
            key,
            "",
        ).strip()

        vocabulary_key = (
            QUALIFIER_VOCABULARIES[key]
        )

        available = system[
            "vocabularies"
        ][vocabulary_key]

        if value and value not in available:
            raise DuckSettingsError(
                f"{value!r} is not an available "
                f"{key} value"
            )

        result[key] = value

    _atomic_write_json(
        project_settings_path(project),
        result,
    )

    return result


def load_session_values(
    project: str,
) -> dict[str, str]:
    result = _default_session_values()
    stored = _read_json(
        session_values_path(project)
    )

    for key in SESSION_VALUE_KEYS:
        value = stored.get(
            key,
            "",
        )

        if isinstance(value, str):
            result[key] = value

    return result


def save_session_values(
    project: str,
    values: dict[str, str],
) -> dict[str, str]:
    result = _default_session_values()

    for key in SESSION_VALUE_KEYS:
        value = values.get(
            key,
            "",
        )

        result[key] = (
            value
            if isinstance(value, str)
            else ""
        )

    _atomic_write_json(
        session_values_path(project),
        result,
    )

    return result
