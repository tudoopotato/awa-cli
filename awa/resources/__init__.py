"""包内只读资源定位（默认系统配置与建表脚本）。

wheel 正常安装时 ``importlib.resources.files`` 指向解包后的真实目录，
因此可以安全地转成 ``Path``；源码开发态同样是真实文件路径。
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def resources_dir() -> Path:
    """返回 ``awa/resources`` 目录的真实文件系统路径。"""

    return Path(str(files("awa.resources")))


def default_system_config_path() -> Path:
    """返回打包内置的默认系统配置 ``system.yaml``。"""

    return resources_dir() / "system.yaml"


def schema_dir() -> Path:
    """返回内置建表脚本目录。"""

    return resources_dir() / "schema"


__all__ = ["default_system_config_path", "resources_dir", "schema_dir"]
