"""CLI 子命令实现。

``doctor``（环境自检 + CA 检查/安装）、``scan``（只读预览）、``crawl``（执行采集）与
``articles``（只读查询已入库文章）四个子命令的实现均在此模块。
"""

from __future__ import annotations

from awa.cli import output
from awa.cli.home import resolve_home


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def _check_storage_dirs(config) -> dict:
    import os
    from pathlib import Path

    dirs = {
        "article_storage_root": Path(config.storage.article_storage_root),
        "db_dir": Path(config.storage.db_dir),
        "temp_dir": Path(config.storage.temp_dir),
        "log_dir": Path(config.storage.log_dir),
    }
    problems: list[str] = []
    for name, path in dirs.items():
        if not path.is_dir():
            problems.append(f"{name} 目录不存在：{path}")
            continue
        probe = path / f".awa-doctor-probe-{os.getpid()}"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            problems.append(f"{name} 目录不可写：{path}（{exc}）")

    detail = "存储目录：" + "；".join(f"{name}={path}" for name, path in dirs.items())
    if problems:
        detail += "；问题：" + "；".join(problems)
        ok = False
    else:
        detail += "；四个目录均存在且可写。"
        ok = True
    return {
        "name": "storage_dirs",
        "ok": ok,
        "detail": detail,
        "dirs": {name: str(path) for name, path in dirs.items()},
    }


def _check_database(db_path) -> dict:
    from awa.storage.sqlite.database_initializer import REQUIRED_TABLES, validate_database

    tables = ", ".join(REQUIRED_TABLES)
    base = f"dbPath={db_path}；必需表={tables}"
    try:
        validate_database(db_path)
    except Exception as exc:  # noqa: BLE001 - 校验失败不应中断 doctor
        return {
            "name": "database",
            "ok": False,
            "detail": f"{base}；校验失败：{exc}",
            "dbPath": str(db_path),
            "requiredTables": list(REQUIRED_TABLES),
        }
    return {
        "name": "database",
        "ok": True,
        "detail": f"{base}；校验通过。",
        "dbPath": str(db_path),
        "requiredTables": list(REQUIRED_TABLES),
    }


def _check_mitm_port(config) -> dict:
    import socket

    host = str(config.proxy.host)
    port = int(config.proxy.port)
    address = f"{host}:{port}"
    try:
        with socket.create_connection((host, port), timeout=1.0):
            occupied = True
    except OSError:
        occupied = False

    if occupied:
        return {
            "name": "mitm_port",
            "ok": False,
            "detail": f"端口 {address} 已被占用，请关闭占用进程后重试。",
            "address": address,
            "occupied": True,
        }
    return {
        "name": "mitm_port",
        "ok": True,
        "detail": f"端口 {address} 空闲，可用于本地 MITM。",
        "address": address,
        "occupied": False,
    }


def _check_ca(config, *, install_ca: bool) -> dict:
    from awa.cli.ca import ca_status
    from awa.cli.ca import install_ca as do_install_ca

    ca_path = config.proxy.ca_cert_path
    status = ca_status(ca_path)
    if install_ca and status.get("status") == "file-present":
        output.progress("CA 证书文件存在但未安装，正在执行安装……")
        install_result = do_install_ca(ca_path)
        if install_result.get("ok"):
            output.progress("CA 证书安装命令执行成功，正在复检……")
        else:
            output.warn(f"CA 证书安装失败：{install_result.get('message')}")
        status = ca_status(ca_path)

    installed = bool(status.get("installed"))
    detail = str(status.get("message") or "")
    if not installed:
        if status.get("status") == "missing":
            detail += (
                " 首次运行采集时 mitmproxy 会自动生成 CA 证书，"
                "生成后再执行 `awa doctor --install-ca` 安装。"
            )
        else:
            detail += " 可执行 `awa doctor --install-ca` 安装。"
    return {
        "name": "ca_certificate",
        "ok": installed,
        "detail": detail,
        "status": status.get("status"),
        "message": status.get("message"),
        "caPath": status.get("caPath"),
        "thumbprint": status.get("thumbprint"),
        "installed": installed,
        "storeCertificateCount": status.get("storeCertificateCount"),
    }


