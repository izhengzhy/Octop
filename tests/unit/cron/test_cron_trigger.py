"""tests/unit/test_cron_trigger.py"""

from __future__ import annotations

import datetime as dt

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from octop.infra.cron.trigger import build_trigger
from octop.infra.errors import ErrorCode, OctopError


def test_interval_seconds():
    trig = build_trigger("interval:60")
    assert isinstance(trig, IntervalTrigger)
    assert trig.interval == dt.timedelta(seconds=60)


def test_cron_expression():
    trig = build_trigger("cron:0 9 * * *")
    assert isinstance(trig, CronTrigger)


def test_date_iso():
    trig = build_trigger("date:2026-12-31T09:00:00")
    assert isinstance(trig, DateTrigger)


def test_unknown_kind_raises():
    with pytest.raises(OctopError) as ei:
        build_trigger("webhook:foo")
    assert ei.value.code is ErrorCode.CRON_TRIGGER_INVALID


def test_missing_colon_raises():
    with pytest.raises(OctopError):
        build_trigger("interval60")


def test_malformed_cron_raises():
    with pytest.raises(OctopError):
        build_trigger("cron:not a cron")
