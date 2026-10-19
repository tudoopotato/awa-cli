"""无 HTTP、无 UI 的 headless 采集运行时装配。

装配顺序与参数取值均对齐开发期后端的 ``create_dev_backend``，但剔除了所有
界面、诊断与资源监控组件，只保留命令行采集所需的服务。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from awa.app.main_orchestrator import ApplicationRuntime, load_application_runtime
from awa.cli.home import ensure_home
from awa.services.main_flow.home_scan_service import HomeScanService
from awa.services.main_flow.main_flow_factory import build_main_flow_service
from awa.services.runtime.database_init_service import DatabaseInitService
from awa.services.runtime.runtime_directory_service import RuntimeDirectoryService
from awa.services.runtime.runtime_log_service import RuntimeLogService
from awa.services.task.article_detail_comments_huey_service import (
    ArticleDetailCommentsHueyService,
)
from awa.services.task.article_detail_offline_cache_huey_service import (
    ArticleDetailOfflineCacheHueyService,
)
from awa.services.task.huey_runtime_queue import reset_runtime_huey_queue_dir
from awa.services.task.initial_content_storage_huey_service import (
    InitialContentStorageHueyService,
)


class HeadlessRuntime:
    """无 HTTP、无 UI 的采集运行时。"""

    def __init__(
        self,
        *,
        home: str | Path,
        config_path: str | Path | None = None,
    ) -> None:
        self.home = ensure_home(home)
        self.config_path = config_path
        self.runtime: ApplicationRuntime | None = None
        self.config: Any | None = None
        self.db_path: Path | None = None
        self.runtime_logger: RuntimeLogService | None = None
        self._foreground_service: InitialContentStorageHueyService | None = None
        self._detail_service: InitialContentStorageHueyService | None = None
        self._comments_service: ArticleDetailCommentsHueyService | None = None
        self._offline_service: ArticleDetailOfflineCacheHueyService | None = None
        self._main_flow_service: Any | None = None
        self._dispatcher: Any | None = None
        self._shutdown_done = False

    def prepare(self) -> "HeadlessRuntime":
        """按启动顺序装配配置、目录、数据库、日志与 Huey 队列。"""

        self.runtime = load_application_runtime(
            home=self.home,
            config_path=self.config_path,
        )
        self.config = self.runtime.config
        RuntimeDirectoryService().prepare(self.config)
        self.db_path = DatabaseInitService().initialize(self.config)
        self.runtime_logger = RuntimeLogService(
            log_dir=self.config.storage.log_dir,
            level=self.config.runtime.log_level,
        )
        reset_runtime_huey_queue_dir(self.config.storage.temp_dir)
        return self

    def build_main_flow(
        self,
        *,
        comments: bool = False,
        offline: bool = False,
    ) -> tuple[Any, Any]:
        """构造前台/详情 Huey 服务并装配主流程，返回 (service, dispatcher)。

        ``comments`` / ``offline`` 为真时按 ``create_dev_backend`` 中主服务实例的
        参数逐项对齐构造对应 Huey 服务；为假时对应参数传 ``None``，主流程不会
        采集评论、也不会做离线归档。
        """

        self._ensure_prepared()
        foreground_service = InitialContentStorageHueyService(
            temp_root=self.config.storage.temp_dir,
            config=self.config,
            window_factory=self.runtime.window_factory,
            capture_factory=self.runtime.capture_factory,
            database_path=self.db_path,
            write_coordinator=self.runtime.database_write_coordinator,
            worker_count=1,
            job_prefix="main-flow-foreground",
            queue_name="main-flow-foreground",
            task_name="MainFlowForegroundTask",
            action="main-flow-foreground",
            title="主服务单篇前台结果",
            flow_label="主服务单篇前台捕获",
        )
        detail_service = InitialContentStorageHueyService(
            temp_root=self.config.storage.temp_dir,
            config=self.config,
            window_factory=self.runtime.window_factory,
            capture_factory=self.runtime.capture_factory,
            database_path=self.db_path,
            write_coordinator=self.runtime.database_write_coordinator,
            worker_count=2,
            job_prefix="main-flow-detail",
            queue_name="main-flow-detail",
            task_name="MainFlowDetailTask",
            action="main-flow-detail",
            title="主服务单篇详情结果",
            flow_label="主服务单篇详情",
        )
        comments_service = None
        if comments:
            comments_service = ArticleDetailCommentsHueyService(
                temp_root=self.config.storage.temp_dir,
                config=self.config,
                window_factory=self.runtime.window_factory,
                capture_factory=self.runtime.capture_factory,
                database_path=self.db_path,
                write_coordinator=self.runtime.database_write_coordinator,
                worker_count=self.config.comment.max_concurrent_processes,
            )
        offline_service = None
        if offline:
            offline_service = ArticleDetailOfflineCacheHueyService(
                temp_root=self.config.storage.temp_dir,
                config=self.config,
                window_factory=self.runtime.window_factory,
                capture_factory=self.runtime.capture_factory,
                database_path=self.db_path,
                browser_cache_dir=self.home / ".playwright-browsers",
                write_coordinator=self.runtime.database_write_coordinator,
                worker_count=self.config.offline_cache.max_concurrent_processes,
            )
        self._foreground_service = foreground_service
        self._detail_service = detail_service
        self._comments_service = comments_service
        self._offline_service = offline_service
        service, dispatcher = build_main_flow_service(
            project_root=self.home,
            config=self.config,
            db_path=self.db_path,
            storage_root=self.config.storage.article_storage_root,
            temp_root=self.config.storage.temp_dir,
            window_factory=self.runtime.window_factory,
            foreground_service=foreground_service,
            detail_service=detail_service,
            comments_service=comments_service,
            offline_service=offline_service,
            runtime_logger=self.runtime_logger,
        )
        self._main_flow_service = service
        self._dispatcher = dispatcher
        return service, dispatcher

    def build_scan_service(self) -> HomeScanService:
        """只读扫描服务，不装配任何 Huey 服务。"""

        self._ensure_prepared()
        return HomeScanService(
            window_factory=self.runtime.window_factory,
            config=self.config,
            trace=None,
        )

    def shutdown(self) -> None:
        """安全释放已装配的服务；重复调用幂等。"""

        if self._shutdown_done:
            return
        self._shutdown_done = True
        main_flow_service = self._main_flow_service
        if main_flow_service is not None:
            try:
                main_flow_service.shutdown()
            except Exception:
                pass
        for service in (
            self._foreground_service,
            self._detail_service,
            self._comments_service,
            self._offline_service,
        ):
            if service is None:
                continue
            try:
                service.shutdown()
            except Exception:
                pass

    def _ensure_prepared(self) -> None:
        if self.runtime is None or self.config is None or self.db_path is None:
            raise RuntimeError("请先调用 HeadlessRuntime.prepare()")


__all__ = ["HeadlessRuntime"]
