# 托福接入：`/api/v1/toefl/…`

> 本文档说明在既有 CIE/Edexcel/IELTS 服务之上新增的 TOEFL（托福 TPO + 公开第三方索引）
> 网关。托福部分为**纯增量**（`src/examdata/api/toefl.py` + 仓库旁 `toefl-api/` Node 聚合器），
> 不改动任何既有端点。

## 1. 数据从哪里来

| 来源 | 前缀 | 数据位置 | 说明 |
|---|---|---|---|
| CIE | `/api/v1/…`（既有 unified 网关） | examdata 数据库（已解析） | 既有端点 |
| Edexcel | `/api/v1/…`（既有 unified 网关） | 数据库 + 实时发现 | 既有端点 |
| IELTS | `/api/v1/ielts/…` | 仓库旁 `ielts-api/` Node 聚合器 | 每次请求起短命 `node ielts-cli.mjs` |
| **TOEFL** | **`/api/v1/toefl/…`（本文档）** | **仓库旁 `toefl-api/` Node 聚合器** | 每次请求起短命 `node toefl-cli.mjs`，JSON 原样透传 |

数据源头（公开可访问，遵守 robots 与限速）：

- `toefl.kmf.com`（考满分）——**唯一的「题干+选项+答案」源**，按需实时抓取并缓存到 `toefl-api/.data/`
  （2026-10-05 已对 read+listen 全量预抓取：450 条 / 3217 页；同日对 speak+write 全量预抓取：
  308 条 / 308 页——此后请求命中本地缓存；修复轮全量离线重解析 971/971 无新增失败、
  联网四科样本 4/4，见 §8/§9）；
- `SAOHPRWHG/FindSimilarTPO`（GitHub）——TPO 阅读原文 / 听力转写；
- `ddy-ddy/TOEFL-TPO`（GitHub）——TPO 30–54 结构化阅读（标题 + 段落）。

启动：

```bash
examdata serve --host 127.0.0.1 --port 8000
```

## 2. 快速调用（2026-10-05 本机实测，真实服务 + 真实源）

```bash
# ① 能力清单 / 索引
curl "http://127.0.0.1:8000/api/v1/toefl/info"
curl "http://127.0.0.1:8000/api/v1/toefl/coverage"

# ② 按「时间（编号分区）」与「形式（Section）」筛选套次
curl "http://127.0.0.1:8000/api/v1/toefl/sets?era=tpo-51-54&page-size=4"
curl "http://127.0.0.1:8000/api/v1/toefl/sets?tpo=54&section=listening"

# ③ 单套取题（或单 Section 元数据）
curl "http://127.0.0.1:8000/api/v1/toefl/get?set=tpo-30"
curl "http://127.0.0.1:8000/api/v1/toefl/questions?set=tpo-30&section=reading&item=1"
curl "http://127.0.0.1:8000/api/v1/toefl/questions?set=tpo-54&section=listening&item=1"

# ④ 关键词搜索（跨源）
curl "http://127.0.0.1:8000/api/v1/toefl/search?q=punctuated&limit=8"

# ⑤ 机经真题板块（/jj/order/27..30；索引 325 条 = 免费 213 + 锁定 112）
curl "http://127.0.0.1:8000/api/v1/toefl/jj"
curl "http://127.0.0.1:8000/api/v1/toefl/jj?section=speak&batch=25&free=1&list=1"
curl "http://127.0.0.1:8000/api/v1/toefl/jj?url=https%3A%2F%2Ftoefl.kmf.com%2Fdetail%2Fread%2F82df4j.html%2F1"

# ⑥ 单条详情（TPO 口写内容与机经通用；口写内容级入口）
curl "http://127.0.0.1:8000/api/v1/toefl/detail?url=https%3A%2F%2Ftoefl.kmf.com%2Fdetail%2Fspeak%2Ff1m9gj.html"
```

实测结果（证据落盘 `toefl-api/probe/live_evidence/`，12/12 校验通过）：

