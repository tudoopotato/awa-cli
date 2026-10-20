---
name: wechat-article-crawler
description: 采集微信公众号公开文章。当用户要求“爬取/采集微信公众号的文章”“抓某个公众号的文章列表”“把这个公众号的文章存下来”，或在微信 PC 客户端打开了某个公众号主页并希望批量抓取文章时使用。通过 awa CLI（`awa doctor` / `awa scan` / `awa crawl` / `awa articles`）完成，输出结构化 JSON。
---

# 微信公众号文章采集（wechat-article-crawler）

通过 `awa` CLI 采集微信公众号公开文章。CLI 复用桌面端的采集链路（MITM 抓包 → HTML 解析 → 入库 + 归档），但完全无界面，只向 stdout 输出一个结构化 JSON，便于 Agent 驱动。

## 1. 使用前提

- **操作系统**：仅支持 **Windows 10/11**。非 Windows 平台任一命令都会返回 `ok=false`、`status="unsupported-platform"`、退出码 2。
- **CLI 已安装**：要求 `awa` 命令可直接调用。
  - 若仓库已 `uv sync`，可在项目根目录用 `uv run awa <子命令> [选项]` 执行；
  - 或把它装成全局命令：仓库根目录执行 `uv tool install .`（推荐）或 `pipx install .`，之后直接用 `awa <子命令>`。
- **用户必须先手动打开公众号主页**：CLI **无法自己打开**任何窗口。需要用户自己在**微信 PC 客户端**中打开目标公众号的主页（窗口里能看到该公众号的文章列表；窗口标题可能是「公众号 / 服务号 / 订阅号」，也可能是「微信」）。采集只针对当前打开的那一个主页窗口。
- **CA 证书**：MITM 抓包依赖 mitmproxy 的 CA 证书已安装到**当前用户根证书库**。先用 `awa doctor` 检查；若 `ca_certificate.ok=false`，执行 `awa doctor --install-ca` 安装。
- **数据目录 AWA_HOME**：默认 `%LOCALAPPDATA%\awa`（即 `C:\Users\<用户>\AppData\Local\awa`），可用环境变量 `AWA_HOME` 或命令行 `--home <路径>` 覆盖（解析优先级：`--home` > `AWA_HOME` 环境变量 > `%LOCALAPPDATA%\awa`）。
- **评论采集与离线归档均为可选能力**：`crawl --comments`、`crawl --offline` 默认**关闭**，只在用户明确需要评论数据或离线网页副本时才开启；两者都会显著增加单篇耗时。
- **离线归档需先安装 Playwright Chromium**（仅 `--offline` 需要）。用 CLI 自带命令安装即可，它会自动装到 CLI 使用的缓存目录（`<AWA_HOME>\.playwright-browsers`，默认即 `%LOCALAPPDATA%\awa\.playwright-browsers`），无需手动设置环境变量：

  ```powershell
  awa doctor --install-browser
  ```

  项目内未安装全局命令时用 `uv run awa doctor --install-browser`。该命令需要联网下载约 150 MB，耗时较长；安装完成后可用 `awa doctor` 确认 `playwright_browsers.ok=true`。
- **`awa doctor` 的 `playwright_browsers` 检查项只影响离线归档**：该项为**非阻塞**检查（`ok=false` 时 `ready` 仍可为 `true`、退出码仍为 0），不影响 `scan` / `crawl` / `articles` 等普通采集流程；只有准备使用 `--offline` 时才需要处理。
- **采集期间**：提醒用户**不要操作鼠标键盘**，**不要关闭或最小化微信窗口**。采集是前台阻塞任务，鼠标键盘干扰会导致点击/滚动错位。

## 2. 标准流程

严格按以下顺序执行（`doctor` → `scan` → 用户确认 → `crawl` → `articles`）：

1. **`doctor` — 检查环境**
   - 执行 `awa doctor`。
   - 判定依据：`ready=true` 且退出码 0 → 环境就绪，进入第 2 步。
   - 若退出码 2（`ready=false`），看 `checks[]` 里哪个 `ok=false`，按 `name` 定位（`playwright_browsers` 为非阻塞项，不会单独导致退出码 2）：
     - `wechat_home_window` 未通过 → 请用户在微信 PC 客户端打开目标公众号主页后重试。
     - `ca_certificate` 未通过 → 执行 `awa doctor --install-ca` 安装证书后重新 `doctor`。
     - `mitm_port` 未通过 → 提示用户关闭占用 `127.0.0.1:18000` 端口的程序。
     - `playwright_browsers` 未通过 → 只影响 `--offline` 离线归档，**不阻塞** `ready`，此时无需处理；若用户确实要离线归档，按第 1 节的 PowerShell 命令安装 chromium 后重试。
     - 其他项（`config` / `storage_dirs` / `database` / `dependencies`）未通过 → 结合 `detail` 说明原因并请用户处理，不要臆断。

