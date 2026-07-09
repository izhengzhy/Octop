"""Resolved model list across enabled providers."""

from __future__ import annotations

from typing import Any


def list_resolved_models(providers: list[Any]) -> list[dict[str, Any]]:
    """Return enabled models for providers that have credentials configured."""
    resolved: list[dict[str, Any]] = []
    for provider in providers:
        if not provider.enabled or not provider.api_key:
            continue
        for m in provider.get_models():
            if not m.get("enabled", True):
                continue
            resolved.append(
                {
                    "provider_id": provider.id,
                    "provider_name": provider.name,
                    "provider_kind": provider.kind,
                    "model": m["id"],
                    "name": m.get("name") or m["id"],
                    "input": m.get("input") or ["text"],
                    "reasoning": m.get("reasoning"),
                    "context_window": m.get("context_window"),
                    "max_tokens": m.get("max_tokens"),
                    "max_input_tokens": m.get("context_window"),
                }
            )
    return resolved
