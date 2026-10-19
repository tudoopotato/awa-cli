# awa-cli 真实端到端验证报告（Task 8）

> 说明：本报告已脱敏，真实公众号名称与文章标题已替换为示例，指标数值为实测值。

- 验证日期：2026-10-19
- 验证工作目录：`<PROJECT_ROOT>`
- `AWA_HOME`：`<AWA_HOME>`
- 公众号：`示例公众号`
- 微信 PC 客户端：运行中，`wechat_home_window` 检测到窗口标题「微信」，窗口句柄 `528679990`
- 本章所有数据均来自本次真实命令输出，未经验证的项目已明确标注「未验证」。

---

## 1. 环境与前置

### 1.1 步骤 0：基线

系统代理（注册表 `HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings`）：

```
ProxyEnable   : 1
ProxyServer   : 127.0.0.1:7897
AutoConfigURL :
```

`<AWA_HOME>` 初始目录树（`Get-ChildItem -Recurse -Depth 3 -Force`）：

```
<AWA_HOME>\.mitmproxy                          （目录，内容为空）
<AWA_HOME>\data                                （目录）
<AWA_HOME>\storages                            （目录，空）
<AWA_HOME>\data\logs\runtime-detail.log        0 字节  2026/10/19 10:39:50
<AWA_HOME>\data\logs\runtime-summary.log       0 字节  2026/10/19 10:39:50
<AWA_HOME>\data\runtime\huey                   （目录）
<AWA_HOME>\data\sql\awa-v2.1.sqlite3           81920 字节  2026/10/19 10:39:50
<AWA_HOME>\data\tmp                            （目录）
```

`.mitmproxy` 目录存在但为空（无任何 CA 文件）。

---

## 2. 逐步实测记录

### 步骤 1：`doctor` 初检

命令：

```
uv run awa doctor --home <AWA_HOME>
```

- 退出码：`2`
- `ok`: `false`
- `status`: `ca-not-installed`
- `ready`: `false`

`checks` 逐项：

| name | ok | detail（关键内容） |
|---|---|---|
| config | true | 配置加载并通过校验。 |
| storage_dirs | true | article_storage_root=`<AWA_HOME>\storages`；db_dir=`<AWA_HOME>\data\sql`；temp_dir=`<AWA_HOME>\data\tmp`；log_dir=`<AWA_HOME>\data\logs`；四个目录均存在且可写。 |
| database | true | dbPath=`<AWA_HOME>\data\sql\awa-v2.1.sqlite3`；必需表=awa_fetch_history, awa_public_accounts, awa_public_articles；校验通过。 |
| mitm_port | true | 端口 127.0.0.1:18000 空闲，可用于本地 MITM。 |
| ca_certificate | **false** | `status=missing`，`installed=false`，`thumbprint=null`，`caPath=<AWA_HOME>\.mitmproxy\mitmproxy-ca-cert.cer`，`storeCertificateCount=0`；detail：「CA 证书文件不存在……首次运行采集时 mitmproxy 会自动生成 CA 证书，生成后再执行 `awa doctor --install-ca` 安装。」 |
| wechat_home_window | true | 已定位公众号主页窗口：标题「微信」，窗口句柄 528679990；已读到文章日期分组。accountName=`示例公众号` |
| dependencies | true | 依赖 mitmproxy、uiautomation 均已安装。 |
| playwright_browsers | **false** | `browserCacheDir=<AWA_HOME>\.playwright-browsers`，`chromePath=null`，「未找到 Playwright chromium……离线归档（--offline）需要它；该项不影响其他命令。」 |

### 步骤 2：首次采集（触发 mitmproxy 生成 CA）

命令：

```
uv run awa crawl --limit 1 --home <AWA_HOME> --timeout 180
```