2. **`scan` — 只读预览列表（不抓取）**
   - 执行 `awa scan [--limit N] [--date-mode …] …`。`scan` **不点击文章、不启动 MITM、不写数据库**。
   - 把输出里的 `accountName`、`count` 和 `items[]` 的文章标题（连同 `articleDate` 发布日期）**展示给用户**。
   - **请用户确认采集范围**（要采哪些 / 限制多少篇 / 哪个日期区间）。用户确认后才进入第 3 步。

3. **`crawl` — 执行采集（需用户确认范围后）**
   - 依据用户确认的范围，用 `--limit` / `--date-mode` / `--start` / `--end` 控制范围。
   - **按用户需要决定是否加 `--comments` / `--offline`**：默认都不加；用户只要文章正文时保持默认，明确需要评论或离线网页副本时才加对应开关（`--offline-mode` 仅在加 `--offline` 时生效）。两者都会**显著增加耗时**，加之前先向用户说明。
   - 这是**长耗时前台任务**，必须为命令设置足够长的超时：例如 `--limit 10` 建议至少预留 **10 分钟**（开启 `--comments` / `--offline` 时需更久）。若不想由外部超时控制，可不设 CLI 自身的 `--timeout`（默认 0 = 不限时），由 CLI 自行跑完。
   - 采集期间提示用户不要操作鼠标键盘、不要关闭/最小化微信窗口。

4. **`articles` — 查询并汇报已入库结果**
   - 执行 `awa articles --account "<公众号名>" --limit 50`。
   - 用 `accountCount` / `articleCount` / `items[]` 向用户汇报本次已入库的文章。

## 3. 命令速查

所有子命令格式：`awa <子命令> [选项]`（项目内未安装全局命令时用 `uv run awa <子命令> [选项]`）。顶层与每个子命令都接受 `--home <路径>`，二者语义一致。

### `doctor`

```powershell
awa doctor [--install-ca] [--install-browser] [--home PATH]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--install-ca` | 关闭（store_true） | CA 文件存在但未安装时安装到用户根证书库并重新检查 |
| `--install-browser` | 关闭（store_true） | 安装离线归档所需的 Chromium 到 `<AWA_HOME>\.playwright-browsers`，安装后仍会执行一次完整检查 |
| `--home PATH` | 无（用 AWA_HOME / 默认） | AWA_HOME 用户数据目录 |

- 关键输出字段：`ok`/`ready`（bool，所有检查项是否全部通过）、`status`、`home`、`checks[]`、`accountName`、`dbPath`、`proxyAddress`。
- `checks[]` 每项含 `name`、`ok`、`detail`；`name` 取值：`config`、`storage_dirs`、`database`、`mitm_port`、`ca_certificate`、`wechat_home_window`、`dependencies`、`playwright_browsers`（**非阻塞**：该项 `ok=false` 不影响 `ready` 与退出码，仅表示 `--offline` 离线归档所需的 chromium 未安装，`detail` 里会给出安装命令）。
- 退出码：全部通过 → 0；前置条件不满足 → 2；运行时装配失败 → 1。

### `scan`

```powershell
awa scan [--limit N] [--date-mode {all,range,before,after}] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--max-scrolls N] [--home PATH]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--limit N` | `0`（不限） | 最多返回多少篇，0 表示不限 |
| `--date-mode {all,range,before,after}` | `all` | 日期筛选模式 |
| `--start YYYY-MM-DD` | 无 | `range` / `after` 模式下使用 |
| `--end YYYY-MM-DD` | 无 | `range` / `before` 模式下使用 |
| `--max-scrolls N` | `200` | 滚动安全上限，达到即停止并标记 `truncated=true` |
| `--home PATH` | 无 | AWA_HOME 用户数据目录 |

- 关键输出字段：`accountName`、`dateFilter`（`mode` + `label`）、`count`、`items[]`（每项含 `sequence`、`title`、`articleDate`、`fingerprint`）、`boundaryReached`、`truncated`、`scrolls`、`rawCount`、`skippedCount`。
- 退出码：成功 → 0；未找到主页窗口（`status="window-not-found"`）→ 2；其他扫描失败（`status="scan-failed"`）→ 1。
- 注意：`count` 与 `items[]` 才是实际可用条目数；`sequence` 是窗口内序号，**可能跳号**（例如 1,2,3,8），`rawCount` 通常大于 `count`，均属正常现象。给用户看清单时用 `items[]`，不要用 `rawCount`。

