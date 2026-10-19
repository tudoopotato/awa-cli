# awa-cli 分发方案：PyInstaller 独立 exe

> 本文只做方案设计，不包含代码改动。目标：让没有任何 Python / uv / Git 环境的 Windows 用户，下载解压后直接运行 `awa.exe`。

---

## 1. 结论先行

**可行，但必须用 `onedir`（目录模式）+ ZIP 分发，不要用 `onefile`。**

原因：本项目大量使用 `multiprocessing.get_context("spawn")`（MITM 抓包、评论、离线归档、数据库写锁各一个子进程）。`spawn` 子进程会**重新执行同一个 exe**：

- `onefile`：每次子进程启动都要把上百 MB 依赖重新解压到临时目录，单篇采集会多出数秒到十几秒开销，`crawl` 会被拖垮；
- `onedir`：子进程直接复用同目录的 `_internal`，启动接近正常程序。

最终交付形态：

```text
awa-0.1.0-windows-x64.zip
└── awa\
    ├── awa.exe                 # 控制台程序
    ├── _internal\              # Python 运行时 + 依赖 + 资源
    └── README-安装说明.txt
```

用户操作：解压 → 在该目录打开 PowerShell → `.\awa.exe doctor`。

---

## 2. 与 npm 方案的对比（为什么选 exe）

| 方案 | 用户命令 | 用户前置依赖 | 主要问题 |
| --- | --- | --- | --- |
| PyPI | `uv tool install awa-cli` | 需先装 uv | 对非技术用户仍是两步 |
| npm 包装 | `npm i -g awa-cli` | 需 Node.js | 仍需 postinstall 下载 uv/Python；npm 层只是壳，安装体积更大 |
| PyInstaller exe | 解压即用 | 无 | 包体大、需处理子进程/资源、可能被杀软误报 |

本项目依赖 `mitmproxy`、`uiautomation`（Windows COM）、`playwright`，都属于“跟解释器/系统绑定”的库，**打成一个 exe 目录是最彻底、对用户最友好的方案**。npm 只能在上面再加一层引导脚本，没有实质收益。

---

## 3. 打包前必须处理的阻塞点（按优先级）

### 3.1 `multiprocessing` spawn（必须）

现状：`awa/app/main_orchestrator.py`、`process_launcher.py`、`offline_cache_process_launcher.py`、`comment_process_launcher.py`、`database_write_coordinator.py` 均使用 `spawn`。

frozen 程序必须在入口最开始调用 `multiprocessing.freeze_support()`，且要在 `argparse` 之前。当前 `awa/cli/main.py::main()` 没有调用。

需要新增打包入口（不污染源码入口）：

```python
# packaging/awa_entry.py
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from awa.cli.main import main
    sys.exit(main())
```

验收：`crawl --comments --offline` 能正常派生子进程，子进程无 `ModuleNotFoundError` / 立刻退出。

### 3.2 `doctor` 的 Playwright 探测（必须）

`awa/cli/commands.py` 的 `_run_playwright_dry_run()` 使用：

```python
[sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"]
```

frozen 后 `sys.executable` 是 `awa.exe`，`-m playwright` 不成立，该检查会失败。

处理方案（二选一）：

1. frozen 时跳过 dry-run，直接走已有的目录探测 `_find_playwright_executable()`（改动最小，但版本匹配精度下降）；
2. frozen 时改为调用内置 Playwright 驱动：
   `_internal\playwright\driver\node.exe _internal\playwright\driver\package\cli.js install --dry-run chromium`。

建议先做 1 保证 `doctor` 不误报，再做 2 恢复精度。

### 3.3 离线归档的浏览器安装（必须决策）

frozen 后用户无法执行 `python -m playwright install chromium`。两个选择：

- **A. 内置驱动安装（推荐）**：Playwright wheel 自带 `driver/node.exe` 与 `driver/package/cli.js`，可直接用它们安装 Chromium：
  `node.exe cli.js install chromium`，并设置 `PLAYWRIGHT_BROWSERS_PATH=<AWA_HOME>\.playwright-browsers`。
  可在 CLI 增加隐藏子命令（如 `awa setup-browser`）或给 `doctor` 加 `--install-browser`。
- **B. 不内置**：`doctor` 输出手动安装说明，用户自行用其他机器/工具准备浏览器目录。体验差，不推荐。

