"""Agent backend configuration — Octop DB rows → harness specs + probes.

- :mod:`adapter` — ``storage_backends`` row → harness spec (no I/O)
- :mod:`resolver` — agent config ``named`` / ``composite`` expansion
- :mod:`probe` — admin connectivity checks (delegates round-trip to harness-agent)
"""

from octop.infra.backend.adapter import row_to_backend_spec
from octop.infra.backend.probe import probe_storage_backend
from octop.infra.backend.resolver import resolve_agent_backend_spec

__all__ = [
    "probe_storage_backend",
    "resolve_agent_backend_spec",
    "row_to_backend_spec",
]
