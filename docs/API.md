# examdata 统一 API 调用指南（`/api/v1`）

> 2026-10-05 状态更新：整个工作区的模块进度、最新断点与验收边界见 [项目总文档](../../docs/PROJECT_STATUS.md)。本文保留的响应、路由数量和测试输出属于各次取证快照，不代表本次重新验证运行服务。

这份文档只回答两件事：

1. **统一网关 `/api/v1` 怎么调**——端点、参数、响应、错误码，以及 board 别名与自动判定；
2. **部署到 VPS 之后，怎么从公网调它**——监听地址、nginx + HTTPS、防火墙、API Key、CORS、限流与故障排查。

安装、CLI、Python 库、备份、升级等部署总纲见 [DEPLOY.md](DEPLOY.md)（2779 行）；本文与它互补，不重复 CLI 全量参考。

> 本文中的**实测输出**是在本机（Windows + Git Bash，仓库根 `C:\Users\weo\Desktop\api\examdata`，数据库 `.data/examdata.db`）真实跑出来的，命令与结果原样贴出。
> 涉及 systemd / nginx / certbot / ufw / firewalld / 云安全组的段落**无法在本机（Windows）验证**，均明确标注「**模板，未在本机验证**」，请把 `<尖括号>` 换成你自己的值。

## 目录

