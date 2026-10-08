# 剑桥雅思（剑1–剑21）多源聚合 API —— 开发文档 v5.0

> 状态：**已联网跑通 + 真实下载落盘验证**
> - 端到端验证：**84 套阅读 3360 条答案键 / 84 套听力 3346 条答案键 / 剑1–20 PDF 文件 20/20（剑20为Test1分册） / 剑21 全套**
> - 真实下载：剑1–20 PDF 共 642 MB，**逐个与 LFS 记录的 oid 做 SHA256 字节级比对，20/20 一致**
>
> v6.0：三项原「全网无源」缺口全部补齐 —— 剑3 听力 T2–T4 答案（ieltsprogress.com）、
> 剑21 整本 PDF（aqinaq/agylshyn 社区镜像）、剑20/21 中英对照精读（小站备考）；
> 听力题目+答案覆盖率 81/84 → **84/84**；新增 `iprog` / `zhan` / `pdf21` 接口与路由。
>
> v5.0：新增**剑桥21 完整源**（阅读+听力+官方音频+逐句原文）；新增听力交叉源；
> 听力原文覆盖率 6/20 → **20/20**；聚合新增 score 字段与多层降级。

> 覆盖数字为2026-10-01保留的联网审查证据，不保证源站持续可用。84/84表示可调用套数，不等于每套40个独立题干完整；组合题与 `questions_missing` 必须单独检查。319 Part 表示剑1–20有可用原文，剑20仍缺1段。PDF哈希一致证明所下载文件与LFS指针相符，不证明整本教材内容完整。本轮续作及未完成检查见 `AUDIT_REPORT.md`（位于工作区旁ielts-api）。

---

## 1. 架构：题目 / 答案 / 音频 / 原文 / PDF 分源拼装

官方剑桥雅思无公开 API，因此本方案**不依赖单一权威源**，把一套题拆成多个独立槽位，
每槽由覆盖最好的源供给，最后在 `aggregate()` 拼回完整试卷：

| 槽位 | 内容 | 主源 | 覆盖 |
|---|---|---|---|
| **S1 阅读** | 原文 + 题目 + 答案 + 解析 | `practicepteonline.com` ⭐ | **剑1–21**（84 套） |
| **S2 听力** | 题目 + 答案 + 音频 | `practicepteonline.com` ⭐ | **剑1–21**（84 套完整；剑3 T2–T4 由 S14 兜底） |
| **S3 PDF** | 剑1–19整本；剑20 Test1分册 | `BaBaLiBoo/IELTS-Resources` ⭐⭐ | **20/20 文件（剑1–19 整本 + 剑20 Test1 分册）** |
| **S4 精讲解析 PDF** | 真题精讲 | `BaBaLiBoo/IELTS-Resources` ⭐⭐ | 剑7–20 + 456 合辑 |
| **S5 精读补充** | 中英对照 + 语法 + 同义替换 | `userheyy/ielts-reader` + 小站备考 | 剑1–19（228 篇）+ 剑20/21（24 篇） |
| **S6 听力题目+答案** | 时间戳 + 语速 + 干扰项 | `TaroFlink/...` | 剑16–20 |
| **S7 听力原文** | 逐 Part 全文 | **双源择优** `maslow` / `userheyy` | **剑1–20 全覆盖** |
| **S8 听力音频** | Part 级 MP3 | `maslow` + `practicepteonline` | 剑1–21 |
| **S9 整本 PDF（旧）** | 原版整本书 | `zeeklog/IELTS` | 剑4–18 |
| **S10 逐句时间轴** | 词级 start/end + 置信度 | `userheyy/ielts-reader` | 剑1–19 |
| **S11 实时补充** | Recent Actual Tests | `mini-ielts.com` | 实时 |
| **S12 剑桥21** | 阅读+听力+音频+原文 | `maqsudjon-cell/cambridge-21` ⭐⭐ | **剑21 全套** |
| **S13 听力交叉源** | 听力原文 + 答案表 | `ieltstrainingonline.com` | 剑10–21（48/48；部分 Part 源侧以 "…" 截尾，非解析问题） |
| **S14 剑3 听力答案兜底** | 答案键（题目页无题干；T2–T4 题干已重建） | `ieltsprogress.com` | 剑3 4/4 套，160 条答案键 |
| **S15 剑20/21 精读** | 逐句中英对照 | 小站备考（top.zhan.com） | 剑20/21（24 篇） |
| **S16 剑21 整本 PDF** | 完整书扫描版 | `aqinaq/agylshyn`（社区镜像） | 剑21（146 页 / 44.1 MB） |

