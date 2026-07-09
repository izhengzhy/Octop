"""tests/unit/test_env_file.py"""

from __future__ import annotations

from pathlib import Path

from octop.infra.utils.env_file import (
    apply_env_file,
    format_env_file,
    load_env_file,
    parse_env_text,
    save_env_file,
)


def test_parse_and_roundtrip() -> None:
    text = '# comment\nFOO=bar\nexport BAZ="hello world"\nEMPTY=\n'
    parsed = parse_env_text(text)
    assert parsed == {"FOO": "bar", "BAZ": "hello world", "EMPTY": ""}
    assert format_env_file(parsed).splitlines() == [
        'BAZ="hello world"',
        "EMPTY=",
        "FOO=bar",
    ]


def test_save_and_load(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "env"
    save_env_file(path, {"API_KEY": "secret", "COUNT": "1"})
    assert load_env_file(path)["API_KEY"] == "secret"
    monkeypatch.delenv("API_KEY", raising=False)
    apply_env_file(path)
    import os

    assert os.environ["API_KEY"] == "secret"
