"""AWA_HOME 解析优先级的最小测试：``--home`` > 环境变量 ``AWA_HOME`` > 平台默认。"""

from __future__ import annotations

import sys

from awa.cli.home import resolve_home


def test_cli_home_wins_over_env(tmp_path, monkeypatch) -> None:
    """验证点：显式传入的 cli_home（--home）优先级高于环境变量 AWA_HOME。"""

    env_home = tmp_path / "env-home"
    cli_home = tmp_path / "cli-home"
    monkeypatch.setenv("AWA_HOME", str(env_home))

    assert resolve_home(str(cli_home)) == cli_home.resolve()


def test_env_home_used_when_no_cli(tmp_path, monkeypatch) -> None:
    """验证点：未传 --home 时使用环境变量 AWA_HOME。"""

    env_home = tmp_path / "env-home"
    monkeypatch.setenv("AWA_HOME", str(env_home))

    assert resolve_home(None) == env_home.resolve()


def test_platform_default_when_no_cli_no_env(tmp_path, monkeypatch) -> None:
    """验证点：既无 --home 也无 AWA_HOME 时，Windows 回退到 %LOCALAPPDATA%\\awa。"""

    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.delenv("AWA_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setattr(sys, "platform", "win32")

    assert resolve_home(None) == (local_app_data / "awa").resolve()