- [1 总览：一个 API，两个上游](#1-总览一个-api两个上游)
- [2 起服务与快速验证（本机）](#2-起服务与快速验证本机)
- [3 统一网关 `/api/v1` 完整参考](#3-统一网关-apiv1-完整参考)
  - [3.1 通用约定：board 归一与自动判定](#31-通用约定board-归一与自动判定)
  - [3.2 `GET /api/v1/boards`](#32-get-apiv1boards)
  - [3.3 `GET /api/v1/paper`](#33-get-apiv1paper)
  - [3.4 `GET /api/v1/search`](#34-get-apiv1search)
  - [3.5 `GET /api/v1/question/{question_id}`](#35-get-apiv1questionquestion_id)
  - [3.6 错误码总表](#36-错误码总表)
  - [3.7 与既有端点的关系](#37-与既有端点的关系)
  - [3.8 `GET /api/v1/materials`（考试发放资料）](#38-get-apiv1materials考试发放资料)
  - [3.9 `GET /api/v1/timetable`（CIE Zone 5 时间表）](#39-get-apiv1timetablecie-zone-5-时间表)
  - [3.10 `GET /api/v1/timetable`（Edexcel 时间表）](#310-get-apiv1timetableedexcel-时间表)
- [4 完整调用示例](#4-完整调用示例)
- [5 公网调用](#5-公网调用)
- [6 数据现状与能力边界](#6-数据现状与能力边界)
- [7 相关文件](#7-相关文件)

## 1 总览：一个 API，两个上游

examdata 在内部对接**两个互不相干的上游站点**，对外只暴露**一套调用形态**。调用方不需要知道「这道题该去哪个站点、那个站点的接口长什么样」。

```text
                    ┌──────────────────────────────────────────┐
   你的客户端  ───▶ │  examdata 统一网关  /api/v1              │
   curl / Python    │                                          │
   浏览器 / 服务器   │  board 别名归一 + 自动判定 + 统一错误码    │
                    └───────────────┬──────────────┬───────────┘
                                    │              │
                 ┌──────────────────▼───┐   ┌──────▼─────────────────────┐
                 │ CIE 源                │   │ Pearson Edexcel 源          │
                 │ cie.fraft.cn          │   │ qualifications.pearson.com │
                 │ 整份 PDF（qp/ms/both）│   │ 整卷 / 按题裁剪 / 题目+答案  │
                 └───────────────────────┘   └────────────────────────────┘
```

| 上游 | 上游主机 | board 规范名 | 数据库 `board.key` | 科目形态 | 考季 | 取卷模式 | 按题裁剪 |
|---|---|---|---|---|---|---|---|
| Cambridge / CIE | `cie.fraft.cn` | `cie` | `cambridge` | 四位数字，如 `0580` | `Mar` / `Jun` / `Nov` | `qp` / `ms` / `both` | 不支持（只给整份 PDF） |
| Pearson Edexcel | `qualifications.pearson.com` | `edexcel` | `edexcel` | 规格代码或科目名，如 `ial18-economics` | `January` / `June` / `October` / `November` | `paper` / `question` / `qa` | 支持（裁成 PNG） |

**两套命名由统一层归一。** 内部 `paperqa` 层认 `cie` / `edexcel`，数据库 `board.key` 是 `cambridge` / `edexcel`。统一网关负责换算，所以：

- 你传 `board=cambridge` 或 `board=cie` 都一样，规范名都是 `cie`；
- 检索接口返回的 `board` 字段是**数据库 key**（`cambridge`），因为那是库里的真实取值；顶层另给一个 `board` 是规范名。两者的对应关系见 3.1 节。

**统一网关核心四端点**：

| 端点 | 干什么 | 读什么 |
|---|---|---|
| `GET /api/v1/boards` | 能力发现：有哪些考试局、别名、考季、模式、是否支持裁剪 | 常量表 |
| `GET /api/v1/paper` | 统一取卷：解析清单 + 下载文件（整卷 / 按题裁剪 / 题目+答案配对） | 上游站点 |
| `GET /api/v1/search` | 跨考试局统一检索题目 | 本地数据库 |
| `GET /api/v1/question/{id}` | 单题聚合：题目内容 + 所属试卷定位 + 可直接调用的取卷链接 | 本地数据库 |

除核心四端点外，`/api/v1` 还提供两类能力（详见 3.8 / 3.9 / 3.10）：

- **考试发放资料** `/api/v1/materials`——按科目列出考生在考试中得到/使用的官方材料（9709 MF19 公式表、各科 insert / source material、Edexcel 公式表与化学数据手册等），可公开取回的原件实时取回；印在试卷内的条目（如化学元素周期表）仅登记、不提供独立文件（取回返回 422 并说明访问方式）；
- **考试时间表** `/api/v1/timetable`——CIE Zone 5 与 Edexcel 时间表转成结构化考试事件（CIE：25 个可得考季 + 2 个不可得考季的证据；Edexcel：106 季 + 6 个取消季 + 15 个不可得季的证据）。

**最新状态摘要（2026-10-05）**：Edexcel IAL 报告现为 43856 题全部有标签、答案关联 88.5%；CIE 定位批次有 63 个服务索引，当前视觉门槛通过 19 卷，最新停止为 `8238/2025/Jun/32` HTTP 502。IAL 统计、数据库检索总数与 CIE 外部定位索引属于不同统计范围，不能混用。本文第 6 节及示例中的 43564 为较早接口快照；最新工作区状态与证据见 [项目总文档](../../docs/PROJECT_STATUS.md)。

## 2 起服务与快速验证（本机）

工作目录必须是仓库根（数据库与 `.env` 都按当前工作目录解析）：

```bash
cd <仓库根>
PYTHONIOENCODING=utf-8 .venv/Scripts/examdata.exe serve --port 8000     # Windows
PYTHONIOENCODING=utf-8 .venv/bin/examdata serve --port 8000             # Linux / macOS
```

`serve` 的全部参数只有三个：`--host`（默认 `127.0.0.1`）、`--port`（默认 `8000`）、`--reload`（开发用）。启动后终端会打印：

```text
API 文档 http://127.0.0.1:8000/docs
```

三条命令确认服务与统一网关都活着（**实测输出**）：

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok","papers":1549}

curl -s http://127.0.0.1:8000/api/v1/boards
# {"schema_version":"1","auto_detect":{...},"boards":[{...},{...}]}   # 见 3.2

curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&leaves_only=true&limit=2'
# {"total":332,"limit":2,"offset":0,"by_board":{"cambridge":332,"edexcel":0},"items":[...],"board":null,"board_source":null}
```

交互式文档在 `/docs`（Swagger UI）、`/redoc`、`/openapi.json`；实测当前 `openapi.json` 共 **71 条路径**（非 `/api/v1` 20 条 + `/api/v1` 51 条：核心四端点 4 条 + 资料 4 条 + 时间表 3 条 + 雅思/托福/索引等 40 条），全部端点在 OpenAPI 里登记。

## 3 统一网关 `/api/v1` 完整参考

### 3.1 通用约定：board 归一与自动判定

**board 别名表**（大小写不敏感，两侧空白自动去掉）：

| 你传的值 | 归一后的规范名 | 数据库 key |
|---|---|---|
| `cie` / `cambridge` / `ca` | `cie` | `cambridge` |
| `edexcel` / `edx` / `pearson` / `ial` | `edexcel` | `edexcel` |
| 其它任意值 | **422** | — |

无法识别时的错误体（实测）：

```json
{"detail":"无法识别的 board: xxx（可用别名：cie/cambridge/ca 或 edexcel/edx/pearson/ial）"}
```

**自动判定 `infer_board(subject)`**：科目代码去掉首尾空白后，整体匹配 `^\d{4}$`（四位数字）→ `cie`；否则 → `edexcel`。**显式传 `board` 时以显式为准**，不做二次推断。

**`board_source`** 告诉你这个 board 是怎么来的：

| 值 | 含义 |
|---|---|
| `"explicit"` | 调用方显式传了 `board`（别名也行） |
| `"inferred"` | 未传 `board`，由科目代码形态自动判定 |
| `null` | 该端点本次请求没有 board 概念（目前只有 `/api/v1/search` 不传 `board` 时） |

**考季别名**：`/api/v1/paper` 的 `season` 走各考试局的别名表，`november`/`nov`/`Nov` 等价，`summer`/`jun`/`June` 等价（实测：CIE 传 `season=november` → 归一成 `Nov`；Edexcel 传 `season=summer` → 归一成 `June`）。完整别名表见 `/api/v1/boards` 的 `season_aliases`。

**错误体**：统一网关的所有错误都是 FastAPI 的 `{"detail": ...}`。参数校验失败（FastAPI 自带，如 `limit=0`）时 `detail` 是**数组**；业务校验失败（如非法 board、非法 season）时 `detail` 是**字符串**。

**请求方法**：业务路由只接受 `GET`，**不接受 `HEAD`**。用 `curl -I` 探测会拿到 `405`，请用 `curl -s -o /dev/null -w '%{http_code}\n'`。

### 3.2 `GET /api/v1/boards`

无参数（多余的参数会被忽略）。响应字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `schema_version` | string | 网关 schema 版本，当前 `"1"` |
| `auto_detect.rule` | string | 自动判定规则的文字说明 |
| `auto_detect.cie_subject_pattern` | string | `^\d{4}$` |
| `auto_detect.fallback_board` | string | 匹配不上时落到 `edexcel` |
| `auto_detect.explicit_board_wins` | bool | 显式传 board 时以显式为准 |
| `boards[]` | array | 每个考试局一条 |

`boards[]` 每条：

| 字段 | 类型 | CIE 取值 | Edexcel 取值 |
|---|---|---|---|
| `board` | string | `cie` | `edexcel` |
| `aliases` | array | `["cie","cambridge","ca"]` | `["edexcel","edx","pearson","ial"]` |
| `db_key` | string | `cambridge` | `edexcel` |
| `name` | string | `Cambridge International` | `Pearson Edexcel` |
| `upstream` | string | `cie.fraft.cn` | `qualifications.pearson.com` |
| `subject_hint` | string | 四位数字科目代码，如 `0580` / `9709` | Pearson 规格代码或科目名，如 `ial18-accounting` |
| `subject_pattern` | string | `^\d{4}$` | `^(?!\d{4}$).+$` |
| `seasons` | array | `["Mar","Jun","Nov"]` | `["January","June","October","November"]` |
| `season_aliases` | array | `mar/march/jun/june/nov/november` | `jan/january/winter/jun/june/summer/oct/october/nov/november` |
| `modes` | array | `["qp","ms","both"]` | `["paper","question","qa"]` |
| `question_crop` | bool | `false` | `true` |
| `default_mode` | string | `qp` | `paper` |

**实测响应**（完整、未截断）：

```bash
curl -s http://127.0.0.1:8000/api/v1/boards
```

```json
{"schema_version":"1","auto_detect":{"rule":"未显式传 board 时：科目代码去空白后匹配四位数字则判为 cie，否则判为 edexcel","cie_subject_pattern":"^\\d{4}$","fallback_board":"edexcel","explicit_board_wins":true},"boards":[{"board":"cie","aliases":["cie","cambridge","ca"],"db_key":"cambridge","name":"Cambridge International","upstream":"cie.fraft.cn","subject_hint":"四位数字科目代码，如 0580 / 9709","subject_pattern":"^\\d{4}$","seasons":["Mar","Jun","Nov"],"season_aliases":["mar","march","jun","june","nov","november"],"modes":["qp","ms","both"],"question_crop":false,"default_mode":"qp"},{"board":"edexcel","aliases":["edexcel","edx","pearson","ial"],"db_key":"edexcel","name":"Pearson Edexcel","upstream":"qualifications.pearson.com","subject_hint":"Pearson 规格代码或科目名（非四位数字），如 ial18-accounting / accounting","subject_pattern":"^(?!\\d{4}$).+$","seasons":["January","June","October","November"],"season_aliases":["jan","january","winter","jun","june","summer","oct","october","nov","november"],"modes":["paper","question","qa"],"question_crop":true,"default_mode":"paper"}]}
```

状态码：`200`。

### 3.3 `GET /api/v1/paper`

统一取卷：把「解析官方清单」和「下载文件」合成一个入口。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `subject` | string | **是** | — | 科目代码，如 `0580`；也是自动判定 board 的依据 |
| `year` | int | **是** | — | 年份，范围 `2000..2099` |
| `season` | string | **是** | — | 考季，取值见 `/api/v1/boards` 的 `seasons`（别名可用） |
| `board` | string | 否 | 自动判定 | 别名见 3.1；显式传入时以显式为准 |
| `paper` | string | 否 | — | Paper 代码：CIE 如 `11`；Edexcel 建议给变体级，如 `wec11-01` |
| `question` | string | 否 | — | 题号，如 `2` / `12(a)` / `1ai`；**仅 Edexcel 的 `question`/`qa` 模式支持** |
| `mode` | string | 否 | 该局默认值 | CIE：`qp`/`ms`/`both`；Edexcel：`paper`/`question`/`qa` |
| `download` | bool | 否 | `true` | `true` 取回文件；`false` 只解析清单（永不下载） |
| `format` | string | 否 | — | `binary`（默认）或 `json`；**给其它值 → 422** |

三种出口：

| 组合 | 返回 |
|---|---|
| `download=false` | JSON 清单，schema 与 `GET /paper-qa/resolve` **完全一致**，另加 `board`、`board_source`；`files` 恒为 `[]` |
| `download=true`（默认）且 `format != json` | **原始字节**：单文件是 PDF，多文件在内存里打 ZIP；响应头带 `Content-Disposition: attachment; filename="..."` 与 `Content-Length` |
| `download=true&format=json` | base64 JSON，schema 与 `GET /paper-qa/query?format=json` **完全一致**，另加 `board`、`board_source` |

`paper` 不传时会命中该组合下的**全部**文件（实测：`0580/2024/Jun` 不带 `paper` → `counts.documents=12`，下载得到一个 2 466 850 字节的 ZIP）。

**实测：CIE 清单**（不下载）

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&download=false'
```

```json
{"schema_version":"1","request":{"board":"cie","subject":"0580","year":2024,"season":"Jun","paper":"11","question":null,"mode":"qp"},"counts":{"documents":1,"files":0,"bytes":0},"documents":[{"name":"0580_s24_qp_11.pdf","url":"https://cie.fraft.cn/obj/Common/Fetch/redir/0580_s24_qp_11.pdf","role":"qp","paper":"11","media_type":"application/pdf"}],"files":[],"board":"cie","board_source":"inferred"}
```

**实测：CIE 下载整卷**（响应头原样）

```bash
curl -sS -D - -o cie_qp.pdf 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp'
```

```text
HTTP/1.1 200 OK
date: Tue, 29 Sep 2026 12:21:01 GMT
server: uvicorn
content-disposition: attachment; filename="0580_s24_qp_11.pdf"
content-length: 235092
content-type: application/pdf
```

落盘文件 235 092 字节，`file` 识别为 `PDF document, version 1.7`。

**实测：CIE 取 QP + MS 配对**（多文件 → 内存 ZIP）

```bash
curl -sS -o cie_both.zip -w 'http=%{http_code} type=%{content_type} size=%{size_download}\n' \
  'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=both'
# http=200 type=application/zip size=438428
```

**实测：Edexcel 整卷 / 按题裁剪 / 题目+答案配对**

```bash
# 整卷（单文件 PDF，358 629 字节）
curl -sS -o edx_paper.pdf -w 'http=%{http_code} type=%{content_type} size=%{size_download}\n' \
  'http://127.0.0.1:8000/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&mode=paper'
# http=200 type=application/pdf size=358629

# 按题裁剪（单张 PNG，18 243 字节，717x228）
curl -sS -o edx_q1.png -w 'http=%{http_code} type=%{content_type} size=%{size_download}\n' \
  'http://127.0.0.1:8000/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&question=1&mode=question'
# http=200 type=image/png size=18243

# 题目 + 答案配对（QP 与 MS 各裁一份，多文件 → ZIP）
curl -sS -o edx_qa.zip -w 'http=%{http_code} type=%{content_type} size=%{size_download}\n' \
  'http://127.0.0.1:8000/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&question=12(a)&mode=qa'
# http=200 type=application/zip size=227320
```

**实测：`format=json`（base64 内联）**——Edexcel `qa` 模式，2 份文档裁出 4 个文件：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&question=12(a)&mode=qa&format=json'
```

```json
{"schema_version":"1","request":{"board":"edexcel","subject":"ial18-economics","year":2024,"season":"June","paper":"wec11-01","question":"12(a)","mode":"qa"},"counts":{"documents":2,"files":4,"bytes":237995},"documents":[{"name":"wec11-01-que-20240510.pdf","url":"https://qualifications.pearson.com/content/dam/pdf/International-Advanced-Level/Economics/2018/Exam-materials/wec11-01-que-20240510.pdf","role":"qp","paper":"wec11-01","media_type":"application/pdf"},{"name":"wec11-01-rms-20240815.pdf","url":"...","role":"ms","paper":"wec11-01","media_type":"application/pdf"}],"files":[{"name":"wec11-01-que-20240510-q12-a-p11.png","media_type":"image/png","role":"qp","size":8089,"sha256":"a8a4d586bed2b73ac0acb079b5064982f5d74178b223227f07b39c9736c49653","page":11,"bbox":[37.51909637451172,54.49399948120117,555.3116455078125,260.91534423828125],"data_base64":"iVBORw0KGgo..."}]}
```

`files[]` 每个成员：`name`、`media_type`、`role`（`qp`/`ms`）、`size`、`sha256`、`page`（裁剪来源页码，1 起，整卷为 `null`）、`bbox`（PDF 用户空间坐标，整卷为 `null`）、`data_base64`（`format=json` 时有值，否则恒为 `null`）。

**文件名规则**：整卷就是上游原始文件名；裁剪件是 `<原文件名去掉 .pdf>-q<题号，括号换成连字符>-p<页码>.png`，例如 `wec11-01-que-20240510-q12-a-p11.png`。多文件打包时固定叫 `paper-qa.zip`。

**状态码**：`200`；`422` 参数非法（含 `format` 非法、`question` 给了 CIE、Edexcel `question`/`qa` 模式缺 `paper` 或 `question`、`paper` 模式却传了 `question`）；`404` 上游没有对应文件；`403` 命中非公开资源；`409` 命中多份候选无法安全选择（Edexcel 给了 `wec11` 这种短代号且存在多个变体时）；`502` 上游故障。

### 3.4 `GET /api/v1/search`

跨考试局统一检索（**只读本地数据库，不访问上游**）。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `keyword` | string | 无 | 题干关键词（大小写不敏感的子串匹配） |
| `subject` | string | 无 | 科目代码，如 `0580` |
| `board` | string | 无 | 别名归一；**不传则跨局检索** |
| `year` | int | 无 | 年份 |
| `session` | string | 无 | **数据库里的原始考季写法**（如 `june` / `june 2025`），与 `/questions` 的 `session` 语义一致，不做归一 |
| `paper` | string | 无 | Paper 代码 |
| `marks_min` | int | 无 | 分值下限 |
| `marks_max` | int | 无 | 分值上限 |
| `leaves_only` | bool | `false` | 只取可独立作答的叶子题 |
| `has_answer` | bool | 无 | 三态：`true` 要求有官方答案、`false` 要求没有、不传不限 |
| `limit` | int | **20** | 范围 `1..500`，越界 422 |
| `offset` | int | `0` | `>= 0`，负值 422 |

响应：

| 字段 | 说明 |
|---|---|
| `total` | 满足条件的题目总数（受 `board` 约束） |
| `limit` / `offset` | 本次分页参数回显 |
| `by_board` | `{"cambridge": n1, "edexcel": n2}`——**同一份过滤条件**分别对两个考试局计数，用于区分「这一局没命中」和「这一局没有数据」 |
| `items[]` | 与 `GET /questions` 的 `items` 形状**完全一致**：`question_id`、`number_path`、`depth`、`kind`、`marks`、`page_from`、`page_to`、`stem_text`、`board`、`subject_code`、`year`、`paper_code`、`paper_id` |
| `board` | 归一后的规范名；未传 `board` 时为 `null` |
| `board_source` | `"explicit"` 或 `null`（未传 board 时没有推断对象） |

**实测**：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/search?limit=2'
```

```json
{"total":44315,"limit":2,"offset":0,"by_board":{"cambridge":751,"edexcel":43564},"items":[{"question_id":752,"number_path":"1","depth":0,"kind":"question","marks":null,"page_from":3,"page_to":3,"stem_text":"Kim takes part in a race that covers a total distance of 20 000 m.\nShe cycles 17 875 m and runs the remaining distance.","board":"cambridge","subject_code":"0580","year":2025,"paper_code":"01","paper_id":17},{"question_id":753,"number_path":"1(a)","depth":1,"kind":"sub","marks":1,"page_from":3,"page_to":3,"stem_text":"Work out the distance Kim runs.\n............................................. m [1]","board":"cambridge","subject_code":"0580","year":2025,"paper_code":"01","paper_id":17}],"board":null,"board_source":null}
```

```bash
# 只看 Edexcel：归一成规范名 edexcel，board_source=explicit，by_board 仍给出两局各自的数量
curl -s 'http://127.0.0.1:8000/api/v1/search?board=pearson&limit=2'
# {"total":43564,"limit":2,"offset":0,"by_board":{"cambridge":751,"edexcel":43564},"items":[...],"board":"edexcel","board_source":"explicit"}

# 大小写不敏感
curl -s 'http://127.0.0.1:8000/api/v1/search?board=CIE&subject=0580&limit=2'
# {"total":440,"limit":2,"offset":0,"by_board":{"cambridge":440,"edexcel":0},"items":[...],"board":"cie","board_source":"explicit"}

# 关键词
curl -s 'http://127.0.0.1:8000/api/v1/search?keyword=triangle&limit=1'
# {"total":177,"limit":1,"offset":0,"by_board":{"cambridge":24,"edexcel":153},"items":[...],"board":null,"board_source":null}

# 非法 board
curl -s 'http://127.0.0.1:8000/api/v1/search?board=xxx'
# 422 {"detail":"无法识别的 board: xxx（可用别名：cie/cambridge/ca 或 edexcel/edx/pearson/ial）"}
```

### 3.5 `GET /api/v1/question/{question_id}`

单题聚合视图：一次请求拿到「题目内容」+「它属于哪份卷子」+「怎么把那卷取回来」。

响应结构：

| 字段 | 说明 |
|---|---|
| `question_id` | 题目 id |
| `board` | **数据库 key**：`cambridge` / `edexcel` |
| `board_source` | 固定 `"inferred"`（由题目自身的归属反推） |
| `source` | 试卷定位信息（见下表） |
| `bundle` | `GET /questions/{id}` 的**原样结果**：`question`、`paper`、`children`、`assets`、`official_answers`、`mark_scheme_entries`、`taxonomy`、`difficulty`、`similar_questions` |

`source` 字段：

| 字段 | 说明 |
|---|---|
| `board` | 数据库 key |
| `board_canonical` | 统一层规范名（`cie` / `edexcel`） |
| `subject_code` | 科目代码 |
| `year` | 年份 |
| `session` | 已归一成 paperqa 认的考季名（`Jun` / `June` …） |
| `session_raw` | 数据库里的原始写法（如 `june`），可能为 `null` |
| `paper_code` | Paper 代码 |
| `document_id` | 文档 id |
| `doc_type` | 文档类型，如 `question_paper` |
| `paper_endpoint` | **可直接调用**的相对 URL，形如 `/api/v1/paper?subject=0580&year=2024&season=Jun&mode=qp&paper=11`；缺关键定位信息（例如无考季的样卷）时为 `null`——绝不拼一个取不回来的 URL |

**实测**：

```bash
curl -s http://127.0.0.1:8000/api/v1/question/1
```

```json
{"question_id":1,"board":"cambridge","board_source":"inferred","source":{"board":"cambridge","board_canonical":"cie","subject_code":"0580","year":2024,"session":"Jun","session_raw":"june","paper_code":"11","document_id":5,"doc_type":"question_paper","paper_endpoint":"/api/v1/paper?subject=0580&year=2024&season=Jun&mode=qp&paper=11"},"bundle":{"question":{"id":1,"number_label":"1","number_path":"1","depth":0,"kind":"question","marks":12,"page_from":2,"page_to":2,"stem_text":"","parse_confidence":0.8,"has_override":true},"paper":{"paper_id":1,"document_id":5,"paper_code":"11","year":2024,"doc_type":"question_paper"},"children":[{"id":2,"number_path":"1(a)","marks":1,"depth":1},{"id":3,"number_path":"1(b)","marks":1,"depth":1},{"id":4,"number_path":"1(c)","marks":1,"depth":1}],"assets":[],"official_answers":[],"mark_scheme_entries":[],"taxonomy":[],"difficulty":[{"source":"estimated","value":0.41,"scale":"0-1","features":{...}}],"similar_questions":[]}}
```

样卷（无考季）的题会拿到 `paper_endpoint: null`（实测 `GET /api/v1/question/272`）：

```json
{"question_id":272,"board":"cambridge","board_source":"inferred","source":{"board":"cambridge","board_canonical":"cie","subject_code":"0580","year":2025,"session":null,"session_raw":null,"paper_code":"02","document_id":11,"doc_type":"specimen_paper","paper_endpoint":null},...}
```

**状态码**：`200`；`404` 题目不存在（`{"detail":"题目 999999 不存在"}`）；`422` id 不是整数。

### 3.6 错误码总表

以下状态码与 `detail` 均为**实测**（`detail` 是字符串时原样贴出；FastAPI 参数校验失败时是数组）。

| 状态码 | 触发场景（示例请求） | `detail` |
|---|---|---|
| `200` | 正常 | — |
| `401` | 服务端设了 `EXAMDATA_API_KEY`，请求没带或带错 `X-API-Key`（豁免路径除外） | `缺少或无效的 X-API-Key 请求头`（响应头带 `WWW-Authenticate: X-API-Key`） |
| `403` | 命中非公开资源（Pearson 登录墙内容） | `Requested Pearson document is not publicly downloadable` |
| `404` | 题目不存在 | `题目 999999 不存在` |
| `404` | 上游没有对应文件 | `Requested CIE PDFs were not found` / `Requested Pearson PDFs were not found` |
| `409` | 命中多份候选，无法安全选择（Edexcel `question`/`qa` 模式给了 `wec11` 这类短代号、且该考季命中多个变体时） | `Specify an exact paper identifier, such as wec11-01` |
| `422` | `format` 不是 `binary`/`json` | `format must be binary or json` |
| `422` | 无法识别的 board | `无法识别的 board: xxx（可用别名：cie/cambridge/ca 或 edexcel/edx/pearson/ial）` |
| `422` | 考季不支持该考试局 | `Unsupported season for this board` |
| `422` | CIE 传了 `question` | `CIE supports whole PDFs only; question selection is unavailable` |
| `422` | CIE 科目不是四位数字或 paper 非法 | `CIE requires a four-digit subject and one/two-digit paper` |
| `422` | Edexcel `question`/`qa` 模式缺 `paper` 或 `question` | `question and paper are required for question/qa mode` |
| `422` | Edexcel `paper` 模式却传了 `question` | `paper mode does not accept question` |
| `422` | 模式不属于该考试局 | `Unsupported mode for this board` |
| `422` | 年份越界 | `year must be between 2000 and 2099` |
| `422` | 缺少必填参数 / 类型错误 / `limit` 越界 | `[{"type":"missing","loc":["query","subject"],"msg":"Field required","input":null}]` 这样的**数组** |
| `502` | 上游不可用或返回不完整清单 | `CIE catalogue unavailable (HTTP 503)` / `Invalid or incomplete CIE catalogue` 等 |
| `405` | 用了 `HEAD`（如 `curl -I`） | `Method Not Allowed`，响应带 `Allow` 头 |

### 3.7 与既有端点的关系

统一网关是**新增入口**，既有端点行为一律未变（回归对比仍可用）。本机实测当前 `openapi.json` 共 **71 条路径** = 非 `/api/v1` 20 条 + `/api/v1` 51 条（核心四端点 4 条 + 资料 4 条 + 时间表 3 条 + 雅思/托福/索引 40 条）。

| 既有端点 | 与统一层的关系 |
|---|---|
| `GET /paper-qa/resolve` | 需要显式传 `board=cie|edexcel`；`/api/v1/paper?download=false` 就是它 + board 归一 + `board`/`board_source` |
| `GET /paper-qa/query` | 同上，对应 `/api/v1/paper`（默认下载）与 `format=json` |
| `GET /questions` | 需要显式传 `board=cambridge|edexcel`（数据库 key）；`/api/v1/search` = 它 + 别名归一 + `by_board` 分局计数 |
| `GET /questions/{id}` | `/api/v1/question/{id}` 的 `bundle` 字段就是它的原样结果 |
| `GET /papers`、`/papers/{id}/tree`、`/taxonomy`、`POST /sample` | 试卷检索 / 整卷题目树 / 知识点 / 随机抽题；统一层暂未包装，按 DEPLOY.md 第 8 章调用 |
| `GET /health` | 存活探针，`{"status":"ok","papers":1549}`；不受 API Key 限制 |
| `GET /assets/{id}` | 取回图形资产原件（`Content-Type` 取资产 mime，不设 `Content-Disposition`） |
| `GET /questions/{id}/explanation`、`/explanations/review-queue` | 生成解析与审核队列 |
| `GET /monitor`、`/review`、`/overrides`、`/classifications`、`/provenance/coverage`、`/questions/{id}/provenance`、`/assets/{id}/provenance` | 治理与溯源视图 |
| `GET /docs`、`/redoc`、`/openapi.json` | 交互式文档；设了 API Key 也可匿名访问 |

各既有端点的逐条参数表见 [DEPLOY.md 第 8 章](DEPLOY.md#8-调用方式二-http-api)。

### 3.8 `GET /api/v1/materials`（考试发放资料）

按考试局/科目列出「考生在考试中实际得到或使用」的官方发放资料（公式表、元素周期表、insert、数据手册等），并对可公开获取的资料按需实时取回原件。逐科调研与实测证据：CIE 见 [`research/exam-materials-cie.md`](../research/exam-materials-cie.md)、Edexcel 见 [`research/exam-materials-edexcel.md`](../research/exam-materials-edexcel.md)。资料目录落盘于 `src/examdata/materials/data/catalog.json`。

| 端点 | 作用 |
|---|---|
| `GET /api/v1/materials` | 资料目录（摘要）：`board` / `subject` / `kind` / `candidate_facing` 过滤；含版本、SHA256 与适用科目；响应另带 `dynamic_endpoints`（CIE 随卷发放入口） |
| `GET /api/v1/materials/{id}` | 单条资料完整记录，附 `content_endpoint` |
| `GET /api/v1/materials/{id}/content` | 取回原件：`format=binary`（默认 PDF）/ `format=json`（base64+sha256）；`version` 为 label 全等或 0 起索引（缺省取第一项） |
| `GET /api/v1/materials/cie/in-paper` | CIE「随卷发放」清单/取回：按 `subject`/`year`/`season`/`paper`/`role` 定位 insert、说明页或保密须知 |

目录过滤参数：

| 参数 | 作用 |
|---|---|
| `board` | `cie`/`cambridge`/`ca` 或 `edexcel`/`edx`/`pearson`/`ial` |
| `subject` | CIE 四位数字科目代码；Edexcel 科目 slug（如 `ial18-chemistry`） |
| `kind` | 资料类别，如 `formula-and-statistical-tables`、`insert` |
| `candidate_facing` | `true` 面向考生；`false` 为考务/教师文件 |

`in-paper` 参数：

| 参数 | 作用 |
|---|---|
| `subject` / `year` / `season` | 四位 CIE 科目代码 / 考季年 / `Mar`、`June`、`Nov`（大小写不敏感） |
| `paper` | 组件号（如 `11`）；不传时返回全部命中 |
| `role` | `in`（insert）/ `ir` / `ci`（保密须知） |
| `download` | `false` 只列清单；`true` 取回文件（唯一命中时；多个命中返回 409 并列出 `detail.papers`） |
| `format` | `binary`（默认）或 `json`（base64） |

二进制出口带头部 `Content-Disposition` 与 `X-Material-Id` / `X-Material-Sha256` / `X-Material-Sha256-Match`（实测与快照对照一致）；没有独立可公开取回版本的条目（如印在试卷内的 CIE 元素周期表）返回 422，`detail` 说明 `access` 判定与已登记的动态入口。

```bash
# 资料目录（实测 8 条）
curl 'http://127.0.0.1:8000/api/v1/materials'
# 9709 的 MF19 公式与统计表：实测 200、311234 字节、sha256 c075388e…、match=true
curl -o mf19.pdf 'http://127.0.0.1:8000/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content'
# Edexcel 一例：IAL 化学数据手册（实测 2542080 字节、sha256 a372a93d…）
curl -o chemistry-data-booklet.pdf 'http://127.0.0.1:8000/api/v1/materials/edexcel-ial-chemistry-data-booklet/content'
# 印在试卷内的条目：422 并说明访问方式
curl 'http://127.0.0.1:8000/api/v1/materials/cie-periodic-table/content'
# → {"detail":{"message":"资料 cie-periodic-table 没有可独立取回的版本","access":"in-paper","dynamic_endpoint":null}}
# CIE 随卷发放：0500 2024 Jun 有 6 份 insert（11/12/13/21/22/23）
curl 'http://127.0.0.1:8000/api/v1/materials/cie/in-paper?subject=0500&year=2024&season=Jun'
# 指定组件取回：实测 200、114871 字节、sha256 7d49097c…（X-Material-Role: in / X-Material-Paper: 11）
curl -o 0500_s24_in_11.pdf 'http://127.0.0.1:8000/api/v1/materials/cie/in-paper?subject=0500&year=2024&season=Jun&paper=11&download=true'
```

### 3.9 `GET /api/v1/timetable`（CIE Zone 5 时间表）

CIE 官方按 Zone 5 发布的考试时间表（PDF）已解析为结构化考试事件（年份/考季/日期/场次/科目与卷号/时长），随仓库快照 `src/examdata/timetable/data/zone5/` 离线提供。调研与逐季核对：[`research/exam-timetable-cie-zone5.md`](../research/exam-timetable-cie-zone5.md)。

| 端点 | 作用 |
|---|---|
| `GET /api/v1/timetable/seasons` | 考季总览：`seasons`（可得，含事件数/窗口数与原件 sha256）+ `unobtainable`（不可得，含 `reason`/`evidence`/`search_exhausted`）+ `unobtainable_search_note_zh`（穷尽检索口径） |
| `GET /api/v1/timetable` | 结构化考试事件：`year`/`season` 必填，可按 `subject`/`date`/`session`/`level` 过滤，`limit`（≤2000，默认 200）/`offset` 分页 |
| `GET /api/v1/timetable/windows` | 各 syllabus/component 的 "Test date windows"：`window_raw` + 解析出的 ISO `window_start`/`window_end`（737 条中 514 条成功解析，其余保留原文、日期为 null；分布见[调研报告](../research/exam-timetable-cie-zone5.md) §7） |

`/api/v1/timetable` 过滤参数：

| 参数 | 作用 |
|---|---|
| `year` / `season` | 考季年 / `Jun`（`June`）或 `Nov`（`November`），大小写不敏感 |
| `subject` | 科目代码，前缀或全等匹配（`97` 命中 `9709`） |
| `date` | ISO 日期 `YYYY-MM-DD` |
| `session` | `AM` / `PM` / `EV` |
| `level` | `IG` / `OL` / `AS` / `AL` / `PR` |
| `limit` / `offset` | 每页条数（1–2000，默认 200）/ 跳过的条数 |

当前快照（2026-10-05 生成）：25 个可得考季（2013-11 … 2026-11）、8307 条考试事件、737 条日期窗口；2 个考季不可得（2019-06、2020-11；均经穷尽检索，标 `search_exhausted: true`），接口对其返回 404 并带 `reason`/`evidence`；未收录考季（如 `2001-06`）返回 422；快照文件缺失返回 503。

```bash
curl 'http://127.0.0.1:8000/api/v1/timetable/seasons'
curl 'http://127.0.0.1:8000/api/v1/timetable?year=2026&season=Nov&subject=9709'
# → {"count":6,"events":[{"date":"2026-10-13","weekday":"Tuesday","session":"AM","level":"AS","subject_code":"9709","paper_code":"13",...}]}
# 2026 Nov 实测 22 条日期窗口
curl 'http://127.0.0.1:8000/api/v1/timetable/windows?year=2026&season=Nov'
# 旧版式考季（2013–2016 经 Wayback 取回）同样可查：2013 Nov 实测 407 条事件，其中 9709 有 7 条
curl 'http://127.0.0.1:8000/api/v1/timetable?year=2013&season=Nov&subject=9709'
# → {"count":7,"events":[{"date":"2013-10-15","weekday":"Tuesday","session":"AM","level":"AS","subject_code":"9709","paper_code":"13",...}]}
# 不可得考季：404 + reason/evidence
curl 'http://127.0.0.1:8000/api/v1/timetable?year=2019&season=Jun'
# → {"detail":{"message":"2019-06 时间表不可得","reason":"文件 513557-june-2019-timetable-zone-5.pdf 从未被有效存档：新域名 CDX 仅 1 条 2024-06-16 404 记录","evidence":"…"}}
```

### 3.10 `GET /api/v1/timetable`（Edexcel 时间表）

Pearson Edexcel 历年时间表（官网现行文件 + Wayback 存档 PDF）已解析为结构化考试事件，随仓库快照 `src/examdata/timetable/data/edexcel/` 离线提供。覆盖四个族谱共 106 个考季（含 13 份 R 卷变体）：UK GCSE 22 季、International GCSE 37 季、International A Level 34 季、GCE A-level 13 季。调研与逐季核对：[`research/exam-timetable-edexcel.md`](../research/exam-timetable-edexcel.md)。

Edexcel 查询在 CIE 参数基础上增加 `board` 与 `family`：

| 参数 | 作用 |
|---|---|
| `board=edexcel` | 必填（别名 `edx` / `pearson`）；不传时默认按 CIE 处理 |
| `family` | 必填：`gcse` / `intgcse` / `ial` / `gce` |
| `year` / `season` | 考季年 / `Jan`（`January`）、`Jun`（`June`）、`Oct`（`October`）、`Nov`（`November`），大小写不敏感 |
| `r_paper` | `true` 取 R 卷变体（仅 IntGCSE 部分考季有，快照键如 `intgcse\|2018\|06\|R`） |
| `subject` / `date` / `session` | 科目代码前缀或全等 / ISO 日期 / `AM` / `PM`（与 CIE 相同） |
| `limit` / `offset` | 每页条数（1–2000，默认 200）/ 跳过的条数 |

当前快照（2026-10-05 生成）：106 季 / 8479 条事件 / 23 个日期窗口；6 个考季因 COVID-19 取消（返回 404 + `cancelled: true` + reason，如 `gcse\|2020\|06`）；15 个考季不可得（返回 404 + reason/evidence，如 `intgcse\|2019\|06`）；未收录考季或非法参数返回 422（`level` 参数仅适用于 CIE）。`/api/v1/timetable/seasons?board=edexcel` 另返回 `counts`（seasons / cancelled / unobtainable）与逐季明细、取消季与不可得季的完整证据。

```bash
curl 'http://127.0.0.1:8000/api/v1/timetable/seasons?board=edexcel&family=ial'
# → {"counts":{"seasons":34,"cancelled":1,"unobtainable":0},...}
curl 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=ial&year=2026&season=June'
# → {"count":90,"events":[{"date":"2026-05-05","weekday":"Tuesday","session":"AM","subject_code":"WAC11","paper_code":"01",...}]}
# R 卷变体
curl 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=intgcse&year=2018&season=June&r_paper=true'
# → {"count":36,"variant":"R",...}
curl 'http://127.0.0.1:8000/api/v1/timetable/windows?board=edexcel&family=gce&year=2017&season=June'
# → {"count":3,"date_windows":[{"subject_code":"6957","paper_code":"01","window_start":"2017-05-08","window_end":"2017-05-26",...}]}
# 取消季：404 + cancelled 标记
curl 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=gcse&year=2020&season=June'
# → {"detail":{"message":"gcse|2020|06 考季已取消","reason":"UK GCSE summer 2020 series cancelled (COVID-19); ...","cancelled":true}}
# 不可得季：404 + reason/evidence
curl 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=intgcse&year=2019&season=June'
# → {"detail":{"message":"intgcse|2019|06 时间表不可得","reason":"穷尽候选（Wayback + 官网直连）后无可用 PDF（非 PDF 或校验失败）","evidence":[...]}}
```

## 4 完整调用示例

### 4.1 curl

```bash
BASE=http://127.0.0.1:8000          # 公网部署换成 https://<你的域名>

# ---- 能力发现 ----
curl -s "$BASE/api/v1/boards"

# ---- CIE 取卷（三位一体：qp / ms / both）----
curl -s  "$BASE/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp&download=false"   # 只看清单
curl -sS -o 0580_qp.pdf   "$BASE/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp"
curl -sS -o 0580_ms.pdf   "$BASE/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=ms"
curl -sS -o 0580_both.zip "$BASE/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=both"
curl -s  "$BASE/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp&format=json" | head -c 400

# ---- Edexcel 取卷 / 按题裁剪 / 题目+答案配对 ----
curl -sS -o edx_paper.pdf "$BASE/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&mode=paper"
curl -sS -o edx_q1.png    "$BASE/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&question=1&mode=question"
curl -sS -o edx_q12a.zip  "$BASE/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&question=12(a)&mode=qa"

# ---- 自动判定：不给 board，四位数字 → CIE ----
curl -s "$BASE/api/v1/paper?subject=9709&year=2026&season=Mar&paper=12&download=false"
# ---- 自动判定：不给 board，非四位数字 → Edexcel ----
curl -s "$BASE/api/v1/paper?subject=ial18-economics&year=2024&season=June&paper=wec11-01&download=false"
# ---- 显式覆盖：同一科目也可以强制指定 ----
curl -s "$BASE/api/v1/paper?board=cambridge&subject=0580&year=2024&season=Jun&paper=11&download=false"

# ---- 检索 ----
curl -s "$BASE/api/v1/search?subject=0580&leaves_only=true&limit=5"
curl -s "$BASE/api/v1/search?board=edexcel&limit=5"
curl -s "$BASE/api/v1/search?keyword=triangle&marks_min=2&limit=5"

# ---- 单题 ----
curl -s "$BASE/api/v1/question/1"
```

### 4.2 Python（`requests`）

```python
import requests

BASE = "http://127.0.0.1:8000"          # 公网部署换成 https://<你的域名>
HEADERS = {"X-API-Key": "<API_KEY>"}    # 服务端没设 EXAMDATA_API_KEY 时删掉这行

# 1) 能力发现
boards = requests.get(f"{BASE}/api/v1/boards", headers=HEADERS, timeout=30).json()
for b in boards["boards"]:
    print(b["board"], b["aliases"], b["seasons"], b["modes"], b["question_crop"])

# 2) 跨考试局检索
r = requests.get(f"{BASE}/api/v1/search",
                 params={"subject": "0580", "leaves_only": "true", "limit": 5},
                 headers=HEADERS, timeout=30).json()
print(r["total"], r["by_board"])
for item in r["items"]:
    print(item["question_id"], item["number_path"], item["marks"], item["board"])

# 3) 取卷：先看清单，再决定下不下载
manifest = requests.get(f"{BASE}/api/v1/paper",
                        params={"subject": "0580", "year": 2024, "season": "Jun",
                                "paper": "11", "download": "false"},
                        headers=HEADERS, timeout=60).json()
print(manifest["board"], manifest["board_source"], [d["name"] for d in manifest["documents"]])

# 3a) 整卷 PDF 落盘（文件名从响应头拿）
resp = requests.get(f"{BASE}/api/v1/paper",
                    params={"subject": "0580", "year": 2024, "season": "Jun",
                            "paper": "11", "mode": "qp"},
                    headers=HEADERS, timeout=300)
resp.raise_for_status()
name = resp.headers["content-disposition"].split('filename="')[1].rstrip('"')
open(name, "wb").write(resp.content)
print(name, len(resp.content))

# 3b) Edexcel 按题裁剪（PNG）与题目+答案配对（ZIP）
crop = requests.get(f"{BASE}/api/v1/paper",
                    params={"subject": "ial18-economics", "year": 2024, "season": "June",
                            "paper": "wec11-01", "question": "12(a)", "mode": "qa"},
                    headers=HEADERS, timeout=300)
open("wec11-01-q12a.zip", "wb").write(crop.content)

# 3c) 只接受 JSON 的客户端：base64 内联
payload = requests.get(f"{BASE}/api/v1/paper",
                       params={"subject": "ial18-economics", "year": 2024, "season": "June",
                               "paper": "wec11-01", "question": "12(a)", "mode": "qa",
                               "format": "json"},
                       headers=HEADERS, timeout=300).json()
import base64
for f in payload["files"]:
    if f["media_type"] == "image/png":
        open(f["name"], "wb").write(base64.b64decode(f["data_base64"]))
        print(f["name"], f["page"], f["bbox"])

# 4) 单题聚合
q = requests.get(f"{BASE}/api/v1/question/1", headers=HEADERS, timeout=30).json()
print(q["board"], q["source"]["board_canonical"], q["source"]["paper_endpoint"])
# 顺着 paper_endpoint 就能把这道题所在的那份卷取回来：
pdf = requests.get(BASE + q["source"]["paper_endpoint"], headers=HEADERS, timeout=300)
print(len(pdf.content), pdf.headers["content-type"])
```

仓库里还有现成的可运行客户端（覆盖同样四类调用）：`examples/python_client.py`、`examples/node_client.mjs`（Node 18+，零依赖）、`examples/browser.html`。

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe examples/python_client.py demo
python examples/python_client.py search --subject 0580 --leaves-only --limit 5
python examples/python_client.py paper --subject 0580 --year 2024 --season Jun --paper 11 --out /tmp/examdata-out
node examples/node_client.mjs question --id 1
```

### 4.3 浏览器 `fetch`

页面与 API **同源**时（例如页面就部署在 `https://<你的域名>/` 下）不需要任何额外配置：

```html
<script>
const BASE = "";   // 同源留空；跨源写 "https://<你的域名>"
const API_KEY = "<API_KEY>";   // 服务端没设 EXAMDATA_API_KEY 时删掉

async function search() {
  const params = new URLSearchParams({ subject: "0580", leaves_only: "true", limit: "5" });
  const resp = await fetch(`${BASE}/api/v1/search?${params}`, {
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
  });
  if (!resp.ok) {                      // 401/422/404 的 body 都是 {"detail": ...}
    console.error(resp.status, await resp.json());
    return;
  }
  const data = await resp.json();
  console.log(data.total, data.by_board, data.items);
}

async function downloadPaper() {
  const params = new URLSearchParams({
    subject: "0580", year: "2024", season: "Jun", paper: "11", mode: "qp",
  });
  const resp = await fetch(`${BASE}/api/v1/paper?${params}`, {
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
  });
  if (!resp.ok) { console.error(resp.status, await resp.json()); return; }
  const blob = await resp.blob();      // 单文件 PDF，或多文件 ZIP
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "paper.bin";            // 真实文件名见 resp.headers.get("content-disposition")
  a.click();
}
</script>
```

**页面与 API 不同源**时（例如页面在 `http://127.0.0.1:5500`、API 在 `https://<你的域名>`），浏览器会先发预检请求（`OPTIONS`）。必须让服务端开 CORS，否则控制台报 `blocked by CORS policy`：

```bash
# 只放行你的页面来源（推荐）
EXAMDATA_CORS_ORIGINS='https://<你的页面域名>' examdata serve --host 127.0.0.1 --port 8000
# 多个来源用逗号分隔；调试期可临时用 '*'
EXAMDATA_CORS_ORIGINS='https://a.example.com,https://b.example.com' examdata serve --port 8000
```

实测（临时挂上安全层）：允许的来源预检返回 `200` 且带 `access-control-allow-origin`；不在白名单的来源拿不到该响应头，浏览器会拦下。CORS 层在鉴权层外层，所以预检不带 `X-API-Key` 也能通过，`401` 响应同样会补上 CORS 头。

### 4.4 一条命令自检

`scripts/smoke_public_api.py` 只用标准库，任何装了 Python 3.11+ 的机器都能跑，用来确认「部署好的 API 到底通没通」：

```bash
python scripts/smoke_public_api.py --base-url http://127.0.0.1:8000
python scripts/smoke_public_api.py --base-url https://<你的域名> --api-key <API_KEY>
python scripts/smoke_public_api.py --base-url https://<你的域名> --skip-download   # 省流量
```

实测（对本地 8791 端口的服务，完整输出；2026-10-05 重跑）：

```text
examdata 上线自检
目标      http://127.0.0.1:8791
超时      30s（下载检查另有下限 180s）
鉴权      未提供（不检查鉴权）
下载检查  执行
--------------------------------------------------------------------
[1/8] 存活探针 GET /health
      PASS  HTTP 200  status=ok  papers=1549

[2/8] 能力发现 GET /api/v1/boards
      PASS  HTTP 200  boards=cie,edexcel  schema_version=1

[3/8] 跨考试局检索 GET /api/v1/search?limit=1
      PASS  HTTP 200  total=44607  by_board={"cambridge": 751, "edexcel": 43856}

[4/8] 考试时间表 GET /api/v1/timetable/seasons（CIE 与 Edexcel ial）
      PASS  HTTP 200  board=cie  zone=5  totals.available_seasons=25 | edexcel family=ial counts.seasons=34（期望 34，该局总数 106）

[5/8] 考试资料 GET /api/v1/materials
      PASS  HTTP 200  count=8

[6/8] 清单解析 GET /api/v1/paper?download=false（不下载）
      PASS  HTTP 200  counts.documents=12  counts.files=0  board=cie  board_source=inferred

[7/8] 真实下载 GET /api/v1/paper?mode=qp（0580/2024/Jun）
      PASS  HTTP 200  application/zip  Content-Length=2466850  实收=2466850B  文件头=PK  耗时=21.72s

[8/8] 错误语义：不存在的路径必须 404
      PASS  HTTP 404  detail=Not Found

====================================================================
通过 8 / 8（失败 0，跳过 0），耗时 32.55s
结论：全部通过，API 已就绪。
====================================================================
```

带 `--api-key` 时会多一项鉴权检查（共 9 项）。上面完整输出 8 项全过；加 `--skip-download` 时下载项会跳过（实测 7 通过 / 1 跳过 / 0 失败）。第 7 项耗时随上游波动（历次实测 16～22 秒），不必对具体秒数敏感。

第 6、7 项会真的访问上游站点（CIE 走 `cie.fraft.cn`），上游临时不可用时它们会 FAIL——那是上游问题，不是你的部署问题。

## 5 公网调用

### 5.1 先选暴露方式

| 方式 | 适用 | 代价 | 章节 |
|---|---|---|---|
| **SSH 隧道** | 少数几台机器、少数几个人 | 每个用户要服务器账号；浏览器里不能直接用 | DEPLOY.md 第 10 章 |
| **只监听内网** | 同一 VPC / 内网的其他服务调用 | 出不了公网 | DEPLOY.md 第 11 章 |
| **nginx + HTTPS（本文重点）** | 要给别人用、要浏览器直接访问 | 需要域名与证书；必须自己做访问控制 | 5.2–5.9 |

### 5.2 监听地址：`--host 0.0.0.0` 与为什么不要裸奔

`examdata serve` 默认只监听 `127.0.0.1`（只有本机能连）。要让**同机 nginx** 转发，保持默认即可——nginx 就在本机，走回环最安全。

```bash
# 推荐：只监听回环，由同机 nginx 对外
examdata serve --host 127.0.0.1 --port 8000

# 需要被别的机器直连时才用（把 8000 端口暴露到网络上）
examdata serve --host 0.0.0.0 --port 8000
```

**为什么不要把 8000 端口裸奔在公网**：

1. 数据库里是**受版权保护的真题内容**（Cambridge / Pearson 的试卷、评分标准、题目图片），裸奔等于把版权风险转嫁给你的服务器与域名；
2. 服务本身**不区分调用方**：`/paper-qa/*` 会让你的服务器替任何人去访问上游站点，成为免费的代理与放大点；
3. **没有 HTTPS**：明文传输，中间人可读可改；
4. 限流、CORS、访问控制都还没有（要靠 `EXAMDATA_API_KEY` / nginx 补）。

正确形态是：**examdata 只监听 `127.0.0.1`，由同机 nginx 提供 443/80**，访问控制、TLS、限流、日志都在 nginx 这一层做。

```text
客户端 ──HTTPS(443)──▶ nginx ──HTTP(127.0.0.1:8000)──▶ examdata
                         │
                    访问控制 / 限流 / 日志都在这里
```

### 5.3 systemd 常驻

> **模板，未在本机验证**（本机是 Windows，跑不了 systemd）。占位符按你的环境替换。

`/etc/systemd/system/examdata.service`：

```ini
[Unit]
Description=examdata 统一检索 API
Documentation=file:///srv/examdata/docs/API.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=examdata
Group=examdata
WorkingDirectory=/srv/examdata
Environment=EXAMDATA_DATA_DIR=/var/lib/examdata
Environment=EXAMDATA_DATABASE_URL=sqlite:////var/lib/examdata/examdata.db
Environment="EXAMDATA_USER_AGENT=ExamDataBot/0.1 (+https://<你的域名>/examdata; contact=<你的邮箱>)"
# 需要 API Key 保护时打开下面这行（值换成你自己的随机串）
# Environment=EXAMDATA_API_KEY=<API_KEY>
# 需要浏览器跨域访问时打开下面这行（逗号分隔的 origin 白名单）
# Environment=EXAMDATA_CORS_ORIGINS=https://<你的页面域名>
Environment=PYTHONUNBUFFERED=1
ExecStart=/srv/examdata/.venv/bin/examdata serve --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

要点（与 DEPLOY.md 12.2–12.3 一致，不重复展开）：

- `EXAMDATA_DATA_DIR` 与 `EXAMDATA_DATABASE_URL` **必须成对设置**；SQLite 绝对路径是**四个斜杠**：`sqlite:////var/lib/examdata/examdata.db`。
- `Environment=` 的值含空格时必须整体加双引号（`EXAMDATA_USER_AGENT` 就是这种）。
- `ExecStart` 里**不要**写 `--host 0.0.0.0`，让 nginx 走回环。
- 生成一个 API Key：`python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now examdata
sudo systemctl status examdata
sudo journalctl -u examdata -n 50 --no-pager
sudo ss -ltnp | grep 8000        # 应当显示 127.0.0.1:8000，而不是 0.0.0.0:8000
```

### 5.4 nginx 反向代理 + HTTPS

> **模板，未在本机验证**。`nginx -t` 通过后再 reload。

安装 nginx 与 certbot：

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
# RHEL / Rocky / Alma
sudo dnf install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/examdata`（RHEL 系放 `/etc/nginx/conf.d/examdata.conf`）：

```nginx
# 限流区：按客户端 IP，平均 5 req/s，突发 20；下载类接口单独放宽
limit_req_zone $binary_remote_addr zone=examdata_api:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=examdata_dl:10m rate=1r/s;

server {
    listen 80;
    listen [::]:80;
    server_name <你的域名>;

    access_log /var/log/nginx/examdata.access.log;
    error_log  /var/log/nginx/examdata.error.log;

    # 取卷/下载：上游要现取 PDF（含按主机 1 秒限速），超时给足
    location /api/v1/paper {
        limit_req zone=examdata_dl burst=5 nodelay;
        limit_req_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";

        # 想由 nginx 统一注入 API Key（客户端就不必带）时打开：
        # proxy_set_header X-API-Key <API_KEY>;

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;          # PDF/ZIP 直接透传，不先缓冲到磁盘
        proxy_request_buffering off;
    }

    # 其余接口：快、限流紧一些
    location / {
        limit_req zone=examdata_api burst=20 nodelay;
        limit_req_status 429;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";
        # proxy_set_header X-API-Key <API_KEY>;

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;
    }
}
```

说明：

- `proxy_read_timeout 300s`：默认 60 秒不够——服务端要现去上游下载整份 PDF，还要遵守「每主机至少 1.0 秒 + 0~0.5 秒抖动」的抓取限速，慢的时候远超 60 秒，客户端会先看到 nginx 的 `504`。
- `proxy_buffering off`：PDF / ZIP 是二进制大对象，缓冲既费磁盘又增加首字节延迟。
- **不需要** `client_max_body_size`：所有路由都不接受请求体。
- **同源页面不需要 CORS**；页面与 API 不同源才需要（见 5.6）。
- `X-API-Key` 是自定义头，nginx 默认会原样转发；上面的 `proxy_set_header X-API-Key` 是**可选**的「由网关统一注入 key」写法。

启用并签发证书：

```bash
sudo ln -s /etc/nginx/sites-available/examdata /etc/nginx/sites-enabled/examdata
sudo nginx -t && sudo systemctl reload nginx

# 此时 http://<你的域名>/health 应当返回 {"status":"ok","papers":...}
sudo certbot --nginx -d <你的域名>          # 会自动改写 nginx 配置加上 443 与证书路径
sudo certbot renew --dry-run                # 验证自动续期链路
curl -s -o /dev/null -w '%{http_code}\n' https://<你的域名>/health   # 期望 200
```

证书要点：certbot 只为你 nginx 里**已声明**的域名签发（要 `www.` 就先把 `server_name` 写全）；域名在国内无法签发 Let's Encrypt 时，换商业证书或云厂商免费证书，把路径写进 `ssl_certificate` / `ssl_certificate_key` 即可。

### 5.5 防火墙与安全组

只放行 **22（SSH）、80、443**，**不要放行 8000**。

```bash
# Ubuntu / Debian（ufw）
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw enable && sudo ufw status verbose

# CentOS / RHEL / Rocky（firewalld）
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload && sudo firewall-cmd --list-all
```

**云服务器还有一层安全组**（阿里云 / 腾讯云 / AWS / Azure 等）：入方向同样只放行 22/80/443，不要放行 8000。

从**另一台机器**验证 8000 没有暴露：

```bash
curl -m 5 http://<服务器公网IP>:8000/health     # 应当连接超时或被拒绝
```

如果拿到了 `{"status":"ok",...}`，说明服务监听在了 `0.0.0.0` 或防火墙没生效——任何人都能绕过 nginx 直接读你的库，必须回去修。

### 5.6 从别的地方调用

**（1）在服务器本机**：

```bash
curl -s http://127.0.0.1:8000/api/v1/boards | head -c 200
```

**（2）从你的笔记本 / 另一台服务器（Python）**：把 base URL 换成公网域名，需要 key 就加 `X-API-Key`。

```python
import requests
BASE = "https://<你的域名>"
r = requests.get(f"{BASE}/api/v1/search",
                 params={"subject": "0580", "leaves_only": "true", "limit": 5},
                 headers={"X-API-Key": "<API_KEY>"},   # 服务端没设就删掉
                 timeout=30)
print(r.status_code, r.json()["total"])
```

**（3）浏览器页面**：

- 页面与 API **同源**（都挂在 `https://<你的域名>` 下）：什么都不用配，直接 `fetch`。
- 页面与 API **不同源**：服务端必须设 `EXAMDATA_CORS_ORIGINS`，否则浏览器拦下请求。写法与实测见 4.3 节。
- 也可以在 nginx 里手工加 CORS 头（不想改服务端配置时）：

```nginx
    location / {
        # 只允许你的页面来源；需要携带凭据时把 * 换成具体 origin 并加 always
        add_header Access-Control-Allow-Origin "https://<你的页面域名>" always;
        add_header Access-Control-Allow-Headers "X-API-Key, Content-Type" always;
        add_header Access-Control-Allow-Methods "GET, OPTIONS" always;
        if ($request_method = OPTIONS) { return 204; }
        # ... 其余 proxy_pass 配置同上
    }
```

**（4）其他服务器 / 定时任务**：与（2）相同；把 `https://<你的域名>` 与 `X-API-Key` 写进配置或环境变量，不要硬编码在仓库里。

### 5.7 用 `EXAMDATA_API_KEY` 保护服务

服务端设了这个环境变量之后，**除豁免路径外**的所有请求都必须带 `X-API-Key` 头且值一致：

```bash
EXAMDATA_API_KEY='<API_KEY>' examdata serve --host 127.0.0.1 --port 8000
# systemd 部署：Environment=EXAMDATA_API_KEY=<API_KEY>（见 5.3）
```

- 豁免路径：`/health`、`/docs`、`/redoc`、`/openapi.json`（探活与接口文档必须能匿名访问）。
- 不带或带错 → `401`，响应体 `{"detail":"缺少或无效的 X-API-Key 请求头"}`，响应头带 `WWW-Authenticate: X-API-Key`。
- 不设置该变量 → 完全放行（适合只监听 `127.0.0.1` 的本地部署）。

调用方：

```bash
curl -H 'X-API-Key: <API_KEY>' https://<你的域名>/api/v1/boards
```

```python
requests.get("https://<你的域名>/api/v1/boards", headers={"X-API-Key": "<API_KEY>"}, timeout=30)
```

```javascript
fetch("https://<你的域名>/api/v1/boards", { headers: { "X-API-Key": "<API_KEY>" } })
```

实测（本机真实跑过）：不带 key 调 `/api/v1/boards` → `401`；带对 → `200`；`/health`、`/docs`、`/openapi.json` 不带 key 也返回 `200`；`/questions` 不带 key 同样 `401`。

两个注意点：

1. **Swagger UI 不会自动带 key**：`/docs` 能匿名打开，但页面里点 “Try it out” 发出的请求不带 `X-API-Key`，会拿到 `401`。要么在浏览器插件里加头，要么改用 `curl` / 脚本验证。
2. key 是**单一静态值**，没有按用户区分、没有过期时间。要「每人一个账号」请用 nginx Basic 认证（DEPLOY.md 12.7），要更细的权限得自己在前置网关做。

### 5.8 限流交给 nginx

服务自身**没有**限流。用 nginx 的 `limit_req` 兜（配置见 5.4，这里是解释）：

```nginx
limit_req_zone $binary_remote_addr zone=examdata_api:10m rate=5r/s;   # 普通接口 5 req/s/IP
limit_req_zone $binary_remote_addr zone=examdata_dl:10m rate=1r/s;    # 取卷 1 req/s/IP

location /api/v1/paper {
    limit_req zone=examdata_dl burst=5 nodelay;   # 允许突发 5 个，超出立刻 429
    limit_req_status 429;
    # ...
}
```

- `rate` 是**平均速率**，`burst` 是允许的瞬时队列深度；`nodelay` 表示突发额度内的请求立即处理而不是排队。
- 触发限流返回 `429`，不是 `403`。
- 取卷接口特别贵：每个请求都会让你的服务器去上游下载整份 PDF，务必单独收紧。
- 改完 `sudo nginx -t && sudo systemctl reload nginx`。
- 想按 key 而不是按 IP 限流，可以把 `limit_req_zone` 的键换成 `$http_x_api_key`。

### 5.9 故障排查

逐条给排查命令。先记住一个判断依据：**nginx 自己产生的错误是 HTML 页面，examdata 的错误是 JSON `{"detail": ...}`**。

**（1）连不上 / 超时**

```bash
sudo systemctl status examdata                       # 服务活着吗
sudo journalctl -u examdata -n 100 --no-pager        # 启动报错？
sudo ss -ltnp | grep 8000                            # 在监听吗、监听在哪
curl -s -m 5 http://127.0.0.1:8000/health            # 本机回环通不通
curl -s -m 10 -o /dev/null -w '%{http_code}\n' http://<你的域名>/health   # 走域名通不通
dig +short <你的域名>                                 # DNS 指对了吗
sudo ufw status verbose                              # 防火墙（firewalld: firewall-cmd --list-all）
```

依次排除：服务没起 → 只监听了回环而你从外面直连 8000（正常现象）→ 防火墙/安全组没放行 443 → DNS 未解析到本机。

**（2）502 Bad Gateway**

```bash
sudo journalctl -u examdata -n 50 --no-pager         # 服务是不是崩了 / 端口对不对
curl -s -m 5 http://127.0.0.1:8000/health            # nginx 能否打到上游
sudo tail -50 /var/log/nginx/examdata.error.log      # nginx 侧的真实原因
getenforce                                          # RHEL 系 SELinux 拦截
sudo setsebool -P httpd_can_network_connect 1        # SELinux 拦截时放行（RHEL 系）
```

常见原因：examdata 没启动、`proxy_pass` 端口写错、服务监听在别的端口、SELinux 禁止 nginx 连本地端口。

**（3）403 Forbidden**

```bash
curl -s -i http://127.0.0.1:8000/api/v1/boards | head -5     # 绕过 nginx，看是不是服务自己返回的
curl -s -i https://<你的域名>/api/v1/boards | head -5        # 经过 nginx 的
sudo grep -n "auth_basic\|allow\|deny" /etc/nginx/sites-enabled/examdata
```

- 响应是 **HTML** → nginx 层的拒绝：Basic 认证没带凭据、IP 白名单没放行你（DEPLOY.md 12.7）。
- 响应是 **JSON** `{"detail": ...}` → 服务层：`403` 通常来自上游资源非公开（Pearson 登录墙内容），换一份公开资源。

**（4）504 / 请求超时**

```bash
# 先排除「慢」是不是出在上游：清单解析很快，下载才慢
time curl -s -m 60 'https://<你的域名>/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&download=false' >/dev/null
time curl -s -m 300 -o /dev/null 'https://<你的域名>/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp'
grep -n "proxy_read_timeout" /etc/nginx/sites-enabled/examdata
sudo tail -50 /var/log/nginx/examdata.error.log
```

下载路径本来就慢（服务端要先访问上游，且受 1 秒/请求的抓取限速约束），所以 `proxy_read_timeout` 要给到 `300s`；仍超时说明上游慢或被限流，稍后重试。

**（5）401**

```bash
curl -s -i https://<你的域名>/api/v1/boards | head -5          # 看 detail 与 WWW-Authenticate
curl -s -H 'X-API-Key: <API_KEY>' https://<你的域名>/api/v1/boards
```

确认请求头名字是 `X-API-Key`（不是 `Authorization`），值与服务端 `EXAMDATA_API_KEY` 完全一致（注意复制时的换行与空格）；如果 key 是通过 nginx `proxy_set_header` 注入的，检查那行有没有被注释掉。

**（6）429**

命中 nginx 限流。`grep -n "limit_req" /etc/nginx/sites-enabled/examdata` 看速率与 `burst`；取卷接口默认给的是 1 req/s，批量抓卷请加间隔或临时放宽。

**（7）证书问题**

```bash
curl -vI https://<你的域名>/health 2>&1 | head -20       # 看证书链与有效期
sudo certbot certificates                                 # 当前证书与到期时间
sudo certbot renew --dry-run                              # 续期链路是否可用
date                                                      # 服务器时间偏差过大会导致校验失败
sudo ss -ltnp | grep ':80 '                               # HTTP-01 验证需要 80 可达
```

自签证书调试时可以加 `-k`（`curl -k`）或 `--insecure`（`smoke_public_api.py`），但**不要**把 `-k` 写进生产脚本。

**（8）405 / CORS**

- `curl -I` 拿 `405` 是**正常**的：路由不支持 `HEAD`，用 `curl -s -o /dev/null -w '%{http_code}\n'` 代替。
- 浏览器控制台报 `blocked by CORS policy`：确认服务端设了 `EXAMDATA_CORS_ORIGINS` 且包含页面的**完整 origin**（含 scheme，如 `https://app.example.com`，不要带路径）；预检失败时先用 `curl -i -X OPTIONS -H 'Origin: <你的页面origin>' -H 'Access-Control-Request-Method: GET' https://<你的域名>/api/v1/boards` 看有没有 `access-control-allow-origin`。

### 5.10 上线验收清单

- [ ] `sudo systemctl status examdata` 是 `active (running)`
- [ ] `sudo ss -ltnp | grep 8000` 显示 `127.0.0.1:8000`
- [ ] `curl -s http://127.0.0.1:8000/health` 返回 `{"status":"ok","papers":1549}`
- [ ] `curl -s https://<你的域名>/api/v1/boards` 返回 `schema_version` 与两个 board
- [ ] `python scripts/smoke_public_api.py --base-url https://<你的域名> --api-key <API_KEY>` 全部 PASS
- [ ] 从外部机器 `curl -m 5 http://<服务器公网IP>:8000/health` 失败
- [ ] 云安全组只放行 22/80/443
- [ ] `certbot renew --dry-run` 成功
- [ ] 设了 `EXAMDATA_API_KEY` 时：不带 key 的请求被 `401` 拒绝，`/health` 仍可匿名访问
- [ ] 需要跨域时：`EXAMDATA_CORS_ORIGINS` 只列出你的页面来源（生产环境不要用 `*`）

## 6 数据现状与能力边界

> 本节原有表格与接口输出为历史取证快照。后续 Edexcel r13 报告及 CIE 16:36 汇总已更新，当前状态以 [项目总文档](../../docs/PROJECT_STATUS.md) 与其链接证据为准；不将旧响应数字改写成未经重跑的接口输出。

如实说明，免得你以为是接口坏了（以下为 2026-10-05 快照）：

| 项 | 现状 |
|---|---|
| Cambridge（`board.key=cambridge`） | **751 道题 / 16 卷**；科目 `0580`、`9709`、`0620`、`0478`；文档 35 份 |
| Edexcel（`board.key=edexcel`） | **43564 道题 / 1533 卷 / 3732 份文档**（1832 QP + 1884 MS + 14 examiner report + 2 其它） |
| `/api/v1/search` 的 `by_board` | `{"cambridge": 751, "edexcel": 43564}`——**这是数据现状，不是接口缺陷** |
| `/api/v1/paper` | **两个考试局都能真实取到文件**（本文 3.3 节的字节数都是实测值） |
| 数据库里的考季写法 | 不规范（`june` / `june 2025` / `november 2025`），所以 `/api/v1/search` 的 `session` 按原始值匹配，不做归一；`/api/v1/question/{id}` 的 `source.session` 才是归一后的考季名 |
| CIE 题目裁剪 | 不支持：上游只提供整份 PDF，传 `question` 会 `422` |
| Edexcel 题号裁剪 | 支持；短代号（如 `wec11`）命中多个变体会 `409`，稳妥写法是给变体级 `wec11-01` |
| 版权 | 库里是受版权保护的真题内容；公开部署前请自行确认使用范围与合规性 |

数据不够用时，用 CLI 补（详见 DEPLOY.md 第 5 章与第 7 章）：

```bash
examdata db-stats                       # 看当前规模
examdata sync --adapter cambridge --resources 5
examdata parse-docs && examdata enrich
```

## 7 相关文件

| 文件 | 用途 |
|---|---|
| `docs/API.md` | 本文：统一网关调用 + 公网部署 |
| `docs/DEPLOY.md` | 部署总纲：安装、数据准备、CLI 全量参考、既有 HTTP 端点逐条说明、Python 调用、运维、备份 |
| `src/examdata/api/unified.py` | 统一网关实现（board 归一、自动判定、核心四端点） |
| `src/examdata/materials/` | 考试发放资料：目录 `catalog.py` + `data/`（`catalog.json`、逐科 `subjects_*.json`）；取回 `fetch.py` + `router.py` |
| `src/examdata/timetable/` | 考试时间表：CIE Zone 5（解析 `parser.py` + `build.py`，快照 `data/zone5/`）与 Edexcel（解析 `edexcel_parser.py` + `build_edexcel.py`，快照 `data/edexcel/`），共用路由 `router.py` |
| `research/` | 调研报告：`exam-materials-cie.md`、`exam-materials-edexcel.md`、`exam-timetable-cie-zone5.md`、`exam-timetable-edexcel.md`（结论与实测证据） |
| `src/examdata/api/app.py` | 应用入口：挂载既有路由与统一网关 |
| `src/examdata/api/security.py` | 可选安全层：`EXAMDATA_CORS_ORIGINS` 与 `EXAMDATA_API_KEY` |
| `src/examdata/paperqa/` | 上游适配：`sources/cie_fraft.py`、`sources/pearson.py`、`locator.py`（裁剪）、`errors.py`（状态码） |
| `scripts/smoke_public_api.py` | 上线自检脚本（只用标准库） |
| `examples/python_client.py` / `examples/node_client.mjs` / `examples/browser.html` | 三种形态的可运行客户端示例 |
