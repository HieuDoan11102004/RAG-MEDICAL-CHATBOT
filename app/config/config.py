"""Validated application configuration loaded from the repository root."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_KEYS = frozenset(
    {
        "openai_model",
        "openai_embedding_model",
        "db_faiss_path",
        "data_path",
        "chunk_size",
        "chunk_overlap",
    }
)
_ENVIRONMENT_KEYS = {
    "openai_model": "OPENAI_MODEL",
    "openai_embedding_model": "OPENAI_EMBEDDING_MODEL",
    "db_faiss_path": "DB_FAISS_PATH",
    "data_path": "DATA_PATH",
    "chunk_size": "CHUNK_SIZE",
    "chunk_overlap": "CHUNK_OVERLAP",
}


class ConfigurationError(ValueError):
    """Raised when application configuration is missing or invalid."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found non-string key {key!r}",
                key_node.start_mark,
            )
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True)
class Settings:
    openai_model: str
    openai_embedding_model: str
    db_faiss_path: Path
    data_path: Path
    chunk_size: int
    chunk_overlap: int


def _read_yaml(config_path: Path) -> dict[str, Any]:
    try:
        with config_path.open(encoding="utf-8") as config_file:
            document = yaml.load(config_file, Loader=_UniqueKeySafeLoader)
    except OSError as exc:
        raise ConfigurationError(f"Unable to read configuration file {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in configuration file {config_path}: {exc}") from exc

    if document is None:
        raise ConfigurationError(f"Configuration file {config_path} is empty.")
    if not isinstance(document, dict):
        raise ConfigurationError(f"Configuration file {config_path} must contain a mapping.")

    actual_keys = set(document)
    missing_keys = _CONFIG_KEYS - actual_keys
    unknown_keys = actual_keys - _CONFIG_KEYS
    if missing_keys:
        raise ConfigurationError(
            "Configuration is missing required key(s): " + ", ".join(sorted(missing_keys))
        )
    if unknown_keys:
        raise ConfigurationError(
            "Configuration contains unknown key(s): "
            + ", ".join(sorted(map(str, unknown_keys)))
        )
    return document


def _dotenv_values(dotenv_path: Path | None) -> Mapping[str, str | None]:
    if dotenv_path is None or not dotenv_path.is_file():
        return {}
    try:
        return dotenv_values(dotenv_path)
    except OSError as exc:
        raise ConfigurationError(f"Unable to read dotenv file {dotenv_path}: {exc}") from exc


def _resolve_value(
    field: str,
    yaml_values: Mapping[str, Any],
    dotenv: Mapping[str, str | None],
    environ: Mapping[str, str],
) -> tuple[Any, bool]:
    environment_key = _ENVIRONMENT_KEYS[field]
    if environment_key in environ:
        return environ[environment_key], True
    if environment_key in dotenv and dotenv[environment_key] is not None:
        return dotenv[environment_key], True
    return yaml_values[field], False


def _required_string(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be a non-blank string.")
    return value.strip()


def _integer_at_least(
    field: str, value: Any, *, allow_string: bool, minimum: int
) -> int:
    requirement = "positive" if minimum == 1 else "non-negative"
    if isinstance(value, bool):
        raise ConfigurationError(f"{field} must be a {requirement} integer, not a boolean.")
    if isinstance(value, int):
        parsed = value
    elif allow_string and isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ConfigurationError(f"{field} must be a {requirement} integer.") from exc
    else:
        raise ConfigurationError(f"{field} must be a {requirement} integer.")
    if parsed < minimum:
        raise ConfigurationError(f"{field} must be a {requirement} integer.")
    return parsed


def _project_path(field: str, value: Any) -> Path:
    path_text = _required_string(field, value)
    path = Path(path_text)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_settings(
    config_path: str | Path | None = None,
    dotenv_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Load configuration without modifying the process environment."""
    resolved_config_path = Path(config_path) if config_path is not None else PROJECT_ROOT / "config.yaml"
    resolved_dotenv_path = Path(dotenv_path) if dotenv_path is not None else PROJECT_ROOT / ".env"
    yaml_values = _read_yaml(resolved_config_path)
    dotenv = _dotenv_values(resolved_dotenv_path)
    source_environ = os.environ if environ is None else environ

    resolved_values = {
        field: _resolve_value(field, yaml_values, dotenv, source_environ)
        for field in _CONFIG_KEYS
    }
    values = {field: resolved[0] for field, resolved in resolved_values.items()}
    chunk_size = _integer_at_least(
        "chunk_size",
        values["chunk_size"],
        allow_string=resolved_values["chunk_size"][1],
        minimum=1,
    )
    chunk_overlap = _integer_at_least(
        "chunk_overlap",
        values["chunk_overlap"],
        allow_string=resolved_values["chunk_overlap"][1],
        minimum=0,
    )
    if chunk_overlap >= chunk_size:
        raise ConfigurationError("chunk_overlap must be smaller than chunk_size.")

    return Settings(
        openai_model=_required_string("openai_model", values["openai_model"]),
        openai_embedding_model=_required_string(
            "openai_embedding_model", values["openai_embedding_model"]
        ),
        db_faiss_path=_project_path("db_faiss_path", values["db_faiss_path"]),
        data_path=_project_path("data_path", values["data_path"]),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def get_openai_api_key(
    environ: Mapping[str, str] | None = None,
    dotenv_path: str | Path | None = None,
) -> str | None:
    """Return the API key from environment or dotenv without mutating either source."""
    source_environ = os.environ if environ is None else environ
    value = source_environ.get("OPENAI_API_KEY")
    if value is None:
        path = Path(dotenv_path) if dotenv_path is not None else PROJECT_ROOT / ".env"
        value = _dotenv_values(path).get("OPENAI_API_KEY")
    return value.strip() if isinstance(value, str) and value.strip() else None


settings = load_settings()

# Compatibility exports for existing component imports.
OPENAI_MODEL = settings.openai_model
OPENAI_EMBEDDING_MODEL = settings.openai_embedding_model
DB_FAISS_PATH = str(settings.db_faiss_path)
DATA_PATH = str(settings.data_path)
CHUNK_SIZE = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap
