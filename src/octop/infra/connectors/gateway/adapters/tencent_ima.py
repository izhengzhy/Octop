"""Tencent IMA notes and knowledge base gateway."""

from __future__ import annotations

import json
from typing import Any

import httpx

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_notes",
        "description": "List recent IMA notes (no search keyword required)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder_id": {
                    "type": "string",
                    "description": "Optional notebook ID; omit to list across all notebooks",
                },
                "cursor": {
                    "type": "string",
                    "description": 'Pagination cursor; use "" for the first page',
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results per page (1-20), default 20",
                },
            },
        },
    },
    {
        "name": "search_notes",
        "description": "Search notes by title or content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword"},
                "start": {"type": "integer", "description": "Start offset, default 0"},
                "end": {"type": "integer", "description": "End offset, default 20"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_knowledge_bases",
        "description": "List IMA knowledge bases",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results, default 50"},
            },
        },
    },
    {
        "name": "search_knowledge",
        "description": "Search content inside a knowledge base",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "knowledge_base_id": {"type": "string"},
                "limit": {"type": "integer", "description": "Max results, default 10"},
            },
            "required": ["query"],
        },
    },
]


def list_tools() -> list[dict[str, Any]]:
    return TOOLS


def call_tool(creds: dict[str, Any], name: str, args: dict[str, Any]) -> str:
    if name == "list_notes":
        folder_id = str(args.get("folder_id") or "").strip()
        cursor = str(args.get("cursor") if args.get("cursor") is not None else "")
        limit = int(args.get("limit") or 20)
        limit = max(1, min(limit, 20))
        body: dict[str, Any] = {"cursor": cursor, "limit": limit}
        if folder_id:
            body["folder_id"] = folder_id
        return _openapi(creds, "openapi/note/v1/list_note", body)
    if name == "search_notes":
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        start = int(args.get("start") or 0)
        end = int(args.get("end") or 20)
        return _openapi(
            creds,
            "openapi/note/v1/search_note",
            {
                "search_type": 0,
                "query_info": {"title": query},
                "start": start,
                "end": end,
            },
        )
    if name == "list_knowledge_bases":
        limit = int(args.get("limit") or 50)
        return _openapi(
            creds,
            "openapi/wiki/v1/search_knowledge_base",
            {"limit": limit},
        )
    if name == "search_knowledge":
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        body = {
            "query": query,
            "limit": int(args.get("limit") or 10),
        }
        kbase = str(args.get("knowledge_base_id") or "").strip()
        if kbase:
            body["knowledge_base_id"] = kbase
        return _openapi(creds, "openapi/wiki/v1/search_knowledge", body)
    raise ValueError(f"unknown IMA tool: {name}")


def _headers(creds: dict[str, Any]) -> dict[str, str]:
    client_id = str(creds.get("client_id") or "").strip()
    api_key = str(creds.get("api_key") or "").strip()
    if not client_id or not api_key:
        raise ValueError("IMA client_id and api_key are required")
    return {
        "ima-openapi-clientid": client_id,
        "ima-openapi-apikey": api_key,
        "Content-Type": "application/json",
        "User-Agent": "octop-connector/0.1",
    }


def _openapi(creds: dict[str, Any], path: str, body: dict[str, Any]) -> str:
    url = f"https://ima.qq.com/{path.lstrip('/')}"
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, headers=_headers(creds), json=body)
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=2)
    return str(data)
