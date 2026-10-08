# TOEFL 题库聚合与 API 集成报告（toefl-api）

- 日期：2026-10-04/05（探测与首轮实现；2026-10-05 复核轮见第九节、机经轮见第十节、口写轮见第十一节）
- 目标服务：`examdata`（FastAPI，`/api/v1` 统一网关）
- 新增聚合器：`toefl-api/`（Node ≥18，零 npm 依赖，对标 `ielts-api/ielts-cli.mjs`）
- 约束：纯增量（既有文件唯一改动 `src/examdata/api/app.py` 注册 4 行：import + 2 行注释 + include_router，无删改）；业务失败 `ok:false` + HTTP 200；
  只聚合公开可访问源（遵守 robots 与限速）；版权试卷原文不提交进 git。

## 一、任务与验收

在 `examdata` 中新增 `/api/v1/toefl/…`，覆盖四类能力：

1. 能力清单/索引（info）
2. 按「考试时间」（TPO 编号 / 分代 era）与「考试形式」（阅读/听力/口语/写作）筛选的套次列表（sets）
3. 单套（或分 Section / 分项）取题（get）
4. 关键词搜索（search）

外加：`coverage`（覆盖自检）与 `questions`（kmf 逐题题干/选项/答案/解析，实时抓取+本地缓存）。

验收：既有 pytest 全绿且 CIE/Edexcel/IELTS 端点行为不变；真实 HTTP 实测四类能力并留证；
新增离线契约测试 + `EXAMDATA_TEST_LIVE=1` live 测试；报告与 `examdata/docs/TOEFL_API.md` 齐备；
覆盖数字以实际抓取为准，禁止探活/样例冒充全量。

## 二、方法与合规

- robots.txt 逐一检查（2026-10-04）：
  - `toefl.kmf.com`：仅 `Disallow: /admin/`、`/record` → 其余公开页可抓；抓取限速 1 req/s（索引构建）。
  - `top.zhan.com`：`Disallow: /*?*` → 含查询串的路径全部禁止，不纳入自动聚合（见源 5）。
  - GitHub raw：公开仓库原始文件，无 robots 限制。
- 抓取均为公开页面，不使用登录/付费墙内容；kmf 的「官方解析」有登录门槛的会话功能不做；
  静态 DOM 内可见的解析文本按页面原样解析（页面公开可见，CSS blur 不改变可达性）。
- 版权：仓库只提交元数据（标签、URL、篇目标题、段落数、字符数）；试卷/题目原文只进本地缓存
  （`toefl-api/.data/`，已 gitignore），不进 git。

## 三、源探测结论（逐源）

### 1. SAOHPRWHG/FindSimilarTPO（GitHub，master）——可用（原文类）
- 内容：TPO 1–54 阅读原文（`data/TPO/{n}-{1..3}.txt`）、听力讲座 `L{n}-{1..4}.txt`、对话 `C{n}-{1..2}.txt`。
- 实测非空计数：阅读 **156**、听力 **312**（讲座 208 + 对话 104）；TPO 26、31 全部为空（与 kmf 缺失一致）。
- 格式：阅读=标题行+段落实文；听力=说话人标签（NARRATOR/MALE PROFESSOR…）+ 转写实文。
- 无题目、无答案。
- 重复内容对（6 组，已在 coverage.json 标注）：C17-1=C17-2、L3-3=L3-4、13-1=13-3、6-3=7-1、C27-1=L27-1、C52-2=L52-2。
- raw 前缀：`https://raw.githubusercontent.com/SAOHPRWHG/FindSimilarTPO/master/`。

### 2. ddy-ddy/TOEFL-TPO（GitHub，master）——可用（结构化阅读）
- 内容：`data/json/tpo-30-35.json` 等 5 个文件，TPO 30–54 阅读 **72** 条（TPO 31 缺失；example.json 除外），全部非空。
- 条目：`{id:"tpo-30-1", title, link(kmf), article:[段落…]}`；链接指向 kmf 同篇。
- 交叉校验：72 条中 71 条的 kmf link 哈希与 kmf 索引标签一致；`tpo-38-1` 的 link 实际指向 Official 38 Passage 2（ddy 侧错位，已记录；实现以 kmf 索引标签为准）。

### 3. toefl.kmf.com 考满分——可用（唯一「题目+答案」源）
- robots 宽松；sitemap 50,333 URL（read 22,101 / listen 16,729 / speak 7,182 / write 3,645）。
- 列表页（`/read/ets/order/{n}/0`、`/listen/ets/new-order/{n}/0`、`/speak/ets/`、`/write/ets/order/{n}/`）
  以 `data-detail` + `data-title` 标注「Official N Set/Passage/Task」——可枚举全部 ETS Official 条目。
- 详情页静态 HTML 含：文章原文（`js-stem-cont`）、题干（`question-title`）、选项（`answers-radio`/`options-sn`）、
  正确答案（`ShowAnswer`/「正确答案: X」）、部分解析（`analytical-detail`，部分带登录提示）。