- 退出码：`0`
- `status`: `completed`
- `taskId`: `main-fcc4faae3c914d8db34037391a3b4b81`
- `accountName`: `示例公众号`
- `processedCount`: `1`
- `detailSuccessCount`: `0`
- `skippedCount`: `0`
- `errorCount`: `1`
- `averageArticleSeconds`: `null`
- `articles`: `[]`
- `errors`:
  ```json
  [{ "count": 1, "latestError": "文章窗口已关闭，但未捕获到 HTML 或 reference" }]
  ```
- `startedAt`: `2026-10-19 10:44:29`
- `finishedAt`: `2026-10-19 10:44:37`
- `commentsEnabled`: `false`
- `offlineEnabled`: `false`

采集后 `<AWA_HOME>\.mitmproxy` 内容：

| 文件 | 字节数 | 修改时间 |
|---|---:|---|
| mitmproxy-ca-cert.cer | 1172 | 2026/10/19 10:44:32 |
| mitmproxy-ca-cert.p12 | 1035 | 2026/10/19 10:44:32 |
| mitmproxy-ca-cert.pem | 1172 | 2026/10/19 10:44:32 |
| mitmproxy-ca.p12 | 2384 | 2026/10/19 10:44:32 |
| mitmproxy-ca.pem | 2847 | 2026/10/19 10:44:32 |
| mitmproxy-dhparam.pem | 770 | 2026/10/19 10:44:32 |

### 步骤 3：安装 CA 并复检

命令：

```
uv run awa doctor --home <AWA_HOME> --install-ca
```

- 退出码：`0`
- `ok`: `true`，`status`: `ok`，`ready`: `true`
- `ca_certificate`：
  - `ok`: `true`
  - `status`: `installed`
  - `installed`: `true`
  - `thumbprint`: `56D8C725DF84A64737B36639757EDB22F52529B1`
  - `storeCertificateCount`: `61`
  - detail：「CA 证书已安装到当前用户证书库，指纹 56D8C725DF84A64737B36639757EDB22F52529B1。」

随后执行普通 `uv run awa doctor --home <AWA_HOME>`：

- 退出码：`0`
- `ok`: `true`，`status`: `ok`，`ready`: `true`
- 各检查项：config/storage_dirs/database/mitm_port/ca_certificate/wechat_home_window/dependencies 全部 `true`；**仅 `playwright_browsers` 为 `false`**（该检查在报告中注明「不影响其他命令」）。

stderr 中记录到（安装仍成功）：

```
[awa] CA 证书文件存在但未安装，正在执行安装……
Exception in thread Thread-3 (_readerthread):
Traceback (most recent call last):
  File "...\threading.py", line 1044, in _bootstrap_inner
  ...
  File "...\subprocess.py", line 1615, in _readerthread
    buffer.append(fh.read())
  File "<frozen codecs>", line 325, in decode
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xca in position 6: invalid continuation byte
[awa] CA 证书安装命令执行成功，正在复检……
```

### 步骤 4：`scan --limit 5`

命令：

```
uv run awa scan --limit 5 --home <AWA_HOME>
```

- 退出码：`0`
- `status`: `ok`
- `accountName`: `示例公众号`
- `dateFilter`: `{"mode": "all", "label": "不限日期"}`
- `count`: `5`
- `boundaryReached`: `false`
- `truncated`: `false`
- `scrolls`: `3`
- `rawCount`: `12`
- `skippedCount`: `0`

`items` 前 3 条：

| sequence | title | articleDate |
|---|---|---|
| 1 | 示例文章2 | 2026-10-16 |
| 2 | 示例文章 | 2026-10-15 |
| 5 | 示例文章3 | 2026-10-15 |

完整 5 条的 sequence 依次为 `1, 2, 5, 8, 12`。

### 步骤 5：真实采集 1 篇

命令：

```
uv run awa crawl --limit 1 --home <AWA_HOME>
```

