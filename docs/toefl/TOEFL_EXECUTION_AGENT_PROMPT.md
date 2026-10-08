# 可直接复制给执行 Agent 的提示词（TOEFL）

下面横线之间为完整提示词（逐字复制自执行期规格 `toefl-api/AGENT_FIX_PROMPT_20261005.md`，该文件与本次会话用户提示词一致）。本目录三份文件（本提示词、`TOEFL_REPAIR_IMPLEMENTATION_PLAN.md`、`TOEFL_COMPLETENESS_AUDIT_20261005.md`）必须保持在相同目录；执行 Agent 应能访问整个工作区及已保存的本地证据。

配套阅读：审计报告副本 `docs/toefl/TOEFL_COMPLETENESS_AUDIT_20261005.md`（原 `toefl-api/AUDIT_REPORT_20261005.md`）与统计证据 `toefl-api/audit-20261005/`。执行结果见本目录 `TOEFL_IMPLEMENTATION_RESULT.md`、`EXECUTION_CHECKLIST.md`、`TOEFL_REMAINING_GAPS.md`。

---

# 给执行 Agent 的完整提示词

你在 Windows PowerShell 工作区 `C:\Users\weo\Desktop\api` 执行托福 API 修复。按下面顺序完成，不自行扩大任务。先阅读 `toefl-api/AUDIT_REPORT_20261005.md` 和 `toefl-api/audit-20261005/{cache-summary,flow-summary,audio-summary,cleanup-manifest}.json`。报告里的实际反例是任务依据；旧 REPORT.md 的 done 标记不是验收证据。

## 1. 边界与准备

允许修改 `toefl-api/lib/*.mjs`、`toefl-api/toefl-cli.mjs`、必要的 `toefl-api/tools`、`examdata/src/examdata/api/toefl.py`、`examdata/docs/TOEFL_API.md`、`toefl-api/REPORT.md`。不得改 CIE、Edexcel、IELTS 实现，不得操作既有服务、数据库、绑定或密钥。不得 commit/push，不安装依赖，不抓登录或付费内容。

先检查适用 AGENTS.md、Python/Node 路径和可用端口。用脚本记录上述允许文件的修改前 SHA256，并记录 CIE/Edexcel/IELTS 关键模块 SHA256，在结束时复核。根目录可能不是 Git 仓库，不依赖 git diff。必要备份只备份将修改的业务文件，放专用工作目录；不备份已要求删除的测试下载物。

建立 `toefl-api/repair-20261005/` 保存计划、统计和最终报告；临时测试程序与下载物放它下面单独的 `runtime/`，最终删除 runtime。不要覆盖独立审查证据。

## 2. 修复 URL 校验和缓存写入

实现共用详情 URL 解析器，在 detail、jj、questions 的用户 URL 输入以及低层 fetchPage 前调用。只接受 `https://toefl.kmf.com`，禁止用户名密码、非标准端口、其他协议/域名/IP。路径须完整匹配 `/detail/(read|listen|speak|write)/[a-z0-9]+.html`，兼容现有索引中确实存在的 `/1` 等数字后缀；先统计实际路径再确定允许后缀。拒绝多余后缀、query/fragment 注入，除非源索引有可核实的必要用例。内部 tab 相对路径先用可信 origin 解析，再校验。

不要靠 substring、includes 或只禁 localhost。校验必须发生在读业务缓存之前，防止非法主机命中相同 hash。禁止自动跟随未校验重定向；每一跳都校验目标 origin/path，限制最多五跳，失败返回 ok:false。GitHub 原文 fetch 的合法用途与 kmf 详情校验分开处理。

使用受控 localhost HTTP 服务验证非法 URL 请求数为零；恶意主机但合法 hash 不得读取现有缓存；校验合法来源无需访问敏感地址。覆盖 userinfo、子域伪装、非 HTTPS、端口、片段中的合法路径、跨主机重定向。合法缓存和合法原站详情必须继续工作。

对 speak/write 内容在写缓存之前验证必要结构。阅读/听力也拒绝明显错误页。口语必须有实际题干；写作必须有明确材料/题干节点，不得用整页 text 非空判成功。根据当前真实 HTML 确定提取节点，保留原返回字段兼容性，可新增结构化字段和缺口标记。写作 essay 可空、独立写作 audio 可空；这些空值不是失败。合法页面结构不可识别时明确失败并保留统计，不编造题干。

已有缓存命中也要验证内容，错误页不得返回 ok:true。HTTP 200 维护页、登录页、无题干页需复现并拒绝，不能把这些写入正式缓存。仅清除本次测试创建的缓存键；既有可疑缓存先列清单和来源，修复时仅针对已证实无效项，不全删业务缓存。

## 3. 修复听力表格题

以 cache-summary.answer_gaps 列出的 14 个 URL 逐项读取业务缓存，检查 table.content-logic、行列文本、true-answer 和 data-type；不要猜 A/B 对应顺序。

新增明确的表格题表示，保存列、行和按行对应的答案，顺序以 DOM 为准；兼容已有 options/answer 契约，在文档说明新增字段。修复题型判断，不能把表格题标为普通 multiple_choice。多值答案不能只截取首个字母。

代表页 listen/11dwej.html 的四行 Yes/No 题必须保留全部行列、四个答案 B A A B。其余 13 页逐条复核，验证答案数量与行数匹配、答案落在合法列范围。不得用题干长度或答案非空替代这两个检查。

