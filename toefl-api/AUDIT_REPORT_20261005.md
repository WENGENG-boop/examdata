# 托福 API 独立重复审查报告

审查日期：2026-10-05（北京时间）。工作区：`C:\Users\weo\Desktop\api`。

## 结论

**有条件通过，不能接受“全部核验通过、所有任务已完成”的最终验收结论。**

四科内容入口、机经免费内容、CLI 与 HTTP 网关的基本流程可用；本轮强制联网抓取四科代表条目成功。但是发现 URL 校验缺失、错误页面假成功、14 道听力表格题内容丢失、两项 era 筛选不可用等问题。当前只能确认第三方索引范围内的缓存覆盖与代表样本的联网可用性，不能确认每题答案完整、源站全量内容实时一致或生产并发安全。

本轮只审查、测试和清理，没有修复业务代码，没有提交。后续修复任务见同目录 `AGENT_FIX_PROMPT_20261005.md`。

## 本轮证据与方法

- `audit-20261005/cache-summary.json`：禁用网络后，对全部 TPO 758 条和免费机经 213 条逐条调用当前详情解析代码；记录缓存缺口、解析失败、题干/答案字段与异常条目。
- `audit-20261005/flow-summary.json`：独立本地 HTTP 服务上的流程结果与 8 个 CLI 命令的退出码、内容长度、数量、响应 SHA256。原始响应已在汇总后清理。
- `audit-20261005/audio-summary.json`：对联网返回的 3 条音频地址发送 Range 请求，记录状态、类型、样本字节数和 SHA256，不保留下载音频。
- 全量 pytest 结果见本报告末尾“整体回归终态”；不能引用此前日志替代本次结果。
- 清理文件明细与终态见 `audit-20261005/cleanup-manifest.json`。保留统计、日志和来源信息，删除临时执行脚本和探针原文；业务 `.data` 缓存及源索引保留。

旧报告仅作为待验证主张。特别是旧 `verify_live_vs_cache_20261005.log` 只列出 4 个列表页和 2 个详情页的归一化比较，**不能据此声称所有 758 条在线内容与缓存逐条零差异**。

## 覆盖复算

| 项目 | 本轮结果 | 能证明的范围 |
|---|---|---|
| TPO 索引 | read 156 / listen 294 / speak 207 / write 101，共 758 | 本地索引内容；本轮未重新爬取全部在线列表 |
| 免费机经 | read 32 / listen 85 / speak 64 / write 32，共 213 | 免费索引范围；锁定内容不抓取 |
| 缓存 | HTML 4417 页；971 个入口无缺失 | 文件存在且当前代码可解析，不等于语义完整 |
| 读听题 | 4013 道，题干空值 0 | TPO 3217 道 + 机经 796 道 |
| 答案与选项 | 14 道 TPO 听力题两者均为空 | 全部有源表格和源答案，属于解析器漏支持 |
| 口写 | 全部索引条目可读取；口语 question 非空，写作 text 非空 | 写作 text 为整页去标签文本，不是结构化题干/阅读材料/听力转写的完整性证明 |
| search | punctuated 命中 21 | 此关键词查询可用，不代表每页每字段可准确检索 |

Official 26/31 缺口是现有来源索引的边界，不能推广为全网没有材料。`exam_date:null` 如实保留；本轮没有发现或补造逐年发布时间与考试季节。

## 实际流程与联网拉取

HTTP：能力发现 → coverage → era/section 套次筛选 → get 元数据 → read/listen questions → speak/write detail → search → 机经汇总、四科详情和锁定条目列表。8 条业务路由均实际请求。缺 detail.url 返回 422；非法详情路径、未知 section、非法 page 返回 HTTP 200 + `ok:false`。后者符合该参数当前的业务失败实现，不能一律期待 422。

本轮 HTTP 共 27 次（26 次托福请求 + 1 次 OpenAPI），其中负向与问题复现用例单独判定，不能写成 27/27 业务通过。8 个 CLI 命令 info/coverage/sets/get/questions/detail/search/jj 均 exit=0；正常用例 `ok:true`。

强制联网调用 `/detail?...&refresh=1`：

