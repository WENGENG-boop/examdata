# 剑桥雅思 API —— 接口使用文档

> 面向调用方。讲清楚：**怎么取一套卷子、怎么单独取听力、怎么取各个部分、返回的 JSON 长什么样**。
> 配套：架构与源探测过程见 [DEVELOPMENT.md](./DEVELOPMENT.md)

> 覆盖数字为2026-10-01保留的联网审查证据，不保证源站持续可用。84/84表示可调用套数，不等于每套40个独立题干完整；组合题与 `questions_missing` 必须单独检查。319 Part 表示剑1–20有可用原文，剑20仍缺1段。PDF哈希一致证明所下载文件与LFS指针相符，不证明整本教材内容完整。本轮续作及未完成检查见 `AUDIT_REPORT.md`（位于工作区旁ielts-api）。

---

## 目录

> 新调用方建议直接看 [v2 规范化接口（推荐）](#v2-规范化接口推荐)。

1. [两种用法](#1-两种用法)
2. [核心概念：槽位与降级](#2-核心概念槽位与降级)
3. [聚合接口 aggregate()](#3-聚合接口-aggregate)
4. [分槽接口](#4-分槽接口)
5. [剑桥21 专用接口](#5-剑桥21-专用接口)
6. [整本 PDF 接口](#6-整本-pdf-接口)
7. [覆盖率自检接口](#7-覆盖率自检接口)
8. [HTTP 服务](#8-http-服务)
9. [返回结果总览表](#9-返回结果总览表)
10. [错误处理](#10-错误处理)
11. [实战范例](#11-实战范例)

---

## 0. 三分钟上手

```bash
cd ielts-api
node ielts-cli.mjs serve 8787
```

```bash
# 1) 先看这一册有哪些套
curl http://127.0.0.1:8787/api/pte-book/20

# 2) 拉一整套（阅读+听力+原文+音频+PDF）
curl http://127.0.0.1:8787/api/aggregate/20/1

# 3) 只要阅读
curl http://127.0.0.1:8787/api/pte-reading/20/1

# 4) 只要听力题目+答案
curl http://127.0.0.1:8787/api/pte-listening/20/1

# 5) 听力原文
curl http://127.0.0.1:8787/api/listening-script/20

# 6) 音频直链
curl http://127.0.0.1:8787/api/pte-audio/20/1
```

**最常用的三个接口**：

| 需求 | 接口 |
|---|---|
| 要一整套（什么都想要） | `aggregate({book, test})` |
| 只要题目和答案 | `pteReading()` / `pteListening()` |
| 只要听力和原文 | `cam21Listening()`（剑21）/ `listeningScript()` |

---

## v2 规范化接口（推荐）

v1 接口（下文 §3–§9）原样保留；**新调用方建议用 v2**。v2 把题目、答案、资产、音频、覆盖度收敛为
一套本地索引驱动的规范接口（schema `ielts.v2/1`），CLI / Node HTTP / FastAPI 三入口共享同一
resolver，**零网络请求**（S13 起）。

```bash
node ielts-cli.mjs books-v2                                   # 21 册目录
node ielts-cli.mjs test-v2 10 1                               # 整套元数据 + 完整度单元（含 expected 分母）
node ielts-cli.mjs test-v2 10 gta --variant=general           # General Training A 套（gta/gtb）
node ielts-cli.mjs questions-v2 10 1 --skill=reading          # 逐题（含 answer.status）
node ielts-cli.mjs questions-v2 10 1 --skill=reading --passage=2   # 单篇语义
node ielts-cli.mjs questions-v2 10 1 --skill=reading --status=empty  # 只看空答案槽位
node ielts-cli.mjs question-v2 q-10-1-reading-academic-34     # 单题（空答案保位示例）
node ielts-cli.mjs coverage-v2                                # 覆盖度（分母 + 逐单元状态 + gap 列表）
node ielts-cli.mjs asset-v2 <sha256|book-pdf-1>               # 资产：图片/音频（sha256）或整本 PDF
node ielts-cli.mjs compare-official 9 1                       # 官方答案页对照（只报告，不改数据）
```

HTTP 等价路由：Node 服务（`node ielts-cli.mjs serve 8787`）为 `/api/ielts/v2/info`、
`/api/ielts/v2/books`、`/api/ielts/v2/test/{book}/{test}`、`/api/ielts/v2/questions/{book}/{test}`、
`/api/ielts/v2/question/{question_id}`、`/api/ielts/v2/coverage`、`/api/ielts/v2/asset/{asset_id}`；
FastAPI 网关同语义、前缀 `/api/v1/ielts/v2/…`。

语义要点：

- **整套 vs 单篇**：`test-v2` 返回整套结构（阅读 3 篇、听力 4 Part、组题层级）；`questions-v2` 用
  `--passage=` / `--part=` 过滤单篇/单 Part；阅读**缺省返回整卷 40 题**，不是单篇回落。
- **A/G 变体**：`--variant=academic|general`；剑 10–19 的 General Training 以测试标识 `gta`/`gtb`
  访问（如 `test-v2 10 gta`）。变体与身份不符返回类型化错误 `variant_mismatch`。
- **开放题**：Writing/Speaking 为开放任务，只给原书期望清单（`expected` + 来源状态），
  **不标唯一标准答案**；缺原书内容标 `source_missing`。
- **答案状态**：每题带 `answer.status`（`verified` 源键与题面/编号一致；`official_verified` 官方答案页
  核验；`empty` 源缺但编号保位，如剑10 T1 Q34；`source_missing` 等）。组题（多选/匹配）带
  `group_ref` 与 accepted 集合；跨源冲突保留双方原值及裁决来源。
- **完整度分母**：`test-v2` 的 `completion.units[]` 给出每个单元的 `expected`（如 40 题；
  剑1 T2 听力为 41 题）与当前状态；抓不到的单元保留在分母里，不从分母删除。
- **音频**：`asset-v2` 按 sha256 解析本地音频/图片；音频身份（identity + content_sha256）经校验
  才计 verified。逐题时间区间仅在音频身份与时间基准通过校验后标记；未对齐项暴露为 `unverified`，
  不伪造区间、不按题号均分时长。
- **数据目录**：默认 `<工作区>/ielts-data`，可用 `EXAMDATA_IELTS_DATA_DIR` 覆盖（三入口一致）；
  更新/审计命令见 [DEVELOPMENT.md](./DEVELOPMENT.md) §7。

---

## 1. 两种用法

### 方式 A：直接 import（Node 18+，零依赖）

```js
import * as api from "./ielts-api.mjs";

const paper = await api.aggregate({ book: 20, test: 1 });
console.log(paper.parts.reading.answer_key);
```

### 方式 B：起 HTTP 服务，跨语言调用

```bash
node ielts-cli.mjs serve 8787
# 然后浏览器/curl 访问 http://127.0.0.1:8787/api/aggregate/20/1
```

---

## 2. 核心概念：槽位与降级

一套剑桥雅思被拆成 **5 个独立槽位**（外加 2 个补充槽位），每个槽位由覆盖最好的源提供，互不依赖：

| 槽位 key | 含义 | 典型源 |
|---|---|---|
| `reading` | 阅读原文 + 题目 + 答案 + 解析 | practicepteonline / cam21（剑21） |
| `listening_qa` | 听力题目 + 答案 | practicepteonline / cam21（剑21）/ ieltsprogress（剑3 T2–T4 兜底） |
| `listening_script` | 听力原文（逐 Part） | maslow / reader / cam21 |
| `listening_audio` | 听力音频 URL 列表 | practicepteonline / maslow |
| `pdf` | 整本 PDF 直链 | BaBaLiBoo（Git LFS）/ aqinaq（剑21 社区镜像） |

> 补充槽位（不计入 `score`）：`reading_enriched` 精读（reader 剑1–19 / 小站备考 剑20/21）、
> `listening_transcript` 剑21 官方逐句原文（含说话人与时间戳）。

**降级规则**：某个槽位的主源失败时自动换备源；全失败则该槽位为 `ok:false`，
写入 `warnings`，**其余槽位照常返回**。所以调用方永远拿到一个对象，不会抛异常。

**打分**：`score` 形如 `\"4/5\"`，表示 5 个槽位里成功几个。

---

## 3. 聚合接口 aggregate()

一次拿到一套完整试卷。

```js
const paper = await api.aggregate({ book: 20, test: 1 });
```

| 参数 | 类型 | 范围 | 说明 |
|---|---|---|---|
| `book` | number | 1–21 | 剑桥雅思册号 |
| `test` | number | 1–4 | 第几套 |

### 返回结构（真实响应）

```jsonc
{
  "book": 20,
  "test": 1,
  "generated_at": "2026-10-01T13:16:32.080Z",

  "parts": {
    // ① 阅读：原文 + 题目 + 答案 + 解析
    "reading": {
      "ok": true,
      "source": "practicepteonline.com",
      "book": 20, "test": 1,
      "title": "IELTS Reading Test 310",
      "url": "https://practicepteonline.com/ielts-reading-test-310/",
      "passage": ["The kakapo is a nocturnal, flightless parrot…"],   // 原文段落，x10
      "instructions": ["Do the following statements agree…"],          // 题型说明，x8
      "questions": [                                                   // ★ 逐题，x40
        {
          "number": 1,
          "prompt": "There are other parrots that share the kakapo's inability to fly.",
          "answer": "False",
          "explanation": "…The keywords are other parrots share inability to fly…"
        }
      ],
      "answer_key": ["False", "…"],   // 按题号顺序，x40
      "answer_count": 40,
      "questions_missing": []          // 未提取到独立题干的题号；组合题说明见 4.3 节
    },

    // ①b 精读补充（不计入 score）：剑1–19 用 reader，剑20/21 用小站备考
    "reading_enriched": {
      "ok": true, "source": "top.zhan.com",
      "section_id": "20-1-P1",
      "sentences": [ { "en": "…", "zh": "…" } ],   // 逐句中英对照
      "note": "精读补充（剑20/21）：逐句中英对照（小站备考；题目解析需登录，不在本接口范围）"
    },

    // ② 听力题目 + 答案
    "listening_qa": {
      "ok": true,
      "source": "practicepteonline.com",
      "title": "IELTS Listening Test 201",
      "url": "https://practicepteonline.com/ielts-listening-test-201/",
      "audio": ["https://practicepteonline.com/wp-content/uploads/…mp3"],
      "instructions": ["Complete the notes below. Write ONE WORD…"],
      "questions": [ { "number": 1, "prompt": "Good for people who are especially keen on [(1)]",
                       "answer": "Fish", "explanation": null } ],
      "answer_key": ["Fish", "…"],
      "answer_count": 40,
      "questions_missing": [17, 18, "…", 26]   // 组合题编号在标题/图上，共 10 个
    },

    // ③ 听力原文：按 Part 分组的全文
    "listening_script": {
      "ok": true,
      "source": "maslow/EnglishLearning",
      "book": 20, "test": 1,
      "parts": ["part1", "part2", "part3", "part4"],
      "text": { "part1": "**WOMAN**  I've been meaning to ask you…", "part2": "…" }
    },

    // ④ 听力音频：4 个 Part 的直链（maslow 源；alt 为 pte 源的整卷音频）
    "listening_audio": [
      { "ok": true, "source": "maslow/EnglishLearning", "book": 20, "test": 1, "part": 1,
        "url": "https://raw.githubusercontent.com/maslow/EnglishLearning/main/ielts_listening/book_20/test_1_part_1.mp3",
        "cdn": "https://cdn.jsdelivr.net/gh/maslow/EnglishLearning@main/ielts_listening/book_20/test_1_part_1.mp3",
        "type": "audio/mpeg" },
      { "ok": true, "part": 2, "url": "…" }, { "ok": true, "part": 3, "url": "…" }, { "ok": true, "part": 4, "url": "…" }
    ],
    "listening_audio_alt": { "source": "practicepteonline.com", "url": "https://practicepteonline.com/wp-content/uploads/audio/201_we.mp3" },

    // ⑤ 真题 PDF（剑1–19 为整本；剑20 为分册，另有 pdf_book20_tests 打包 4 分册 + 音频）
    "pdf": {
      "ok": true, "source": "BaBaLiBoo/IELTS-Resources", "book": 20,
      "url": "https://media.githubusercontent.com/media/…/剑桥20真题（抢先版）/剑20-Test1.pdf",
      "bytes": 5327081,
      "note": "真实 PDF"
    }
  },

  "warnings": [],                     // 空数组 = 无降级、无缺失
  "sources_used": ["practicepteonline.com", "…"],   // 去重后的实际源列表
  "completeness": { "reading": true, "listening_qa": true,
                    "listening_script": true, "audio": true, "pdf": true },
  "score": "5/5"
}
```

> ⚠️ **`aggregate()` 没有顶层 `ok` 字段**（它总是返回一个结构完整对象）。
> 判断成功与否请看 **`parts.*.ok`**、**`completeness`** 和 **`score`**。
> 其余所有分槽接口都有顶层 `ok`。

### 读结果的标准姿势

```js
const p = await api.aggregate({ book: 20, test: 1 });

// 逐题遍历（含答案与解析）
for (const q of p.parts.reading.questions) {
  console.log(q.number, q.prompt, "=>", q.answer);
}

// 只要答案键
const keys = p.parts.reading.answer_key;      // ["False", "True", …]

// 判分
const userAnswers = ["False", "True", /* … */];
const score = userAnswers.filter((a, i) => a === keys[i]).length;

// 听力原文按 Part 取
const part1 = p.parts.listening_script.text.part1;

// 音频直链
const mp3 = p.parts.listening_audio[0].url;

// 有没有缺失？
if (p.warnings.length) console.warn(p.warnings);
```

---

## 4. 分槽接口

只想拿某一部分时，直接调对应的分槽接口，比 `aggregate()` 快很多。

### 4.1 册级目录：pteBook(book)

先看这一册有哪些套、对应什么 slug。

```js
await api.pteBook(20);
// {
//   ok: true, source: "practicepteonline.com", book: 20, hub_id: 12381,
//   title: "Official IELTS Tests Book 20",
//   reading: { 1: "ielts-reading-test-310", 2: "…", 3: "…", 4: "…",
//              general: { 1: "…", 2: "…", 3: "…", 4: "…" } },   // 培训类
//   listening: { 1: "ielts-listening-test-201", 2: "…", 3: "…", 4: "…" }
// }
```

> `reading` 里数字键是学术类（Academic），`reading.general` 是培训类（General Training）。

### 4.2 阅读：pteReading(book, test)

```js
const r = await api.pteReading(20, 1);
r.passage        // 原文段落数组
r.questions      // [{ number, prompt, answer, explanation }]
r.answer_key     // ["False", …]
r.answer_count   // 40
r.questions_missing // 未能提取到题干的题号数组（无缺失时为 []）
```

**加精读**（中英对照 + 语法点 + 同义替换）：

> 📌 **仅覆盖剑1–19**。剑20/21 该接口返回 `ok:false`；
> 剑20/21 的中英对照精读改用 `zhanReading()`（小站备考），题目+答案用 `pteReading()`。

```js
const deep = await api.reading(19, 1, 1);   // 第 3 个参数是第几篇 passage（源仅覆盖剑1–19）
deep.sentences   // 逐句中英对照 + 语法点：[{ id, para, en, zh, grammar: { type, note } }]
deep.phrases     // 同义替换短语
```

### 4.3 听力题目 + 答案：pteListening(book, test)

```js
const l = await api.pteListening(20, 1);
l.questions      // [{ number, prompt, answer, explanation }]
l.answer_key     // 40 个答案，按题号顺序
l.questions_missing // 未能从源页提取到题干的题号数组（如 [15,16]；组合题编号在标题/图上）
l.audio          // 该套的音频直链数组
```

> ⚠️ `questions` 可能少于 `answer_count`（如 36 题 vs 40 答案）：
> 源站把部分题型（配对题、地图题）合并渲染，题号在标题或图上。
> **判分请用 `answer_key`**，`questions` 用于展示题干，
> 缺失题号见 `questions_missing`（无缺失时为 `[]`）。

### 4.4 听力原文：listeningScript(book)

按册取，一次拿到该册全部 4 套的原文。

```js
const s = await api.listeningScript(20);
s.tests.test1.part1   // 第 1 套 Part 1 的全文
s.tests.test1.part2
s.source              // "maslow/EnglishLearning" 或 "userheyy/ielts-reader"
```

> ⚠️ **剑20 源侧仅 15 段**：test2 缺 Part 4（只有 part1–3），其余各册均为 16 段。
> 全库合计 319 Part = 剑1–19 各 16 段 + 剑20 15 段。

### 4.5 听力音频

```js
// 按套（4 个 Part 一起）
const a = await api.pteAudio(20, 1);
a.url     // 主音频
a.all     // 该套所有音频直链

// 按 Part（剑1–20，maslow 源）
const one = await api.listeningAudio(20, 1, 1);   // 第 1 套 Part 1
```

### 4.6 逐句时间轴：listeningSegments(book, test, part)

> 📌 **仅覆盖剑1–19**（源 `userheyy/ielts-reader`）。剑20/21 请用 `cam21Listening()` 的 `transcript`。

词级 `start`/`end` + 置信度，适合做精听、跟读、断句。

```js
const seg = await api.listeningSegments(19, 1, 1);   // 仅剑1–19
seg.segments[0]
// { id: 1, start: 0.08, speaker: "RECEPTIONIST",
//   en: "Sorry to keep you waiting…", zh: "",
//   words: [{ word: "Sorry", start: 0.93, end: 1.206, confidence: 0.94 }] }
```

### 4.7 听力交叉源：itoScript(book, test)

`practicepteonline` 之外的**独立第二源**（剑10–21），用于对照校验。

```js
const alt = await api.itoScript(21, 1);
alt.sections.section1   // Part 1 全文
alt.section_count       // 4
```

### 4.8 剑3 听力答案兜底：iprogListening(book, test)

`practicepteonline` 未发布剑3 听力 T2–T4（站点缺页），由 `ieltsprogress.com` 补答案键。

```js
const k = await api.iprogListening(3, 2);
k.answer_key      // 40 个答案
k.answer_count    // 40
await api.iprogCoverage();   // { coverage: { "3-1": 40, … }, total_answers: 160, tests_covered: "4/4" }
```

> 该源只有答案键（题目页无题干）；`aggregate()` 会自动兜底并附上 reader 词级时间轴。

### 4.9 剑20/21 精读：zhanReading(book, test, passage)

`reader` 精读只到剑19；剑20/21 的逐句中英对照来自小站备考（top.zhan.com）。

```js
const z = await api.zhanReading(21, 1, 1);   // 剑21 T1 P1
z.section_id  // "21-1-P1"
z.sentences   // [{ en, zh }] 逐句中英对照（36 句）
await api.zhanIndex(21);      // 剑21 篇目表（12 篇）
await api.zhanCoverage();     // 剑20/21 各 12 篇
```

> 站点上的题目解析需登录，不在本接口范围（仅提供逐句中英对照）。

---

## 5. 剑桥21 专用接口

剑21 是最新册，走独立的 `cam21.mjs`（源：`maqsudjon-cell/cambridge-21`），
**内容比通用接口更全**：带官方音频和逐句原文。

### 5.1 cam21Reading(test)

```js
const r = await api.cam21Reading(1);
r.passages      // 3 篇原文
r.questions     // 40 题
r.answer_key    // 40 答案
r.counts        // { passages: 3, questions: 40, answers: 40 }
```

### 5.2 cam21Listening(test)

```js
const l = await api.cam21Listening(1);
l.sections      // 4 个 Section
l.audio         // [{ section: 1, url: "…C21T1_Section_1.mp3" }, …]  ← 官方音频
l.answer_key    // 38 答案
l.transcript    // ★ 逐句原文：[{ section, lines: [{ speaker, text, time }] }]
l.counts        // { sections: 4, questions: 30, answers: 38, audio: 4, transcript_sections: 4, transcript_lines: 89 }
```

### 5.3 其它

```js
await api.cam21Audio(1, 2);    // 第 1 套 Section 2 的音频直链
await api.cam21Full(1);        // 阅读 + 听力 + 音频 + 原文，一次全拿
await api.cam21Index();        // 剑21 目录
await api.cam21Coverage();     // 剑21 覆盖自检
```

---

## 6. 整本 PDF 接口

剑1–19整本 PDF、剑20 Test1 分册走 GitHub **Git LFS**。剑20其余分册见 `book20Set()`；单个 `pdfLfs(20)` 不代表整本。

```js
const p = await api.pdfLfs(1);
p.url     // https://media.githubusercontent.com/media/…/Cambridge-1.pdf
p.bytes   // 28252883（约 26.9 MB）
```

> ⚠️ **必须用返回的 `url`（media.githubusercontent.com）**。
> 如果自己拼 `raw.githubusercontent.com` 的地址，只会拿到 ~130 字节的 LFS 指针文件，
> 不是真 PDF。

```js
await api.explainPdf(7);   // 剑7 精讲解析 PDF
await api.book20Set();     // 剑20 的试卷 PDF + 音频打包
await api.lfsProbe("Cambridge-20.pdf", "media");   // 探活（只发 Range 请求）
await api.lfsCoverage();   // 剑1–20 PDF 覆盖自检
```

剑21 走社区镜像（非 LFS）：

```js
const p21 = await api.pdf21();
p21.url    // https://raw.githubusercontent.com/aqinaq/agylshyn/main/site/pdf/ielts-21.pdf
p21.bytes  // 44148624（44.1 MB）
p21.pages  // 146
```

---

## 7. 覆盖率自检接口

```js
await api.coverage();       // 全源覆盖矩阵
await api.cam21Coverage();  // 剑21
await api.itoCoverage();    // 听力交叉源
await api.lfsCoverage();    // 整本 PDF
await api.iprogCoverage();  // 剑3 听力答案兜底
await api.zhanCoverage();   // 剑20/21 精读
await api.pdf21();          // 剑21 整本 PDF
```

### 实测覆盖（各源自检命令的真实数字）

> 口径说明：下列“答案”均为**答案键条目数**，不等于题目数。例如剑21 听力 4 套共 160 题、
> 147 条答案键（多选组一题多键）。题数与逐题状态以 v2 `coverage-v2` 的完整度单元为准。

```
阅读            84/84    剑1–21 × 4 套，共 3360 条答案键
听力            84/84    共 3346 条答案键（剑3 T2–T4 由 ieltsprogress.com 兜底；剑1 T2 源站仅 39 条；剑21 各套 35–38 条）
剑3 听力兜底      4/4    160 条答案键（ieltsprogress.com；T2–T4 题干已重建为完整 40 题/套）
剑21 阅读         4/4    160 条答案键 + 12 篇原文
剑21 听力         4/4    160 题 / 147 条答案键（多选组一题多键）+ 16 段官方音频（本地已核验 sha256）+ 738 行逐句原文
剑20/21 精读      24/24   逐句中英对照（top.zhan.com；剑20/21 各 12 篇）
听力原文         20/20   剑1–20 全覆盖，319 Part（剑20 源侧仅 15 段，test2 缺 part4）
听力交叉源       48/48   剑10–21
PDF 文件         20/20   剑1–19整本 + 剑20 Test1（分册）
剑21 整本 PDF     1/1     146 页 / 44.1 MB（社区镜像）
```

---

## 8. HTTP 服务

```bash
node ielts-cli.mjs serve 8787
```

### 路由表

| 路径 | 等价调用 |
|---|---|
| `/api/aggregate/:book/:test` | `aggregate({book, test})` |
| `/api/pte-book/:book` | `pteBook(book)` |
| `/api/pte-reading/:book/:test` | `pteReading(book, test)` |
| `/api/pte-listening/:book/:test` | `pteListening(book, test)` |
| `/api/pte-audio/:book/:test` | `pteAudio(book, test)` |
| `/api/reading/:book/:test/:passage` | `reading(book, test, passage)` |
| `/api/reading-index` | `readingIndex()` |
| `/api/listening-index` | `listeningIndex()` |
| `/api/listening-qa/:book/:test` | `listeningQA(book, test)` |
| `/api/listening-script/:book` | `listeningScript(book)` |
| `/api/listening-audio/:book/:test/:part` | `listeningAudio(book, test, part)` |
| `/api/listening-segments/:book/:test/:part` | `listeningSegments(book, test, part)` |
| `/api/pdf/:book` | `pdf(book)` |
| `/api/pdf-lfs/:book` | `pdfLfs(book)` |
| `/api/pdf21` | `pdf21()` |
| `/api/book20-set` | `book20Set()` |
| `/api/explain-pdf/:book` | `explainPdf(book)` |
| `/api/lfs-coverage` | `lfsCoverage()` |
| `/api/ito-script/:book/:test` | `itoScript(book, test)` |
| `/api/ito-listening/:book/:test` | `itoListening(book, test)` |
| `/api/ito-coverage` | `itoCoverage()` |
| `/api/iprog-listening/:book/:test` | `iprogListening(book, test)` |
| `/api/iprog-coverage` | `iprogCoverage()` |
| `/api/cam21-reading/:test` | `cam21Reading(test)` |
| `/api/cam21-listening/:test` | `cam21Listening(test)` |
| `/api/cam21-audio/:test/:section` | `cam21Audio(test, section)` |
| `/api/cam21-full/:test` | `cam21Full(test)` |
| `/api/cam21-index` | `cam21Index()` |
| `/api/cam21-coverage` | `cam21Coverage()` |
| `/api/zhan-index/:book` | `zhanIndex(book)`（剑20/21） |
| `/api/zhan-reading/:book/:test/:passage` | `zhanReading(book, test, passage)`（`?passage=` 同效） |
| `/api/zhan-coverage` | `zhanCoverage()` |
| `/api/mini-list/:page` | `miniList(page)` |
| `/api/mini-solution/:id/:slug` | `miniSolution(id, slug)` |
| `/api/coverage` | `coverage()` |

> 参数省略时使用默认值：`book` 各路由不同（多数 19/20；`ito`/`zhan` 为 21，`iprog` 为 3），
> `test`/`part`/`passage`/`section` 默认 1。
> `/api/reading/:book/:test/:passage`、`/api/listening-audio/:book/:test/:part`、
> `/api/listening-segments/:book/:test/:part`、`/api/zhan-reading/:book/:test/:passage`
> 的第 3 段路径参数也支持用查询串（`?passage=` / `?part=`）传入。

### 调用示例

```bash
curl http://127.0.0.1:8787/api/aggregate/20/1
curl http://127.0.0.1:8787/api/cam21-listening/1
curl "http://127.0.0.1:8787/api/listening-segments/19/1/1"
```

```js
// 前端
const paper = await (await fetch("/api/aggregate/20/1")).json();
renderQuestions(paper.parts.reading.questions);
```

---

## 9. 返回结果总览表

所有接口统一返回对象，正常路径不抛异常。失败时：`{ ok: false, error: "…" }`。
> 例外：`aggregate()` 无顶层 `ok`，请看 `score` / `completeness` / `parts.*.ok`；`score`（如 5/5）只表示分片槽位可用，不代表每题答案正确。

| 接口 | ok | source | 主要数据字段 |
|---|---|---|---|
| `aggregate` | ✓ | 多处 | `parts.*`、`warnings`、`score` |
| `pteBook` | ✓ | practicepteonline | `reading`、`listening`（slug 表） |
| `pteReading` | ✓ | practicepteonline | `passage`、`questions`、`answer_key` |
| `pteListening` | ✓ | practicepteonline | `questions`、`answer_key`、`audio` |
| `pteAudio` | ✓ | practicepteonline | `url`、`all` |
| `reading` | ✓ | userheyy/ielts-reader | `sentences`（中英对照 + 语法） |
| `listeningScript` | ✓ | maslow / userheyy | `tests.testN.partM` |
| `listeningQA` | ✓ | TaroFlink | `questions`（带时间戳） |
| `listeningAudio` | ✓ | maslow | `url` |
| `listeningSegments` | ✓ | userheyy/ielts-reader | `segments[].words[]` |
| `cam21Reading` | ✓ | maqsudjon-cell | `passages`、`questions`、`answer_key` |
| `cam21Listening` | ✓ | maqsudjon-cell | `sections`、`audio`、`transcript` |
| `cam21Audio` | ✓ | maqsudjon-cell | `url` |
| `itoScript` | ✓ | ieltstrainingonline | `sections` |
| `itoListening` | ✓ | ieltstrainingonline | `answer_key` |
| `iprogListening` | ✓ | ieltsprogress.com | `answer_key`、`answer_count`（剑3 T2–T4） |
| `iprogCoverage` | ✓ | ieltsprogress.com | `coverage`、`total_answers` |
| `zhanIndex` | ✓ | top.zhan.com | 篇目表（剑20/21） |
| `zhanReading` | ✓ | top.zhan.com | `sentences`（逐句中英对照） |
| `zhanCoverage` | ✓ | top.zhan.com | `coverage` |
| `pdfLfs` | ✓ | BaBaLiBoo（LFS） | `url`、`bytes` |
| `explainPdf` | ✓ | BaBaLiBoo（LFS） | `url`、`bytes` |
| `pdf21` | ✓ | aqinaq/agylshyn | `url`、`bytes`、`pages` |
| `coverage` | ✓ | multi | 覆盖矩阵 |

### 关键字段速查

| 想做什么 | 用哪个字段 |
|---|---|
| 展示题干 | `.questions[].prompt` |
| 判分 | `.answer_key`（按题号顺序） |
| 看解析 | `.questions[].explanation`（可能为 null） |
| 放音频 | `.audio[].url` / `.url` |
| 精听断句 | `.segments[].words[].start / .end`（听力时间轴） |
| 中英对照 | `.sentences[].en / .zh`（阅读精读）/ `.segments[].en / .zh`（听力时间轴） |
| 拿原文 | `.passage`（阅读）/ `.text.partN`（听力） |
| 查数据来源 | 任意层的 `.source` |

---

## 10. 错误处理

```js
const r = await api.pteReading(3, 2);

if (!r.ok) {
  console.error(r.error);      // 例如 "HTTP 404"、"fetch failed"、超时
  return;
}
```

### 常见 `ok:false` 与处置

| 场景 | `error` | 处置 |
|---|---|---|
| 该套源站未发布 | `no hub` / HTTP 404 | 剑3 听力 T2–T4 属此类；`aggregate()` 已自动用 ieltsprogress.com 兜底答案 |
| 网络抖动 | `fetch failed` | 内部已重试 3 次 + 退避；仍失败可重试 |
| 超时 | `The operation was aborted` | 单请求 30s 上限；批量时并发别开太高 |
| LFS 指针 | 返回 ~130 字节文件 | 改用 `pdfLfs()` 返回的 `url`（media.githubusercontent.com） |

### 聚合的降级表现

```js
const p = await api.aggregate({ book: 3, test: 2 });
p.score       // "5/5"
p.warnings    // []（剑3 T2–T4 已由 ieltsprogress.com 兜底补齐答案）
p.parts.listening_qa.source      // "ieltsprogress.com"（pte 未发布，自动降级）
p.parts.listening_qa.answer_key  // 40 个答案；原文/词级时间轴见 .segments
```

> 有 `warnings` 不代表失败 —— 只表示某个槽位走了备源或部分缺失。
> 判分前请先检查 `parts.listening_qa.answer_key` 是否为空。

---

## 11. 实战范例

### 例 1：做一个在线模考

```js
import * as api from "./ielts-api.mjs";

async function loadExam(book, test) {
  const p = await api.aggregate({ book, test });
  if (!p.parts.reading?.ok) throw new Error("阅读不可用");

  return {
    reading: p.parts.reading.questions.map(q => ({
      no: q.number, text: q.prompt, answer: q.answer, tip: q.explanation,
    })),
    listening: {
      audio: p.parts.listening_audio.filter(a => a.ok).map(a => a.url),
      questions: p.parts.listening_qa.questions,
      keys: p.parts.listening_qa.answer_key,
    },
    warnings: p.warnings,
  };
}

// 判分
function grade(userAns, keys) {
  let right = 0;
  keys.forEach((k, i) => {
    if (String(userAns[i] ?? "").trim().toLowerCase() === String(k).trim().toLowerCase()) right++;
  });
  return { right, total: keys.length, band: Math.round(right / keys.length * 9) };
}
```

### 例 2：批量导出某一册

```js
for (let test = 1; test <= 4; test++) {
  const p = await api.aggregate({ book: 21, test });
  console.log("T" + test, p.score, p.parts.reading.answer_count + "答");
}
// T1 5/5 40答 / T2 5/5 40答 / T3 5/5 40答 / T4 5/5 40答
```

### 例 3：下载听力音频到本地

```js
import { writeFile } from "node:fs/promises";

const a = await api.pteAudio(20, 1);
for (const [i, url] of a.all.entries()) {
  const res = await fetch(url);
  const buf = Buffer.from(await res.arrayBuffer());
  await writeFile("book20-t1-" + (i + 1) + ".mp3", buf);
  console.log("saved", buf.length, "bytes");
}
```

### 例 4：精听练习（词级时间轴）

```js
const seg = await api.listeningSegments(19, 1, 1);   // 仅剑1–19

for (const s of seg.segments) {
  console.log("[" + s.start.toFixed(1) + "s] " + s.speaker + ": " + s.en);
  // 挖空：把关键词换成 ___
  const blanked = s.en.replace(/\b(kakapo|parrot)\b/gi, "_____");
  console.log("  挖空版: " + blanked);
}
```

### 例 5：只取剑21 的逐句原文

```js
const l = await api.cam21Listening(1);
for (const sec of l.transcript) {
  console.log("=== Section " + sec.section + " ===");
  for (const line of sec.lines) {
    console.log(line.speaker + " (" + line.time + "): " + line.text);
  }
}
```

---

## 附：CLI 速查

```bash
node ielts-cli.mjs aggregate 20 1          # 整套聚合
node ielts-cli.mjs pte-book 20             # 册目录（套号 → slug）
node ielts-cli.mjs pte-reading 20 1        # 阅读（原文+题目+答案+解析）
node ielts-cli.mjs pte-listening 20 1      # 听力题目+答案
node ielts-cli.mjs pte-audio 20 1          # 听力音频直链
node ielts-cli.mjs listening-script 20     # 听力原文（按 Part）
node ielts-cli.mjs listening-qa 20 1       # 听力题目（带时间戳，剑16–20）
node ielts-cli.mjs listening-audio 20 1 1  # 指定 Part 的音频
node ielts-cli.mjs listening-segments 19 1 1   # 词级时间轴（精听，仅剑1–19）
node ielts-cli.mjs reading 19 1 1          # 精读（中英对照+语法，仅剑1–19）
node ielts-cli.mjs cam21-full 1            # 剑21 一整套（阅读+听力+音频+原文）
node ielts-cli.mjs cam21-coverage          # 剑21 自检
node ielts-cli.mjs ito-coverage            # 听力交叉源自检（48/48）
node ielts-cli.mjs iprog-coverage          # 剑3 听力答案兜底自检（4/4）
node ielts-cli.mjs iprog-listening 3 2     # 剑3 T2 听力答案键（40 答案）
node ielts-cli.mjs zhan-reading 21 1 1     # 剑20/21 精读（逐句中英对照）
node ielts-cli.mjs zhan-coverage           # 剑20/21 精读自检（24 篇）
node ielts-cli.mjs pdf-lfs 1               # 剑1 整本 PDF
node ielts-cli.mjs pdf21                   # 剑21 整本 PDF（44.1 MB / 146 页）
node ielts-cli.mjs explain-pdf 7           # 剑7 精讲解析 PDF
node ielts-cli.mjs lfs-coverage            # PDF 覆盖自检
node ielts-cli.mjs coverage                # 全源覆盖矩阵
node ielts-cli.mjs serve 8787              # 起 HTTP 服务

# v2（推荐，见文档开头「v2 规范化接口」）：
# books-v2 / test-v2 / questions-v2 / question-v2 / coverage-v2 / asset-v2 / compare-official
```