"""v2.1 配置对象、系统 YAML 默认值、加载和校验。"""

from awa.config.app_config import AppConfig
from awa.config.config_loader import load_app_config

__all__ = ["AppConfig", "load_app_config"]
