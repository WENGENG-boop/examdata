"""IAL Arabic (2016, Issue 3) spec 解析器。

结构（内容区 = "Arabic content" 到 "Assessment information"，页 15-32，共 2 个单元）：
  Unit N: <name>          → 单元；unit_key 取自附录 1 "Unit N: WAA0N/01"
    N.M <section title>   → 主题/内容区（1.1-1.4、2.1-2.6）
      n <label>           → 编号知识点；code 规范为 "{section}.{n}"（见下）

spec 用表格排版，三类区块的处理方式不同：
  - table_rows（1.1/1.2/2.1/2.2）：左列编号行是表格标签，右列是整块正文（1.2/2.2 为
    跨行合并单元格，1.1/2.1 为每行一段）。抽取文本没有段落边界，正文只能整块挂在
    section 节点上，行节点只保留标签文本，限制记入 issues；
  - topic_areas（1.3/2.3）：编号 + 主题领域名（可能折行）后跟未编号的子条目；子条目
    保留在父节点 text 中，不强行编号；
  - prose（1.4/2.4/2.5/2.6）：无编号结构，section 节点即能负责的最细层级。

已知 spec 缺陷（规范化动作全部记入 issues，不静默）：
  - 2.1 第 4 行标签印成 "pic areas"（应为 "Topic areas"），按原文保留；
  - 条目编号在每个 section 内从 1 重新开始，不是全局唯一，因此规范为
    "{section}.{n}"（如 1.3.1）；重复/缺号由 _normalize_item_codes/_check_gaps 处理。
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional

from ..common import clean_block, content_span, page_of_offset
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-arabic"
SUBJECT = "International A Level Arabic (2016)"

UNIT_HEADER_RE = re.compile(r"^Unit (?P<code>\d+): (?P<name>.+?)\s*$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
SECTION_RE = re.compile(r"^(?P<code>\d\.\d)\s+(?P<title>\S.*?)\s*$", re.M)
ROW_RE = re.compile(r"^(?P<num>\d{1,2})\s+(?P<label>\S.*?)\s*$")

# 页眉第二种折行（" – Specification – Issue 3 – …"）不在 common.clean_block 的规则里
_HEADER_RE = re.compile(r"^[–-]?\s*Specification\s*[–-]\s*Issue\b.*$")

# 表格正文起始判定：正文行要么以项目符号开头，要么明显长于左列标签（标签 ≤ 17 字符）
_BODY_MIN_LEN = 26

# 独占一行的项目符号（PDF 里与紧随的正文同一行，抽取后分行）
_BULLET_ONLY = {"•", "●", "▪", "-", "–"}

# 折行续接的连接词（标签/条目末词是它们时说明还没写完）
_CONNECTORS = {
    "and", "or", "of", "the", "in", "to", "with", "for", "a", "an",
    "on", "at", "by", "from", "its",
}

_SECTION_KINDS = {
    "1.1": "table_rows",
    "1.2": "table_rows",
    "1.3": "topic_areas",
    "1.4": "prose",
    "2.1": "table_rows",
    "2.2": "table_rows",
    "2.3": "topic_areas",
    "2.4": "prose",
    "2.5": "prose",
    "2.6": "prose",
}

# 按原文保留、但需在 issues 里点名的印刷缺陷（键为小写标签）
_LABEL_NOTES = {
    "pic areas": (
        "row label 'pic areas' is printed that way in the spec "
        "(apparently 'Topic areas' with dropped text); kept as printed"
    ),
}


def _clean(block: str) -> str:
    """clean_block + 本 spec 页眉折行变体 + 合并独占一行的项目符号。"""
    lines = [
        line
        for line in clean_block(block).splitlines()
        if not _HEADER_RE.match(line.strip())
    ]
    out: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s in _BULLET_ONLY and i + 1 < len(lines) and lines[i + 1].strip():
            out.append(f"{s} {lines[i + 1].strip()}")
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip()


def _sep_after(raw_line: str) -> str:
    """左列窄栏里行尾无空格 = 单词被折断，续接时直接拼接。"""
    return " " if raw_line.rstrip("\r\n").endswith((" ", "\t")) else ""


def _iter_lines(block: str, base: int) -> Iterator[tuple[int, str]]:
    """按行遍历并给出每行在原始 text 中的绝对 offset。"""
    pos = 0
    for line in block.splitlines(keepends=True):
        yield base + pos, line
        pos += len(line)


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录页列表与附录 1 的代码行）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        if re.fullmatch(r"W[A-Z0-9]+/\d+", m.group("name").strip()):
            continue
        last[m.group("code")] = m
    return sorted(last.values(), key=lambda m: m.start())


def _continues(prev: str, nxt: str) -> bool:
    """折行续接判定：前一行以逗号/连字符/连接词结尾，或后一行以小写字母开头。"""
    p = prev.strip()
    if p.endswith((",", "-", "–")):
        return True
    if p.rsplit(" ", 1)[-1].lower().strip(".,;:") in _CONNECTORS:
        return True
    return nxt.strip()[:1].islower()


def _normalize_item_codes(
    section: str, nums: list[str], where: str, spec: ParsedSpec
) -> list[str]:
    """规范 section 内的条目编号：重复编号递增到未占用的号并记入 issues。"""
    out: list[str] = []
    used: set[str] = set()
    for num in nums:
        cand = num
        if cand in used:
            k = 1
            while str(k) in used:
                k += 1
            spec.issues.append(
                f"{where}: duplicate item number {num!r} in spec; normalized to {str(k)!r}"
            )
            cand = str(k)
        used.add(cand)
        out.append(cand)
    return out


def _check_gaps(nums: list[str], where: str, spec: ParsedSpec) -> None:
    """缺号检查：编号不连续时记入 issues（编号本身按 spec 原样保留）。"""
    ints = sorted({int(n) for n in nums})
    missing = [str(i) for i in range(1, max(ints) + 1) if i not in ints] if ints else []
    if missing:
        spec.issues.append(f"{where}: item numbers skip {missing} in spec; printed numbering kept")


def _table_rows(
    body: str, base: int
) -> tuple[list[tuple[str, str, int]], str, int]:
    """表格类区块：返回 ([(编号, 标签, offset)], 正文文本, 正文 offset)。"""
    lines = list(_iter_lines(body, base))
    cut = len(lines)
    for i, (_off, line) in enumerate(lines):
        s = line.strip()
        if s.startswith("•") or len(s) > _BODY_MIN_LEN:
            cut = i
            break

    rows: list[tuple[str, str, int]] = []
    cur: Optional[tuple[str, str, int, str]] = None
    for off, line in lines[:cut]:
        s = line.strip()
        if not s:
            continue
        m = ROW_RE.match(s)
        if m:
            if cur is not None:
                rows.append(cur[:3])
            cur = (m.group("num"), m.group("label"), off, line)
        elif cur is not None:
            cur = (cur[0], f"{cur[1]}{_sep_after(cur[3])}{s}".strip(), cur[2], line)
    if cur is not None:
        rows.append(cur[:3])

    rest = "".join(line for _off, line in lines[cut:])
    rest_off = lines[cut][0] if cut < len(lines) else base
    return rows, rest, rest_off


def _topic_areas(
    body: str, base: int
) -> tuple[list[str], list[tuple[str, str, list[str], int]]]:
    """主题领域类区块：返回 (前言行, [(编号, 名称, 子条目, offset)])。

    spec 里 "What students need to learn:" 与第 1 个主题之间可能没有空行，所以按行
    推进：编号行开新主题，其后先按折行规则续接名称，其余行才是子条目。
    """
    preamble: list[str] = []
    topics: list[list[Any]] = []
    in_label = False
    last_raw = ""
    for off, line in _iter_lines(body, base):
        s = line.strip()
        if not s:
            in_label = False
            continue
        m = ROW_RE.match(s)
        if m:
            topics.append([m.group("num"), m.group("label"), [], off])
            in_label = True
            last_raw = line
            continue
        if topics and in_label and _continues(topics[-1][1], s):
            topics[-1][1] = f"{topics[-1][1]}{_sep_after(last_raw)}{s}".strip()
            last_raw = line
            continue
        in_label = False
        if not topics:
            preamble.append(s)
            continue
        items: list[str] = topics[-1][2]
        if items and (s.startswith("(") or _continues(items[-1], s)):
            items[-1] = f"{items[-1]}{_sep_after(last_raw)}{s}".strip()
        else:
            items.append(s)
        last_raw = line
    return preamble, [tuple(t) for t in topics]


def _check_topic_wording(unit: SpecUnit, spec: ParsedSpec) -> None:
    """对照单元描述里的主题领域项目符号与 §N.3 主题表标题，措辞不一致时记入 issues。"""
    desc = next((n for n in unit.nodes if n.code == f"{unit.code}.1"), None)
    areas = next((n for n in unit.nodes if n.code == f"{unit.code}.3"), None)
    if desc is None or areas is None or not areas.children:
        return
    bullets = {
        _norm_phrase(line.lstrip("• ").strip())
        for line in desc.text.splitlines()
        if line.strip().startswith("•")
    }
    for child in areas.children:
        if bullets and _norm_phrase(child.title) not in bullets:
            spec.issues.append(
                f"Unit {unit.code} §{areas.code}: topic title {child.title!r} differs in wording from "
                f"the unit description's topic-area bullets; title kept as printed in §{areas.code}"
            )


def _norm_phrase(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"Arabic content", r"(?m)^Assessment information\s*$")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    if not headers:
        spec.issues.append("no unit headers found in content region")
        return spec

    for i, header in enumerate(headers):
        num = header.group("code")
        name = header.group("name").strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, f"U{num}")
        if num not in keys:
            spec.issues.append(
                f"Unit {num}: no unit code in Appendix 1; unit_key {key!r} used"
            )

        unit = SpecUnit(code=num, name=name, unit_key=key)
        spec.units.append(unit)
        spec.issues.append(
            f"Unit {num}: spec restarts item numbering inside each section; codes normalized to "
            f"'<section>.<item>' (e.g. '{num}.3.1') so labels stay unique"
        )

        sections = [
            (m.group("code"), m.group("title"), m.start())
            for m in SECTION_RE.finditer(ubody)
            if m.group("code").startswith(f"{num}.")
        ]
        if not sections:
            spec.issues.append(
                f"Unit {num} ({key}): no numbered sections found; unit-level content only"
            )

        for j, (sec_code, sec_title, sec_start) in enumerate(sections):
            sec_end = sections[j + 1][2] if j + 1 < len(sections) else len(ubody)
            raw = ubody[sec_start:sec_end]
            nl = raw.find("\n")
            body = raw[nl + 1 :] if nl != -1 else ""
            body_off = ustart + sec_start + (nl + 1 if nl != -1 else len(raw))
            node = SpecNode(
                code=sec_code,
                label=f"{key}-{sec_code}",
                title=sec_title,
                page=page_of_offset(text, start + ustart + sec_start),
            )
            unit.nodes.append(node)
            where = f"Unit {num} §{sec_code}"
            kind = _SECTION_KINDS.get(sec_code, "prose")

            if kind == "table_rows":
                rows, rest, _rest_off = _table_rows(body, start + body_off)
                node.text = _clean(rest)
                nums = _normalize_item_codes(
                    sec_code, [r[0] for r in rows], where, spec
                )
                _check_gaps(nums, where, spec)
                for (rnum, rlabel, roff), code in zip(rows, nums):
                    icode = f"{sec_code}.{code}"
                    node.children.append(
                        SpecNode(
                            code=icode,
                            label=f"{key}-{icode}",
                            title=rlabel,
                            text="",
                            page=page_of_offset(text, roff),
                        )
                    )
                spec.issues.append(
                    f"{where}: table rows are left-column labels and the right column is a body "
                    f"cell; body text attached to the section node, row nodes carry no separate text"
                )
                for _rnum, rlabel, _roff in rows:
                    note = _LABEL_NOTES.get(rlabel.strip().casefold())
                    if note:
                        spec.issues.append(f"{where}: {note}")
            elif kind == "topic_areas":
                preamble, topics = _topic_areas(body, start + body_off)
                node.text = _clean("\n".join(preamble))
                nums = _normalize_item_codes(
                    sec_code, [t[0] for t in topics], where, spec
                )
                _check_gaps(nums, where, spec)
                for (tnum, tlabel, items, toff), code in zip(topics, nums):
                    icode = f"{sec_code}.{code}"
                    node.children.append(
                        SpecNode(
                            code=icode,
                            label=f"{key}-{icode}",
                            title=tlabel,
                            text=_clean("\n".join(items)),
                            page=page_of_offset(text, toff),
                        )
                    )
                spec.issues.append(
                    f"{where}: topic-area sub-items are unnumbered in the spec; kept in the parent "
                    f"point's text instead of being given invented codes"
                )
            else:
                node.text = _clean(body)
                spec.issues.append(
                    f"{where}: no numbered items in this section; section node is the finest level parsed"
                )

        _check_topic_wording(unit, spec)

    return spec