- 退出码：`0`
- `status`: `completed`
- `taskId`: `main-4c248f11739b4a8d9235037f0050d243`
- `accountName`: `示例公众号`
- `processedCount`: `1`
- `detailSuccessCount`: `1`
- `skippedCount`: `0`
- `errorCount`: `0`
- `averageArticleSeconds`: `2.552`
- `articles`:
  ```json
  [
    {
      "articleId": 1,
      "title": "示例文章",
      "publishedArticleTime": "2026-10-15 21:43",
      "articleLink": "https://mp.weixin.qq.com/s/&lt;示例文章短链&gt;",
      "archiveDir": "<AWA_HOME>\\storages\\示例公众号\\2026-10-15 21-43 示例文章__73f814bb497f"
    }
  ]
  ```
- `errors`: `[]`
- `startedAt`: `2026-10-19 10:45:27`
- `finishedAt`: `2026-10-19 10:45:37`
- `logPath`: `<AWA_HOME>\data\logs\runtime-summary.log`
- `commentsEnabled`: `false`
- `offlineEnabled`: `false`

stderr 前 5 行（PowerShell 5 将 stderr 包装为 `NativeCommandError`）：

```
uv : [awa] 正在装配采集运行时……
At line:15 char:6102
+ ... pgrep\bin'; uv run awa crawl --limit 1 --home <AWA_HOME> > C:\tmp ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: ([awa] 正在装配采集运行时……:String) [], RemoteException
```

stderr 最后 3 行：

```
[awa] [采集中] 示例公众号 进度 1/1，错误 0｜正在等待文章标签关闭
[awa] [采集中] 示例公众号 进度 1/1，错误 0｜正在清理运行资源
[awa] [已完成] 示例公众号 进度 1/1，错误 0｜主流程已完成
```

### 步骤 6：采集后校验

系统代理（采集完成后）：

```
ProxyEnable   : 1
ProxyServer   : 127.0.0.1:7897
AutoConfigURL :
```

`uv run awa articles --limit 5 --home <AWA_HOME>`：

- 退出码：`0`
- `accountCount`: `1`
- `articleCount`: `1`
- `items`（实际仅 1 条，即前 1 条；第 2 条不存在）：
  ```json
  {
    "articleId": 1,
    "accountName": "示例公众号",
    "title": "示例文章",
    "publishedArticleTime": "2026-10-15 21:43",
    "articleLink": "https://mp.weixin.qq.com/s/&lt;示例文章短链&gt;",
    "archiveDir": "<AWA_HOME>\\storages\\示例公众号\\2026-10-15 21-43 示例文章__73f814bb497f",
    "lastCollectedTime": "2026-10-19 10:45:36",
    "existsOnDisk": true
  }
  ```

数据库文件：`<AWA_HOME>\data\sql\awa-v2.1.sqlite3`，`81920` 字节，修改时间 `2026/10/19 10:45:36`。

`awa_fetch_history` 查询（以 `mode=ro` 只读 URI 打开；此处为步骤 6 时点）：

| id | article_id | status | task_type | started_time | finished_time |
|---|---|---|---|---|---|
| 1 | 1 | success | article_capture | 2026-10-19 10:45:34 | 2026-10-19 10:45:36 |

该时点表中仅 1 条记录（最近 3 条查询的实际返回）。

---

## 3. 归档产物文件树与 `article_detail.json`

归档目录（步骤 5 返回的 `articles[0].archiveDir`）：

`<AWA_HOME>\storages\示例公众号\2026-10-15 21-43 示例文章__73f814bb497f`

步骤 7 时点文件树（`Get-ChildItem -Recurse`）：

```
<archiveDir>\
├─ article_detail.json        786 字节
└─ origin\
   ├─ main.html               3653750 字节
   └─ request.json            6418 字节
```

三个必需文件均存在：`origin/main.html`、`origin/request.json`、`article_detail.json`。

`article_detail.json` 全部键与关键值（步骤 7 时点）：

