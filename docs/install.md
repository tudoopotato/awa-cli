# awa-cli 安装与部署教程

面向第一次接触本项目的使用者：从一台干净的 Windows 电脑开始，按顺序完成环境准备、代码获取、依赖安装、微信侧准备、证书配置，直到用 `awa doctor` / `scan` / `crawl` / `articles` 跑通一次完整采集。

> 本文偏逐步操作；项目概览、命令输出字段与归档结构见 [README](../README.md)。

- 适用系统：Windows 10 / 11
- 项目地址：<https://github.com/tudoopotato/awa-cli>
- 所有命令均在 **PowerShell** 中执行（开始菜单搜索 “PowerShell” 后打开即可，无需管理员权限）

---

## 0. 快速安装：独立 exe（无需 Python/uv/Git）

> 使用独立 exe 的用户请直接按本节操作，并**跳过第 1–3 节**；第 4 节之后凡写作 `awa` 的命令，在 exe 模式下都替换为 `.\awa.exe`。

1. **下载**：打开 <https://github.com/tudoopotato/awa-cli/releases>，下载最新版本的 `awa-<version>-windows-x64.zip`（例如 `awa-0.1.0-windows-x64.zip`）。

2. **校验（建议）**：下载 Release 附带的 `SHA256SUMS.txt`，在 ZIP 所在目录执行：

   ```powershell
   Get-FileHash .\awa-0.1.0-windows-x64.zip -Algorithm SHA256
   ```

   将输出的 SHA256 值与 `SHA256SUMS.txt` 中对应行比对，一致再继续。

