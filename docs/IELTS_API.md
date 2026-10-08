# 三源统一调用：CIE × Edexcel × IELTS

> 本文档说明如何在**同一台服务、同一套 `/api/v1` 前缀**下同时调用
> Cambridge International（CIE）、Pearson Edexcel 与 IELTS（剑桥雅思）三个来源的题目。
> IELTS 部分为**纯增量网关**（`src/examdata/api/ielts.py`），不改动任何既有端点。

## 1. 三个来源各走什么路径

| 来源 | 前缀 | 数据位置 | 说明 |
|---|---|---|---|
| CIE | `/api/v1/…`（既有 unified 网关） | examdata 数据库（已解析） | `search` / `papers` / `question` 等既有端点 |
| Edexcel | `/api/v1/…`（既有 unified 网关） | 数据库 + 实时发现 | `search` 查库；`/api/v1/paper` 支持 live resolve 直链 |
| **IELTS** | **`/api/v1/ielts/…`（本文档）** | **仓库旁 `ielts-api/` Node 聚合器** | 每次请求起短命 `node ielts-cli.mjs` 子进程，JSON 原样透传 |

启动：

```bash
examdata serve --host 127.0.0.1 --port 8000
```

## 2. 三源同调示例（可直接运行）

```bash
# ① CIE：全库检索（题目在库里）
curl "http://127.0.0.1:8000/api/v1/search?board=cie&limit=2"

# ② Edexcel：实时解析某份卷（QP+MS 直链；download=false 只返回链接）
curl "http://127.0.0.1:8000/api/v1/paper?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&mode=both&download=false"

# ③ IELTS：单套阅读（题目+答案）
curl "http://127.0.0.1:8000/api/v1/ielts/reading/19/1"

# ③ IELTS：整卷聚合（阅读+听力+原文+音频+PDF，score 给出完整度）
curl "http://127.0.0.1:8000/api/v1/ielts/aggregate/21/1"
```

实测结果（2026-10-02，本机）：

| 调用 | 结果 |
|---|---|
| `/api/v1/search?board=cie&limit=2` | `total=751`，题干如 `"Kim takes part in a race …"`（0580 2025） |
| `/api/v1/paper?board=edexcel&…wec11-01…` | `counts.documents=2`（que + rms 两个 PDF 直链） |
| `/api/v1/ielts/reading/19/1` | `ok:true`，13 题（含 `answer` / `evidence_sentence` / 同义替换） |
| `/api/v1/ielts/aggregate/21/1` | `score="5/5"`，`sources_used` 5 个源，`warnings=[]` |

> Edexcel 的 **live resolve**（`/api/v1/paper`）实时可用；数据库内当前
> edexcel 仅有 44 个 document、0 道题（数据状态，非代码缺陷）——需要题目时
> 用 `paper` 端点按需发现/下载，或先跑 Edexcel 同步流程入库。

## 3. IELTS 路由清单（v1 20 条 + v2 7 条）

| 路径 | 说明 |
|---|---|
| `/api/v1/ielts/info` | 能力清单（书目范围、路由、源、env） |
| `/api/v1/ielts/books/{book}` | 单册目录（pteBook slug 表） |
| `/api/v1/ielts/reading/{book}/{test}?passage=` | 阅读题目+答案（passage 1–3，默认 1） |
| `/api/v1/ielts/listening/{book}/{test}` | 听力题目+答案 |
| `/api/v1/ielts/aggregate/{book}/{test}` | 整卷聚合（无顶层 `ok`，看 `score`/`completeness`/`parts.*.ok`） |
| `/api/v1/ielts/coverage` | 全源覆盖自检（较慢） |
| `/api/v1/ielts/cam21/reading/{test}` | 剑桥21 阅读（4 套 × 40 条答案键） |
| `/api/v1/ielts/cam21/listening/{test}` | 剑桥21 听力（160 题 / 147 条答案键，多选组一题多键） |
| `/api/v1/ielts/cam21/coverage` | 剑桥21 自检 |
| `/api/v1/ielts/ito/script/{book}/{test}` | 听力原文交叉源（剑10–21） |
| `/api/v1/ielts/ito/coverage` | 交叉源自检 |
| `/api/v1/ielts/listening-script/{book}` | 整册听力原文（4 套） |
| `/api/v1/ielts/listening-audio/{book}/{test}?part=` | 听力音频直链（part 1–4，默认 1） |
| `/api/v1/ielts/pdf/{book}` | 整本 PDF 信息（Git LFS，剑1–19 整本 + 剑20 Test1 分册） |
| `/api/v1/ielts/lfs-coverage` | LFS 整本 PDF 覆盖自检 |
| `/api/v1/ielts/pdf21` | 剑桥21 整本 PDF（146 页 / 44.1 MB） |
| `/api/v1/ielts/iprog/listening/{book}/{test}` | 剑3 听力答案兜底（ieltsprogress.com） |
| `/api/v1/ielts/iprog/coverage` | 剑3 听力答案自检 |
| `/api/v1/ielts/zhan/reading/{book}/{test}?passage=` | 剑20/21 阅读逐句中英对照 |
| `/api/v1/ielts/zhan/coverage` | 剑20/21 精读自检 |

### v2 规范化接口（推荐）

（S13 起）v2 由本地索引驱动、零网络请求，CLI / Node HTTP / FastAPI 三入口共享同一 resolver。

