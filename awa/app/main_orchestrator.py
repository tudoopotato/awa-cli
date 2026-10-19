from __future__ import annotations

from dataclasses import dataclass
import multiprocessing
from pathlib import Path
from typing import Any

from awa.config.app_config import AppConfig
from awa.services.capture.capture_runtime_factory import CaptureRuntimeFactory
from awa.services.capture.single_article_capture_service import SingleCaptureSettings
from awa.services.capture.window_runtime_factory import WindowRuntimeFactory
from awa.services.config.config_service import ConfigService
from awa.services.runtime.database_write_coordinator import DatabaseWriteCoordinator


@dataclass(frozen=True, slots=True)
class ApplicationRuntime:
    """应用启动后共享的只读配置和由配置装配出的运行组件。"""

    config_service: ConfigService | Any
    config: AppConfig
    window_factory: WindowRuntimeFactory
    capture_factory: CaptureRuntimeFactory
    single_capture_settings: SingleCaptureSettings
    database_write_coordinator: DatabaseWriteCoordinator


def load_application_runtime(
    *,
    home: str | Path,
    config_path: str | Path | None = None,
) -> ApplicationRuntime:
    """启动阶段合并 system.yaml 与 custom.yaml，并生成共享运行时上下文。"""
    config_service = ConfigService(
        home=home,
        config_path=config_path,
    )
    return build_application_runtime(
        config_service=config_service,
        config=config_service.current,
    )


def build_application_runtime(
    *,
    config_service: ConfigService | Any,
    config: AppConfig,
) -> ApplicationRuntime:
    """根据内存配置重建运行时对象；用于配置保存后刷新主流程上下文。"""
    window_factory = WindowRuntimeFactory(config)
    process_context = multiprocessing.get_context("spawn")
    write_coordinator = DatabaseWriteCoordinator(context=process_context)
    return ApplicationRuntime(
        config_service=config_service,
        config=config,
        window_factory=window_factory,
        capture_factory=CaptureRuntimeFactory(
            config,
            window_factory=window_factory,
        ),
        single_capture_settings=SingleCaptureSettings.from_app_config(config),
        database_write_coordinator=write_coordinator,
    )


__all__ = [
    "ApplicationRuntime",
    "build_application_runtime",
    "load_application_runtime",
]