3. **解压**：解压到任意目录，建议路径不含空格与中文（例如 `D:\tools\awa`）。解压后为 onedir 结构：

   ```text
   D:\tools\awa\
   ├── awa.exe
   └── _internal\
   ```

   `awa.exe` 必须与 `_internal\` 保持在同一目录，不要只拷贝 `awa.exe`；整个目录约 172 MB。

4. **首次运行**：在解压目录打开 PowerShell，依次执行：

   ```powershell
   cd D:\tools\awa
   .\awa.exe --help
   .\awa.exe doctor
   ```

   `--help` 应打印 usage 并列出 `doctor` / `scan` / `crawl` / `articles`。`doctor` 此时退出码可能为 2（尚未打开公众号主页、CA 未安装等），按下面的步骤处理即可。

5. **CA 证书（两步，顺序不能反）**：

   1. 在微信 PC 客户端中**手动打开目标公众号主页**（CLI 无法自行打开窗口）；
   2. 先执行一次采集，让 mitmproxy 生成证书文件：

      ```powershell
      .\awa.exe crawl --limit 1
      ```

   3. 再把证书安装到当前用户根证书库（无需管理员权限）：

      ```powershell
      .\awa.exe doctor --install-ca
      ```

   4. 最后确认：

      ```powershell
      .\awa.exe doctor
      ```

   `checks[]` 中 `ca_certificate.ok=true` 即完成。

6. **离线归档浏览器（仅 `--offline` 需要）**：

   ```powershell
   .\awa.exe doctor --install-browser
   ```

   该命令使用随包分发的 Playwright 驱动，将 Chromium 下载到 `<AWA_HOME>\.playwright-browsers`（默认 `%LOCALAPPDATA%\awa\.playwright-browsers`），需要联网。

7. **升级**：下载新版 `awa-<version>-windows-x64.zip`，解压后替换程序目录中的 `awa.exe` 与 `_internal\` 即可。数据目录 `AWA_HOME`（默认 `%LOCALAPPDATA%\awa`）不在程序目录内，升级不会影响数据库、归档与证书。

8. **卸载**：直接删除程序目录（例如 `D:\tools\awa`）即可，`AWA_HOME` 默认保留；如需彻底清理数据，确认已备份后再按 11.4 节删除该目录。

9. **注意事项**：

   - 发布包**未签名**，Windows SmartScreen 可能提示“未知发布者”；确认来源并核对 SHA256 后，可选“更多信息 → 仍要运行”。
   - 采集行为与源码安装完全一致：必须由你手动在微信中打开目标公众号主页，采集期间不要操作鼠标键盘。
   - 若使用 `--home <目录>` 或自定义 `AWA_HOME`，数据库、归档与浏览器缓存都会跟随该目录。

---

## 1. 前置条件

> 使用第 0 节独立 exe 安装的用户无需准备 Python / uv / Git，请直接按第 0 节操作并跳过第 1–3 节。

开始前请确认以下五项。

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| 操作系统 | Windows 10 / 11 | 其他平台上任何子命令都会返回 `status="unsupported-platform"`、退出码 2 |
| Python | 3.13+ | 由 `uv` 自动下载和管理，通常无需手动安装 |
| uv | 最新版 | 本项目使用 uv 管理虚拟环境与依赖 |
| Git | 可选 | 使用 ZIP 下载源码时不需要 |
| 微信 PC 客户端 | 必需 | 需已登录，并能手动打开目标公众号主页 |

### 1.1 安装 uv

任选一种方式（推荐 winget）：

```powershell
winget install --id=astral-sh.uv -e
```

若没有 winget，使用官方安装脚本：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装完成后**新开一个 PowerShell 窗口**，验证：

```powershell
uv --version
```

能打印形如 `uv 0.12.5 (...)` 的版本号即成功。若提示“无法识别 uv”，请关闭并重新打开终端，或重新登录 Windows。

### 1.2 Python 3.13+

`uv` 会读取项目内的 `.python-version`（当前为 `3.13`）并自动准备对应解释器。也可以提前安装：

```powershell
uv python install 3.13
```

验证：

```powershell
uv run python --version
```

在项目目录内执行时应显示 `Python 3.13.x`。

### 1.3 Git（可选）

验证：

```powershell
git --version
```

没有 Git 也能继续，改用第 2 节的 ZIP 下载方式即可。

### 1.4 微信 PC 客户端

保持微信已登录。本工具不会自动打开任何窗口，必须由你在微信里手动打开目标公众号主页（见第 5 节）。

---

## 2. 获取代码

### 方式一：Git 克隆（推荐）

```powershell
git clone https://github.com/tudoopotato/awa-cli.git
cd awa-cli
```

### 方式二：下载 ZIP

1. 浏览器打开 <https://github.com/tudoopotato/awa-cli>；
2. 点击绿色的 **Code** 按钮 → **Download ZIP**；
3. 解压到任意目录（路径尽量不含空格与中文），然后在该目录打开 PowerShell。

### 确认目录正确

以下命令应能看到 `pyproject.toml`、`README.md`、`awa` 目录：

```powershell
Get-ChildItem
```

后续所有命令都必须在这个**项目根目录**下执行。

---

## 3. 安装依赖

在项目根目录执行：

```powershell
uv sync
```

它会创建 `.venv` 虚拟环境并安装 `mitmproxy`、`uiautomation`、`playwright` 等依赖。

**成功的标志**：

- 输出中出现 `Resolved N packages`，并以 `Installed N packages in ...` 或 `Audited N packages in ...` 结束；
- 没有 `error:` 开头的报错；
- 项目根目录出现 `.venv` 文件夹。

随后验证 CLI 可执行：

```powershell
uv run awa --help
```

应打印 `usage: awa [-h] [--home HOME] <command> ...` 以及 `doctor` / `scan` / `crawl` / `articles` 四个子命令。

> 说明：`uv run` 在首次运行时可能自动补装依赖，属正常现象。

---

## 4. 三种使用方式

安装完成后，任选一种方式调用。三种方式功能完全一致，区别只在命令前缀。

### 方式一：仓库内运行（开发用法，最省事）

在项目根目录直接用 `uv run` 前缀：

```powershell
uv run awa --help
```

本文后面的示例默认采用这一写法。若你已全局安装，把 `uv run awa` 换成 `awa` 即可。

### 方式二：全局安装（uv tool）

在项目根目录执行：

```powershell
uv tool install .
```

验证：

```powershell
awa --help
```

若提示 `awa` 不在 PATH 中，执行下面的命令后重开终端：

```powershell
uv tool update-shell
```

之后可在任意目录使用 `awa`。修改源码后需要重新安装才能生效：

```powershell
uv tool install --force .
```

### 方式三：全局安装（pipx）

确认已安装 pipx（没有则先执行第一条）：

```powershell
python -m pip install --user pipx
python -m pipx ensurepath
```

在项目根目录安装：

```powershell
pipx install .
```

验证：

```powershell
awa --help
```

若 PATH 未刷新，请关闭并重新打开 PowerShell。

---

## 5. 微信侧准备

这是最容易忽略、但必须由人工完成的一步：

1. 打开并登录 **微信 PC 客户端**；
2. 在微信中找到目标公众号（订阅号 / 服务号）；
3. **手动打开该公众号的主页**（进入公众号会话后，点击公众号名称/头像进入资料页或历史文章列表）。

**如何判断“开对了”**：

- 窗口中显示的是**该公众号的文章列表**（能看到一篇篇文章的标题和日期），而不是聊天消息列表；
- 窗口不要最小化，也不要被其他窗口完全遮挡；
- 采集只针对当前打开的**那一个**公众号主页窗口。若要换公众号，请先在微信里切换到新主页，再执行命令。

采集期间请**不要操作鼠标键盘**，也不要关闭或最小化微信窗口——采集是前台阻塞任务，键鼠干扰会导致点击/滚动错位。

---

## 6. CA 证书（最容易卡住的一步）

MITM 抓包依赖 mitmproxy 的 CA 证书。该证书**只在代理首次启动时生成**，所以在全新的数据目录下：

1. 此时 `<AWA_HOME>\.mitmproxy\` 里还没有 `mitmproxy-ca-cert.cer`；
2. 直接执行 `awa doctor --install-ca` **无效**（没有文件可装）；
3. 必须先跑一次采集，让 mitmproxy 启动并生成证书。

**正确顺序**：

```powershell
uv run awa crawl --limit 1
```

首次运行可能因为证书未安装而采集失败，这属正常；关键是让 mitmproxy 生成证书文件。随后检查文件是否出现：

```powershell
Test-Path "$env:LOCALAPPDATA\awa\.mitmproxy\mitmproxy-ca-cert.cer"
```

返回 `True` 后安装证书（安装到**当前用户**根证书库，不需要管理员权限）：

```powershell
uv run awa doctor --install-ca
```

最后重新检查：

```powershell
uv run awa doctor
```

**判定依据**（`checks[]` 中 `name="ca_certificate"` 的那一项）：

- `installed` 为 `true`；
- `ok` 为 `true`；
- `thumbprint` 是一串 40 位大写十六进制 SHA-1 指纹，且与证书库中该证书的指纹一致；
- `status` 为 `installed`。

也可以手动核对证书库：

```powershell
Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -like '*mitmproxy*' } | Select-Object Subject, Thumbprint
```

其中 `Thumbprint` 应与 `awa doctor` 输出的 `ca_certificate.thumbprint` 相同。

确认完成后，再次执行采集：

```powershell
uv run awa crawl --limit 1
```

> 若使用 `--home <目录>` 或自定义 `AWA_HOME`，上面的 `Test-Path` 路径请相应替换为 `<AWA_HOME>\.mitmproxy\mitmproxy-ca-cert.cer`。

---

## 7. Playwright 浏览器（仅离线归档需要）

**不加 `--offline` 就完全不需要这一步。** 普通的 `scan` / `crawl` / `articles` 都不依赖 Playwright 浏览器。

只有需要把文章保存为可离线打开的网页副本（`crawl --offline`）时，才要安装 Chromium。安装目录必须与 CLI 使用的缓存目录一致，即 `<AWA_HOME>\.playwright-browsers`。

> **使用独立 exe（第 0 节）的用户**：无需设置 `PLAYWRIGHT_BROWSERS_PATH`，也不用 `python -m playwright`，直接在解压目录执行 `.\awa.exe doctor --install-browser` 即可。

在项目根目录执行（命令与 `awa doctor` 中 `playwright_browsers` 检查项给出的提示一致）：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='<AWA_HOME>\.playwright-browsers'; uv run python -m playwright install chromium
```

