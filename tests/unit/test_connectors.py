"""Unit tests for connector builder and repo."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octop.config import OctopConfig
from octop.infra.connectors.builder import (
    build_http_mcp_spec,
    mcp_server_name,
    normalize_weiyun_mcp_token,
    validate_create_credentials,
)
from octop.infra.connectors.catalog import get_catalog_entry
from octop.infra.connectors.gateway.protocol import handle_mcp_request
from octop.infra.db.migrate import run_migrations
from octop.infra.db.pool import DBPool
from octop.infra.db.repos.connectors import ConnectorRepo
from octop.infra.utils.ulid import new_ulid


@pytest.fixture
def db(tmp_path: Path) -> DBPool:
    pool = DBPool(tmp_path / "octop.db")
    run_migrations(pool)
    return pool


def test_mcp_server_name_format():
    iid = new_ulid()
    assert mcp_server_name("tencent-docs", iid) == f"tencent-docs__{iid}"


def test_validate_tencent_token():
    payload = validate_create_credentials("tencent-docs", {"token": "abc"})
    assert payload["token"] == "abc"


def test_build_tencent_remote_spec():
    entry = get_catalog_entry("tencent-docs")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="x",
        creds={"token": "tok"},
        config=OctopConfig(),
    )
    assert spec["transport"] == "http"
    assert spec["headers"]["Authorization"] == "tok"
    assert spec["tool_arg_aliases"]["manage.search_file"]["query"] == "search_key"


def test_build_weiyun_remote_spec():
    entry = get_catalog_entry("tencent-weiyun")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="x",
        creds={"token": "wy-token"},
        config=OctopConfig(),
    )
    assert spec["transport"] == "http"
    assert spec["url"] == "https://www.weiyun.com/api/v3/mcpserver"
    assert spec["headers"]["WyHeader"] == "mcp_token=wy-token"
    assert spec["headers"]["Accept"] == "application/json, text/event-stream"
    assert "weiyun.list" in spec["allowed_tools"]


def test_normalize_weiyun_mcp_token():
    assert normalize_weiyun_mcp_token("abc123") == "abc123"
    assert normalize_weiyun_mcp_token("mcp_token=abc123") == "abc123"
    assert normalize_weiyun_mcp_token('export WEIYUN_MCP_TOKEN="abc123"') == "abc123"
    assert normalize_weiyun_mcp_token("WyHeader: mcp_token=abc123") == "abc123"


@pytest.mark.asyncio
async def test_prepare_probe_credentials_allows_empty_weiyun_token():
    from octop.infra.connectors.probe import prepare_probe_credentials

    creds = await prepare_probe_credentials("tencent-weiyun", {})
    assert creds == {}

    creds = await prepare_probe_credentials(
        "tencent-weiyun",
        {"token": "mcp_token=real-token"},
    )
    assert creds == {"token": "real-token"}


def test_validate_weiyun_token_normalizes_prefix():
    payload = validate_create_credentials(
        "tencent-weiyun",
        {"token": "mcp_token=wy-token"},
    )
    assert payload == {"token": "wy-token"}


def test_build_notion_remote_spec():
    entry = get_catalog_entry("notion")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="x",
        creds={"access_token": "ntn_xxx"},
        config=OctopConfig(),
    )
    assert spec["url"] == "https://mcp.notion.com/mcp"
    assert spec["headers"]["Authorization"] == "Bearer ntn_xxx"
    assert spec["headers"]["Accept"] == "application/json, text/event-stream"


def test_gateway_tools_list():
    resp = handle_mcp_request(
        kind="qq-mail",
        creds={"email": "a@qq.com", "password": "p"},
        body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert len(resp["result"]["tools"]) == 3


def test_gateway_ima_tools():
    tools = handle_mcp_request(
        kind="tencent-ima",
        creds={"api_key": "k", "client_id": "c"},
        body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert len(tools["result"]["tools"]) == 4


def test_gateway_ima_tool_call_dispatch():
    resp = handle_mcp_request(
        kind="tencent-ima",
        creds={"api_key": "k", "client_id": "c"},
        body={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "list_notes", "arguments": {"start": 0, "end": 5}},
        },
    )
    assert "error" not in resp
    assert resp["result"]["isError"] is True
    assert "arguments" not in str(resp["result"]["content"][0]["text"])


def test_gateway_wechat_reading_tools():
    tools = handle_mcp_request(
        kind="wechat-reading",
        creds={"api_key": "x=1"},
        body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert len(tools["result"]["tools"]) == 2


def test_ima_api_key_credentials():
    payload = validate_create_credentials(
        "tencent-ima",
        {"api_key": "ima_key", "client_id": "ima_client"},
    )
    assert payload["api_key"] == "ima_key"
    assert payload["client_id"] == "ima_client"
    assert "internal_token" in payload


def test_ima_list_notes_uses_list_note_api(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"note_book_list": [], "is_end": True}

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> _Resp:
            captured["url"] = url
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(
        "octop.infra.connectors.gateway.adapters.tencent_ima.httpx.Client",
        _Client,
    )
    from octop.infra.connectors.gateway.adapters.tencent_ima import (
        call_tool as _ima_call_tool,
    )

    out = _ima_call_tool(
        {"api_key": "wrk-x", "client_id": "cid"},
        "list_notes",
        {"limit": 8},
    )
    assert '"note_book_list"' in out
    assert captured["url"] == "https://ima.qq.com/openapi/note/v1/list_note"
    assert captured["json"] == {"cursor": "", "limit": 8}


def test_ima_requires_client_id():
    with pytest.raises(ValueError, match="client_id"):
        validate_create_credentials("tencent-ima", {"api_key": "k"})


def test_api_key_weread():
    payload = validate_create_credentials("wechat-reading", {"api_key": "wrk-testkey"})
    assert payload["api_key"] == "wrk-testkey"
    assert "internal_token" in payload


def test_api_key_weread_rejects_cookie():
    with pytest.raises(ValueError, match="wrk-"):
        validate_create_credentials("wechat-reading", {"api_key": "wr_skey=abc; wr_vid=1"})


def test_weread_shelf_uses_agent_gateway(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"books": [], "albums": []}

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> _Resp:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(
        "octop.infra.connectors.gateway.adapters.wechat_reading.httpx.Client",
        _Client,
    )
    from octop.infra.connectors.gateway.adapters.wechat_reading import shelf as _weread_shelf

    out = _weread_shelf({"api_key": "wrk-abc"})
    assert '"books"' in out
    assert captured["url"] == "https://i.weread.qq.com/api/agent/gateway"
    assert captured["headers"]["Authorization"] == "Bearer wrk-abc"
    assert captured["json"] == {
        "api_name": "/shelf/sync",
        "skill_version": "1.0.3",
    }


def test_youdao_personal_token_credentials():
    payload = validate_create_credentials(
        "youdao-note",
        {"token": "ynote-api-key"},
    )
    assert payload["token"] == "ynote-api-key"
    assert "internal_token" not in payload


def test_auth_code_passthrough_news():
    payload = validate_create_credentials("tencent-news", {"cookie": "sess=1"})
    assert payload["cookie"] == "sess=1"
    assert "internal_token" in payload


def test_baidu_probe_tools():
    from octop.infra.connectors.baidu_token import baidu_probe_tools

    tools = baidu_probe_tools()
    assert len(tools) >= 3
    assert any(t["name"] == "list_files" for t in tools)


def test_http_error_message_baidu_auth_fail():
    import httpx

    from octop.infra.connectors.probe import http_error_message

    r = httpx.Response(400, json={"errno": 2003, "show_msg": "auth fail:token fail"})
    assert http_error_message(r) == "auth fail:token fail"


def test_static_probe_tools_baidu():
    from octop.infra.connectors.probe import static_probe_tools

    tools = static_probe_tools("baidu-netdisk")
    assert len(tools) >= 3
    assert static_probe_tools("notion") == []


def test_build_gateway_mcp_spec():
    entry = get_catalog_entry("tencent-ima")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="inst1",
        creds={"api_key": "k", "client_id": "c", "internal_token": "tok"},
        config=OctopConfig(),
    )
    assert spec["transport"] == "http"
    assert "/api/internal/mcp/tencent-ima/inst1" in spec["url"]
    assert "token=" in spec["url"]


def test_build_gateway_langchain_tools():
    from octop.infra.connectors.gateway.langchain import build_gateway_langchain_tools

    entry = get_catalog_entry("tencent-ima")
    assert entry is not None
    tools = build_gateway_langchain_tools(
        entry=entry,
        instance_id="inst1",
        mcp_server_name="tencent-ima__inst1",
        creds={"api_key": "k", "client_id": "c"},
    )
    names = {t.name for t in tools}
    assert "tencent-ima__inst1_list_notes" in names


def test_gateway_search_news_passes_query(monkeypatch: pytest.MonkeyPatch):
    from octop.infra.connectors.gateway.langchain import build_gateway_langchain_tools

    captured: dict[str, object] = {}

    def _fake_news(_creds: dict[str, object], args: dict[str, object]) -> str:
        captured.update(args)
        return "[]"

    monkeypatch.setattr(
        "octop.infra.connectors.gateway.adapters.tencent_news.search_news",
        _fake_news,
    )
    entry = get_catalog_entry("tencent-news")
    assert entry is not None
    tools = build_gateway_langchain_tools(
        entry=entry,
        instance_id="inst1",
        mcp_server_name="tencent-news__inst1",
        creds={"cookie": "x"},
    )
    search = next(t for t in tools if t.name.endswith("search_news"))
    assert "query" in search.args_schema.model_json_schema()["properties"]
    search.invoke({"query": "热点", "max_results": 5})
    assert captured["query"] == "热点"
    assert captured["max_results"] == 5


def test_baidu_personal_token_credentials_invalid():
    with pytest.raises(ValueError, match="32 位授权码"):
        validate_create_credentials("baidu-netdisk", {"token": "785329e1434f623b0562f6663921fb31"})


def test_prepare_baidu_auth_code_requires_secret_for_builtin_app():
    from octop.api.routers.connectors import _prepare_credentials

    class _Settings:
        def get(self, _key: str) -> str:
            return ""

    with pytest.raises(ValueError, match="access_token="):
        asyncio.run(
            _prepare_credentials(
                "baidu-netdisk",
                {"token": "069adffeef42c9af962b4802b6f255b1"},
                _Settings(),
            )
        )


def test_prepare_baidu_auth_code_exchanges_with_client_secret(
    monkeypatch: pytest.MonkeyPatch,
):
    from octop.api.routers.connectors import _prepare_credentials

    async def _fake_exchange(**_kwargs: object) -> dict[str, object]:
        return {
            "access_token": "bd_access",
            "refresh_token": "bd_refresh",
            "expires_at": 9999999999,
        }

    monkeypatch.setattr(
        "octop.infra.connectors.oauth.baidu.exchange_baidu_oob_code",
        _fake_exchange,
    )
    monkeypatch.setattr(
        "octop.infra.connectors.oauth.baidu.resolve_baidu_client_credentials",
        lambda _repo: ("cid", "secret"),
    )
    monkeypatch.setattr(
        "octop.infra.connectors.baidu_token.validate_baidu_access_token_sync",
        lambda _token: (True, None),
    )

    class _Settings:
        def get(self, _key: str) -> str:
            return ""

    payload = asyncio.run(
        _prepare_credentials(
            "baidu-netdisk",
            {"token": "785329e1434f623b0562f6663921fb31"},
            _Settings(),
        )
    )
    assert payload["access_token"] == "bd_access"


def test_baidu_personal_token_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "octop.infra.connectors.baidu_token.validate_baidu_access_token_sync",
        lambda _token: (True, None),
    )
    payload = validate_create_credentials("baidu-netdisk", {"token": "bd_token"})
    assert payload["access_token"] == "bd_token"


def test_extract_baidu_access_token_from_url():
    from octop.infra.connectors.oauth.registry import _extract_baidu_access_token

    assert (
        _extract_baidu_access_token("https://example.com/#access_token=abc123&expires=1")
        == "abc123"
    )


def test_baidu_authorize_url_uses_token_flow():
    from octop.infra.connectors.oauth.registry import authorize_url_for_paste

    class _Settings:
        def get(self, _key: str) -> str:
            return ""

    url = authorize_url_for_paste("baidu-netdisk", _Settings())
    assert url is not None
    assert "response_type=token" in url
    assert "zF5kkNsCvckX4aIpRdHxpFkcSMxnGZky" in url
    assert "force_login=1" in url


def test_mail_provider_netease():
    payload = validate_create_credentials(
        "qq-mail",
        {
            "email": "a@163.com",
            "password": "code",
            "mail_provider": "netease",
        },
    )
    assert payload["imap_host"] == "imap.163.com"
    assert payload["smtp_host"] == "smtp.163.com"


def test_catalog_entry_dict_has_no_tools():
    from octop.infra.connectors.catalog import catalog_entry_to_dict, get_catalog_entry

    entry = get_catalog_entry("tencent-ima")
    assert entry is not None
    data = catalog_entry_to_dict(entry)
    assert "tools" not in data


def test_oauth_ready_notion():
    from octop.infra.connectors.oauth import oauth_ready_for_kind

    class _Settings:
        def get(self, _key: str) -> str:
            return ""

    assert oauth_ready_for_kind("notion", _Settings()) is True
    assert oauth_ready_for_kind("baidu-netdisk", _Settings()) is False
    assert oauth_ready_for_kind("youdao-note", _Settings()) is False


def test_personal_token_meeting():
    payload = validate_create_credentials(
        "tencent-meeting",
        {"token": "meeting-token"},
    )
    assert payload["token"] == "meeting-token"


def test_build_tencent_meeting_remote_spec():
    entry = get_catalog_entry("tencent-meeting")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="x",
        creds={"token": "tok"},
        config=OctopConfig(),
    )
    assert spec["transport"] == "http"
    assert spec["url"] == "https://mcp.meeting.tencent.com/mcp/wemeet-open/v1"
    assert spec["headers"]["X-Tencent-Meeting-Token"] == "tok"
    assert spec["headers"]["X-Skill-Version"] == "v1.0.1"


def test_build_youdao_remote_spec():
    entry = get_catalog_entry("youdao-note")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="x",
        creds={"token": "api-key"},
        config=OctopConfig(),
    )
    assert spec["transport"] == "sse"
    assert spec["url"] == "https://open.mail.163.com/api/ynote/mcp/sse"
    assert spec["headers"]["x-api-key"] == "api-key"


def test_youdao_probe_invalid_api_key(monkeypatch: pytest.MonkeyPatch):
    from contextlib import asynccontextmanager

    import httpx

    from octop.infra.connectors.probe import probe_youdao_note

    class _FakeResponse(httpx.Response):
        def __init__(self) -> None:
            super().__init__(
                401,
                json={"error": 10002, "desc": "get api key info error"},
                request=httpx.Request("GET", "https://open.mail.163.com/api/ynote/mcp/sse"),
            )

    @asynccontextmanager
    async def _failing_sse_client(*_args: object, **_kwargs: object):
        req = httpx.Request("GET", "https://open.mail.163.com/api/ynote/mcp/sse")
        raise httpx.HTTPStatusError("401", request=req, response=_FakeResponse())
        yield  # pragma: no cover

    monkeypatch.setattr("mcp.client.sse.sse_client", _failing_sse_client)

    out = asyncio.run(probe_youdao_note("bad"))
    assert out["ok"] is False
    assert "api key" in out["error"].lower()


def test_probe_youdao_routes_to_sse_probe(monkeypatch: pytest.MonkeyPatch):
    from octop.infra.connectors.probe import probe_connector

    captured: dict[str, str] = {}

    async def _fake(api_key: str) -> dict[str, object]:
        captured["api_key"] = api_key
        return {"ok": True, "tool_count": 1, "tools": [{"name": "list", "description": ""}]}

    monkeypatch.setattr("octop.infra.connectors.probe.probe_youdao_note", _fake)
    entry = get_catalog_entry("youdao-note")
    assert entry is not None

    out = asyncio.run(
        probe_connector(
            entry,
            {"token": "yn-key"},
            instance_id="probe",
            config=OctopConfig(),
        )
    )
    assert captured["api_key"] == "yn-key"
    assert out["ok"] is True


def test_build_tencent_lexiang_remote_spec():
    entry = get_catalog_entry("tencent-lexiang")
    assert entry is not None
    spec = build_http_mcp_spec(
        entry=entry,
        instance_id="x",
        creds={"api_key": "lx-tok", "company_from": "csig"},
        config=OctopConfig(),
    )
    assert spec["url"] == "https://mcp.lexiang-app.com/mcp?company_from=csig"
    assert spec["headers"]["Authorization"] == "Bearer lx-tok"


def test_tencent_lexiang_credentials():
    payload = validate_create_credentials(
        "tencent-lexiang",
        {"api_key": "lx-tok", "client_id": "csig"},
    )
    assert payload == {"api_key": "lx-tok", "company_from": "csig"}


def test_connector_repo_user_kind_unique(db: DBPool):
    repo = ConnectorRepo(db)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, 0)",
            ("u", "h", "user"),
        )
        uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    iid = new_ulid()
    repo.create(
        instance_id=iid,
        user_id=uid,
        kind="tencent-docs",
        display_name="doc",
        mcp_server_name=mcp_server_name("tencent-docs", iid),
    )
    repo.upsert_credentials(instance_id=iid, blob=b"enc", expires_at=None)
    mcp_name = mcp_server_name("tencent-docs", iid)
    assert repo.validate_mcp_servers_for_user(uid, [mcp_name]) == [mcp_name]
    with pytest.raises(ValueError):
        repo.validate_mcp_servers_for_user(uid, ["other"])


def test_validate_mcp_servers_for_user(db: DBPool):
    repo = ConnectorRepo(db)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, 0)",
            ("u2", "h", "user"),
        )
        uid = conn.execute("SELECT id FROM users WHERE username = 'u2'").fetchone()["id"]
    iid = new_ulid()
    mcp_name = mcp_server_name("tencent-docs", iid)
    repo.create(
        instance_id=iid,
        user_id=uid,
        kind="tencent-docs",
        display_name="doc",
        mcp_server_name=mcp_name,
    )
    repo.upsert_credentials(instance_id=iid, blob=b"enc", expires_at=None)
    assert repo.validate_mcp_servers_for_user(uid, [mcp_name]) == [mcp_name]
    with pytest.raises(ValueError):
        repo.validate_mcp_servers_for_user(uid, ["other"])
