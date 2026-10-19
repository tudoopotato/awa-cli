"""文章采集业务编排。"""

from awa.services.capture.capture_runtime_factory import CaptureRuntimeFactory
from awa.services.capture.html_parse_save_service import (
    ArticleSaveData,
    HtmlParseSaveService,
)
from awa.services.capture.window_runtime_factory import WindowRuntimeFactory

__all__ = [
    "ArticleSaveData",
    "CaptureRuntimeFactory",
    "HtmlParseSaveService",
    "WindowRuntimeFactory",
]
