# 高考真题可拉取渠道清单（实测记录）

日期：2026-10-04。方法：匿名 HTTP（curl，桌面 UA）+ 匿名浏览器（部分渠道）。
边界：不注册、不登录、不绕付费墙；仅小量抽样验证，非全量采集。

## 分级标准

| 级别 | 含义 |
|---|---|
| L1 | 文件级可下载（无需登录） |
| L2 | 在线图文可抓取 |
| L3 | 需账号 / 积分 / 付费 |
| L4 | 仅人工（网盘等需人工转存） |
| L5 | 未发现渠道 |

附加记法：**L1图片** = 图片可直下、成卷需按页码拼接；**L3(下载需账号)** = 网盘；**L1题目级** = 题目级语料非成卷。

## 渠道汇总

| # | 渠道 | 类型 | 分级 | 证据位置 |
|---|---|---|---|---|
| 1 | GitHub 开源仓库（6 个） | 文件（PDF/DOCX） | **L1** | `logs/inventory.csv`、`samples/manifest.csv` |
| 2 | 中国教育在线 EOL（gaokao.eol.cn） | 在线图文（图片序列） | **L1图片** | `logs/eol-article-index2.csv`、`logs/eol-sample.csv`、`samples/eol/` |
| 3 | 商业题库/资源站（5 家） | 文件/在线 | **L3** | `logs/channels/{21cnjy,51test,jyeoo,zujuan,zxxk}/NOTES.md` |
| 4 | 百度网盘（经易试卷/知乎索引） | 网盘 | **L3(下载需账号)** | `logs/channels/pan/NOTES.md` + 截图 |
| 5 | HuggingFace 数据集 | 题目级 CSV/JSONL | **L1题目级** | `samples/hf/` |
| 6 | 官方考试院（4 家） | — | **L5** | `logs/channels/official/NOTES.md` |

---

## 1. GitHub 开源仓库（L1，免费、文件级）

6 个仓库、共 415 个文件（`logs/inventory.csv`）：

| 仓库 | 文件数 | 内容 |
|---|---|---|
| `qingshuo/China-Gaokao-Papers-Collection` | 299 | 2024–2026 各省/全国卷 PDF+DOCX，按 `papers/<年>/<省代号>/<科目>/` 组织 |
| `deekur/gaokaophysics` | 65 | 物理卷（含黑吉辽蒙、陕晋宁青等共享卷） |
| `deekur/gaokaomath` | 20 | 数学卷 |
| `Zaxaerith/GaokaoGEO` | 15 | 地理 DOCX（质量差，见下） |
| `Zaxaerith/GaokaoCHN` | 8 | 语文 DOCX |
| `Zaxaerith/GaokaoENG` | 8 | 英语 DOCX |

实测下载（`samples/manifest.csv`）：**64/64 成功**，68.5 MB，覆盖 22 个专属省目录 + 共享卷（`_shared/`）。
下载链：`raw.githubusercontent.com` 主链；备选回退 `cdn.jsdelivr.net`。每条含 url/bytes/sha256/status/header。

风险与质量注记：
- **Zaxaerith 系 DOCX 质量混合**（`logs/_probe/HEADER-CHECK.md`）：GEO 全目录 10 个异常、CHN 3 个中 2 个异常、ENG 5 个中 1 个异常——异常文件头为 `59aae78a782daee9`（约 180KB，非 OOXML），**可下载但打不开**，属仓库质量问题，批量采集需逐文件校验头（`PK`/`%PDF`）。
- 许可：`deekur/*` license=NOASSERTION；`Zaxaerith/*` 无 license；`qingshuo/*` 未明示。存在版权/再分发风险。
- 稳定性：依赖 GitHub 可用性；仓库可能删档。

## 2. 中国教育在线 EOL（L1图片，图片免登录直下）

机制（`logs/eol/` 原始文章页 + `scripts/eol_sample.py`）：
- 真题栏目文章页（`gaokao.eol.cn/shiti/.../t2025....shtml`）内嵌试卷图片序列；
- 页面含 `_PAGE_COUNT = "N"`（试卷页数），图片命名 `xxx01.png…xxxNN.png`（部分从 `00` 起，如 `sw00.png`）；
- 图源域名：`img.eol.cn`（2024/2025）、`img1.eol.cn`（2023），个别为协议相对路径；
- 实测（2026-10-04 复核直下，全部 200 + PNG 头）：
  - 2025 全国一卷英语 `yy01.png` = 1,296,887B（1587×2245）、`yy08.png` = 1,130,879B；
  - 2024 天津数学 `sx08.png` = 185,596B；2023 新课标I数学 `sx04.png` = 76,627B；
  - 2025 北京数学文章 `_PAGE_COUNT="21"`，首图 `img.eol.cn/e_images/gk/2025/st/bj/sx01.jpg`。
- 证据样本：`samples/eol/`（3 张，覆盖 2023/2024/2025）。

覆盖统计（`logs/eol-article-index2.csv`，共 **2631** 篇文章）：

| 年份 | 文章数 | 有图链数 |
|---|---|---|
| 2023 | 423 | 303 |
| 2024 | 606 | 429 |
| 2025 | 801 | 127（答案 104 / 试卷 13 / 解析 10） |
| 2026 | 801 | **0**（复核过，尚未挂图） |