| 调用 | 结果 |
|---|---|
| `/api/v1/toefl/info` | 200，`schema:"toefl.v1"`，6 路由 / 8 eras（当时；jj 集成后 7 路由，见下行） |
| `/api/v1/toefl/coverage` | 200，FindSimilar 486 文件，TPO 范围 1–54 |
| `/sets?era=tpo-51-54&page-size=4` | 200，`total=4`，套次 `[54,53,52,51]` |
| `/get?set=tpo-30` | 200，阅读 3 项 / 听力 6 项，`sources` 含 3 源 |
| `/questions?set=tpo-30&section=reading&item=1` | 200，`complete:true`，10 题全量，原文 4456 字符 |
| `/questions?set=tpo-54&section=listening&item=1` | 200，`complete:true`，5 题 + mp3 音频直链 |
| `/search?q=punctuated&limit=8` | 200，`total_matches=11`，跨 4 源（ddy/find-similar/kmf-index/kmf-cache） |

2026-10-05 新增 jj 机经板块实测（真实服务 + 真实源，证据 `toefl-api/probe/jj_verify_20261005/`）：
`/jj` summary 200（325/213/112）；`/jj?section=speak&batch=25&free=1&list=1` 4 条；
`/jj?url=…/read/82df4j.html/1` 10/10 `complete:true`；`/jj?section=read&batch=5&locked=1&list=1`
2 条 locked（无 url）；`/search` 命中 `set_id:"jj-25"`；`/coverage` 含 `jj_index`；
边界（未知 section / batch 越界）→ 200+`ok:false`；`info` 含 jj 路由与 `kmf-jj` 源。

2026-10-05 新增口写 detail 实测（真实服务 + 真实源，证据 `toefl-api/probe/tpo_sw_20261005/`）：
`/detail` speak `f1m9gj` → `tpo-54`、"Official 54 Q 2"、题干+音频；write `c1m97j` → `tpo-54`、
材料/题干文本（范文不内嵌）；jj `52ds6j` → jj 元数据保留、无 `kmf_item`；非法 URL → 200+`ok:false`；
缺 `url` → 422 标准校验错误；`/search` 口写页归因 `tpo-54`（改前未归因）；`/info` 8 路由含 detail。

## 3. 路由清单（8 条）

| 路径 | 说明 |
|---|---|
| `/api/v1/toefl/info` | 能力清单（静态；schema、eras、路由、源、env） |
| `/api/v1/toefl/coverage` | 源覆盖自检（离线；逐 TPO 计数、缺口、重复） |
| `/api/v1/toefl/sets` | 按编号分区 / 编号范围 / Section 筛选套次（`tpo`、`era`、`section`、`tpo-min`、`tpo-max`、`page`、`page-size`） |
| `/api/v1/toefl/get` | 单套元数据视图（`set=tpo-N`，可选 `section`）；`file=<名>` 时返回 FindSimilarTPO 原文文件解析（网络+缓存，`refresh=1` 强制重抓） |
| `/api/v1/toefl/questions` | 逐题内容：`set=tpo-N`、`section=reading\|listening`、`item`（Passage/Set 序号）、`limit`（0=全部）、`refresh`、`url`（覆盖索引查找，高级用法） |
| `/api/v1/toefl/detail` | 单条详情页内容（`url` 必填、`refresh`）：TPO speak/write（题干+音频 / 材料文本）与机经通用；命中 kmf 条目时补 `kmf_item/label/official/set_id` |
| `/api/v1/toefl/search` | 关键词检索：`q`、`limit`（1–200）、`sources`（`ddy-ddy,find-similar-tpo,kmf-index,kmf-cache` 子集；机经免费条目并入 `kmf-cache`） |
| `/api/v1/toefl/jj` | 机经真题板块（`/jj/order/27..30`）：`section=read\|listen\|speak\|write`（空=汇总）、`batch`（期数）、`free`/`locked`、`list=1`、`page`/`page-size`；`url=<详情页>`（`refresh=1` 强制重抓）抓单条——read/listen 逐题全量，speak/write 题干/范文/音频 |

