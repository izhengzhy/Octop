"""Cross-platform non-blocking reads from subprocess stdout pipes."""

from __future__ import annotations

import errno
import json
import os
from typing import IO, Any

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]


def read_available_bytes(stream: IO[bytes]) -> bytes:
    """Read whatever is currently buffered on *stream* without blocking."""
    if stream is None:
        return b""
    if os.name == "nt":
        return _read_available_windows(stream)
    return _read_available_posix(stream)


def _read_available_posix(stream: IO[bytes]) -> bytes:
    import fcntl

    fd = stream.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    try:
        return os.read(fd, 65536)
    except OSError as exc:
        if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
            return b""
        raise
    finally:
        fcntl.fcntl(fd, fcntl.F_SETFL, flags)


def _read_available_windows(stream: IO[bytes]) -> bytes:
    handle = msvcrt.get_osfhandle(stream.fileno())  # type: ignore[attr-defined]
    avail = wintypes.DWORD()
    ok = _kernel32.PeekNamedPipe(
        handle,
        None,
        0,
        None,
        ctypes.byref(avail),
        None,
    )
    if not ok or avail.value == 0:
        return b""
    return stream.read(avail.value)


def parse_json_lines(raw: bytes) -> list[dict[str, Any]]:
    """Decode newline-delimited JSON objects from subprocess stdout."""
    lines: list[dict[str, Any]] = []
    if not raw:
        return lines
    text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            lines.append({"action": "log", "level": "info", "step": "raw", "message": line})
        else:
            if isinstance(parsed, dict):
                lines.append(parsed)
            else:
                lines.append({"action": "log", "level": "info", "step": "raw", "message": line})
    return lines


def parse_subprocess_json_lines(proc: Any) -> list[dict[str, Any]]:
    """Non-blocking read of stdout JSON lines from a running subprocess."""
    if proc.stdout is None:
        return []
    return parse_json_lines(read_available_bytes(proc.stdout))
