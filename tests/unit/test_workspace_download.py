"""tests/unit/test_workspace_download.py"""

from __future__ import annotations

import pytest

from octop.infra.gateway.media.backend_files import (
    normalize_workspace_download_path,
    normalize_workspace_media_path,
    workspace_download_url,
)


def test_normalize_workspace_media_path_outbound() -> None:
    assert normalize_workspace_media_path("/outbound/a.png") == "outbound/a.png"
    assert normalize_workspace_media_path("outbound/a.png") == "outbound/a.png"


def test_normalize_download_rejects_harness_browser() -> None:
    with pytest.raises(ValueError):
        normalize_workspace_download_path("/Users/me/.harness-browser/screenshots/x.png")


def test_normalize_download_rejects_windows_users_path() -> None:
    with pytest.raises(ValueError):
        normalize_workspace_download_path(r"C:\Users\me\secret.png")


def test_normalize_download_rejects_windows_temp_path() -> None:
    with pytest.raises(ValueError):
        normalize_workspace_download_path(r"C:\Windows\Temp\shot.png")


def test_normalize_download_allows_workspace_file() -> None:
    assert normalize_workspace_download_path("/logo.png") == "logo.png"


def test_normalize_download_allows_workspace_relative_tmp_var() -> None:
    """COS/local workspace keys must not be mistaken for host /tmp or /var."""
    assert normalize_workspace_download_path("tmp/cache.bin") == "tmp/cache.bin"
    assert normalize_workspace_download_path("var/data.json") == "var/data.json"


def test_workspace_download_url_only_outbound() -> None:
    url = workspace_download_url("agent-1", "outbound/chart.png")
    assert "path=%2Foutbound%2Fchart.png" in url
    with pytest.raises(ValueError):
        workspace_download_url("agent-1", "/Users/me/x.png")
