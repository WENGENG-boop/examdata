# Examdata 公共试卷查询前端

独立单页，只修改 frontend 目录，不修改、重启后端或写入数据库。白色、冷灰、近黑与少量蓝色；保留可跳过、可重播的开场动画和减少动态效果支持。

运行 `node server.mjs`，打开 http://127.0.0.1:5188 。需要 Node.js 20+，无第三方运行依赖，只监听本机。

科目框点击即可查看课程。支持中文、英文、全角代码；“数学”默认 CIE A Level 9709，物理 9702、化学 9701、生物 9700、经济 9708，显式选择 IGCSE 0580 等课程优先。Edexcel 列表来自 Pearson 官方 IAL 课程目录，包含中文名称、课程年份和规格代码，输入“经济”“数学”可自动匹配。卷号选填，留空查询本考季全部卷；新课程可能尚无历史试卷。

CIE 默认浏览本地官方目录快照（2026-10-01），包含 1,121 份 QP、MS、ER。`node build-catalog.mjs` 从已有根目录 cie_all_discovery.json 和前端保存的 Pearson 课程目录重新生成 catalog.json，不联网，不修改后端数据。快照不代表全科全卷覆盖。

完整科目、年份、考季查询由前端 server.mjs 的 GET /resources 独立读取来源目录：CIE 工坊文件清单提供 QP/MS/ER/GT，ER 缺失时补充相同科目与考季的官方快照；Pearson 官方目录提供公开 QP/MS/ER，GT 从官方分数线页面或经 HEAD 确认存在的官方 PDF 获得。Edexcel 分数线为该考季 IAL 全科目合集，标明适用范围。来源没有的类型显示“来源未提供”，不伪造下载链接。资料详情标注实时来源或目录快照。登录限制文件不显示。

前端来源请求有超时与十分钟内存缓存；失败可手动再查。原只读 /gateway 代理仍保留，EXAMDATA_URL 默认 http://127.0.0.1:8000 ，支持 EXAMDATA_API_KEY；FRONTEND_PORT 默认 5188。运行检查：`node --check app.js`、`node --check server.mjs`、`node --test search.test.mjs`。

2026-10-02 验证：13 项匹配和文件筛选测试通过。实际浏览器查询 CIE 数学 / 2024 June / 11，显示 QP、MS、GT 和官方目录 ER；Edexcel 经济 / 2024 June / WEC11-01 查询确认四类文件，中文科目下拉可选择，无需记忆代码。只重启前端服务，现有后端保持运行。

所有考季修复：选择科目和年份后，留空考季会汇总 CIE 的 March/June/November，或 Edexcel 的 January/June/October/November。每份文件保留实际考季；缺少资料的考季可以为空，查询失败的考季明确提示，其他结果继续显示。16 项测试通过，已验证两局实际汇总请求。

考纲（Syllabus）返回：syllabi.json 快照（2026-10-02）收录 CIE 198 个科目与 Edexcel 24 门 IAL 课程的官方考纲链接（CIE 科目页内的 Syllabus PDF；Pearson 官方目录的 Specification 记录），`node build-syllabi.mjs` 联网刷新，`node --test syllabi.test.mjs` 校验解析规则。查询科目时，结果区与详情弹窗显示“考纲”条：优先列出官方考纲 PDF，没有 PDF 时退回科目页；GET /resources 响应同时携带 syllabus 字段（title、page、syllabuses）。Edexcel 2027 版三门课程（ial27-biology/physics/chemistry）尚无公开 Specification，仅显示科目页。
