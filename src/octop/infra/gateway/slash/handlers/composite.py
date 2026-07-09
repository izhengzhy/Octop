"""Composite slash commands (gateway + harness runtime data)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from harness_agent.slash import SlashCommand, SlashSink, thread_message_count

from octop.i18n.domains.agents import agent_error_message
from octop.i18n.domains.slash import localized_rows, tr
from octop.infra.gateway.slash.ctx import SlashCtx, chat_type, ensure_thread_id, lang_of, subject_id
from octop.infra.gateway.slash.formatting import (
    format_duration,
    markdown_kv_block,
    server_uptime_label,
)
from octop.infra.gateway.slash.types import GatewayHandler
from octop.infra.utils.locale import Locale, normalize_locale

if TYPE_CHECKING:
    from octop.infra.db.repos.users import UserRepo
    from octop.infra.gateway.slash.dispatcher import SlashDispatcher


def _format_slash_user(
    user_repo: UserRepo | None,
    user_id: int | None,
    lang: str,
    *,
    shared_label: str,
) -> str:
    if user_id is None:
        return shared_label
    if user_repo is None:
        return str(user_id)
    row = user_repo.get(user_id)
    if row is None:
        return str(user_id)
    locale: Locale = normalize_locale(lang)
    return tr("status.user_fmt", locale, username=row.username, user_id=user_id)


def _resolve_agent_row(ctx: SlashCtx) -> Any:
    if ctx.agent_manager is not None:
        return ctx.agent_manager.get_row(ctx.agent_id)
    if ctx.agent_repo is not None:
        return ctx.agent_repo.get(ctx.agent_id)
    return None


async def cmd_compact(
    d: SlashDispatcher, cmd: SlashCommand, ctx: SlashCtx, sink: SlashSink
) -> None:
    lang = lang_of(ctx)
    old_tid = ctx.thread_registry.get_bound_thread_id(ctx.session_key)
    msg_count = 0
    if old_tid and ctx.agent_manager is not None:
        try:
            harness = ctx.agent_manager.get_agent(ctx.agent_id)
            msg_count = await thread_message_count(harness, old_tid)
        except Exception:
            msg_count = 0
    new_tid = await ctx.thread_registry.reset(
        agent_id=ctx.agent_id,
        user_id=ctx.user_id,
        channel_type=ctx.channel_type,
        channel_subject_id=subject_id(ctx),
        channel_chat_type=chat_type(ctx),
    )
    if old_tid:
        d.clear_thread_model_override(ctx, old_tid)
    archived = ""
    if old_tid:
        archived = tr("compact.archived", lang, count=msg_count, short=old_tid[-6:])
    await sink.text(tr("compact.done", lang, short=new_tid[-6:], archived=archived))


async def cmd_history(
    d: SlashDispatcher, cmd: SlashCommand, ctx: SlashCtx, sink: SlashSink
) -> None:
    lang = lang_of(ctx)
    tid = await ensure_thread_id(ctx)
    row = ctx.thread_registry.get_thread(tid)
    msg_count = 0
    if ctx.agent_manager is not None:
        try:
            harness = ctx.agent_manager.get_agent(ctx.agent_id)
            msg_count = await thread_message_count(harness, tid)
        except Exception:
            msg_count = 0
    title = row.title if row else None
    rows: list[tuple[str, str]] = [
        ("thread", tid[-6:]),
        ("messages", str(msg_count)),
        ("title", title or tr("untitled", lang)),
    ]
    if row is not None:
        rows.append(("pinned", tr("yes", lang) if row.pinned else tr("no", lang)))
        if row.last_active:
            rows.append(("last_active", str(row.last_active)))
    override = d.get_thread_model_override(ctx, tid)
    if override:
        rows.append(("model_override", override))
    await sink.text(markdown_kv_block(tr("history.title", lang), localized_rows(rows, lang)))


async def cmd_status(d: SlashDispatcher, cmd: SlashCommand, ctx: SlashCtx, sink: SlashSink) -> None:
    lang = lang_of(ctx)
    tid = await ensure_thread_id(ctx)
    row = ctx.thread_registry.get_thread(tid)

    from octop.i18n.domains.agents import agent_state_label  # noqa: PLC0415

    agent_row = _resolve_agent_row(ctx)
    agent_state = agent_state_label(None, lang)
    default_model: str | None = None
    agent_name: str | None = None
    if agent_row is not None:
        agent_state = agent_state_label(agent_row.last_state, lang)
        default_model = agent_row.default_model
        agent_name = agent_row.name

    override = d.get_thread_model_override(ctx, tid)
    if override:
        model_line = tr("status.model_override", lang, model=override)
    elif default_model:
        model_line = tr("status.model_default", lang, model=default_model)
    else:
        model_line = tr("status.model_auto", lang)

    msg_count = 0
    if ctx.agent_manager is not None:
        try:
            harness = ctx.agent_manager.get_agent(ctx.agent_id)
            msg_count = await thread_message_count(harness, tid)
        except Exception:
            msg_count = 0

    token_line = tr("status.tokens_none", lang)
    if ctx.usage_repo is not None:
        totals = ctx.usage_repo.thread_totals(agent_id=ctx.agent_id, thread_id=tid)
        if totals["turns"] > 0:
            token_line = tr(
                "status.tokens_summary",
                lang,
                total=totals["total_tokens"],
                input=totals["input_tokens"],
                output=totals["output_tokens"],
                turns=totals["turns"],
            )

    session_age = ""
    if row is not None and row.created_at:
        session_age = format_duration(int(time.time()) - int(row.created_at))

    session_key_display = (
        f"…{ctx.session_key[-24:]}" if len(ctx.session_key) > 24 else ctx.session_key
    )
    thread_label = f"`{tid[-6:]}` — {row.title if row and row.title else tr('untitled', lang)}"

    workspace_line = tr("unknown", lang)
    if ctx.paths is not None:
        workspace_line = str(ctx.paths.agent_workspace(ctx.agent_id))

    chat_user_line = _format_slash_user(
        ctx.user_repo,
        ctx.user_id if ctx.user_id > 0 else None,
        lang,
        shared_label="—",
    )
    owner_line = _format_slash_user(
        ctx.user_repo,
        agent_row.user_id if agent_row is not None else None,
        lang,
        shared_label=tr("status.owner_shared", lang),
    )

    rows: list[tuple[str, str]] = [
        ("octop", ctx.octop_version or tr("unknown", lang)),
        ("uptime", server_uptime_label(ctx.server_started_at)),
        ("agent_id", ctx.agent_id),
        ("agent", f"{agent_name or ctx.agent_id[-6:]} ({agent_state})"),
        ("owner", owner_line),
        ("chat_user", chat_user_line),
        ("workspace", workspace_line),
        ("model", model_line),
        ("thread", thread_label),
        ("session", f"`{session_key_display}`"),
        ("channel", ctx.channel_type),
        ("context", tr("status.context", lang, count=msg_count)),
        ("tokens", token_line),
    ]
    if agent_row is not None and agent_row.template_name:
        rows.insert(7, ("template", agent_row.template_name))
    if session_age:
        rows.append(("thread_age", session_age))
    if row is not None:
        rows.append(("pinned", tr("yes", lang) if row.pinned else tr("no", lang)))
    if ctx.gateway_channels:
        kinds = ", ".join(c.get("kind", "?") for c in ctx.gateway_channels[:5])
        rows.append(
            (
                "im_channels",
                tr("status.im_channels", lang, count=len(ctx.gateway_channels), kinds=kinds),
            )
        )
    if ctx.cron_manager is not None:
        cron_count = len(ctx.cron_manager.list_by_agent(ctx.agent_id, include_disabled=False))
        rows.append(("cron_jobs", str(cron_count)))
    if agent_row is not None and agent_row.last_error:
        rows.append(
            (
                "last_error",
                agent_error_message(agent_row.last_error, lang)[:120],
            )
        )

    await sink.text(markdown_kv_block(tr("status.title", lang), localized_rows(rows, lang)))


async def cmd_model(d: SlashDispatcher, cmd: SlashCommand, ctx: SlashCtx, sink: SlashSink) -> None:
    lang = lang_of(ctx)
    tid = await ensure_thread_id(ctx)
    name = cmd.args.strip()
    if not name:
        override = d.get_thread_model_override(ctx, tid)
        default_model: str | None = None
        if ctx.agent_manager is not None:
            row = ctx.agent_manager.get_row(ctx.agent_id)
            if row is not None:
                default_model = row.default_model
        elif ctx.agent_repo is not None:
            row = ctx.agent_repo.get(ctx.agent_id)
            if row is not None:
                default_model = row.default_model
        if override:
            await sink.text(tr("model.override", lang, model=override))
        elif default_model:
            await sink.text(tr("model.current_default", lang, model=default_model))
        else:
            await sink.text(tr("model.usage", lang))
        return
    if name.lower() == "reset":
        d.clear_thread_model_override(ctx, tid)
        if hasattr(sink, "action"):
            await sink.action("clear_model")
        await sink.text(tr("model.cleared", lang))
        return
    d.set_thread_model_override(ctx, tid, name)
    if hasattr(sink, "action"):
        await sink.action("set_model", model=name)
    await sink.text(tr("model.set", lang, model=name))


COMPOSITE_HANDLERS: dict[str, GatewayHandler] = {
    "compact": cmd_compact,
    "history": cmd_history,
    "status": cmd_status,
    "model": cmd_model,
    "models": cmd_model,
}
