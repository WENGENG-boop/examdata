# examdata 部署与调用完整指南

这份文档覆盖从零到公网可调用的全过程：拿到代码、装好依赖、把数据准备好、起服务、用 CLI / HTTP / Python 三种方式调用，以及把它放到一台公网服务器上长期运行所需的 systemd、nginx、HTTPS、防火墙与备份。

三条并行使用路径：

| 路径 | 适合谁 | 入口 |
|---|---|---|
| CLI | 一次性检索、同步、维护、人工审核 | `examdata <子命令>`（32 个子命令） |
| HTTP | 其他程序、前端、跨语言调用 | `examdata serve` 起服务，20 条只读路由 + `/docs` |
| Python | 同进程内直接调库、写脚本 | `import examdata.paperqa` / `examdata.query` |

CLI 与 HTTP 返回同一套数据结构，HTTP 的响应字段与 `examdata.query` 的返回一一对应，不需要为两条通道写两套解析。

**最容易卡住的地方是数据**：本仓库**只收录代码，不包含数据库、不包含任何试卷原件**。克隆下来直接启动会得到一个能跑但查不到东西的空服务。第 5 章专门讲这件事，请务必读完再往下走。

## 目录

- [1 这份文档能让你做到什么](#1-这份文档能让你做到什么)
  - [1.1 三条使用路径](#11-三条使用路径)
  - [1.2 最快上手](#12-最快上手)
- [2 它是什么与能力边界](#2-它是什么与能力边界)
  - [2.1 能查什么](#21-能查什么)
  - [2.2 不能查什么](#22-不能查什么)
  - [2.3 未实现项](#23-未实现项)
- [3 前置条件](#3-前置条件)
  - [3.1 软件](#31-软件)
  - [3.2 磁盘与内存](#32-磁盘与内存)
  - [3.3 网络](#33-网络)
- [4 获取代码与安装](#4-获取代码与安装)
  - [4.1 Linux 与 macOS](#41-linux-与-macos)
  - [4.2 Windows](#42-windows)
  - [4.3 安装验证](#43-安装验证)
  - [4.4 常见安装报错](#44-常见安装报错)
- [5 准备数据](#5-准备数据)
  - [5.1 为什么克隆下来是空的](#51-为什么克隆下来是空的)
  - [5.2 路线 A 把已有数据搬到服务器](#52-路线-a-把已有数据搬到服务器)
  - [5.3 路线 B 在服务器上从头抓取](#53-路线-b-在服务器上从头抓取)
  - [5.4 两条路线怎么选](#54-两条路线怎么选)
  - [5.5 验证数据是否到位](#55-验证数据是否到位)
- [6 启动服务](#6-启动服务)
  - [6.1 前台启动](#61-前台启动)
  - [6.2 serve 的全部参数](#62-serve-的全部参数)
  - [6.3 验证服务](#63-验证服务)
  - [6.4 用 uvicorn 直接启动](#64-用-uvicorn-直接启动)
- [7 调用方式一 CLI 全量参考](#7-调用方式一-cli-全量参考)
  - [7.1 命令总表](#71-命令总表)
  - [7.2 常用命令完整示例](#72-常用命令完整示例)
  - [7.3 出网、写库、只读标注](#73-出网写库只读标注)
- [8 调用方式二 HTTP API](#8-调用方式二-http-api)
  - [8.1 交互式文档](#81-交互式文档)
  - [8.2 通用约定](#82-通用约定)
  - [8.3 路由逐条说明](#83-路由逐条说明)
  - [8.4 错误语义](#84-错误语义)
  - [8.5 实测示例](#85-实测示例)
  - [8.6 paper-qa 组合速查](#86-paper-qa-组合速查)
- [9 调用方式三 Python 直接调用](#9-调用方式三-python-直接调用)
  - [9.1 直接取真题文件 paperqa](#91-直接取真题文件-paperqa)
  - [9.2 查询本地库 query](#92-查询本地库-query)
  - [9.3 治理与智能层](#93-治理与智能层)
  - [9.4 什么时候该走 CLI 或 HTTP](#94-什么时候该走-cli-或-http)
- [10 从本机调用远程服务](#10-从本机调用远程服务)
  - [10.1 SSH 本地端口转发](#101-ssh-本地端口转发)
  - [10.2 为什么这比直接暴露公网安全](#102-为什么这比直接暴露公网安全)
- [11 从内网其他机器调用](#11-从内网其他机器调用)
  - [11.1 只监听内网的写法](#111-只监听内网的写法)
  - [11.2 防火墙放行](#112-防火墙放行)
  - [11.3 风险](#113-风险)
- [12 从公网调用 生产部署](#12-从公网调用-生产部署)
  - [12.1 先读安全警告](#121-先读安全警告)
  - [12.2 创建系统用户与目录](#122-创建系统用户与目录)
  - [12.3 systemd 常驻单元](#123-systemd-常驻单元)
  - [12.4 nginx 反向代理](#124-nginx-反向代理)
  - [12.5 HTTPS 证书](#125-https-证书)
  - [12.6 防火墙](#126-防火墙)
  - [12.7 访问控制三选一](#127-访问控制三选一)
  - [12.8 部署验收清单](#128-部署验收清单)
- [13 配置项完整参考](#13-配置项完整参考)
  - [13.1 全部配置项](#131-全部配置项)
  - [13.2 .env 文件与优先级](#132-env-文件与优先级)
- [14 运维手册](#14-运维手册)
  - [14.1 日志](#141-日志)
  - [14.2 备份](#142-备份)
  - [14.3 升级代码](#143-升级代码)
  - [14.4 重新同步与重建派生数据](#144-重新同步与重建派生数据)
- [15 故障排查](#15-故障排查)
  - [15.1 服务与网络](#151-服务与网络)
  - [15.2 数据](#152-数据)
  - [15.3 CLI 与 API 调用](#153-cli-与-api-调用)
  - [15.4 同步与解析](#154-同步与解析)
  - [15.5 测试](#155-测试)
- [16 开发](#16-开发)
  - [16.1 项目结构](#161-项目结构)
  - [16.2 跑测试](#162-跑测试)
  - [16.3 已知限制](#163-已知限制)
  - [16.4 版权与许可](#164-版权与许可)
- [17 速查表](#17-速查表)
  - [17.1 从零到跑起来](#171-从零到跑起来)
  - [17.2 最常用的命令](#172-最常用的命令)
  - [17.3 最常用的 URL](#173-最常用的-url)
  - [17.4 容易记错的地方](#174-容易记错的地方)
  - [17.5 端口与路径约定](#175-端口与路径约定)

第 12 章中的 nginx、systemd、HTTPS、防火墙、SSH 隧道部分属于通用运维写法，**不含项目专有配置**，请把 `<尖括号占位符>` 换成你自己的值后再使用。

文中的终端输出为便于阅读做过折行与宽度调整，数字与真实输出一致，但表格边框宽度可能与你的终端不同。

## 1 这份文档能让你做到什么

读完并照着做，你能得到：

- 一台服务器上常驻运行的 examdata 只读检索 API，带 HTTPS 域名，开机自启、崩溃自重启。
- 一份本地数据库（SQLite），包含已解析的试卷、题目、评分条目、图形资产与溯源链。
- 三种可用的调用方式：命令行、HTTP、Python。
- 一套可执行的备份、升级与故障排查流程。

### 1.1 三条使用路径

**CLI**：32 个子命令，覆盖建库、发现、抓取、解析、检索、抽题、治理、智能层、服务、paper-qa。适合人工操作与定时任务。命令形式 `examdata <子命令> [参数]`。

**HTTP**：`examdata serve` 起一个 FastAPI 服务，20 条业务路由全部只读（唯一一个 POST `/sample` 也只查库、不写库）。自带 `/docs`（Swagger UI）、`/redoc`、`/openapi.json`。适合其他程序调用。

**Python**：`import examdata.paperqa` 取真题文件；`import examdata.query` 直接查本地库。适合写脚本或嵌进自己的服务。

### 1.2 最快上手

下面 5 行能跑通，但第 3 行需要你先有数据（第 5 章讲怎么来）：

```bash
git clone https://github.com/WENGENG-boop/examdata.git && cd examdata
python -m venv .venv && .venv/bin/pip install .
rsync -av <已有数据的主机>:<已有数据的路径>/.data/ .data/    # 见 5.2；没有现成数据就走 5.3 从头抓
.venv/bin/examdata serve --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
```

要替换的占位符：`<已有数据的主机>` 与 `<已有数据的路径>`（如果你在另一台机器上已经跑过同步）。Windows 上把 `.venv/bin/` 换成 `.venv\Scripts\`，第 4.2 节有完整说明。

最后一行返回 `{"status":"ok","papers":16}` 就说明服务和数据都就绪了（`papers` 的数字取决于你自己的数据规模，16 是本项目实测样例库的值）。

## 2 它是什么与能力边界

examdata 是一个把 Cambridge International 与 Pearson Edexcel 的**公开**试卷转成结构化数据、再对外提供只读检索的工具。

- **只读服务**：所有 HTTP 路由都不写库。写入类操作（人工修正、重新解析、同步）刻意只走 CLI，避免"生成内容与官方内容物理隔离"这条约束被匿名写接口绕过。
- **不收录版权原件**：仓库只收录代码。真实试卷受考试局版权保护，`tests/fixtures/*.pdf` 已被 `.gitignore` 排除。
- **无鉴权、无 CORS、无限流**：API 层没有注册任何中间件，没有 API key、没有 OAuth、没有 IP 限制。部署时必须自己在外层解决（第 12 章）。
- **已接入考试局**：Cambridge International（`accessibility=public`）、Pearson Edexcel（`accessibility=partial_public`）。

### 2.1 能查什么

| 能力 | 说明 | 入口 |
|---|---|---|
| 试卷检索 | 按考试局、考试体系、科目、年份、考试季、Paper、Component、Variant、Level、文件类型过滤 | `GET /papers`、`examdata search-papers` |
| 题目检索 | 题号路径、题干关键词（子串匹配）、分值区间、叶子题/大题、是否带图、是否有官方答案、知识点代码 | `GET /questions`、`examdata search-questions` |
| 单题完整内容 | 题干、层级、图形资产、官方答案、评分条目（含 M/A/B 分与 ECF）、知识点、难度、相似题 | `GET /questions/{id}`、`examdata show-question` |
| 整卷题目树 | 一份试卷的完整题目层级、分值、页码、资产数量 | `GET /papers/{id}/tree` |
| 随机抽题 / 组卷 | 按题数或目标总分抽叶子题，`seed` 固定即可复现 | `POST /sample`、`examdata sample-questions` |
| 知识点体系 | 两层（topic / subtopic），带题目计数 | `GET /taxonomy` |
| 相似题 | TF-IDF 字符 3-gram 余弦，方法标识 `tfidf-ngram-v1` | `GET /questions/{id}/similar` |
| 生成解析 | 从官方 Mark Scheme 派生的规则式脚手架，`provider=rule-based`、`is_official=false` | `GET /questions/{id}/explanation` |
| 溯源 | 题目/资产最初来自哪个官方 URL、哪份文件、何时被发现 | `GET /questions/{id}/provenance`、`GET /assets/{id}/provenance`、`GET /provenance/coverage` |
| 治理视图 | 人工修正记录、待检查队列、文件类型判定与证据 | `GET /overrides`、`GET /review`、`GET /classifications` |
| 监控视图 | 各考试局同步/解析状态、采集健康度、待检查队列 | `GET /monitor`、`examdata monitor` |
| 图形资产原件 | 按内容寻址取回 PNG/JPEG 等资产 | `GET /assets/{id}` |
| 按需取真题文件 | CIE 整份 PDF；Edexcel 整卷 PDF 或裁剪出的题目/答案 PNG | `/paper-qa/resolve`、`/paper-qa/query`、`examdata paper-qa` |

### 2.2 不能查什么

| 限制 | 说明 |
|---|---|
| 没有试卷原件 | 仓库层面不收录；运行时能否取到取决于你是否做了第 5 章的数据准备，以及 `paper-qa` 是否出网成功 |
| 没有全文检索 | `keyword` 走的是 `stem_text ILIKE %kw%` 子串匹配，不是分词检索，也没有排序与高亮 |
| 没有公式检索 | schema 里存在 `formula` 表，但检索层与 HTTP 层都没有暴露公式查询入口 |
| 没有学生端逻辑 | 没有作答、判分、成绩、用户体系；抽题只做"按条件选题" |
| 没有写入接口 | 全部 20 条 HTTP 路由都是只读；写入走 CLI |
| 没有权限体系 | 服务自身不区分调用者，谁能连上谁就能看到全库 |
| 没有 AP / SAT / IB | 见 2.3 |

### 2.3 未实现项

以下内容项目文档明确记录为**尚未实现**，不要在部署方案里假设它们可用：

1. **AP / SAT / IB 适配器**。AP（`apcentral.collegeboard.org`）与 SAT（`satsuite.collegeboard.org`）站点实测可达但未实现；IB 的 `ibo.org` 返回 403，需另行评估。
2. **Alembic 迁移未做**。建表仍是 `Base.metadata.create_all` + `db.py` 里的一份补列清单，是过渡方案。它能保证升级代码后不必重建数据库，但不是正式迁移。
3. **全量同步未执行**。Cambridge 发现层已枚举 198 个 syllabus，但只同步过 4 个科目（0580 / 9709 / 0620 / 0478）；Edexcel 已枚举 258 个科目页，仅试同步 1 个。
4. **生成解析是规则式而非推理式**。`provider=rule-based`，能重组官方评分结构，但**不会真正演算数学题**。要产出真正的解题步骤需要接入模型服务。
5. **分值合计仍有偏差**。当前样例库中 `marks_total_mismatch` 命中 10 份文档（另有跨文档项 `marks_total_mismatch_cross_document` 11 份）未收敛，最大偏差是 0580/41 的 120 vs 130。
6. **9709 Mark Scheme 关联偏低**。38/60，深层子题路径匹配待改进。

## 3 前置条件

### 3.1 软件

| 项 | 要求 | 出处 |
|---|---|---|
| Python | **>= 3.11** | `pyproject.toml` 的 `requires-python` |
| 操作系统 | Linux、macOS、Windows 均可 | 纯 Python 依赖，无平台专有代码 |
| 包管理器 | 随 Python 的 `pip`（venv 内置） | — |
| `git` | 拉取代码需要 | — |
| `rsync` | 仅在走 5.2 的"搬数据"路线时需要 | — |
| `sqlite3` CLI | 仅在备份/排查时需要（Python 自带 sqlite3 模块） | — |
| nginx / certbot | 仅在 12 章的公网部署时需要 | — |

运行时依赖（安装时自动装，共 11 个）：`httpx`、`beautifulsoup4`、`lxml`、`sqlalchemy`、`pydantic`、`pydantic-settings`、`pymupdf`、`typer`、`rich`、`fastapi`、`uvicorn`。

可选 extra 只有一个：`dev`（`pytest`、`pytest-cov`）。

### 3.2 磁盘与内存

| 项 | 估算 | 依据 |
|---|---|---|
| 代码 + 虚拟环境 | 约 150–250 MB | 主要是 `pymupdf` 与 `lxml` 的 wheel；本机实测 `.venv` 142 MB，源码 1–2 MB |
| `.data/artifacts/` | 与你的同步规模成正比 | 本机实测样例库约 38 MB |
| `.data/examdata.db` | 与题目数成正比 | 本机实测 751 道题约 4.0 MB |
| 整个 `.data/` | 本机实测约 45 MB | 见 5.1 的目录说明 |
| 内存 | 512 MB 起，1 GB 更稳 | 解析 PDF 时 PyMuPDF 会占用较多内存 |

磁盘规划建议：给数据目录留出**至少 3 倍于当前 `.data/` 的空闲空间**，因为重新同步会产生新的 `DocumentRevision` 与新的 artifacts（内容寻址存储只增不删）。

### 3.3 网络

| 场景 | 需要出网吗 | 目标 |
|---|---|---|
| 只做本地检索（18 条路由 + 大部分 CLI） | **不需要** | 只读本地 SQLite 与 `artifacts/` |
| `cambridge-syllabuses` / `cambridge-probe` / `cambridge-discover` | 需要 | `https://www.cambridgeinternational.org` |
| `sync --adapter cambridge` | 需要 | 同上 |
| `sync --adapter edexcel` | 需要 | `https://qualifications.pearson.com` |
| `/paper-qa/resolve`、`/paper-qa/query`、`examdata paper-qa` | 需要 | CIE：`https://cie.fraft.cn`；Edexcel：`https://qualifications.pearson.com` |
| 其余全部 | 不需要 | — |

抓取侧默认行为（都可通过环境变量调整，见第 13 章）：

- 强制校验 `robots.txt`（`EXAMDATA_RESPECT_ROBOTS=True`）。
- 同一主机两次请求之间至少间隔 1.0 秒，再加 0~0.5 秒随机抖动。**这是设计上的限速，不是性能缺陷**，同步慢是正常的。
- 超时 30 秒，最多尝试 3 次，退避基数 2 秒（即 2s / 4s / 8s）。
- 只对网络层异常与 HTTP `>= 500` 重试；4xx / 3xx 不重试。

服务器上如果只读本地数据，可以完全断网运行；只有 `paper-qa` 与同步类命令需要出网。

## 4 获取代码与安装

### 4.1 Linux 与 macOS

```bash
git clone https://github.com/WENGENG-boop/examdata.git
cd examdata
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install .
```

**`pip install .` 还是 `pip install -e .`**：

| 场景 | 用哪个 | 原因 |
|---|---|---|
| 服务器部署（只运行，不改代码） | `pip install .` | 装成普通包，源码目录可以只读 |
| 本地开发（要改代码） | `pip install -e ".[dev]"` | editable 安装，改完立刻生效，并装上测试依赖 |

装完后 CLI 入口在 `.venv/bin/examdata`。你可以直接用绝对/相对路径调用，也可以激活虚拟环境后直接用 `examdata`：

```bash
source .venv/bin/activate
examdata --help
```

### 4.2 Windows

在 Git Bash 或 PowerShell 中：

```bash
git clone https://github.com/WENGENG-boop/examdata.git
cd examdata
python -m venv .venv
.venv/Scripts/pip install --upgrade pip
.venv/Scripts/pip install .
```

Windows 与 Linux/macOS 的差异只有两处：

- 可执行文件在 `.venv\Scripts\`（Git Bash 里写 `.venv/Scripts/`），不是 `.venv/bin/`。
- 控制台默认编码可能不是 UTF-8，输出中文会乱码。先设一次环境变量：

```bash
# Git Bash
export PYTHONIOENCODING=utf-8

# PowerShell
$env:PYTHONIOENCODING='utf-8'
```

### 4.3 安装验证

三条命令，全部无副作用（只读适配器注册表、不碰数据库、不出网）：

```bash
.venv/bin/examdata --help          # 应列出 32 个子命令
.venv/bin/examdata adapters        # 应输出 cambridge 与 edexcel 两行
.venv/bin/python -c "import examdata, examdata.api.app; print(examdata.__version__)"
```

`adapters` 的预期输出形如：

```
  cambridge    Cambridge International        accessibility=public
  edexcel      Pearson Edexcel                accessibility=partial_public
```

### 4.4 常见安装报错

| 报错 | 原因 | 处理 |
|---|---|---|
| `ERROR: Package 'examdata' requires a different Python: 3.10.x not in '>=3.11'` | Python 版本过低 | 装 3.11 或更新版本，重建 venv |
| `error: Microsoft Visual C++ 14.0 or greater is required` | 在旧版 Python 上编译 `lxml` | 升级 Python（3.11+ 有预编译 wheel），或装 Visual Studio Build Tools |
| `ModuleNotFoundError: No module named 'examdata'` | 没在 venv 里安装，或用了系统 `python` | 用 `.venv/bin/python` / `.venv/Scripts/python.exe` 的绝对路径 |
| `examdata: command not found` | 没激活 venv，也没写路径 | 用 `.venv/bin/examdata`，或 `source .venv/bin/activate` |
| `pip install` 卡在下载 | 网络问题 | 换镜像源，例如 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |

## 5 准备数据

### 5.1 为什么克隆下来是空的

`.gitignore` 里排除了与本文相关的两类东西（下面是节选，此外还排除了 `.venv/`、`__pycache__/`、`*.egg-info/`、`build/`、`dist/`、`.pytest_cache/`、`pytest-of-weo/`、`.piptmp/`、`tmpwork/`、`wheels/` 等）：

```text
# --- 运行时数据（数据库、下载的原件、图形资产）---
.data/
*.db
*.sqlite3

# --- 版权材料：真实试卷不得进入版本库 ---
tests/fixtures/*.pdf
```

结果就是：

- **`.data/` 不在仓库里**。它是运行时数据目录，装的是数据库和所有下载/解析出来的文件。
- **`tests/fixtures/*.pdf` 不在仓库里**。测试用的真实试卷是考试局版权文件，公开仓库不收录。

所以你 `git clone` 下来的是一个**能跑但没数据**的空壳。`examdata serve` 能起来，`/health` 会返回 `{"status":"ok","papers":0}`，所有检索返回空列表。

`.data/` 里应该有什么（以本机实测样例库为例）：

| 路径 | 内容 | 本机实测 |
|---|---|---|
| `.data/examdata.db` | SQLite 数据库，全部结构化数据 | 约 4.0 MB |
| `.data/artifacts/` | 内容寻址对象存储，PDF 原件与图形资产 | 约 38 MB，158 个一级分片目录 |
| `.data/assets/` | 资产目录（本项目当前实现里由 `artifacts/` 承担实际存储） | 空 |
| `.data/raw_pages/` | 原始 HTML 快照目录（`ensure_dirs()` 会创建） | 空 |
| `.data/samples/`、`.data/discovery.json`、`.data/syllabuses.json` | 样例与发现结果，由具体操作生成，非必需 | — |

`artifacts/` 的布局是 `ab/cd/<sha256><ext>`（取 sha256 前两位与次两位做两级分片），与 S3/MinIO 的 key 布局一致。**数据库里存的是这个相对路径**（`storage_key`），所以数据库和 `artifacts/` 必须一起搬、保持相对结构不变，缺一个就会出现"查得到记录、取不到文件"。

### 5.2 路线 A 把已有数据搬到服务器

适用：你已经在一台机器上跑过 `sync` + `parse-docs`，想把现成的数据搬过去，不想重新抓一遍。

**第 1 步：在源机器上停掉可能正在写的进程**（正在跑的服务、正在跑的 `sync`/`parse-docs`）。SQLite 开了 WAL 模式，运行时会有 `-wal` / `-shm` 辅助文件，热拷贝可能拿到不一致的快照。

**第 2 步：传输**。注意源路径末尾的 `/`，它表示"拷贝目录内容"而不是"拷贝目录本身"：

```bash
rsync -av --progress \
  /path/to/examdata/.data/ \
  <用户名>@<目标主机>:/srv/examdata/.data/
```

要替换的占位符：`/path/to/examdata/.data/`（源机器上的数据目录）、`<用户名>`、`<目标主机>`、`/srv/examdata/.data/`（目标机器上的数据目录）。

这里的 `/srv/examdata/.data/` 只是一个示例路径。如果你按第 12 章的生产布局部署，数据目录约定是 `/var/lib/examdata`，把目标路径与后面的 `EXAMDATA_DATA_DIR` / `EXAMDATA_DATABASE_URL` 一并换成它即可。

如果你在**本机**（比如 Windows 开发机）往服务器搬：

```bash
rsync -av --progress \
  .data/ \
  <用户名>@<目标主机>:/srv/examdata/.data/
```

`rsync -av` 只传增量，重复执行很快。**不要加 `--delete`**，除非你确定要镜像删除目标端的额外文件。

**第 3 步：在目标机器上设权限**。服务进程需要对整个 `.data/` 有读写权限——SQLite 需要能写数据库文件和它所在目录（WAL、临时文件），`artifacts/` 也可能在后续操作中新增文件：

```bash
sudo chown -R examdata:examdata /srv/examdata/.data
sudo find /srv/examdata/.data -type d -exec chmod 750 {} \;
sudo find /srv/examdata/.data -type f -exec chmod 640 {} \;
```

`examdata` 是第 12.2 节创建的服务账号；如果你还没创建，先看那一节，或者暂时用你自己的账号。

**第 4 步：在目标机器上把路径配成绝对路径**（这一步最容易被忘，忘了就会静默指向空库）：

```bash
export EXAMDATA_DATA_DIR=/srv/examdata/.data
export EXAMDATA_DATABASE_URL=sqlite:////srv/examdata/.data/examdata.db
```

注意 `sqlite:////` 是**四个斜杠**：三个是 SQLAlchemy 的 scheme 分隔符，第四个是绝对路径的开头。写成三个斜杠会被当成相对路径（详见 15 章）。

**第 5 步：验证**。跳到 5.5。

### 5.3 路线 B 在服务器上从头抓取

适用：你没有现成数据，或者想自己控制抓取范围。

完整序列（本项目 README 给出的就是这条）：

```bash
.venv/bin/examdata initdb
.venv/bin/examdata sync --adapter cambridge --syllabus 0580
.venv/bin/examdata parse-docs
.venv/bin/examdata enrich
.venv/bin/examdata provenance-rebuild
.venv/bin/examdata db-stats
```

逐步说明：

**`initdb`** — 建表并补齐后加的列。幂等，重复跑无副作用。**不出网、不下载**。耗时：亚秒级。

**`sync --adapter cambridge --syllabus 0580`** — 完整数据闭环：发现 → 去重 → 下载 → 版本化 → 落库。这是**唯一会大量出网**的一步。

- `--syllabus 0580` 同时接受 slug 与科目代码，按科目代码过滤最方便。不指定就会处理全部已发现的 syllabus。
- 会写 `Board` / `Qualification` / `Subject` / `ExamSeries` / `ResourceSource` / `ResourceCandidate` / `Document` / `Artifact` / `DocumentRevision`。
- 重复运行不会重复下载：用 ETag / `If-Modified-Since` 做条件请求；内容真的变了才生成新的 `DocumentRevision`，历史版本保留。
- **耗时**：受上游限速支配。同一主机两次请求之间至少间隔 1.0 秒再加 0~0.5 秒抖动，即单机串行抓取的速率上限约每分钟 40–60 个请求。每个资源通常至少需要"发现页/清单"+"下载"两次请求，所以一个科目的同步量级基本就是"候选资源数 × 2 次请求 ÷ 50 每分钟"分钟。想先估算规模，可以先用 `--resources` 限制每个 syllabus 的资源数：

```bash
.venv/bin/examdata sync --adapter cambridge --syllabus 0580 --resources 5
```

**`parse-docs`** — 解析已下载的 PDF：题目结构化 + 评分标准关联 + 校验落库。

- **不出网**，只读本地内容寻址存储里的 PDF。
- 只处理 `parse_status=pending` 的 `DocumentRevision`，已解析的不会重复处理。
- 解析产物写入新的 `ParseRun`，历史结果保留。
- 会写 `ParseRun` / `Paper` / `Question` / `Asset` / `MarkScheme` / `MarkSchemeEntry` / `OfficialAnswer` / `ValidationFinding` / `ReviewTask`。
- **耗时**：与文档页数和题目数成正比，纯本地计算，比同步快得多。
- 可选：`--limit N` 只解析前 N 个待解析版本；`--document-id ID` 只解析指定文档；`--show-tree` 打印题目树。

**`enrich`** — 一次跑完智能层：知识点 → 难度 → 相似题 → 生成解析。

- **不出网**，全部确定性可复现，不依赖模型服务。
- 内部依次执行 `sync_taxonomy` → `assign_taxonomy` → `estimate_all` → `find_similar` → `generate_explanations`，对后四项都传 `replace=True`。
- 会写知识点节点、知识点标注、难度估计、相似题对、生成解析。
- 可选：`--subject 0580` 只处理指定科目；`--min-score` 调整相似度阈值（默认 `0.62`）。
- **耗时**：本地计算。相似题是两两比较，题目多时明显变慢。
- 跑完会打印提示：生成解析均为 `provider=rule-based`、`review_status=pending`，需人工审核后才可视为可信材料。

**`provenance-rebuild`** — 重建溯源边。纯投影、幂等，**不出网**。可选 `--board cambridge` 限定考试局。耗时：亚秒到秒级。

**`db-stats`** — 查看已落库的数据规模（只读）。

**Edexcel 适配器的差异**：

```bash
.venv/bin/examdata sync --adapter edexcel
```

- 数据源不同：Cambridge 靠服务端渲染的 HTML 锚点，Edexcel 走站内 Algolia JSON servlet（`/services/pearson/algolia/GET.servlet`）。
- **结果上限 1000 条**（`hitsPerPage` 硬上限）。撞上限时会按考季/文档类型递归分片；切到深度上限仍饱和就**显式报错**，不会返回可能被截断的清单。
- **大量资源是登录墙**。实测同步 `accounting-2023-modular` 得到 44 份文档，其中只有 1 份是公开可下载的 PDF，其余为登录墙资源或非试题材料。
- Edexcel 的 `gating` 字段实测恒为 false，**不能**用它判断资源是否受限；实现里改用 URL 前缀判定。这个坑已经修掉，但你如果自己写脚本抓 Pearson，别信那个字段。

### 5.4 两条路线怎么选

| 情况 | 建议 |
|---|---|
| 已有可用的 `.data/`，目标只是换台机器跑 | **路线 A**。几分钟搞定，且拿到的是已经验证过的数据 |
| 想要新科目、新考季，或源数据已经过期 | **路线 B**。先用 `--resources` 小批量试，确认上游可达再全量 |
| 服务器不能出网 | 只能**路线 A**。`/paper-qa` 也会不可用，但其余 18 条路由正常 |
| 只是想先跑通看看 | **路线 B** 加 `--resources` 限制，十几分钟能拿到可检索的最小数据集 |
| 想要完整数据集 | 先在某台能出网的机器上跑**路线 B**，再用**路线 A** 搬到目标机器 |

### 5.5 验证数据是否到位

在数据目录已配成绝对路径的前提下（`EXAMDATA_DATA_DIR` / `EXAMDATA_DATABASE_URL`，见 5.2 第 4 步）：

```bash
.venv/bin/examdata db-stats
```

预期能看到各实体的计数，形如（本机实测样例库）：

```
数据库规模
┏━━━━━━━━━━━━┳━━━━━━━┓
┃ 实体       ┃  数量 ┃
┡━━━━━━━━━━━━╇━━━━━━━┩
│ 资源候选   │    84 │
│ 科目       │     5 │
│ 文档       │    79 │
│ 文档版本   │    37 │
│ 内容对象   │    37 │
│ 题目       │   751 │
│ 评分条目   │   580 │
└────────────┴───────┘
```

再交叉验证几条（都是只读查询）：

```bash
.venv/bin/examdata search-papers --subject 0580 --limit 5
.venv/bin/examdata search-questions --subject 0580 --leaves --limit 5
.venv/bin/examdata monitor
```

如果 `db-stats` 全是 0，说明路径指向了一个新建的空库——回到 5.2 第 4 步检查两个环境变量，或者看第 15 章第一行。

## 6 启动服务

### 6.1 前台启动

```bash
.venv/bin/examdata serve --host 127.0.0.1 --port 8000
```

启动时它会先建表（幂等），然后打印 API 文档地址：

```
API 文档 http://127.0.0.1:8000/docs
```

前台运行适合调试；长期运行请用第 12.3 节的 systemd 单元。

**工作目录很重要**：`--host` 与 `--port` 之外的路径配置全部相对**进程当前工作目录**解析（`.env` 文件也是从当前工作目录读）。所以要么在启动前把 `EXAMDATA_DATA_DIR` 与 `EXAMDATA_DATABASE_URL` 配成绝对路径，要么确保每次都在同一个目录启动。第 12.3 节的 systemd 单元用 `WorkingDirectory=` 固定了这一点。

### 6.2 serve 的全部参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--host` | `<str>` | `127.0.0.1` | 监听地址 |
| `--port` | `<int>` | `8000` | 监听端口 |
| `--reload` | 布尔开关 | 关闭 | 热重载，仅开发用 |

`serve` **没有** `--workers`、`--log-level`、`--uds`、`--root-path` 等参数，内部也只把 `host` / `port` / `reload` 三个值传给 `uvicorn.run("examdata.api.app:app", ...)`。需要多进程或改日志级别时，用 6.4 的 uvicorn 直启写法。

### 6.3 验证服务

```bash
curl http://127.0.0.1:8000/health
```

返回：

```json
{"status":"ok","papers":16}
```

`papers` 是全库试卷总数（`count_papers` 不带过滤条件的结果）。数字是 0 不代表服务坏了，只代表库是空的——见第 5 章。

再确认交互式文档可用：

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs
```

应返回 `200`。

### 6.4 用 uvicorn 直接启动

`examdata serve` 的等价写法（需要 uvicorn 在当前环境的 PATH 里）：

```bash
.venv/bin/uvicorn examdata.api.app:app --host 127.0.0.1 --port 8000
```

用它的理由只有两个：

- **多进程**：`--workers 4`。`examdata serve` 不暴露这个选项。
- **调日志**：`--log-level info` / `--access-log`。

```bash
.venv/bin/uvicorn examdata.api.app:app --host 127.0.0.1 --port 8000 --workers 4 --log-level info
```

注意：`uvicorn` 直启**不会**执行 `examdata serve` 里的那次 `init_db()`，app 本身也没有 lifespan / startup 钩子。除 `/health`、`/paper-qa/resolve`、`/paper-qa/query` 三条之外，其余 17 条路由都在 `get_session` 依赖里调 `init_db()`（第一行），所以它们不受影响——只是首次请求会多花一点时间。实测 `init_db()` 的耗时是 **1.18 ms**，不是性能问题。

但 `/health` 走的是 `session_scope()`，**不调 `init_db()`**。库还是空的时候（一个表都没建），`GET /health` 不会返回 6.3 节那种 `{"status":"ok","papers":0}`，而是 `503`，`detail` 形如 `数据库不可用: no such table: paper`。所以用 uvicorn 直启时，先跑一次 `examdata initdb`（或先访问任意一条建表路由），再验证 `/health`。

`--reload` 与 `--workers` 同时给**不会报错**：uvicorn 只发一条 warning（`"workers" flag is ignored when reloading is enabled.`）并忽略 `--workers`，实际仍是单进程热重载。

## 7 调用方式一 CLI 全量参考

命令形式统一是 `examdata <子命令> [参数]`。任何子命令加 `--help` 都能看到它自己的参数表与默认值：

```bash
examdata search-questions --help
examdata paper-qa --help
```

下面把 32 个子命令按用途分成 7 组列出，再给可复制的完整示例。

### 7.1 命令总表

**建库与状态**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `initdb` | 建表 | 无 |
| `adapters` | 列出已注册适配器 | 无 |
| `db-stats` | 查看已落库的数据规模 | 无 |
| `monitor` | 各考试局同步/解析状态与待检查队列 | `--json` |

**发现与抓取**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `cambridge-syllabuses` | 枚举 Cambridge 全部公开 syllabus（第一层发现） | `--json <文件路径>` |
| `cambridge-probe` | 探查单个 syllabus 的 past-papers 页（第二、三层发现） | `--slug`（必填） |
| `cambridge-discover` | 全量发现：家族 -> syllabus -> 资源，不下载，仅枚举与分类 | `--limit`、`--json <文件路径>` |
| `fetch` | 抓取单个文件（统一抓取器：robots 强制 + 限速 + 重试） | `--url`（必填）、`--out`（必填） |
| `sync` | 完整数据闭环：发现 -> 去重 -> 下载 -> 版本化 -> 落库 | `--adapter`（默认 `cambridge`）、`--syllabus`、`--syllabuses`、`--resources`、`--download/--no-download` |

**解析**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `parse-pdf` | 解析试卷 PDF，输出题目树与校验发现 | `--path`（必填）、`--json`、`--show`（默认 12） |
| `parse-docs` | 解析已下载的 PDF：题目结构化 + 评分标准关联 + 校验落库 | `--limit`、`--document-id`、`--show-tree` |
| `reparse` | 用当前算法重新解析历史资源，并对比新旧结果 | `--document-id`、`--limit`、`--json` |
| `classify-content` | 基于 PDF 内容识别文件类型，与锚文本判定交叉验证 | `--apply`、`--subject` |

**检索（只读）**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `search-papers` | 按考试信息检索试卷 | `--board`、`--qualification`、`--subject`、`--year`、`--session`、`--paper`、`--component`、`--variant`、`--level`、`--limit`（默认 50）、`--json` |
| `search-questions` | 题目级检索 | `--board`、`--subject`、`--year`、`--session`、`--paper`、`--number`、`--keyword`、`--marks-min`、`--marks-max`、`--leaves`、`--roots`、`--has-asset`、`--has-answer`、`--taxonomy`、`--limit`（默认 20）、`--json` |
| `show-question` | 取出一道题的完整数据：题干、图形资产、官方答案、评分条目 | `<question_id>`（位置参数）、`--json` |
| `sample-questions` | 随机抽题 / 自动组题基础能力 | `--subject`、`--year`、`--marks-min`、`--count`、`--marks`（目标总分）、`--seed`、`--json` |

**智能层**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `taxonomy-sync` | 把官方 syllabus 的知识点种子写库（幂等） | 无 |
| `taxonomy-assign` | 给题目自动标注知识点（关键词打分，确定性可复现） | `--subject`、`--replace`、`--limit` |
| `difficulty-estimate` | 估计题目难度（与官方难度分离存储） | `--subject`、`--replace` |
| `similarity-find` | 发现相似题（TF-IDF n-gram 余弦，确定性） | `--subject`、`--min-score`（默认 0.62）、`--top-k`（默认 5）、`--replace` |
| `enrich` | 一次跑完智能层：知识点 -> 难度 -> 相似题 -> 生成解析 | `--subject`、`--min-score`（默认 0.62） |
| `explain` | 生成学生向解题解析（规则式，从官方 Mark Scheme 派生） | `--subject`、`--limit`、`--replace` |
| `explain-review` | 人工审核生成的解析 | `<explanation_id>`、`--approve`、`--reject`、`--author`（必填） |

**治理**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `override-set` | 登记一条人工修正（下次自动同步不会覆盖） | `<target_type>` `<target_id>`、`--field`（必填）、`--value`（必填）、`--author`（必填）、`--note` |
| `override-list` | 列出人工修正记录 | `--target-type`、`--target-id`、`--conflicts` |
| `review-list` | 待人工检查队列 | `--status`（默认 `open`）、`--limit`（默认 50） |
| `review-resolve` | 处置一条待检查项 | `<review_id>`、`--resolution`（必填）、`--author`（必填）、`--dismiss` |
| `provenance-rebuild` | 重建溯源边（纯投影，幂等） | `--board` |
| `provenance-trace` | 追踪某个主体的来源 | `<subject_type>` `<subject_id>` |

**服务与真题文件**

| 命令 | 作用 | 关键参数 |
|---|---|---|
| `serve` | 启动只读检索 API（FastAPI + OpenAPI 文档） | `--host`（默认 `127.0.0.1`）、`--port`（默认 8000）、`--reload` |
| `paper-qa` | CIE 整份 PDF / Edexcel IAL 整卷 PDF 与题目·答案 PNG | `--board`、`--subject`、`--year`、`--season`（均必填）、`--paper`、`--question`、`--mode`、`--out`、`--json` |

### 7.2 常用命令完整示例

以下输出取自一个真实数据库（cambridge 35 个文档 / 751 道题 / 580 条评分条目）。表格线是终端渲染，实际以你机器上的输出为准。

**看库的规模**

```bash
examdata db-stats
```

```text
    数据库规模
┌──────────┬──────┐
│ 实体     │ 数量 │
├──────────┼──────┤
│ 资源候选 │   84 │
│ 科目     │    5 │
│ 文档     │   79 │
│ 文档版本 │   37 │
│ 内容对象 │   37 │
│ 题目     │  751 │
│ 评分条目 │  580 │
└──────────┴──────┘
```

`内容对象` 是内容寻址存储里的 artifact 数（每份原始文件一份），`文档版本` 是 DocumentRevision 数（同一份文件重新同步会新增版本而不是覆盖）。

**检索题目**

```bash
examdata search-questions --subject 0580 --leaves --limit 3
```

```text
                         题目检索（共 332 条，显示 3）
┌─────┬──────┬──────┬──────┬──────┬───────┬───────────────────────────────────┐
│ id  │ 题号 │ 分值 │ 科目 │ 年份 │ Paper │ 题干                              │
├─────┼──────┼──────┼──────┼──────┼───────┼───────────────────────────────────┤
│ 753 │ 1(a) │ 1    │ 0580 │ 2025 │ 01    │ Work out the distance Kim runs.   │
│ 754 │ 1(b) │ 1    │ 0580 │ 2025 │ 01    │ Write the number 17 875 in words. │
│ 755 │ 1(c) │ 1    │ 0580 │ 2025 │ 01    │ Write the number 17 875 correct   │
│     │      │      │      │      │       │ to the nearest hundred.           │
└─────┴──────┴──────┴──────┴──────┴───────┴───────────────────────────────────┘
```

`--leaves` 只取可独立作答的叶子题（第 7.1 节的表里就是它；旧版 README 曾误写成 `--leaves-only`，会报 `No such option`，仓库里的 README 已修正）。题号里的 `1(a)` 是层级路径，不是字符串编号。

**取一道题的完整数据**

```bash
examdata show-question 753
```

```text
1(a)  marks=1  depth=1
  试卷: 01 (2025)
  题干: Work out the distance Kim runs.
............................................. m [1]
            评分标准条目
┌──────┬──────┬──────┬───────┬──────┐
│ 题号 │ 分值 │ 答案 │ M/A/B │ ECF  │
├──────┼──────┼──────┼───────┼──────┤
│ 1(a) │ 1    │ 2125 │ 0/0/0 │ None │
└──────┴──────┴──────┴───────┴──────┘
```

题干里的连续点是原卷的作答横线，属于真实内容。`M/A/B` 是 Mark Scheme 里的方法分 / 答案分 / 独立分计数。

**抽题**

```bash
examdata sample-questions --subject 0580 --marks 10 --seed 7
```

```text
                          抽题结果：5 题，合计 10 分
┌─────┬───────────┬──────┬───────┬────────────────────────────────────────────┐
│ id  │ 题号      │ 分值 │ Paper │ 题干                                       │
├─────┼───────────┼──────┼───────┼────────────────────────────────────────────┤
│ 763 │ 7         │ 1    │ 01    │ The diagram shows a shape with five shaded │
│ 92  │ 2(a)(iii) │ 2    │ 31    │ Find the ratio of people who prefer each   │
│ 306 │ 18(b)     │ 2    │ 02    │ Find f -1(x).                              │
│ 431 │ 19        │ 4    │ 04    │ The cross-section of a prism is an         │
│ 174 │ 4(b)(i)   │ 1    │ 41    │ Write down the class interval that         │
└─────┴───────────┴──────┴───────┴────────────────────────────────────────────┘
```

`--marks` 是目标总分，`--count` 是目标题数。两者至少给一个，但**校验只在 HTTP 层**：`POST /sample` 都不给会返回 422（`{"detail":"count 与 marks_target 至少给一个"}`），**CLI 不校验**——`examdata sample-questions --subject 0580` 不报错，会直接把筛选条件下的全部叶子题都抽出来（实测 327 题、合计 693 分），别把它当成默认值。给了 `--seed` 后同样的库 + 同样的参数必然得到同样的结果，方便复现。注意 HTTP 的 `POST /sample` 里这个参数叫 `marks_target`，与 CLI 的 `--marks` 是同一个东西的两个名字。

**看同步与解析状态**

```bash
examdata monitor
```

```text
                                同步与解析状态
┌────────┬──────┬──────┬──────┬────────┬───────┬──────┬──────┬────────┬───────┐
│ board  │ 文档 │ 试卷 │ 题目 │ 已解析 │ 待解… │ 失败 │ 错误 │ 待检查 │ 最后… │
├────────┼──────┼──────┼──────┼────────┼───────┼──────┼──────┼────────┼───────┤
│ cambr… │ 35   │ 16   │ 751  │ 35     │ 0     │ 0    │ 167  │ 21     │ 2026… │
│ edexc… │ 44   │ 0    │ 0    │ 2      │ 0     │ 0    │ 0    │ 0      │ 2026… │
└────────┴──────┴──────┴──────┴────────┴───────┴──────┴──────┴────────┴───────┘
资源候选状态: [{'board': 'cambridge', 'candidates': {'missing': 29, 'new': 6}},
{'board': 'edexcel', 'candidates': {'missing': 41, 'seen': 2, 'skipped': 6}}]
待人工检查 42 条
  - #22 question:760 override_target_missing_after_reparse
  - #23 question:760 override_target_missing_after_reparse
  - #24 question:760 override_target_missing_after_reparse
  - #25 question:760 override_target_missing_after_reparse
  - #26 question:760 override_target_missing_after_reparse
```

`待检查` 这一列只统计**该考试局自己的** parse_run 关联的 open 任务；而下面 `待人工检查 N 条` 是**全局**的 open 队列，且最多取 50 条（`review_queue(session, limit=50)`），紧跟其后只打印前 5 条。两者口径不同，数字不相等是正常的。想升级成完整机器可读的格式加 `--json`。

**追踪来源**

```bash
examdata provenance-trace question 753
```

```text
official_resource document:10#1(a)
  来源: https://www.cambridgeinternational.org/Images/663662-2025-specimen-paper-1.pdf
  观测时间: 2026-09-29T08:18:40.270048
  证据: {"document_id": 10, "revision_id": 10, "artifact_sha256":
"471a80b888adab75dfc5826ba54b22e05039847c7c926cbfec39e3cc4740249b",
"number_path": "1(a)", "paper_id": 17}
```

`official_resource` 表示这条链的起点是官方资源，不是推导出来的。`artifact_sha256` 指向内容寻址存储里的实际文件，可以用它在 `.data/artifacts/` 下反查。

**登记一条人工修正**

```bash
examdata override-set question 753 \
  --field marks \
  --value 2 \
  --author ops \
  --note "对照官方 Mark Scheme 修正"
```

`--author` 必填，写入 Override 记录时会一并落库，用于追责。人工确认的值不会被下一次自动同步覆盖。

**取真题文件**

```bash
examdata paper-qa --board cie --subject 9709 --year 2026 --season Mar --paper 12 --out ./downloads
```

`--out` 是**目录**，文件按来源给出的名字写进去；不给 `--out` 就只在内存里持有，退出即丢。加 `--json` 打印与 HTTP `/paper-qa/resolve` 同一套 schema 的清单，但每个文件的 `data_base64` 恒为 `null`——CLI 不把字节塞进 JSON。注意 CLI 没有"只解析清单"的入口，`--json` 也会先把文件下载到内存；**取 CIE PDF 与 Edexcel 题目/答案的每种组合见 8.6 节**，Python 调用见第 9 章。

**端到端重建（写库，耗时长）**

```bash
examdata initdb
examdata sync --adapter cambridge --syllabus 0580 --resources 5
examdata parse-docs --limit 20
examdata enrich --subject 0580
examdata provenance-rebuild
examdata db-stats
```

这就是 README 里的那条序列。`--resources 5` 是故意的小批量，用来先验证链路能通；确认没问题再去掉它跑全量。详见第 5 章。

### 7.3 出网、写库、只读标注

| 命令 | 出网 | 写本地库 | 备注 |
|---|---|---|---|
| `initdb` | 否 | 是 | 只建表，不改数据 |
| `adapters` | 否 | 否 | 纯打印 |
| `db-stats` | 否 | 否 | 纯只读 |
| `monitor` | 否 | 否 | 纯只读 |
| `cambridge-syllabuses` | 是 | 否 | 只写 `--json` 指定的文件 |
| `cambridge-probe` | 是 | 否 | 纯打印 |
| `cambridge-discover` | 是 | 否 | 只写 `--json` 指定的文件 |
| `fetch` | 是 | 否 | 写磁盘文件到 `--out` |
| `sync` | 是 | 是 | 下载 + 落库 |
| `parse-pdf` | 否 | 否 | 不写库；带 `--json` 时写指定文件 |
| `parse-docs` | 否 | 是 | 读本地 PDF，写题目与评分条目 |
| `reparse` | 否 | 是 | 不重新下载，只读本地内容寻址存储 |
| `classify-content` | 否 | 仅 `--apply` | 不加 `--apply` 是试算 |
| `search-papers` | 否 | 否 | 纯只读 |
| `search-questions` | 否 | 否 | 纯只读 |
| `show-question` | 否 | 否 | 纯只读 |
| `sample-questions` | 否 | 否 | 纯只读 |
| `taxonomy-sync` | 否 | 是 | 幂等 |
| `taxonomy-assign` | 否 | 是 | 幂等 |
| `difficulty-estimate` | 否 | 是 | 幂等 |
| `similarity-find` | 否 | 是 | 幂等 |
| `enrich` | 否 | 是 | 幂等，等于上面四个连跑 |
| `explain` | 否 | 是 | 写入的解析默认待人工审核 |
| `explain-review` | 否 | 是 | 人工审核动作 |
| `override-set` | 否 | 是 | 人工修正 |
| `override-list` | 否 | 否 | 纯只读 |
| `review-list` | 否 | 否 | 纯只读 |
| `review-resolve` | 否 | 是 | 人工处置动作 |
| `provenance-rebuild` | 否 | 是 | 纯投影，幂等 |
| `provenance-trace` | 否 | 否 | 纯只读 |
| `serve` | 运行时看路由 | 启动时建表 | 见下方说明 |
| `paper-qa` | 是 | 否 | 只写 `--out` 目录 |

两点补充：

- **`serve` 的运行期行为**：进程启动时执行一次 `init_db()`。之后 20 条业务路由里只有 `/paper-qa/resolve` 和 `/paper-qa/query` 会出网，其余 18 条只读本地库，全部路由都不写库。
- **“只读”命令仍会触碰数据库文件**：除 `adapters`、`cambridge-syllabuses`、`cambridge-probe`、`cambridge-discover`、`fetch`、`parse-pdf`、`paper-qa` 这 7 条之外，其余 25 条子命令在开头都会执行一次 `init_db()`（`CREATE TABLE IF NOT EXISTS`，幂等）。所以运行“只读”命令的账号仍然需要数据库文件所在目录的写权限。实测 `init_db()` 耗时约 1.18 ms。

## 8 调用方式二 HTTP API

`examdata serve` 起的就是这一套。20 条业务路由，全部只读——唯一一个 POST `/sample` 也只查库、只在内存里抽题，不写任何数据。写入类操作（人工修正、重新解析）刻意不开放 HTTP，只能走 CLI。

### 8.1 交互式文档

服务起来之后，FastAPI 自带三份文档，全部不需要额外配置：

| 路径 | 内容 |
|---|---|
| `/docs` | Swagger UI，可以直接在浏览器里点“Try it out”发请求 |
| `/redoc` | ReDoc，适合通读参数与模型 |
| `/openapi.json` | OpenAPI 3 规范原文，给代码生成器用 |

```bash
curl -s http://127.0.0.1:8000/openapi.json | head -c 400
```

**一个必须知道的限制**：除 `/paper-qa/resolve`、`/paper-qa/query`、`/assets/{asset_id}` 之外，其余 17 条路由的响应模型都写成 `dict[str, Any]`，OpenAPI 里只声明成 `object`，**没有字段级 schema**。也就是说 `/docs` 能告诉你每条路由收什么参数，但不会告诉你响应里有哪些字段。响应字段以本章 8.3 节的表和 8.5 节的实测输出为准。

### 8.2 通用约定

**参数位置**：所有参数都在 query string 里，包括 `POST /sample`（它没有请求体，`Content-Type` 随便，`curl -X POST` 后面直接拼 query 就行）。

**鉴权**：没有。服务不认任何 token、cookie 或 header。谁能连上端口谁就能调，所以访问控制必须靠网络层（第 10–12 章）。

**CORS**：没有。中间件列表是空的，浏览器里跨域调这个 API 会被同源策略挡掉。要从前端页面直接调，只能把页面放到同一个域名下，或者自己在前面加一层带 CORS 头的反向代理。

**请求方法**：业务路由只接受 `GET` 或 `POST`，**不接受 `HEAD`**。用 `curl -I` 探测会拿到 405。

**执行模型**：所有路由函数都是同步 `def`，FastAPI 会把它们丢进线程池执行，不会阻塞事件循环。慢请求（`/paper-qa/query`）不会卡住其他请求，但线程池大小有限，并发很高时会排队。

**每次请求都建表**：除 `/health`、`/paper-qa/resolve`、`/paper-qa/query` 三条之外，其余 17 条路由的数据库依赖第一行都会执行一次 `init_db()`（`CREATE TABLE IF NOT EXISTS`，幂等）。实测耗时约 1.18 ms，不是性能问题；但这意味着服务进程需要对数据库文件所在目录有写权限。

**分页**：`/papers` 和 `/questions` 用 `limit` + `offset`，响应形如 `{"total": <过滤后总数>, "limit": <本次 limit>, "offset": <本次 offset>, "items": [...]}`。`total` 是**过滤后**的总数，不是全库总数。`/review`、`/overrides`、`/classifications` 用 `count` + `items`，没有 `offset`。

**布尔参数**：写 `true` / `false` 或 `1` / `0`。`has_asset` 和 `has_answer` 是三态——`true` 要求有、`false` 要求没有、不传则不限。

**错误体**：业务错误固定是 `{"detail": ...}`。参数校验失败（422）时 `detail` 是**数组**（FastAPI 的标准格式），业务校验失败时 `detail` 是**字符串**。未捕获的异常返回 `text/plain` 的 `Internal Server Error`，不是 JSON。未知路径返回 `{"detail": "Not Found"}`；方法不匹配返回 405 并带 `Allow` 响应头。

### 8.3 路由逐条说明

以下按功能分组，与 `src/examdata/api/app.py` 里的定义顺序不完全一致（以文件为准）。

#### 健康检查

**`GET /health`**

无参数。响应：

| 字段 | 类型 | 含义 |
|---|---|---|
| `status` | string | 固定 `ok` |
| `papers` | int | 全库试卷总数（不带任何过滤） |

状态码：`200` 正常；`503` 数据库不可用，`detail` 形如 `数据库不可用: <异常文本>`。除两条 paper-qa 路由外，这是唯一不触发 `init_db()` 的路由，也是唯一一条把异常转成 503 的路由。

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{"status":"ok","papers":16}
```

`papers` 为 0 不代表服务坏了，只代表库是空的——见第 5 章。

#### 检索

**`GET /papers`** —— 按考试信息检索试卷。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `board` | string | 无 | 考试局 key，如 `cambridge` |
| `qualification` | string | 无 | 考试体系 key |
| `subject` | string | 无 | 科目代码，如 `0580` |
| `year` | int | 无 | 年份 |
| `session` | string | 无 | 考试季，如 `june` |
| `paper` | string | 无 | Paper 代码，如 `11` |
| `component` | string | 无 | 组件 |
| `variant` | string | 无 | 变体 |
| `level` | string | 无 | 级别 |
| `doc_type` | string | 无 | 文档类型，如 `question_paper` |
| `limit` | int | 50 | 范围 1–500 |
| `offset` | int | 0 | 从 0 开始 |

响应 `items[]` 每条字段：`paper_id`、`document_id`、`board`、`board_name`、`subject_code`、`subject_title`、`year`、`session`、`paper_code`、`component`、`variant`、`level`、`doc_type`、`title`、`duration_minutes`、`marks_total`、`question_count`、`page_count`、`status`。

```bash
curl -s 'http://127.0.0.1:8000/papers?subject=0580&limit=2'
```

**`GET /questions`** —— 题目级检索。最常用的一条。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `board` | string | 无 | 考试局 key |
| `subject` | string | 无 | 科目代码 |
| `year` | int | 无 | 年份 |
| `session` | string | 无 | 考试季 |
| `paper` | string | 无 | Paper 代码 |
| `level` | string | 无 | 级别 |
| `number_path` | string | 无 | 题号路径，如 `1(a)` |
| `keyword` | string | 无 | 题干关键词 |
| `marks_min` | int | 无 | 分值下限 |
| `marks_max` | int | 无 | 分值上限 |
| `leaves_only` | bool | false | 只取可独立作答的叶子题 |
| `roots_only` | bool | false | 只取大题 |
| `has_asset` | bool | 无 | true 要求有图形，false 要求没有 |
| `has_answer` | bool | 无 | true 要求有官方答案，false 要求没有 |
| `taxonomy` | string | 无 | 知识点代码 |
| `limit` | int | **20** | 范围 1–500 |
| `offset` | int | 0 | 从 0 开始 |

注意默认 `limit` 是 20，比 `/papers` 的 50 小。

响应 `items[]` 每条字段：`question_id`、`number_path`、`depth`、`kind`、`marks`、`page_from`、`page_to`、`stem_text`、`board`、`subject_code`、`year`、`paper_code`、`paper_id`。

```bash
curl -s 'http://127.0.0.1:8000/questions?subject=0580&leaves_only=true&limit=5'
```

**`GET /questions/{question_id}`** —— 单题完整内容。

响应是一个大对象，固定有 9 个顶层键：

| 键 | 类型 | 含义 |
|---|---|---|
| `question` | object | 题目本体：`id`、`number_label`、`number_path`、`depth`、`kind`、`marks`、`page_from`、`page_to`、`stem_text`、`parse_confidence`、`has_override` |
| `paper` | object | 所属试卷：`paper_id`、`document_id`、`paper_code`、`year`、`doc_type` |
| `children` | array | 子题 |
| `assets` | array | 图形资产 |
| `official_answers` | array | 官方答案 |
| `mark_scheme_entries` | array | 评分条目：`mark_scheme_id`、`mark_scheme_document_id`、`number_path`、`marks`、`answer_text`、`acceptable_answers`、`method_marks`、`accuracy_marks`、`independent_marks`、`ecf`、`guidance`、`parse_confidence` |
| `taxonomy` | array | 知识点标注 |
| `difficulty` | array | 难度 |
| `similar_questions` | array | 相似题 |

状态码：`200`；`404` 时 `detail` 是 `题目 {question_id} 不存在`。

```bash
curl -s http://127.0.0.1:8000/questions/753
```

**`GET /questions/{question_id}/similar`** —— 相似题。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 10 | 范围 1–50 |

响应：`{question_id, count, items}`。状态码：`200`；`404` 题目不存在。

```bash
curl -s 'http://127.0.0.1:8000/questions/753/similar?limit=5'
```

**`GET /papers/{paper_id}/tree`** —— 整卷题目树。

无参数。响应：`{paper, roots}`，`roots` 是嵌套的题目树。状态码：`200`；`404` 时 `detail` 是 `试卷 {paper_id} 不存在`。

```bash
curl -s http://127.0.0.1:8000/papers/1/tree
```

**`GET /taxonomy`** —— 知识点体系。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `board` | string | 无 | 只取某个考试局的体系 |

响应：`{roots, topic_count}`。每个 root 有 `id`、`code`、`name`、`node_type`、`source`、`question_count`、`children`。

```bash
curl -s 'http://127.0.0.1:8000/taxonomy?board=cambridge'
```

**`POST /sample`** —— 随机抽题 / 自动组题。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `subject` | string | 无 | 科目代码 |
| `year` | int | 无 | 年份 |
| `paper` | string | 无 | Paper 代码 |
| `marks_min` | int | 无 | 每题分值下限 |
| `count` | int | 无 | 抽题数量，范围 1–200 |
| `marks_target` | int | 无 | 目标总分，范围 1–300 |
| `seed` | int | 无 | 随机种子，便于复现 |

没有请求体，参数全在 query string。`count` 和 `marks_target` **至少要给一个**，否则 422，`detail` 是字符串 `count 与 marks_target 至少给一个`。抽题池固定是叶子题（等价于强制 `leaves_only=true`）、上限 5000 条。

响应：`{marks_total, requested_marks, question_count, questions}`。

```bash
curl -X POST 'http://127.0.0.1:8000/sample?subject=0580&marks_target=20&seed=7'
```

`seed` 相同 + 库不变 → 结果完全一致。

#### 内容

**`GET /assets/{asset_id}`** —— 取回图形资产原件。

无参数。返回的是**文件本身**（`FileResponse`），`Content-Type` 取资产的 `mime`，缺失时是 `application/octet-stream`。**不设 `Content-Disposition`**，所以浏览器会内联显示图片而不是下载。想存成文件用 `curl -o`。

状态码：`200`；`404` 时 `detail` 是 `资产 {asset_id} 不存在`；`410` 时 `detail` 是 `资产文件已丢失`（数据库里有记录，但内容寻址存储里的文件不见了）。

```bash
curl -o asset1.png http://127.0.0.1:8000/assets/1
```

实测返回 5866 字节的 `image/png`。

**`GET /questions/{question_id}/explanation`** —— 系统生成的解题解析。

无参数。响应：`{question_id, official, generated}`。

`official[]` 每条：`id`、`source`、`content`、`is_official`。

`generated[]` 每条：`id`、`provider`、`model`、`prompt_version`、`approach`、`steps`、`final_answer`、`marking_points`、`common_errors`、`review_status`、`is_official`。

生成内容恒为 `is_official=false`、`provider=rule-based`，`review_status` 默认 `pending`。**未审核的生成内容不应直接展示给学生**。状态码：`200`；`404` 题目不存在。

```bash
curl -s http://127.0.0.1:8000/questions/2/explanation
```

**`GET /explanations/review-queue`** —— 待审核的生成解析队列。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `status` | string | `pending` | `pending` / `approved` / `rejected` |
| `limit` | int | 50 | 范围 1–500 |

响应：`{status, total, count, items}`。`total` 是该状态下全部条数，`count` 是本次返回条数。`items[]` 每条只有 `id`、`question_id`、`provider`、`review_status`。

```bash
curl -s 'http://127.0.0.1:8000/explanations/review-queue?status=pending&limit=20'
```

#### 治理

**`GET /monitor`** —— 后台监控总览。

无参数。响应：`{sync, health, review_queue}`。

- `sync`：每个考试局一条，含 `board`、`name`、`accessibility`、`documents`、`papers`、`questions`、`parsed`、`pending`、`failed`、`open_review_tasks`、`open_errors`、`last_sync_at`、`last_sync_status`、`last_sync_stats`。
- `health`：采集健康度列表。
- `review_queue`：待检查队列，**固定取前 200 条**，不受任何参数控制。

```bash
curl -s http://127.0.0.1:8000/monitor
```

**`GET /review`** —— 待人工检查队列。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `status` | string | `open` | `open` / `in_progress` / `done` / `dismissed` |
| `target_type` | string | 无 | 按目标类型过滤 |
| `limit` | int | 50 | 范围 1–500 |

响应：`{status, count, items}`。`items[]` 每条：`id`、`target_type`、`target_id`、`reason`、`priority`、`status`、`assignee`、`resolution`。

```bash
curl -s 'http://127.0.0.1:8000/review?status=open&limit=20'
```

**`GET /overrides`** —— 已登记的人工修正。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `target_type` | string | 无 | 按目标类型过滤 |
| `target_id` | int | 无 | 按目标 id 过滤 |
| `conflicts` | bool | false | 只看冲突未生效的 |

响应：`{count, items}`。这条路由只返回 `active=true` 的记录，没有参数能改变这一点。

```bash
curl -s 'http://127.0.0.1:8000/overrides?conflicts=true'
```

**`GET /classifications`** —— 文件类型判定及其证据。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `document_id` | int | 无 | 只看某个文档 |
| `method` | string | 无 | 精确匹配判定方法，如 `label_grammar+slug_crosscheck` |
| `limit` | int | 50 | 范围 1–500 |

响应：`{count, conflicts, items}`。`conflicts` 是 `items` 里 `method == "conflict"` 的条数（**不是全库冲突数**，是本次返回结果里的冲突数）。`items[]` 每条：`id`、`document_id`、`doc_type`、`confidence`、`method`、`evidence`。

按 `id` 倒序返回，最新的在前。`method` 是精确匹配，实际取值由解析器决定，别照抄文档里的示例值。

```bash
curl -s 'http://127.0.0.1:8000/classifications?limit=10'
```

#### 溯源

**`GET /questions/{question_id}/provenance`** —— 一道题的最初来源。

无参数。响应：`{question_id, sources}`。`sources[]` 每条：`source_kind`、`source_ref`、`source_url`、`run_id`、`observed_at`、`attrs`（含 `document_id`、`revision_id`、`artifact_sha256`、`number_path`、`paper_id` 等）。

状态码：`200`；`404` 题目不存在。

```bash
curl -s http://127.0.0.1:8000/questions/753/provenance
```

**`GET /assets/{asset_id}/provenance`** —— 一个图形资产的来源。

无参数。响应：`{asset_id, sources}`，字段同上。状态码：`200`；`404` 资产不存在。

```bash
curl -s http://127.0.0.1:8000/assets/1/provenance
```

**`GET /provenance/coverage`** —— 溯源覆盖率。

无参数。响应：`{coverage, complete}`。`coverage` 固定 5 个键：`question`、`mark_scheme_entry`、`asset`、`official_answer`、`paper`，每个值是 `{total, linked, edges, ratio}`。`complete` 是所有 `ratio >= 1.0` 时为 true。

`ratio` 低于 1.0 说明有派生数据追不到来源，应当重建溯源（见第 14 章）。

```bash
curl -s http://127.0.0.1:8000/provenance/coverage
```

实测：

```json
{"coverage":{"question":{"total":751,"linked":751,"edges":751,"ratio":1.0}, "...": "..."},"complete":true}
```

#### paper-qa

这两条是唯一会**出网**的路由，需要能访问 `cie.fraft.cn` 与 `qualifications.pearson.com`。

**`GET /paper-qa/resolve`** —— 解析真题清单，不下载文件。

| 参数 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `board` | 是 | string | `cie` 或 `edexcel`（写 `cambridge` 会被归一化成 `cie`） |
| `subject` | 是 | string | CIE 为四位数字；Edexcel 如 `accounting-2023-modular` |
| `year` | 是 | int | 2000–2099 |
| `season` | 是 | string | 见下方归一化表 |
| `paper` | 否 | string | Paper 代码 |
| `question` | 否 | string | 题号，如 `1(a)` |
| `mode` | 否 | string | CIE：`qp` / `ms` / `both`；Edexcel：`paper` / `question` / `qa` |

响应就是 paper-qa 的统一 schema：顶层 `schema_version` / `request` / `counts{documents,files,bytes}` / `documents[]` / `files[]`。**`files` 恒为空数组**——本路由只回答“这个组合对应哪些官方文件”，不回答“文件内容是什么”，从不下载。每个 file 对象的 `data_base64` 键恒存在，此处为 `null`。

```bash
curl -s 'http://127.0.0.1:8000/paper-qa/resolve?board=cie&subject=9709&year=2026&season=Mar&paper=12&mode=qp'
```

**`GET /paper-qa/query`** —— 取回真题文件。

参数与 `/paper-qa/resolve` 完全相同，额外多一个：

| 参数 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `format` | 否 | string | `binary`（默认）或 `json`，其它值 422 |

默认（`binary`）行为：单文件直接返回原始字节（`application/pdf` 或 `image/png`），带 `Content-Disposition: attachment; filename="<名字>"` 与 `Content-Length`；多文件（`mode=both` / `mode=qa`）在内存里打 ZIP，文件名固定 `paper-qa.zip`，`media_type` 是 `application/zip`。服务端全程只在内存处理，不落盘。

`format=json` 返回与 `/paper-qa/resolve` 同一套 schema 的 JSON，每个文件额外带 `data_base64`（载荷的 base64）、`sha256`、`page`、`bbox`。给处理不了二进制的客户端用（浏览器脚本、只收 JSON 的网关）。

```bash
curl -o qp.pdf 'http://127.0.0.1:8000/paper-qa/query?board=cie&subject=9709&year=2026&season=Mar&paper=12'
```

实测这份 `9709_m26_qp_12.pdf` 是 101,095 字节，sha256 前缀 `47a6c66a3223`。

**参数归一化规则**

- `board`：`cie` / `edexcel`，`cambridge` 改写成 `cie`。
- `subject`：正则 `[A-Za-z0-9][A-Za-z0-9 -]{0,79}`。
- CIE `season`：`mar` / `march` → `Mar`，`jun` / `june` → `Jun`，`nov` / `november` → `Nov`。**`Jan` 不在 CIE 的合法值里**，传了会 422 `Unsupported season for this board`。
- Edexcel `season`：`jan` / `january` / `winter` → `January`，`jun` / `june` / `summer` → `June`，`oct` / `october` → `October`，`nov` / `november` → `November`。
- `mode`：不传时 CIE 默认 `qp`、Edexcel 默认 `paper`。CIE 的 `qp+ms` 归一化成 `both`。
- CIE 要求 subject 四位数字、paper 一到两位数字，**不接受 `question`**。Edexcel 的 `question` / `qa` 模式必须同时给 `paper` 和 `question`。
- `paper` 正则 `[a-z0-9]+(?:-[a-z0-9]+)?`，`/` 会替换成 `-`。`question` 支持 `1`、`1(a)`、`1a`、`1(a)(i)`、`1ai` 几种写法（短写会自动补全）。

**错误码**

| 状态码 | 含义 |
|---|---|
| 422 | 参数非法（`InvalidRequest` / `LocationError`），如季节不支持、题号格式不对 |
| 404 | 上游没有对应的官方文件 |
| 409 | 命中多份候选文件，无法唯一确定（`AmbiguousDocument`） |
| 403 | 资源非公开（`AccessDenied`） |
| 502 | 上游故障（`UpstreamError`） |

`detail` 都是字符串。实测三条：

```text
GET /paper-qa/query?board=cie&subject=abc&year=2026&season=Mar   -> 422 {"detail":"CIE requires a four-digit subject and one/two-digit paper"}
GET /paper-qa/query?...&format=xml                                -> 422 {"detail":"format must be binary or json"}
GET /paper-qa/resolve?board=cie&subject=9709&year=2026&season=Jan -> 422 {"detail":"Unsupported season for this board"}
```

**出网行为**

`/paper-qa/resolve` 只发清单请求：CIE 一次 `POST /obj/Common/Fetch/renum`；Pearson 一次或多次 servlet GET。`/paper-qa/query` 在清单之外还要下载：CIE 的 `both` 模式 2 次 GET，`qp` / `ms` 各 1 次；Pearson 的 `qa` 模式 2 份 PDF，`paper` / `question` 各 1 份。题目裁剪在内存里用 PyMuPDF 做，不再出网。

每次调用都会新建一个抓取器，robots 缓存与按主机限速状态**不跨请求复用**。所以高频调用会受“每主机至少 1.0 秒”的间隔约束，响应时间可能明显长于本地查询。

### 8.4 错误语义

| 状态码 | 触发条件 | `detail` 形态 |
|---|---|---|
| 200 | 正常 | — |
| 403 | paper-qa 命中非公开资源 | 字符串 |
| 404 | 业务对象不存在 / 未知路径 / paper-qa 上游没有文件 | 字符串；未知路径固定是 `Not Found` |
| 405 | 方法不匹配（例如对 GET 路由发 POST，或用 `curl -I`） | 字符串，响应带 `Allow` 头 |
| 409 | paper-qa 命中多份候选 | 字符串 |
| 410 | 资产记录存在但文件已丢失 | 字符串 |
| 422 | 参数校验失败（类型、范围） | **数组** |
| 422 | 业务校验失败（如 `/sample` 两个参数都没给、`format` 非法） | 字符串 |
| 502 | paper-qa 上游故障 | 字符串 |
| 503 | 数据库不可用（仅 `/health`） | 字符串 |
| 500 | 未捕获异常 | 非 JSON，`text/plain` 的 `Internal Server Error` |

实测样例：

```text
GET /questions/999999        -> 404 {"detail":"题目 999999 不存在"}
GET /papers/999999/tree      -> 404 {"detail":"试卷 999999 不存在"}
GET /assets/999999           -> 404 {"detail":"资产 999999 不存在"}
GET /nope                    -> 404 {"detail":"Not Found"}
POST /questions/1            -> 405 {"detail":"Method Not Allowed"}  Allow: GET
GET /questions?limit=0       -> 422 {"detail":[{"type":"greater_than_equal","loc":["query","limit"],...}]}
POST /sample                 -> 422 {"detail":"count 与 marks_target 至少给一个"}
```

排错时先看 `detail` 是字符串还是数组：数组说明是 FastAPI 的参数校验（`loc` 字段会直接告诉你哪个参数错了），字符串说明是业务逻辑主动拒绝。

### 8.5 实测示例

下面三条是完整可复制的调用，输出都是真实结果。

**带过滤的题目检索**

```bash
curl -s 'http://127.0.0.1:8000/questions?subject=0580&leaves_only=true&limit=5'
```

```json
{"total":332,"limit":5,"offset":0,"items":[{"question_id":753,"number_path":"1(a)","depth":1,"kind":"sub","marks":1,"page_from":3,"page_to":3,"stem_text":"Work out the distance Kim runs.\n............................................. m [1]","board":"cambridge","subject_code":"0580","year":2025,"paper_code":"01","paper_id":17}]}
```

为便于阅读，`items` 只留了第一条，真实响应里有 5 条。`stem_text` 里的换行与连续点是原卷的作答横线，属于真实内容，不是截断标记。

**固定种子的抽题**

```bash
curl -s -X POST 'http://127.0.0.1:8000/sample?subject=0580&marks_target=20&seed=7'
```

```json
{"marks_total":21,"requested_marks":20,"question_count":11,"questions":[{"question_id":763,"number_path":"7","depth":0,"kind":"question","marks":1,"page_from":5,"page_to":5,"stem_text":"The diagram shows a shape with five shaded sections.\nShade one more section on the diagram so that it has rotational symmetry of order 3.\b\n[1]","board":"cambridge","subject_code":"0580","year":2025,"paper_code":"01","paper_id":17}, …]}
```

`questions` 是题目对象数组（字段与 `/questions` 的 `items` 相同），为便于阅读这里只留第一个，真实响应里有 11 个。`marks_total` 可能略高于 `requested_marks`——抽题是按题累加，最后一题会超过目标分。同一 `seed` 连发两次，响应逐字节一致。

**取回一份真题 PDF**

```bash
curl -o qp.pdf 'http://127.0.0.1:8000/paper-qa/query?board=cie&subject=9709&year=2026&season=Mar&paper=12'
```

落盘后 `qp.pdf` 是 101,095 字节的 PDF（`file` 命令识别为 `PDF document`）。

Edexcel 的题目裁剪示例（`mode=question`，`question=12(a)`）实测返回 **3 张 PNG 的 ZIP**（195,805 字节）：题目本体 8,089 字节落在第 11 页，`bbox` 为 `[37.51909637451172, 54.49399948120117, 555.3116455078125, 260.91534423828125]`（PDF 坐标，单位点）；另两张是题目引用的 Extract 材料页（第 30/31 页）。想拿到 `bbox` 就加 `format=json`。为什么是 3 张、什么情况下是单张，见下一节。

### 8.6 paper-qa 组合速查

上一节讲了每个参数的含义，这一节把**取 CIE PDF 与 Edexcel 题目/答案的每种组合**逐一列出，CLI 与 HTTP 两种写法都给全，全部实测通过。三个通道（CLI / HTTP / Python）的参数与归一化规则完全一致，只是形状不同：

| 通道 | 形状 |
|---|---|
| CLI | `examdata paper-qa --board <board> --subject <subject> --year <year> --season <season> [--paper <paper>] [--question <question>] [--mode <mode>] [--out <目录>] [--json]` |
| HTTP | `GET /paper-qa/query?board=<board>&subject=<subject>&year=<year>&season=<season>[&paper=<paper>][&question=<question>][&mode=<mode>][&format=binary\|json]` |
| Python | `query("<board>", "<subject>", <year>, "<season>", "<paper>", "<question>", "<mode>", out_dir=...)` |

**一个必须知道的区别**：CLI 没有"只解析清单"的入口——`examdata paper-qa` 总是调用 `query()` 把文件下载到内存，`--json` 只改变打印格式（`data_base64` 恒为 `null`），`--out` 才落盘。只有 HTTP 的 `/paper-qa/resolve` 与 Python 的 `resolve()` 是从不下载的纯解析。

#### 8.6.1 CIE：整份 PDF

CIE 只有整份 PDF，**没有题目裁剪**（传 `question` 会 422）。

| 想要 | `--mode` | 必填 | 返回 |
|---|---|---|---|
| 一份 QP（试题卷） | `qp`（默认） | `--paper` | 单份 PDF |
| 一份 MS（答案卷） | `ms` | `--paper` | 单份 PDF |
| 一份 QP + MS 打包 | `both`（或 `qp+ms`） | `--paper` | 2 份的 ZIP |
| 该考季全部 QP | `qp` | 不带 `--paper` | N 份的 ZIP |
| 该考季全部 QP+MS | `both` | 不带 `--paper` | 2N 份的 ZIP |

`--season` 只认 `Mar` / `Jun` / `Nov`（大小写不敏感，`march`、`june`、`november` 也行）；**没有 `Jan`**。`--paper` 是一到两位数字，如 `12`。

**取一份 QP**（实测 101,095 字节，sha256 前缀 `47a6c66a3223`）：

```bash
# CLI：下载到内存并列出清单，--out <目录> 才落盘
examdata paper-qa --board cie --subject 9709 --year 2026 --season Mar --paper 12 --out ./downloads

# HTTP：单文件直接返回原始字节，直接落盘
curl -o qp.pdf 'http://127.0.0.1:8000/paper-qa/query?board=cie&subject=9709&year=2026&season=Mar&paper=12'
```

**取一份 MS**：`--mode ms`（HTTP 加 `&mode=ms`）。实测 431,061 字节。

**取 QP+MS 打包**：`--mode both`。HTTP 返回 `application/zip`，包内两份 PDF，实测 482,901 字节；ZIP 成员按文件名排序（`9709_m26_ms_12.pdf` 在前，`9709_m26_qp_12.pdf` 在后），不要假设顺序。

**取该考季全部 QP**：省略 `--paper`。实测 9709 Mar 2026 共 6 份（卷号 12/22/32/42/52/62），ZIP 562,868 字节。`both` 不带 `--paper` 时要求每一份 QP 都有配对的 MS，缺任何一对整体 404。

**只看清单不下载**：

```bash
curl -s 'http://127.0.0.1:8000/paper-qa/resolve?board=cie&subject=9709&year=2026&season=Mar&paper=12&mode=qp'
```

实测返回 1 份 `9709_m26_qp_12.pdf`，`files` 恒为空数组。

#### 8.6.2 Edexcel：整卷与单题裁剪

| 想要 | `--mode` | 必填 | 返回 |
|---|---|---|---|
| 整卷 QP | `paper`（默认） | 强烈建议给 `--paper` | 单份 PDF |
| 某题的题面（PNG） | `question` | `--paper` + `--question` | 1 张 PNG，跨页/带附图时是 ZIP |
| 某题的题面+答案（PNG） | `qa` | `--paper` + `--question` | ZIP（题面 + 答案，通常 ≥2 张） |

`--season` 用 `January` / `June` / `October` / `November`（也接受 `winter` → January、`summer` → June）。`--paper` 用形如 `wec11-01` 的变体级代号；`question` / `qa` 模式给 `wec11` 这种短代号时，若该考季命中多个变体会被拒绝（409 `Specify an exact paper identifier, such as wec11-01`），稳妥写法是直接给变体级。`paper` 模式不给 `--paper` 会匹配该考季同科目的全部变体——实测 Economics June 2024 解析出 15 份，来自多个 spec，几乎总是要给的。

**取整卷 QP**（实测 358,629 字节）：

```bash
examdata paper-qa --board edexcel --subject Economics --year 2024 --season Jun --paper wec11-01 --out ./downloads

curl -o paper.pdf 'http://127.0.0.1:8000/paper-qa/query?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01'
```

**取某题的题面**（`question` 模式）：

```bash
# 实测 question=2：单页，直接返回一张 PNG（38,927 字节）；注意 shell 里给 12(a) 加引号
examdata paper-qa --board edexcel --subject Economics --year 2024 --season Jun --paper wec11-01 --question 2 --mode question --out ./downloads

curl -o q2.png 'http://127.0.0.1:8000/paper-qa/query?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&question=2&mode=question'
```

题号写法：`12`、`12(a)`、`12(a)(ii)`，也接受短写 `12a`、`12ai`（自动补全成规范形式）。题面跨页、或题目引用了 Source Booklet 里的 Extract/Figure 时，返回的是多张 PNG 的 ZIP——实测 `12(a)` 返回 3 张：第 11 页题面（8,089 字节）+ 第 30/31 页的 Extract 材料页（75,310 与 122,179 字节），ZIP 共 195,805 字节。

**取某题的题面+答案**（`qa` 模式）：

```bash
examdata paper-qa --board edexcel --subject Economics --year 2024 --season Jun --paper wec11-01 --question '12(a)' --mode qa --out ./downloads

curl -o qa.zip 'http://127.0.0.1:8000/paper-qa/query?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&question=12(a)&mode=qa'
```

实测 `12(a)` 返回 4 张 PNG 的 ZIP（227,320 字节）：题面 3 张来自 `wec11-01-que-20240510.pdf`，答案 1 张来自 `wec11-01-rms-20240815.pdf`（第 11 页，32,417 字节）。`rms` 是 Pearson 对评分方案（Mark Scheme）的文件名标记。`qa` 模式先解析出 QP 与 MS 两份清单（`/paper-qa/resolve` 加 `mode=qa` 实测 `documents` 为 2），再分别裁剪。

#### 8.6.3 输出形态与文件名

**什么时候是单文件、什么时候是 ZIP**：

| 条件 | 响应 |
|---|---|
| 恰好 1 个文件 | 原始字节（`application/pdf` 或 `image/png`），带 `Content-Disposition: attachment; filename="<名字>"` 与 `Content-Length` |
| 2 个及以上 | 内存里打的 ZIP，文件名固定 `paper-qa.zip`，`media_type` 是 `application/zip` |
| `format=json` | 不打包：JSON 清单，每个文件自带 `data_base64`、`sha256`、`page`、`bbox` |

注意"几个文件"由**实际内容**决定，不是模式本身：`question` 模式单页题是 1 张 PNG（单文件响应），跨页题或带 Extract 的题是 3 张（ZIP）。写客户端时按响应 `content-type` 判断，不要按模式预设。

**文件名规则**（`--out` 落盘与 ZIP 成员都用它）：

| 来源 | 形态 | 例子 |
|---|---|---|
| CIE | `{科目}_{考季码}{年}_{qp 或 ms}_{卷号}.pdf`，考季码 `m`=Mar、`s`=Jun、`w`=Nov | `9709_m26_qp_12.pdf` |
| Edexcel 整卷 | `{卷代号}-{que 或 rms}-{日期}.pdf` | `wec11-01-que-20240510.pdf` |
| 裁剪 PNG | `{整卷名去掉 .pdf}-q{题号}-p{页码}.png`，题号里的括号换成 `-` | `wec11-01-que-20240510-q12-a-p11.png` |

裁剪 PNG 的 `page`（1 起）与 `bbox`（PDF 用户坐标）在 `format=json` 里给出，方便回到原件复核那一小块。实测 `12(a)` 题面的 `bbox` 是 `[37.52, 54.49, 555.31, 260.92]`。

#### 8.6.4 三个通道的对照与常见坑

| 场景 | 用什么 |
|---|---|
| 人工下一次、顺便看清单 | CLI 加 `--out`；或先 `GET /paper-qa/resolve` 看清单再 `query` |
| 程序里批量取 | Python `query()` 复用 `Fetcher`（见 9.1 节），比 HTTP 快 |
| 只要 JSON（网关、浏览器脚本） | `GET /paper-qa/query?...&format=json` |
| 只要清单、不想下载 | HTTP `/paper-qa/resolve` 或 Python `resolve()`；CLI 没有纯解析入口 |

**常见坑**：

- CIE 传 `question` → 422 `CIE supports whole PDFs only; question selection is unavailable`。
- Edexcel `question` / `qa` 缺 `paper` 或 `question` → 422 `question and paper are required for question/qa mode`。
- 题号定位不到 → 422 `Question 1(a) could not be located reliably`（实测 1(a) 就报这个）。换个题号或核对卷子版式；这是明确拒绝给错图，不是 bug。
- 版式不支持（扫描件、无可靠左栏编号）→ 422 `No reliable left-column question numbering; scanned/unsupported PDF layout`。
- 409 `Multiple ... PDFs match ...; cannot select safely` → 卷代号给粗了，补全到 `wec11-01` 这样的变体级。
- 上游限速：每台主机至少间隔 1.0 秒，且每次 HTTP 请求新建抓取器。一次 `qa` 调用要下 2 份 PDF，实测 6–7 秒属正常。

## 9 调用方式三 Python 直接调用

同一台机器上写脚本、做批处理、把 examdata 嵌进别的服务时，直接 `import` 比走 HTTP 省事：不占端口、不经过网络、能拿到还没序列化的原始对象。

代价是**调用方要自己管理数据库 session 的生命周期**。这是本章反复出现的模式。

### 9.1 直接取真题文件 paperqa

`examdata.paperqa` 只导出两个函数，两个都不落盘：

```python
resolve(board, subject, year, season, paper=None, question=None, mode=None, *, fetcher=None) -> Result
query(board, subject, year, season, paper=None, question=None, mode=None, out_dir=None, *, fetcher=None) -> Result
```

`resolve()` 只解析官方清单、从不下载，所以 `result.files` 恒为空。`query()` 在清单之外把文件取回内存。参数归一化规则与 HTTP 完全一致（见 8.3 节的归一化表）；取 CIE PDF 与 Edexcel 题目/答案的每种组合见 8.6 节。

```python
from examdata.paperqa import resolve, query

manifest = resolve("cie", "9709", 2026, "Mar", "12", mode="qp")
print(manifest.metadata()["counts"])
for doc in manifest.documents:
    print(doc.name, doc.media_type, doc.role)

result = query("cie", "9709", 2026, "Mar", "12", mode="qp")
for f in result.files:
    print(f.name, len(f.data), f.sha256[:12])
    with open(f.name, "wb") as stream:
        stream.write(f.data)
```

`Result` 的字段：`request`（归一化后的请求）、`documents`（清单里的文件）、`files`（实际取回的字节）。`result.metadata()` 给出与 HTTP 同一套 schema 的字典：`schema_version` / `request` / `counts` / `documents` / `files`；加 `inline_data=True` 时每个文件额外带 `data_base64`。

**`out_dir` 是目录，不是文件路径**。传了它就会把每个文件按来源名字写进去，且用的是独占创建（`open("xb")`）——**同名文件已存在时直接抛 `FileExistsError`，不会覆盖**。批量重跑前先清空目标目录或换一个新目录。

**批量调用时复用抓取器**。默认每次调用都会新建一个 `Fetcher`，robots 缓存与按主机限速状态不跨调用共享，连续取十几份文件会非常慢。自己传一个进来就能复用：

```python
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher
from examdata.paperqa import query

with Fetcher(Settings()) as fetcher:
    for paper in ["11", "12", "13"]:
        result = query("cie", "9709", 2026, "Mar", paper, mode="qp", fetcher=fetcher)
        print(paper, [f.name for f in result.files])
```

异常统一是 `PaperQAError` 的子类，HTTP 状态码挂在异常的 `status_code` 属性上（见 8.3 节的错误码表）：

```python
from examdata.paperqa import PaperQAError, query

try:
    result = query("cie", "9709", 2026, "Mar", "12", mode="qp")
except PaperQAError as exc:
    print(exc.status_code, exc)
```

### 9.2 查询本地库 query

所有查询函数都是 `(session, ...)` 的形式，session 由调用方提供。标准写法：

```python
from examdata.core.db import init_db, session_scope
from examdata.query import QuestionFilter, count_questions, search_questions

init_db()  # 幂等，进程启动时调一次即可

with session_scope() as session:
    f = QuestionFilter(subject_code="0580", leaves_only=True, limit=3)
    print("命中", count_questions(session, f), "条")
    for row in search_questions(session, f):
        print(row["question_id"], row["number_path"], row["marks"], row["stem_text"].splitlines()[0])
```

`session_scope()` 是上下文管理器：正常退出提交、抛异常回滚。只读查询用它也没问题。

可用的入口：

| 函数 | 作用 |
|---|---|
| `search_papers(session, PaperFilter)` | 试卷检索，返回 dict 列表 |
| `count_papers(session, PaperFilter)` | 试卷计数 |
| `search_questions(session, QuestionFilter)` | 题目检索，返回 dict 列表 |
| `count_questions(session, QuestionFilter)` | 题目计数 |
| `get_question_bundle(session, question_id)` | 单题完整数据，不存在返回 `None` |
| `similar_questions(session, question_id, *, limit=10)` | 相似题 |
| `get_paper_tree(session, paper_id)` | 整卷题目树，不存在返回 `None` |
| `taxonomy_tree(session, *, board=None)` | 知识点体系 |
| `sample_questions(session, f, *, count=None, marks_target=None, seed=None)` | 抽题，返回 `PaperComposition` |
| `sync_status(session)` | 各考试局同步/解析状态 |
| `board_health(session)` | 采集健康度 |
| `review_queue(session, *, limit=100)` | 待检查队列 |

`PaperFilter` / `QuestionFilter` 是 dataclass，字段名与 HTTP 参数一一对应，但有 Python 命名差异：HTTP 的 `subject` 对应 `subject_code`、`paper` 对应 `paper_code`、`has_answer` 对应 `has_official_answer`；`session` 两边同名。两者默认 `limit=50`（HTTP `/questions` 路由自己把默认值改成了 20）。

`QuestionFilter` 还多出几个 HTTP 没暴露的字段：`depth`、`taxonomy_source`、`difficulty_min`、`difficulty_max`、`difficulty_source`。用 Python 时可以直接按难度区间过滤：

```python
from examdata.core.db import init_db, session_scope
from examdata.query import QuestionFilter, count_questions, search_questions

init_db()
with session_scope() as session:
    f = QuestionFilter(
        subject_code="0580",
        leaves_only=True,
        difficulty_min=0.4,
        difficulty_source="estimated",
        limit=3,
    )
    print("命中", count_questions(session, f), "条")  # 实测 12
    for row in search_questions(session, f):
        print(row["question_id"], row["number_path"], row["marks"])
```

实测输出（本题库里 0580 的估计难度都在 0.5 以下，`difficulty_min` 设太高会得到 0 条）：

```text
命中 12 条
317 22 4
362 14(a)(ii) 2
364 14(b) 3
```

```python
from examdata.core.db import init_db, session_scope
from examdata.query import get_question_bundle, taxonomy_tree

init_db()
with session_scope() as session:
    bundle = get_question_bundle(session, 753)
    print(bundle["question"]["stem_text"])
    print(bundle["mark_scheme_entries"][0]["answer_text"])

    roots = taxonomy_tree(session, board="cambridge")
    print(len(roots), roots[0]["code"], roots[0]["name"])
```

返回结构与 HTTP 的响应体**部分**一致：`get_question_bundle`、`search_papers`、`search_questions` 等与 HTTP 响应体直接对应，第 8 章的字段表对这些同样适用。其余路由在 HTTP 层另有包装，不能照搬——例如 `taxonomy_tree` 返回 list，HTTP 的 `/taxonomy` 包成 `{roots, topic_count}`；`sample_questions` 返回 `PaperComposition`，HTTP 的 `/sample` 包成 `{marks_total, requested_marks, question_count, questions}`；`/health`、`/monitor`、`/review`、`/explanations/review-queue`、`/provenance/coverage`、`/questions/{id}/similar` 也都各自另有包装。以第 8 章为准。

### 9.3 治理与智能层

这两个包里的函数**会写库**，这是 Python 入口相比 HTTP 的最大区别——HTTP 刻意不开放写入。

`examdata.governance`：

| 函数 | 作用 |
|---|---|
| `set_override(session, *, target_type, target_id, field_path, value, author, applies_to_parser_versions="*", note=None)` | 登记人工修正 |
| `revert_override(session, *, target_type, target_id, field_path, author)` | 撤销修正（保留历史，置 `active=False`） |
| `list_overrides(session, *, target_type=None, target_id=None, only_conflicts=False, only_active=True)` | 列出修正 |
| `list_reviews(session, *, status="open", target_type=None, limit=100)` | 待检查队列 |
| `resolve_review(session, *, review_id, resolution, author, status="done")` | 处置待检查项，`status` 只能是 `done` / `dismissed` / `in_progress` |
| `claim_review(session, *, review_id, author)` | 认领 |
| `trace(session, subject_type, subject_id)` | 溯源 |
| `coverage(session)` | 溯源覆盖率 |
| `rebuild(session, *, board=None)` | 重建溯源边（幂等投影） |
| `reparse_documents(session, *, document_ids=None, limit=None, keep_history=True)` | 重新解析 |
| `snapshot(session, document_id)` / `diff(before, after)` | 解析前后快照与对比 |

`examdata.intelligence`：

| 函数 | 作用 |
|---|---|
| `sync_taxonomy(session)` | 写入知识点种子（幂等） |
| `assign_taxonomy(session, *, subject_code=None, limit=None, replace=False)` | 批量标注知识点 |
| `classify_question(stem_text, subject_code)` | 单题标注（纯函数，不碰库） |
| `estimate_all(session, *, subject_code=None, replace=False)` | 批量难度估计 |
| `find_similar(session, *, subject_code=None, replace=False, min_score=..., top_k=...)` | 相似题发现 |
| `generate_explanations(session, *, subject_code=None, limit=None, replace=False)` | 批量生成解析 |
| `generate_for_question(session, question_id, *, replace=False)` | 单题生成解析；没有官方依据时返回 `None` |
| `review_explanation(session, explanation_id, *, status, author)` | 审核解析，`status` 只能是 `approved` / `rejected` / `pending` |

版本常量：`DIFFICULTY_MODEL_VERSION`、`EXPLANATION_PROMPT_VERSION`、`EXPLANATION_PROVIDER`、`SIMILARITY_METHOD`。

```python
from examdata.core.db import init_db, session_scope
from examdata.governance import set_override, coverage
from examdata.intelligence import assign_taxonomy, estimate_all

init_db()
with session_scope() as session:
    assign_taxonomy(session, subject_code="0580")
    estimate_all(session, subject_code="0580")
    set_override(
        session,
        target_type="question",
        target_id=753,
        field_path="marks",
        value=2,
        author="ops",
        note="对照官方 Mark Scheme 修正",
    )
    print(coverage(session)["question"])
```

可修正的字段受 `OVERRIDABLE` 白名单约束，不在名单里的字段会抛 `OverrideError`。要查白名单：

```python
from examdata.governance import OVERRIDABLE
print(sorted(OVERRIDABLE))
```

`assign_taxonomy` 的 `replace=True` 只清 `source="auto"` 的旧标注，不动人工标注；`estimate_all` 只写 `source="estimated"` 的行，官方难度不受影响。

### 9.4 什么时候该走 CLI 或 HTTP

Python 入口最灵活，但也最需要你自己兜底：

- **session 生命周期由你负责**。查询函数不提交事务、不关连接，用错了会留下长事务或泄漏连接。图省事就用 `session_scope()`。
- **写操作没有二次确认**。CLI 的 `override-set` 有必填的 `--author`，Python 里 `author` 也是必填关键字参数，但没有任何东西阻止你在循环里批量写错数据。
- **没有版本稳定性承诺**。`examdata.query` 的函数签名是内部接口，跨版本可能变；HTTP 的 URL 与 CLI 的参数名相对更稳定。
- **同一进程内**才能用。跨机器、跨语言没有选择。

经验规则：

- 一次性操作、定时任务、需要留痕 → **CLI**。
- 跨机器、跨语言、给前端用 → **HTTP**（第 8 章）。
- 同机批处理、把结果喂给别的 Python 代码、需要复用 `Fetcher` 做限速友好的批量下载 → **Python**。

## 10 从本机调用远程服务

服务器上跑着 examdata，但只想让它监听 `127.0.0.1`（第 12 章的默认做法），而你人在自己的电脑上——这时候用 SSH 本地端口转发，不用动防火墙、不用证书、不用 nginx。

### 10.1 SSH 本地端口转发

在**你自己的电脑**上执行（不是服务器上）：

```bash
ssh -N -L 8000:127.0.0.1:8000 <用户名>@<服务器地址>
```

参数含义：

- `-N`：只做转发，不在服务器上开 shell。
- `-L 8000:127.0.0.1:8000`：把本机的 `8000` 端口转发到“从服务器视角看的”`127.0.0.1:8000`。右边那段的解析发生在**服务器侧**，所以它指向的正是服务器上那个只监听本机的服务。

命令会一直挂在前台，保持这个终端开着，然后在**另一个终端**里正常调用：

```bash
curl -s http://127.0.0.1:8000/health
```

想让它后台跑：

```bash
ssh -f -N -L 8000:127.0.0.1:8000 <用户名>@<服务器地址>
```

`-f` 让 ssh 转到后台。想关掉就 `pkill -f "ssh -f -N -L 8000"`，或者用 `ps` 找到进程号再 `kill`。

**本机 8000 被占用**时改左边的端口：

```bash
ssh -N -L 18000:127.0.0.1:8000 <用户名>@<服务器地址>
curl -s http://127.0.0.1:18000/health
```

如果服务器上的服务监听的不是 8000，右边跟着改：

```bash
ssh -N -L 8000:127.0.0.1:<服务端口> <用户名>@<服务器地址>
```

**放进 SSH 配置省事**。在 `~/.ssh/config` 里加：

```ini
Host examdata
    HostName <服务器地址>
    User <用户名>
    LocalForward 8000 127.0.0.1:8000
```

之后只需要 `ssh -N examdata`。

Windows 上同样可用：Windows 10 1809 以后自带的 OpenSSH 客户端支持这套语法，在 PowerShell 或 Git Bash 里直接敲上面的命令即可。

### 10.2 为什么这比直接暴露公网安全

- **服务端口从未暴露**。全程只有 SSH 端口（默认 22）对外开放，examdata 端口始终只在服务器回环地址上。
- **认证由 SSH 负责**。密钥、口令、双因素、登录审计都是 SSH 现成的，不用自己写。
- **传输加密由 SSH 负责**。不用申请证书，不用配 HTTPS。
- **撤权就是删密钥**。不用改任何服务配置。

代价是每个客户端都要有服务器账号，并且要在本机开一个常驻 ssh 进程。给少数几台机器、少数几个人用，这是性价比最高的方案。要给不受控的第三方用，或者要给浏览器页面用，就必须走第 12 章。

## 11 从内网其他机器调用

同一内网里有多台机器要调，SSH 隧道一个个开太麻烦，可以让服务直接监听内网地址。

### 11.1 只监听内网的写法

```bash
examdata serve --host 0.0.0.0 --port 8000
```

`0.0.0.0` 表示监听所有网卡，包括公网那张——**只有在机器本身不直接暴露公网时才可以这么用**。更稳妥的写法是只绑内网网卡：

```bash
examdata serve --host <内网网卡地址> --port 8000
```

`<内网网卡地址>` 换成服务器在局域网里的地址，例如 `10.0.0.12` 或 `192.168.1.12`。用 `ip addr`（Linux）或 `ipconfig`（Windows）查。

systemd 常驻时改单元里的 `ExecStart`（见 12.3 节）。

### 11.2 防火墙放行

**Ubuntu / Debian（ufw）**

```bash
sudo ufw allow from <内网网段> to any port 8000 proto tcp
```

`<内网网段>` 写成 CIDR，例如 `10.0.0.0/24` 或 `192.168.1.0/24`。不要用 `ufw allow 8000`——那是对全网开放。

**CentOS / RHEL / Rocky（firewalld）**

```bash
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<内网网段>" port port="8000" protocol="tcp" accept'
sudo firewall-cmd --reload
```

**Windows**

```powershell
New-NetFirewallRule -DisplayName "examdata 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress <内网网段> -Action Allow
```

`New-NetFirewallRule` 必须在**以管理员身份运行**的 PowerShell 里执行，普通窗口会报权限不足。

以上都是模板，按你的环境改占位符。

### 11.3 风险

**服务本身没有任何鉴权**（第 8.2 节）。能连上 8000 端口的人就能读走全部数据、调用全部路由，包括触发 `/paper-qa/*` 让服务器去访问外网。

所以：

- 防火墙规则里**必须**带来源限制。只放行需要访问的网段，不要图省事放行全网。
- 不要在有公网 IP 的机器上用 `--host 0.0.0.0`，除非前面还有一层带访问控制的 nginx（第 12 章）。
- 内网也不等于可信。同一个办公网里的访客设备、被入侵的测试机，都能连上来。敏感数据要么别放，要么加第 12.7 节的访问控制。

## 12 从公网调用 生产部署

这一章把服务放到一台有公网域名的服务器上，开机自启、崩溃自重启、带 HTTPS。以下内容中的 nginx、systemd、HTTPS、防火墙部分属于通用运维写法，**不含项目专有配置**，请把 `<尖括号占位符>` 换成你自己的值后再使用。

本章的 systemd / nginx / certbot / 防火墙配置是按通用最佳实践给出的**模板**，未在真机逐条验证；占位符请按你的环境替换，上线前用 `nginx -t`、`systemctl status` 自行确认。

### 12.1 先读安全警告

在动手之前，必须清楚三件事：

1. **examdata 的 HTTP API 没有任何鉴权**。没有 token、没有 API key、没有登录。只要能把 HTTP 请求发到端口上，就能读走全库数据，并让服务器替你访问外网（`/paper-qa/*`）。
2. **数据库里是受版权保护的真题内容**。Cambridge 与 Pearson 的试卷、评分标准、题目图片都有版权，且 Pearson 的部分资源属于 `secure-content`（非公开）。把它原样挂到公网，等于把版权风险转嫁给你的服务器和域名。
3. **它没有为公网做加固**。没有限流、没有 CORS 白名单、没有请求体大小限制（因为不接受请求体），未捕获异常会返回纯文本 500。

因此本节的推荐架构是：

```text
客户端  ->  HTTPS(443)  ->  nginx  ->  HTTP(127.0.0.1:8000)  ->  examdata
                              ^
                              |
                        访问控制放在这里
```

**examdata 永远只监听 `127.0.0.1`，由 nginx 对外**。访问控制、TLS、限流、日志全在 nginx 这一层做，不需要改 examdata 的代码。

如果你的使用场景不要求公网（少数几台机器、少数几个人），第 10 章的 SSH 隧道更简单也更安全，不需要读本章剩下的内容。

### 12.2 创建系统用户与目录

约定：代码放 `/srv/examdata`，数据放 `/var/lib/examdata`，服务以专用系统账号 `examdata` 运行。

```bash
sudo useradd --system --home /srv/examdata --shell /usr/sbin/nologin examdata
sudo mkdir -p /srv/examdata /var/lib/examdata
sudo chown -R examdata:examdata /srv/examdata /var/lib/examdata
```

`--system` 表示系统账号（不设密码、不建家目录），`--shell /usr/sbin/nologin` 表示不允许登录。这个账号只用来跑服务。

把代码放进去（在服务器上执行，用 `examdata` 身份安装依赖）：

```bash
sudo -u examdata git clone <仓库地址> /srv/examdata
cd /srv/examdata
sudo -u examdata python3 -m venv .venv
sudo -u examdata .venv/bin/pip install --upgrade pip
sudo -u examdata .venv/bin/pip install .
```

服务器上用 `pip install .`（普通安装），不要用 `pip install -e ".[dev]"`——后者是本地开发用的，会把测试依赖也装上。

把数据搬过来（在**你的开发机**上执行，把 `.data/` 整体同步过去）：

```bash
rsync -av --progress .data/ <用户名>@<服务器地址>:/tmp/examdata-data/
```

然后在服务器上：

```bash
sudo rsync -a /tmp/examdata-data/ /var/lib/examdata/
sudo chown -R examdata:examdata /var/lib/examdata
rm -rf /tmp/examdata-data
```

`.data/` 里包含数据库、内容寻址存储（`artifacts/`）与样本文件，必须整体搬，不能只搬 `.db` 文件——数据库里的资产记录指向 `artifacts/` 里的实际文件，只搬一半会导致 `/assets/{id}` 返回 410。

以服务账号验证一次：

```bash
sudo -u examdata env \
  EXAMDATA_DATA_DIR=/var/lib/examdata \
  EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db \
  /srv/examdata/.venv/bin/examdata db-stats
```

注意 `sqlite:////var/lib/examdata/examdata.db` 里是**四个斜杠**：`sqlite://` 是协议前缀，后面跟的 `/var/...` 是绝对路径。写成三个斜杠会被当成相对路径 `var/...`，服务会在错误的位置建一个空库。

`db-stats` 能打出表就说明权限和路径都对。

### 12.3 systemd 常驻单元

新建 `/etc/systemd/system/examdata.service`：

```ini
[Unit]
Description=examdata 只读检索 API
Documentation=file:///srv/examdata/docs/DEPLOY.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=examdata
Group=examdata
WorkingDirectory=/srv/examdata
Environment=EXAMDATA_DATA_DIR=/var/lib/examdata
Environment=EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db
Environment="EXAMDATA_USER_AGENT=ExamDataBot/0.1 (+https://<你的域名>/examdata; contact=<你的邮箱>)"
Environment=PYTHONUNBUFFERED=1
ExecStart=/srv/examdata/.venv/bin/examdata serve --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

逐项说明：

- **`WorkingDirectory=/srv/examdata`**：`.env` 文件是按当前工作目录找的，`data_dir` 的默认值也是相对路径。固定工作目录能消除这类歧义。
- **`Environment=` 显式列出变量**：`EXAMDATA_DATA_DIR` 与 `EXAMDATA_DATABASE_URL` 必须**成对设置**。只设 `data_dir` 的话，`database_url` 的默认值 `sqlite:///.data/examdata.db` 仍会解析到工作目录下的 `.data/`，数据库和 artifacts 就分家了。
- **`EXAMDATA_USER_AGENT` 请务必改成你自己的联系方式**。默认值里的 `example.invalid` 是占位符，拿它去抓上游站点既不礼貌也不专业。这个值含空格，**必须**像上面那样整体加双引号；否则 systemd 会按空白拆词、逐词校验，非法词只记一条 `Invalid environment assignment, ignoring` 警告后跳过——UA 被截成 `ExamDataBot/0.1`，联系方式静默丢失，而服务照常启动。
- **`Restart=on-failure` + `RestartSec=3`**：崩溃后 3 秒重启。`on-failure` 而不是 `always`，这样手动 `systemctl stop` 不会被自动拉起来。
- **`ProtectSystem=full`**：把 `/usr`、`/boot`、`/etc` 挂成只读，但 `/srv` 与 `/var` 保持可写——代码和数据正好都在可写区，不需要额外的 `ReadWritePaths`。
- **`ProtectHome=true`**：隐藏 `/home`、`/root`、`/run/user`。
- **`PrivateTmp=true`**：独立的 `/tmp`，避免临时文件互相干扰。
- **日志**：没有 `StandardOutput=` 配置，默认进 journald，用 `journalctl -u examdata` 看。

变量多了之后 `Environment=` 会很长，也可以改用环境文件：

```ini
EnvironmentFile=/etc/examdata.env
```

`/etc/examdata.env` 内容（注意 systemd 的环境文件**不要**加 `export`，也不要加引号包裹整个值）：

```ini
EXAMDATA_DATA_DIR=/var/lib/examdata
EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db
EXAMDATA_USER_AGENT=ExamDataBot/0.1 (+https://<你的域名>/examdata; contact=<你的邮箱>)
```

文件权限设成 `chmod 640`、属主 `root:examdata`，避免被其他账号读取。

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now examdata
sudo systemctl status examdata
sudo journalctl -u examdata -n 50 --no-pager
```

状态应该是 `active (running)`，日志里能看到 `API 文档 http://127.0.0.1:8000/docs`。

验证服务确实只监听回环：

```bash
sudo ss -ltnp | grep 8000
```

应该显示 `127.0.0.1:8000`，而不是 `0.0.0.0:8000` 或 `[::]:8000`。

常用操作：

```bash
sudo systemctl restart examdata   # 改完配置重启
sudo systemctl stop examdata      # 停
sudo systemctl disable examdata   # 取消开机自启
```

### 12.4 nginx 反向代理

先装 nginx：

```bash
sudo apt update && sudo apt install -y nginx      # Debian / Ubuntu
sudo dnf install -y nginx                          # RHEL / Rocky / Alma
```

新建 `/etc/nginx/sites-available/examdata`（RHEL 系是 `/etc/nginx/conf.d/examdata.conf`，内容相同）：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name <你的域名>;

    access_log /var/log/nginx/examdata.access.log;
    error_log  /var/log/nginx/examdata.error.log;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";

        # /paper-qa/query 要从上游下载整份 PDF，再加上 robots 抓取与按主机限速，
        # 很容易超过 nginx 默认的 60 秒 proxy_read_timeout 而变成 504。
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;

        # 让二进制字节直接透传，而不是先缓冲到临时文件再发给客户端。
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
```

**为什么必须调这两个参数**

- `proxy_read_timeout 300s`：nginx 默认只等上游 60 秒。`/paper-qa/query` 在服务端要先解析清单、再受“每主机至少 1.0 秒 + 0~0.5 秒抖动”的限速约束去下载文件，慢的时候远超 60 秒。不调这个值，客户端看到的是 nginx 的 504，而不是服务返回的真实错误。
- `proxy_buffering off`：默认 nginx 会把上游响应完整缓冲到磁盘临时文件再转发。PDF 与 ZIP 是二进制大对象，缓冲既浪费磁盘又增加首字节延迟。关掉之后字节直接透传。

其它说明：

- **不需要配 CORS**。浏览器访问的是 `https://<你的域名>`，API 在同一域名下，属于同源请求。
- **不需要配 `client_max_body_size`**。所有路由都不接受请求体。
- **`proxy_set_header Connection ""`**：清空这个头，避免上游连接被意外关闭，配合 `proxy_http_version 1.1` 使用。
- **`Host` 转发**：uvicorn 默认信任来自 `127.0.0.1` 的 `X-Forwarded-*` 头，所以访问日志里记录的会是真实客户端 IP 而不是 nginx 的地址。

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/examdata /etc/nginx/sites-enabled/examdata
sudo nginx -t
sudo systemctl reload nginx
```

`nginx -t` 必须输出 `syntax is ok` 与 `test is successful` 才能 reload。

此时用域名访问 `http://<你的域名>/health` 应该能拿到 `{"status":"ok","papers":...}`。

### 12.5 HTTPS 证书

用 Let's Encrypt 的 certbot，它会自动改写上面的 nginx 配置、加上 443 监听与证书路径。

```bash
sudo apt install -y certbot python3-certbot-nginx    # Debian / Ubuntu
sudo dnf install -y certbot python3-certbot-nginx    # RHEL 系
```

签发（把占位符换掉）：

```bash
sudo certbot --nginx -d <你的域名>
```

certbot 会问你要不要自动把 HTTP 跳转到 HTTPS，选是。

想连 `www.<你的域名>` 一起签，得先在 §12.4 的 nginx 配置里把它写进 `server_name`（`server_name <你的域名> www.<你的域名>;`），然后这里再加一个 `-d www.<你的域名>`——certbot 只为你 nginx 里已声明的域名签发，两边对不上会失败。

验证自动续期：

```bash
sudo certbot renew --dry-run
```

dry-run 成功说明续期链路可用。certbot 安装时会自动注册 systemd timer 或 cron 任务，一般不需要手动加。

完成后检查：

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<你的域名>/health
```

应该返回 `200`。（不要用 `curl -sI`：业务路由不接受 `HEAD`，只会拿到 405。）

**如果域名在国内且无法签发 Let's Encrypt 证书**，改用商业证书或云厂商的免费证书，把证书文件路径写进 nginx 的 `ssl_certificate` / `ssl_certificate_key` 即可——这两行就是 certbot 自动写入的内容。

### 12.6 防火墙

只放行 22（SSH）、80、443，**不要放行 8000**。

**Ubuntu / Debian（ufw）**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

**CentOS / RHEL / Rocky（firewalld）**

```bash
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
sudo firewall-cmd --list-all
```

**验证 8000 没有暴露**（从另一台机器执行）：

```bash
curl -m 5 http://<服务器公网地址>:8000/health
```

应当连接超时或拒绝。如果拿到了 `{"status":"ok",...}`，说明服务监听在了 `0.0.0.0` 或防火墙没生效，必须回去修——这时任何人都能绕过 nginx 直接读你的库。

**云服务器还要看安全组**。阿里云、腾讯云、AWS、Azure 等平台的实例除了系统防火墙，还有一层云平台的安全组。两边都要只放行 22/80/443。

### 12.7 访问控制三选一

nginx 已经就位，访问控制在这一层加。按使用场景选一种：

**方案一：HTTP Basic 认证**

适合“少数几个固定的人用，每人一个账号”。

```bash
sudo apt install -y apache2-utils      # Debian/Ubuntu：提供 htpasswd
# RHEL/CentOS/Rocky：sudo dnf install -y httpd-tools
sudo htpasswd -c /etc/nginx/.htpasswd <用户名>
```

会提示输入密码。再加账号时**不要**加 `-c`（`-c` 会覆盖整个文件）：

```bash
sudo htpasswd /etc/nginx/.htpasswd <另一个用户名>
```

在 `location /` 里加两行：

```nginx
        auth_basic           "examdata";
        auth_basic_user_file /etc/nginx/.htpasswd;
```

`sudo nginx -t && sudo systemctl reload nginx` 生效。

调用方式：

```bash
curl -u <用户名>:<密码> https://<你的域名>/health
```

浏览器访问 `/docs` 时会弹原生登录框，填完就能用 Swagger UI。

**方案二：来源 IP 白名单**

适合“只有公司网络或固定几台机器要访问”。

```nginx
        allow <你的固定IP>;
        allow <另一个IP或网段>;
        deny all;
```

放在 `location /` 内部。网段写成 CIDR，例如 `allow 203.0.113.0/24;`。改完同样 `nginx -t` + `reload`。

被拒的请求返回 403，不会到达 examdata。

**方案三：完全不暴露，走 SSH 隧道**

服务保持只监听 `127.0.0.1`，nginx 只用来提供 HTTPS 也可以干脆不要。用户通过第 10 章的 `ssh -L` 访问。

```bash
ssh -N -L 8000:127.0.0.1:8000 <用户名>@<服务器地址>
```

这是三种里最安全的：攻击面只剩 SSH，认证与审计都是 SSH 现成的。代价是每个用户都要有服务器账号，且不能在浏览器里直接用（除非本地再起一个转发）。

**三种可以叠加**。例如：Basic 认证 + IP 白名单，只有白名单来源能连、且仍需密码。

### 12.8 部署验收清单

逐条打勾，全部通过才算部署完成。

**服务层**

- [ ] `systemctl status examdata` 是 `active (running)`
- [ ] `sudo ss -ltnp | grep 8000` 显示的是 `127.0.0.1:8000`
- [ ] `curl -s http://127.0.0.1:8000/health` 在服务器本机返回 `{"status":"ok","papers":<非0>}`
- [ ] `sudo systemctl restart examdata` 后服务能在 10 秒内恢复

**数据层**

- [ ] `sudo -u examdata env EXAMDATA_DATA_DIR=/var/lib/examdata EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db /srv/examdata/.venv/bin/examdata db-stats` 能打出非空的表
- [ ] `curl -s 'http://127.0.0.1:8000/questions?limit=1'` 的 `total` 大于 0
- [ ] 至少取一个资产成功：`curl -o /tmp/a.png http://127.0.0.1:8000/assets/<一个存在的id>` 返回 200 且文件非空
- [ ] `curl -s http://127.0.0.1:8000/provenance/coverage` 的 `complete` 是 `true`

**网络层**

- [ ] `https://<你的域名>/health` 返回 200
- [ ] `http://<你的域名>/health` 会跳转到 HTTPS（如果启用了跳转）
- [ ] 从外部机器 `curl -m 5 http://<服务器公网地址>:8000/health` 失败
- [ ] 云平台安全组只放行了 22/80/443

**安全层**

- [ ] 访问控制方案已生效：未带凭据 / 不在白名单的请求被拒（403 或 401）
- [ ] `EXAMDATA_USER_AGENT` 里的联系方式已经换成你自己的
- [ ] `certbot renew --dry-run` 成功

**功能层**

- [ ] `https://<你的域名>/docs` 能打开
- [ ] 三条实测示例能跑通（见 8.5 节）
- [ ] 如果要用 `/paper-qa/*`，服务器能出网：`curl -s -o /dev/null -w '%{http_code}\n' https://cie.fraft.cn/` 有响应

## 13 配置项完整参考

所有配置集中在 `src/examdata/core/config.py` 的 `Settings` 类，环境变量前缀统一是 `EXAMDATA_`。

### 13.1 全部配置项

| 环境变量 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `EXAMDATA_DATA_DIR` | Path | `.data` | 数据根目录，相对路径按当前工作目录解析 |
| `EXAMDATA_DATABASE_URL` | str | `sqlite:///.data/examdata.db` | 数据库连接串 |
| `EXAMDATA_USER_AGENT` | str | `ExamDataBot/0.1 (+https://example.invalid/examdata; contact=ops@example.invalid)` | 抓取时发送的 User-Agent，**请务必改掉** |
| `EXAMDATA_REQUEST_TIMEOUT_SECONDS` | float | `30.0` | 单次 HTTP 请求超时（秒） |
| `EXAMDATA_MAX_RETRIES` | int | `3` | 请求失败时的**总尝试次数**（不是重试次数） |
| `EXAMDATA_RETRY_BACKOFF_SECONDS` | float | `2.0` | 重试退避基数（秒） |
| `EXAMDATA_MIN_HOST_INTERVAL_SECONDS` | float | `1.0` | 同一主机两次请求的最小间隔（秒） |
| `EXAMDATA_HOST_INTERVAL_JITTER_SECONDS` | float | `0.5` | 间隔抖动上限（秒） |
| `EXAMDATA_RESPECT_ROBOTS` | bool | `true` | 是否遵守 robots.txt |
| `EXAMDATA_MAX_CONCURRENCY` | int | `4` | **当前版本不生效**，见下方说明 |
| `EXAMDATA_PARSER_VERSION` | str | `0.1.0` | 解析器版本，派生数据重建的关键 |

逐项补充：

- **`EXAMDATA_DATABASE_URL`**：默认的 `sqlite:///.data/examdata.db` 是**相对路径**（三个斜杠 + 相对路径）。绝对路径要写**四个斜杠**：`sqlite:////var/lib/examdata/examdata.db`。代码层面也支持 PostgreSQL（`postgresql+psycopg://...`），但本仓库的部署脚本与文档都按 SQLite 写的，换库请自行验证。
- **`EXAMDATA_MAX_RETRIES=3`** 表示最多尝试 3 次（首次 + 2 次重试），不是“重试 3 次”。
- **退避算法**是 `retry_backoff_seconds * 2**attempt`，默认值下依次是 2 秒、4 秒、8 秒。
- **`EXAMDATA_MAX_CONCURRENCY` 是死配置**。默认 4，但当前版本的抓取路径是同步串行的，全仓库没有任何地方读这个值。调大它不会让 `sync` 变快，调小也不会变慢。抓取速度实际由 `MIN_HOST_INTERVAL_SECONDS` 与 `HOST_INTERVAL_JITTER_SECONDS` 决定。
- **`EXAMDATA_RESPECT_ROBOTS=false` 只影响本地行为**。关掉它只是不检查 robots.txt，不会改变限速。不建议关。

**不能通过环境变量设置的派生路径**（它们是 `Settings` 的属性，由 `data_dir` 推导）：

| 属性 | 值 |
|---|---|
| `artifacts_dir` | `<data_dir>/artifacts`，内容寻址存储 |
| `assets_dir` | `<data_dir>/assets` |
| `raw_pages_dir` | `<data_dir>/raw_pages`，原始 HTML 快照 |

要改这些位置，只能改 `EXAMDATA_DATA_DIR`。

**settings 在进程内只读一次**。`get_settings()` 带 `lru_cache(maxsize=1)`，进程启动后第一次调用时构造并缓存。改环境变量必须重启进程（systemd 下 `systemctl restart examdata`）。

**构造时会自动建目录**。`get_settings()` 内部调用 `ensure_dirs()`，会创建 `data_dir`、`artifacts/`、`assets/`、`raw_pages/` 四个目录。所以服务账号需要对 `data_dir` 有写权限，即使只是跑只读命令。

### 13.2 .env 文件与优先级

`Settings` 配置了 `env_file=".env"`，也就是**当前工作目录**下的 `.env` 文件（不是仓库根目录，也不是配置文件所在目录）。`.env` 写法：

```ini
EXAMDATA_DATA_DIR=/var/lib/examdata
EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db
EXAMDATA_USER_AGENT=ExamDataBot/0.1 (+https://<你的域名>/examdata; contact=<你的邮箱>)
EXAMDATA_MIN_HOST_INTERVAL_SECONDS=1.5
```

**优先级从高到低**：

1. 显式构造参数（`Settings(data_dir=...)`，只在代码里用）
2. 环境变量
3. 当前工作目录下的 `.env`
4. 代码默认值

也就是说 `.env` 会被同名的环境变量覆盖。systemd 用 `Environment=` 设了值，`.env` 里同名的项就不起作用——排查配置不生效时先看这个。

**未知变量被忽略**。`Settings` 配了 `extra="ignore"`，带 `EXAMDATA_` 前缀但不认识的变量不会报错，会被静默丢弃。所以拼错变量名不会有任何提示，配置“没生效”往往就是这个原因。改完配置记得 `systemctl restart` 再用 `db-stats` 验证。

**仓库里没有任何 `.env` 文件**。需要就自己建，并且不要把带密钥或内部地址的 `.env` 提交进版本库。

## 14 运维手册

### 14.1 日志

systemd 部署下，服务的 stdout / stderr 全部进 journald。

```bash
sudo journalctl -u examdata -f                  # 实时跟踪
sudo journalctl -u examdata -n 200 --no-pager   # 最近 200 行
sudo journalctl -u examdata --since "1 hour ago"
sudo journalctl -u examdata --since today | grep -i error
```

服务自己会打印启动横幅与每条 uvicorn 访问日志。正常的一条访问日志形如：

```text
INFO:     127.0.0.1:54321 - "GET /questions?limit=5 HTTP/1.1" 200 OK
```

因为 uvicorn 默认信任来自 `127.0.0.1` 的 `X-Forwarded-*` 头，经 nginx 转发后这里记录的是**真实客户端 IP**，不是 nginx 的地址。

**控制日志量**。默认每个请求一行访问日志，流量大时 journald 会吃掉不少磁盘。限制 journald 总量：

```bash
sudo journalctl --vacuum-size=500M      # 立即裁剪到 500M
```

长期限制改 `/etc/systemd/journald.conf` 里的 `SystemMaxUse=500M`，然后 `sudo systemctl restart systemd-journald`。

**关掉访问日志**。`examdata serve` 不暴露日志开关。要去掉访问日志，只能用 uvicorn 直启并加参数（见 6.4 节）：

```bash
.venv/bin/uvicorn examdata.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

**前台运行时**（第 6.1 节）日志直接打在终端上，Ctrl+C 停。

### 14.2 备份

需要备份的只有两样东西：

| 路径 | 内容 | 参考体积 |
|---|---|---|
| `/var/lib/examdata/examdata.db` | SQLite 数据库 | 约 4 MB |
| `/var/lib/examdata/artifacts/` | 内容寻址存储的原始文件 | 约 38 MB |

`samples/`、`discovery.json`、`discovery.log`、`syllabuses.json` 是采集过程的中间产物，服务运行不需要，丢了可以重新生成。`assets/` 与 `raw_pages/` 在本项目的实际数据里是空的。

**顺序很重要：先同步 `artifacts/`，再备份数据库。**

理由是 `artifacts/` 是**只增不改**的。内容寻址存储的写入逻辑是“文件已存在就跳过”，文件名就是内容的 sha256，所以同一个路径的内容永远不会变。这意味着：

- 先 rsync `artifacts/`，期间可能多同步了一些数据库还没引用的新文件——无害，多余的文件不影响一致性。
- 再对数据库做一次一致性快照。此时数据库引用的每个 sha256 文件都已经在备份目录里了。
- 反过来先备份数据库再同步 artifacts，会出现“快照里的数据库引用了尚未同步的文件”的窗口期，恢复出来就是 `/assets/{id}` 返回 410。

**备份 artifacts**（增量，首次会慢，之后只传新增文件）：

```bash
sudo mkdir -p /var/backups/examdata
sudo chown examdata:examdata /var/backups/examdata
sudo rsync -a --info=progress2 /var/lib/examdata/artifacts/ /var/backups/examdata/artifacts/
```

`chown` 这一行不能省：`sudo mkdir` 建出来的目录属主是 `root`，而下面两步数据库备份都以 `examdata` 身份写入，目录不可写会直接报 `unable to open database file`。让 `examdata` 拥有备份目录，后续 rsync 与 sqlite 都不再需要 `sudo`。

**备份数据库**（在线一致性备份，服务不用停）。有 `sqlite3` 命令行时：

```bash
sudo -u examdata sqlite3 /var/lib/examdata/examdata.db ".backup '/var/backups/examdata/examdata-$(date +%F).db'"
```

没装 `sqlite3` 就用 Python（venv 里一定有）：

```bash
sudo -u examdata /srv/examdata/.venv/bin/python - <<'PY'
import datetime, sqlite3
src = sqlite3.connect("/var/lib/examdata/examdata.db")
dst = sqlite3.connect(f"/var/backups/examdata/examdata-{datetime.date.today():%F}.db")
src.backup(dst)
dst.close()
src.close()
PY
```

**不要直接 `cp` 数据库文件**。SQLite 在写入过程中直接复制会拿到损坏或不一致的副本；`.backup` 与 `Connection.backup()` 走的是 SQLite 官方的在线备份协议。

**恢复**：

```bash
sudo systemctl stop examdata
sudo rsync -a /var/backups/examdata/artifacts/ /var/lib/examdata/artifacts/
sudo rm -f /var/lib/examdata/examdata.db-wal /var/lib/examdata/examdata.db-shm
sudo cp /var/backups/examdata/examdata-<日期>.db /var/lib/examdata/examdata.db
sudo chown -R examdata:examdata /var/lib/examdata
sudo systemctl start examdata
curl -s http://127.0.0.1:8000/health
```

`rm -f` 这一行同样不能省。SQLite 在 WAL 模式下，主库文件旁边还有 `-wal`（未合并的事务日志）和 `-shm`（共享内存索引）。如果直接覆盖主库文件而留下旧的 `-wal`，SQLite 下次打开时会尝试把旧日志应用到新库上——两份不匹配的状态拼在一起，轻则报 `database disk image is malformed`，重则把恢复出来的数据又改坏。先删干净这两个伴随文件，再拷主库，才是干净恢复。

**定时备份**用 cron 或 systemd timer，脚本里按上面的顺序做两件事即可。保留策略自定，数据库是单文件，用 `find /var/backups/examdata -name 'examdata-*.db' -mtime +30 -delete` 之类的规则清理。

**验证备份可用**。备份完至少验一次：

```bash
sqlite3 /var/backups/examdata/examdata-<日期>.db "select count(*) from question;"
```

能打出数字才算备份成功。只看文件大小不够——损坏的 SQLite 文件大小也正常。

### 14.3 升级代码

```bash
cd /srv/examdata
sudo -u examdata git pull
sudo -u examdata .venv/bin/pip install .
sudo systemctl restart examdata
sudo systemctl status examdata
sudo journalctl -u examdata -n 30 --no-pager
```

**升级前先备份**（14.2 节）。数据库 schema 由 `init_db()` 在启动时用 `CREATE TABLE IF NOT EXISTS` 补齐，不会删表，但跨版本升级仍建议留一份备份。

**升级后检查是否需要重算派生数据**。如果新版改了 `parser_version`（见第 13 章），旧解析结果不会自动重算——它们记录的是旧版本号。需要时按 14.4 节的顺序重建。

**回滚**：

```bash
cd /srv/examdata
sudo -u examdata git checkout <上一个版本号或 tag>
sudo -u examdata .venv/bin/pip install .
sudo systemctl restart examdata
```

如果新版改了数据库结构，回滚代码的同时还要按 14.2 节恢复数据库。

### 14.4 重新同步与重建派生数据

完整链路（README 里的那条序列）：

```bash
examdata initdb
examdata sync --adapter cambridge
examdata parse-docs
examdata enrich
examdata provenance-rebuild
examdata db-stats
```

每一步做什么、能不能跳过：

| 步骤 | 作用 | 能否单独重跑 |
|---|---|---|
| `initdb` | 建表，幂等 | 能，随时 |
| `sync` | 发现新资源、去重、下载、版本化、落库 | 能，重复运行不会重复下载（用 ETag / If-Modified-Since 判断） |
| `parse-docs` | 解析 `parse_status=pending` 的版本，写题目与评分条目 | 能，只处理待解析的 |
| `enrich` | 知识点 -> 难度 -> 相似题 -> 生成解析 | 能，幂等 |
| `provenance-rebuild` | 重建溯源边，纯投影、幂等 | 能，随时 |

**派生数据必须按依赖顺序重建**。顺序是：知识点标注 -> 难度估计 -> 相似题 -> 生成解析。`enrich` 一次把四步按序做完，单独跑其中一个子命令（如 `similarity-find`）不会自动补上游。跳过上游的后果是**静默缺失**——不会报错，只是查不到数据。

**重新解析的三个已知坑**：

1. **人工修正可能对不上号**。人工修正记录挂在题目的主键上，重新解析会重建题目行、主键随之变化。系统会按自然键 `(document_id, number_path)` 尝试重映射；映射不上的会记成冲突、进入待检查队列，并**保留人工值不丢**。处理方式：
   ```bash
   examdata override-list --conflicts
   examdata review-list --status open
   ```
2. **派生数据不会自动跟着重建**。重解析后必须重新跑一遍 `enrich`，否则知识点、难度、相似题、解析全是空的。
3. **评分条目的关联会丢**。题目重建后，评分条目与题目的关联需要重新建立，`parse-docs` 会尝试重连；没连上的同样进待检查队列。

**只重解析某一份文档**：

```bash
examdata reparse --document-id <文档id>
```

`reparse` 不重新下载，只读本地内容寻址存储里的原件，然后用当前算法重建，并输出新旧对比。

**破坏性重置（最后手段）**。`scripts/reset_derived.py` 会清空 15 张派生表（`question_asset`、`official_answer`、`generated_explanation`、`mark_scheme_entry`、`formula`、`question_taxonomy`、`difficulty`、`question_similarity`、`asset`、`question`、`mark_scheme`、`paper`、`validation_finding`、`review_task`、`parse_run`），把 `document_revision.parse_status` 重置成 `pending`、`document.status` 重置成 `stored`：

```bash
python scripts/reset_derived.py
examdata parse-docs
examdata enrich
examdata provenance-rebuild
```

**这会清空全部派生数据**，包括人工修正关联的基线。执行前必须备份。脚本里的数据库路径是硬编码的 `.data/examdata.db`，所以在服务器上跑之前要先 `cd` 到 `/srv/examdata` 并确认 `EXAMDATA_*` 环境变量指向正确的库——更稳妥的做法是先在开发机上验证。

**核对不变量**：

```bash
python scripts/verify_state.py
```

它会端到端核对一致性（内部会调用 `provenance.rebuild()`，所以不是只读脚本）。

## 15 故障排查

按症状查表。每条都给出“怎么确认”和“怎么处理”。

### 15.1 服务与网络

| 症状 | 可能原因 | 确认与处理 |
|---|---|---|
| 启动报 `Address already in use` | 8000 端口被占用 | `sudo ss -ltnp \| grep 8000` 找出占用进程，或换端口 `--port 8080` |
| 浏览器连不上，`curl` 超时 | 服务只监听 `127.0.0.1`，你却从别的机器访问 | 在服务器本机 `curl 127.0.0.1:8000/health` 验证服务本身；远程访问按第 10 或 11 章处理 |
| 从外部能直接访问 8000 | 监听在了 `0.0.0.0`，或防火墙没生效 | `sudo ss -ltnp \| grep 8000` 应显示 `127.0.0.1:8000`；按 12.6 节修防火墙 |
| 经 nginx 访问返回 502 | nginx 连不上上游 | `sudo systemctl status examdata`；`curl 127.0.0.1:8000/health` 确认服务活着；检查 nginx 的 `proxy_pass` 地址与端口 |
| 经 nginx 访问返回 504 | 请求超过 `proxy_read_timeout` | 通常是 `/paper-qa/*`。按 12.4 节把 `proxy_read_timeout` 调到 300s |
| 浏览器跨域请求被挡 | 服务没有 CORS 头 | 把前端页面放到同域名下，或在 nginx 里自己加 CORS 头（见 8.2 节） |
| `curl -I` 返回 405 | 路由不接受 `HEAD` | 改用 `curl -s -o /dev/null -w '%{http_code}\n'` |

### 15.2 数据

| 症状 | 可能原因 | 确认与处理 |
|---|---|---|
| `/health` 返回 `{"status":"ok","papers":0}` | 库是空的，数据没准备 | 见第 5 章。确认 `EXAMDATA_DATA_DIR` 与 `EXAMDATA_DATABASE_URL` 指向有数据的库 |
| 启动报 `unable to open database file` | 路径不对或服务账号没有写权限 | `sqlite:///` 后面跟绝对路径要写成**四个斜杠**；确认 `chown -R examdata:examdata /var/lib/examdata` |
| 数据库写到了意想不到的位置 | 只设了 `EXAMDATA_DATA_DIR`，没设 `EXAMDATA_DATABASE_URL` | 两者必须成对设置，否则 `database_url` 的默认相对路径会落在工作目录下（见 12.3 节） |
| `/assets/{id}` 返回 410 `资产文件已丢失` | 数据库搬了但 `artifacts/` 没搬全 | 按 5.2 节重新同步整个 `.data/`；确认 `artifacts_dir` 指向正确位置 |
| `/questions` 的 `total` 是 0 但 `papers` 不为 0 | 还没跑解析 | `examdata parse-docs`，然后 `examdata db-stats` 确认题目数 |
| 查得到题但知识点/难度/相似题都是空 | 还没跑智能层，或重解析后没重建 | `examdata enrich --subject <科目>` |
| `/provenance/coverage` 的 `complete` 是 false | 有派生数据追不到来源 | `examdata provenance-rebuild`，再查一次 |
| 改完配置没生效 | `.env` 被环境变量覆盖，或变量名拼错被静默忽略 | 见 13.2 节。确认后 `systemctl restart examdata` |

### 15.3 CLI 与 API 调用

| 症状 | 可能原因 | 确认与处理 |
|---|---|---|
| `--leaves-only` / `--marks-target` 报 unknown option | 旧版 README 曾把参数名误写成这样 | CLI 里真实参数是 `--leaves` 和 `--marks`；HTTP 里是 `leaves_only` 和 `marks_target`。仓库里的 README 已修正 |
| 422 且 `detail` 是数组 | FastAPI 参数校验失败 | 数组里的 `loc` 字段直接指出是哪个参数错了，照着改 |
| 422 且 `detail` 是字符串 | 业务校验失败 | 例如 `/sample` 没给 `count` 或 `marks_target`、`format` 不是 `binary`/`json` |
| `/paper-qa/*` 返回 502 | 服务器不能出网 | `curl -s -o /dev/null -w '%{http_code}\n' https://cie.fraft.cn/` 验证；检查代理与 DNS |
| `/paper-qa/*` 返回 422 `Unsupported season for this board` | 季节写法不对 | CIE 只认 `Mar` / `Jun` / `Nov`，**没有 `Jan`**；Edexcel 用 `January` / `June` / `October` / `November` |
| `/paper-qa/*` 返回 409 | 命中多份候选文件 | 补上 `--paper`（或 HTTP 的 `paper` 参数）把范围收窄 |
| `/paper-qa/*` 返回 403 | 命中了非公开资源 | 该资源属于 Pearson 的 `secure-content`，无公开访问权限 |
| `/paper-qa/query` 很慢 | 上游限速 + 每次调用新建抓取器 | 属正常现象。批量取文件用 Python 复用 `Fetcher`（见 9.1 节） |
| 返回纯文本 `Internal Server Error` | 未捕获异常，不是 JSON | 看 `journalctl -u examdata` 里的堆栈 |
| `--out` 指定的目录里已有同名文件 | 输出用独占创建，不覆盖 | 清空目标目录或换一个目录（见 9.1 节） |

### 15.4 同步与解析

| 症状 | 可能原因 | 确认与处理 |
|---|---|---|
| `sync` 很慢 | 按主机限速，每主机至少 1.0 秒 + 0~0.5 秒抖动 | 属正常。先用 `--resources 5` 小批量验证，别一上来就跑全量 |
| 调大 `EXAMDATA_MAX_CONCURRENCY` 没变快 | 这个配置当前版本不生效 | 抓取是同步串行的（见 13.1 节），速度只由限速参数决定 |
| `sync --adapter edexcel` 报错、切不动分片 | Pearson 的 `hitsPerPage` 有硬上限 1000 | 撞上限时递归分片；切不动会显式报错而不是静默漏数据，按报错里的提示缩小范围 |
| Edexcel 资源被判成公开 | `gating` 字段恒为 false，不能用来判断 | 用 URL 前缀判定公开性，不要读这个字段 |
| 重解析后人工修正丢了 | 题目主键变了 | `examdata override-list --conflicts` 查看冲突项；人工值被保留，只是映射不上（见 14.4 节） |
| 重解析后派生数据没了 | 没有按依赖顺序重建 | 跑 `examdata enrich`，再 `examdata provenance-rebuild` |
| 裁剪出来的题目图片位置不对 | 版式常量按 Edexcel A4（QP）/ Letter（MS）标定 | 换考试局需要重新标定；扫描件 PDF、识别不出编号、找不到匹配题号时 paper-qa 会明确失败而不是给错图 |

### 15.5 测试

| 症状 | 可能原因 | 确认与处理 |
|---|---|---|
| 一批用例被跳过 | `tests/fixtures/` 里缺真实试卷 PDF | 这些文件被 `.gitignore` 排除（版权原因），需要时自己放到 `tests/fixtures/` 下 |
| `conformance/` 里的用例大量跳过 | 它们需要访问真实考试局站点 | 离线环境下会 `pytest.skip`，这是设计行为 |
| `pytest` 命令找不到 | 没装开发依赖 | `pip install -e ".[dev]"` |

## 16 开发

### 16.1 项目结构

```text
examdata/
├── pyproject.toml            # 依赖、入口点、pytest 配置
├── README.md
├── LICENSE                   # MIT 许可
├── docs/
│   └── DEPLOY.md             # 本文档
├── research/                 # 考试局调研与实现现状笔记
│   ├── cambridge.md
│   ├── edexcel.md
│   └── implementation-status.md
├── src/examdata/
│   ├── cli.py                # 32 个子命令的 Typer 入口
│   ├── adapters/             # 考试局适配器：发现与入库
│   │   ├── base.py           # 适配器契约
│   │   ├── registry.py       # 适配器注册表
│   │   ├── cambridge/        # adapter.py + classify.py
│   │   └── edexcel/          # adapter.py + classify.py + servlet.py
│   ├── api/
│   │   └── app.py            # FastAPI 应用，20 条路由
│   ├── core/
│   │   ├── config.py         # Settings，EXAMDATA_ 前缀
│   │   ├── db.py             # engine / session / init_db
│   │   ├── fetch.py          # 统一抓取器：robots + 限速 + 重试
│   │   ├── ids.py
│   │   ├── models.py         # SQLAlchemy 模型
│   │   ├── robots.py
│   │   └── storage.py        # 内容寻址存储
│   ├── governance/
│   │   ├── override.py       # 人工修正与待检查队列
│   │   ├── provenance.py     # 溯源边
│   │   └── reparse.py        # 重新解析与快照对比
│   ├── intelligence/
│   │   ├── difficulty.py     # 难度估计
│   │   ├── explanation.py    # 解析生成
│   │   ├── similarity.py     # 相似题（TF-IDF n-gram）
│   │   ├── taxonomy.py       # 知识点标注
│   │   └── taxonomy_seed.py  # 知识点种子
│   ├── markscheme/
│   │   ├── base.py
│   │   └── cambridge.py
│   ├── paperqa/              # 按需取回真题文件
│   │   ├── api.py            # resolve() / query()
│   │   ├── errors.py         # 错误类型与状态码映射
│   │   ├── locator.py        # 题目裁剪
│   │   ├── models.py         # Request / Result / OutputFile
│   │   └── sources/          # base.py + cie_fraft.py + pearson.py
│   ├── parsing/
│   │   ├── content_classify.py
│   │   ├── metadata.py
│   │   ├── numbering.py      # 题号解析
│   │   ├── pdfdoc.py
│   │   ├── pipeline.py       # 解析流水线
│   │   ├── segment.py
│   │   └── tables.py
│   ├── query/
│   │   └── service.py        # 检索与抽题服务
│   └── sync/
│       └── service.py        # 同步闭环
├── scripts/                  # 运维与验证脚本
│   ├── e2e_cambridge.py
│   ├── pip_sandbox.py
│   ├── probe_edexcel.py
│   ├── reset_derived.py      # 破坏性
│   └── verify_state.py
└── tests/
    ├── conformance/          # 适配器契约测试
    ├── fixtures/             # 真实试卷样本（被 .gitignore 排除）
    └── test_*.py             # 340 项测试
```

### 16.2 跑测试

```bash
pip install -e ".[dev]"
pytest
```

`pyproject.toml` 里已经配好 `testpaths=["tests"]`，并且把 `tmpwork`、`.venv`、`.data`、`wheels`、`.piptmp` 排除在递归之外。默认带 `-q`。

共 **340 项**测试，分布在：

| 文件 | 项数 |
|---|---|
| `tests/conformance/test_adapter_contract.py` | 39 |
| `tests/test_api.py` | 28 |
| `tests/test_cambridge_classify.py` | 28 |
| `tests/test_cambridge_parsing.py` | 20 |
| `tests/test_classification_validation.py` | 6 |
| `tests/test_content_classify.py` | 13 |
| `tests/test_edexcel_adapter.py` | 31 |
| `tests/test_explanation.py` | 14 |
| `tests/test_governance.py` | 29 |
| `tests/test_intelligence.py` | 28 |
| `tests/test_paperqa.py` | 65 |
| `tests/test_paperqa_api.py` | 10 |
| `tests/test_paperqa_locator.py` | 9 |
| `tests/test_parsing_regressions.py` | 20 |

**关于跳过**：`tests/fixtures/*.pdf` 是真实试卷，出于版权原因被 `.gitignore` 排除，公开仓库里没有。缺少这些文件时，依赖它们的解析测试会自动 `skip`（`tests/test_cambridge_parsing.py` 用 `pytest.mark.skipif` 判定）。`tests/conformance/` 里的用例需要访问真实考试局站点，离线环境下同样会跳过。所以“全绿”里可能包含若干 skip，`pytest -q` 的汇总行会写清楚 `passed` 与 `skipped` 各多少。

只跑某一部分：

```bash
pytest tests/test_api.py
pytest tests/test_paperqa.py -q
pytest -k "governance"
```

### 16.3 已知限制

- **知识点种子只覆盖 4 个已同步科目**，且是两层结构（`topic` -> `subtopic`）。没有种子的科目无法自动标注。
- **生成解析只在有官方依据时才生成**。没有官方 Mark Scheme 或官方答案的题目，`generate_for_question` 返回 `None`，不会生成空壳内容。
- **生成内容与官方内容物理隔离**。生成解析恒为 `is_official=false`、`provider=rule-based`、默认 `review_status=pending`，未经人工审核不应展示给学生。
- **写入类操作不开放 HTTP**。人工修正、重新解析只能走 CLI 或 Python。
- **`EXAMDATA_MAX_CONCURRENCY` 不生效**。抓取是同步串行的。
- **题目裁剪是布局启发式**。版式常量按 Edexcel A4（QP）/ Letter（MS）标定，换考试局需要重新标定；扫描件 PDF、识别不出编号、找不到匹配题号时会明确失败。
- **`formula` 与 `job` 两张表在 schema 里存在但没有任何业务代码引用**（`core/models.py` 里只有定义；`formula` 仅在 `scripts/reset_derived.py` 的清理列表里出现，`job` 连清理列表都没有）。检索层与 HTTP 层都没有入口。
- **API 无鉴权、无 CORS、无限流**，生产部署必须靠 nginx 或网络层兜底。

### 16.4 版权与许可

代码以 **MIT** 许可发布，`Copyright (c) 2026 WENGENG-boop`。

**但代码的许可不覆盖数据**。Cambridge International 与 Pearson Edexcel 的试卷、评分标准、题目图片均受版权保护，Pearson 的部分资源属于 `secure-content`（非公开）。仓库刻意不收录任何试卷原件，`.gitignore` 里也明确排除了 `tests/fixtures/*.pdf`。

自己抓取、存储、分发这些材料之前，请自行确认你所在司法辖区与考试局条款下的合规性。本文档只讲技术操作，不构成法律意见。

## 17 速查表

### 17.1 从零到跑起来

```bash
git clone <仓库地址> && cd examdata
python3 -m venv .venv
.venv/bin/pip install --upgrade pip && .venv/bin/pip install .
.venv/bin/examdata initdb
.venv/bin/examdata sync --adapter cambridge --resources 5
.venv/bin/examdata parse-docs
.venv/bin/examdata enrich
.venv/bin/examdata provenance-rebuild
.venv/bin/examdata db-stats
.venv/bin/examdata serve --host 127.0.0.1 --port 8000
```

Windows 把 `.venv/bin/` 换成 `.venv/Scripts/`。

### 17.2 最常用的命令

```bash
examdata db-stats                                  # 看规模
examdata monitor                                   # 看同步/解析状态
examdata search-questions --subject 0580 --leaves --limit 5
examdata show-question 753
examdata sample-questions --subject 0580 --marks 20 --seed 7
examdata provenance-trace question 753
examdata override-list --conflicts                 # 看人工修正冲突
examdata review-list --status open                 # 看待检查队列
examdata paper-qa --board cie --subject 9709 --year 2026 --season Mar --paper 12 --out ./dl
examdata paper-qa --board edexcel --subject Economics --year 2024 --season Jun --paper wec11-01 --question '12(a)' --mode qa --out ./dl
```

### 17.3 最常用的 URL

```bash
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/papers?subject=0580&limit=5'
curl -s 'http://127.0.0.1:8000/questions?subject=0580&leaves_only=true&limit=5'
curl -s http://127.0.0.1:8000/questions/753
curl -s 'http://127.0.0.1:8000/questions/753/similar?limit=5'
curl -s http://127.0.0.1:8000/papers/1/tree
curl -s 'http://127.0.0.1:8000/taxonomy?board=cambridge'
curl -s -X POST 'http://127.0.0.1:8000/sample?subject=0580&marks_target=20&seed=7'
curl -o asset1.png http://127.0.0.1:8000/assets/1
curl -s http://127.0.0.1:8000/questions/2/explanation
curl -s 'http://127.0.0.1:8000/explanations/review-queue?status=pending'
curl -s http://127.0.0.1:8000/monitor
curl -s 'http://127.0.0.1:8000/review?status=open'
curl -s http://127.0.0.1:8000/overrides
curl -s 'http://127.0.0.1:8000/classifications?limit=10'
curl -s http://127.0.0.1:8000/questions/753/provenance
curl -s http://127.0.0.1:8000/assets/1/provenance
curl -s http://127.0.0.1:8000/provenance/coverage
curl -s 'http://127.0.0.1:8000/paper-qa/resolve?board=cie&subject=9709&year=2026&season=Mar&paper=12'
curl -o qp.pdf 'http://127.0.0.1:8000/paper-qa/query?board=cie&subject=9709&year=2026&season=Mar&paper=12'
curl -o qa.zip 'http://127.0.0.1:8000/paper-qa/query?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&question=12(a)&mode=qa'
curl -s 'http://127.0.0.1:8000/paper-qa/query?board=cie&subject=9709&year=2026&season=Mar&paper=12&format=json'
```

### 17.4 容易记错的地方

| 容易记错 | 实际是 |
|---|---|
| CLI `--leaves-only` | `--leaves` |
| CLI `--marks-target` | `--marks`（HTTP 里叫 `marks_target`） |
| `/questions` 的默认 `limit` 是 50 | 是 **20**（`/papers` 才是 50） |
| SQLite 绝对路径写三个斜杠 | 写**四个**斜杠：`sqlite:////var/lib/...` |
| `EXAMDATA_MAX_RETRIES` 是重试次数 | 是**总尝试次数**（默认 3 次） |
| 调大 `EXAMDATA_MAX_CONCURRENCY` 能加速抓取 | 该配置**不生效**，抓取是串行的 |
| 只设 `EXAMDATA_DATA_DIR` 就够了 | 还要设 `EXAMDATA_DATABASE_URL`，否则两者会分家 |
| 改 `.env` 就能覆盖 systemd 的 `Environment=` | 反过来，环境变量优先级更高 |
| `/paper-qa/resolve` 会下载文件 | 它**从不下载**，`files` 恒为空 |
| CLI `paper-qa --out` 是文件路径 | 是**目录** |
| Edexcel 的 `question` / `qa` 给 `wec11` 这种短代号就行 | 命中多个变体时会 409，稳妥写法是直接给**变体级** `wec11-01` |
| `question` 模式一定返回单张 PNG | 跨页或引用 Extract 时是**多张 PNG 的 ZIP**，按 `content-type` 判断 |
| CIE 也能裁剪题目 | CIE 只支持整份 PDF，传 `question` 会 422 |
| `curl -I` 可以探测接口 | 路由不支持 `HEAD`，会返回 405 |

### 17.5 端口与路径约定

| 项 | 默认值 |
|---|---|
| 服务监听 | `127.0.0.1:8000` |
| 数据根目录 | `./.data`（相对当前工作目录） |
| 数据库 | `sqlite:///.data/examdata.db` |
| 内容寻址存储 | `<data_dir>/artifacts/<sha256前2位>/<次2位>/<sha256><扩展名>` |
| 生产部署建议 | 代码 `/srv/examdata`，数据 `/var/lib/examdata` |
| systemd 单元 | `/etc/systemd/system/examdata.service` |
| nginx 站点 | `/etc/nginx/sites-available/examdata` |
