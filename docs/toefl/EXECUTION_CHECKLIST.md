# TOEFL 修复执行清单（S01–S06）

- 任务：按 `docs/toefl/TOEFL_REPAIR_IMPLEMENTATION_PLAN.md` 执行 S01–S06；解决 `docs/toefl/TOEFL_COMPLETENESS_AUDIT_20261005.md` 所列 P1-01、P1-02、P1-03、P2-01、P2-02、P2-03。
- 执行日期：2026-10-05（北京时间）；执行期目录 `toefl-api/repair-20261005/`（临时物在 `runtime/`，已按 S06 删除）。
- 治理说明：本会话按用户显式流程执行（任务规格 `toefl-api/AGENT_FIX_PROMPT_20261005.md`）；工作区根与 `toefl-api/` 非 git 仓库，`examdata/` 为既有 git 仓库（只读记录，未改其历史）。
- 状态枚举：pending / running / done / partial / blocked。
- 每步固定字段：id、status、files、command、exit_code、evidence、gaps、next_action。

## 总览

| id | 标题 | status | 关键证据 |
|----|------|--------|----------|
| S01 | 基线、备份、受保护文件清单 | done | `repair-20261005/hashes-before.json`、`backup/`（11 文件） |
| S02 | URL 校验与缓存写入修复（P1-01、P1-02） | done | `evidence/cli-matrix-after.txt`（59/59）、`evidence/zero-request.json`（24/24）、`evidence/redirect-validation.json`（10/10）、`evidence/validate-scan.json`（4417+971） |
| S03 | 听力表格题修复（P1-03） | done | `evidence/reparse-diff-summary.txt`、`evidence/reparse-diff.json`（971 入口、14 表格题、0 新增失败） |
| S04 | 筛选与身份修复（P2-01、P2-02） | done | `evidence/cli-matrix-after.txt`、`evidence/http-flow-after.json`、`evidence/cli-info-after.json` |
| S05 | 完整复测 | done | `evidence/http-flow-after.json`（30 cases）、`evidence/live-samples.json`、`evidence/pytest-full.log`（exit 1；1178 pass + 6 skip + 1 fail） |
| S06 | 文档、清理与最终交付（P2-03） | done | `cleanup-manifest.json`、`evidence/hashes-compare-final.txt`、`evidence/final-smoke-post-cleanup.json`（5/5） |

---

## S01. 基线、备份、受保护文件清单

- id: S01
- status: done
- files:
  - 新增 `toefl-api/repair-20261005/hash_files.py`（SHA256 记录/对比；区分 `[allowed]` 允许修改文件与 `[control]` 控制文件）
  - 新增 `toefl-api/repair-20261005/hashes-before.json`（34 文件 = 19 允许 + 15 控制）
  - 新增 `toefl-api/repair-20261005/backup/**`（11 个待改业务文件备份，保持相对路径）
  - 新增 `toefl-api/repair-20261005/{PLAN.md,evidence/,runtime/}`
- command:
  - `python toefl-api/repair-20261005/hash_files.py record`（修前基线）
  - 备份：将 7 个目标文件 + 相关 lib/tools 复制到 `backup/`（保持相对路径）
  - 环境侦察：`node --version`（v24.19.0）、`examdata/.venv/Scripts/python.exe --version`（3.14.7）、`netstat` 查端口 8125 空闲
- exit_code: 0
- evidence:
  - `hashes-before.json`：19 个 `[allowed]`（7 个最终修改 + lib/catalog、detail、search、sources、tools 等未改文件）+ 15 个 `[control]`（CIE/Edexcel/IELTS 关键模块）
  - `backup/`：11 文件（7 个最终修改文件的修前副本 + 相关控制副本）
  - `evidence/probe-read-gap.txt`、`probe-listen.txt`、`probe-speak.txt`、`probe-write*.txt`、`calibration.json`、`calibration-text.json`：修前探针与解析器校准
- gaps: 无。备注：根目录非 git 仓库 → 以哈希 + 备份替代 git diff；`examdata` 仓库状态只读记录（分支 main、HEAD d8e64a6）。
- next_action: S02（URL 校验与缓存写入修复）