注意：Chromium 约 150 MB，**不要打进 ZIP**，应在首次需要 `--offline` 时按需下载。

### 3.4 内置资源路径（必须验证）

`awa/resources/__init__.py` 通过 `importlib.resources.files("awa.resources")` 转 `Path`。在 onedir 模式下资源位于 `_internal/awa/resources`，通常可用，但必须实测：

- `system.yaml` 能被读取；
- `schema/create_awa_v2_1.sql` 能被读取并完成建库。

若 `files()` 在 frozen 下返回非文件系统路径，改为：

```python
if getattr(sys, "frozen", False):
    return Path(sys._MEIPASS) / "awa" / "resources"
```

（onedir 下 `sys._MEIPASS` 指向 `_internal`。）

### 3.5 依赖收集（必须）

PyInstaller 默认分析不到的动态导入，需要在 spec 中显式收集：

- `mitmproxy`：`collect_all("mitmproxy")`，并确认 `mitmproxy.tools.dump`、`mitmproxy.addons.*`、`mitmproxy.proxy.layers.*` 被收集；
- `uiautomation` + `comtypes`：`collect_submodules("comtypes.gen")`、`hiddenimports=["comtypes.gen.UIAutomationClient"]`（comtypes 的 typelib 缓存需可写 `%TEMP%`）；
- `playwright`：`collect_data_files("playwright")`，确保 `driver/node.exe`、`driver/package/cli.js` 存在；
- `ruamel.yaml`：确认 C 扩展或纯 Python 回退可用；
- `huey`：内嵌线程 consumer，一般无需额外处理，但需实测；
- 包元数据：`copy_metadata("mitmproxy")`、`copy_metadata("playwright")`、`copy_metadata("awa-cli")`（部分库通过 `importlib.metadata` 读版本）；
- 排除项：`tkinter`、`matplotlib`、`pytest`、`tests`，减小体积。

`mitmproxy` 另外依赖 `cryptography`、`h2`、`zstandard`、`brotli`、`kaitaistruct`、`pylsqpack`、`publicsuffix2` 等，建议先 `collect_all("mitmproxy")`，再根据运行时报错补 hiddenimports。

### 3.6 暂不需要改的部分（已确认）

- `certutil` / `powershell` 调用（CA 安装与证书库读取）在 exe 下正常；
- `huey` 使用嵌入式线程 consumer，不是独立进程；
- 数据目录逻辑不依赖源码路径；
- 控制台输出为 UTF-8 JSON，`console=True` 即可。

---

## 4. 打包配置

### 4.1 依赖

在 `pyproject.toml` 增加构建依赖（不进入运行时依赖）：

```toml
[dependency-groups]
build = ["pyinstaller>=6.11"]
```

### 4.2 `packaging/awa.spec`

核心内容：

```python
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas, binaries, hiddenimports = [], [], []

for package in ("mitmproxy", "playwright"):
    d, b, h = collect_all(package)
    datas += d; binaries += b; hiddenimports += h

hiddenimports += collect_submodules("comtypes.gen")
hiddenimports += [
    "comtypes.gen.UIAutomationClient",
    "mitmproxy.tools.dump",
    "huey",
    "ruamel.yaml",
]

for dist in ("mitmproxy", "playwright", "awa-cli"):
    datas += copy_metadata(dist)

a = Analysis(
    ["packaging/awa_entry.py"],
    pathex=["."],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="awa", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="awa")
```

要点：

- `console=True`（CLI 必须保留 stdout/stderr）；
- 不使用 `--onefile`；
- 不使用 UPX（会加大杀软误报概率）；
- 可加图标与版本信息（`version_info.txt`）。

### 4.3 版本号

exe 版本与 `pyproject.toml` 的 `version` 保持一致；打包脚本从 `pyproject.toml` 读取，避免手改两处。

---

## 5. CI 自动构建（GitHub Actions）

新增 `.github/workflows/build-exe.yml`：