限制：成卷需按 `_PAGE_COUNT` 抓全序列并拼 PDF（可脚本化）；2025 多数文章未挂图、2026 全空；图片为扫描/排版图，无文字层。

## 3. 商业题库/资源站（L3，匿名不可下载）

| 站 | 匿名可达 | 下载门槛 | 结论 |
|---|---|---|---|
| 21cnjy（书城 book.21cnjy.com） | 首页/搜索/专题/书籍页 200 | JS 强制跳登录（`passport.21cnjy.com`）；资源页另有阿里云 WAF（acw_sc__v2） | L3；免费账号可否 0 学币下载未验证；另有校网通/订阅/会员 |
| 51test（无忧考网） | 栏目/文章 200 | "Word 文档下载" → `user.51test.net/vip/download/word/` 302 → 微信注册页；路径含 `/vip/` | L3；匿名仅得正文+前五页预览图（预览图 CDN 匿名可下，样本 `samples/channels/51test/preview1.png`） |
| jyeoo（菁优网） | 首页/列表页 200 | 试卷详情、做题页均 302 跳登录 | L3（疑似叠加积分/会员） |
| zujuan.xkw.com（组卷网） | ✗ 全站阿里云 alicfw JS 挑战 | 无法进入任何页面 | L3+（反爬；浏览器可过但未验证） |
| zxxk.com（学科网） | ✗ 同上（`alicfw_gfver v1.200309.1`） | 同上 | L3+ |

备注：本轮不注册、不登录，故 L3 站"登录后可否免费下载"均未验证；未下载任何样本。

## 4. 百度网盘渠道（L3 下载需账号）

发现路径：易试卷（yishijuan.com）条目页**明文**给出百度网盘链接+提取码（`item1544.html`：`https://pan.baidu.com/s/1wbgfJenS1BNowgCosdpeRw?pwd=6677`；`item998.html` 另一条）；知乎文章正文亦可读到链接文本（外链点击被知乎登录弹窗拦截，仅作发现渠道）。

实测（`logs/channels/pan/`）：
- 匿名 curl 过提取码校验 → `{"errno":0}` + randsk cookie → 可拿分享页 HTML（分享者、shareid）；`share/list` API 匿名被拒（errno:2）。
- 匿名浏览器可浏览目录树（16 个子文件夹）直至文件级（全国一卷 试卷.pdf 1.3M、答题卡.pdf 813KB）。
- 点"普通下载" → **登录墙**（扫码/账号/短信）。→ **下载文件必须百度账号**。
- 截图 5 张：`pan-share-root.png`、`pan-share-folder-list.png`、`pan-file-level.png`、`pan-download-dialog.png`、`pan-download-login-wall.png`。

风险：链接易失效；版权不明；批量自动化触发风控。分级记 **L3(下载需账号)**（浏览 L1 级、下载 L3 级，整体按 L3 记）。

## 5. HuggingFace 数据集（L1题目级）

- `samples/hf/gaokao_bench.zip`（903,487B）：**14 个 CSV**（`gaokao_bench/Multiple-choice_Questions/`），2010–2022 各科选择题/英语阅读/完形/填空等，含题目+答案+解析。
- `samples/hf/2010-2013_English_MCQs.jsonl`（63,969B）：逐题 JSON（year/category/question/answer/analysis）。
- 定位：**题目级语料，不是成卷文件**；适合题库/NLP 用途。

## 6. 官方渠道（L5）

`neea.edu.cn`（教育部教育考试院）、`shmeea.edu.cn`（上海）、`zjzs.net`（浙江）、`eea.gd.gov.cn`（广东）首页均匿名可达（200），**未发现真题文件下载**（与普遍认知一致：官方只发布考试安排、评析、成绩；试题以评析/新闻形式出现）。证据：`logs/channels/official/`。

---

## 证据索引

```
gaokao-feasibility/
├── channels.md                  ← 本文件
├── scope-map.md                 ← 2023–2026 卷种×省份映射
├── coverage-matrix.csv          ← 31 省 × 渠道 × 分级矩阵
├── samples/
│   ├── manifest.csv             ← 64 个 GitHub 样本清单（url/bytes/sha256/status/header）
│   ├── _shared/ by-province/    ← 样本文件（22 省目录 + 共享卷）
│   ├── eol/                     ← EOL 图片样本 3 张（2023/2024/2025）
│   ├── hf/                      ← HuggingFace 题目级数据集 2 件
│   └── channels/51test/         ← 51test 预览图样本
├── logs/
│   ├── inventory.csv            ← GitHub 6 仓库 415 文件清单
│   ├── eol-article-index2.csv   ← EOL 2631 篇文章索引（含图链）
│   ├── eol-sample.csv           ← EOL 逐省抽样 18 条
│   ├── _probe/HEADER-CHECK.md   ← docx 文件头抽检
│   ├── eol/                     ← EOL 原始文章页
│   └── channels/*/NOTES.md      ← 8 个渠道探测记录（含截图/头文件/HTML）
└── scripts/                     ← fetch_trees/inventory/fetch_samples/parse_eol/eol_sample/build_matrix
```