def _home_window_has_date_groups(window_factory, window, config) -> bool:
    """深度校验：激活窗口后能否读到主页的文章日期分组。

    标题命中只是候选，只有真正能读到 UIA 日期分组时才认为当前窗口是公众号主页。
    调用方式与 ``HomeScanService.initialize()`` 一致：
    ``create_home_guard().activate(window)`` → 按配置等待 → ``create_window_test_reader()``
    → ``read_date_groups(window)``。
    """

    import time

    guard_factory = getattr(window_factory, "create_home_guard", None)
    if callable(guard_factory):
        try:
            guard = guard_factory()
            activate = getattr(guard, "activate", None)
            if callable(activate):
                activate(window)
                wait_seconds = float(
                    getattr(
                        getattr(config, "window", None),
                        "activation_wait_seconds",
                        0.0,
                    )
                    or 0.0
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
        except Exception:  # noqa: BLE001 - 激活失败仍继续尝试读取
            pass

    reader_factory = getattr(window_factory, "create_window_test_reader", None)
    if not callable(reader_factory):
        return False
    try:
        reader = reader_factory()
        snapshot = reader.read_date_groups(window)
    except Exception:  # noqa: BLE001 - 读取失败即判定不是公众号主页
        return False
    groups = tuple(getattr(snapshot, "groups", ()) or ())
    visible_groups = tuple(getattr(snapshot, "visible_groups", ()) or ())
    return bool(groups or visible_groups)


def _is_home_unavailable_message(message: str) -> bool:
    """错误信息是否指向「公众号主页不可用」。

    只匹配主页 / 日期组相关特征，避免把无关异常误判为 window-not-found。
    """

    text = str(message or "")
    if "公众号主页" in text:
        return True
    if "日期组" in text:
        return True
    return "未找到" in text and "主页" in text


def _check_home_window(runtime, config) -> tuple[dict, str | None]:
    from awa.modules.window.wechat_home_window_finder import (
        WechatHomeWindowFindTimeout,
        WechatHomeWindowMinimized,
    )

    window_factory = runtime.runtime.window_factory
    find_timeout = float(config.window.home_find_timeout_seconds)
    try:
        reader = window_factory.create_reader()
        window = window_factory.find_home_window(
            reader=reader,
            timeout_seconds=find_timeout,
        )
    except WechatHomeWindowMinimized as exc:
        handle = getattr(getattr(exc, "window", None), "handle", None)
        return (
            {
                "name": "wechat_home_window",
                "ok": False,
                "detail": "检测到公众号主页窗口处于最小化状态，请在微信中恢复（还原）公众号主页窗口后重试。",
                "windowHandle": handle,
            },
            None,
        )
    except WechatHomeWindowFindTimeout as exc:
        return (
            {
                "name": "wechat_home_window",
                "ok": False,
                "detail": f"查找公众号主页窗口超时：{exc}。请在微信中打开公众号主页后重试。",
            },
            None,
        )
    except Exception as exc:  # noqa: BLE001 - 查找失败不能中断 doctor
        return (
            {
                "name": "wechat_home_window",
                "ok": False,
                "detail": (
                    f"查找公众号主页窗口失败：{type(exc).__name__}: {exc}。"
                    "请在微信中打开公众号主页后重试。"
                ),
            },
            None,
        )

    if window is None:
        return (
            {
                "name": "wechat_home_window",
                "ok": False,
                "detail": "未找到公众号主页窗口。请在微信中打开公众号主页后重试。",
            },
            None,
        )

    title = str(getattr(window, "title", "") or "")
    handle = int(getattr(window, "handle", 0) or 0)

    # 深度校验：标题命中只是候选，必须真正读到文章日期分组才算公众号主页。
    if not _home_window_has_date_groups(window_factory, window, config):
        return (
            {
                "name": "wechat_home_window",
                "ok": False,
                "detail": (
                    "当前窗口不是公众号主页（未读到文章日期分组）。"
                    "请在微信中打开目标公众号主页后重试。"
                ),
                "windowTitle": title,
                "windowHandle": handle,
            },
            None,
        )

    account_name: str | None = None
    try:
        info = window_factory.create_home_reader().read(window)
        account_name = str(getattr(info, "account_name", "") or "").strip() or None
    except Exception:  # noqa: BLE001 - 公众号名称仅作附加信息
        account_name = None

    check = {
        "name": "wechat_home_window",
        "ok": True,
        "detail": (
            f"已定位公众号主页窗口：标题「{title}」，窗口句柄 {handle}；已读到文章日期分组。"
        ),
        "windowTitle": title,
        "windowHandle": handle,
    }
    if account_name:
        check["accountName"] = account_name
    return check, account_name


def _check_dependencies() -> dict:
    import importlib.util

    missing = [
        name
        for name in ("mitmproxy", "uiautomation")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        return {
            "name": "dependencies",
            "ok": False,
            "detail": f"缺少依赖模块：{', '.join(missing)}。请执行 `uv sync` 安装依赖。",
            "missing": missing,
        }
    return {
        "name": "dependencies",
        "ok": True,
        "detail": "依赖 mitmproxy、uiautomation 均已安装。",
        "missing": [],
    }


# 非阻塞检查项：不通过时 doctor 仍可 ready（不影响退出码判定）。
_NON_BLOCKING_CHECKS = frozenset({"playwright_browsers"})

_PLAYWRIGHT_TIMEOUT_SECONDS = 30
_PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS = 900


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包后的 frozen 环境中。"""

    import sys

    return bool(getattr(sys, "frozen", False))


def _locate_bundled_playwright_driver():
    """定位 Playwright wheel 自带的驱动，返回 ``(node.exe, cli.js)``；缺失时返回 None。"""

    from pathlib import Path

    try:
        import playwright
    except Exception:  # noqa: BLE001 - 未安装 Playwright 时视为无内置驱动
        return None
    driver = Path(playwright.__file__).resolve().parent / "driver"
    node = driver / "node.exe"
    cli = driver / "package" / "cli.js"
    if node.exists() and cli.exists():
        return node, cli
    return None


def _playwright_install_command(browsers_root) -> str:
    """返回可直接粘贴执行的 PowerShell 安装命令。"""

    if _is_frozen():
        return "awa doctor --install-browser"
    return (
        f"$env:PLAYWRIGHT_BROWSERS_PATH='{browsers_root}'; "
        "uv run python -m playwright install chromium"
    )


def _parse_playwright_dry_run(stdout: str) -> list[tuple[str, "object"]]:
    """解析 ``playwright install --dry-run`` 输出中的 (标题, 安装目录) 列表。

    输出示例::

        Chrome for Testing 156.0.8078.4 (playwright chromium v1248)
          Install location:    C:\\...\\chromium-1248
    """

    import re
    from pathlib import Path

    pattern = re.compile(r"^[ \t]*Install location:[ \t]*(.+?)[ \t]*$")
    entries: list[tuple[str, Path]] = []
    title = ""
    for line in stdout.splitlines():
        match = pattern.match(line)
        if match:
            entries.append((title, Path(match.group(1))))
            continue
        stripped = line.strip()
        if stripped and not line[:1].isspace():
            title = stripped
    return entries


def _playwright_entry_problem(title: str, location) -> str | None:
    """判断 dry-run 列出的 chromium 条目是否缺失；缺失时返回说明文本。"""

    from pathlib import Path

    directory = Path(location)
    lower = title.lower()
    if not directory.is_dir():
        return f"{title}（目录不存在：{directory}）"
    if "chromium-headless-shell" in lower:
        if not any(directory.glob("**/chrome-headless-shell.exe")):
            return f"{title}（缺少 chrome-headless-shell.exe：{directory}）"
    elif "playwright chromium" in lower:
        if not any(directory.glob("**/chrome.exe")):
            return f"{title}（缺少 chrome.exe：{directory}）"
    return None


def _run_playwright_dry_run(
    browsers_root,
) -> tuple[list[tuple[str, "object"]] | None, str | None, bool]:
    """执行 Playwright dry-run。

    返回 ``(entries, error, fallback_allowed)``：

    - 成功：``(entries, None, False)``；
    - 命令返回非 0（通常是旧版本不支持 ``--dry-run``）：``(None, 原因, True)``，
      允许退回目录校验；
    - 超时/无法启动/输出不可解析：``(None, 原因, False)``，无法确认浏览器状态。

    dry-run 只打印当前 Playwright 版本期望安装的浏览器及安装目录，
    因此以它给出的安装目录为准，可以避免「目录名 glob 命中旧版本」的假阳性。
    """

    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_root)
    if _is_frozen():
        driver = _locate_bundled_playwright_driver()
        if driver is None:
            return (None, "frozen 模式下未找到内置 Playwright 驱动", True)
        node, cli = driver
        command = [str(node), str(cli), "install", "--dry-run", "chromium"]
    else:
        command = [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PLAYWRIGHT_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return (
            None,
            f"playwright install --dry-run chromium 超时（{_PLAYWRIGHT_TIMEOUT_SECONDS} 秒）",
            False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"playwright install --dry-run chromium 调用失败：{exc}", False

    if completed.returncode != 0:
        output_text = (completed.stderr or completed.stdout or "").strip()[:200]
        return (
            None,
            f"playwright install --dry-run chromium 返回 {completed.returncode}：{output_text}",
            True,
        )
    entries = _parse_playwright_dry_run(completed.stdout or "")
    if not entries:
        return None, "playwright install --dry-run chromium 输出中未找到 Install location", True
    return entries, None, False


def _find_playwright_executable(browsers_root, dir_pattern: str, exe_name: str):
    """在浏览器缓存目录下按目录名 + 可执行文件名查找 Playwright 产物。"""

    from pathlib import Path

    root = Path(browsers_root)
    if not root.is_dir():
        return None
    for directory in sorted(root.glob(dir_pattern)):
        if not directory.is_dir():
            continue
        for executable in directory.glob(f"**/{exe_name}"):
            if executable.is_file():
                return executable
    return None


def _check_playwright_path_fallback(browsers_root, reason: str) -> dict:
    """dry-run 不可用时的降级校验：chromium 与 headless shell 目录都必须存在。"""

    install_command = _playwright_install_command(browsers_root)
    chromium = _find_playwright_executable(browsers_root, "chromium-*", "chrome.exe")
    headless = _find_playwright_executable(
        browsers_root, "chromium_headless_shell-*", "chrome-headless-shell.exe"
    )
    missing: list[str] = []
    if chromium is None:
        missing.append("chromium-*（未找到 chrome.exe）")
    if headless is None:
        missing.append("chromium_headless_shell-*（未找到 chrome-headless-shell.exe）")

    base = {
        "name": "playwright_browsers",
        "browserCacheDir": str(browsers_root),
        "installCommand": install_command,
        "detection": "directory-fallback",
        "dryRunError": reason,
    }
    if not missing:
        return {
            **base,
            "ok": True,
            "detail": (
                f"Playwright chromium 与 headless shell 均已就绪（{chromium}；{headless}）；"
                f"离线归档 --offline 可用。如需重装：{install_command}"
            ),
            "chromePath": str(chromium),
            "headlessShellPath": str(headless),
            "missing": [],
        }
    return {
        **base,
        "ok": False,
        "detail": (
            f"Playwright 浏览器缺失：{'；'.join(missing)}。"
            f"（dry-run 不可用：{reason}）离线归档（--offline）需要它们；该项不影响其他命令。"
            f"请在 PowerShell 中执行：{install_command}"
        ),
        "chromePath": str(chromium) if chromium is not None else None,
        "headlessShellPath": str(headless) if headless is not None else None,
        "missing": missing,
    }


def _playwright_check_failure(browsers_root, reason: str) -> dict:
    """dry-run 无法完成时的结果：无法确认浏览器状态，按未就绪处理。"""

    install_command = _playwright_install_command(browsers_root)
    return {
        "name": "playwright_browsers",
        "ok": False,
        "detail": (
            f"无法通过 Playwright 校验浏览器状态：{reason}。"
            "离线归档（--offline）需要 chromium；该项不影响其他命令。"
            f"请确认 Playwright 可用后重试，或在 PowerShell 中执行：{install_command}"
        ),
        "browserCacheDir": str(browsers_root),
        "installCommand": install_command,
        "detection": "playwright-dry-run",
        "dryRunError": reason,
        "chromePath": None,
        "missing": [],
    }


def _check_playwright_browsers(home) -> dict:
    """检查 <home>/.playwright-browsers 是否为当前 Playwright 版本所需的完整浏览器。

    优先执行 ``python -m playwright install --dry-run chromium``：由 Playwright 自己
    给出当前版本期望的安装目录（例如 chromium-1248 / chromium_headless_shell-1248），
    再逐个校验目录与可执行文件，避免旧版本目录导致的假阳性。
    """

    from pathlib import Path

    browsers_root = Path(home) / ".playwright-browsers"
    install_command = _playwright_install_command(browsers_root)
    entries, dry_run_error, fallback_allowed = _run_playwright_dry_run(browsers_root)
    if entries is None:
        if fallback_allowed:
            return _check_playwright_path_fallback(browsers_root, str(dry_run_error))
        return _playwright_check_failure(browsers_root, str(dry_run_error))

    chromium_entries = [
        (title, location)
        for title, location in entries
        if "chromium" in title.lower()
    ]
    if not chromium_entries:
        return _check_playwright_path_fallback(
            browsers_root, "dry-run 输出中没有 chromium 条目"
        )

    missing = [
        problem
        for title, location in chromium_entries
        if (problem := _playwright_entry_problem(title, location)) is not None
    ]
    expected = [
        {"name": title, "installLocation": str(location)}
        for title, location in chromium_entries
    ]
    chrome_path = None
    for title, location in chromium_entries:
        if "chromium-headless-shell" in title.lower():
            continue
        chrome_path = next(Path(location).glob("**/chrome.exe"), None)
        break
    base = {
        "name": "playwright_browsers",
        "browserCacheDir": str(browsers_root),
        "installCommand": install_command,
        "detection": "playwright-dry-run",
        "expectedBrowsers": expected,
    }
    if missing:
        return {
            **base,
            "ok": False,
            "detail": (
                f"Playwright 校验发现缺少浏览器：{'；'.join(missing)}。"
                "离线归档（--offline）需要它们；该项不影响其他命令。"
                f"请在 PowerShell 中执行：{install_command}"
            ),
            "chromePath": str(chrome_path) if chrome_path is not None else None,
            "missing": missing,
        }
    locations = "；".join(
        f"{title} -> {location}" for title, location in chromium_entries
    )
    return {
        **base,
        "ok": True,
        "detail": (
            f"Playwright dry-run 校验通过：当前版本期望的 chromium 组件均已安装"
            f"（{locations}）；离线归档 --offline 可用。如需重装：{install_command}"
        ),
        "chromePath": str(chrome_path) if chrome_path is not None else None,
        "missing": [],
    }


def _install_playwright_browsers(home) -> dict:
    """把离线归档所需的 Chromium 安装到 ``<home>/.playwright-browsers``。

    返回 ``{"ok": bool, "message": str, "browsersRoot": str}``，不抛出未捕获异常。
    """

    import os
    import subprocess
    import sys
    from pathlib import Path

    browsers_root = Path(home) / ".playwright-browsers"
    try:
        browsers_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        message = f"创建浏览器目录失败：{exc}"
        output.warn(message)
        return {"ok": False, "message": message, "browsersRoot": str(browsers_root)}

    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_root)

    driver = _locate_bundled_playwright_driver() if _is_frozen() else None
    if driver is not None:
        node, cli = driver
        command = [str(node), str(cli), "install", "chromium"]
    else:
        command = [sys.executable, "-m", "playwright", "install", "chromium"]

    output.progress(f"正在安装 Chromium 到 {browsers_root}……")
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        message = f"Playwright Chromium 安装超时（{_PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS} 秒）"
        output.warn(message)
        return {"ok": False, "message": message, "browsersRoot": str(browsers_root)}
    except (OSError, subprocess.SubprocessError) as exc:
        message = f"Playwright Chromium 安装调用失败：{exc}"
        output.warn(message)
        return {"ok": False, "message": message, "browsersRoot": str(browsers_root)}

    if completed.returncode != 0:
        output_text = (completed.stderr or completed.stdout or "").strip()[:200]
        message = f"Playwright Chromium 安装返回 {completed.returncode}：{output_text}"
        output.warn(message)
        return {"ok": False, "message": message, "browsersRoot": str(browsers_root)}

    return {
        "ok": True,
        "message": f"Chromium 已安装到 {browsers_root}",
        "browsersRoot": str(browsers_root),
    }


def _doctor_status(checks: list[dict]) -> str:
    by_name = {check["name"]: check for check in checks}
    window = by_name.get("wechat_home_window")
    if window is not None and not window["ok"]:
        return "window-not-found"
    ca = by_name.get("ca_certificate")
    if ca is not None and not ca["ok"]:
        return "ca-not-installed"
    if not all(
        check["ok"]
        for check in checks
        if check["name"] not in _NON_BLOCKING_CHECKS
    ):
        return "not-ready"
    return "ok"


def run_doctor(
    *,
    install_ca: bool = False,
    install_browser: bool = False,
    home: str | None = None,
) -> int:
    """检查运行前置条件（Task 2 实现）。"""

    from awa.cli.bootstrap import HeadlessRuntime

    output.progress("开始检查运行前置条件……")
    home_path = resolve_home(home)
    runtime = HeadlessRuntime(home=home_path)
    checks: list[dict] = []
    account_name: str | None = None
    db_path = None
    config = None

    try:
        try:
            runtime.prepare()
        except Exception as exc:  # noqa: BLE001 - 装配失败需要转成结构化输出
            checks.append(
                {
                    "name": "config",
                    "ok": False,
                    "detail": f"配置装配失败：{type(exc).__name__}: {exc}",
                }
            )
            output.emit_error(
                "doctor",
                "doctor-failed",
                f"运行时装配失败：{type(exc).__name__}: {exc}",
                ready=False,
                checks=checks,
                home=str(home_path),
            )
            return output.EXIT_FAILED

        config = runtime.config
        db_path = runtime.db_path
        checks.append(
            {
                "name": "config",
                "ok": True,
                "detail": "配置加载并通过校验。",
            }
        )
        checks.append(_check_storage_dirs(config))
        checks.append(_check_database(db_path))
        checks.append(_check_mitm_port(config))
        checks.append(_check_ca(config, install_ca=install_ca))
        window_check, account_name = _check_home_window(runtime, config)
        checks.append(window_check)
        checks.append(_check_dependencies())
        if install_browser:
            install_result = _install_playwright_browsers(home_path)
            if not install_result.get("ok"):
                output.warn(f"安装 Chromium 失败：{install_result.get('message')}")
        checks.append(_check_playwright_browsers(home_path))

        ready = all(
            check["ok"]
            for check in checks
            if check["name"] not in _NON_BLOCKING_CHECKS
        )
        status = _doctor_status(checks)
        proxy_address = f"{config.proxy.host}:{config.proxy.port}"
        output.emit_ok(
            "doctor",
            status=status,
            ok=ready,
            ready=ready,
            home=str(home_path),
            checks=checks,
            accountName=account_name,
            dbPath=str(db_path),
            proxyAddress=proxy_address,
        )
        return output.EXIT_OK if ready else output.EXIT_PRECONDITION
    finally:
        runtime.shutdown()


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


def run_scan(
    *,
    limit: int = 0,
    date_mode: str = "all",
    start: str | None = None,
    end: str | None = None,
    max_scrolls: int = 200,
    home: str | None = None,
) -> int:
    """只读预览公众号主页文章（Task 3 实现）。"""

    from awa.cli.bootstrap import HeadlessRuntime
    from awa.services.main_flow.home_scan_service import HomeScanError
    from awa.services.main_flow.main_flow_models import MainFlowCommand

    runtime = HeadlessRuntime(home=resolve_home(home))
    try:
        runtime.prepare()
        scanner = runtime.build_scan_service()
        command = MainFlowCommand(
            target_count=int(limit or 0),
            date_filter_mode=date_mode,
            start_date=start,
            end_date=end,
        )
        output.progress("正在定位公众号主页并读取文章列表……")
        session = scanner.initialize(command)

        collected = []
        seen: set[str] = set()
        raw_count = 0
        skipped_count = 0
        scrolls = 0
        truncated = False

        while True:
            batch = scanner.scan_visible_targets(session)
            for target in sorted(batch.targets, key=lambda item: item.sequence):
                if target.fingerprint in seen:
                    continue
                seen.add(target.fingerprint)
                collected.append(target)
            raw_count += int(batch.raw_count)
            skipped_count += int(batch.skipped_count)

            if limit > 0 and len(collected) >= limit:
                break
            if session.boundary_reached:
                break
            if not scanner.scroll_next(session):
                break
            scrolls += 1
            if scrolls >= max_scrolls:
                truncated = True
                break

        boundary_reached = bool(session.boundary_reached)
        if limit > 0:
            collected = collected[:limit]
        items = [
            {
                "sequence": int(target.sequence),
                "title": target.title_display or target.title_raw,
                "articleDate": target.article_date,
                "fingerprint": target.fingerprint,
            }
            for target in collected
        ]
        output.emit_ok(
            "scan",
            accountName=session.account_name,
            dateFilter={"mode": date_mode, "label": session.date_filter.label},
            count=len(items),
            items=items,
            boundaryReached=boundary_reached,
            truncated=truncated,
            scrolls=scrolls,
            rawCount=raw_count,
            skippedCount=skipped_count,
        )
        return output.EXIT_OK
    except HomeScanError as exc:
        message = str(exc)
        if _is_home_unavailable_message(message):
            output.emit_error(
                "scan",
                "window-not-found",
                "未找到可用的公众号主页窗口。请在微信中打开目标公众号主页后重试。",
            )
            return output.EXIT_PRECONDITION
        output.emit_error("scan", "scan-failed", message)
        return output.EXIT_FAILED
    except Exception as exc:  # noqa: BLE001 - 未预期异常统一转结构化输出
        if _is_home_unavailable_message(str(exc)):
            output.emit_error(
                "scan",
                "window-not-found",
                "未找到可用的公众号主页窗口。请在微信中打开目标公众号主页后重试。",
            )
            return output.EXIT_PRECONDITION
        output.emit_error("scan", "scan-failed", f"{type(exc).__name__}: {exc}")
        return output.EXIT_FAILED
    finally:
        runtime.shutdown()


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------

_CRAWL_STATUS_LABELS = {
    "idle": "空闲",
    "starting": "启动中",
    "running": "采集中",
    "stopping": "正在停止",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}


def _crawl_progress_line(status: str, runtime_state: dict) -> str:
    label = _CRAWL_STATUS_LABELS.get(status, status or "未知")
    account = str(runtime_state.get("accountName") or "等待识别")
    done = runtime_state.get("progressDone", 0)
    total = runtime_state.get("progressTotalLabel", "全部")
    errors = runtime_state.get("errorCount", 0)
    action = str(runtime_state.get("currentAction") or "")
    return f"[{label}] {account} 进度 {done}/{total}，错误 {errors}｜{action}"


def _archive_absolute_path(storage_root, archive_dir: str) -> str:
    from pathlib import Path

    directory = str(archive_dir or "").strip()
    if not directory:
        return str(storage_root)
    return str(Path(storage_root) / directory)


def _query_crawl_new_articles(
    db_path,
    started_at: str,
    account_name: str | None,
    storage_root,
) -> list[dict]:
    from awa.storage.sqlite.connection import sqlite_connection

    sql = (
        "SELECT ar.id, a.account_name, ar.article_title, ar.published_article_time, "
        "ar.article_link, ar.archive_dir, ar.last_collected_time "
        "FROM awa_public_articles ar "
        "JOIN awa_public_accounts a ON a.id = ar.account_id "
        "WHERE ar.last_collected_time >= ?"
    )
    params: list = [started_at]
    if account_name:
        sql += " AND a.account_name = ?"
        params.append(account_name)
    sql += " ORDER BY ar.last_collected_time DESC, ar.id DESC"

    items: list[dict] = []
    with sqlite_connection(db_path, write=False) as connection:
        for row in connection.execute(sql, params):
            items.append(
                {
                    "articleId": int(row["id"]),
                    "title": row["article_title"],
                    "publishedArticleTime": row["published_article_time"],
                    "articleLink": row["article_link"],
                    "archiveDir": _archive_absolute_path(storage_root, row["archive_dir"]),
                }
            )
    return items


def run_crawl(
    *,
    limit: int = 0,
    date_mode: str = "all",
    start: str | None = None,
    end: str | None = None,
    skip_collected: bool = False,
    interval: float = 0.0,
    timeout: float = 0.0,
    comments: bool = False,
    offline: bool = False,
    offline_mode: str = "standard",
    home: str | None = None,
) -> int:
    """执行文章采集（Task 4 实现）。"""

    import time
    from datetime import datetime
    from pathlib import Path

    from awa.cli.bootstrap import HeadlessRuntime
    from awa.services.main_flow.main_flow_models import MainFlowCommand

    runtime = HeadlessRuntime(home=resolve_home(home))
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timed_out = False
    db_path = None
    storage_root = None
    log_path = None
    service = None
    task_id = None
    snapshot = None

    try:
        output.progress("正在装配采集运行时……")
        runtime.prepare()
        config = runtime.config
        db_path = runtime.db_path
        storage_root = Path(config.storage.article_storage_root)
        log_path = str(Path(config.storage.log_dir) / "runtime-summary.log")

        service, _dispatcher = runtime.build_main_flow(
            comments=bool(comments),
            offline=bool(offline),
        )

        command = MainFlowCommand(
            target_count=int(limit or 0),
            date_filter_mode=date_mode,
            start_date=start,
            end_date=end,
            collect_comments=bool(comments),
            archive_offline=bool(offline),
            offline_archive_mode=offline_mode,
            skip_collected_records=bool(skip_collected),
            single_task_interval_seconds=float(interval or 0.0),
        )
        output.progress("正在启动采集任务……")
        snapshot = service.start(command)
        task_id = snapshot.task_id
    except Exception as exc:  # noqa: BLE001 - 启动失败统一转结构化输出
        output.emit_error("crawl", "crawl-failed", str(exc))
        runtime.shutdown()
        return output.EXIT_FAILED

    start_monotonic = time.monotonic()
    settle_deadline: float | None = None
    last_line: str | None = None
    try:
        while True:
            snapshot = service.get(task_id)
            status = str(snapshot.status)
            runtime_state = snapshot.runtime_state or {}
            line = _crawl_progress_line(status, runtime_state)
            if line != last_line:
                output.progress(line)
                last_line = line

            if status in {"completed", "failed", "cancelled"}:
                break

            elapsed = time.monotonic() - start_monotonic
            if not timed_out and float(timeout or 0.0) > 0 and elapsed >= float(timeout):
                output.progress(
                    f"已超过超时时间 {float(timeout):g} 秒，正在请求停止采集……"
                )
                try:
                    service.stop(task_id)
                except Exception:  # noqa: BLE001 - 停止失败不阻断收尾
                    pass
                timed_out = True
                settle_deadline = time.monotonic() + max(float(timeout), 30.0)

            if (
                timed_out
                and settle_deadline is not None
                and time.monotonic() >= settle_deadline
            ):
                output.warn("等待采集停止超时，结束轮询。")
                break

            time.sleep(2.0)
    except KeyboardInterrupt:
        output.warn("收到中断信号（Ctrl+C），正在请求停止采集……")
        try:
            service.stop(task_id)
        except Exception:  # noqa: BLE001 - 停止失败不阻断收尾
            pass
    finally:
        runtime.shutdown()

    # shutdown 之后仍可用只读连接查询本次新增文章。
    try:
        snapshot = service.get(task_id)
    except Exception:  # noqa: BLE001 - 查询失败时沿用最后一次快照
        pass

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    runtime_state = (snapshot.runtime_state if snapshot is not None else {}) or {}
    account_name = str(runtime_state.get("accountName") or "").strip()
    if account_name in {"", "等待识别"}:
        account_name = None
    error_count = int(runtime_state.get("errorCount") or 0)
    latest_error = str(runtime_state.get("latestError") or "")

    articles: list[dict] = []
    try:
        articles = _query_crawl_new_articles(
            db_path, started_at, account_name, storage_root
        )
    except Exception as exc:  # noqa: BLE001 - 汇总失败不影响退出码判定
        output.warn(f"查询本次新增文章失败：{type(exc).__name__}: {exc}")

    errors: list[dict] = []
    if error_count > 0:
        errors.append({"count": error_count, "latestError": latest_error})

    final_status = str(snapshot.status) if snapshot is not None else "failed"
    message_text = str(getattr(snapshot, "message", "") or "") if snapshot else ""
    extra_fields: dict = {}
    if timed_out:
        final_status = "timeout"
        exit_code = output.EXIT_FAILED
    elif final_status == "completed":
        exit_code = output.EXIT_OK
    elif final_status == "failed":
        if _is_home_unavailable_message(message_text):
            final_status = "window-not-found"
            extra_fields["message"] = (
                "未找到可用的公众号主页窗口。请在微信中打开目标公众号主页后重试。"
            )
            exit_code = output.EXIT_PRECONDITION
        else:
            exit_code = output.EXIT_FAILED
    else:
        # cancelled / stopping / 未知状态统一按失败处理。
        final_status = "cancelled" if final_status != "failed" else final_status
        exit_code = output.EXIT_FAILED

    output.emit_ok(
        "crawl",
        status=final_status,
        taskId=task_id,
        accountName=account_name,
        processedCount=int(runtime_state.get("progressDone") or 0),
        detailSuccessCount=int(runtime_state.get("detailSuccessCount") or 0),
        skippedCount=int(runtime_state.get("skippedCount") or 0),
        errorCount=error_count,
        averageArticleSeconds=runtime_state.get("averageArticleSeconds"),
        articles=articles,
        errors=errors,
        startedAt=started_at,
        finishedAt=finished_at,
        logPath=log_path,
        commentsEnabled=bool(comments),
        offlineEnabled=bool(offline),
        **extra_fields,
    )
    return exit_code


# ---------------------------------------------------------------------------
# articles
# ---------------------------------------------------------------------------


def run_articles(
    *,
    account: str | None = None,
    limit: int = 50,
    since: str | None = None,
    home: str | None = None,
) -> int:
    """只读查询已采集文章（Task 5 实现，不初始化数据库）。"""

    from pathlib import Path

    from awa.app.main_orchestrator import load_application_runtime
    from awa.storage.sqlite.connection import sqlite_connection

    try:
        runtime = load_application_runtime(home=resolve_home(home))
        config = runtime.config
        db_path = Path(config.storage.database_path)
        storage_root = Path(config.storage.article_storage_root)
    except Exception as exc:  # noqa: BLE001 - 装配失败统一转结构化输出
        output.emit_error("articles", "query-failed", f"{type(exc).__name__}: {exc}")
        return output.EXIT_FAILED

    if not db_path.exists():
        output.emit_error(
            "articles",
            "database-missing",
            "数据库不存在，请先执行一次 crawl。",
        )
        return output.EXIT_PRECONDITION

    clamped_limit = max(1, min(500, int(limit)))

    try:
        conditions: list[str] = []
        params: list = []
        if account:
            conditions.append("a.account_name = ?")
            params.append(account)
        if since:
            conditions.append("ar.last_collected_time >= ?")
            params.append(since)
        where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        base_sql = (
            "FROM awa_public_articles ar "
            "JOIN awa_public_accounts a ON a.id = ar.account_id"
            + where_sql
        )

        output.progress(f"正在查询数据库：{db_path}")
        with sqlite_connection(db_path, write=False) as connection:
            article_count = int(
                connection.execute(
                    f"SELECT COUNT(*) {base_sql}", params
                ).fetchone()[0]
            )
            account_count = int(
                connection.execute(
                    f"SELECT COUNT(DISTINCT ar.account_id) {base_sql}", params
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT ar.id, a.account_name, ar.article_title, "
                "ar.published_article_time, ar.article_link, ar.archive_dir, "
                "ar.last_collected_time "
                + base_sql
                + " ORDER BY ar.last_collected_time DESC, ar.id DESC LIMIT ?",
                params + [clamped_limit],
            ).fetchall()

        items: list[dict] = []
        for row in rows:
            archive_dir = str(row["archive_dir"] or "")
            absolute_path = Path(storage_root) / archive_dir if archive_dir else Path(
                storage_root
            )
            items.append(
                {
                    "articleId": int(row["id"]),
                    "accountName": row["account_name"],
                    "title": row["article_title"],
                    "publishedArticleTime": row["published_article_time"],
                    "articleLink": row["article_link"],
                    "archiveDir": str(absolute_path),
                    "lastCollectedTime": row["last_collected_time"],
                    "existsOnDisk": absolute_path.is_dir(),
                }
            )
    except Exception as exc:  # noqa: BLE001 - 查询失败统一转结构化输出
        output.emit_error("articles", "query-failed", f"{type(exc).__name__}: {exc}")
        return output.EXIT_FAILED

    output.emit_ok(
        "articles",
        accountCount=account_count,
        articleCount=article_count,
        items=items,
        dbPath=str(db_path),
        storageRoot=str(storage_root),
    )
    return output.EXIT_OK


__all__ = ["run_articles", "run_crawl", "run_doctor", "run_scan"]
