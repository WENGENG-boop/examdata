# examdata 统一网关（/api/v1）curl 完整示例

本文件是可直接复制粘贴的 curl 命令清单，覆盖统一网关的全部端点：

| 端点 | 作用 | 是否出网 |
|---|---|---|
| `GET /api/v1/boards` | 能力发现：考试局、别名、科目形态、考季、模式 | 否 |
| `GET /api/v1/search` | 跨考试局题目检索（读本地数据库） | 否 |
| `GET /api/v1/paper` | 统一取卷：解析清单 / 下载 PDF / base64 JSON | 是（访问考试局站点） |
| `GET /api/v1/question/{id}` | 单题聚合：题目内容 + 所属试卷定位 + 取卷链接 | 否 |
| `GET /api/v1/materials` | 考试发放资料：目录 / 单条详情 / 原件取回 / CIE 卷内动态定位 | 目录与详情否；`/content`、`cie/in-paper` 是 |
| `GET /api/v1/timetable` | 考试时间表：考季清单 / 结构化事件 / 日期窗口（CIE Zone 5 + Edexcel） | 否（离线快照） |

字段级说明见 [docs/API.md](../docs/API.md)；Python / Node / 浏览器版本见同目录的
`python_client.py`、`node_client.mjs`、`browser.html`。

## 0 先约定四件事

**1. 服务地址。** 下面统一用 `http://127.0.0.1:8000`，按需替换：

```bash
export EXAMDATA_BASE_URL='http://127.0.0.1:8000'   # 只在本 shell 生效
```

**2. 启动服务。** 另一个终端，工作目录是仓库根：

```bash
examdata serve --host 127.0.0.1 --port 8000
# 交互式文档：http://127.0.0.1:8000/docs
```

**3. API Key（可选）。** 服务端进程设了 `EXAMDATA_API_KEY` 时，除 `/health`、`/docs`、
`/redoc`、`/openapi.json` 外的所有请求都必须带 `X-API-Key` 头，否则返回 401。
没设该变量时完全放行，本地部署无需关心。

```bash
export EXAMDATA_API_KEY='你的密钥'
```

**4. board 别名（大小写不敏感）。** 传错了是 422，不会静默当成默认值：

| 你写的 | 归一为 | 数据库里的名字 |
|---|---|---|
| `cie` / `cambridge` / `ca` | `cie` | `cambridge` |
| `edexcel` / `edx` / `pearson` / `ial` | `edexcel` | `edexcel` |

不传 `board` 时按科目代码形态自动判定：四位数字（`0580`）判为 `cie`，其余
（`ial18-economics`）判为 `edexcel`。响应里的 `board_source` 会告诉你这次用的是
`explicit`（你显式传的）还是 `inferred`（系统判的）。

> Windows 提示：在 Git Bash 里下面这些单引号命令可以原样跑。在 PowerShell / CMD 里
> 请把 `curl` 写成 `curl.exe`（PowerShell 的 `curl` 是 `Invoke-WebRequest` 的别名，
> 参数不兼容），并把单引号换成双引号。

## 1 能力发现：GET /api/v1/boards

调用前先看一眼有哪些考试局、各自的科目形态与可用模式：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/boards'
```

格式化输出（Windows 用 `python -m json.tool`，装了 jq 的话用 `jq`）：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/boards' | python -m json.tool
```

只看每个考试局的规范名与别名：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/boards' \
  | python -c "import json,sys; [print(b['board'], b['aliases'], b['seasons'], b['modes']) for b in json.load(sys.stdin)['boards']]"
```

## 2 跨考试局检索：GET /api/v1/search

`items` 与既有 `GET /questions` 的 `items` 形状完全一致（含 `board` 字段，值是数据库
key `cambridge` / `edexcel`）；`by_board` 给出同一组条件下各考试局的命中数——
"这一局没命中"和"这一局根本没数据"是两件事，必须能区分。

```bash
# 2.1 关键词检索，跨考试局
curl -s 'http://127.0.0.1:8000/api/v1/search?keyword=angle&limit=5'