---

## 2. v5.0 的关键突破

### 突破一：找到剑桥21 完整源 ⭐⭐

`maqsudjon-cell/cambridge-21` 是一个把结构化数据**直接内嵌在 HTML `<script>` 里**的题库站：

| 数据结构 | 内容 |
|---|---|
| `PASSAGES` / `QUESTIONS` / `ANSWERS` | 阅读：3 篇原文 + 40 题 + 40 答案键（4 套共 160 条） |
| `PARTS` / `correctAnswers` / `multiCorrect` | 听力：4 Section + 答案键（4 套共 160 题 / 147 条答案键，多选组一题多键） |
| `audioTracks` | **16 段官方音频**（每段约 10 MB） |
| `TRANSCRIPTS` | **逐句原文，含说话人与时间戳**（738 行） |

音频已本地固化并按 sha256 核验（16 段，见 `ielts-data` 的 audio-catalog）；样本 `C21T1_Section_1.mp3` → **11,216,604 B，ID3v2.4 头 + 17,890 帧有效 MP3（192 kbps，7 分 47 秒）**。

**解析难点与解法**：数据是 JS 字面量而非 JSON，且混用三种引号 ——
`{id:1,g:'g1',text:"their grandfather's wealth"}` 里既有单引号字符串又有双引号字符串内的撇号。
用正则转换会跨越字符串边界把 JSON 改坏（实测解析全空）。
最终写了**逐字符扫描的 `jsToJson()`**：分别处理双引号串、单引号串、模板串、注释，并给裸 key（含数字键）加引号。

### 突破二：听力原文覆盖率 6/20 → 20/20

初版只认 `PART N` 标题，而剑5–16 用的是 `SECTION N` → 剑3–16 全部解析成 0 Part。
修完标题后仍有问题：**剑4–10 的 maslow 文件只有 ~11k 字符（截断）**，reader 有 ~58k。
最终改为**按正文体量择优**（先比 Part 数，再比字符数），并加廉价探测（28.4s → 2.4s）：

```
剑 1–10: userheyy/ielts-reader   (~58–65k 字符，含说话人 + 中英对照)
剑11–13: maslow/EnglishLearning  (~69–75k 字符)
剑14–16: userheyy/ielts-reader
剑17–20: maslow/EnglishLearning
```

### 突破三：真实下载验证（不是探活）

早期验证只发 `Range: bytes=0-300`，那只能证明"文件在"，**不能证明能完整下载**。
改成完整拉到磁盘 + 结构校验后发现 2 个真 bug（见突破二）。

---

## 3. 覆盖矩阵（实测）

> 口径说明：下列“答案”均为**答案键条目数**，不等于题目数（多选组一题多键）。
> 题数与逐题状态以 v2 `coverage-v2` 的完整度单元为准（§9）。

