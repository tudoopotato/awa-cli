"""AWA_HOME（用户数据目录）定位与初始化。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_home(cli_home: str | Path | None = None) -> Path:
    """解析 AWA_HOME 绝对路径。

    优先级：``cli_home`` 参数 > 环境变量 ``AWA_HOME`` > Windows 的
    ``%LOCALAPPDATA%\\awa``（``LOCALAPPDATA`` 缺失时退回 ``~\\AppData\\Local\\awa``）
    > 其他平台的 ``~/.awa``。
    """

    if cli_home is not None and str(cli_home).strip():
        return Path(cli_home).expanduser().resolve()

    env_home = os.environ.get("AWA_HOME")
    if env_home and env_home.strip():
        return Path(env_home).expanduser().resolve()

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data and local_app_data.strip():
            return (Path(local_app_data).expanduser() / "awa").resolve()
        return (Path.home() / "AppData" / "Local" / "awa").resolve()

    return (Path.home() / ".awa").resolve()


def ensure_home(home: str | Path) -> Path:
    """创建并返回 AWA_HOME 目录，同时确保必需的子目录存在。"""

    path = Path(home).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    for relative in ("data/sql", "data/logs", "data/tmp", "storages", ".mitmproxy"):
        (path / relative).mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["ensure_home", "resolve_home"]
