"""Tests for octop.infra.setup.self_update."""

from __future__ import annotations

from octop.infra.setup.self_update import is_newer, parse_version


def test_parse_version_ignores_suffix() -> None:
    assert parse_version("0.7.2") > parse_version("0.7.1")
    assert parse_version("0.7.1rc1") == parse_version("0.7.1")


def test_is_newer() -> None:
    assert is_newer("0.7.2", "0.7.1")
    assert not is_newer("0.7.1", "0.7.2")
    assert not is_newer("0.7.1", "0.7.1")
