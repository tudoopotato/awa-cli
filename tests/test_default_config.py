"""包内默认配置（awa/resources/system.yaml）加载与校验的最小测试。"""

from __future__ import annotations

from pathlib import Path

from awa.config.config_loader import load_system_app_config
from awa.config.config_validator import validate_app_config
from awa.resources import default_system_config_path


def test_default_system_config_loads_and_validates(tmp_path: Path) -> None:
    """验证点：加载包内 system.yaml 得到 AppConfig 并通过 validate_app_config，关键字段存在。"""

    system_path = default_system_config_path()
    assert system_path.is_file()

    config = load_system_app_config(system_path, home_root=tmp_path)

    # 显式再校验一次，确认默认配置满足全部约束。
    validate_app_config(config)

    assert config.software.data_schema_version == "v2.1"
    assert config.proxy.host == "127.0.0.1"
    assert config.proxy.port == 18000

    assert config.storage.article_storage_root == (Path(tmp_path) / "storages").resolve()
    assert config.storage.db_dir == (Path(tmp_path) / "data" / "sql").resolve()
    assert config.storage.temp_dir == (Path(tmp_path) / "data" / "tmp").resolve()
    assert config.storage.log_dir == (Path(tmp_path) / "data" / "logs").resolve()
    assert config.storage.database_path.name == "awa-v2.1.sqlite3"
    assert config.proxy.confdir == (Path(tmp_path) / ".mitmproxy").resolve()


def test_config_service_uses_defaults_in_empty_home(tmp_path: Path) -> None:
    """验证点：空 home 下 ConfigService 仅凭系统默认配置即可得到通过校验的 AppConfig。"""

    from awa.services.config.config_service import ConfigService

    service = ConfigService(home=tmp_path)
    config = service.current

    validate_app_config(config)
    assert config.proxy.port == 18000
    assert config.storage.db_dir == (Path(tmp_path) / "data" / "sql").resolve()
    assert config.storage.database_path.name == "awa-v2.1.sqlite3"