## 4. 返回契约

- **业务失败与成功同为 HTTP 200**：失败响应为 `{ok:false, board:"toefl", error}`。
  典型：未知 `section`、未收录的 `tpo-N`（如 tpo-99）、kmf 索引中没有对应条目。
- **只有基础设施错误用 HTTP 错误码**（错误体为 FastAPI `{"detail": …}` 形状）：

| 状态码 | 场景 |
|---|---|
| 503 | 找不到 `node`，或找不到 `toefl-cli.mjs`；并发排队超时 |
| 504 | 子进程超时（默认按路由 60–300s，可用 env 覆盖） |
| 502 | 子进程非零退出，或输出不是合法 JSON |

- 响应顶层补 `board: "toefl"`，便于跨考试局识别来源。
- `questions` 响应要点：`set.fetched`（实际抓到的题数）、`set.questions[]`（每题
  `{number, type, stem, options[], answer[], insert_sentence, analysis, audio_url}`）、
  `set.passage`（文章原文）、`set.audio_url`（听力音频，若有）。**部分页失败时
  `ok:true` 但 `complete:false` + `errors[]`**——不伪造全量。
- 完整性双口径（2026-10-05 修复轮）：`set.complete` = 抓取页数完整（fetched==expected 且
  errors 空）；`set.content_complete` = 可作答内容完整（另要求逐题必要字段齐备），
  缺口逐题列于 `set.content_gaps[]`（`{qid,label,type,missing[]}`）。二者分开表达，
  不再无条件 `complete:true`。
- 题目级字段（2026-10-05 修复轮，兼容既有契约）：
  - 听力表格题：`type:"table_choice"`，附 `table:{columns[], rows:[{label, answer}], answer_letters[]}`
    （行列文本与顺序按页面 DOM；`answer` 为逐行字母；顶层 `answer[]` 仍为同一字母序列）。
    不再标为普通 `multiple_choice`，多值答案不截断。
  - 阅读多选：`multi_select:true`（原有 `options[]/answer[]` 契约不变）。
  - 插入句子题：`type:"insert_sentence"` + `insert_sentence`（无选项，合法题型）。
- URL 校验（2026-10-05 修复轮）：`detail`、`jj?url=`、`questions?url=` 仅接受
  `https://toefl.kmf.com/detail/{read|listen|speak|write}/{hash}.html`（hash 为小写字母数字，
  可带实测存在的单个数字后缀如 `/1`）；拒绝 userinfo、非标准端口、其他协议/域名/IP、
  query/fragment 注入（均 200+`ok:false`）。重定向逐跳校验 origin/path、最多 5 跳，
  非法即失败。校验先于缓存读取（非法主机不会命中同 hash 缓存）。
- 缓存写入前内容校验（2026-10-05 修复轮）：speak 必须有题干节点（`item-desc`）、write 必须
  有题干节点（`content-subject`）才写缓存；维护页/登录页/错误页不写正式缓存、缓存命中时
  同样校验、不返回 `ok:true`。write 的 `essay` 可空、独立写作 `audio_url` 可空（非失败）。
- `speaking`/`writing` 已内容级覆盖（2026-10-05 口写轮）：用 `detail` 抓取——speak 返回
  题干+音频；write 返回材料/题干文本（范文不内嵌于静态页，如实为空）；`questions` 仍仅
  支持 `reading`/`listening`。

## 5. 时间与形式口径

- **时间**：TPO 无官方逐年发布日（不编造）。服务以 **TPO 编号 + 编号分区 era**
  表达；**可筛选 era 仅六个编号分区**（`tpo-01-10` … `tpo-51-54`）。`pre-2023-07` /
  `post-2023-07` 不再作为筛选值（`sets?era=pre-2023-07` → 200+`ok:false`），仅出现在
  info 的 `format_revision_reference`（格式改版参考说明）中，**不支持按它们映射套次**
  （无真实来源，不建立映射）。`get.exam_date` 恒为 `null` 并附 `exam_date_note`。
