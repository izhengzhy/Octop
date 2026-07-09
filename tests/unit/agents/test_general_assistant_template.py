"""Sanity checks for the bundled general-assistant template."""

from __future__ import annotations

import json

import yaml

from octop.infra.agents.experts.catalog import default_library_root

_DIR = default_library_root() / "general-assistant"


def test_all_required_files_present() -> None:
    for name in ("SOUL.md", "MEMORY.md", "skills.json", "meta.yaml"):
        assert (_DIR / name).is_file(), f"missing {name}"
    assert (_DIR / "skills/octop-assistant/SKILL.md").is_file()


def test_meta_yaml_has_id_and_display_name() -> None:
    meta = yaml.safe_load((_DIR / "meta.yaml").read_text(encoding="utf-8"))
    assert meta["id"] == "general-assistant"
    assert isinstance(meta.get("display_name"), str) and meta["display_name"]


def test_skills_json_is_a_list() -> None:
    skills = json.loads((_DIR / "skills.json").read_text(encoding="utf-8"))
    assert isinstance(skills, list)
