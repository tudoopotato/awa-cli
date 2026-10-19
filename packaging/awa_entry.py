"""PyInstaller 打包入口：frozen 模式下必须先启用 multiprocessing.freeze_support。"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    multiprocessing.freeze_support()
    from awa.cli.main import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