| 科目 | 真实来源 | 结果 |
|---|---|---|
| 阅读 | Official 54，read/11m4mj.html | 成功，全题解析 complete=true |
| 听力 | Official 54，listen/11mc6j.html | 成功，全题解析 complete=true |
| 口语 | Official 54 Q 2，speak/f1m9gj.html | 成功，题干与音频非空 |
| 写作 | Official 54，write/c1m97j.html | 成功，材料所在整页 text 非空，audio_url 非空，essay 为空 |

另对 listen/speak/write 的音频各发一次实际 Range 请求，3/3 HTTP 206、`audio/mpeg`，读取 47646 / 65536 / 65536 字节，文件头符合 MP3 帧或 ID3。证明地址可获取音频样本，**未完整下载、解码或人工试听全部音频**。

缓存读取与强制联网拉取分别记录；971 条缓存复算不能写成 971 次联网测试。网关在独立端口 8125 运行，测试完成后终止本轮进程，不操作其他服务。

## 发现的问题

### P1-01：详情 URL 没有限制主机，存在任意地址访问及缓存污染风险

位置：`lib/jj.mjs:jjHashOf`、`lib/detail.mjs:fetchKmfDetail`、`lib/kmf.mjs:fetchPage/fetchKmfSet`、`lib/util.mjs:httpGet`。

`jjHashOf` 只用非锚定正则寻找 `/detail/{section}/{hash}.html`，没有解析 origin。`fetchPage` 对该 URL 发请求，缓存键只取 section/hash。`questions --url` 路径甚至不要求 kmf 主机。`httpGet` 自动跟随重定向。

本轮仅用受控的 127.0.0.1 随机端口复现，没有访问系统敏感地址：`http://127.0.0.1:<port>/detail/speak/auditprobe20261005.html` 被 CLI detail 接受；本地服务收到 1 次请求；响应被写入 kmf 缓存。该临时缓存随后立即删除。见 cache-summary.url_validation。

影响：HTTP detail/jj/questions 的用户输入可触发服务端访问任意地址；不同主机同一路径可争用业务缓存。后续修复必须在请求和读缓存之前严格校验，并校验重定向目标，不能只拦住 localhost。

### P1-02：口写错误页被当作成功内容

同一次受控复现返回 HTTP 200 HTML，正文仅 `upstream maintenance`。detail 返回 `ok:true`、`question:null`、`text:"upstream maintenance"`，并写入缓存。

位置：`lib/jj.mjs:fetchJjDetail` 的 speak/write 分支，以及先写缓存后验内容的 `fetchPage`。

影响：HTTP 200 与非空 text 不能证明题目有效；现有缓存数量和预抓取 ok 计数会计入错误页。应按科目验证必要 DOM 和有效题干/材料，并在确认内容有效后写缓存；已有坏缓存也必须拒绝。合法写作无范文、部分写作无音频是正常状态，不应一刀切要求 essay/audio。

### P1-03：14 道听力表格题丢失选项与答案，却报告完整

位置：`lib/kmf.mjs` 的听力选项/答案/题型解析及 `fetchKmfSet.complete`。

14 道全部返回 `type:"multiple_choice"`、`options:[]`、`answer:[]`，所在套题仍 complete=true。源 HTML 含 `table.content-logic`、行列文本与 `span.true-answer` 的多值答案。本轮逐个读取源缓存确认，详见 cache-summary.answer_gaps。

最小代表：Official 04 Set 2，`https://toefl.kmf.com/detail/listen/11dwej.html`，qid=64670。源表格为 Yes/No 判断，源答案 B A A B；API 丢失表格与答案。其他条目为 Official 53/45/33/24/20/18/16/13/10/08/05/02（02 两道），共 14。

影响：使用者无法完成这些题；“抓到全部题号”被当作“全部可作答”。需要支持实际表格结构和多值答案；缺必要内容的条目必须产生明确缺口，不能只依题数判 complete。

### P2-01：info 暴露的 pre/post-2023-07 era 无法筛选

`info.eras` 同时列出两项改版分区；CLI info 还给它们相同的 1–54 编号范围。`catalog.eraOf` 只返回六个编号分区，`listSets` 按它与输入 era 相等筛选。

本轮 `/sets?era=pre-2023-07` 与 `/sets?era=post-2023-07` 均 HTTP 200、ok=true、total=0。这不是查实了“两个分区没有数据”，而是两值没有对应筛选实现。