| 键 | 值 |
|---|---|
| account_name | 示例公众号 |
| article_title | 示例文章 |
| published_article_time | 2026-10-15 21:43 |
| article_link | https://mp.weixin.qq.com/s?__biz=&lt;示例公众号biz&gt;&amp;idx=1&amp;mid=&lt;示例文章mid&gt;&amp;sn=&lt;示例文章sn&gt; |
| article_short_link | https://mp.weixin.qq.com/s/&lt;示例文章短链&gt; |
| ip_location | 北京 |
| audience_count | 716 |
| read_count | 100001 |
| like_count | 1150 |
| share_count | 3329 |
| recommend_count | 760 |
| comment_count | 22 |
| html_source | reference_request |
| duration_seconds | 5.179 |
| collect_time | 2026-10-19 10:45:36 |
| record_status | saved |

> 说明：步骤 9 的再次采集覆盖了同一归档（步骤 9 完成后 `article_detail.json` 为 782 字节，`html_source=mitm_response`，`duration_seconds=9.461`，`collect_time=2026-10-19 10:55:14`，其余指标数值不变，`record_status=saved`）。

---

## 4. 系统代理前后对比

| 字段 | 步骤 0（基线） | 步骤 6（采集后） | 步骤 10（收尾） | 结论 |
|---|---|---|---|---|
| ProxyEnable | 1 | 1 | 1 | 一致 |
| ProxyServer | 127.0.0.1:7897 | 127.0.0.1:7897 | 127.0.0.1:7897 | 一致 |
| AutoConfigURL | 空 | 空 | 空 | 一致 |

采集期间 CLI 使用的 `127.0.0.1:18000` 在采集结束后未残留于系统代理设置。

---

## 5. 数据库前后对比

| 项目 | 采集前 | 步骤 6 采集后 | 步骤 9 完成后 |
|---|---|---|---|
| `awa-v2.1.sqlite3` 大小 | 81920 字节 | 81920 字节 | 81920 字节 |
| `awa-v2.1.sqlite3` 修改时间 | 2026/10/19 10:39:50 | 2026/10/19 10:45:36 | 2026/10/19 10:55:26 |
| `awa articles` articleCount | 未查询（未验证） | 1 | 1（步骤 8 跨 cwd 查询仍为 1） |
| `awa_fetch_history` 行数 | 未查询（未验证） | 1 | 7 |

步骤 9 完成后 `awa_fetch_history` 全部 7 条记录（只读查询）：

| id | article_id | status | task_type | started_time | finished_time | error_stage |
|---|---|---|---|---|---|---|
| 1 | 1 | success | article_capture | 2026-10-19 10:45:34 | 2026-10-19 10:45:36 | |
| 2 | 1 | success | article_capture | 2026-10-19 10:46:42 | 2026-10-19 10:46:44 | |
| 3 | 1 | **failed** | offline_cache | 2026-10-19 10:46:45 | 2026-10-19 10:46:46 | offline_cache |
| 4 | 1 | success | comment_fetch | 2026-10-19 10:46:45 | 2026-10-19 10:46:46 | |
| 5 | 1 | success | article_capture | 2026-10-19 10:55:12 | 2026-10-19 10:55:14 | |
| 6 | 1 | success | comment_fetch | 2026-10-19 10:55:14 | 2026-10-19 10:55:16 | |
| 7 | 1 | success | offline_cache | 2026-10-19 10:55:14 | 2026-10-19 10:55:26 | |

`awa_public_articles` 行数：`1`；`awa_public_accounts` 行数：`1`（2026-10-19 10:55 只读查询）。

---

## 6. 入口等价性与跨 cwd（SubTask 8.2 / 8.4）

### 6.1 `awa` 与 `python -m awa`

在同一 cwd（`<PROJECT_ROOT>`）分别执行：

```
uv run awa doctor --home <AWA_HOME>
uv run python -m awa doctor --home <AWA_HOME>
```