```
题目/阅读        84/84   剑1–21 × Test1–4，共 3360 条答案键
题目/听力        84/84   共 3346 条答案键（剑3 T2–T4 由 ieltsprogress.com 兜底；剑1 T2 源站仅 39 条；剑21 各套 35–38 条）
剑3 听力兜底      4/4   160 条答案键（ieltsprogress.com；T2–T4 题干已重建）
剑21 阅读         4/4   160 条答案键 + 12 篇原文
剑21 听力         4/4   160 题 / 147 条答案键 + 16 段官方音频（本地 sha256 已核验）+ 738 行逐句原文
剑20/21 精读      24/24  逐句中英对照（top.zhan.com；剑20/21 各 12 篇）
听力原文         20/20  剑1–20 全覆盖，319 Part（剑20 缺 1 段）
听力交叉源       48/48  剑10–21（独立第二源）
PDF 文件         20/20  剑1–19整本 + 剑20 Test1，642.4 MiB，oid 全部一致
剑21 整本 PDF     1/1    146 页 / 44.1 MB（社区镜像 aqinaq/agylshyn）
精讲解析         16/16  剑7–20 + 456 合辑
```

### 统计口径与实测值（2026-10-02 复核）

原稿「PTE 约 338 MB / maslow 9/9 约 50.6 MB / 每个文件 70k–157k 帧」为早期抽样口径（URL 集合与时间点已不可复原），已废弃；以下为可复核的实测口径（证据文件在 `../tmp_audit_ielts/`）：

- **pte 音频总量**（`pte_audio_scan.json`，generated 2026-10-02T02:12:00Z）：81 个独立 MP3 URL 做
  HEAD 扫描，80 成功 / 1 失败，Content-Length 合计 **1,371,675,709 B（1308.1 MiB）**。
  ⚠️ 这是 URL 集合的 HEAD 总量，**不是完整下载量**。
- **maslow 音频总量**（`maslow_tree.json`，GitHub git/trees API，tree sha `2064b88b…`，
  truncated=false，文件 sha256 `7cdd9173…`）：346 个 MP3，合计 **2,592,743,250 B（2472.6 MiB）**。
- **帧数**：不再宣称统一区间。两个完整下载样本（`audio/parse_result_v2.json`）：
  - `maslow_b01_t1_p1.mp3` 3,731,165 B：ID3v2.4，MPEG2.5 11025 Hz 64 kbps，**8,927 帧**，466.39 s，坏字节 0
  - `pte_201_we.mp3` 2,141,282 B：ID3v2.3，MPEG2 24000 Hz 64 kbps，**11,152 帧**，267.65 s，坏字节 0
  - 剑21 样本：11,216,604 B，**17,890 帧**，192 kbps，7 分 47 秒（§2）
- **PDF 字节级回归**：`node ielts-cli.mjs verify-pdfs 1 20`（或 `node verify-pdfs.mjs`）流式下载
  全部 20 册并比对 SHA256 vs LFS oid；全量运行输出存 `tmp_audit_ielts/verify_pdfs_live_full_20261002.txt`。
  剑20 为 Test1 分册（34 页），非整本。

---

## 4. API 参考

```js
// 题目（practicepteonline，剑1–21）
api.pteBook(book) / api.pteReading(book, test) / api.pteListening(book, test) / api.pteAudio(book, test)

// 剑桥21 专属
api.cam21Reading(test)      // 3 篇原文 + 40 题 + 40 答案
api.cam21Listening(test)    // 4 Section + 答案 + 音频 + 逐句原文
api.cam21Audio(test, section)
api.cam21Full(test) / api.cam21Index() / api.cam21Coverage()

// 听力交叉源（剑10–21）
api.itoScript(book, test) / api.itoListening(book, test) / api.itoCoverage()

// 剑3 听力答案兜底（ieltsprogress.com）
api.iprogListening(book, test) / api.iprogCoverage()

// 剑20/21 阅读精读（小站备考）
api.zhanIndex(book) / api.zhanReading(book, test, passage) / api.zhanCoverage()

// 整本 PDF（Git LFS，剑1–19 整本 + 剑20 Test1 分册）
api.pdfLfs(book) / api.explainPdf(book) / api.book20Set() / api.lfsProbe(path, via) / api.lfsCoverage()
api.pdf21()                           // 剑21 整本 PDF（社区镜像，146 页）

// 精读 / 听力辅助
api.reading(book, test, passage)      // 剑1–19 中英对照+语法+同义替换
api.listeningQA(book, test)           // 剑16–20 带时间戳/语速
api.listeningScript(book)             // 剑1–20 双源择优
api.listeningAudio(book, test, part)  // 剑1–20 Part 级音频
api.listeningSegments(book, test, part) // 词级时间轴
api.pdf(book)                         // zeeklog 剑4–18
api.miniList(page) / api.miniSolution(id, slug)

// 聚合
api.aggregate({book, test})   // ★ 跨源拼装，返回 score（如 "5/5"）与 warnings
api.coverage()                // 全源覆盖率自检
```

