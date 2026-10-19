# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 6.x 构建配置。

- onedir：产物为 dist/awa/awa.exe + _internal/，启动快、便于替换资源；
  不使用 onefile（每次启动都要解压，且 spawn 子进程会重复解压）。
- console=True：CLI 需要标准输入输出，且 frozen 下 Crawl 使用 spawn 子进程，
  入口 awa_entry.py 会先调用 multiprocessing.freeze_support()。
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

# spec 位于 packaging/ 下，SPECPATH 指向该目录，其父目录即仓库根目录。
ROOT = Path(SPECPATH).resolve().parent

datas = []
binaries = []
hiddenimports = []

# 显式收集资源，保证 _internal/awa/resources/system.yaml 与 schema/*.sql 存在。
datas += [(str(ROOT / "awa" / "resources"), "awa/resources")]

# 这些包包含动态导入/数据文件/二进制，需要整包收集。
for package in ("mitmproxy", "playwright", "uiautomation", "comtypes"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

hiddenimports += [
    "mitmproxy.tools.dump",
    "mitmproxy.addons",
    "mitmproxy.proxy.layers",
    "mitmproxy.proxy.layers.http",
    "comtypes.gen",
    "comtypes.gen.UIAutomationClient",
    "playwright.sync_api",
    "playwright._impl._driver",
    "huey",
    "huey.api",
    "ruamel.yaml",
    "ruamel.yaml.clib",
]

# 运行时需要读取发行包元数据（版本号等）。
for distribution in (
    "mitmproxy",
    "playwright",
    "uiautomation",
    "comtypes",
    "huey",
    "ruamel.yaml",
):
    datas += copy_metadata(distribution)

# 本项目可能以源码方式构建（未安装为发行包），缺失时跳过而不是让 spec 报错。
try:
    datas += copy_metadata("awa-cli")
except Exception:
    pass

a = Analysis(
    [str(ROOT / "packaging" / "awa_entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "tests"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="awa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="awa",
)