使用默认数据目录（`%LOCALAPPDATA%\awa`）时，可直接粘贴：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\awa\.playwright-browsers"; uv run python -m playwright install chromium
```

若使用 `--home <目录>` 或自定义 `AWA_HOME`，请把 `PLAYWRIGHT_BROWSERS_PATH` 指向 `<AWA_HOME>\.playwright-browsers`。

全局安装（`uv tool install .` 或 `pipx install .`）时，仓库外没有项目环境，`uv run` 不可用，可改用工具环境的 Python：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\awa\.playwright-browsers"; & "$env:APPDATA\uv\tools\awa-cli\Scripts\python.exe" -m playwright install chromium
```

或：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\awa\.playwright-browsers"; & "$env:LOCALAPPDATA\pipx\pipx\venvs\awa-cli\Scripts\python.exe" -m playwright install chromium
```

安装后验证：

```powershell
uv run awa doctor
```

`checks[]` 中 `playwright_browsers.ok=true` 即就绪。该项是**非阻塞**检查：即使为 `false`，`ready` 仍可为 `true`、退出码仍为 0，只是 `--offline` 会失败。

---

## 8. 跑通验证

确认微信已打开目标公众号主页后，按下面四步依次执行。每条命令后附成功标志与常见失败。

### 第 1 步：环境检查

```powershell
uv run awa doctor
```

- **成功标志**：退出码 0；`ready=true`；`status="ok"`；`checks[]` 中非阻塞项之外全部 `ok=true`。
- **常见失败**：退出码 2（前置条件不满足）。看 `status`：
  - `window-not-found` → 第 5 节的公众号主页没开对；
  - `ca-not-installed` → 按第 6 节先跑一次采集再 `--install-ca`；
  - `not-ready` → 逐项看 `checks[]` 的 `detail`（端口占用、目录不可写等）。

### 第 2 步：只读预览

```powershell
uv run awa scan --limit 5
```

- **成功标志**：退出码 0；`count>0`；`items[]` 里能看到文章标题与日期。`scan` 不点击文章、不启动代理、不写数据库。
- **常见失败**：`count=0` → 主页窗口不对，或日期参数把文章过滤掉了；退出码 2 → 同第 1 步。

### 第 3 步：执行采集（先采 1 篇）

```powershell
uv run awa crawl --limit 1
```

- **成功标志**：退出码 0；`status="completed"`；`processedCount=1`；`detailSuccessCount>=1`；`articles[]` 中有 `archiveDir`。
- **常见失败**：`status="window-not-found"`（退出码 2）→ 回第 5 节；`status="failed"` / `timeout`（退出码 1）→ 看 `errors[]` 的 `latestError`；`errorCount>0` 但不影响已成功篇目时，可在同一主页重跑并加 `--skip-collected` 只补缺。

### 第 4 步：查询入库结果

```powershell
uv run awa articles --limit 5
```

- **成功标志**：退出码 0；`articleCount>=1`；`items[]` 中对应文章 `existsOnDisk=true`，`archiveDir` 指向 `<AWA_HOME>\storages\...`。
- **常见失败**：`status="database-missing"`（退出码 2）→ 数据库尚未初始化，先成功执行一次 `doctor` 或 `crawl`。

补充说明：

- 退出码 `0` = 成功，`1` = 运行失败，`2` = 前置条件不满足，`3` = 参数错误；
- 全部输出为 UTF-8 JSON，进度与警告走 stderr，可直接被脚本或 Agent 解析。

---

## 9. 数据目录（AWA_HOME）

### 9.1 默认位置与优先级

| 优先级 | 来源 | 示例 |
| --- | --- | --- |
| 1（最高） | 命令行 `--home <PATH>` | `awa doctor --home D:\awa-data` |
| 2 | 环境变量 `AWA_HOME` | `$env:AWA_HOME='D:\awa-data'` |
| 3（默认） | `%LOCALAPPDATA%\awa` | `%LOCALAPPDATA%\awa` |

顶层与每个子命令都接受 `--home`，语义一致。

设置用户级环境变量（永久生效，需重开终端）：

```powershell
[Environment]::SetEnvironmentVariable('AWA_HOME', 'D:\awa-data', 'User')
```

仅当前窗口临时生效：

```powershell
$env:AWA_HOME = 'D:\awa-data'
```

### 9.2 目录结构

```text
%LOCALAPPDATA%\awa\
├── custom.yaml                  # 可选：自定义配置，覆盖内置 system.yaml 的同名字段
├── data\
│   ├── sql\
│   │   └── awa-v2.1.sqlite3     # SQLite 数据库（由 doctor / scan / crawl 自动初始化）
│   ├── logs\                    # runtime-summary.log、runtime-detail.log
│   ├── tmp\                     # 临时文件
│   └── runtime\                 # 运行时状态（含 huey 任务队列文件）
├── storages\                    # 文章归档根目录
├── .mitmproxy\                  # mitmproxy 配置目录与 CA 证书（mitmproxy-ca-cert.cer）
└── .playwright-browsers\        # 可选：离线归档用的 Chromium（安装后才会出现）
```

说明：

- `custom.yaml` 不存在时只使用内置默认配置；
- `storages\`、`data\`、`.mitmproxy\` 都是用户数据，请勿随意删除；
- 归档目录形如 `<AWA_HOME>\storages\<公众号名>\<发布时间 标题__哈希>\`。

### 9.3 备份与迁移

备份（先关闭正在运行的采集）：

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item -Recurse -Force "$env:LOCALAPPDATA\awa" "$env:USERPROFILE\awa-backup-$stamp"
```