- 索引构建结果（本仓库 `tools/build_kmf_index.py`，1 req/s，2026-10-04）：
  - **758** 条：read 156、listen 294、speak 207、write 101；Official **1–54** 中缺 26、31（与源 1 一致）。
  - 分布：read 每套 3；listen 34 套×6 + 18 套×5（27–30、41–54 为 5）；speak 51 套×4 + Official 8 为 3；write 49 套×2 + Officials 9/14/24 为 1。
- 阅读详情页逐题分页：同一文章页含 Q1 与 Q1–Q10 的跳转链接，每题一个 `/detail/read/{hash}.html`；
  逐题页含该题全量静态数据。听力详情页（`/detail/listen/{hash}`）含整组题目与「正确答案: X」。
- 口语/写作详情页：speak 页静态含题干（`p.item-desc`）与音频直链；write 页含 Task 1 阅读/听力
  材料文本与 Task 2 题干（范文不内嵌于静态页，如实为空）。2026-10-05 以 `detail` 命令/路由
  纯增量补齐内容级覆盖（见第十一节），`questions` 命令维持 reading/listening。

### 4. scottpedia/TpoExtractor（GitHub）——低价值候选
- 567 个 md（418 listenings + 118 passages），内容为纯文本且文件名只有标题、无 TPO 编号；
  Windows 非法文件名致 checkout 失败（须 `git ls-tree`/`git show` 读取）。README 自述为第三方 App 数据库导出（CC-BY-NC-SA）。
- 结论：不纳入主链路（无编号无法对应套次），记录为候选。

### 5. top.zhan.com（小站）——排除
- robots `Disallow: /*?*`；其题目发现路径（paper 列表/paper 页）全为查询串 URL。
- 无查询串的 review 页内容为小站自编 C-Test 式 10 空，非 TPO 真题。
- 结论：以 robots 合规为由不纳入自动运行时聚合（探测产物留档 `probe/zhan_*.html`）。

### 6. 其他候选（未深挖，记录）
- testdaily.cn、toefl.xdf.cn、ETS 官网：仅首页级别产物，未发现可直接聚合的结构化题库入口。
- GitHub 其它仓库：`wsdindin/tpo` 等为空壳/无关（contents 探测为空），不纳入。

## 四、覆盖数字（实测口径）

| 源 | 范围 | 数量 | 是否有题/答案 |
| --- | --- | --- | --- |
| FindSimilarTPO | TPO 1–54 阅读原文 | 156 篇（26、31 空） | 无（仅原文/转写） |
| FindSimilarTPO | TPO 1–54 听力转写 | 312 项（讲座 208 + 对话 104） | 无 |
| ddy-ddy | TPO 30–54 结构化阅读 | 72 条（31 缺） | 无（原文+标题） |
| kmf 索引 | Official 1–54 | 758 条（read 156/listen 294/speak 207/write 101） | 题干+选项+答案（read+listen 已全量预抓取） |
| kmf 逐题缓存（预抓取轮 2026-10-05） | Official 1–54 read+listen 全部条目 | 450 条 / 3217 页（`.data/cache/kmf/`，不进 git） | 题干+选项+答案+解析（0 失败） |
| kmf 口写缓存（口写轮 2026-10-05） | Official 1–54 speak+write 全部条目 | 308 条 / 308 页（`.data/cache/kmf/`，不进 git） | speak 题干+音频（207 条全有）；write 材料/题干文本（101 条，其中 49 条含听力材料音频）（0 失败） |

「考试时间」口径：TPO 无官方逐年发布日（禁止编造），服务以 **TPO 编号 + 编号分代 era** 表达，
并在 info 中给出 iBT 形式变更参考表（2005 iBT 上线 / 2019-08 缩短 / 2023-07 新制）。
本批源的主体是改版前材料，2023-07 后（学术讨论写作等）材料缺位——如实标注。

## 五、架构

```
examdata/src/examdata/api/toefl.py   FastAPI 网关（纯代理，spawn node）
toefl-api/toefl-cli.mjs               CLI（命令 → stdout JSON；未知命令 exit 2）
toefl-api/lib/*.mjs                   实现模块（sources/github、kmf、catalog、search、jj、detail）
toefl-api/data/coverage.json          FindSimilarTPO 逐项清单（元数据）
toefl-api/data/ddy-index.json         ddy-ddy 阅读索引（标题/段数/链接）
toefl-api/data/kmf-index.json         kmf Official 清单（标签/URL）
toefl-api/data/jj-index.json          机经真题板块索引（325 条，含免费/锁定标记）
toefl-api/tools/*.py                  数据构建工具（索引/覆盖，需网络时 1 req/s）
toefl-api/tools/prefetch_kmf.mjs      kmf 逐题全量预抓取（断点续跑，1 req/s）
toefl-api/tools/prefetch_jj.mjs       jj 免费条目预抓取（断点续跑，1 req/s）
toefl-api/tools/prefetch_kmf_sw.mjs   kmf TPO 口语/写作详情预抓取（断点续跑，1 req/s）
toefl-api/.data/                      运行时缓存（gitignore；含 kmf 抓取原文）
```