| 项目 | `awa` | `python -m awa` | 结论 |
|---|---|---|---|
| 退出码 | 0 | 0 | 一致 |
| 顶层字段集合 | accountName, checks, command, dbPath, home, ok, proxyAddress, ready, status | 同左 | 一致 |
| checks 名称序列 | config, storage_dirs, database, mitm_port, ca_certificate, wechat_home_window, dependencies, playwright_browsers | 同左 | 一致 |
| status | ok | ok | 一致 |
| ready | True | True | 一致 |

**结论：一致。**

### 6.2 全局工具安装与跨 cwd

```
uv tool install . --force
```

- 退出码：`0`
- 末尾输出：`Installed 1 executable: awa`

切换到 `<SYSTEM_DRIVE_ROOT>` 执行：

```
awa articles --limit 3 --home <AWA_HOME>
```

- 退出码：`0`
- `accountCount`: `1`
- `articleCount`: `1`
- `items[0].archiveDir`: `<AWA_HOME>\storages\示例公众号\2026-10-15 21-43 示例文章__73f814bb497f`
- `items[0].existsOnDisk`: `true`
- `dbPath`/`storageRoot` 均正确指向 `<AWA_HOME>`

**结论：资源定位不依赖 cwd，通过。**

---

## 7. 评论 + 离线归档（SubTask 8.5）

### 7.1 浏览器准备

- `<AWA_HOME>\.playwright-browsers` 初始不存在；旧项目 `<OLD_PROJECT_ROOT>\.playwright-browsers` 存在，包含 `chromium-1223`、`chromium_headless_shell-1223` 等。
- 使用 PowerShell 创建目录联接（`cmd /c` 被环境禁止，改用 `New-Item -ItemType Junction`）：
  ```
  New-Item -ItemType Junction -Path '<AWA_HOME>\.playwright-browsers' -Target '<OLD_PROJECT_ROOT>\.playwright-browsers'
  ```
  创建成功（`LinkType: Junction`，`Target: <OLD_PROJECT_ROOT>\.playwright-browsers`）。
- 联接生效后 `doctor` 的 `playwright_browsers` 变为 `ok: true`，`chromePath=<AWA_HOME>\.playwright-browsers\chromium-1223\chrome-win64\chrome.exe`。
- 但第一次离线归档失败，原因是当前 Playwright 需要 build 1248，而旧缓存只有 1223：
  ```
  离线缓存失败：Error: BrowserType.launch: Executable doesn't exist at <OLD_PROJECT_ROOT>\.playwright-browsers\chromium_headless_shell-1248\chrome-headless-shell-win64\chrome-headless-shell.exe
  ```
  该次采集：退出码 `0`，`status=completed`，`detailSuccessCount=1`，`errorCount=1`，`commentsEnabled=true`，`offlineEnabled=true`；评论已成功写入 `comments/final.json`（54654 字节），`awa_fetch_history` 中 `offline_cache` 记录为 `failed`。
- 第一次 `uv run playwright install chromium`（未设置代理）下载停在 197.5 MiB 的 30% 约 6 分钟，手动终止（退出码 1）。
- 第二次设置 `HTTPS_PROXY/HTTP_PROXY=http://127.0.0.1:7897`（仅进程环境变量，未修改系统代理）后安装成功：
  ```
  Chrome Headless Shell 156.0.8078.4 (playwright chromium-headless-shell v1248) downloaded to <AWA_HOME>\.playwright-browsers\chromium_headless_shell-1248
  ```
  `.playwright-browsers` 新增 `chromium-1248`、`chromium_headless_shell-1248`；退出码 `0`。

### 7.2 最终执行

命令：

```
uv run awa crawl --limit 1 --comments --offline --home <AWA_HOME>
```