| 路径 | 说明 |
|---|---|
| `/api/v1/ielts/v2/info` | v2 能力清单（schema `ielts.v2/1`、路由、数据根） |
| `/api/v1/ielts/v2/books` | 21 册目录 |
| `/api/v1/ielts/v2/test/{book}/{test}?variant=academic|general` | 整套元数据 + 完整度单元（`expected` 分母；GT 用 `gta`/`gtb`） |
| `/api/v1/ielts/v2/questions/{book}/{test}?skill=&variant=&part=&passage=&type=&status=&alignment=&offset=&limit=` | 逐题（含 `answer.status`；阅读缺省整卷 40 题，单篇用 `passage=`） |
| `/api/v1/ielts/v2/question/{question_id}` | 单题（如 `q-10-1-reading-academic-34`：源缺答案但编号保位） |
| `/api/v1/ielts/v2/coverage?book=&test=` | 覆盖度（分母 + 逐单元状态 + gap 列表） |
| `/api/v1/ielts/v2/asset/{asset_id}` | 资产：图片/音频（sha256）或整本 PDF（`book-pdf-<n>`） |

要点：A/G 变体（`variant=`，身份不符返回 `variant_mismatch`）；Writing/Speaking 为开放题，只给期望清单、**不标唯一标准答案**；答案状态 `verified`/`official_verified`/`empty`/`source_missing`；音频身份（identity + content_sha256）核验后才计 verified，逐题时间区间未对齐保持 `unverified`（不伪造、不均分）。

## 4. 返回契约

- **业务失败与成功同为 HTTP 200**：通常失败返回 `ok:false` + `error`；
  `aggregate` 例外（无顶层 `ok`；`score`（如 5/5）只表示分片槽位可用，不代表每题答案正确）。
- **只有基础设施错误用 HTTP 错误码**（错误体为 FastAPI `{"detail": …}` 形状）：

| 状态码 | 场景 |
|---|---|
| 503 | 找不到 `node`，或找不到 `ielts-cli.mjs`；并发排队超时 |
| 504 | 子进程超时（默认按路由 90–600s，可用 env 覆盖） |
| 502 | 子进程非零退出，或输出不是合法 JSON |

- 响应顶层会补 `board: "ielts"`，便于调用方跨考试局识别来源。

## 5. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `EXAMDATA_IELTS_DIR` / `IELTS_API_DIR` | `<repo>/ielts-api` | 聚合器目录（找不到时自动尝试 parents[3]、cwd） |
| `EXAMDATA_NODE` | 从 PATH 找 `node` | node 可执行文件 |
| `EXAMDATA_IELTS_TIMEOUT` | 按路由 90–600s | 统一覆盖所有 IELTS 子进程超时（秒） |
| `EXAMDATA_IELTS_MAX_CONCURRENT` | 4 | 每个服务进程/事件循环同时执行的IELTS子进程数（1–64） |
| `EXAMDATA_IELTS_QUEUE_TIMEOUT` | 5s | 等待并发槽位超时返回503（大于0、不超过60s）；取消请求回收子进程 |
| `EXAMDATA_IELTS_DATA_DIR` | `<repo>/ielts-data` | v2 索引/覆盖数据根（透传给 Node resolver；缺省用仓库旁 ielts-data） |

## 6. 覆盖范围（IELTS 侧）

```
阅读        84/84   剑1–21 × Test1–4，共 3360 条答案键（多选组一题多键时计多键）
听力        84/84   共 3346 条答案键（剑3 T2–T4 由 ieltsprogress.com 兜底）
剑21 全套    4/4    阅读 160 条答案键 + 听力 160 题（147 条答案键）+ 16 段官方音频 + 738 行逐句原文
听力原文    20/20   剑1–20 全覆盖，319 Part（剑20 源侧仅 15 段，test2 缺 part4）
剑20/21 精读 24/24  逐句中英对照（top.zhan.com）
PDF 文件    20/20   剑1–19整本 + 剑20 Test1（Git LFS）；另有剑21社区镜像146页
```

> 口径：覆盖表中的数字均为答案键条目数（多选组一题多键时计多键），不等于题数；题数与逐题状态以 v2 coverage 为准。

详见仓库旁 `ielts-api/API.md` 与 `ielts-api/DEVELOPMENT.md`。

## 7. 测试

```bash
# 离线测试（不联网）：info 清单、ok:false 透传、node 缺失 503
pytest tests/test_api_ielts.py

# 契约测试（离线；需 EXAMDATA_IELTS_DATA_DIR 指向真实 ielts-data 数据根）
pytest tests/test_ielts_resolver_contract.py

# 并发与取消回收（离线）
pytest tests/test_ielts_concurrency.py

# 含联网 live 测试
EXAMDATA_TEST_LIVE=1 pytest tests/test_api_ielts.py
```

> 覆盖数字为2026-10-01保留的联网审查证据，不保证源站持续可用。84/84表示可调用套数，不等于每套40个独立题干完整；组合题与 `questions_missing` 必须单独检查。319 Part 表示剑1–20有可用原文，剑20仍缺1段。PDF哈希一致证明所下载文件与LFS指针相符，不证明整本教材内容完整。本轮续作及未完成检查见 `AUDIT_REPORT.md`（位于工作区旁ielts-api）；v2 逐题覆盖与剩余缺口见 `docs/ielts/IELTS_REMAINING_GAPS.md`。
