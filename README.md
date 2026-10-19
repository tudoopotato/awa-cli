# awa-cli

Windows 上的微信公众号文章采集命令行工具，面向学术研究与公开材料整理。

`awa` 复用桌面端的采集链路（MITM 抓包 → HTML 解析 → 入库归档），但不包含任何图形界面：所有子命令只向 stdout 输出一个结构化 JSON，人类可读的进度与警告走 stderr，便于脚本与 AI Agent 驱动。

---

## 免责声明

本项目仅供**研究、学习与公开材料整理**使用。

使用者需自行遵守微信平台服务协议、《中华人民共和国网络安全法》及相关法律法规，合理处理公开文章材料、引用方式与研究结果。使用过程中产生的法律风险、平台规则风险与研究伦理责任，均由使用者自行承担。

---

## 本项目与原仓库的关系

本仓库是 [`Access_wechat_article`](https://github.com/yeximm/Access_wechat_article) 的 **CLI 衍生版本**：

- 只保留命令行采集能力（`doctor` / `scan` / `crawl` / `articles`），**不包含桌面界面**；
- 采集核心代码衍生自上游项目，上游采用 **CC BY-NC-SA 4.0** 许可；
- 依据该许可，本项目保留原作者署名、**禁止商业使用**、修改后的作品须以**相同方式共享**（详见 [LICENSE](LICENSE)）。

---

## 系统要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11（其他平台上的任何子命令都会返回 `status="unsupported-platform"`、退出码 2） |
| Python | 3.13+ |
| 微信 PC 客户端 | 必需；运行前需**手动打开目标公众号主页**（CLI 无法自行打开窗口） |

---

## 安装

> 第一次安装？请按 [docs/install.md](docs/install.md) 的逐步教程操作。

### 方式一：开发用法（从源码运行）

```powershell
git clone https://github.com/tudoopotato/awa-cli.git awa-cli
cd awa-cli
uv sync
uv run awa --help
```

> 仓库地址为 `https://github.com/tudoopotato/awa-cli.git`；已在本地拿到源码时可跳过 `git clone`，直接进入项目目录。

### 方式二：全局安装（uv tool）

```powershell
uv tool install .
awa --help
```

### 方式三：全局安装（pipx）

```powershell
pipx install .
```

### 方式四：下载独立 exe（无需 Python，推荐给非开发者）

1. 打开仓库 Release 页面 <https://github.com/tudoopotato/awa-cli/releases>，下载最新版本的 `awa-<version>-windows-x64.zip`（例如 `awa-0.1.0-windows-x64.zip`）；
2. 解压到任意目录（建议路径不含空格与中文）。解压后为 onedir 结构：`awa.exe` 与 `_internal\` 必须保持在同一目录，整个目录约 172 MB；
3. 在解压目录打开 PowerShell，依次执行：

   ```powershell
   .\awa.exe --help
   .\awa.exe doctor
   ```

无需安装 Python / uv / Git。程序目录未加入 PATH，因此后续所有示例中的 `awa` 都要替换为 `.\awa.exe`（例如 `.\awa.exe scan --limit 20`）。

补充说明：

- CA 流程与源码安装一致：先执行 `.\awa.exe crawl --limit 1` 让 mitmproxy 生成证书，再执行 `.\awa.exe doctor --install-ca`，最后用 `.\awa.exe doctor` 确认 `ca_certificate.ok=true`；
- 离线归档所需 Chromium 可执行 `.\awa.exe doctor --install-browser`，由内置 Playwright 驱动下载到 `<AWA_HOME>\.playwright-browsers`；
- 发布包未签名，Windows SmartScreen 可能提示“未知发布者”；建议用 Release 附带的 `SHA256SUMS.txt` 校验下载的 ZIP 后再运行；
- 数据目录仍是 `AWA_HOME`（默认 `%LOCALAPPDATA%\awa`）；升级或卸载只替换/删除程序目录，数据保留；
- 仍需由你手动在微信 PC 客户端打开目标公众号主页，CLI 无法自行打开窗口。

安装完成后，下文所有示例都可以直接使用 `awa ...`。若采用开发用法，把 `awa` 换成 `uv run awa` 即可（例如 `uv run awa doctor`）；若采用方式四，把 `awa` 换成 `.\awa.exe`，并在解压目录中执行。

---

## 首次使用三步

1. **打开公众号主页**：在微信 PC 客户端中手动打开目标公众号主页，窗口里应能看到该公众号的文章列表。采集只针对当前打开的那一个主页窗口。
2. **检查环境**：执行

   ```powershell
   awa doctor
   ```

   按 `checks[]` 中的提示修复。若 `ca_certificate.ok=false`，执行：

   ```powershell
   awa doctor --install-ca
   ```

   若是 `wechat_home_window` 未通过，请回到第 1 步确认主页窗口已打开且未最小化。

3. **先预览，再采集**：

   ```powershell
   awa scan --limit 20
   awa crawl --limit 5
   ```

### 关于 CA 证书（重要）

在**全新的数据目录**下，CA 证书文件尚不存在，`awa doctor --install-ca` 此时无法完成安装。正确顺序是：

> **首次运行 → CA 生成 → 安装证书 → 再次采集**

具体为：

1. 先执行一次采集（如 `awa crawl --limit 1`），mitmproxy 会在 `<AWA_HOME>\.mitmproxy\` 下自动生成 CA 证书；
2. 再执行 `awa doctor --install-ca`，把证书安装到**当前用户根证书库**；
3. 重新执行 `awa doctor` 确认 `ca_certificate.ok=true`，然后继续正常采集。

采集期间请不要操作鼠标键盘，也不要关闭或最小化微信窗口；采集是前台阻塞任务，键鼠干扰可能导致点击/滚动错位。

---

## 命令说明

通用约定：

- 顶层与每个子命令都接受 `--home <PATH>`（AWA_HOME 用户数据目录），语义一致；
- stdout 只输出一个 JSON 文档（UTF-8、缩进 2 空格，可直接 `json.loads`），stderr 输出 `[awa]` / `[awa][warn]` 开头的进度与告警；
- 每个子命令都支持 `-h` / `--help`。

### `awa doctor`

```text
usage: awa doctor [-h] [--install-ca] [--home HOME]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--install-ca` | 关闭 | CA 证书文件存在但未安装时，安装到当前用户根证书库并重新检查 |
| `--home HOME` | 无 | AWA_HOME 用户数据目录 |
| `-h`, `--help` | — | 显示帮助 |

输出字段：`ok`、`command`、`status`、`ready`、`home`、`checks[]`、`accountName`、`dbPath`、`proxyAddress`。

`status` 取值：`ok`、`window-not-found`、`ca-not-installed`、`not-ready`。

`checks[]` 每项含 `name`、`ok`、`detail`，`name` 取值：

| 检查项 | 含义 |
| --- | --- |
| `config` | 配置加载与校验 |
| `storage_dirs` | 归档、数据库、临时、日志四个目录存在且可写 |
| `database` | SQLite 数据库及必需表校验 |
| `mitm_port` | MITM 监听端口（默认 `127.0.0.1:18000`）是否空闲 |
| `ca_certificate` | CA 证书文件与用户根证书库安装状态 |
| `wechat_home_window` | 是否定位到公众号主页窗口并读到文章日期分组 |
| `dependencies` | `mitmproxy`、`uiautomation` 依赖是否已安装 |
| `playwright_browsers` | `<AWA_HOME>\.playwright-browsers` 下是否有 Chromium（**非阻塞**，仅影响 `--offline`） |

### `awa scan`

只读预览公众号主页文章：不点击文章、不启动 MITM、不采集文章详情。

```text
usage: awa scan [-h] [--limit LIMIT] [--date-mode {all,range,before,after}]
                [--start START] [--end END] [--max-scrolls MAX_SCROLLS]
                [--home HOME]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--limit LIMIT` | `0`（不限） | 最多列出多少篇 |
| `--date-mode {all,range,before,after}` | `all` | 日期筛选模式 |
| `--start START` | 无 | 起始日期，格式 `YYYY-MM-DD` |
| `--end END` | 无 | 截止日期，格式 `YYYY-MM-DD` |
| `--max-scrolls MAX_SCROLLS` | `200` | 滚动次数上限，达到后停止并置 `truncated=true` |
| `--home HOME` | 无 | AWA_HOME 用户数据目录 |
| `-h`, `--help` | — | 显示帮助 |

输出字段：`ok`、`command`、`status`、`accountName`、`dateFilter`（含 `mode`、`label`）、`count`、`items[]`、`boundaryReached`、`truncated`、`scrolls`、`rawCount`、`skippedCount`。

`items[]` 每项含：`sequence`（窗口内序号，可能跳号）、`title`、`articleDate`、`fingerprint`。

### `awa crawl`

执行文章采集。

```text
usage: awa crawl [-h] [--limit LIMIT] [--date-mode {all,range,before,after}]
                 [--start START] [--end END] [--skip-collected]
                 [--interval INTERVAL] [--timeout TIMEOUT] [--comments]
                 [--offline] [--offline-mode {standard,beta}] [--home HOME]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--limit LIMIT` | `0`（不限） | 最多采集多少篇 |
| `--date-mode {all,range,before,after}` | `all` | 日期筛选模式 |
| `--start START` | 无 | 起始日期，格式 `YYYY-MM-DD` |
| `--end END` | 无 | 截止日期，格式 `YYYY-MM-DD` |
| `--skip-collected` | 关闭 | 跳过已入库文章 |
| `--interval INTERVAL` | `0.0` | 单篇任务派发间隔（秒） |
| `--timeout TIMEOUT` | `0.0`（不限） | 整体超时（秒），超时后请求停止并返回 `status="timeout"` |
| `--comments` | 关闭 | 采集文章评论（默认不采集评论） |
| `--offline` | 关闭 | 对文章做离线归档（默认不做离线归档） |
| `--offline-mode {standard,beta}` | `standard` | 离线归档模式：`standard` 常规模式，`beta` 带状态实验模式（仅在 `--offline` 时生效） |
| `--home HOME` | 无 | AWA_HOME 用户数据目录 |
| `-h`, `--help` | — | 显示帮助 |

输出字段：`ok`、`command`、`status`、`taskId`、`accountName`、`processedCount`、`detailSuccessCount`、`skippedCount`、`errorCount`、`averageArticleSeconds`、`articles[]`、`errors[]`、`startedAt`、`finishedAt`、`logPath`、`commentsEnabled`、`offlineEnabled`。

- `status` 取值：`completed`、`failed`、`cancelled`、`timeout`、`window-not-found`；
- `articles[]` 每项含：`articleId`、`title`、`publishedArticleTime`、`articleLink`、`archiveDir`；
- `errors[]` 为失败摘要，每项含 `count`、`latestError`。

日期参数校验（`scan` / `crawl` 共用）：`--date-mode range` 必须同时提供 `--start` 与 `--end`；`before` 必须提供 `--end`；`after` 必须提供 `--start`；日期格式必须为 `YYYY-MM-DD`。不满足时退出码为 3。

### `awa articles`

只读查询已采集文章（不初始化数据库）。

```text
usage: awa articles [-h] [--account ACCOUNT] [--limit LIMIT] [--since SINCE]
                    [--home HOME]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--account ACCOUNT` | 无（全部） | 按公众号名过滤 |
| `--limit LIMIT` | `50`（生效范围 1–500，超出会被夹取） | 返回条数上限 |
| `--since SINCE` | 无 | 按最后采集时间过滤（`YYYY-MM-DD`） |
| `--home HOME` | 无 | AWA_HOME 用户数据目录 |
| `-h`, `--help` | — | 显示帮助 |

输出字段：`ok`、`command`、`status`、`accountCount`、`articleCount`、`items[]`、`dbPath`、`storageRoot`。

`items[]` 每项含：`articleId`、`accountName`、`title`、`publishedArticleTime`、`articleLink`、`archiveDir`、`lastCollectedTime`、`existsOnDisk`。

---

## 评论与离线归档

两者都是**可选能力，默认关闭**，需要显式传参：

| 能力 | 参数 | 默认 | 说明 |
| --- | --- | --- | --- |
| 评论采集 | `--comments` | 关闭 | 追加写入 `comments/final.json` |
| 离线归档 | `--offline` | 关闭 | 追加生成 `index.html` + `assets/` |
| 离线归档模式 | `--offline-mode {standard,beta}` | `standard` | 仅在 `--offline` 时生效 |

离线归档依赖 Playwright 的 Chromium。首次使用前请安装到 AWA_HOME 的浏览器缓存目录。

`awa doctor` 的 `playwright_browsers` 检查项在未就绪时，`detail` 会给出可直接执行的安装命令（`installCommand` 字段即该命令），其形式为：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH='<AWA_HOME>\.playwright-browsers'; uv run python -m playwright install chromium
```

默认 AWA_HOME 为 `%LOCALAPPDATA%\awa`，对应的可执行写法为：

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\awa\.playwright-browsers"; uv run python -m playwright install chromium
```

按安装方式选择执行位置：

- **仓库开发用法**（方式一，已在仓库根执行 `uv sync`）：在仓库根目录直接执行上面的命令。
- **全局安装（`uv tool install .`）**：仓库外没有 `uv run` 的项目环境，需改用工具环境的 Python 执行等价命令（`uv tool list --show-paths` 可查看工具环境路径，默认在 `%APPDATA%\uv\tools\awa-cli`）：

  ```powershell
  $env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\awa\.playwright-browsers"; & "$env:APPDATA\uv\tools\awa-cli\Scripts\python.exe" -m playwright install chromium
  ```

- **全局安装（`pipx install .`）**：同样使用 pipx 虚拟环境中的 Python（默认位于 `%LOCALAPPDATA%\pipx\pipx\venvs\awa-cli`，若修改过 `PIPX_HOME` 请相应调整）：

  ```powershell
  $env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\awa\.playwright-browsers"; & "$env:LOCALAPPDATA\pipx\pipx\venvs\awa-cli\Scripts\python.exe" -m playwright install chromium
  ```

若使用 `--home <目录>` 或自定义 `AWA_HOME`，请把 `PLAYWRIGHT_BROWSERS_PATH` 指向 `<AWA_HOME>\.playwright-browsers`。

安装后可用 `awa doctor --home <目录>` 查看 `playwright_browsers` 检查项：`ok=true` 表示当前 Playwright 版本所需组件均已就绪；未就绪时 `detail` 会列出缺失项并给出上述安装命令。该项**不影响**其他命令的 `ready` 判定。

---

## 数据目录（AWA_HOME）

解析优先级：`--home <路径>` > 环境变量 `AWA_HOME` > Windows 默认 `%LOCALAPPDATA%\awa`（`LOCALAPPDATA` 缺失时退回 `~\AppData\Local\awa`）。

默认目录结构：

```text
%LOCALAPPDATA%\awa\
├── custom.yaml                  # 可选：自定义配置，覆盖内置 system.yaml 的同名字段
├── data\
│   ├── sql\
│   │   └── awa-v2.1.sqlite3     # SQLite 数据库（文件名由数据结构版本决定）
│   ├── logs\                    # runtime-summary.log、runtime-detail.log
│   ├── tmp\                     # 临时文件（中间结果、诊断记录等）
│   └── runtime\                 # 运行时状态目录（含 runtime\huey 任务队列文件）
├── storages\                    # 文章归档根目录
├── .mitmproxy\                  # mitmproxy 配置目录与 CA 证书（mitmproxy-ca-cert.cer）
└── .playwright-browsers\        # 可选：离线归档用的 Chromium（安装后才会出现）
```

说明：

- `custom.yaml` 不存在时程序只使用内置默认配置，可自行新建以覆盖需要调整的字段；
- `data\sql\awa-v2.1.sqlite3` 由 `doctor` / `scan` / `crawl` 自动初始化；`articles` 在数据库不存在时返回 `status="database-missing"`、退出码 2；
- `data\logs\` 中 `runtime-summary.log` 的路径会出现在 `crawl` 输出的 `logPath` 字段；
- `.mitmproxy\`、`storages\`、`data\` 属于用户数据，请勿随意删除或移动。

---

## 归档结构

每篇文章归档在：

```text
<AWA_HOME>\storages\<公众号名>\<发布时间 标题__哈希>\
```

其中目录名格式为 `YYYY-MM-DD HH-MM <清洗后的标题>__<12 位小写十六进制哈希>`（Windows 非法字符会被替换为 `_`）。

基础文件：

```text
<文章目录>\
├── origin\
│   ├── main.html              # 抓取到的原始页面
│   └── request.json           # 抓包请求信息
└── article_detail.json        # 解析后的文章详情
```

按需追加：

| 参数 | 追加内容 |
| --- | --- |
| `--comments` | `comments\final.json` |
| `--offline` | `index.html` + `assets\` |

---

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功（`ok=true`） |
| `1` | 运行失败（采集 `failed` / `cancelled` / `timeout`、查询失败、未预期异常） |
| `2` | 前置条件不满足（未找到主页窗口、CA 未安装、端口占用、数据库不存在、非 Windows 等） |
| `3` | 参数错误（参数解析失败或日期校验失败） |

---

## 安装 Skill（可选）

仓库内自带 `skills/wechat-article-crawler/`，把它复制到 AI Agent 的 skills 目录（例如 Trae 的 `%USERPROFILE%\.trae-cn\skills\`），Agent 即可按流程自动调用 `awa`：

```powershell
Copy-Item -Recurse -Force .\skills\wechat-article-crawler "$env:USERPROFILE\.trae-cn\skills\"
```

---

## 常见问题

| 现象 | 判断依据 | 处理方式 |
| --- | --- | --- |
| 未找到公众号主页窗口 | `doctor` 的 `wechat_home_window.ok=false`；`scan`/`crawl` 返回 `status="window-not-found"`、退出码 2 | 在微信 PC 客户端打开目标公众号主页（窗口内能看到文章列表），并确保窗口未最小化，然后重试 |
| CA 未安装 | `doctor` 的 `ca_certificate.ok=false` | 若证书文件已生成，执行 `awa doctor --install-ca`；若尚不存在，先跑一次采集让 mitmproxy 生成，再安装 |
| 18000 端口被占用 | `doctor` 的 `mitm_port.ok=false`，`detail` 显示 `127.0.0.1:18000` 已被占用 | 关闭占用该端口的程序后重新执行 `awa doctor` |
| 采集 0 篇 | `scan` 的 `count=0` 或 `crawl` 的 `processedCount=0` | 确认当前主页窗口是否正确；检查 `--date-mode` / `--start` / `--end` 是否把文章过滤掉，放宽或去掉日期条件后重试 |
| 部分失败 | `crawl` 的 `errorCount>0`，`errors[]` 有 `latestError` | 读取 `errors[]` 定位原因；可在同一主页重新 `crawl`（可加 `--skip-collected` 只补缺） |
| 系统代理异常 | 采集后网络异常 | 不要手工修改系统代理或注册表。CLI 会在采集时临时切换到 `127.0.0.1:18000` 并在结束后恢复；异常时重跑 `awa doctor` 检查，必要时重启相关程序 |
| 离线归档缺浏览器 | `doctor` 的 `playwright_browsers.ok=false`，或离线归档报浏览器相关错误 | 按上文「评论与离线归档」给出的命令安装：`$env:PLAYWRIGHT_BROWSERS_PATH='<AWA_HOME>\.playwright-browsers'; uv run python -m playwright install chromium`（全局安装改用对应环境的 Python）；普通采集不受影响 |

---

## 上游署名与许可

本项目部分代码衍生自 [`yeximm/Access_wechat_article`](https://github.com/yeximm/Access_wechat_article)，原项目采用 **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International（CC BY-NC-SA 4.0）** 许可。

依据该许可：

- **保留署名**：必须保留原作者署名及原项目链接；
- **禁止商业使用**：不得将本项目或其衍生作品用于商业目的；
- **相同方式共享**：修改后的作品必须以相同许可（CC BY-NC-SA 4.0）发布。

完整条款见 [LICENSE](LICENSE)。

---

## 开发

```powershell
uv run pytest -q
```
