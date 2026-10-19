from __future__ import annotations

from pathlib import Path

from awa.config.app_config import AppConfig
from awa.storage.sqlite.database_initializer import DatabaseInitializer
from awa.storage.sqlite.schema_loader import load_schema


class DatabaseInitService:
    """只在程序启动阶段初始化或验证当前版本数据库。"""

    def initialize(self, config: AppConfig) -> Path:
        schema = load_schema(config.software.data_schema_version)
        return DatabaseInitializer().initialize(
            config.storage.database_path,
            schema.sql,
        )