迁移到另一台电脑：

1. 把备份目录复制到新电脑（例如 `D:\awa-data`）；
2. 在新电脑设置 `AWA_HOME`：

   ```powershell
   [Environment]::SetEnvironmentVariable('AWA_HOME', 'D:\awa-data', 'User')
   ```

3. 重开终端后执行 `awa doctor`；
4. 证书属于“当前用户证书库”，不随目录迁移，若 `ca_certificate.ok=false`，按第 6 节重新执行 `awa doctor --install-ca`。

---

## 10. 安装 Skill（可选）

仓库自带 `skills/wechat-article-crawler/`。把它复制到 AI Agent 的 skills 目录后，Agent 即可按内置流程自动调用 `awa`。

### Trae

```powershell
Copy-Item -Recurse -Force .\skills\wechat-article-crawler "$env:USERPROFILE\.trae-cn\skills\"
```

复制后确认：

```powershell
Test-Path "$env:USERPROFILE\.trae-cn\skills\wechat-article-crawler\SKILL.md"
```

### 其它 Agent

按各自约定的 skills 目录放置整个 `wechat-article-crawler` 文件夹（保持 `SKILL.md` 位于该文件夹根部）。常见做法是复制到 Agent 配置目录下的 `skills\` 子目录，然后在 Agent 中刷新/重载技能列表。

---

## 11. 升级与卸载

### 11.1 仓库内运行方式

```powershell
git pull
uv sync
```

ZIP 用户请重新下载 ZIP 覆盖代码，再执行 `uv sync`。

### 11.2 uv tool 全局安装

```powershell
uv tool upgrade awa-cli
```

若安装自本地目录且升级未生效，用重新安装代替：

```powershell
uv tool install --force .
```

卸载：

```powershell
uv tool uninstall awa-cli
```

### 11.3 pipx 全局安装

```powershell
pipx upgrade awa-cli
```

卸载：

```powershell
pipx uninstall awa-cli
```

### 11.4 数据是否保留

**默认保留。** 卸载只移除程序与虚拟环境，不会删除 `AWA_HOME`（默认 `%LOCALAPPDATA%\awa`）中的数据库、归档与证书目录。若要彻底清理，请先确认数据已备份，再手动删除该目录：

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\awa"
```