- **形式**：`section` 维度 = `reading` / `listening` / `speaking` / `writing`。

## 6. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `EXAMDATA_TOEFL_DIR` / `TOEFL_API_DIR` | `<repo>/toefl-api` | 聚合器目录（找不到时自动尝试 parents[3]、cwd） |
| `EXAMDATA_NODE` | 从 PATH 找 `node` | node 可执行文件 |
| `EXAMDATA_TOEFL_TIMEOUT` | 按路由 60–300s | 统一覆盖所有 TOEFL 子进程超时（秒） |
| `EXAMDATA_TOEFL_MAX_CONCURRENT` | 4 | 每个服务进程/事件循环同时执行的 TOEFL 子进程数（1–64） |
| `EXAMDATA_TOEFL_QUEUE_TIMEOUT` | 5s | 等待并发槽位超时返回 503（>0、≤60s） |

## 7. 覆盖范围（`toefl-api/data/*.json`，2026-10-05）

```
TPO 套次        52 套   1–54 中缺 26、31（所有主张源一致缺失）
FindSimilarTPO   486 文件  阅读 156 篇 + 听力 312 段（讲座 208 + 对话 104）
ddy-ddy          72 条   TPO 30–54 结构化阅读（31 缺）
kmf 索引         758 条   read 156 / listen 294 / speak 207 / write 101
逐题内容         reading/listening 已全量预抓取缓存（2026-10-05：450 条 / 3217 页，
                 `.data/cache/kmf/`；实测 0 失败，抽查 complete:true）；
                 speaking/writing 已内容级预抓取（2026-10-05 口写轮：308 条 / 308 页，
                 0 失败；speak 题干+音频、write 材料/题干文本，范文不内嵌）
jj 机经索引      325 条   read 50 / listen 125 / speak 100 / write 50（免费 213 / 锁定 112；
                 时间轴=期数 batch 1..25，站点无发布日/年份）
jj 详情缓存      免费 213 条已全量预抓取（213/213、796 题、0 失败，`.data/cache/kmf/`）
```

2026-10-05 复核：索引 758/758 与在线列表逐条一致；read+listen 缓存 450 条 / 3217 页完整
（缺页 0）；在线 vs 缓存 0 内容差异（**该轮 22 文件 / 6 组样本内**；见 `toefl-api/REPORT.md` 第九节）。
机经板块同日纯增量集成并实测通过（325 条索引、免费 213 全量缓存；见 `toefl-api/REPORT.md` 第十节）。
口写轮同日完成：speak+write 308 条全量内容预抓取（308/308 ok、0 失败）与 detail 表面纯增量上线，
实测通过（见 `toefl-api/REPORT.md` 第十一节）。
修复轮同日完成（见 §8 末段与 `toefl-api/REPORT.md` 第十二节）：全量离线重解析 971/971
（TPO 758 + 免费机经 213）无新增失败；缓存 4417 页内容校验 0 失败；证据 `toefl-api/repair-20261005/`。

## 8. 测试

契约测试文件 `tests/test_api_toefl.py`（15 例：离线 11 + live 4）已于 2026-10-05 按用户要求
彻底移除（不保留副本）；移除后 pytest 收集检查 exit=0、无引用残留。历史测试结果（离线 11 通过 + 4 跳过；live 15/15、exit=0；全量套件
0 失败、exit=0）留档于 `toefl-api/REPORT.md` 第七节，实跑服务证据（12/12）见
`toefl-api/probe/live_evidence/`；2026-10-05 复核轮（在线实拉对照、索引/缓存复算全部一致）
见 `toefl-api/REPORT.md` 第九节。

2026-10-05 jj 集成轮：验证全部为真实调用——CLI 6 组 + 网关 10 组（含边界），证据
`toefl-api/probe/jj_verify_20261005/`；全量 pytest 复跑 **1024 = 1018 通过 + 6 跳过、0 失败**
（exit=0），与基线一致；终态冒烟 7/7（`toefl-api/probe/jj_final_smoke_20261005/`）；
见 `toefl-api/REPORT.md` 第十节。

