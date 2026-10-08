"""用 Windows OCR 给一份 CIE 试卷生成题目定位索引（cie-index.json）。

为什么要 OCR：这些 PDF 的文字层是字体子集 + 坏 ToUnicode，`get_text()` 返回乱码，
但排版位置是对的。Windows.Media.Ocr 能把英文正常读出来，所以结构识别全部走 OCR 文本，
坐标最后换算回「未旋转 PDF、左上原点、points」。

流程（单进程、串行、不联网）：
1. locate_pdf 找本地 QP / MS PDF，QP 找不到直接退出码 2
2. 逐页渲染**一档** zoom（默认 2.5）到 tmp/<卷>/pages/<role>-pNNN-z<zoom>.png，一次批量 OCR
3. 结构分析在「显示态」做（渲染图所在空间，px/zoom 即显示态 points）：
   先滤掉页眉页脚/版权/条形码这类 boilerplate，再自适应检测题号列 / 子题列 / 子子题列
4. 逐行解析标签（宽容正则，能吃下 `（ 0 From Source A ...` 这种 OCR 变形），
   按 (page, y0, x0, level) 排序后用栈拼层级；拼不出父题的标签丢弃并记入 dropped_labels
5. 区域 = 本题第一个标签行 y0-2 到文档顺序里第一个「层级不高于本题」的标签行 y0-2；
   跨页时每页一个 region，中间页从该页首个正文行到页面底部，无内容页（BLANK PAGE）跳过
6. 区域的两个角用 page.derotation_matrix 转成未旋转 points 写进 JSON
7. 分值只在没有子题的题上抓，取区域右侧（x0 ≥ 半页宽）的 `[ n ]` 类行
8. MS 只在「同一行同时出现 Question 与 Answer 表头」的页上找标签列，
   用 MS 自己的栈建层级后按题号精确匹配；匹配不到就沿 QP 父链向上找最近的祖先

`--report` 只打印观测结果、不写文件；`--debug-lines` 额外打印每页行数与候选标签行的判定。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import batchlib as B
import import_index as I
import paperlib as P

# 控制台可能是 GBK；报告里有中文和 em dash，统一按 utf-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

OCR_PS1 = B.WORK / "ocr_batch.ps1"
DEFAULT_ZOOM = 2.5
MAX_REGIONS = 25
MAX_TEXT = 20000
MAX_NOTES = 2000
PAD_PT = 2.0
MIN_REGION_PT = 20.0
COL_GAP_PT = 8.0
LINE_TOL_PT = 3.0
TOL_MIN = 6.0
TOL_MAX = 12.0
TOL_RATIO = 0.45
COL_FALLBACK = (0.0, 21.0, 43.0)
MAX_QNUM = 40
MARK_COL_RATIO = 0.5
LABEL_STRIP_HALF_PT = 20.0
LABEL_STRIP_ZOOM = 6.0
SUB_STRIP_BAND_PT = 62.0
SUB_STRIP_ZOOM = 6.0
SUB_STRIP_MAX = 80
OCR_NOTE = "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声"
MS_NOTE = "MS 中未找到对应评分行"

ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
# `(i)` 有时被读成 `(0` / `(l` 且连右括号一起吞掉；只在标签后面紧跟非 ASCII
# 字符（中文试卷正文）时才认，避免把 `(1 mark)` 这类正文误当成 `(i)`。
NOISY_LEAD_RE = re.compile(r"^[\(\[]\s*([A-Za-z0-9|]{1,3})\s+(?=[^\x00-\x7f])")
ROMAN_FIX = {"1": "i", "l": "i", "|": "i", "0": "i", "11": "ii", "ll": "ii", "111": "iii",
             "1v": "iv", "v1": "vi", "vl": "vi", "1i": "ii", "1ii": "iii", "1v1": "ivi"}
WIDTH_MAP = str.maketrans({"（": "(", "）": ")", "［": "[", "］": "]", "【": "[", "】": "]",
                           "．": ".", "，": ",", "。": ".", "：": ":", "｜": "|", "丨": "|"})
BOILER_RE = re.compile(
    r"(camb\w*dge|cambndge|cambrid|turn\s*over|turnover|permission|reproduc|acknowledg|"
    r"blank\s*page|publish|page\s*\d+\s*of|©|university\s*press|international\s*education|"
    r"may\s*/\s*june|this\s*document\s*has|do\s*not\s*write|content\s*removed|"
    r"copyright|exam\w*nat\w*\s+ser\w*\.?\s*$|general\s*marking|specific\s*marking|"
    r"how\s*to\s*use|annotation)", re.I)
PAPER_CODE_RE = re.compile(r"^\s*\d{4}\s*/\s*\d{1,2}\b")
TOP_RE = re.compile(r"^(\d{1,2})(?=[\s(.\]]|$)")
PAREN_CLOSED_RE = re.compile(r"^[\(\[]\s*([A-Za-z0-9|]{1,4})\s*[\)\]]")
PAREN_OPEN_RE = re.compile(r"^[\(\[]\s*([A-Za-z0-9|]{1,4})\s*(?=[A-Z(\[]|$)")
BARE_CLOSED_RE = re.compile(r"^([A-Za-z])\s*[\)\]]")
MARK_RE = re.compile(r"^[\[\(!|]?\s*(\d{1,2})\s*[\]\)!|]?\s*[.,;]?$")
SPLIT_NUM_RE = re.compile(r"(\d)\s+(\d)")
HEADER_WORDS = {"question", "answer", "marks", "guidance"}


def norm(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", (text or "").lower())


def wide(text: str) -> str:
    return (text or "").translate(WIDTH_MAP)


def is_boiler(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if BOILER_RE.search(t) or PAPER_CODE_RE.match(t):
        return True
    key = norm(t)
    return len(key) >= 8 and sum(c.isdigit() for c in key) >= len(key) - 2


def take_paren(s: str):
    """吃掉行首的括号标签，返回 (token, 余下文本)；认不出返回 None。"""
    for pat in (PAREN_CLOSED_RE, PAREN_OPEN_RE, BARE_CLOSED_RE):
        m = pat.match(s)
        if m:
            return m.group(1).lower(), s[m.end():]
    return None


def roman_fix(token: str) -> str:
    return ROMAN_FIX.get(token, token)


def near(value: float, center: float | None, tol: float) -> bool:
    return center is not None and abs(value - center) <= tol


def run_ocr(paths: list[Path], tmp_dir: Path) -> dict[str, list[dict]]:
    if not paths:
        return {}
    tmp_dir.mkdir(parents=True, exist_ok=True)
    listing = tmp_dir / "_idx_list.txt"
    outfile = tmp_dir / "_idx_out.tsv"
    listing.write_text("\n".join(str(p) for p in paths), encoding="utf-8")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(OCR_PS1), "-List", str(listing), "-Out", str(outfile)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(f"OCR 失败 rc={proc.returncode} {proc.stdout} {proc.stderr}")
    result: dict[str, list[dict]] = defaultdict(list)
    if not outfile.exists():
        return result
    for line in outfile.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path, kind = parts[0], parts[1]
        if kind == "ERR":
            result[path].append({"error": parts[2] if len(parts) > 2 else "unknown"})
        elif kind == "SIZE":
            result[path].append({"size": [int(parts[2]), int(parts[3])]})
        elif kind == "LINE" and len(parts) >= 7:
            result[path].append({"x0": float(parts[2]), "y0": float(parts[3]),
                                 "x1": float(parts[4]), "y1": float(parts[5]), "text": parts[6]})
    return result


def page_lines(rows: list[dict], zoom: float) -> tuple[list[dict], int]:
    """OCR 行 -> 显示态 points 行（去 boilerplate），返回 (正文行, OCR 错误数)。"""
    lines, errors = [], 0
    for r in rows:
        if "error" in r:
            errors += 1
            continue
        if "text" not in r:
            continue
        line = {"x0": r["x0"] / zoom, "y0": r["y0"] / zoom,
                "x1": r["x1"] / zoom, "y1": r["y1"] / zoom, "text": r["text"]}
        split = SPLIT_NUM_RE.fullmatch(line["text"].strip())
        if split:
            # OCR 偶尔把两位数题号拆成 `1 5`；TOP_RE 会只认前一位，于是第 15 题
            # 变成重复的第 1 题，整条子树被吞（0472/2026/Jun/12 p8 实测）。
            line["text"] = split.group(1) + split.group(2)
        if not is_boiler(line["text"]):
            lines.append(line)
    lines.sort(key=lambda l: (l["y0"], l["x0"]))
    return lines, errors


def cluster(values: list[float], gap: float) -> list[tuple[float, int]]:
    """一维单链聚类，返回 [(中心, 成员数)]，按中心升序。"""
    groups: list[list[float]] = []
    for value in sorted(values):
        if groups and value - groups[-1][-1] <= gap:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [(sum(g) / len(g), len(g)) for g in groups]


def pick_cluster(groups: list[tuple[float, int]], floor: float) -> float | None:
    """取最左的「≥2 个成员且中心在 floor 右侧」的簇，退而取最大簇。"""
    multi = [g for g in groups if g[1] >= 2 and g[0] > floor]
    if multi:
        return multi[0][0]
    rest = [g for g in groups if g[0] > floor]
    if rest:
        return max(rest, key=lambda g: g[1])[0]
    return None


def detect_columns(pages: dict[int, dict]) -> dict:
    """自适应找题号列 / 子题列 / 子子题列（显示态 x），找不到用经验偏移兜底。"""
    top_x, sub_x, subsub_x = [], [], []
    for page in pages.values():
        for line in page["lines"]:
            s = wide(line["text"]).strip()
            m = TOP_RE.match(s)
            if m and 1 <= int(m.group(1)) <= MAX_QNUM:
                top_x.append(line["x0"])
                s = s[m.end():].lstrip()
            got = take_paren(s)
            if not got:
                continue
            token = roman_fix(got[0])
            if token in ROMAN:
                subsub_x.append(line["x0"])
            elif len(token) == 1 and token.isalpha():
                sub_x.append(line["x0"])
    groups_top = cluster(top_x, COL_GAP_PT)
    top = pick_cluster(groups_top, -1.0)
    if top is None:
        return {"top": None, "sub": None, "subsub": None, "tol": {}}
    sub = pick_cluster(cluster(sub_x, COL_GAP_PT), top + COL_GAP_PT)
    subsub = pick_cluster(cluster(subsub_x, COL_GAP_PT), top + COL_GAP_PT)
    if sub is None or sub <= top + COL_GAP_PT:
        sub = top + COL_FALLBACK[1]
    if subsub is None or subsub <= sub + COL_GAP_PT:
        subsub = top + COL_FALLBACK[2]
    span_sub = max(sub - top, 1.0)
    span_subsub = max(subsub - sub, 1.0)
    return {
        "top": top, "sub": sub, "subsub": subsub,
        "tol": {
            "top": min(TOL_MAX, max(TOL_MIN, TOL_RATIO * span_sub)),
            "sub": min(TOL_MAX, max(TOL_MIN, TOL_RATIO * span_sub)),
            "subsub": min(TOL_MAX, max(TOL_MIN, TOL_RATIO * span_subsub)),
        },
    }


def qp_labels(line: dict, cols: dict) -> list[tuple[int, str]]:
    """QP 行 -> [(层级, token)]；层级 1/2/3 对应题号 / (a) / (i)。"""
    x0 = line["x0"]
    s = wide(line["text"]).strip()
    out: list[tuple[int, str]] = []
    anchor = None
    m = TOP_RE.match(s)
    if m and 1 <= int(m.group(1)) <= MAX_QNUM and near(x0, cols["top"], cols["tol"]["top"]):
        out.append((1, m.group(1)))
        anchor = 1
        s = s[m.end():].lstrip()
    got = take_paren(s)
    if not got:
        return out
    token = roman_fix(got[0])
    level = None
    if token in ROMAN:
        if anchor == 1 or near(x0, cols["subsub"], cols["tol"]["subsub"]) \
                or near(x0, cols["sub"], cols["tol"]["sub"]):
            level = 3
    elif len(token) == 1 and token.isalpha():
        if anchor == 1 or near(x0, cols["sub"], cols["tol"]["sub"]):
            level = 2
    if level is None:
        return out
    out.append((level, token))
    if level == 2:
        got2 = take_paren(got[1].lstrip())
        if got2:
            token2 = roman_fix(got2[0])
            if token2 in ROMAN:
                out.append((3, token2))
    return out


def ms_labels(line: dict, window: tuple[float, float]) -> list[tuple[int, str]]:
    """MS 表格行 -> [(层级, token)]；标签列由表头位置确定。"""
    if not (window[0] <= line["x0"] <= window[1]):
        return []
    s = wide(line["text"]).strip()
    m = TOP_RE.match(s)
    if not m or not (1 <= int(m.group(1)) <= MAX_QNUM):
        return []
    out: list[tuple[int, str]] = [(1, m.group(1))]
    got = take_paren(s[m.end():].lstrip())
    if not got:
        return out
    token = roman_fix(got[0])
    if len(token) == 1 and token.isalpha() and token not in ROMAN:
        out.append((2, token))
        got2 = take_paren(got[1].lstrip())
        if got2:
            token2 = roman_fix(got2[0])
            if token2 in ROMAN:
                out.append((3, token2))
    return out


def build_hierarchy(events: list[dict], role: str) -> tuple[dict[str, dict], list[str], list[str]]:
    """事件 -> {题号: {level, events:[下标]}}；拼不出父题的丢弃。

    第三个返回值 `deepest[i]` 是「处理完第 i 个事件后，层级栈里最深的那道题」，
    用来给「页首没有标签的那一段」找归属（见 lead_owner）。
    """
    questions: dict[str, dict] = {}
    stack: list[tuple[int, str]] = []
    dropped: list[str] = []
    deepest: list[str] = []
    for i, event in enumerate(events):
        level, token = event["level"], event["token"]
        parent = None
        if level == 1:
            qid = token
        elif level == 2:
            parent = next((q for lv, q in reversed(stack) if lv == 1), None)
            qid = f"{parent}({token})" if parent else None
        else:
            parent = next((q for lv, q in reversed(stack) if lv == 2), None)
            qid = f"{parent}({token})" if parent else None
        if qid is None:
            dropped.append(f"{role}:p{event['page']} y{round(event['y0'], 1)} {event['text'][:24]!r}")
            deepest.append(stack[-1][1] if stack else "")
            continue
        node = questions.setdefault(qid, {"question": qid, "parent": parent,
                                          "level": level, "events": []})
        node["events"].append(i)
        stack = [entry for entry in stack if entry[0] < level]
        stack.append((level, qid))
        deepest.append(stack[-1][1])
    return questions, dropped, deepest


def lead_owner(events: list[dict], deepest: list[str]) -> dict[int, str]:
    """每页「第一个标签之前那一段」归哪道题。

    MS 的 Question 列只在新的子题行才印号，跨页续写的正文没有自己的标签；那一段
    属于上一页最后一个标签所在的题（例如 9396 MS p8 顶部 104..291.6 属于 2(b)）。
    """
    first: dict[int, int] = {}
    for i, event in enumerate(events):
        first.setdefault(event["page"], i)
    out: dict[int, str] = {}
    for pno, i in first.items():
        if i > 0 and deepest[i - 1]:
            out[pno] = deepest[i - 1]
    return out


def is_ancestor(questions: dict[str, dict], root: str, qid: str) -> bool:
    """root 是 qid 本身或它的祖先。"""
    seen = 0
    node = questions.get(qid)
    while node is not None and seen < 16:
        if node["question"] == root:
            return True
        node = questions.get(node.get("parent") or "")
        seen += 1
    return False


def subtree_indexes(questions: dict[str, dict], root: str) -> list[int]:
    """root 及其全部后代的标签事件下标。父题的区域因此覆盖整道题，但不越界。"""
    out: list[int] = []
    stack = [root]
    while stack:
        qid = stack.pop()
        node = questions.get(qid)
        if node is None:
            continue
        out.extend(node["events"])
        stack.extend(q for q, n in questions.items() if n["parent"] == qid)
    return out


BODY_TEXT_RE = re.compile(r"[A-Za-z]{4,}")


def band_has_body(lines: list[dict], bottom: float) -> bool:
    """页首无标签段里是否有真正的正文行。

    QP 的页首续写通常只是答题空白，唯一的墨迹是右栏那个分数数字（如 p4 顶部孤零零的
    `4`），这种区域取出来是空白条，既没用又会被核验判成「无文字无墨迹」。只有确实
    印了正文（MS 的评分说明、跨页的题干/表格）才值得建区域。
    """
    return any(line["y0"] < bottom - 1.0 and BODY_TEXT_RE.search(line["text"])
               for line in lines)


def build_regions(indexes: list[int], events: list[dict], pages: dict[int, dict],
                  lead: dict[int, float] | None = None) -> list[dict]:
    """把一道题（含其子题）的标签事件展开成区域（显示态），同页合并。

    每个标签只管辖「本页内、从它到本页下一个标签之前」的那一段：区域绝不跨页延伸，
    因此不会把下一页属于别的题的正文吞进来。同页多段合并成一段。
    只有整页没有任何标签时，才按整页补全（纯答题区 / 跨页续写的无标签页）。

    `lead` 是「本页第一个标签之前那一段」的归属：{页码: 该段下界}，只在本题确实
    承接上一页续写时才传进来（见 lead_owner）。
    """
    by_page: dict[int, list[float]] = {}
    for i in indexes:
        by_page.setdefault(events[i]["page"], []).append(events[i]["y0"])
    for pno in (lead or {}):
        by_page.setdefault(pno, [])
    spans: dict[int, list[float]] = {}
    for pno, ys in by_page.items():
        page = pages.get(pno)
        if page is None or page["content"] is None:
            continue
        cx0, cy0, cx1, cy1 = page["content"]
        dx0, _dy0, dx1, dy1 = page["disp"]
        # 区域一律在**显示态**里量。旋转页的 bounds 是未旋转空间的尺寸（例如 612x792），
        # 直接当显示态下界用会把竖排 MS 表格的整页宽度都吞进来。
        left, right = max(dx0, cx0 - PAD_PT), min(dx1, cx1 + PAD_PT)
        bottom_limit = min(dy1, cy1 + PAD_PT)
        own = [events[i] for i in indexes if events[i]["page"] == pno]
        tops = sorted({round(e["y0"], 2) for e in own})
        lead_bottom = (lead or {}).get(pno)
        lead_top = None
        if (lead_bottom is not None and cy0 < lead_bottom - 1.0
                and band_has_body(page["lines"], lead_bottom)):
            # 页首无标签段：从正文顶部一直到本页第一个标签。
            lead_top = round(cy0, 2)
            tops.insert(0, lead_top)
        for top_y in tops:
            top = top_y - PAD_PT
            is_lead = lead_top is not None and top_y == lead_top
            nxt = next((o["y0"] - PAD_PT for o in events
                        if o["page"] == pno and o["y0"] > top_y + 0.01), None)
            bottom = bottom_limit if nxt is None else min(nxt, bottom_limit)
            if is_lead:
                # 页首无标签段到此为止，不能越过本页第一个标签。
                bottom = min(bottom, lead_bottom)
                if bottom - top < 2.0:
                    continue
            else:
                # 标签行本身必须完整落在区域内。页尾只剩一行时 bottom_limit 会把标签行切掉，
                # 整段又被 MIN_REGION_PT 丢掉，题干就整块消失了（8386 的 1(b) 就是这样）。
                line_y1 = max((e["y1"] for e in own if abs(e["y0"] - top_y) < 0.01),
                              default=top_y + MIN_REGION_PT)
                bottom = max(bottom, min(line_y1 + PAD_PT, dy1))
            if bottom - top < 2.0:
                continue
            span = spans.setdefault(pno, [top, bottom, left, right])
            span[0], span[1] = min(span[0], top), max(span[1], bottom)
            span[2], span[3] = min(span[2], left), max(span[3], right)
    if by_page:
        label_pages = {e["page"] for e in events}
        for pno in range(min(by_page), max(by_page) + 1):
            if pno in spans or pno in label_pages:
                continue
            page = pages.get(pno)
            if page is None or page["content"] is None:
                continue
            cx0, cy0, cx1, cy1 = page["content"]
            dx0, dy0, dx1, dy1 = page["disp"]
            if cy1 - cy0 < MIN_REGION_PT:
                continue
            spans[pno] = [max(dy0, cy0 - PAD_PT), min(dy1, cy1 + PAD_PT),
                          max(dx0, cx0 - PAD_PT), min(dx1, cx1 + PAD_PT)]
    return [{"page": pno, "disp": (v[2], v[0], v[3], v[1])} for pno, v in sorted(spans.items())]


def region_text(regions: list[dict], pages: dict[int, dict]) -> str:
    parts = []
    for reg in regions:
        page = pages.get(reg["page"])
        if page is None:
            continue
        _x0, y0, _x1, y1 = reg["disp"]
        rows = [l for l in page["lines"] if l["y0"] >= y0 - 1.0 and l["y1"] <= y1 + 1.0]
        rows.sort(key=lambda l: (l["y0"], l["x0"]))
        parts.append(" ".join(l["text"] for l in rows))
    return repair(" ".join(parts))


def repair(text: str) -> str:
    """只合并被 OCR 拆断的单词（`O f` -> `Of`、`th e` -> `the`），不改动其余英文。"""
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\b([A-Za-z])\s+([a-z])\b", r"\1\2", t)
    t = re.sub(r"\b([A-Za-z]{2,})\s+([estdnrhcmlpfgyk])\b", r"\1\2", t)
    return t


def find_marks(regions: list[dict], pages: dict[int, dict]) -> int | None:
    values = []
    for reg in regions:
        page = pages.get(reg["page"])
        if page is None:
            continue
        _x0, y0, _x1, y1 = reg["disp"]
        cut = page["bounds"][2] * MARK_COL_RATIO
        for line in page["lines"]:
            if line["x0"] < cut or line["y0"] < y0 - 1.0 or line["y1"] > y1 + 1.0:
                continue
            m = MARK_RE.match(line["text"].strip())
            if m:
                values.append(int(m.group(1)))
    return values[-1] if values else None


def to_unrot(derot, bounds, disp) -> list[float]:
    import pymupdf
    p0 = pymupdf.Point(disp[0], disp[1]) * derot
    p1 = pymupdf.Point(disp[2], disp[3]) * derot
    x0, y0 = min(p0.x, p1.x), min(p0.y, p1.y)
    x1, y1 = max(p0.x, p1.x), max(p0.y, p1.y)
    return [round(max(x0, bounds[0]), 1), round(max(y0, bounds[1]), 1),
            round(min(x1, bounds[2]), 1), round(min(y1, bounds[3]), 1)]


def ms_window(page: dict, cols_x: list[float]) -> tuple[float, float] | None:
    """MS 页的标签列窗口：由 Question 表头与 Answer 表头夹出来。"""
    header = None
    for line in page["lines"]:
        if norm(line["text"]) == "question" and line["x0"] < page["bounds"][2] * 0.5:
            if any(norm(o["text"]) == "answer" and abs(o["y0"] - line["y0"]) < 10
                   for o in page["lines"]):
                header = line
                break
    if header is None:
        return None
    answer_x = min((l["x0"] for l in page["lines"] if norm(l["text"]) == "answer"),
                   default=page["bounds"][2])
    center = pick_cluster(cluster(cols_x, COL_GAP_PT), header["x0"] - 20) or header["x0"]
    left = max(header["x0"] - 20, center - 14)
    right = min(center + 30, answer_x - 8)
    return (left, right) if right > left else None


def noisy_lead_label(s: str):
    """吃掉行首「无右括号」的噪声标签，返回 (token, 余下文本)；认不出返回 None。"""
    m = NOISY_LEAD_RE.match(s)
    if not m:
        return None
    token = roman_fix(m.group(1).lower())
    if token not in ROMAN:
        return None
    return token, s[m.end():]


def label_strip_lines(pdf_path: Path, pages: dict[int, dict], cols: dict, tmp_dir: Path,
                      pages_dir: Path, role: str, debug: bool = False) -> int:
    """题号列窄条二次 OCR：补回整页 OCR 吞掉的孤立题号。

    实测 0413/2026/Jun/11 QP p2：`1` 标签整条没进 OCR rows，第 1 题整棵子树消失，
    索引里只剩 2..14 却没有任何报错。把题号列裁成 ±20pt 窄条、放大 6 倍单独跑一次
    OCR，同一页可以稳定读出 `1`。只认窄条里的短纯数字，且 x 必须落在题号列附近。
    """
    import pymupdf
    center = cols.get("top")
    if center is None:
        return 0
    tol = cols.get("tol", {}).get("top") or TOL_MIN
    lo = center - LABEL_STRIP_HALF_PT
    hi = center + LABEL_STRIP_HALF_PT
    jobs = []
    with pymupdf.open(pdf_path) as pdf:
        for pno, page in pages.items():
            if pno > pdf.page_count:
                continue
            pg = pdf[pno - 1]
            disp_clip = (pymupdf.Rect(lo, page["bounds"][1], hi, page["bounds"][3])
                         * pg.rotation_matrix)
            out = pages_dir / f"{role}-p{pno:03d}-lbl-z{LABEL_STRIP_ZOOM:g}.png"
            pix = pg.get_pixmap(matrix=pymupdf.Matrix(LABEL_STRIP_ZOOM, LABEL_STRIP_ZOOM),
                                clip=disp_clip, alpha=False)
            pix.save(str(out))
            pix = None
            jobs.append((pno, out, disp_clip))
    rows = run_ocr([out for _p, out, _c in jobs], tmp_dir)
    added = 0
    for pno, out, disp_clip in jobs:
        page = pages[pno]
        have = [l["y0"] for l in page["lines"]
                if TOP_RE.match(wide(l["text"]).strip()) and near(l["x0"], center, tol)]
        fresh = []
        for raw in rows.get(str(out), []):
            if "text" not in raw:
                continue
            text = wide(raw["text"]).strip()
            m = TOP_RE.match(text)
            if not m or not (1 <= int(m.group(1)) <= MAX_QNUM) or len(text) > 6:
                continue
            point = pymupdf.Point(raw["x0"] / LABEL_STRIP_ZOOM + disp_clip.x0,
                                  raw["y0"] / LABEL_STRIP_ZOOM + disp_clip.y0) * page["derot"]
            if not near(point.x, center, max(tol, LABEL_STRIP_HALF_PT)):
                continue
            if any(abs(point.y - y) <= LINE_TOL_PT for y in have):
                continue
            fresh.append((point.y, m.group(1)))
        for y, token in fresh:
            page["lines"].append({"x0": round(center - 3.0, 2), "y0": round(y, 2),
                                  "x1": round(center + 6.0, 2), "y1": round(y + 7.0, 2),
                                  "text": token, "from_label_strip": True})
            added += 1
        if fresh:
            page["lines"].sort(key=lambda l: (l["y0"], l["x0"]))
    if debug and added:
        print(f"[label-strip] {role} 补回 {added} 个题号标签")
    return added


def sublabel_strip_lines(pdf_path: Path, pages: dict[int, dict], cols: dict,
                         tmp_dir: Path, pages_dir: Path, role: str,
                         debug: bool = False) -> int:
    """子题标签窄条二次 OCR：补回被整页 OCR 并进上一行的 `(a)` / `(i)`。

    子题标签和正文同列，没有独立题号列，所以不能像顶层那样只扫一列窄条：从
    `cols["sub"]` 起取一条含子子题缩进的横带，放大 6 倍后**只认行首括号标签**。
    实测 9715/2023/Nov/21 QP p2：`(b) 不论懂不懂乐谱…` 被并进 `2(a)` 那一行，
    索引里 2 只剩 (a)(c)；0509/2026/Jun/11 QP p11 的 `(iv)` 被并进 1(h)(iii)。
    整页 OCR 已在同一 y 读到同一标签时不重复补，避免造出假题号。
    """
    import pymupdf
    sub = cols.get("sub")
    if sub is None:
        return 0
    subsub = cols.get("subsub") or sub
    tol = max(cols.get("tol", {}).get("sub") or TOL_MIN, LINE_TOL_PT)
    lo = sub - 8.0
    hi = max(sub, subsub) + SUB_STRIP_BAND_PT
    jobs = []
    with pymupdf.open(pdf_path) as pdf:
        for pno, page in pages.items():
            if pno > pdf.page_count:
                continue
            pg = pdf[pno - 1]
            disp_clip = (pymupdf.Rect(lo, page["bounds"][1], hi, page["bounds"][3])
                         * pg.rotation_matrix)
            out = pages_dir / f"{role}-p{pno:03d}-sub-z{SUB_STRIP_ZOOM:g}.png"
            pix = pg.get_pixmap(matrix=pymupdf.Matrix(SUB_STRIP_ZOOM, SUB_STRIP_ZOOM),
                                clip=disp_clip, alpha=False)
            pix.save(str(out))
            pix = None
            jobs.append((pno, out, disp_clip))
    rows = run_ocr([out for _p, out, _c in jobs], tmp_dir)
    added = 0
    for pno, out, disp_clip in jobs:
        page = pages[pno]
        have: list[tuple[float, str]] = []
        for line in page["lines"]:
            s = wide(line["text"]).strip()
            m = TOP_RE.match(s)
            if m and 1 <= int(m.group(1)) <= MAX_QNUM:
                s = s[m.end():].lstrip()
            got = take_paren(s)
            if got:
                have.append((line["y0"], roman_fix(got[0])))
        fresh: list[tuple[float, str]] = []
        for raw in rows.get(str(out), []):
            if "text" not in raw:
                continue
            got = take_paren(wide(raw["text"]).strip())
            if not got:
                got = noisy_lead_label(wide(raw["text"]).strip())
            if not got:
                continue
            token = roman_fix(got[0])
            if token not in ROMAN and not (len(token) == 1 and token.isalpha()):
                continue
            point = pymupdf.Point(raw["x0"] / SUB_STRIP_ZOOM + disp_clip.x0,
                                  raw["y0"] / SUB_STRIP_ZOOM + disp_clip.y0) * page["derot"]
            # 子题标签贴子题列，子子题标签还要往右缩进一档（0509 p11 的 `(i)` 在
            # x=121.3，而子题列在 94.4），两列都要认，否则缩进过的子子题会被丢掉。
            if not (near(point.x, sub, max(tol, 26.0))
                    or near(point.x, subsub, max(tol, 26.0))):
                continue
            if any(abs(point.y - y) <= LINE_TOL_PT and t == token for y, t in have):
                continue
            if any(abs(point.y - y) <= LINE_TOL_PT and t == token for y, t in fresh):
                continue
            fresh.append((point.y, token))
        for y, token in fresh[:SUB_STRIP_MAX]:
            page["lines"].append({"x0": round(sub, 2), "y0": round(y, 2),
                                  "x1": round(sub + 22.0, 2), "y1": round(y + 7.0, 2),
                                  "text": f"({token})", "from_sublabel_strip": True})
            added += 1
        if fresh:
            page["lines"].sort(key=lambda l: (l["y0"], l["x0"]))
    if debug and added:
        print(f"[sub-label-strip] {role} 补回 {added} 个子题标签")
    return added


def collect(role: str, pdf_path: Path, tmp_dir: Path, pages_dir: Path, zoom: float,
            ocr: dict, debug: bool):
    import pymupdf
    with pymupdf.open(pdf_path) as pdf:
        pages_meta = [{"rot": pg.rotation, "derot": pg.derotation_matrix,
                       "bounds": P.analysis_bounds(pg),
                       "disp": (pg.rect.x0, pg.rect.y0, pg.rect.x1, pg.rect.y1)}
                      for pg in pdf]
        total = pdf.page_count
    jobs = []
    for pno in range(1, total + 1):
        out = pages_dir / f"{role}-p{pno:03d}-z{zoom:g}.png"
        if not out.exists():
            P.render_page(pdf_path, pno, out, zoom=zoom)
        jobs.append((pno, out))
    pages: dict[int, dict] = {}
    errors = 0
    for pno, out in jobs:
        lines, errs = page_lines(ocr.get(str(out), []), zoom)
        errors += errs
        meta = pages_meta[pno - 1]
        content = None
        # 非 boilerplate 行少于 2 行的页视作无内容页（如 8386 QP p12 只剩一行版权碎片）。
        if len(lines) >= 2:
            content = (min(l["x0"] for l in lines), min(l["y0"] for l in lines),
                       max(l["x1"] for l in lines), max(l["y1"] for l in lines))
        if debug:
            print(f"[page p{pno}] lines={len(lines)} content={'yes' if content else 'no'}")
        pages[pno] = {"no": pno, "lines": lines, "content": content, **meta}
    events: list[dict] = []
    if role == "qp":
        cols = detect_columns(pages)
        label_strip_lines(pdf_path, pages, cols, tmp_dir, pages_dir, role, debug)
        sublabel_strip_lines(pdf_path, pages, cols, tmp_dir, pages_dir, role, debug)
        if debug:
            print(f"[cols] top={cols['top']} sub={cols['sub']} subsub={cols['subsub']} "
                  f"tol={ {k: round(v, 1) for k, v in cols['tol'].items()} }")
        for pno, page in pages.items():
            for line in page["lines"]:
                found = qp_labels(line, cols)
                for level, token in found:
                    events.append({"page": pno, "x0": line["x0"], "y0": line["y0"],
                                   "y1": line["y1"], "level": level, "token": token,
                                   "text": line["text"]})
                if debug and (found or wide(line["text"]).strip()[:1] in "(（["):
                    print(f"[qp p{pno}] x0={line['x0']:7.1f} y0={line['y0']:7.1f} "
                          f"{found} | {line['text'][:60]!r}")
    else:
        label_x = [l["x0"] for page in pages.values()
                   for l in page["lines"] if ms_labels(l, (0, 1e6))]
        for pno, page in pages.items():
            window = ms_window(page, label_x)
            if window is None:
                continue
            if debug:
                print(f"[ms p{pno}] window={tuple(round(v, 1) for v in window)}")
            for line in page["lines"]:
                for level, token in ms_labels(line, window):
                    events.append({"page": pno, "x0": line["x0"], "y0": line["y0"],
                                   "y1": line["y1"], "level": level, "token": token,
                                   "text": line["text"]})
    events.sort(key=lambda e: (e["page"], e["y0"], e["x0"], e["level"]))
    return pages, order_events(events), errors


def order_events(events: list[dict]) -> list[dict]:
    """按「页 -> 视觉行 -> 行内 x -> 层级」重排事件。

    实测（9713 QP p7）：同一视觉行上 OCR 把子题 `(a)` 读在 y0=61.2、把父题 `5` 读在
    y0=61.6，按 y0 排序会让 `(a)` 先出栈，绑到上一题的父号上 —— `5(a)` 整条消失，
    `4(a)` 反而多出一段属于第 5 题的页顶区域。同一行内必须按 x0 先读父号再读子号。
    """
    if not events:
        return events
    events = sorted(events, key=lambda e: (e["page"], e["y0"], e["x0"], e["level"]))
    ordered: list[dict] = []
    line_no = -1
    line_page = None
    line_y0 = None
    for event in events:
        if event["page"] != line_page or line_y0 is None \
                or abs(event["y0"] - line_y0) > LINE_TOL_PT:
            line_no += 1
            line_page = event["page"]
            line_y0 = event["y0"]
        else:
            line_y0 = min(line_y0, event["y0"])
        ordered.append({**event, "_line": line_no})
    ordered.sort(key=lambda e: (e["page"], e["_line"], e["x0"], e["level"]))
    for event in ordered:
        event.pop("_line", None)
    return ordered


def main() -> int:
    parser = argparse.ArgumentParser(description="用 OCR 给 CIE 试卷做题目定位")
    parser.add_argument("key")
    parser.add_argument("--out")
    parser.add_argument("--zoom", type=float, default=DEFAULT_ZOOM)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--no-ms", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--debug-lines", action="store_true")
    args = parser.parse_args()

    try:
        subject, year, season, paper = args.key.split("/")
        int(year)
    except ValueError:
        print(f"KEY 格式应为 <subject>/<year>/<season>/<paper>: {args.key!r}")
        return 2

    tmp_dir = P.paper_tmp(args.key)
    pages_dir = tmp_dir / "pages"
    pdfs: dict[str, Path] = {}
    for role in ("qp", "ms"):
        if role == "ms" and args.no_ms:
            continue
        path = I.locate_pdf(args.key, role)
        if path is None:
            if role == "qp":
                print(f"找不到本地 QP PDF：{tmp_dir}（不联网）")
                return 2
            print(f"警告：找不到本地 MS PDF，按无 MS 处理：{tmp_dir}")
            continue
        pdfs[role] = path

    images: list[Path] = []
    for role, path in pdfs.items():
        import pymupdf
        with pymupdf.open(path) as pdf:
            total = pdf.page_count
        for pno in range(1, total + 1):
            out = pages_dir / f"{role}-p{pno:03d}-z{args.zoom:g}.png"
            if not out.exists():
                P.render_page(path, pno, out, zoom=args.zoom)
            images.append(out)
    ocr = run_ocr(images, tmp_dir)

    analysis: dict[str, dict] = {}
    ocr_errors = 0
    for role, path in pdfs.items():
        pages, events, errors = collect(role, path, tmp_dir, pages_dir, args.zoom, ocr,
                                        args.debug_lines)
        analysis[role] = {"pages": pages, "events": events}
        ocr_errors += errors

    questions, dropped, qp_deepest = build_hierarchy(analysis["qp"]["events"], "qp")
    qp_pages = analysis["qp"]["pages"]
    qp_lead = lead_owner(analysis["qp"]["events"], qp_deepest)
    for node in questions.values():
        lead = {p: next(e["y0"] for e in analysis["qp"]["events"] if e["page"] == p)
                for p, owner in qp_lead.items()
                if is_ancestor(questions, node["question"], owner)}
        node["regions"] = build_regions(
            subtree_indexes(questions, node["question"]), analysis["qp"]["events"], qp_pages,
            lead=lead)
        if len(node["regions"]) > MAX_REGIONS:
            node["schema_limit"] = len(node["regions"])
            node["regions"] = node["regions"][:MAX_REGIONS]

    ms_map: dict[str, dict] = {}
    if "ms" in analysis:
        ms_questions, ms_dropped, ms_deepest = build_hierarchy(analysis["ms"]["events"], "ms")
        dropped += ms_dropped
        ms_pages = analysis["ms"]["pages"]
        ms_lead = lead_owner(analysis["ms"]["events"], ms_deepest)
        for qid, node in ms_questions.items():
            lead = {p: next(e["y0"] for e in analysis["ms"]["events"] if e["page"] == p)
                    for p, owner in ms_lead.items()
                    if is_ancestor(ms_questions, qid, owner)}
            node["regions"] = build_regions(
                subtree_indexes(ms_questions, qid), analysis["ms"]["events"], ms_pages,
                lead=lead)
        ms_map = ms_questions
    for node in questions.values():
        node["ms_regions"], node["ms_shared"] = [], None
        hit = ms_map.get(node["question"])
        if hit is None:
            parts = node["question"].replace(")", "").split("(")
            for cut in range(len(parts) - 1, 0, -1):
                candidate = parts[0] + "".join(f"({p})" for p in parts[1:cut])
                if candidate in ms_map:
                    node["ms_shared"] = candidate
                    break
        else:
            node["ms_regions"] = [dict(reg) for reg in hit["regions"]]
        if len(node["ms_regions"]) > MAX_REGIONS:
            node["schema_limit"] = len(node["ms_regions"])
            node["ms_regions"] = node["ms_regions"][:MAX_REGIONS]

    marks_found = 0
    for node in questions.values():
        node["marks"] = None
        node["text"] = region_text(node["regions"], qp_pages)
        if any(other["parent"] == node["question"] for other in questions.values()):
            continue
        node["marks"] = find_marks(node["regions"], qp_pages)
        marks_found += 1 if node["marks"] is not None else 0

    index = {
        "schema_version": "1",
        "board": "cie",
        "identity": {"subject": subject, "year": int(year), "season": season, "paper": paper},
        "coordinate_system": "unrotated_pdf_points_top_left",
        "page_base": 1,
        "documents": [{"role": role, "sha256": B.sha256_file(path)}
                      for role, path in pdfs.items()],
        "questions": [],
    }
    order = sorted(questions, key=lambda q: min(questions[q]["events"]))
    for qid in order:
        node = questions[qid]
        qp_regions = [{"page": reg["page"],
                       "bbox": to_unrot(qp_pages[reg["page"]]["derot"],
                                        qp_pages[reg["page"]]["bounds"], reg["disp"])}
                      for reg in node["regions"]]
        ms_regions = []
        if "ms" in analysis:
            ms_pages = analysis["ms"]["pages"]
            ms_regions = [{"page": reg["page"],
                           "bbox": to_unrot(ms_pages[reg["page"]]["derot"],
                                            ms_pages[reg["page"]]["bounds"], reg["disp"])}
                          for reg in node["ms_regions"]]
        text = node["text"]
        uncertain = not text.strip()
        notes = [OCR_NOTE if node["level"] == 1 else f"{OCR_NOTE}（说明继承自父题 {node['parent']}）"]
        if node["ms_shared"]:
            uncertain = True
            notes.append(f"MS 未单独列出该子题，其评分内容并入 {node['ms_shared']} 的 MS 单元格，"
                         f"请结合 {node['ms_shared']} 的 ms 区域阅读；本题未单独定位")
        elif not ms_regions:
            uncertain = True if "ms" in analysis else uncertain
            notes.append(MS_NOTE if "ms" in analysis else "本次未处理 MS")
        if node.get("schema_limit"):
            notes.append(f"区域数超过上限 {MAX_REGIONS}，已截断为 {MAX_REGIONS}，"
                         f"原为 {node['schema_limit']}")
        if len(text) > MAX_TEXT:
            notes.append(f"text 截断到 {MAX_TEXT} 字符")
        if uncertain:
            notes.append("区域里没有可用的 OCR 文本，请复核定位")
        index["questions"].append({
            "question": qid, "parent": node["parent"], "text": text[:MAX_TEXT],
            "marks": node["marks"], "qp": qp_regions, "ms": ms_regions,
            "uncertain": uncertain, "notes": "；".join(notes)[:MAX_NOTES],
        })

    top = [q for q in index["questions"] if q["parent"] is None]
    stats = {
        "pages": len(qp_pages),
        "pages_with_text": sum(1 for page in qp_pages.values() if page["lines"]),
        "ocr_lines": sum(len(page["lines"]) for page in qp_pages.values()),
        "questions": len(index["questions"]), "top_level": len(top),
        "subs": sum(1 for q in index["questions"] if q["parent"] and q["question"].count("(") == 1),
        "subsubs": sum(1 for q in index["questions"] if q["question"].count("(") == 2),
        "marks_found": marks_found,
        "uncertain": sum(1 for q in index["questions"] if q["uncertain"]),
        "ocr_errors": ocr_errors,
        "dropped_labels": dropped[:10],
    }

    if args.report:
        pages_by_role = {"qp": qp_pages}
        if "ms" in analysis:
            pages_by_role["ms"] = analysis["ms"]["pages"]
        for qid in order:
            node = questions[qid]
            for role, key in (("qp", "regions"), ("ms", "ms_regions")):
                pages_map = pages_by_role.get(role)
                if pages_map is None:
                    continue
                for reg in node[key]:
                    page = pages_map[reg["page"]]
                    x0, y0, x1, y1 = reg["disp"]
                    rows = [l for l in page["lines"]
                            if l["y0"] >= y0 - 1.0 and l["y1"] <= y1 + 1.0]
                    rows.sort(key=lambda l: (l["y0"], l["x0"]))
                    head = repair(" ".join(l["text"] for l in rows[:2]))[:60]
                    bbox = to_unrot(page["derot"], page["bounds"], reg["disp"])
                    print(f"{qid} | {role} | p{reg['page']} | {bbox} | {head}")
        print(json.dumps(stats, ensure_ascii=False))
        return 0

    out = Path(args.out) if args.out else B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    if out.exists() and not args.force:
        print(f"目标已存在，未覆盖（加 --force 才写）：{out}")
        return 3
    B.atomic_write_json(out, index)
    print(json.dumps({"out": str(out), **stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