- 触发：`push tag v*` + 手动 `workflow_dispatch`；
- runner：`windows-latest`；
- 步骤：
  1. `actions/checkout`
  2. `astral-sh/setup-uv` + `uv python install 3.13`
  3. `uv sync --group build`
  4. `uv run pyinstaller packaging/awa.spec --noconfirm`
  5. 运行冒烟：`dist\awa\awa.exe --help`、`awa.exe doctor`（允许退出码 2，但不能崩溃/缺模块）
  6. `Compress-Archive dist\awa dist\awa-${{ github.ref_name }}-windows-x64.zip`
  7. 生成 `SHA256SUMS.txt`
  8. `softprops/action-gh-release` 上传 zip 与校验文件

建议先只在 `workflow_dispatch` 上跑通，再绑定 tag 自动发布。

---

## 6. 分发与安装体验

1. **GitHub Releases**：每个版本一个 zip + SHA256；
2. **一键安装脚本（可选）**：`install.ps1` 下载最新 zip 到 `%LOCALAPPDATA%\awa-cli`，解压并把目录加入用户 PATH：
   `irm https://raw.githubusercontent.com/tudoopotato/awa-cli/main/install.ps1 | iex`
3. **winget / scoop（后续）**：需要稳定的发布 URL 与清单维护；
4. **签名**：不签名会有 SmartScreen“未知发布者”提示。若要面向非技术用户，建议购买代码签名证书，并在发布说明中给出 SHA256 供校验。

---

## 7. 验收清单（必须在干净环境测试）

在一台**未安装 Python / uv / Git** 的 Windows 10 与 Windows 11 上执行：

- [ ] `awa.exe --help` 正常输出，中文不乱码
- [ ] `awa.exe doctor` 返回结构化 JSON，`dependencies` 检查项为 `ok=true`
- [ ] `awa.exe scan --limit 5` 能读取微信主页
- [ ] `awa.exe crawl --limit 1` 完成采集，`articles[]` 有 `archiveDir`
- [ ] 首次采集后 `.mitmproxy\mitmproxy-ca-cert.cer` 生成
- [ ] `awa.exe doctor --install-ca` 安装成功，再次 `doctor` 为 `installed`
- [ ] `awa.exe crawl --limit 1 --comments` 子进程正常
- [ ] `crawl --offline` 能安装/使用 Chromium，生成 `index.html`
- [ ] 进程管理器确认 `crawl` 结束后无残留 `awa.exe` 子进程
- [ ] 路径含空格/中文时正常（如 `D:\我的 数据\awa`）
- [ ] 退出码符合约定（0/1/2/3）
- [ ] Windows Defender 与至少一款主流杀软无拦截（必要时提交误报）

---

## 8. 实施顺序与工作量拆解

| 阶段 | 内容 | 产出 |
| --- | --- | --- |
| 1 | 加 `packaging/awa_entry.py` + 最小 spec，本机出包 | 能跑 `--help` 的 onedir |
| 2 | 修 3.1（freeze_support）与 3.2（doctor Playwright） | `doctor` 不误报 |
| 3 | 补依赖收集，跑通 `doctor` / `scan` / `crawl` / `comments` | 采集主链路可用 |
| 4 | 处理 `--offline` 浏览器安装（方案 A） | 离线归档可用 |
| 5 | 加 CI、ZIP、SHA256、Release | 可对外发布 |
| 6 | 安装脚本 / PATH / 代码签名 / winget（可选） | 一键体验 |

---

## 9. 风险与规避

| 风险 | 影响 | 规避 |
| --- | --- | --- |
| mitmproxy 动态导入漏收集 | 运行时 `ModuleNotFoundError` | `collect_all` + 冒烟测试覆盖抓包 |
| spawn 子进程在 frozen 下失败 | 采集卡死/报错 | 入口调用 `freeze_support()`，CI 实测多子进程 |
| `onefile` 子进程反复解压 | 采集极慢 | 固定使用 onedir |
| 杀软误报 | 用户无法运行 | 不压缩壳、代码签名、提交误报 |
| 包体过大 | 下载体验差 | 不打 Chromium；排除无用依赖；zip 压缩 |
| Playwright 版本与浏览器不匹配 | `--offline` 失败 | 统一版本并用内置驱动安装浏览器 |

---

## 10. 最终建议

先做 **Phase 1–3**，验证「无 Python 环境能完成 `scan` + `crawl`」，这是本项目 90% 的使用场景；`--offline` 的浏览器问题单独作为 Phase 4。CI 跑通后再决定是否投入代码签名与 winget。