统一契约：失败返回 `ok:false` + `error`（正常路径不抛异常）；每条数据带 `source` 可溯源。

---

## 5. CLI / HTTP

```bash
node ielts-cli.mjs aggregate 21 1       # 剑21 完整一套（score 5/5）
node ielts-cli.mjs cam21-reading 1      # 剑21 T1 阅读：3 篇原文 + 40 答案
node ielts-cli.mjs cam21-listening 1    # 剑21 T1 听力：音频 + 逐句原文
node ielts-cli.mjs cam21-coverage       # 剑21 覆盖自检
node ielts-cli.mjs ito-coverage         # 听力交叉源自检（48/48）
node ielts-cli.mjs iprog-coverage       # 剑3 听力答案兜底自检（4/4）
node ielts-cli.mjs pdf21                # 剑21 整本 PDF（44.1 MB / 146 页）
node ielts-cli.mjs zhan-coverage        # 剑20/21 精读自检（24 篇）
node ielts-cli.mjs pdf-lfs 1            # 剑1 整本 PDF（26.9 MB）
node ielts-cli.mjs lfs-coverage         # 剑1–20 PDF 自检
node ielts-cli.mjs verify-pdfs 1 20     # 剑1–20 PDF LFS 字节级回归（SHA256 vs oid；全量下载约 642 MiB）
node ielts-cli.mjs serve 8787
```

> `verify-pdfs` 也可直接用独立脚本运行：`node verify-pdfs.mjs [册号...] [--jobs N] [--json]`。
> 每册先从 raw 拉 LFS 指针（解析 oid/size），再从 `media.githubusercontent.com` 流式下载、边下边算 SHA256（不落盘），
> 比对 sha256===oid、字节数===size、首字节 `%PDF-`；退出码 0=全部一致 / 1=有失败 / 2=参数错误。
> `--jobs N` 只控制并发数（默认 3），**不是册号过滤**（2026-10-02 修复过把它当册号的 bug）。

HTTP 路由：`/api/cam21-reading/:test`、`/api/cam21-listening/:test`、`/api/cam21-audio/:test/:section`、
`/api/ito-script/:book/:test`、`/api/ito-coverage`、`/api/aggregate/:book/:test` 等。

---

## 6. 源探测结论