---

## S02. URL 校验与缓存写入修复（P1-01、P1-02）

- id: S02
- status: done
- files:
  - `toefl-api/lib/kmf.mjs`：新增 `parseKmfDetailUrl`/`isKmfDetailUrl`/`resolveKmfHref`/`kmfRedirectValidator`/`validateKmfContent`；`fetchPage` 改为"先校验 URL → 缓存命中也要验内容 → 联网响应验内容后才写缓存"
  - `toefl-api/lib/util.mjs`：`httpGet` 手动重定向跟随（每跳 `validateRedirect`、`maxRedirects=5`、相对 Location 先解析再校验、缺 Location 报错）
  - `toefl-api/lib/jj.mjs`：`jjHashOf`/`fetchJjDetail` 改用严格解析器
  - `toefl-api/toefl-cli.mjs`、`examdata/src/examdata/api/toefl.py`：detail/jj/questions 入口校验
- command:
  - 后缀与路径形态统计（`evidence/url-stats.json`、`evidence/suffix-scan.txt`）：kmf 758 无后缀 / jj 32 条 `/1` / 缓存 4417 文件无其它形态 / tab 相对路径两种形态
  - `node runtime/zero_request_test.mjs`（受控 localhost 服务；runtime 已删除）
  - `node runtime/redirect_test.mjs`（重定向逐跳校验；runtime 已删除）
  - `node runtime/cli_matrix.mjs`（CLI 59 用例；runtime 已删除）
  - 全量校验扫描（971 索引 URL + 4417 缓存页；runtime 已删除）
- exit_code: 0（全部）
- evidence:
  - `evidence/cli-matrix-after.txt`：59 pass / 0 fail（含 10 类非法 URL × detail/jj/questions + 合法对照）
  - `evidence/zero-request.json`：24/24 pass，`localhostHits=0`（非法 URL 请求数=0；恶意主机+真实缓存 hash 不读缓存；合法 cache-hit 正常）
  - `evidence/redirect-validation.json`：10/10 pass（5 跳成功、6 跳拒绝、跨主机拒绝且恶意主机未被 fetch、http 降级拒绝、相对路径接受、缺 Location、非详情路径、userinfo、query 注入、fetchPage 不写缓存）
  - `evidence/validate-scan.json`：缓存 4417 页（listen 2133/read 1880/speak 271/write 133）内容复检 0 失败；索引 758 kmf + 213 jj（非锁定；锁定 112 url=null）严格解析 0 失败
  - `evidence/url-stats.json`：修前审计复现记录（`http://127.0.0.1:60413/detail/speak/auditprobe20261005.html` → `ok:true`、`cache_written:true`）作为修前反例对照
- gaps: 未做真实源站恶意重定向演练（源站未返回跨主机重定向；以 monkey-patch fetch 模拟）；维护页/登录页拒绝为本地构造 + 缓存级验证；节流为单进程内 `THROTTLE_MS=1100`，非跨进程全局保证。
- next_action: S03（听力表格题修复）

---

## S03. 听力表格题修复（P1-03）

- id: S03
- status: done
- files:
  - `toefl-api/lib/kmf.mjs`：`parseListenTable`（表格题解析）、`isMultiSelectForm`（阅读多选）、`content_complete`/`content_gaps` 完整性字段；`fetchKmfSet` 不再无条件 `complete=true`
  - `examdata/src/examdata/api/toefl.py`、`examdata/docs/TOEFL_API.md`：新增字段透传与文档
- command:
  - 14 个 URL 逐项读取业务缓存（`audit-20261005/cache-summary.json` `answer_gaps`）核对 `table.content-logic`、行列文本、`true-answer`、`data-type`
  - 禁网全量重解析（TPO 758 + 免费机经 213 = 971 入口；runtime 临时脚本已删除）
  - 代表页双查：索引条目 `listen/914lxj.html` 与审计 URL `listen/11dwej.html`
