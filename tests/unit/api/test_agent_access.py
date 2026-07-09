"""tests/unit/api/test_agent_access.py"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from octop.api.common.agent import assert_agent_owner
from octop.infra.errors import ErrorCode, OctopError


def test_owner_may_access() -> None:
    row = SimpleNamespace(user_id=1)
    user = SimpleNamespace(id=1, is_admin=False)
    assert_agent_owner(row, user)


def test_non_owner_forbidden() -> None:
    row = SimpleNamespace(user_id=1)
    user = SimpleNamespace(id=2, is_admin=False)
    with pytest.raises(OctopError) as ei:
        assert_agent_owner(row, user)
    assert ei.value.code is ErrorCode.FORBIDDEN


def test_shared_agent_non_admin_forbidden() -> None:
    row = SimpleNamespace(user_id=None)
    user = SimpleNamespace(id=1, is_admin=False)
    with pytest.raises(OctopError) as ei:
        assert_agent_owner(row, user)
    assert ei.value.code is ErrorCode.FORBIDDEN


def test_shared_agent_admin_allowed() -> None:
    row = SimpleNamespace(user_id=None)
    user = SimpleNamespace(id=1, is_admin=True)
    assert_agent_owner(row, user)
