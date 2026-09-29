# examdata · 国际考试真题统一数据服务

把 Cambridge International 与 Pearson Edexcel 的公开试卷，变成**结构化、可检索、可溯源**的数据。

从官方站点发现资源、下载原件、解析出题目树、关联评分标准、提取图形资产，
再叠加知识点分类、难度估计、相似题识别与生成解析，最后通过 CLI 与只读 HTTP API 对外提供。

> **这是一个工具，不是题库。** 本仓库不包含任何试卷原件——见下方[版权与合规](#版权与合规)。

## 能力

| 层 | 做什么 | 实现 |
|---|---|---|
| 适配器 | 各考试局的发现/下载差异 | `adapters/`，`BoardAdapter` 契约 + 自动发现注册 |
| 同步 | 发现 → 去重 → 下载 → 版本化 → 落库 | `sync/`，内容寻址存储 |
| 解析 | PDF → 题目树、评分条目、图形资产 | `parsing/`、`markscheme/` |
| 治理 | 人工修正、重新解析、溯源、待检查队列 | `governance/` |
| 智能 | 知识点、难度、相似题、生成解析 | `intelligence/`，全部确定性可复现 |
| 检索 | 试卷/题目检索、抽题、监控视图 | `query/`，CLI 与 HTTP 共用同一份返回结构 |
| PaperQA | 按需取回整卷 PDF 或裁剪单题 PNG | `paperqa/`，不落盘 |

**已接入考试局**：Cambridge International（`public`）、Pearson Edexcel（`partial_public`）。

## 快速开始

需要 **Python ≥ 3.11**。

```bash
git clone https://github.com/WENGENG-boop/examdata.git
cd examdata
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Windows 把 `.venv/bin/` 换成 `.venv\Scripts\`。

```bash
examdata initdb            # 建表
examdata sync --adapter cambridge --syllabus 0580
examdata parse-docs        # 解析已下载的 PDF
examdata enrich            # 知识点 → 难度 → 相似题 → 生成解析
examdata provenance-rebuild
examdata db-stats          # 看规模
```

完整部署指南（数据准备、systemd、nginx、HTTPS、故障排查）见 [docs/DEPLOY.md](docs/DEPLOY.md)；
统一 API 的完整参考与**公网调用指南**见 [docs/API.md](docs/API.md)，
可直接运行的客户端示例见 [`examples/`](examples/)。

## 使用

### 命令行

```bash
# 检索
examdata search-papers --subject 0580 --year 2024
examdata search-questions --subject 0580 --leaves --limit 5
examdata show-question 123

# 抽题（seed 固定即可复现）
examdata sample-questions --subject 0580 --marks 20 --seed 7

# 取真题文件（不落盘；加 --out 才保存，且不覆盖已有文件）
examdata paper-qa --board cie --subject 9709 --year 2026 --season Mar --paper 12 --mode both
examdata paper-qa --board edexcel --subject Economics --year 2024 --season Jun \
                  --paper wec11-01 --question '12(a)' --mode qa --out tmp/ --json
```

`examdata --help` 列出全部 32 条命令。

### HTTP API

```bash
examdata serve --host 127.0.0.1 --port 8000
# 交互式文档：http://127.0.0.1:8000/docs
```

24 条只读路由：试卷检索 `/papers`、题目检索 `/questions`、单题完整内容
`/questions/{id}`、相似题、整卷题目树、随机抽题 `/sample`、溯源、待检查队列、
知识点体系、监控视图 `/monitor`、`/paper-qa/resolve`（只解析清单）与
`/paper-qa/query`（取回文件，默认二进制，`format=json` 走 base64），
以及统一网关 `/api/v1/*` 的 4 条（见下一节）。

```bash
curl 'http://127.0.0.1:8000/questions?subject=0580&leaves_only=true&limit=5'
curl -o qp.pdf 'http://127.0.0.1:8000/paper-qa/query?board=cie&subject=9709&year=2026&season=Mar&paper=12'
```

```python
from examdata.paperqa import query

result = query('edexcel', 'Economics', 2024, 'Jun', 'wec11-01', '12(a)', mode='qa')
print(result.metadata()['counts'], result.files[0].sha256[:12], result.files[0].bbox)
```

**写入类操作刻意不开放 HTTP**（人工修正、重新解析走 CLI），避免"生成内容与官方内容
物理隔离"这条约束被匿名写接口绕过。默认无鉴权，公网部署请设置 `EXAMDATA_API_KEY`
或只监听内网、置于反向代理之后。

### 统一 API（`/api/v1`）

两个上游（CIE 与 Pearson Edexcel）已经合并成**一套入口**，调用方不必分别对接：

| 端点 | 作用 |
|---|---|
| `GET /api/v1/boards` | 能力发现：两个考试局的科目形态、考季、模式、是否支持按题裁剪 |
| `GET /api/v1/paper` | 统一取卷：解析清单 / 整卷 PDF / 按题裁剪 PNG / 题目+答案配对 |
| `GET /api/v1/search` | 跨考试局检索，返回 `by_board` 分组计数 |
| `GET /api/v1/question/{id}` | 单题聚合视图，附可直接复用的 `paper_endpoint` |

`board` 可省略：四位数字科目代码（`0580`、`9709`）判为 CIE，其余（`wec11`、
`ial18-economics`）判为 Edexcel；别名 `cie`/`cambridge`、`edexcel`/`edx`/`pearson` 等价。
响应顶层回带 `board` 与 `board_source`（`explicit` / `inferred`），判定过程透明。

```bash
# 不传 board，自动判定
curl -o qp.pdf 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&mode=qp'
# 跨考试局检索
curl 'http://127.0.0.1:8000/api/v1/search?keyword=triangle&limit=5'
```

完整参考（参数表、错误码、curl/Python/浏览器三种调用形态、VPS 公网部署与
nginx + HTTPS + 限流、故障排查）见 [docs/API.md](docs/API.md)；可直接运行的客户端见
[`examples/python_client.py`](examples/python_client.py)、
[`examples/node_client.mjs`](examples/node_client.mjs)、
[`examples/curl.md`](examples/curl.md)、
[`examples/browser.html`](examples/browser.html)。
部署完用 `scripts/smoke_public_api.py` 一键自检：

```bash
python scripts/smoke_public_api.py --base-url https://<你的域名>
```

### 配置

环境变量前缀 `EXAMDATA_`，也读取工作目录下的 `.env`：

```bash
EXAMDATA_DATA_DIR=/var/lib/examdata
EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db
```

默认值是**相对当前工作目录**的 `.data/`，部署时务必改成绝对路径，
否则换个目录启动会静默指向一个空数据库。

## 版权与合规

- 本仓库**只收录代码，不收录任何试卷、评分标准或图形原件**。真实试卷受考试局版权保护，
  `tests/fixtures/*.pdf` 已被 `.gitignore` 排除。
- 抓取层默认遵守 `robots.txt`、按主机限速并带重试（`core/robots.py`、`core/fetch.py`）。
- 使用者需自行确认对目标站点的访问与使用符合其服务条款与所在地法律。
- 生成解析标注为 `provider="rule-based"`、`is_official=False`、`review_status="pending"`——
  它是从官方评分标准派生的规则式脚手架，**不是**真正的解题推理，未经人工审核不应直接展示给学生。

## 测试

```bash
pytest                      # 364 项
pytest tests/conformance    # 适配器契约（参数化遍历 registry）
```

部分解析测试依赖真实试卷样本。**本仓库不提供这些文件**，缺少时相关用例会 skip 而非失败。
需要完整覆盖时，自行把对应 PDF 放入 `tests/fixtures/`：

| 文件名 | 用途 |
|---|---|
| `0580_qp_11.pdf` | 试卷解析、内容级类型判定 |
| `0580_ms_11.pdf` | 评分标准解析 |
| `0580_ms_01_specimen.pdf` | 横排评分表版式回归 |

## 设计取舍

- **溯源是投影，不是副本。** 题目 → `parse_run` → `document_revision` → `source_url`
  这条链在解析时已完整落库，另写一份来源只会多出一份可能不一致的副本。
- **一致性套件传输中立。** `tests/conformance` 只约束行为、不约束实现路径——
  Cambridge 靠正则抽锚点、Edexcel 走站内 Algolia servlet，同一套检查对两者都成立。
  新增考试局只需实现 `BoardAdapter` 并注册，核心系统无需改动。
- **智能层不依赖模型服务。** 知识点 `keyword-v1`、难度 `heuristic-v1`、
  相似题 `tfidf-ngram-v1`，全部确定性可复现。
- **冲突不自动裁决。** 页面判定与 PDF 内容判定真冲突时保留页面判定、压到 0.35 置信度，
  并写入待检查队列（error 级），交人处理。
- **数据不够就报错，不返回可能被截断的结果。** Pearson servlet 有 1000 条硬上限，
  撞上限按考季/文档类型递归分片；切不动时显式失败，不谎报全量。

## 已知未实现

不虚报进度，以下确实还没做：

1. **AP / SAT / IB 适配器**——前两者站点实测可达但未实现，`ibo.org` 返回 403。
2. **Alembic 迁移**——仍是 `create_all` + `db.py` 的补列清单（过渡方案）。
3. **全量同步**——Cambridge 已枚举 198 个 syllabus，仅同步 4 个科目；
   Edexcel 已枚举 258 个科目页，仅试同步 1 个。
4. **生成解析是规则式而非推理式**——不会真正演算数学题。
5. **分值合计仍有偏差**——12 份文档的 `marks_total_mismatch` 未收敛。

更多细节见 `research/implementation-status.md`。

## 许可

MIT，见 [LICENSE](LICENSE)。