- 退出码：`0`
- `status`: `completed`
- `taskId`: `main-75136d5047ea4aaeb3fccd2193782df2`
- `processedCount`: `1`，`detailSuccessCount`: `1`，`skippedCount`: `0`
- `errorCount`: `0`
- `averageArticleSeconds`: `1.268`
- `commentsEnabled`: `true`
- `offlineEnabled`: `true`
- `startedAt`: `2026-10-19 10:55:01`，`finishedAt`: `2026-10-19 10:55:27`
- `errors`: `[]`
- `articles`: 同上一篇（`articleId=1`，同一 `archiveDir`）

本次日志关键行：

```
2026-10-19 10:55:16 | SUCCESS | 任务 1 评论信息：评论信息存储完成：评论 22 条，回复 0 条。
2026-10-19 10:55:26 | SUCCESS | 任务 1 离线归档：离线缓存完成
2026-10-19 10:55:26 | SUCCESS | 任务 1 最终结果：离线缓存完成
```

归档目录新增/更新内容（最终）：

```
<archiveDir>\
├─ article_detail.json        782 字节
├─ index.html                 1077871 字节
├─ assets\
│  ├─ css\                    26 个文件
│  └─ img\                    17 个文件
├─ comments\
│  └─ final.json              54654 字节
└─ origin\
   ├─ main.html               3653747 字节
   └─ request.json            4559 字节
```

归档目录总文件大小：`8768586` 字节。

`comments/final.json` 顶层结构：

```
schema_version = "wechat_comments_raw_v1"
collect_time   = "2026-10-19 10:55:16"
article        = {url_redacted: ...}
summary        = {top_level_comment_count, reply_count, total_message_count, comment_page_count, pagination_complete, stop_reason, page_summaries, reply_fetch}
comments       = 22 条
```

**结论：评论与离线归档均成功。**

---

## 8. `AWA_HOME` 最终目录树（步骤 10）

```
<AWA_HOME>
├─ .mitmproxy\
│  ├─ mitmproxy-ca-cert.cer        1172
│  ├─ mitmproxy-ca-cert.p12        1035
│  ├─ mitmproxy-ca-cert.pem        1172
│  ├─ mitmproxy-ca.p12             2384
│  ├─ mitmproxy-ca.pem             2847
│  └─ mitmproxy-dhparam.pem         770
├─ .playwright-browsers\           （目录联接 → <OLD_PROJECT_ROOT>\.playwright-browsers）
├─ data\
│  ├─ logs\
│  │  ├─ runtime-detail.log        16486
│  │  └─ runtime-summary.log       11932
│  ├─ runtime\huey\
│  │  ├─ article-detail-comments-2f14d726eedf.sqlite3          3645440
│  │  ├─ article-detail-offline-cache-f25b7191daee.sqlite3     3645440
│  │  ├─ main-flow-detail-3c5b1b98a671.sqlite3                 3645440
│  │  └─ main-flow-foreground-90bf0d366752.sqlite3               36864
│  ├─ sql\awa-v2.1.sqlite3          81920
│  └─ tmp\
│     ├─ detail-comments-post-221956784055-comments\
│     ├─ detail-comments-post-7142f6f0e6a5-comments\
│     ├─ main-flow-detail-detail-61563c658dec\
│     ├─ main-flow-detail-detail-7abe1a6aac9b\
│     ├─ main-flow-detail-detail-80677dfe3375\
│     └─ offline-cache\
└─ storages\
   └─ 示例公众号\
      └─ 2026-10-15 21-43 示例文章__73f814bb497f\
         ├─ assets\{css,img}
         ├─ comments\final.json
         ├─ origin\{main.html,request.json}
         ├─ article_detail.json
         └─ index.html
```

收尾进程检查（`Get-Process python,mitmdump`）：无 `mitmdump` 进程；`python` 进程 PID `113224`/`118488`（启动于 2026/10/16 11:02）与 `120652`（2026/10/16 11:50），均早于本次验证，不属于本次采集残留。系统中存在多个 `chrome` 进程（含 10:52–10:55 启动者），未确认其归属，未做处理。

---