# 2.2 按科目检索（0580 是四位数字，board 自动判为 cie）
curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&limit=5'

# 2.3 显式指定考试局（别名可用 cambridge / pearson 等写法；Edexcel 科目用 slug）
curl -s 'http://127.0.0.1:8000/api/v1/search?board=cambridge&subject=0580&limit=5'
curl -s 'http://127.0.0.1:8000/api/v1/search?board=pearson&subject=ial18-economics&limit=5'

# 2.4 分值区间 + 只要可独立作答的叶子题
curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&marks_min=3&marks_max=5&leaves_only=true&limit=10'

# 2.5 按年份、考季、试卷定位
curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&year=2024&session=June&paper=11&limit=10'

# 2.6 只要带官方答案的题
curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&has_answer=true&limit=5'

# 2.7 分页：limit 上限 500，offset 从 0 开始
curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&limit=20&offset=20'
```

只打印命中统计，不打印整包 JSON：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/search?subject=0580&limit=5' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['total'], d['by_board'])"
```

## 3 统一取卷：GET /api/v1/paper

`subject` / `year` / `season` 必填，`board` 可省略（按科目形态自动判定）。

**三种出口：**

| 参数组合 | 返回 | 典型用途 |
|---|---|---|
| `download=false` | JSON 清单（与 `/paper-qa/resolve` 同 schema，另加 `board` / `board_source`） | 先看有哪些文件、多大、什么 URL |
| `download=true`（默认） | 原始字节：单文件 PDF，多文件内存 ZIP，带 `Content-Disposition` 与 `Content-Length` | 直接落盘 |
| `download=true&format=json` | base64 内联载荷（与 `/paper-qa/query?format=json` 同 schema） | 只接受 JSON 的客户端 |

### 3.1 只解析清单（不出网下载，但仍会访问上游目录）

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&download=false'
```

### 3.2 CIE：下载整卷 QP（单文件 PDF）

```bash
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp'
```

`-O` 用 URL 末段命名，`-J` 改用响应头 `Content-Disposition` 里的文件名——服务端一定会给，
所以 `-O -J` 拿到的就是官方文件名。想自己指定文件名就 `-o`：

```bash
curl -s -o 0580_qp_11.pdf 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp'
ls -l 0580_qp_11.pdf
```

### 3.3 CIE：QP + MS 一起取（多文件 → 内存 ZIP）

```bash
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=both'
unzip -l paper-qa.zip        # Windows 没有 unzip 时用：tar -tf paper-qa.zip
```

### 3.4 CIE：只要评分标准

```bash
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=ms'
```

### 3.5 base64 JSON（不给浏览器留二进制口子的场合）

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&format=json' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['board'], d['board_source'], d['counts']); [print(f['name'], f['size'], f['sha256'][:12]) for f in d['files']]"
```

把 base64 载荷落盘：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&format=json' \
  | python -c "
import base64, json, sys
d = json.load(sys.stdin)
for f in d['files']:
    open(f['name'], 'wb').write(base64.b64decode(f['data_base64']))
    print('已保存', f['name'])
"
```

### 3.6 Edexcel：整卷（mode=paper，默认）

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?subject=Economics&year=2024&season=Jun&paper=wec11-01&download=false'
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=Economics&year=2024&season=Jun&paper=wec11-01&mode=paper'
```

### 3.7 Edexcel：按题裁剪 PNG（CIE 不支持，会返回 422）

```bash
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=Economics&year=2024&season=Jun&paper=wec11-01&question=12(a)&mode=question'
```

实测这份卷（2024 June `wec11-01`）：`question=12(a)` 返回 **3 张 PNG 的 ZIP**（195,805 字节）——
第 11 页是题面，另两张是题目引用的 Extract 材料页（第 30/31 页）。题号必须是该卷里真实存在的
编号：`12(a)` 有，`2(a)` 没有，会得到 422 `Question 2(a) could not be located reliably`；
而 `question=2` 是单页，直接返回一张 PNG（38,927 字节）。想拿到 `page` / `bbox` 就加 `format=json`。

