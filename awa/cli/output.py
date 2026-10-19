"""CLI 统一输出契约：stdout 只输出单个 JSON，进度与日志走 stderr。"""

from __future__ import annotations

import json
import sys
from typing import Any

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_PRECONDITION = 2
EXIT_USAGE = 3


def ensure_utf8_streams() -> None:
    """把 stdout/stderr 切换到 UTF-8，保证中文输出在任何区域设置下都不报错。

    Windows 控制台本身已是 UTF-8（PEP 528），但输出被重定向到文件或管道时，
    Python 会退回系统区域编码（英文系统通常是 cp1252），此时打印中文帮助或
    JSON 会抛 UnicodeEncodeError；这里统一为 UTF-8，与文档约定一致。
    """

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # 流已被替换或不可重配置时保持原样，不影响命令继续执行。
            pass


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
    "ensure_utf8_streams",
    "progress",
    "warn",
]