- exit_code: 0
- evidence:
  - `evidence/reparse-diff-summary.txt` / `reparse-diff.json`：entries 971→971、`new_failures=0`、`changed_entries=34`（14 表格题 type+answer + 20 阅读多选 n_options）、`changed_questions=48`、`table_questions=14`、`table_problems=0`、`assert_11dwej` 双查 4 行 B A A B、`audit_url_checks` 14/14 ok、`unexpected=0`、essay 字符差异 0
  - 14 道逐项（qid/答案）：75647 B A A A B；67531 B A B B；66386 B A C B；68017 A B B A A；67977 B A A B A；67831 A A B A B；67742 A B A A A B；64674 A B A B；64673 A B A A B；64672 B A A A B；64671 B A A B B B；64670 B A A B；64680 A B A A；64669 B A C B
- gaps: 无。备注：答案数量=行数、字母落在列范围内为强制检查项；未编造任何源站没有的解析/答案。
- next_action: S04（筛选与身份修复）

---

## S04. 筛选与身份修复（P2-01、P2-02）

- id: S04
- status: done
- files:
  - `toefl-api/toefl-cli.mjs`：`info` eras 仅六分区 + `format_revision_reference`；`normSet`/`normTpo`/`normTpoRange` 整串严格解析
  - `examdata/src/examdata/api/toefl.py`：HTTP `/info` 同步；`/sets` 未知 era → HTTP 200 + `ok:false`；set/tpo 整串严格解析；`exam_date` 保持 null
- command:
  - CLI 矩阵 59 用例（含 18 个 era/身份用例；runtime 已删除）
  - HTTP 流程（独立端口 8125）含 6 个负例
- exit_code: 0
- evidence:
  - `evidence/cli-matrix-after.txt`：`sets --era=pre-2023-07`/`post-2023-07`/`bogus` 全部 `ok:false`；`--tpo=garbage54/54.5/54junk/-3/0`、`--tpo-min=5.5` 拒绝；`get --set=garbage54/tpo-540/tpo-54junk/54.5/tpo--5/tpo-0` 拒绝（tpo-540 为业务失败"未收录"）；`tpo-30`/`tpo-54` 对照仍成功
  - `evidence/cli-info-after.json`：eras=[tpo-01-10,tpo-11-20,tpo-21-30,tpo-31-40,tpo-41-50,tpo-51-54]、`format_revision_reference`、`exam_date=null`
  - `evidence/http-flow-after.json`：负例（era/set/section）全 `ok:false`；HTTP 与 CLI 一致
- gaps: 无。备注：pre/post-2023-07 仅作格式改版参考说明，不支持按它们映射套次；未建立无真实来源的改版套次映射。
- next_action: S05（完整复测）

---

## S05. 完整复测

- id: S05
- status: done
- files: 无代码改动（纯验证）；临时测试程序与私有 DB 在 `runtime/`（已删除）
- command:
  - 离线回归（安全/内容/表格/身份/era 反例 + 合法调用；runtime 已删除）
  - HTTP 流程：独立端口 8125、私有临时 DB（`runtime/http-flow-test.db`）；子进程记录 PID（63128）并在 finally SIGTERM 终止
  - CLI 八命令各执行一次（info/coverage/sets/get/questions/detail/search/jj）
  - 联网四科样本（串行、起始间隔 ≥1.1s；四科各一项 Official 54 详情 `refresh=1`；read/listen 不设 limit）
  - 音频 Range：`bytes=0-1023` × 3（listen/speak/write）
  - examdata 全量 pytest：`examdata` 下 `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`、`EXAMDATA_TEST_LIVE=0`
- exit_code:
  - 离线/HTTP/CLI/联网：0；音频 206×3
  - pytest：**1**（1185 例 = 1178 pass + 6 skip + 1 fail；唯一失败 `tests/test_api.py::test_provenance_coverage_is_complete`，判定既有/不相关候选，未修）