### 3.8 Edexcel：题目 + 答案配对（多文件 → ZIP）

```bash
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=Economics&year=2024&season=Jun&paper=wec11-01&question=12(a)&mode=qa'
```

实测同一份卷：`mode=qa` 的 `12(a)` 返回 **4 张 PNG 的 ZIP**（227,320 字节）——3 张来自 QP
（题面 + Extract 材料），1 张答案来自 MS。

### 3.9 显式指定 board（想跳过自动判定时）

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?board=cambridge&subject=0580&year=2024&season=Jun&paper=11&download=false'
curl -s 'http://127.0.0.1:8000/api/v1/paper?board=pearson&subject=Economics&year=2024&season=Jun&paper=wec11-01&download=false'
```

## 4 单题聚合：GET /api/v1/question/{id}

```bash
curl -s 'http://127.0.0.1:8000/api/v1/question/1' | python -m json.tool
```

只取"这道题来自哪份卷子、去哪取"：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/question/1' \
  | python -c "import json,sys; d=json.load(sys.stdin); s=d['source']; print(d['board'], s['board_canonical'], s['subject_code'], s['year'], s['session'], s['paper_code']); print(s['paper_endpoint'])"
```

拿到 `paper_endpoint` 后可以直接回填给取卷接口（它就是 `/api/v1/paper` 的相对 URL）：

```bash
curl -sO -J 'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp'
```

## 5 考试发放资料：GET /api/v1/materials

考试时发给考生的资料（公式表、元素周期表、随卷 insert 等）也有统一入口：
目录、单条详情、原件取回，以及 CIE 的卷内动态定位。目录与详情读本地快照，
`/content` 与 `cie/in-paper` 会访问上游。

### 5.1 目录与过滤

```bash
# 全部 8 条（实测：CIE 6 条 + Edexcel 2 条）
curl -s 'http://127.0.0.1:8000/api/v1/materials'

# 按考试局、按类别过滤（实测各 2 条）
curl -s 'http://127.0.0.1:8000/api/v1/materials?board=edexcel'
curl -s 'http://127.0.0.1:8000/api/v1/materials?kind=formula-and-statistical-tables'
```

### 5.2 单条详情

```bash
# 9709 考试用的 MF19 公式与统计表
curl -s 'http://127.0.0.1:8000/api/v1/materials/cie-mf19-formulae-and-statistical-tables'
```

### 5.3 取回原件

```bash
# MF19：实测 311234 字节，X-Material-Sha256-Match: true
curl -sO -J 'http://127.0.0.1:8000/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content'

# Edexcel IAL 化学数据手册：实测 2542080 字节
curl -sO -J 'http://127.0.0.1:8000/api/v1/materials/edexcel-ial-chemistry-data-booklet/content'
```