2026-10-05 口写轮：验证全部为真实调用——CLI 5 组 + search 复测 2 组 + 网关 10 组（含边界），
证据 `toefl-api/probe/tpo_sw_20261005/`（摘要 `validation.txt`）；search 回归逐字段 0 差异、
口写归因改善实测；本轮为纯新增改动（examdata 测试库无 toefl 引用），未复跑全量 pytest；
定稿后终态冒烟 4/4（`toefl-api/probe/final_smoke_20261005/`）；见 `toefl-api/REPORT.md` 第十一节。

2026-10-05 修复轮：安全/内容/表格/身份四类修复，验证——CLI 矩阵 59/59（含 10 类非法 URL × 3
命令、era/身份 18 例）；HTTP 流程 30 用例中 28 个真实用例全过（独立端口 8125、私有临时 DB，
含负向与 locked url=null 校验）；全量离线重解析 971/971（TPO 758 + 免费机经 213）无新增失败，
14 道听力表格题逐项 14/14（代表页 11dwej 四行答案 B A A B）；缓存 4417 页内容校验 0 失败；
专项受控 localhost 零请求 24/24 与重定向逐跳校验 10/10；联网四科样本 4/4（refresh=1，串行
≥1.1s）+ 音频 Range 206×3（1KB 样本，未完整下载）。全量 pytest 退出码 **1**（1185 =
1178 通过 + 6 跳过 + 1 失败；唯一失败 `tests/test_api.py::test_provenance_coverage_is_complete`
为既有/不相关候选，未修）。证据 `toefl-api/repair-20261005/`（`REPAIR_REPORT.md` + `evidence/`）；
见 `toefl-api/REPORT.md` 第十二节。

## 9. 合规与限制

- 只聚合公开页面（kmf robots 允许列表与详情页）；登录/付费墙内容不做。
- 抓取限速为**单进程内** ≥1100ms 请求间隔（`THROTTLE_MS=1100`，≈≤1 req/s，进程级状态）；
  多进程/多实例并发不共享该节流，**未做跨进程压测**（文档中各处「1 req/s」均指此口径）。
- 原始源站上限（2026-10-05 修复轮复核）：Official 最高 **54**（无 55+）；列表页第 12–13 页
  为 404（站点本身到此为止）；页面无逐年/考试季节元数据；kmf 静态页不内嵌写作范文、
  听力无转写文本（转写仅 FindSimilarTPO 对部分 TPO 提供）。
- 验证口径（2026-10-05 修复轮）：**全量复算为离线缓存重解析**（TPO 758 + 免费机经 213，
  971/971 无新增失败）；**联网验证为四科各一项样本**（refresh=1，4/4 + 音频 Range 206×3），
  非「全量在线」。不宣称支持 2026 新版全题库。
- 版权试卷/题目原文只进本地缓存（`toefl-api/.data/`）与探针目录（`probe/`），
  两者已列入 `toefl-api/.gitignore`，不提交进 git。
- 逐题解析依赖 kmf 页面静态结构；结构变化时降级为 `ok:false`（不伪造成功）。
- 2023-07 改版后新题型（学术讨论写作等）材料在现有源中缺位，如实标注。
- `search` 的内容级检索范围：ddy 结构化阅读全文 + 标题/标签 + kmf 缓存内容。
  read+listen 全量（450 条 / 3217 页）与 speak+write 全量（308 条）已于 2026-10-05 预抓取入缓存，
  即全部已抓内容均可检索（口写页经 hash 映射归因到 `tpo-N`）；
  解析文本侧车缓存（`.data/cache/kmf/text/`）使全量检索热跑约 6s。
- 机经板块（`/jj/`）仅抓免费条目（213）；锁定 112 无公开 URL，不抓取、如实标注 `url:null`；
  robots 允许 `/jj/` 与 `/detail/`；内容仅进 `.data/` 与 `probe/`（已 gitignore）。