CA 证书如不再需要，可在“管理用户证书 → 受信任的根证书颁发机构 → 证书”中手动删除 mitmproxy 证书。

---

## 12. 常见问题

### 12.1 未找到公众号主页窗口

**现象**：`doctor` 的 `wechat_home_window.ok=false`；`scan` / `crawl` 返回 `status="window-not-found"`、退出码 2。

**处理**：在微信 PC 客户端重新打开目标公众号主页（窗口内能看到该公众号的文章列表），确保窗口未最小化，然后重试。采集只认当前打开的**一个**主页窗口。

### 12.2 CA 未安装

**现象**：`doctor` 的 `ca_certificate.ok=false`，`status` 为 `missing` 或 `file-present`。

**处理**：若证书文件不存在，先执行一次 `awa crawl --limit 1` 让 mitmproxy 生成；若文件已存在但未安装，执行 `awa doctor --install-ca`，再运行 `awa doctor` 确认 `ca_certificate.installed=true`。

### 12.3 18000 端口被占用

**现象**：`doctor` 的 `mitm_port.ok=false`，`detail` 显示 `127.0.0.1:18000` 已被占用。

**排查占用进程**：

```powershell
Get-NetTCPConnection -LocalPort 18000 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess
```

拿到 `OwningProcess` 后可查看进程名：