只要 JSON 的客户端加 `?format=json`（base64 载荷，带 `sha256_match`）：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content?format=json' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['material_id'], d['size'], d['sha256_match'])"
```

元素周期表这类"印在试卷内"的条目（`access: in-paper`）没有独立文件，`/content`
会返回 422 并说明访问方式：

```bash
curl -s -w '\n%{http_code}\n' 'http://127.0.0.1:8000/api/v1/materials/cie-periodic-table/content'
# → 422 {"detail":{"message":"资料 cie-periodic-table 没有可独立取回的版本","access":"in-paper","dynamic_endpoint":null}}
```

### 5.4 CIE 卷内资料动态定位：GET /api/v1/materials/cie/in-paper

insert / 保密须知随考卷变化，用 subject/year/season 实时定位；`download=false`
（默认）只列清单：

```bash
# 0500 2024 Jun 实测 6 份 insert（组件 11/12/13/21/22/23）
curl -s 'http://127.0.0.1:8000/api/v1/materials/cie/in-paper?subject=0500&year=2024&season=Jun' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['counts'], [doc['name'] for doc in d['documents']])"
```

`download=true` 且唯一命中时下载（多命中而未给 `paper` 是 409，并列出候选组件）：

```bash
# 实测 200、114871 字节、sha256 7d49097c…（X-Material-Role: in / X-Material-Paper: 11）
curl -sO -J 'http://127.0.0.1:8000/api/v1/materials/cie/in-paper?subject=0500&year=2024&season=Jun&paper=11&download=true'
```

## 6 考试时间表：GET /api/v1/timetable

CIE Zone 5（含中国大陆在内的考区）与 Edexcel 的历年时间表已结构化进统一网关：
考季清单、单季事件（每场考试一行）、日期窗口。全部读离线快照，不联网、不查库。

### 6.1 考季清单

```bash
# CIE：25 个可得考季（2013-11 … 2026-11）+ 2 个有证据的不可得考季
curl -s 'http://127.0.0.1:8000/api/v1/timetable/seasons'

# Edexcel：可按系列过滤（gcse / intgcse / ial / gce）；ial 实测 34 个考季
curl -s 'http://127.0.0.1:8000/api/v1/timetable/seasons?board=edexcel&family=ial'
```

### 6.2 CIE 单季查询

`season` 接受 `Jun`/`June`/`Nov`/`November`（大小写不敏感）；事件行含
`date`/`weekday`/`session`/`level`/`subject_code`/`paper_code`/`duration_minutes`
等字段；`limit` 默认 200、上限 2000，配合 `offset` 分页：

```bash
# 2026 Nov 的 9709 全部场次：实测 6 条，首条 2026-10-13 周二 AM AS 9709/13 110 分钟
curl -s 'http://127.0.0.1:8000/api/v1/timetable?subject=9709&year=2026&season=Nov'

# 过滤可组合：按日期（实测 11 条）、按时段 + 等级（实测 47 条）
curl -s 'http://127.0.0.1:8000/api/v1/timetable?year=2026&season=Nov&date=2026-10-13'
curl -s 'http://127.0.0.1:8000/api/v1/timetable?year=2026&season=Nov&session=AM&level=AS'
```

只打印条数：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/timetable?subject=9709&year=2026&season=Nov' \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['count'], d['total'])"
```

### 6.3 日期窗口：GET /api/v1/timetable/windows

各 syllabus/component 的 "Test date windows"（2026 Nov 实测 22 条）：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/timetable/windows?year=2026&season=Nov'
```

### 6.4 Edexcel 时间表（family 必填）

```bash
# IAL 2026 June：实测 90 条，首条 2026-05-05 WAC11/01
curl -s 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=ial&year=2026&season=June'

# R 卷变体：intgcse 2018 June：实测 36 条，variant=R
curl -s 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=intgcse&year=2018&season=June&r_paper=true'
```

### 6.5 取消与不可得考季：404 语义

Edexcel 取消考季（COVID-19）与有证据的不可得考季返回 404 并说明原因；
考季形式合法但从未收录是 422：

```bash
curl -s -w '\n%{http_code}\n' 'http://127.0.0.1:8000/api/v1/timetable?board=edexcel&family=gcse&year=2020&season=June'
# → 404 {"detail":{"message":"gcse|2020|06 考季已取消","reason":"UK GCSE summer 2020 series cancelled (COVID-19); grades awarded by centre assessment","cancelled":true}}

curl -s -w '\n%{http_code}\n' 'http://127.0.0.1:8000/api/v1/timetable?year=2019&season=Jun'
# → 404 {"detail":{"message":"2019-06 时间表不可得","reason":"文件 513557-june-2019-timetable-zone-5.pdf 从未被有效存档：…","evidence":"…"}}
```

## 7 带 X-API-Key 的形态

服务端设了 `EXAMDATA_API_KEY` 后，所有端点都要带这个头：

```bash
# 7.1 单次调用
curl -s -H "X-API-Key: $EXAMDATA_API_KEY" 'http://127.0.0.1:8000/api/v1/boards'

