"""CLI 统一输出契约：stdout 只输出单个 JSON，进度与日志走 stderr。"""

from __future__ import annotations

import json
import sys
from typing import Any

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_PRECONDITION = 2
EXIT_USAGE = 3


def _dump(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_ok(command: str, status: str = "ok", **fields: Any) -> None:
    """向 stdout 输出一个成功的 JSON 文档。"""

    payload: dict[str, Any] = {"ok": True, "command": command, "status": status}
    payload.update(fields)
    _dump(payload)


def emit_error(command: str, status: str, message: str, **fields: Any) -> None:
    """向 stdout 输出一个失败的 JSON 文档。"""

    payload: dict[str, Any] = {
        "ok": False,
        "command": command,
        "status": status,
        "message": message,
    }
    payload.update(fields)
    _dump(payload)


def progress(text: str) -> None:
    """向 stderr 输出一行人类可读进度。"""

    sys.stderr.write(f"[awa] {text}\n")
    sys.stderr.flush()


def warn(text: str) -> None:
    """向 stderr 输出一行人类可读告警。"""

    sys.stderr.write(f"[awa][warn] {text}\n")
    sys.stderr.flush()


__all__ = [
    "EXIT_FAILED",
    "EXIT_OK",
    "EXIT_PRECONDITION",
    "EXIT_USAGE",
    "emit_error",
    "emit_ok",
    "progress",
    "warn",
]
