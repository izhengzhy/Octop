"""Trigger string → APScheduler trigger."""

from __future__ import annotations

import datetime as dt

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from octop.infra.errors import ErrorCode, OctopError


def build_trigger(spec: str) -> BaseTrigger:
    """Parse 'cron:<expr>' / 'interval:<seconds>' / 'date:<ISO>'."""
    if ":" not in spec:
        raise OctopError(ErrorCode.CRON_TRIGGER_INVALID, f"trigger spec missing kind: {spec!r}")
    kind, _, value = spec.partition(":")
    value = value.strip()
    if not value:
        raise OctopError(ErrorCode.CRON_TRIGGER_INVALID, f"trigger value empty: {spec!r}")
    try:
        if kind == "interval":
            return IntervalTrigger(seconds=int(value))
        if kind == "cron":
            return CronTrigger.from_crontab(value)
        if kind == "date":
            return DateTrigger(run_date=dt.datetime.fromisoformat(value))
    except (ValueError, TypeError) as exc:
        raise OctopError(
            ErrorCode.CRON_TRIGGER_INVALID,
            f"trigger spec {spec!r} could not be parsed: {exc}",
        ) from exc
    raise OctopError(ErrorCode.CRON_TRIGGER_INVALID, f"unknown trigger kind: {kind!r}")
