"""Tencent News search gateway."""

from __future__ import annotations

import json
from typing import Any

import httpx

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_news",
        "description": "Search Tencent News articles by keyword",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "description": "Max results, default 10"},
                "max_results": {
                    "type": "integer",
                    "description": "Alias of limit, default 10",
                },
            },
            "required": ["query"],
        },
    },
]


def list_tools() -> list[dict[str, Any]]:
    return TOOLS


def call_tool(creds: dict[str, Any], name: str, args: dict[str, Any]) -> str:
    if name == "search_news":
        return search_news(creds, args)
    raise ValueError(f"unknown tool: {name}")


def search_news(creds: dict[str, Any], args: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    limit = int(args.get("limit") or args.get("max_results") or 10)
    if not query:
        raise ValueError("query is required")
    cookie = str(creds.get("cookie") or creds.get("api_key") or "")
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (octop-connector/0.1)",
        "Referer": "https://news.qq.com/",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "page": "0",
        "query": query,
        "is_pc": "1",
        "hippy_custom_version": "25",
        "search_type": "all",
        "search_count_limit": str(limit),
        "appver": "15.5_qqnews_7.1.80",
    }
    url = "https://i.news.qq.com/gw/pc_search/result"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=headers, data=data)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False, indent=2)