CLI 命令：`info`、`coverage`、`sets`、`get`、`questions`、`search`、`detail`、`jj`。
网关路由：`/api/v1/toefl/{info,coverage,sets,get,questions,detail,search,jj}`；
env：`EXAMDATA_TOEFL_DIR`/`TOEFL_API_DIR`、`EXAMDATA_NODE`、`EXAMDATA_TOEFL_TIMEOUT`、
`EXAMDATA_TOEFL_MAX_CONCURRENT`、`EXAMDATA_TOEFL_QUEUE_TIMEOUT`。

## 六、限制与已知缺口

1. 无官方逐年日期：时间维度=编号+era，非发布年份；源提供日期时才填 `exam_date`（当前为空）。
2. TPO 26/31 在所有主张源中均缺失；FindSimilarTPO 6 组重复已在清单标注。
3. kmf 逐题抓取依赖第三方页面结构，解析器按其静态 DOM 编写；结构变化时降级为 `ok:false`（不伪造）。
4. 口语/写作已内容级覆盖（口写轮 2026-10-05：speak 题干+音频、write 材料/题干文本；
   写页范文不内嵌于静态页，如实为空）；2023-07 后新题型材料缺位。
5. ddy-ddy 个别 link 与标签不一致（`tpo-38-1`），以 kmf 索引标签为准。
6. `search` 的内容级检索范围：ddy-ddy 结构化阅读全文 + 各源标题/标签 + kmf 缓存内容。
   预抓取轮后 kmf read+listen 全量（450 条 / 3217 页）已入本地缓存；口写轮后 speak/write
   全量（308 条）亦入缓存并可检索（口写页经 hash 映射归因到 `tpo-N`，未映射页从 1 → 0）；
   解析文本侧车缓存（`.data/cache/kmf/text/`）使全量页面检索热跑约 6s。

## 七、测试与实测记录（随轮次更新）

基线（2026-10-05，本机 venv）：
- [x] examdata 既有 pytest 基线：**986 用例 = 981 通过 + 5 跳过，0 失败**，exit=0
  （pytest -q 汇总行缺失，计数按用例点号统计；日志 `probe/examdata_pytest_baseline.log`）