修正完整性：抓取页数完整和可作答内容完整分别可表达；必要选项/表格/答案缺失必须暴露 errors 或 content_complete=false，不能无条件 complete=true。原本无选项的合法题型按题型判断，不一刀切要求 options 非空。

在禁止网络的模式下重解析全部 TPO 758 和免费机经 213，确认不新增失败，14 项得到正确结构；记录总题数、按题型缺口与逐项结果。不得编造源站没有的解析/答案。

## 4. 修复筛选与身份

info 中可筛选 era 仅保留 catalog 真正实现的六个编号分区。pre/post-2023-07 移到格式改版参考说明，明确不支持按它们映射套次。sets 对未知 era 返回 HTTP 200 + ok:false，不能返回成功的空列表。CLI/HTTP info 同步改，exam_date 保持 null。没有真实来源就不建立改版套次映射。

set 只接受整个字符串 `tpo-N`，N 为正整数；tpo/tpo-min/tpo-max 只接受完整十进制整数，随后按收录范围处理。明确拒绝 garbage54、tpo-540、tpo-54junk、54.5、负值、混杂文本；不存在的合法身份返回业务失败。对 CLI 和 HTTP 同时验证，不改变合法 tpo-30/tpo-54 调用。

## 5. 完整复测

使用独立空闲端口，例如 8125。若被占用另选空闲端口，不停止别人的服务。子进程只由本次启动并记录 PID，finally 中终止并 wait。临时数据库使用 sqlite 内存或 runtime 私有路径，不接生产数据目录。

先跑临时离线回归，覆盖上述安全/内容/表格/身份/era 反例和合法调用。不能仅断言 HTTP 200/ok:true；检查科目关键字段、题目数、答案结构和归因。

HTTP 依次执行 info→coverage→sets(tpo-51-54,section)→get(tpo-54)→questions(read tpo-30全部、listen tpo-54全部)→detail(speak f1m9gj、write c1m97j)→search(punctuated与口语题干独特短语)→jj汇总→免费四科详情→locked列表。验证 locked 项 url=null，不抓锁定内容。CLI 的八个命令各执行一次。负向用例包含缺url=422、非法url/section/era/set=200+ok:false。

联网调用串行，网络请求开始时间间隔至少 1.1 秒。四科各用一项 Official 54 详情 refresh=1；read/listen 不设 limit，应拉全部题，检查完整性；记录真正联网和缓存调用的区别。对 listen/speak/write 返回音频地址各做一次 Range 验证，保存状态、类型、字节数、hash，音频正文不落正式目录。不是完整下载/试听就如实写样本验证。

任一源请求出现 403/404/409/502、超时或解析失败，保存 URL/状态/时间/阶段并停止剩余联网测试；不重试、不换镜像、不加 force、不访问锁定条目。可以继续离线修复和统计，报告联网阻塞，不能写全通过。

运行 examdata 全量 pytest：在 `examdata` 下用 `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，PYTHONDONTWRITEBYTECODE=1，EXAMDATA_TEST_LIVE=0。保留退出码和最终汇总。若失败，逐条确认与修改的关联；仅修允许范围内且有证据关联的托福问题，其他问题列为既有/不相关候选，不改其他模块。不把没有 toefl 测试引用当作免跑回归理由。

## 6. 文档、清理与最终交付

更新 TOEFL_API.md 和 REPORT.md，把所有“完整”“零差异”“1 req/s”“全量在线”宣称限定到实际证据范围。缓存全量复算、联网四科样本、原始源站上限、缺年份/考试季节、缺范文/转写、未做跨进程压测都分别写清。不要宣称支持 2026 新版全题库。

写 `repair-20261005/REPAIR_REPORT.md`：每个问题的根因、改动文件、修前反例、修后结果、精确数量、失败/跳过/未验证项，以及全量 pytest 汇总。写 `repair-20261005/evidence-summary.json`：只留元数据、统计、来源 URL、hash、测试退出码，不留题目原文/下载音频。

最后删除 runtime 中所有临时测试代码、fixture、原始抓取响应、音频和私有测试数据库；删除本次生成的 orphan pyc 和本次 pytest 临时产物。不得删除其他模块的已有测试、正式工具、原始第三方源、data 索引、.data 业务缓存、独立审查报告和统计证据。递归删除前解析绝对路径并确认 runtime 位于 `C:\Users\weo\Desktop\api\toefl-api\repair-20261005\runtime`；用 PowerShell 原生 LiteralPath 删除。

输出清理 manifest（具体路径、类别、数量、剩余检查）、复核非托福模块哈希一致、確認本次服务端口关闭。文档定稿后再跑四项无需新下载的终态冒烟 info/detail/search/questions。若出现新失败修复后再复跑受影响项。

最终答复只写：修复项与实际验证结果、未完成项/阻塞原因、报告和证据路径、清理结果、是否提交。只在上述验收均达到时写完成；否则明确有条件完成或未完成。不要停在计划或能力说明。

---

执行结果：S01–S06 全部完成（2026-10-05）。修复结果见 `TOEFL_IMPLEMENTATION_RESULT.md`，逐步状态与证据见 `EXECUTION_CHECKLIST.md`，未完成/未验证项与源站边界见 `TOEFL_REMAINING_GAPS.md`。
