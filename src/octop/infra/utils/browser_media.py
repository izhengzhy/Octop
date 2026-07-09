"""harness-browser media paths aligned with IM ``outbound/`` layout."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from octop.infra.utils.paths import PathLayout

logger = logging.getLogger(__name__)

OUTBOUND_SCREENSHOTS_REL = "outbound/screenshots"


def agent_outbound_screenshots_dir(paths: PathLayout, agent_id: str) -> Path:
    """``<agent_workspace>/outbound/screenshots`` — same convention as IM ``outbound/``."""
    root = paths.ensure_agent_workspace(agent_id)
    dest = root / OUTBOUND_SCREENSHOTS_REL
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def configure_browser_screenshots_dir(screenshots_dir: Path) -> None:
    """Point harness-browser screenshot actions at an agent workspace directory."""
    resolved = screenshots_dir.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    os.environ["BROWSER_USE_SCREENSHOTS_DIR"] = str(resolved)
    logger.debug("BROWSER_USE_SCREENSHOTS_DIR=%s", resolved)


def harness_settings_for_screenshots_dir(screenshots_dir: Path) -> Any | None:
    """Build :class:`HarnessSettings` when harness-browser is installed."""
    try:
        from harness_browser.settings import HarnessSettings
    except ImportError:
        return None
    return HarnessSettings(screenshots_dir=screenshots_dir.resolve())


def legacy_harness_screenshots_dir() -> Path:
    return Path.home() / ".harness-browser" / "screenshots"
