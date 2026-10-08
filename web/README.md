# Examdata Web（新版前端）

独立于旧版 `frontend/` 的新前端：Notion 式极简界面，覆盖试卷、题库、时间表三个模块。旧前端文件未做任何修改，两者可同时运行。

```bash
cd web
node server.mjs          # http://127.0.0.1:5190
```

需要 Node.js 20+，无第三方依赖，只监听本机，只读。

## 页面

| 路由 | 内容 | 数据来源 |
| --- | --- | --- |
| `#/` 概览 | 题目库、已解析试卷、目录文件、考纲/时间表计数；模块入口 | `/api/stats`（汇总后端 `/health`、`/api/v1/search` 与本地快照） |
| `#/papers` 试卷 | 科目 + 年份 → QP/MS/ER/GT 原件与官方考纲；未选科目时显示科目目录 | `/api/resources`（实时来源）、`data/catalog.json`、`data/syllabi.json` |
| `#/questions` 题库 | 题干关键词检索，按考试局/科目（名称或代码）/卷号/年份/可作答小题/有答案筛选；侧栏查看评分要点、知识点、下载原卷 | 后端 `/api/v1/search`、`/api/v1/question/{id}`、`/api/v1/paper` |
| `#/timetable` 时间表 | CIE Zone 5 与 Edexcel IAL 合并在同一日历：月视图（日历格子）与列表视图（定位到今天），默认全部考试局，可按考试局/科目/场次/级别筛选 | `/api/timetable/events?from&to&board&subject`：只读合并 `examdata/src/examdata/timetable/data` 下全部快照（运行中的后端没有按日期范围查询的接口，且数据即这些快照） |
| `#/q/{id}` | 直接打开某道题 | 同题库 |

模块互通：试卷结果中题库收录的卷显示「题目」链接（逐卷核对，样卷不会误链）；题目侧栏可跳到该卷全部文件；CIE 时间表场次可跳到该卷最近一次已考的试卷；时间表可按筛选结果导出 `.ics` 日历。

未选科目时：Cambridge 显示按 AS & A Level / IGCSE / O Level 分组的科目目录（可即时筛选，另可切换到 1,121 份目录快照）；Edexcel 显示 24 门 IAL 课程目录。只选科目不选年份时默认查询上一完整年份。

开场动画：每个浏览器会话首次打开时播放约 2.5 秒（网格展开、科目数据流、真实数据计数、衬线字标逐字升起，最后沿橙色中线上下分开）；点击、Esc 或「跳过」可立即结束，系统开启“减少动态效果”时不播放；命令面板「重播开场动画」或概览页底部可重播。

时间表：以日期而非考试局/考季组织。默认显示当前月份、全部考试局，CIE 与 Edexcel 用颜色区分；同一天两局都有考试时格子里两局都会出现。月视图点击日期在侧栏列出当天全部场次（按上午/下午/晚间分组）；列表视图打开时定位到“今天”分隔线（上方已考、下方即将进行）。顶部吸附栏：上一月/下一月（也可用 ← →）、今天、月/列表切换、导出本月 .ics；空月份可直接跳到前后最近有考试的月份。URL 参数：`view`、`month`、`board`、`subject`。

全局：`Ctrl K` 或 `/` 打开命令面板（跳转页面、科目试卷、题目搜索、题目编号、科目时间表），浅色/深色主题切换，窄屏侧栏抽屉。

中 / EN 双语：侧栏底部（窄屏在顶栏）切换，选择保存在浏览器本地；首次访问按浏览器语言。所有界面文案通过 `app.js` 中的 `L(中文, English)` 输出；来源服务返回的错误信息保持原文。

视觉：Instrument Serif / Noto Serif SC 标题、JetBrains Mono 标签、细线网格与单一信号橙强调色。概览页包含随光标起伏的点阵、对 `/api/v1/search` 实时发起请求的查询控制台（点击结果可打开题目）、科目滚动条与编号目录。字体来自 Google Fonts，加载失败时回退到系统字体，不影响功能。

## 目录

- `server.mjs`：静态文件、`/api/*` 聚合与 `/gateway/*` 只读代理（白名单：health、boards、search、paper、question、assets）
- `lib/resources.mjs`、`lib/search.mjs`：从旧前端复制的来源查询与科目匹配逻辑（`resources.mjs` 的改动见文末）
- `data/`：从旧前端复制的目录与考纲快照；刷新时用旧前端的 `build-catalog.mjs` / `build-syllabi.mjs` 生成后再复制过来
- `public/`：`index.html`、`app.css`、`app.js`

## 环境变量

`WEB_PORT`（默认 5190）、`EXAMDATA_URL`（默认 `http://127.0.0.1:8000`）、`EXAMDATA_API_KEY`、`EXAMDATA_TIMETABLE_DIR`。

检查：`npm run check`（语法）与 `npm test`（24 项：科目匹配、Edexcel 变体卷号与卷号筛选、CIE 清单过滤、多考季容错、考纲）。

`lib/resources.mjs` 相对旧版的改动：识别带字母后缀的变体卷（如 `wec14-01a`）；Pearson 分数线 PDF 不存在时返回 302 跳转到 404 页，按“未提供”处理而非报错；网络错误重试一次，分数线页面缓存十分钟。
