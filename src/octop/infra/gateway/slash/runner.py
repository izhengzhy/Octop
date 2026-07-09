"""Shared slash command execution for IM processor and dashboard chat."""

from __future__ import annotations

from harness_agent.slash import BufferSink, SlashCommand, SlashSink, parse_slash

from octop.infra.gateway.slash.ctx import SlashCtx
from octop.infra.gateway.slash.dispatcher import SlashDispatcher


async def try_handle_slash(
    text: str | None,
    *,
    dispatcher: SlashDispatcher,
    ctx: SlashCtx,
    sink: SlashSink | None = None,
) -> tuple[bool, list[str], list[dict[str, object]]]:
    """Parse *text* and dispatch if it is a slash command.

    Returns ``(handled, lines, actions)``. *handled* is False when *text* is not
    a slash command; True when a command was recognized (including unknown commands).
    """
    cmd = parse_slash(text)
    if cmd is None:
        return False, [], []
    buf = sink if sink is not None else BufferSink()
    if sink is None:
        assert isinstance(buf, BufferSink)
    await dispatcher.handle(cmd, ctx, buf)
    if isinstance(buf, BufferSink):
        return True, buf.lines, buf.actions
    return True, [], []


async def handle_slash_command(
    cmd: SlashCommand,
    *,
    dispatcher: SlashDispatcher,
    ctx: SlashCtx,
) -> list[str]:
    """Run a parsed command and return response lines."""
    sink = BufferSink()
    await dispatcher.handle(cmd, ctx, sink)
    return sink.lines