### `crawl`

```powershell
awa crawl [--limit N] [--date-mode {all,range,before,after}] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--skip-collected] [--interval SECONDS] [--timeout SECONDS] [--comments] [--offline] [--offline-mode {standard,beta}] [--home PATH]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--limit N` | `0`（不限） | 采集篇数上限，0 表示不限 |
| `--date-mode {all,range,before,after}` | `all` | 日期筛选模式 |
| `--start YYYY-MM-DD` | 无 | 起始日期 |
| `--end YYYY-MM-DD` | 无 | 截止日期 |
| `--skip-collected` | 关闭（store_true） | 跳过已入库文章 |
| `--interval SECONDS` | `0.0` | 单篇任务间隔 |
| `--timeout SECONDS` | `0.0`（不限） | 整体超时，超时则请求停止并返回 `status="timeout"` |
| `--comments` | 关闭（store_true） | 采集文章评论（会显著增加耗时与磁盘占用）；默认不采集评论 |
| `--offline` | 关闭（store_true） | 对文章做离线归档（会显著增加耗时与磁盘占用）；默认不做离线归档，需先安装 Playwright Chromium |
| `--offline-mode {standard,beta}` | `standard` | 离线归档模式：`standard` 常规模式，`beta` 带状态实验模式；**仅在 `--offline` 时生效** |
| `--home PATH` | 无 | AWA_HOME 用户数据目录 |

- 关键输出字段：`status`（`completed` / `failed` / `cancelled` / `timeout` / `window-not-found`）、`taskId`、`accountName`、`processedCount`、`detailSuccessCount`、`skippedCount`、`errorCount`、`averageArticleSeconds`、`articles[]`（每项含 `articleId`、`title`、`publishedArticleTime`、`articleLink`、`archiveDir`）、`errors[]`（失败摘要，含 `count`、`latestError`）、`startedAt`、`finishedAt`、`logPath`、`commentsEnabled`（bool，本次是否开启评论采集）、`offlineEnabled`（bool，本次是否开启离线归档）。
- 退出码：`completed` → 0；`failed` → 1；`cancelled` / `timeout` → 1；未找到主页窗口等前置条件不满足 → 2。

### `articles`

```powershell
awa articles [--account NAME] [--limit N] [--since YYYY-MM-DD] [--home PATH]
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--account NAME` | 无（全部） | 按公众号名过滤 |
| `--limit N` | `50`（生效范围 1–500，超出会被夹取） | 返回条数上限 |
| `--since YYYY-MM-DD` | 无 | 按 `last_collected_time` 过滤 |
| `--home PATH` | 无 | AWA_HOME 用户数据目录 |

- 关键输出字段：`accountCount`、`articleCount`、`items[]`（每项含 `articleId`、`accountName`、`title`、`publishedArticleTime`、`articleLink`、`archiveDir`、`lastCollectedTime`、`existsOnDisk`）、`dbPath`、`storageRoot`。
- 退出码：成功 → 0；数据库不存在（`status="database-missing"`）→ 2；查询失败 → 1。

### 退出码（全部子命令统一）

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功（`ok=true`） |
| 1 | 运行失败（采集 `failed`、cancelled/timeout、未预期异常） |
| 2 | 前置条件不满足（需要用户先操作或先修复环境，如未找到主页窗口、CA 未安装、端口占用、非 Windows） |
| 3 | 参数错误（argparse 参数错误或日期校验失败） |

日期参数校验（`scan`/`crawl` 共用）：`--date-mode range` 必须同时给 `--start` 与 `--end`；`before` 必须给 `--end`；`after` 必须给 `--start`；`--start`/`--end` 必须是 `YYYY-MM-DD`。不满足则以退出码 3 结束。

### 输出与归档格式

- **stdout 只有一个 JSON 文档**（UTF-8、`ensure_ascii=False`、缩进 2 空格），可直接 `json.loads` 解析。成功文档含 `ok=true`、`command`、`status`；失败文档含 `ok=false`、`command`、`status`、`message`。
- **人类可读的进度/警告/错误全部在 stderr**（每行以 `[awa]` 或 `[awa][warn]` 开头）。
- 每篇文章归档在 `<AWA_HOME>/storages/<公众号名>/<发布时间 标题__哈希>/` 目录内：
  - **默认产出**（不加任何开关）：`origin/main.html`（抓取到的原始页面）、`origin/request.json`（抓包请求信息）、`article_detail.json`（解析后的文章详情）。
  - 加 `--comments` 时，追加 `comments/final.json`（评论数据）。
  - 加 `--offline` 时，追加 `index.html`（离线可打开的网页副本）与 `assets/`（页面资源）。
  - 多个开关可同时开启，归档文件会叠加；`--offline-mode` 只影响离线归档的实现方式，不改变上述文件位置。