## 9. 结论表（SubTask 8.1 ~ 8.5）

| 子任务 | 结论 | 依据 |
|---|---|---|
| 8.1 真实端到端采集（doctor → CA 生成/安装 → crawl） | **通过** | CA 安装前 `doctor` 退出码 2（`ca-not-installed`）；首次 crawl 退出码 0 但 `errorCount=1`、0 篇文章，且生成 6 个 CA 文件；`--install-ca` 后 `ca_certificate.installed=true`、`thumbprint=56D8C725DF84A64737B36639757EDB22F52529B1`；随后 `crawl --limit 1` 退出码 0、`errorCount=0`、`detailSuccessCount=1`、`averageArticleSeconds=2.552` |
| 8.2 `awa` 与 `python -m awa` 入口等价 | **通过** | 两者退出码均为 0；顶层字段集合完全相同（9 个字段）；8 项 checks 名称序列相同；`status=ok`、`ready=True` 相同 |
| 8.3 归档产物完整（origin/main.html、origin/request.json、article_detail.json） | **通过** | 三文件均存在，字节数分别为 3653750 / 6418 / 786（步骤 7 时点）；`article_detail.json` 16 个字段均有真实值（阅读 100001、点赞 1150、分享 3329、推荐 760、评论 22 等） |
| 8.4 跨 cwd 资源定位（全局安装后） | **通过** | `uv tool install . --force` 退出码 0；在 `<SYSTEM_DRIVE_ROOT>` 执行 `awa articles --limit 3 --home <AWA_HOME>` 退出码 0，`articleCount=1`，`existsOnDisk=true` |
| 8.5 评论 + 离线归档 | **通过** | 安装 `chromium_headless_shell-1248` 后，`crawl --limit 1 --comments --offline` 退出码 0、`errorCount=0`、`commentsEnabled=true`、`offlineEnabled=true`；生成 `comments/final.json`（54654 字节，22 条评论）、`index.html`（1077871 字节）、`assets/css` 26 个、`assets/img` 17 个 |

---

## 10. 未验证项与发现的问题

### 10.1 未验证项

1. **采集前数据库行数未记录**：步骤 0/1 未执行 `awa_public_articles`、`awa_fetch_history` 的计数查询，因此「采集前为 0 行」未验证。
2. **扫描 `sequence` 不连续的原因未验证**：`scan --limit 5` 实际返回 sequence `1,2,5,8,12`，`rawCount=12`、`skippedCount=0`，原因未在本次验证范围内确认。
3. **10:52–10:55 启动的 chrome 进程归属未验证**：未确认它们是否由 awa 的离线归档/浏览器安装产生，也未做处理。
4. **收尾时 `data\tmp` 下残留的临时目录是否会被后续自动清理**未验证。

### 10.2 发现的问题