- evidence:
  - `evidence/http-flow-after.json`：30 cases = 28 真实用例全 PASS / 0 FAIL（2 项元数据）；含 info→coverage→sets→get→questions（read tpo-30 全 10/10、listen tpo-54 全 5/5）→detail（speak f1m9gj q=125；write c1m97j prompt=142 essay=0）→search（punctuated 21 hits；口语独特短语 1 hit）→jj 汇总与四科详情→locked 列表（18 条全 `url=null`）；负例：缺 url=422、非法 url/section/era/set=200+ok:false；cache-mtime-diff changed=0 added=0；server-shutdown 记录
  - `evidence/cli-matrix-after.txt`：59/59
  - `evidence/live-samples.json`：min_gap_ms=1150、`failure=null`；read 11m4mj 10.5s 10/10；listen 11mc6j 4.9s 5/5；speak f1m9gj 522ms qlen=125；write c1m97j 564ms；纯缓存复跑四科 ok 88–110ms；音频 3×206 `audio/mpeg` 1024B（总长 47646/183065/4611734；sha256 在文件内）
  - `evidence/pytest-full.log`：完整进度与失败详情（exit 1）
- gaps:
  - pytest 唯一失败为既有/不相关候选（审计轮未改业务代码时同一失败；`/provenance/coverage` 通用接口不经 TOEFL 路由），按边界未修 → 见 `TOEFL_REMAINING_GAPS.md` G2。
  - 未做跨进程并发压测；音频仅 1KB Range 样本（非完整下载/试听）；联网为四科各一样本（非全量在线对照）。
- next_action: S06（文档、清理与最终交付）

---

## S06. 文档、清理与最终交付（P2-03）

- id: S06
- status: done
- files:
  - `examdata/docs/TOEFL_API.md`、`toefl-api/REPORT.md`：口径修订（新增字段文档、era 说明、URL 校验与合规限制；"完整/零差异/1 req/s/全量在线"限定到证据范围）
  - `toefl-api/repair-20261005/REPAIR_REPORT.md`、`evidence-summary.json`、`cleanup-manifest.json`
  - 清理：删除 `repair-20261005/runtime`（48 文件/3.1M）与 `.terminal-smoke`（5 文件/520K）；删除 orphan pyc（`toefl.cpython-314.pyc` 两实例）
- command:
  - `python toefl-api/repair-20261005/hash_files.py compare`（终态哈希复核）
  - PowerShell `Resolve-Path` 核对 → `Remove-Item -LiteralPath '...\runtime' -Recurse -Force`；`.terminal-smoke` 同法；pyc `Remove-Item -LiteralPath ... -Force`
  - 终态冒烟（独立端口 8125、私有临时 DB、全走缓存）：info / get tpo-54 / detail speak f1m9gj / search punctuated / questions tpo-30 read
  - `netstat` 复核端口 8125 无监听
- exit_code: 0（compare / 清理 / 冒烟全部 0；冒烟 5/5 PASS）
- evidence:
  - `evidence/hashes-compare-final.txt`：恰好 7 个 `[allowed]` 差异（本轮修复的 7 文件），**0 个 `[control]` 差异**
  - `cleanup-manifest.json`：删除项（路径/类别/数量/方法/删除后复核）、未删项（`.pytest_cache` 并发会话产物、4417 缓存页、`audit-20261005/`、其他模块）、剩余检查（缓存页数 4417、audit 文件数、控制哈希、端口、终态冒烟）
  - `evidence/final-smoke-post-cleanup.json`：5/5 PASS、EXIT=0、port 8125、server pid=66336 SIGTERM 终止；`evidence/final-smoke.json` 首轮同结果（pid=61360）
  - `REPAIR_REPORT.md`、`evidence-summary.json`：最终报告与证据汇总（仅元数据/统计/来源 URL/hash/退出码）
- gaps: 无阻塞。备注：`examdata/.pytest_cache/` 因并发会话产物未动（本修复 pytest 用 `-p no:cacheprovider` 且 conftest 自清理，未写入）；`.data` 业务缓存全量保留（4417 页，无经证实无效项需清除）。
- next_action: 无（S01–S06 全部完成；后续推进项见 `TOEFL_REMAINING_GAPS.md`）