- [x] 探测：robots/列表页/详情页结构取证（probe/*.txt、*.html 留档）
- [x] 索引构建：kmf 758 条、coverage 156+312、ddy 72 条（tools/*.py 可复跑）
- [x] 离线契约测试：`pytest tests/test_api_toefl.py` → **11 通过 + 4 跳过**（live 未开）
  （info/ok:false 透传/node 缺失 503/目录缺失 503/超时 504/本地索引通道）
- [x] live 测试：`EXAMDATA_TEST_LIVE=1 pytest tests/test_api_toefl.py` → **15/15 通过**，exit=0
  （日志 `probe/examdata_pytest_toefl_live.log`）
- 注（2026-10-05）：`tests/test_api_toefl.py` 已按用户要求彻底移除（不保留副本）；
  上述两条为移除前历史结果，移除后复核见第九节。
- [x] 真实 HTTP 四类能力实测：实跑 `examdata serve :8123`，12 端点全部 200，
  结构与计数校验 **12/12**（证据 `probe/live_evidence/`，汇总 `_validation.json`）
- [x] 全量 pytest 第 1 轮（含新文件，after）：**1010 = 1001 通过 + 9 跳过，0 失败，exit=0**
  （日志 `probe/pytest_full_after.log`）
- [x] 全量 pytest 第 2 轮（当前树最终复跑）：**1030 = 1021 通过 + 9 跳过，0 失败，exit=0**
  （日志 `probe/pytest_full_final.log`）
- 用例数对账（986 → 1010 → 1030，均为逐文件数点统计）：
  - +9：`tests/test_api_timetable.py`（并行工作，00:18 落盘，非本任务）
  - +15：`tests/test_api_toefl.py`（**本任务**，00:29 落盘；2026-10-05 按用户要求移除）
  - +20：`tests/test_api_materials.py`（并行工作，00:34 落盘，非本任务）
  - 结论：本任务净增 = 15 例（仅新增文件）；汇总行因 `addopts="-q"` 叠加命令行 `-q` 为 `-qq`
    被静音，故按用例点（`.`/`s`）逐文件统计（`probe/collect_now.txt`）
- [x] 当前树终检（2026-10-05）：`EXAMDATA_TEST_LIVE=1 pytest tests/test_api_toefl.py` →
  **15/15 通过，exit=0**（`probe/pytest_toefl_live_final.log`）；同一现行 app 实例经
  TestClient 复核对照端点 `/health`（papers=1517）、`/papers`、`/taxonomy`、
  `/api/v1/ielts/info` 与 TOEFL 能力路由（info/coverage/get/sets/search）全部 200
  （证据 `probe/live_evidence/current_tree_control.json`；所涉测试文件于当日复核轮移除，见第九节）

预抓取轮（2026-10-05，kmf 逐题内容全量入缓存 + 搜索解析文本侧车）：
- [x] 预抓取：新工具 `tools/prefetch_kmf.mjs` 对 kmf read+listen 全部 **450 条**
  （listen 294 + read 156）逐条抓取，**3217 页**全部落盘（`.data/cache/kmf/pages/`）；
  **ok=450 / incomplete=0 / failed=0 / errors=[]**；条目 fetched 合计 **3217** 道题；
  全程 1 req/s、58.9 分钟、可断点续跑（日志 `probe/prefetch_kmf.log`、状态 `probe/prefetch_kmf_status.json`）
- [x] 取题抽查（纯缓存命中，抓取后页面目录零新增写入）：`tpo-54` listen item1 → 4.9s、
  `complete:true` 5/5 题；`tpo-30` read item1 → 4.6s、`complete:true` 10/10 题（原文 4456 字符）
- [x] 搜索解析文本侧车（`lib/search.mjs`：文本落 `.data/cache/kmf/text/`，页面更新时自动重建）：
  全量 3217 页下 **冷跑 12.1s（建齐侧车）/ 热跑 6.0s**，`unmapped_pages=[]`、命中 url 全非空、
  total_matches=11 与历史一致；中途 632 页两跑 6.4s/5.5s 并证实侧车复用（旧侧车 mtime 不变）
  （`probe/tmp_search_cold.json`、`probe/tmp_search_warm.json`）
- [x] 回归复跑：离线 **11 通过 + 4 跳过**（`probe/pytest_toefl_offline_after_prefetch.log`）；
  live **15/15 通过，exit=0**（`probe/pytest_toefl_live_after_prefetch.log`）；
  全量套件 **1030 = 1021 通过 + 9 跳过、0 失败、exit=0**（`probe/pytest_fullsuite_after_sidecar.log`；
  与预抓取并行运行，离线用例不依赖缓存数据状态）

实测关键数字（真实服务 + 真实源；详见 probe/live_evidence/）：

| 能力 | 调用 | 实测 |
| --- | --- | --- |
| 索引 | /info | schema=toefl.v1，6 路由 / 8 eras |
| 覆盖 | /coverage | FindSimilar 486 文件；TPO 1–54（52 套） |
| 时间筛选 | /sets?era=tpo-51-54 | total=4 → [54,53,52,51] |
| 形式筛选 | /sets?tpo=54&section=listening | 仅 listening（1 套） |
| 单套 | /get?set=tpo-30 | 阅读 3 / 听力 6，源含 3 家 |
| 取题（阅读） | /questions?set=tpo-30&section=reading&item=1 | complete=true，10/10 题，原文 4456 字符 |
| 取题（听力） | /questions?set=tpo-54&section=listening&item=1 | complete=true，5/5 题 + mp3 |
| 搜索 | /search?q=punctuated&limit=8 | total_matches=11，跨 4 源 |
| 对照组 | /health、/papers、/taxonomy、/api/v1/ielts/info | 全部 200，行为不变 |

集成期修复（写入修改计划并已执行）：
- CLI 契约加固：未知 `--section` 原为异常退出码 1 → 现 `ok:false`（退出码 0）；
  `get --set=tpo-99` 原返回空壳 `ok:true` → 现按「未收录」`ok:false`（不伪造）。
  两项均由 `tests/test_api_toefl.py` 离线用例固化（该文件已于 2026-10-05 按用户要求移除，
  修复本身不受影响）。

git 状态口径说明（2026-10-05）：
- `examdata` 工作区在本任务开始前就存在大量未提交改动（IELTS 网关等前序工作，
  47 文件），不属于本任务；本任务对既有文件的唯一改动 = `src/examdata/api/app.py`
  **纯增量 4 行**（`from .toefl import router as toefl_router` + 2 行注释 +
  `app.include_router(toefl_router)`），无任何既有行被修改或删除（该文件 diff 已留存
  `probe/live_evidence/app_py.diff`）。其余交付均为新文件（toefl-api/、tests/test_api_toefl.py、
  docs/TOEFL_API.md）；其中 tests/test_api_toefl.py 已于 2026-10-05 按用户要求彻底移除
  （不保留副本）。
- `toefl-api/` 不在任何 git 仓库内（仓库根 `api/` 无 .git）；已补
  `toefl-api/.gitignore`（`.data/`、`probe/`），保证金源版权原文不会被提交。
- 集成期并行工作核对（2026-10-05）：仓库内并行工作自 00:36 起也修改了 `app.py`
  （materials/timetable 路由注册，非本任务）；本任务注册经复核仍在（`import` 第 55 行、
  注释 + `include_router` 第 76–78 行），现行 app 实例 TestClient 实测
  `/api/v1/toefl/info` → 200；对照快照 `probe/live_evidence/app_py_current.diff`。

## 八、修改计划清单（随轮次勾选）

- [x] R0 源探测与索引构建（2026-10-04）
- [x] R1 toefl-api CLI + 数据文件（info/coverage/sets/get/questions/search；离线+联网实测）
- [x] R2 网关 toefl.py + app.py 纯增量注册（+4 行，无删改）
- [x] R3 tests/test_api_toefl.py：离线 11 通过 + live 4 通过（15/15，exit=0）；
      文件于 2026-10-05 按用户要求彻底移除（不保留副本）
- [x] R4 examdata 全量 pytest 绿（1010 / 1030 两轮均 0 失败、exit=0；对账见第七节）
- [x] R5 真实服务四类能力实测留证（12 端点 200；校验 12/12）
- [x] R6 docs/TOEFL_API.md + 本报告实测数字回填
- [x] R7 git 核对：app.py 纯增量无删改（diff 留档）；无 commit/push/reset
- [x] R8 kmf 逐题全量预抓取（450 条 / 3217 页，0 失败）+ 搜索解析文本侧车缓存
      （冷 12.1s → 热 6.0s）；离线/live/全量套件全部复跑绿（对账见第七节）
- [x] R9 2026-10-05 复核轮：在线实拉对照（0 内容差异）、索引/缓存复算（758/758、
      450/450、3217/3217）、年份/季节结论、jj 板块核查（记录不集成）、测试文件移除
      （收集检查 exit=0）——详见第九节
- [x] R10 2026-10-05 机经轮：`/jj/` 四科 325 条纯增量集成（免费 213 条预抓取 0 失败、
      jj 命令/路由/索引、search 归因）——详见第十节
- [x] R11 2026-10-05 口写轮：kmf TPO speak/write 全量 308 条内容预抓取（0 失败）+ 新
      detail 表面（CLI 命令 + 网关路由，纯增量）+ search 口写归因修复 + coverage 自检
      字段（`speaking_writing_cached`）——详见第十一节

## 九、2026-10-05 复核轮（实际拉取核查 + 测试文件移除）

背景：用户要求对已交付题库做「实际联网拉取」核查（完整性、年份、考试季节），发现问题才修改；
测试文件不保留。本轮证据落盘 `probe/livecheck_20261005/`（22 文件）、`probe/verify_*_20261005.*`、
`probe/pytest_full_after_removal.log`。

### 9.1 在线实拉对照（1 req/s）

- 重新在线拉取四 section 列表页（含第 11/12 页）、read/listen 详情页样例、难度筛选视图、
  jj 板块 5 页等共 22 个文件；与本地缓存归一化对照（`probe/verify_live_vs_cache_20261005.py`）：
  **6/6 组归一化后 0 差异行、0 行数差**——仅 csrf-token、GLOBALNAME（会话 hash）、
  做题人数（±1）等动态字段不同（read_p1、listen_p1/p2/p10、detail read/listen）。
- 最高 Official = **54**（四个 section 列表页首屏一致），**无 55+**；第 12–13 页在线仍为 404
  （站点点位到第 11 页为止；缓存中 16 个 12/13 页文件同为 404）。
- Official 54 Set 5、50 Set 3、10 Set 3 等缺套在**在线列表页本身**即不存在（live 与缓存一致）
  → 缺套为站点自身状态，非索引遗漏。难度筛选视图（官方难题）为「全部」视图的严格子集。

### 9.2 索引与缓存复算（离线，可复跑）

- `probe/verify_index_vs_cache_20261005.mjs`：重解析全部 44 个含条目列表页缓存 vs
  `data/kmf-index.json` → **758/758 一致**；「列表页有、索引无」= 0；「索引有、列表页无」= 0；
  无重复 URL；无不符合 Official 标签模式的条目。
- `probe/verify_cache_recompute_20261005.mjs`：read+listen 全量 450 条逐条重算 →
  **450/450 完整**、expected 3217 = fetched 3217、缓存缺页 0；与 `probe/prefetch_kmf_status.json`
  （ok=450 / questions_fetched=3217）一致；pages 3217 文件 = text 3217 文件。
- 复核澄清：`lib/catalog.mjs perOfficial()` 的 read/listen 计数为三源合并（coverage.json
  FindSimilar + ddy + kmf），非单一 kmf 计数；kmf 侧贡献与索引一致（read 每套 3、listen 5–6）。

### 9.3 年份 / 考试季节维度（结论）

- kmf 页面**无逐年 / 季节元数据**：时间信息仅「Official N Set M」编号与两处改版注记
  （2019-08-01 听力口语改版 ×33、2023-07-26 写作改版 ×11）；季节词仅出现于听力文章正文，非元数据。
- 维持既有口径（与 TOEFL_API.md 第 5 节一致）：时间维度 = TPO 编号 + era 分区
  （另给 pre/post-2023-07 改版参考），`exam_date` 恒为 null、不编造。→ 无需修改。

### 9.4 新发现：`/jj/` 学而思听力机经真题板块（记录；同日集成见第十节）

- `https://toefl.kmf.com/jj/order/28`：听力「机经真题 1–25 × Set 1–5」共 **125 条**，
  5 页 × 25（p1=1–5、p2=6–10、p3=11–15、p4=16–20、默认视图=21–25）。
- **85 条免费**（静态含 `/detail/listen/` 链接：批次 1、10、11–25），**40 条付费锁定**
  （批次 2–9，`js-lock-jj`「限时99元解锁」，匿名态无链接）；免费详情页结构与常规听力
  详情页一致、匿名可见（含正确答案/解析标记）。
- 与主索引 **URL 零重叠**（85/85 均为索引外）；页面无日期。
- 判定：属独立「机经」（学而思品牌）收藏，非 ETS Official TPO 历年真题，不在本次
  「历年托福题库（Official 1–54）」范围内 → 记录为发现；如后续需要纳入，属范围扩张，另行评估。
  证据 `probe/livecheck_20261005/jj_*`、`jj_overlap_check.txt`。
- **后续（同日）**：该板块（四科 325 条）已按用户要求以纯增量方式集成，见**第十节**。

### 9.5 测试文件移除（用户要求）

- `examdata/tests/test_api_toefl.py`（本任务新增 15 例契约测试）已移除；未保留副本
  （含备份）。既有其它测试文件未动；probe/ 证据与日志保留。
- 移除后核查：全库无代码/配置引用残留；`pytest tests/ --collect-only` **exit=0、0 错误**
  （1024 例收集，`probe/tmp_collect_after_removal.txt`）。
- 全量套件复跑（移除后）：**1024 = 1018 通过 + 6 跳过，0 失败**（无 F/E 标记；
  `probe/pytest_full_after_removal.log`）；与旧基线 1030 的差额 = 本任务 −15 +
  并行工作 +9（timetable 9→10、paperqa_locator 35→43，非本任务）。

### 9.6 复核结论

已交付题库完整：索引 758/758 与在线列表一致、缓存 450 条 / 3217 页全部完整、
在线与缓存归一化后 0 差异；年份/季节维度无源可依、文档口径如实；**无需修改服务代码**。
本轮变更仅为文档更新（本报告 + TOEFL_API.md）与测试文件移除（不保留副本）。

## 十、2026-10-05 机经真题板块（`/jj/order/27..30`）纯增量集成

背景：9.4 记录的学而思「机经真题」板块（四科 325 条）本轮按用户「只增加内容，不修改
现有服务」的约束完成集成：新增独立模块/索引/命令/路由；既有命令、路由、字段行为零变化
（逐字段核对见 10.4）。以托福的**考试形式**（四科 × 科内条目）与**时间轴**（机经期数）组织。

### 10.1 板块结构与计数（实测）

- 入口：`https://toefl.kmf.com/jj/order/27..30`（27=阅读、28=听力、29=口语、30=写作）；
  每板块 5 页 × 25 条，默认视图=最新（期数 25）。
- 共 **325 条**：read 50（25 期 × Passage 1–2）/ listen 125（25 期 × Set 1–5）/
  speak 100（25 期 × Q 2/3/4/6）/ write 50（25 期 × Task 1–2）。
- 免费 **213** / 锁定 **112**；锁定边界（实测，含边界列表）：
  read/speak/write = 期数 1 与 11–25 免费、2–10 锁定；listen = 期数 1 与 10–25 免费、2–9 锁定。
  锁定条目匿名态无 `data-detail`、无详情 URL → 不抓取、不伪造（`locked:true` 如实标注）。
- **时间维度**：站点未提供发布日/年份 → 以**机经期数 batch 1..25（25 最新）**为时间轴，
  索引 `time_dimension` 字段如实注明「批次即时间维度」。**考试形式**：`section`=四科，
  `item`=科内条目（Passage/Set/Q/Task）。
- 与既有 kmf 758 条索引 URL/hash **零重叠**（独立收藏板块）。

### 10.2 新增文件（全部为增量）

| 文件 | 说明 |
|---|---|
| `tools/build_jj_index.py` | 抓取四板块列表页（4×5 页）解析 → `data/jj-index.json`；含 counts.per_section、batches_free/locked、lock_note、time_dimension |
| `data/jj-index.json` | 索引产物：325 条（section/url/label/batch/kind/num/item/locked/data_id/page） |
| `lib/jj.mjs` | jj 模块：索引读取、hash 映射（213 入口 + 已缓存入口页逐题 tab 反查）、筛选/分页、缓存统计、详情抓取（read/listen 复用 `fetchKmfSet`；speak/write 整页提取题干/范文/音频直链） |
| `tools/prefetch_jj.mjs` | 免费条目详情预抓取（1 req/s；写 kmf 共用缓存 `.data/cache/kmf/{pages,text}`） |

### 10.3 既有文件增量修改清单（逐处）

| 文件 | 改动 | 对既有行为的影响 |
|---|---|---|
| `lib/kmf.mjs` | `pageCachePath` 正则 `(read\|listen)` → `(read\|listen\|speak\|write)`（1 行） | 无：`fetchKmfSet` 仅传 read/listen |
| `lib/search.mjs` | ① import jj 映射；② `pageHash` 正则加 speak/write；③ `searchKmfCache`：section 识别加 speak/write 前缀、`kmfMetaForPage` 未命中时回退 jj 映射（`set_id=jj-N`、`item`=机经标签、`url`=jj 详情）、section 用四科标签 | 对 read/listen 且命中 kmf 索引的页面：set_id/tpo/section/item/url/field **逐字段同旧值**；仅在旧值为 null/文件名的未映射页上新增 jj 归因 |
| `toefl-cli.mjs` | 新增 `jj` 命令（无参数=summary；`--section/--batch/--free/--locked/--list` 列表；`--url` 详情）；usage、info commands/sources、coverage 加 `jj_index` | 既有命令不变 |
| `examdata/src/examdata/api/toefl.py` | 新增 `/api/v1/toefl/jj` 路由；`/info` 路由表 +1 行、sources +1 行（kmf-jj） | 纯新增；既有 6 路由与行为不变 |

### 10.4 预抓取（免费 213 条）

- `node tools/prefetch_jj.mjs`：**213/213 成功、0 失败、0 不完整、累计 796 题**；
  耗时 16.2 分钟（09:49→10:06，1 req/s）。状态 `probe/prefetch_jj_status.json`（errors=[]）。
- 构成：read 32 篇（10 题/篇全量=320 题）+ listen 85 套（5–6 题/套=476 题）+ speak 64 + write 32。
- jj 页面与常规 kmf 页面同构、共用缓存目录 → `search` 的 kmf-cache 源自动纳入机经内容。

### 10.5 实测验证（全部真实调用；证据 `probe/jj_verify_20261005/`）

CLI（`node toefl-cli.mjs`）：
- `jj` → summary：counts 325/213/112 + per_section 边界 + cache 统计（01-summary.json）。
- `jj --section=listen --batch=25 --free=1` → 5 条（Set 1–5，URL 齐全）（02）。
- `jj --url=…/speak/52ds6j` → 题干 + 音频 + 整页文本；`…/write/22dsaj` → 范文 + 音频；
  `…/read/82df4j.html/1` → 10/10 题 `complete:true`（03–05）。
- `search --q="brought back from the Moon during the Apollo" --sources=kmf-cache` → 命中
  `set_id:"jj-25"`、`item:"机经真题25 Passage 1"`、`url`=jj 详情页（06）——机经可检索且归因正确；
  逐题页（每篇 Passage 的 Q1–Q10 各为独立页面 ID）经 tab 反查同样归因到同一 jj 条目。
- 回归：`search --q=punctuated` → 常规页仍归 `tpo-30` 等（19-search-regression.json），无影响。

网关（`examdata serve` :8123；curl 实测后已停）：
- `/info` 含 jj 路由与 `kmf-jj` 源；`/jj` summary 200；`?section=speak&batch=25&free=1&list=1` 4 条；
  `?url=…read…` 10/10 `complete`；`?section=read&batch=5&locked=1&list=1` 2 条 locked（url=null）；
  `search` 命中 jj-25；`coverage` 含 `jj_index`；分页 `list=1&page=2&page-size=5` 正常（08–15、17）。
- 边界：`section=bogus`、`batch=999/0` → HTTP 200 + `ok:false`（业务失败语义与既有端点一致）（16）。

### 10.6 测试与基线

- 按用户要求不保留测试文件；本板块验证全部为真实调用（10.5）。
- examdata 全量 pytest（本板块改动后复跑）：**1024 = 1018 通过 + 6 跳过，0 失败**
  （exit=0；日志 `probe/jj_verify_20261005/18-pytest-full.log`）——与移除测试文件后的基线
  （见 9.5，1024 = 1018 + 6）完全一致，无退化。
- 终态验收（2026-10-05 10:28，服务 :8124）：对最终交付状态重跑端到端冒烟 **7/7 通过**
  （info 7 路由含 jj / jj summary 325-213-112 / read 详情 10/10 / speak 列表 4 条 /
  search 命中 jj-25 / 回归 tpo-30 / coverage 含 jj_index；证据 `probe/jj_final_smoke_20261005/`，
  校验摘要 `08-validation.txt`）。

### 10.7 限制与合规

- 锁定 112 条无公开 URL，不抓取；响应中 `locked:true` 如实标注。
- 逐题页 tab 反查映射为「先到先得」：同一文章被多期复用时归因取索引中先出现者（边缘情况，
  不影响检索可用性）。
- robots 复验：`/jj/`、`/detail/` 均允许（仅禁 `/admin/`、`/record`）；1 req/s 限速；
  版权内容只进 `.data/` 与 `probe/`（已 gitignore），不提交进 git。
- 学而思「机经」为第三方整理收藏（非 ETS 官方逐年真题）；文档如实标注来源与时间口径。

## 十一、2026-10-05 口写轮（TPO 口语/写作内容级补齐）

背景：第九/十节后，四科中 read/listen 已内容级覆盖（450 条 / 3217 页），speak/write 仍为
「仅索引级」。本轮按用户「只增加内容，不修改现有服务」约束补齐：预抓取 kmf TPO
speak+write 全量 **308 条** 详情内容，并以纯增量方式新增 `detail` 表面（CLI 命令 + 网关路由）。

### 11.1 可抓性与内容边界（实测）

- speak 详情页（如 `/detail/speak/f1m9gj.html`）：静态含题干（`p.item-desc`）与音频直链；匿名可抓。
- write 详情页（如 `/detail/write/c1m97j.html`）：含 Task 1 阅读/听力材料文本与 Task 2 题干；
  **范文不内嵌于静态页**（`js-good-composition` 为空占位），如实为空、不伪造。
- TPO 口写页无 `js-top-title` → 无法用既有标签解析归因；本轮以 kmf 索引 hash 映射补齐归因。

### 11.2 实现清单（全部纯增量）

新增：

| 文件 | 说明 |
|---|---|
| `lib/detail.mjs` | `fetchKmfDetail({url,refresh})`：URL 校验（四科 hash）→ kmf 索引查表 → 复用 `fetchJjDetail` 抓取 → 命中 kmf 条目时补 `kmf_item/label/official/set_id`；jj 页保持 jj 元数据 |
| `tools/prefetch_kmf_sw.mjs` | kmf TPO speak+write 全量预抓取（断点续跑、1 req/s、每 5s 日志；状态 `probe/prefetch_kmf_sw_status.json` 含逐条明细） |

既有文件增量修改（逐处）：

| 文件 | 改动 | 对既有行为的影响 |
|---|---|---|
| `toefl-cli.mjs` | 新增 `detail` 命令（`--url` 必填、`--refresh`）；usage/info 注释与 `exam_forms.note` 同步 | 既有命令不变 |
| `lib/search.mjs` | `hrefHash` 正则 `(?:read\|listen)` → `(?:read\|listen\|speak\|write)`；tab 反查循环改为按前缀分派（speak/write 无逐题页→`[]`） | read/listen 归因逐字段同旧值；speak/write 页由「未归因（文件名）」变为正确归因 |
| `lib/catalog.mjs` | `coverageSummary()` 的 kmf 源新增 `speaking_writing_cached`（按索引 URL 对应缓存页存在性计数）+ 1 行 note | 纯新增字段 |
| `examdata/src/examdata/api/toefl.py` | 新增 `/api/v1/toefl/detail` 路由（`url` 必填、`refresh`，超时 240s）；`/info` 路由表 +1 行、`exam_forms.note` 与 sources 同步 | 纯新增；既有 7 路由与行为不变 |

### 11.3 预抓取（308 条，0 失败）

- `node tools/prefetch_kmf_sw.mjs`：**308/308 ok、0 empty、0 failed、errors=[]**；
  speak 207 + write 101；耗时约 5.6 分钟（1 req/s）。
- 与 `data/kmf-index.json` 交叉核对：0 缺失 / 0 失败 / 0 多余；308/308 有缓存页。
- 构成：speak 207 条全有题干+音频（text_len 5452–9232）；write 101 条（49 条含听力材料
  音频；text_len 5379–11106）；官方覆盖 1–25、27–30、32–54（26/31 为索引级缺失）。
- 缓存写入 kmf 共用目录（`.data/cache/kmf/`，不进 git）。

### 11.4 实测验证（全部真实调用；证据 `probe/tpo_sw_20261005/`，摘要 `validation.txt`）

CLI（`node toefl-cli.mjs`）：
- `detail --url=…/speak/f1m9gj` → tpo-54、"Official 54 Q 2"、题干+音频+kmf_item（01）；
  `…/write/c1m97j` → tpo-54、text 10802（04）；`…/write/21m98j` → "Official 54 Task 2"（08）。
- jj 回归：`…/speak/52ds6j` → jj 元数据保留（batch 25）、无 kmf_item（02）；
  非法 URL → `ok:false`、exit 0（03）。
- search 归因改善：`--q="childhood is the best time"` 命中由未归因（`speak-f1m9gj.html`，
  `set_id:null`）→ `tpo-54` / "Official 54 Q 2"，`unmapped_pages` 1 → 0（06 vs 00）。
- search 回归：`--q=punctuated` 5 条命中与基线**逐字段 0 差异**、total_matches 21=21；
  仅扫描页数 4112 → 4417（+305 新页，纯增量）（07 vs 00）。

网关（`examdata serve` :8124；curl 实测后已停）：
- `/info` 8 路由含 detail、note 已更新（10）；`/detail` speak/write/jj/bogus 四例全部符合
  预期（11–14）；缺 `url` → HTTP 422 标准校验错误（19）。
- 回归：`/questions?set=tpo-30&section=reading&item=1` 10/10 题（15）；
  `/jj?section=speak&batch=25&free=1&list=1` 4 条（16）；`/search` 两例与 CLI 一致（17/18）。
- `coverage` 自检：`speaking_writing_cached: {"indexed":308,"cached":308}`（预抓取完成后）。

文档定稿后终态冒烟（`probe/final_smoke_20261005/`）：`/info` 8 路由含 detail、
`/detail` speak → tpo-54/"Official 54 Q 2"/题干+音频、`/search?q=punctuated` 21 命中、
`/questions?set=tpo-30&section=reading&item=1` 10/10 题——**4/4 通过**。

### 11.5 测试与基线

- 按用户要求不保留测试文件；本轮验证全部为真实调用（11.4）。
- 本轮仅改 `toefl.py`（纯新增路由）与 toefl-api 侧新文件/1 行式扩展；examdata 测试库无
  toefl 引用（grep 0 命中），既有全量基线（1024 = 1018 + 6，见 9.5）不受影响，未复跑。

### 11.6 限制（如实标注）

- TPO 写页范文不内嵌 → detail 仅返回材料/题干文本（范文如空，不伪造）。
- write 页 `audio_url` 为听力材料音频（Task 1 综合写作），非口语音频。
- Official 26/31 口写条目在 kmf 索引缺失（索引级上限，非本轮抓取失败）。
- 时间维度维持既有口径：TPO 编号 + era 分区（无官方逐年发布日）。