> 说明：以下为本次验证当时的原始记录，保留以保留问题发现历史。其中第 1、2 项已在后续修复，修复状态与验收证据见 [§11 缺陷修复状态（后续修复）](#11-缺陷修复状态后续修复) 及 `reports/report-task-9.md`。

1. **`doctor` 对 Playwright 的就绪判断与实际启动需求不一致**：创建目录联接后，`doctor` 报告 `playwright_browsers.ok=true`，`chromePath` 指向 `chromium-1223\chrome-win64\chrome.exe`；但 `playwright 1.64.0` 实际启动 `chromium_headless_shell-1248`，导致 `--offline` 报 `Executable doesn't exist ... chromium_headless_shell-1248`。doctor 通过不代表离线归档可用。**已修复（见 §11 与 `reports/report-task-9.md`）。**
2. **`doctor --install-ca` 读取子进程输出时抛出 `UnicodeDecodeError`**：`Thread-3 (_readerthread)` 中 UTF-8 解码遇到 `0xca` 失败（certutil 输出为本地编码）。安装本身成功，但 stderr 打印了完整异常堆栈。**已修复（见 §11 与 `reports/report-task-9.md`）。**
3. **CA 未信任时的采集错误信息不含根因**：首次采集（CA 未安装）返回 `errorCount=1`，`latestError` 为「文章窗口已关闭，但未捕获到 HTML 或 reference」，未提示 CA/HTTPS 拦截问题；同时命令退出码为 `0`、`status=completed`，脚本调用方无法仅凭退出码识别失败。
4. **`crawl --limit 1` 在多轮执行中重复选择同一篇文章**：步骤 5、步骤 9 第一次、步骤 9 最终三次 `crawl --limit 1` 均处理 `articleId=1`（「示例文章…」，对应 scan 的 sequence 2），而不是继续处理 scan 列表中的下一篇（sequence 1「示例文章2…」）。是否与 `--comments/--offline` 的补采逻辑有关，未验证。
5. **浏览器缓存经目录联接复用旧项目目录**：`playwright install chromium` 通过联接将 `chromium-1248`、`chromium_headless_shell-1248` 写入旧项目 `<OLD_PROJECT_ROOT>\.playwright-browsers`，对该目录产生了新增文件（未删除旧文件）。
6. **`doctor --install-ca` 的 stderr 被 PowerShell 5.1 包装为 NativeCommandError**：仅影响日志可读性，不影响命令结果；本次所有命令的实际退出码以 `$LASTEXITCODE` 记录。

---

## 11. 缺陷修复状态（后续修复）

本节为后续回填。§10.2 的原始记录保持不变，其第 1、2 项的最终状态如下。修复依据文件：`reports/report-task-9.md`（该报告为内部交付文档，未随仓库发布）。

| §10.2 编号 | 问题 | 状态 | 修复方式 |
|---|---|---|---|
| 1 | `doctor` 的 `playwright_browsers` 检查假阳性（旧版本目录被判为可用） | **已修复** | 改为执行 `python -m playwright install --dry-run chromium`（`PLAYWRIGHT_BROWSERS_PATH` 指向 `<home>\.playwright-browsers`），解析当前 Playwright 版本期望的 `Install location` 并逐个校验目录与可执行文件；不支持 dry-run 时降级为同时校验 `chromium-*` 与 `chromium_headless_shell-*`。见 `reports/report-task-9.md` §1.1。 |
| 2 | `doctor --install-ca` 抛出 `UnicodeDecodeError` | **已修复** | `awa/cli/` 下 4 处 `subprocess.run` 统一显式指定 `encoding="utf-8", errors="replace"`。见 `reports/report-task-9.md` §1.2、验收 6。 |

修复后的验收证据（均取自 `reports/report-task-9.md` 的真实命令输出）：

- **空 home**（`<AWA_HOME_EMPTY>`）：`playwright_browsers.ok=false`；`detail` 列出缺失的 `chromium-1248` 与 `chromium_headless_shell-1248`，`chromePath=null`。
- **stale home**（`<AWA_HOME_STALE>`，仅保留 `chromium-1223` / `chromium_headless_shell-1223`）：`playwright_browsers.ok=false`（不再假阳性）；同时 `ready=True`、退出码 0，确认该项仍为**非阻塞**。
- **补齐浏览器后**（`<AWA_HOME>`）：`playwright_browsers.ok=true`，`detection=playwright-dry-run`，`chromePath` 指向 `chromium-1248\chrome-win64\chrome.exe`，`missing=[]`。
- **`doctor --install-ca`**：「未安装 → 安装 → 复检」与「已安装重复执行」两种路径均退出码 0、`ca.installed=true`，stderr 无 Traceback，stdout 可被 PowerShell `ConvertFrom-Json` 解析为单个 JSON。
- **回归**：`uv run pytest -q` → `11 passed`。

**结论：§10.2 第 1、2 项均已修复并复验通过。** §10.2 第 3~6 项属于验证过程中的观察与记录，本次未作代码修改。
