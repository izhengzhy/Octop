"""tests/unit/cron/test_task_type.py"""

from __future__ import annotations

import pytest

from octop.infra.cron.task_type import CRON_PROMPT_MAX_LEN, require_cron_prompt


def test_require_cron_prompt_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        require_cron_prompt("   ")


def test_require_cron_prompt_rejects_too_long() -> None:
    with pytest.raises(ValueError, match=str(CRON_PROMPT_MAX_LEN)):
        require_cron_prompt("x" * (CRON_PROMPT_MAX_LEN + 1))


def test_require_cron_prompt_strips() -> None:
    assert require_cron_prompt("  hello  ") == "hello"
