"""CLI 参数解析与退出码的最小回归测试。

全部用例都不依赖微信窗口、MITM 或浏览器：

- 参数错误类用例只经过 argparse 语法与日期校验，不会装配运行时；
- 合法的 crawl 用例通过打桩 ``commands.run_crawl`` 避免真实采集；
- articles 用例在 tmp 目录内自行初始化 SQLite 库，不触碰真实 AWA_HOME。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """以子进程运行 ``python -m awa``，真实覆盖退出码；强制 UTF-8 便于读取中文输出。"""

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "awa", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _init_database(home: Path) -> None:
    """在指定 home 下初始化 SQLite 库（纯本地文件与 SQLite 操作，无外部依赖）。"""

    from awa.app.main_orchestrator import load_application_runtime
    from awa.services.runtime.database_init_service import DatabaseInitService

    runtime = load_application_runtime(home=home)
    DatabaseInitService().initialize(runtime.config)


def test_articles_success_exit_code(tmp_path: Path) -> None:
    """验证点：articles 在库存在时返回退出码 0，且 stdout 为合法 JSON、ok 为 True。"""

    home = tmp_path / "home"
    home.mkdir()
    _init_database(home)

    result = _run_cli("articles", "--limit", "1", "--home", str(home))

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "articles"
    assert payload["articleCount"] == 0


def test_unknown_command_exit_code() -> None:
    """验证点：未知子命令触发用法错误，退出码为 3，stdout JSON 的 ok 为 False。"""

    result = _run_cli("bogus")

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "usage-error"


def test_crawl_range_missing_end_exit_code() -> None:
    """验证点：date-mode=range 缺少 --end 时被判为参数错误，退出码为 3。"""

    result = _run_cli("crawl", "--date-mode", "range", "--start", "2026-01-01")

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "usage-error"


def test_crawl_valid_range_not_usage_error(tmp_path: Path, monkeypatch, capsys) -> None:
    """验证点：合法的 range 参数通过参数校验，不会返回用法错误码 3。

    为避免依赖真实微信窗口（本机可能正开着公众号主页、会触发真实点击采集），
    这里直接调用 ``awa.cli.main.main()``，并把 ``commands.run_crawl`` 打桩为
    立即返回 0 的假实现，只验证「参数解析 + 日期校验 + 分发参数」这一层。
    """

    from awa.cli import commands
    from awa.cli import main as cli_main
    from awa.cli import output

    seen: dict = {}

    def fake_run_crawl(**kwargs):
        seen.update(kwargs)
        output.emit_ok("crawl", status="completed", taskId="stub-task")
        return output.EXIT_OK

    monkeypatch.setattr(commands, "run_crawl", fake_run_crawl)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "awa",
            "crawl",
            "--date-mode",
            "range",
            "--start",
            "2026-01-01",
            "--end",
            "2026-02-01",
            "--home",
            str(tmp_path / "home"),
        ],
    )

    code = cli_main.main()

    assert code != output.EXIT_USAGE
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert seen["date_mode"] == "range"
    assert seen["start"] == "2026-01-01"
    assert seen["end"] == "2026-02-01"