建议：在没有逐套真实改版身份数据的情况下，仅让六个编号分区作为筛选选项；改版信息移到明确标注为不可筛选的参考说明；未知 era 返回业务错误，禁止伪造分区映射。

### P2-02：套次参数宽松匹配，错误身份被静默接受

CLI `normTpo` 从任意字符串提取一到两位数字。HTTP `/get?set=garbage54` 实际成功返回 tpo-54。三位编号也可能被截断，而小数、混杂文本未严格拒绝。

影响：调用者以为身份有效，实际访问另一套。应规定并严格解析整串输入（set=tpo-N；tpo 参数为整数），确保 CLI 和 HTTP 一致。

### P2-03：完成汇报超出当前证据

- 758/758 本地索引/列表缓存对照，不等于本轮在线全量逐项复验。
- 旧“在线 vs 缓存 0 内容差异”日志仅支持列出的六个样本。
- 971 个入口解析成功，不等于每题选项和答案完整；本轮已有 14 个反例。
- write 整页 text 含导航和站点内容；非空不能直接验收结构化材料或听力转写。
- 单进程内部限速不提供跨 CLI/网关子进程的全局 1 req/s 保证；并发门也不是生产压测。
- 工作区根目录不是 Git 仓库，不能从本轮 git diff 证明历史“只改指定文件”。

后续文档需保留日期、单位、来源、缓存/联网区分和未验证项，不得用历史“done”勾选替代本轮证据。

## 测试文件清理与限制

业务缓存 `toefl-api/.data`、索引 `data`、正式工具 `tools`、库 `lib` 和第三方原始仓库保留。清理针对本项目探针中的临时执行脚本、下载 HTML、含题目正文的临时响应文件及本轮运行脚本；统计 JSON、状态、来源清单和日志保留以追溯。

`examdata/tests` 原有其他模块回归测试保留。不能把“删除测试文件”扩大成删除整个服务的测试体系或原始数据。具体删除路径、总数和剩余扫描结果以 cleanup-manifest 为准。

本轮已删除 154 文件；探针中的临时程序/HTML 剩余 0，examdata/tests 中托福命名测试文件剩余 0。源站提供的原文现在只留业务缓存和原始第三方仓库，音频验证数据仅在内存读取，未保存音频文件。原报告中被删除探针原文的链接属于历史记录，不再承诺可打开；本轮统计摘要保留可追溯路径与删除前 SHA256。

## 工程判断

结构清晰，短命 Node CLI 与网关接口容易复测，业务失败约定也较一致。但当前安全边界与“完整”状态有实际反例。工程审查评分：**6/10**（主观判断，非自动测试结果）；优先级为 URL/错误页 → 表格题 → era/身份 → 文档证据口径。没有做跨进程并发或生产负载验收。

## 整体回归终态

**全量回归未完成，不能判绿。** 启动命令：在 examdata 下运行 `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，`EXAMDATA_TEST_LIVE=0`、`PYTHONDONTWRITEBYTECODE=1`。11:45 开始，超过 12 分钟后长时间没有越过 36% 输出；本轮主动结束自己的测试子进程。日志 `audit-20261005/pytest-incomplete.log`。不能声称超时处的具体测试已经定位，不能写完整通过/失败总数。

另外运行相同套件的 `-x` 诊断，exit=1，首个失败为 `tests/test_api.py::test_provenance_coverage_is_complete`（第 220 行）：`/provenance/coverage` HTTP 200，但 body.complete=false，与该测试的 true 断言不符；停止时之前 53 个测试通过。详见 `pytest-first-failure.log`。这是通用来源覆盖接口，不是托福路由；本轮没有修改业务代码，尚未证明其失败是托福接入导致，也未证明历史基线已经存在，交给后续 Agent 检查，不擅自修其他模块。

本轮测试收集显示当前测试树已经不同于历史 1024 例快照；历史汇报不能代替当前回归。托福联网测试另外执行，不把 pytest 的 offline 标记当作源站验证。

终态：本轮临时 HTTP 服务已结束，8125 无监听；8124 也无监听。本轮临时执行脚本已删除，原始 flow 响应已转为统计摘要后删除，音频未落盘。pytest 统计日志作为证据保留。本次新增交付为本报告、执行提示词和统计证据；未提交业务代码改动。
