"""awa CLI 入口：argparse 子命令注册、参数校验与统一异常兜底。"""

from __future__ import annotations

import argparse
import sys

from . import output

_SUBCOMMANDS = ("doctor", "scan", "crawl", "articles")
_DATE_MODES = ("all", "range", "before", "after")
_OFFLINE_MODES = ("standard", "beta")
_HOME_HELP = "AWA_HOME 用户数据目录；默认为环境变量 AWA_HOME 或 %%LOCALAPPDATA%%\\awa"


def _current_command() -> str:
    """从 argv 推断当前子命令，用于错误输出；识别不出时用 awa。"""

    for token in sys.argv[1:]:
        if token in _SUBCOMMANDS:
            return token
    return "awa"


class _ArgumentParser(argparse.ArgumentParser):
    """把 argparse 的参数错误退出码从 2 改成 3，并输出 JSON。"""

    def error(self, message: str) -> None:  # type: ignore[override]
        command = _current_command()
        sys.stderr.write(f"[awa] 参数错误：{message}\n")
        sys.stderr.flush()
        output.emit_error(command, "usage-error", message)
        raise SystemExit(output.EXIT_USAGE)


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="awa",
        description="微信公众号文章采集 CLI",
    )
    parser.add_argument("--home", type=str, default=None, help=_HOME_HELP)
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    doctor = subparsers.add_parser("doctor", help="检查运行前置条件")
    doctor.add_argument("--install-ca", action="store_true", help="安装 CA 证书")
    doctor.add_argument(
        "--install-browser",
        action="store_true",
        help="安装离线归档所需的 Chromium",
    )
    doctor.add_argument("--home", type=str, default=argparse.SUPPRESS, help=_HOME_HELP)

    scan = subparsers.add_parser("scan", help="只读预览公众号主页文章")
    scan.add_argument("--limit", type=int, default=0, help="最多列出多少篇，0 表示不限")
    scan.add_argument("--date-mode", choices=_DATE_MODES, default="all")
    scan.add_argument("--start", type=str, default=None)
    scan.add_argument("--end", type=str, default=None)
    scan.add_argument("--max-scrolls", type=int, default=200)
    scan.add_argument("--home", type=str, default=argparse.SUPPRESS, help=_HOME_HELP)

    crawl = subparsers.add_parser("crawl", help="执行文章采集")
    crawl.add_argument("--limit", type=int, default=0, help="最多采集多少篇，0 表示不限")
    crawl.add_argument("--date-mode", choices=_DATE_MODES, default="all")
    crawl.add_argument("--start", type=str, default=None)
    crawl.add_argument("--end", type=str, default=None)
    crawl.add_argument("--skip-collected", action="store_true")
    crawl.add_argument("--interval", type=float, default=0.0)
    crawl.add_argument("--timeout", type=float, default=0.0)
    crawl.add_argument(
        "--comments",
        action="store_true",
        help="采集文章评论（默认不采集评论）",
    )
    crawl.add_argument(
        "--offline",
        action="store_true",
        help="对文章做离线归档（默认不做离线归档）",
    )
    crawl.add_argument(
        "--offline-mode",
        choices=_OFFLINE_MODES,
        default="standard",
        help="离线归档模式：standard 为常规模式，beta 为带状态实验模式（仅在 --offline 时生效）",
    )
    crawl.add_argument("--home", type=str, default=argparse.SUPPRESS, help=_HOME_HELP)

    articles = subparsers.add_parser("articles", help="只读查询已采集文章")
    articles.add_argument("--account", type=str, default=None)
    articles.add_argument("--limit", type=int, default=50)
    articles.add_argument("--since", type=str, default=None)
    articles.add_argument("--home", type=str, default=argparse.SUPPRESS, help=_HOME_HELP)

    return parser


def _is_valid_date(value: str) -> bool:
    from datetime import datetime

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return True


def _validate_dates(
    date_mode: str,
    start: str | None,
    end: str | None,
) -> str:
    """返回中文错误信息；校验通过返回空字符串。"""

    if date_mode == "range" and (not start or not end):
        return "date-mode 为 range 时必须同时提供 --start 与 --end。"
    if date_mode == "before" and not end:
        return "date-mode 为 before 时必须提供 --end。"
    if date_mode == "after" and not start:
        return "date-mode 为 after 时必须提供 --start。"
    for label, value in (("--start", start), ("--end", end)):
        if value and not _is_valid_date(value):
            return f"{label} 日期格式必须为 YYYY-MM-DD：{value}"
    return ""


def _dispatch(args: argparse.Namespace) -> int:
    command = args.command
    if command == "doctor":
        from . import commands

        return commands.run_doctor(
            install_ca=args.install_ca,
            install_browser=args.install_browser,
            home=args.home,
        )
    if command == "scan":
        error = _validate_dates(args.date_mode, args.start, args.end)
        if error:
            output.emit_error("scan", "usage-error", error)
            return output.EXIT_USAGE
        from . import commands

        return commands.run_scan(
            limit=args.limit,
            date_mode=args.date_mode,
            start=args.start,
            end=args.end,
            max_scrolls=args.max_scrolls,
            home=args.home,
        )
    if command == "crawl":
        error = _validate_dates(args.date_mode, args.start, args.end)
        if error:
            output.emit_error("crawl", "usage-error", error)
            return output.EXIT_USAGE
        from . import commands

        return commands.run_crawl(
            limit=args.limit,
            date_mode=args.date_mode,
            start=args.start,
            end=args.end,
            skip_collected=args.skip_collected,
            interval=args.interval,
            timeout=args.timeout,
            comments=args.comments,
            offline=args.offline,
            offline_mode=args.offline_mode,
            home=args.home,
        )
    if command == "articles":
        from . import commands

        return commands.run_articles(
            account=args.account,
            limit=args.limit,
            since=args.since,
            home=args.home,
        )
    raise ValueError(f"未知子命令：{command}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    command = getattr(args, "command", None)
    if not command:
        parser.print_help(sys.stderr)
        output.emit_error("awa", "usage-error", "未指定子命令。")
        return output.EXIT_USAGE

    if sys.platform != "win32":
        output.emit_error(command, "unsupported-platform", "本工具仅支持 Windows 10/11。")
        return output.EXIT_PRECONDITION

    try:
        return _dispatch(args)
    except Exception as exc:
        output.emit_error(command, "internal-error", f"{type(exc).__name__}: {exc}")
        return output.EXIT_FAILED


__all__ = ["main"]