| 源 | 结果 | 说明 |
|---|---|---|
| `practicepteonline.com` | ✅ **采用** | WP REST，剑1–21 题目/答案/音频/解析 |
| `maqsudjon-cell/cambridge-21` | ✅ **采用** ⭐⭐ | **提供剑桥21结构化数据的源** |
| `BaBaLiBoo/IELTS-Resources` | ✅ **采用** | Git LFS，剑1–19 整本 + 剑20 Test1 分册 PDF + 16 份精讲 |
| `ieltstrainingonline.com` | ✅ **采用** | 剑10–21 听力原文（**posts** 而非 pages） |
| `ieltsprogress.com` | ✅ **采用**（v6.0 新增） | 剑3 听力答案键 4/4 套，160 条（T2–T4 题干已重建） |
| `top.zhan.com`（小站备考） | ✅ **采用**（v6.0 新增） | 剑20/21 逐句中英对照精读（24 篇） |
| `aqinaq/agylshyn` | ✅ **采用**（v6.0 新增） | 剑21 整本 PDF（146 页 / 44.1 MB，社区镜像） |
| `userheyy/ielts-reader` | ✅ 采用 | 剑1–19 精读 + 听力原文/时间轴 |
| `maslow/EnglishLearning` | ✅ 采用 | 剑1–20 听力原文 + 320 Part 音频 |
| `TaroFlink/...` | ✅ 采用 | 剑16–20 带时间戳/语速 |
| `zeeklog/IELTS` | ✅ 采用 | 剑4–18 整本 PDF |
| `mini-ielts.com` | ✅ 采用 | 实时 Recent Actual Tests |
| `ieltscat.xdf.cn` | ⚠️ 备用 | 需动态签名，返回 `{"status":42}` |
| `lincohlesteban-art/ielts-academic-platform` | ⚠️ 未采用 | 仅 practicepteonline 镜像，无新增覆盖 |
| `engnovate` / `test-english` / `youpass` | ❌ | Cloudflare 403 |

### 6.1 CDN 回落复验（2026-10-02）

- 模拟 `raw.githubusercontent.com` 全面故障（拦截 fetch 抛错）后重跑端到端（脚本 `tmp_audit_ielts/fallback_e2e.mjs`，输出 `fallback_e2e_20261002.txt`）：
  - `cam21.reading(1)` → `{ok:true, via:"cdn", answers:40}`（raw 1 次失败 → cdn 1 次成功）
  - `reading(1,1,1)` → `{ok:true, questions:15}`（raw 3 次失败 → cdn 1 次成功）
- 直连复验 4 条 `cdn.jsdelivr.net/gh/...` URL（输出 `fallback_cdn_curl_20261002.txt`）全部 HTTP 200 且**无 301**：
  cam21 `t1-reading.html` 87,412 B；reader `data/passages/c1-test1-p1.json` 40,458 B；
  maslow `ielts_index/listening_index.json` 505,035 B；LFS 指针 133 B（oid `93ba03c1…`，size 28,252,883）。
- 结论：「jsDelivr 301 指回 raw」的旧记录在本次复验中**不可再现**；`via:"cdn"` 作为 raw 的备用通道保留。

---

## 7. 已知缺口（已确认无公开源）

| 缺口 | 现状 | 排查过程 |
|---|---|---|
| **剑21 整本 PDF** | ✅ 已解决（v6.0） | 社区镜像 `aqinaq/agylshyn`：146 页 / 44.1 MB；接口 `pdf21()` |
| **剑3 听力 T2/T3/T4** | ✅ 已解决（v6.0） | `ieltsprogress.com` 答案键 4/4（各 40 答案）；aggregate 自动兜底 |
| **剑1 T2 听力第 40–41 题** | ⚠️ 源缺 | 官方书该套共 41 题（40–41 为图表题）；站点页全文无 "40"/"41" 字样，非解析失败 |
| **剑20/21 阅读精读** | ✅ 已解决（v6.0） | 小站备考逐句中英对照 24 篇；接口 `zhanReading()` |
| **剑1–3 听力原文完整度** | ⚠️ 部分 | maslow 源自带 `source_quality` 标注 |

> 聚合对缺口**自动降级**：剑3 T2–T4 现由 ieltsprogress.com 补齐答案（题目页无题干，
> 但含 40 答案 + reader 词级时间轴）；其余槽位照常返回，不影响 `score`。

---

## 8. 快速开始

```bash
cd ielts-api
node ielts-cli.mjs cam21-coverage     # 剑21 全套自检
node ielts-cli.mjs aggregate 21 1     # 剑21 完整一套
node ielts-cli.mjs pdf-lfs 1          # 剑1 整本 PDF
node ielts-cli.mjs serve 8787
```