```powershell
Get-Process -Id <PID>
```

**处理**：关闭占用该端口的程序（常见为上一次未退出的代理或采集进程），然后重新执行 `awa doctor`。

### 12.4 采集 0 篇

**现象**：`scan` 的 `count=0`，或 `crawl` 的 `processedCount=0`。

**处理**：

- 确认微信里打开的是正确的公众号主页，而不是聊天窗口；
- 检查是否使用了 `--date-mode` / `--start` / `--end` 把文章过滤掉，先去掉日期条件重试；
- 文章列表需要先加载出来，可适当增大 `scan --max-scrolls`；
- 仍为 0 时执行 `awa doctor`，确认 `wechat_home_window.ok=true`。

### 12.5 离线归档缺浏览器

**现象**：`doctor` 的 `playwright_browsers.ok=false`，或 `--offline` 报浏览器相关错误。

**处理**：按第 7 节安装 Chromium。该项不影响普通采集，只有 `--offline` 需要。

### 12.6 系统代理异常

**现象**：采集后网络异常，或 `doctor` 报代理相关错误。

**处理**：不要手工修改注册表中的系统代理。CLI 会在采集时临时把系统代理切到 `127.0.0.1:18000`，结束后自动恢复。异常时可查看当前代理状态：

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable, ProxyServer
```

确认没有残留的 `127.0.0.1:18000` 后重新运行 `awa doctor`；必要时重启相关程序或系统。

---

## 13. 安全与合规

本项目采用 **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International（CC BY-NC-SA 4.0）** 许可，完整条款见 [LICENSE](../LICENSE)。使用与再分发时须遵守：

- **禁止商业使用**：不得将本项目或其衍生作品用于任何商业目的；
- **保留署名**：必须保留原作者署名及原项目链接；
- **相同方式共享**：修改后的作品必须以相同许可（CC BY-NC-SA 4.0）发布。

此外：

- 本项目仅供**研究、学习与公开材料整理**使用；
- 采集过程会临时修改系统代理并读取微信窗口 UI 内容，请仅在你有权访问与处理的内容上使用；
- 使用者需自行遵守微信平台服务协议、《中华人民共和国网络安全法》及相关法律法规，并自行承担由此产生的平台规则风险、法律风险与研究伦理责任。

---

## 附：最小跑通清单

```powershell
git clone https://github.com/tudoopotato/awa-cli.git
cd awa-cli
uv sync
uv run awa --help
```

打开目标公众号主页，然后：

```powershell
uv run awa crawl --limit 1
uv run awa doctor --install-ca
uv run awa doctor
uv run awa scan --limit 5
uv run awa crawl --limit 1
uv run awa articles --limit 5
```

四步全部退出码为 0，即部署完成。
