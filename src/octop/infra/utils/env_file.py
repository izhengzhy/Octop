"""Persisted environment variables at ``~/.octop/env`` (dotenv format)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def env_file_path(root: Path) -> Path:
    return root / "env"


def parse_env_text(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not _KEY_RE.match(key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        out[key] = value
    return out


def load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_env_text(path.read_text(encoding="utf-8"))


def format_env_file(values: dict[str, str]) -> str:
    lines: list[str] = []
    for key in sorted(values):
        if not _KEY_RE.match(key):
            continue
        val = values[key]
        if not val:
            lines.append(f"{key}=")
        elif re.search(r"[\s#\"'\\]", val):
            escaped = val.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        else:
            lines.append(f"{key}={val}")
    return "\n".join(lines) + ("\n" if lines else "")


def save_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_env_file(values), encoding="utf-8")


def apply_env_file(path: Path) -> dict[str, str]:
    """Load ``path`` and merge into ``os.environ`` (does not unset missing keys)."""
    values = load_env_file(path)
    for key, value in values.items():
        os.environ[key] = value
    return values


def list_env_items(path: Path) -> list[dict[str, str]]:
    return [{"key": k, "value": v} for k, v in sorted(load_env_file(path).items())]