# 7.2 取卷（下载也一样，头照带）
curl -sO -J -H "X-API-Key: $EXAMDATA_API_KEY" \
  'http://127.0.0.1:8000/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp'

# 7.3 探活与文档不需要 Key（豁免路径）
curl -s 'http://127.0.0.1:8000/health'
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8000/docs'

# 7.4 不带 Key 会得到 401
curl -s -w '\n%{http_code}\n' 'http://127.0.0.1:8000/api/v1/boards'
```

## 8 常见错误与排查

统一错误体是 FastAPI 的 `{"detail": ...}`：

| 状态码 | 触发条件 | 例子 |
|---|---|---|
| 401 | 服务端设了 `EXAMDATA_API_KEY` 但请求没带或带错 `X-API-Key` | `{"detail": "缺少或无效的 X-API-Key 请求头"}` |
| 404 | 题目 / 资料 ID 不存在；上游没有对应文件；考季已取消或不可得 | `{"detail": "题目 999999 不存在"}` |
| 403 | 上游把该资源判为非公开 | 非公开试卷 |
| 409 | 同一组条件命中多份候选，无法确定取哪份 | 需要补 `paper` 精确定位 |
| 422 | 参数非法：board 别名不认识、season 不在该局考季表内、CIE 传了 `question`、`format` 不是 binary/json | `{"detail": "无法识别的 board: ..."}` |
| 502 | 上游故障 / 超时 | 稍后重试 |

几条自查命令：

```bash
# 看服务是否活着（同时确认数据库可达）
curl -s 'http://127.0.0.1:8000/health'

# 确认 board 该写什么
curl -s 'http://127.0.0.1:8000/api/v1/boards' | python -c "import json,sys; d=json.load(sys.stdin); [print(b['board'], b['aliases']) for b in d['boards']]"

# 连不上服务时先看端口
curl -sv 'http://127.0.0.1:8000/health' 2>&1 | head -20
```

**注意**：`/api/v1/search` 读的是本地数据库，两个考试局的题目都已入库。
不带 board 搜 `triangle`，`by_board` 是 `{"cambridge": 24, "edexcel": 153}`。
Edexcel 科目用数据库里的 slug 写法（如 `ial18-economics`、`ial-accounting`）：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/search?board=edexcel&subject=ial18-economics&limit=5'
```

某一局命中为 0 只说明该局没有匹配这个条件的题（Edexcel 用科目名 `Economics`
搜不到，要用上面的 slug），不是接口故障。

旧版式端点也一致：`GET /papers?board=edexcel` 实测 `total=1533`，
`GET /papers` 全量为 1549 条（16 Cambridge + 1533 Edexcel）。

Edexcel 侧上游取卷走统一网关（`counts.documents=1` 就说明上游有这份卷）：

```bash
curl -s 'http://127.0.0.1:8000/api/v1/paper?board=edexcel&subject=Economics&year=2024&season=Jun&paper=wec11-01&download=false'
```

## 9 一条完整链路

```bash
BASE='http://127.0.0.1:8000'

# 1) 有哪些考试局、怎么传参数
curl -s "$BASE/api/v1/boards" | python -m json.tool | head -30

# 2) 检索一道题
curl -s "$BASE/api/v1/search?subject=0580&leaves_only=true&limit=1" \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['total'], d['by_board']); print(d['items'][0]['question_id'])"

# 3) 看这道题的完整内容与来源（把上一步的 id 填进来）
curl -s "$BASE/api/v1/question/1" | python -m json.tool | head -40

# 4) 用 source.paper_endpoint 给的地址取整卷 PDF
curl -sO -J "$BASE/api/v1/paper?subject=0580&year=2024&season=Jun&paper=11&mode=qp"
ls -l *.pdf
```