## 9. v2 规范化接口、测试与运维（S13–S15 新增）

### 9.1 v2 接口（schema `ielts.v2/1`）

v1 接口全部保留；v2 以本地索引（`ielts-data/runs/<run>/index/question-index.json`）与本地资产
（`assets/` `audio/` `pdf/`）驱动，CLI / Node HTTP / FastAPI 三入口共享同一 resolver，**零网络请求**：

- CLI：`books-v2`、`test-v2 <book> <test> [--variant=academic|general]`、
  `questions-v2 <book> <test> [--skill= --variant= --part= --passage= --type= --status= --alignment= --offset= --limit=]`、
  `question-v2 <question_id>`、`coverage-v2`、`asset-v2 <asset_id>`、`compare-official <book> <test>`；
- Node HTTP（`serve 8787`）：`/api/ielts/v2/info|books|test/{book}/{test}|questions/{book}/{test}|question/{question_id}|coverage|asset/{asset_id}`；
- FastAPI 网关：同语义，前缀 `/api/v1/ielts/v2/…`。

语义要点：整套 vs 单篇（`--passage=`/`--part=`；阅读缺省整卷 40 题）；A/G 变体（GT 用 `gta`/`gtb`）；
逐题 `answer.status`（`verified`/`official_verified`/`empty`/`source_missing`）；组题带 `group_ref` 与
accepted 集合；完整度单元带 `expected` 分母（如剑1 T2 听力 = 41 题）；Writing/Speaking 开放题只给
期望清单、不标唯一标准答案；音频资产按 sha256 解析，身份（identity + content_sha256）核验后才计
verified；逐题时间区间仅在音频身份与时间基准校验通过后标记，未对齐项保持 `unverified`。

### 9.2 测试与回归（全部离线、零网络）

```bash
cd ielts-api
node --test tests/*.test.mjs          # 全量单测 + e2e（309 用例，含 22 个端到端子进程案例）
node --test contract.test.mjs         # 契约（9）
node tools/verify-decisions.mjs       # 45 裁决 + 7 窄修正 + 2 组核验（39 项校验）
node tools/check-route-inventory.mjs  # 独立端口 8799 校验三入口路由清单（11 项）
```

FastAPI 网关（examdata）：

```bash
cd examdata
EXAMDATA_TEST_LIVE=0 EXAMDATA_IELTS_DATA_DIR=<工作区>/ielts-data \
EXAMDATA_IELTS_DIR=<工作区>/ielts-api \
.venv/Scripts/python.exe -m pytest tests/test_api_ielts.py tests/test_ielts_concurrency.py tests/test_ielts_resolver_contract.py
```

### 9.3 数据目录与更新命令

- 数据根默认 `<工作区>/ielts-data`，可用 `EXAMDATA_IELTS_DATA_DIR` 覆盖（三入口一致）；
  测试夹具登记见 `tests/fixtures/manifest.json`。
- `node tools/refresh.mjs …`：本地复用固化刷新（网络请求恒为 0；raw/pdf 内容寻址；ledger + checkpoint；`--resume` 幂等）。
- `node tools/build-index.mjs --dataset current`：构建 indexes/manifests/normalized 并原子发布 current。
- `node tools/audit-all.mjs --dataset current --verify-assets --verify-audio`：全量审计（矩阵/错误/逐题 JSONL；音频流式 sha256 校验；退出码 0/1/2/3）。
- `node tools/run-alignment.mjs …`：听力逐题对齐（候选/上下文/动态规划；仅在音频身份与时间基准校验通过后标 verified，不按题号均分时长）。

## 10. 合规提示

仅聚合**公开可访问的第三方索引/仓库**，用于个人学习检索。剑桥雅思真题版权归
Cambridge University Press & Assessment 所有；PDF 与音频为第三方镜像，
**请勿商业分发**，生产环境请替换为自有授权素材。
