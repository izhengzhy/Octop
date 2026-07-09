"""Static connector catalog — bundled presets for HTTP MCP services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AuthKind = Literal[
    "personal_token",
    "oauth2",
    "auth_code",
    "api_key",
    "imap_app_password",
    "session_cookie",
    "api_credentials",
]


@dataclass(frozen=True)
class ConnectorCatalogEntry:
    kind: str
    name: str
    description: str
    auth_kind: AuthKind
    doc_url: str
    icon: str
    color: str
    phase: Literal["available", "coming_soon"]
    mcp_mode: Literal["remote", "gateway"]
    quick_auth_url: str | None = None
    login_url: str | None = None
    guide_url: str | None = None
    manual_url: str | None = None
    auth_hint: str | None = None
    # Optional allowlist of tool names exposed to the LLM.
    # None means no restriction (all tools from the MCP server are available).
    allowed_tools: tuple[str, ...] | None = None


_CATALOG: tuple[ConnectorCatalogEntry, ...] = (
    ConnectorCatalogEntry(
        kind="tencent-docs",
        name="腾讯文档",
        description="读写腾讯文档、智能表格与空间文件",
        auth_kind="personal_token",
        doc_url="https://developer.cloud.tencent.com/mcp/server/11803",
        icon="tencent-docs",
        color="#0052d9",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://docs.qq.com/open/auth/mcp.html",
        guide_url="https://developer.cloud.tencent.com/mcp/server/11803",
        manual_url="https://docs.qq.com/open/auth/mcp.html",
        auth_hint="打开 MCP 授权页登录，复制页面上的 Token 并粘贴到下方",
        allowed_tools=(
            "create_smartcanvas_by_mdx",
            "smartcanvas.read",
            "smartcanvas.edit",
            "smartcanvas.find",
            "manage.create_file",
            "scrape_url",
            "manage.export_file",
            "manage.search_file",
            "manage.set_privilege",
            "manage.folder_list",
        ),
    ),
    ConnectorCatalogEntry(
        kind="tencent-ima",
        name="腾讯 IMA",
        description="笔记与知识库读写、检索与管理",
        auth_kind="api_key",
        doc_url="https://qclaw.qq.com/docs/206424375046045696",
        icon="tencent-ima",
        color="#07c160",
        phase="available",
        mcp_mode="gateway",
        quick_auth_url="https://ima.qq.com/agent-interface",
        manual_url="https://ima.qq.com/agent-interface",
        auth_hint="点击「打开授权页」在 IMA 中获取 API Key 与 Client ID（API Key 仅展示一次）",
    ),
    ConnectorCatalogEntry(
        kind="tencent-meeting",
        name="腾讯会议",
        description="会议管理、查询、录制与智能纪要",
        auth_kind="personal_token",
        doc_url="https://meeting.tencent.com/ai-skill.html",
        icon="tencent-meeting",
        color="#006eff",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://meeting.tencent.com/ai-skill.html",
        guide_url="https://meeting.tencent.com/ai-skill.html",
        manual_url="https://meeting.tencent.com/ai-skill.html",
        auth_hint="打开授权页登录腾讯会议，复制页面上的 Token 并粘贴到下方",
    ),
    ConnectorCatalogEntry(
        kind="tencent-news",
        name="腾讯新闻",
        description="新闻搜索与热点订阅",
        auth_kind="auth_code",
        doc_url="https://news.qq.com/exchange?scene=appkey",
        icon="tencent-news",
        color="#1485ee",
        phase="available",
        mcp_mode="gateway",
        quick_auth_url="https://news.qq.com/exchange?scene=appkey",
        auth_hint="点击「打开授权页」获取授权码后粘贴到下方",
    ),
    ConnectorCatalogEntry(
        kind="wechat-reading",
        name="微信读书",
        description="书架同步与读书笔记",
        auth_kind="api_key",
        doc_url="https://weread.qq.com/r/weread-skills",
        icon="wechat-reading",
        color="#1aad19",
        phase="available",
        mcp_mode="gateway",
        quick_auth_url="https://weread.qq.com/r/weread-skills",
        auth_hint="登录 https://weread.qq.com/r/weread-skills 获取 wrk- 开头的 API Key 后粘贴到下方",
    ),
    ConnectorCatalogEntry(
        kind="tencent-lexiang",
        name="腾讯乐享",
        description="知识库检索、阅读、创建与文档管理",
        auth_kind="api_key",
        doc_url="https://qclaw.qq.com/docs/211858629271314432",
        icon="tencent-lexiang",
        color="#00c1de",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://lexiangla.com/ai/claw?company_from=csig",
        guide_url="https://qclaw.qq.com/docs/211858629271314432",
        manual_url="https://lexiangla.com/mcp",
        auth_hint="打开乐享凭证页登录，复制企业标识（company_from）与访问令牌，分别填入下方",
    ),
    ConnectorCatalogEntry(
        kind="tencent-weiyun",
        name="腾讯微云",
        description="官方 MCP：网盘列表、上传、下载、分享与文件管理",
        auth_kind="personal_token",
        doc_url="https://www.weiyun.com/act/openclaw",
        icon="tencent-weiyun",
        color="#00a4ff",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://www.weiyun.com/act/openclaw",
        guide_url="https://www.weiyun.com/act/openclaw",
        manual_url="https://www.weiyun.com/act/openclaw",
        auth_hint="打开微云 Skill 配置页登录，复制 MCP Token 并粘贴到下方",
        allowed_tools=(
            "weiyun.list",
            "weiyun.list_by_category",
            "weiyun.download",
            "weiyun.delete",
            "weiyun.upload",
            "weiyun.gen_share_link",
            "weiyun.rename_file",
            "weiyun.rename_dir",
            "weiyun.create_dir",
            "weiyun.move_dir",
            "weiyun.move_file",
            "check_skill_update",
        ),
    ),
    ConnectorCatalogEntry(
        kind="qq-mail",
        name="个人邮箱",
        description="通过 IMAP/SMTP 连接 QQ 邮箱、网易邮箱、Gmail 等",
        auth_kind="imap_app_password",
        doc_url="https://mail.qq.com/",
        icon="qq-mail",
        color="#12b7f5",
        phase="available",
        mcp_mode="gateway",
        manual_url="https://mail.qq.com/",
        auth_hint="选择邮箱服务商，在邮箱设置中开启 IMAP/SMTP 并生成授权码后填入下方",
    ),
    ConnectorCatalogEntry(
        kind="figma",
        name="Figma",
        description="官方 MCP：设计上下文与截图",
        auth_kind="oauth2",
        doc_url="https://developers.figma.com/docs/figma-mcp-server/",
        icon="figma",
        color="#a259ff",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/",
        guide_url="https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/",
        auth_hint="点击「一键授权」完成 Figma 登录，或按官方文档手动获取 Token",
    ),
    ConnectorCatalogEntry(
        kind="baidu-netdisk",
        name="百度网盘",
        description="网盘文件列表、搜索与管理",
        auth_kind="personal_token",
        doc_url="https://github.com/baidu-netdisk/mcp",
        icon="baidu-netdisk",
        color="#2932e1",
        phase="available",
        mcp_mode="remote",
        quick_auth_url=(
            "https://openapi.baidu.com/oauth/2.0/authorize"
            "?client_id=zF5kkNsCvckX4aIpRdHxpFkcSMxnGZky"
            "&display=popup&qrcode=1"
            "&redirect_uri=oob&response_type=token"
            "&scope=basic%2Cnetdisk&force_login=1"
        ),
        manual_url=(
            "https://openapi.baidu.com/oauth/2.0/authorize"
            "?client_id=zF5kkNsCvckX4aIpRdHxpFkcSMxnGZky"
            "&display=popup&qrcode=1"
            "&redirect_uri=oob&response_type=token"
            "&scope=basic%2Cnetdisk&force_login=1"
        ),
        auth_hint=(
            "点击「打开授权页」登录并授权，从跳转链接中复制 access_token= 后的完整 Access Token 并粘贴到下方"
        ),
    ),
    ConnectorCatalogEntry(
        kind="youdao-note",
        name="有道云笔记",
        description="官方 MCP：笔记创建、搜索、整理与管理",
        auth_kind="personal_token",
        doc_url="https://qclaw.qq.com/docs/207508177113886720",
        icon="youdao-note",
        color="#00c853",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://mopen.163.com/#/dashboard",
        guide_url="https://qclaw.qq.com/docs/207508177113886720",
        manual_url="https://mopen.163.com/#/dashboard",
        auth_hint="点击「打开授权页」登录 MCP 平台，在 API 管理创建 API Key 并粘贴到下方",
    ),
    ConnectorCatalogEntry(
        kind="notion",
        name="Notion",
        description="官方 MCP：搜索、读写页面与数据库",
        auth_kind="oauth2",
        doc_url="https://developers.notion.com/docs/mcp",
        icon="notion",
        color="#000000",
        phase="available",
        mcp_mode="remote",
        quick_auth_url="https://developers.notion.com/guides/mcp/get-started-with-mcp",
        guide_url="https://developers.notion.com/guides/mcp/get-started-with-mcp",
        auth_hint="点击「一键授权」完成 Notion 登录，或按官方文档手动获取 Token",
    ),
)


def list_catalog() -> list[ConnectorCatalogEntry]:
    return list(_CATALOG)


def get_catalog_entry(kind: str) -> ConnectorCatalogEntry | None:
    for entry in _CATALOG:
        if entry.kind == kind:
            return entry
    return None


def catalog_entry_to_dict(
    entry: ConnectorCatalogEntry, *, oauth_ready: bool = False
) -> dict[str, object]:
    from octop.infra.connectors.oauth import oauth_mode_for_kind  # noqa: PLC0415

    oauth_mode = oauth_mode_for_kind(entry.kind)
    return {
        "kind": entry.kind,
        "name": entry.name,
        "description": entry.description,
        "auth_kind": entry.auth_kind,
        "doc_url": entry.doc_url,
        "icon": entry.icon,
        "color": entry.color,
        "phase": entry.phase,
        "mcp_mode": entry.mcp_mode,
        "quick_auth_url": entry.quick_auth_url,
        "login_url": entry.login_url,
        "guide_url": entry.guide_url or entry.doc_url,
        "manual_url": entry.manual_url or entry.guide_url or entry.doc_url,
        "auth_hint": entry.auth_hint,
        "oauth_mode": oauth_mode,
        "oauth_ready": oauth_ready,
        "supports_quick_auth": entry.phase == "available" and entry.auth_kind != "api_credentials",
    }