### 解析示例（PowerShell）

stdout 是纯 JSON，stderr 是进度文本，**两者要分开**。推荐把 stdout 重定向到文件后再解析：

```powershell
# 把 stdout 写入 result.json（stderr 仍打印到控制台）
awa scan --limit 20 1> result.json

# 再解析 result.json
$data = Get-Content result.json -Raw | ConvertFrom-Json
$data.accountName
$data.count
$data.items | Select-Object -First 10 title, articleDate
```

> [!IMPORTANT]
> **不要用 `2>&1` 把 stderr 混进 JSON**。`2>&1` 会把 `[awa]` 进度行与 JSON 拼在一起，导致 `ConvertFrom-Json` / `json.loads` 失败。如需同时看进度，就**保持 stderr 在控制台**、只把 stdout（`1>`）写文件。

## 4. 失败处置对照表

| 现象 | 判断依据 | 处置动作 |
| --- | --- | --- |
| 未找到主页窗口 | `ok=false`、`status="window-not-found"`、退出码 2 | 请用户在微信 PC 客户端**打开目标公众号主页**（窗口里能看到该公众号的文章列表；标题可能是「公众号/服务号/订阅号」，也可能是「微信」），再重试 `scan`/`crawl` |
| CA 未安装 | `doctor` 的 `ca_certificate.ok=false` | 执行 `awa doctor --install-ca`，然后重新 `doctor` 确认 `ca_certificate.ok=true` |
| 18000 端口被占用 | `doctor` 的 `mitm_port.ok=false`（detail 显示 `127.0.0.1:18000` 已被占用） | 提示用户关闭占用 `127.0.0.1:18000` 端口的程序，重新 `doctor` |
| 采集 0 篇 | `scan` / `crawl` 输出 `count=0`（或 `processedCount=0`） | 确认当前主页窗口是否正确、文章是否被 `--date-mode` 日期条件过滤掉；放宽日期范围或去掉过滤后重试 |
| 部分失败 | `crawl` 的 `errorCount>0`，`errors[]` 有摘要 | 读取 `errors[]`（含 `latestError`）确认失败原因；对失败文章可在同一主页重新 `crawl`（可加 `--skip-collected` 只补缺），不要编造成功数量。注意：开启 `--comments` / `--offline` 时，评论采集或离线归档的失败**也会计入 `errorCount`**，需结合 `latestError` 判断是正文采集失败还是附加环节失败 |
| 系统代理异常 | 采集后网络异常 / 提示代理未恢复 | **不要手工改系统代理**。CLI 会在采集时临时切到 `127.0.0.1:18000`、结束后自动恢复；若异常请重跑 `doctor` 检查，必要时重启相关程序，切勿手工修改注册表代理 |
| `crawl` 超时 | 输出 `status="timeout"`、退出码 1 | 说明未在 `--timeout` 内跑完。可减小 `--limit` 或放宽/去掉 `--timeout` 后重试；已入库的文章可用 `articles` 查看，不必重采 |
| 离线归档缺浏览器 | `doctor` 的 `playwright_browsers.ok=false`（`detail` 会指出缺失的 chromium 目录） | 执行 `awa doctor --install-browser`（项目内用 `uv run awa doctor --install-browser`）安装 Chromium，再重新 `doctor` 确认 `playwright_browsers.ok=true`，然后重试带 `--offline` 的 `crawl`；该项不影响不带 `--offline` 的采集 |

## 5. 硬性规则

- **MUST** 在 `crawl` 之前先执行 `scan`，并把列表给用户**确认采集范围**；**MUST NOT** 未经用户确认就直接批量采集。
- **MUST NOT** 在用户未确认的情况下擅自开启 `--comments` / `--offline`（会显著增加耗时与磁盘占用）。
- **MUST NOT** 并发执行多个 `crawl` —— 同一时间只能有一个采集任务在跑。
- `crawl` 期间 **MUST** 提醒用户不要操作鼠标键盘、不要关闭或最小化微信窗口。
- **MUST NOT** 修改用户的系统代理设置。CLI 会在采集时临时切换代理并自动恢复，不要手工干预（不要改注册表代理、不要开关系统代理）。
- **MUST NOT** 删除或移动 `<AWA_HOME>/storages/`、数据库文件等用户数据；**MUST NOT** 清空采集历史。
- 汇报结果 **MUST** 以 CLI 的 JSON 输出为唯一依据；**MUST NOT** 编造文章标题、数量或任何指标。
- 采集范围 **MUST NOT** 超出用户确认的范围。
