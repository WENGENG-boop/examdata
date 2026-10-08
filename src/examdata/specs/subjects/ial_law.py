"""IAL Law spec 解析器（Pearson Edexcel International Advanced Level in Law）。

仓库里有两份 PDF，版式不同，按各自印出来的编号解析：

ial-law-0（Issue 4, 2021；入口码 YLA1）——"N.3 Paper content" 起是两栏表：
  左栏 "Subject content"：内容区标题，印刷编号 1.1 / 1.2 / 2.1 / 2.2 / 2.3；
  右栏 "What students need to learn:"：编号知识点 N.M.K。
  → 单元 = Paper，主题 = 内容区（N.M），节点 = 知识点（N.M.K）。
  右栏还有无编号的分组标题（Legislation / Judicial law making / The law of
  contract 等），spec 没给编号，因此不建节点、也不硬造编号，按原文顺序留在
  知识点文本里（多数落在前一个知识点的末尾，卷首的落在首个知识点开头；见 issues）。

ial-law-1（Issue 3, 2015；入口码 YLA0）——"N.3 Content" 起是分节表：
  节标题带印刷编号 1.3.1–1.3.4 / 2.3.1–2.3.5；每节只有一张
  "What students need to learn:" 表，表内是要点符号（无编号），左栏行号 "1"
  是表内计数而非内容编号。
  → 单元 = Paper，节点 = 节；节内无编号要点保留在节文本里（见 issues）。

单元键：ial-law-0 用附录 1 的试卷入口码 YLA1/01、YLA1/02（'/' 不能出现在 label
里，换成 '-'）；ial-law-1 附录 2 只有资格码 YLA0，没有分卷入口码，用
YLA0-P1、YLA0-P2 这种稳定可解释的键，两种情况都写进 issues。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    PAGE_MARK_RE,
    clean_block,
    first_sentence,
    page_of_offset,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-law"
SUBJECT = "International A Level Law"

# 标题跨行续接的判定：行尾是逗号 / 悬空词，或下一行以小写开头
_DANGLING = {"and", "or", "of", "the", "in", "to", "with", "for", "its", "a", "an", "on", "by"}

# ---- 两栏表版式（ial-law-0）----
_PAPER_CONTENT_RE = re.compile(r"(?m)^(\d{1,2})\.3 Paper content\s*$")
_TABLE_HEAD_A = "Subject content"
_TABLE_HEAD_B_RE = re.compile(r"^What students need to learn:?\s*$")
_TOPIC_LINE_RE = re.compile(r"^(\d{1,2}\.\d{1,2})[ \t]+(\S.*)$")
_POINT_LINE_RE = re.compile(r"(?m)^[ \t]*(\d{1,2}\.\d{1,2}\.\d{1,2})[ \t]*(.*)$")
_PAPER_HEAD_RE = re.compile(r"(?m)^Paper (\d{1,2}): (.+)$")
_PAPER_ENTRY_RE = re.compile(r"(?m)^Paper (\d{1,2}): (Y[A-Z0-9]+)/(\d{2})\s*$")
_QUAL_CODE_RE = re.compile(r"in Law \(([A-Z]{3}\d)\)")
_CONTENT_END_RE = re.compile(r"(?m)^Assessment information\s*$")

# ---- 分节表版式（ial-law-1）----
_SECTION_RE = re.compile(r"(?m)^[ \t]*(\d{1,2}\.\d{1,2}\.\d{1,2})[ \t]+(Section [A-Z][^\n]*?)[ \t]*$")
_SECTION_CONTENT_RE = re.compile(r"(?m)^[ \t]*(\d{1,2})\.3[ \t]+Content[ \t]*$")
_SECTION_END_RE = re.compile(r"(?m)^D\t\s*Assessment and additional information\s*$")
_ROW_RE = re.compile(r"^(\d{1,2})[ \t]+(\S.*)$")
_BULLET = "\u0084"  # 项目符号在文本层被抽成 U+0084


def _continues(acc: str, nxt: str) -> bool:
    """标题是否跨行续接（与 biology/mathematics 同一套判定）。"""
    acc = acc.rstrip()
    if acc.endswith(","):
        return True
    if acc.rsplit(" ", 1)[-1].strip(",").lower() in _DANGLING:
        return True
    return nxt[:1].islower()


def _lines(region: str) -> list[tuple[int, str]]:
    """[(行首在本区域内的 offset, 行文本), ...]"""
    out: list[tuple[int, str]] = []
    pos = 0
    for line in region.splitlines(keepends=True):
        out.append((pos, line.rstrip("\r\n")))
        pos += len(line)
    return out


def _blank(buf: list[str], offset: int, line: str) -> None:
    """把该行抹成空格（保留换行），offset 因此始终对得上原文本。"""
    for i in range(offset, offset + len(line)):
        if buf[i] != "\n":
            buf[i] = " "


def _paper_names(text: str, before: Optional[dict[int, int]] = None) -> dict[int, str]:
    """试卷名："Paper N: <title>"，标题跨行时合并。

    "Paper N:" 在目录、总览、卷首页、评估表和附录里反复出现，取本卷内容区
    （before[paper]，即该卷 "N.3 Paper content" 的起点）之前的最后一次。
    """
    picks: dict[int, re.Match[str]] = {}
    for m in _PAPER_HEAD_RE.finditer(text):
        paper = int(m.group(1))
        if before and paper in before and m.start() >= before[paper]:
            continue
        picks[paper] = m  # 后出现的覆盖前面的
    out: dict[int, str] = {}
    for paper, m in picks.items():
        name = m.group(2).strip()
        for line in text[m.end():].splitlines()[1:5]:
            s = line.strip()
            if not s or PAGE_MARK_RE.match(s):
                break
            if _continues(name, s):
                name = f"{name} {s}".strip()
                continue
            break
        out[paper] = name
    return out


def _paper_entry_codes(text: str) -> dict[int, str]:
    """附录 1 的试卷入口码："Paper 1: YLA1/01" → {1: "YLA1/01"}。"""
    return {int(m.group(1)): f"{m.group(2)}/{m.group(3)}" for m in _PAPER_ENTRY_RE.finditer(text)}


def _qual_code(text: str) -> str:
    m = _QUAL_CODE_RE.search(text)
    return m.group(1) if m else "YLA"


def _unit_key(spec: ParsedSpec, paper: int, entry: str, qual: str) -> str:
    """单元键：优先试卷入口码（'/' 换成 '-'），没有就用资格码 + 卷号。"""
    if entry:
        key = entry.replace("/", "-")
        spec.issues.append(
            f"Paper {paper}: entry code {entry!r} contains '/', which is not allowed in a label; "
            f"unit_key uses {key!r}"
        )
        return key
    key = f"{qual}-P{paper}"
    spec.issues.append(
        f"Paper {paper}: the spec prints no per-paper entry code (only qualification code {qual!r}); "
        f"unit_key falls back to {key!r}"
    )
    return key


def _normalize_codes(
    codes: list[str],
    topic_codes: list[str],
    issues: list[str],
    *,
    where: str,
) -> list[str]:
    """修正 spec 自身编号缺陷，返回修正后的编号（与输入等长）。

    本 spec 是三段编号 N.M.K（common.resolve_code_conflicts 只认两段），规则与
    仓库其它科目一致（所有修正写入 issues，不静默）：
      - 编号的主题号（前两段）与所在主题不符 → 改成 `{topic}.{末段}`；
      - 同一单元内编号重复 → 末段递增直到唯一。
    """
    out: list[str] = []
    seen: set[str] = set()
    for code, topic in zip(codes, topic_codes):
        new = re.sub(r"\s+", "", code)
        prefix, _, last = new.rpartition(".")
        if topic and prefix and last and prefix != topic:
            fixed = f"{topic}.{last}"
            issues.append(
                f"{where}: code {new!r} does not match its topic {topic!r}; normalized to {fixed!r}"
            )
            new = fixed
        if new in seen:
            prefix, _, last = new.rpartition(".")
            k = int(last) + 1 if last.isdigit() else 2
            while f"{prefix}.{k}" in seen:
                k += 1
            fixed = f"{prefix}.{k}"
            issues.append(f"{where}: duplicate code {new!r}; normalized to {fixed!r}")
            new = fixed
        seen.add(new)
        out.append(new)
    return out


# --------------------------------------------------------------------------
# 两栏表版式（ial-law-0）
# --------------------------------------------------------------------------


def _scan_columns(region: str) -> tuple[list[tuple[int, str, str, int]], str]:
    """抹掉表头与左栏内容区标题，返回 (boundaries, masked)。

    boundaries = [(区域内 offset, 内容区编号, 标题, 标题块末尾 offset), ...]，
    按 offset 升序。左栏标题每个跨页表只在首行出现一次，位置紧跟在
    "Subject content / What students need to learn:" 之后，据此定位。
    """
    buf = list(region)
    rows = _lines(region)
    headings: dict[str, tuple[str, int, int]] = {}
    i = 0
    while i < len(rows):
        off, line = rows[i]
        if line.strip() == _TABLE_HEAD_A and i + 1 < len(rows) and _TABLE_HEAD_B_RE.match(rows[i + 1][1].strip()):
            _blank(buf, off, line)
            _blank(buf, rows[i + 1][0], rows[i + 1][1])
            j = i + 2
            if j < len(rows):
                m = _TOPIC_LINE_RE.match(rows[j][1].strip())
                if m and m.group(2).strip() != "Paper content":
                    code = m.group(1)
                    head = m.group(2).strip()
                    k = j + 1
                    while k < len(rows):
                        nxt = rows[k][1].strip()
                        if not nxt or PAGE_MARK_RE.match(nxt):
                            break
                        if nxt == "(continued)":
                            _blank(buf, rows[k][0], rows[k][1])
                            k += 1
                            break
                        if _continues(head, nxt):
                            _blank(buf, rows[k][0], rows[k][1])
                            head = f"{head} {nxt}".strip()
                            k += 1
                            continue
                        break
                    for t in range(j, k):
                        _blank(buf, rows[t][0], rows[t][1])
                    block_end = rows[k - 1][0] + len(rows[k - 1][1])
                    prev = headings.get(code)
                    if prev is None or len(head) > len(prev[0]):
                        headings[code] = (head, off, block_end)
                    i = k
                    continue
            i += 1
            continue
        i += 1
    boundaries = sorted(
        (off, code, head, block_end) for code, (head, off, block_end) in headings.items()
    )
    return boundaries, "".join(buf)


def _parse_columns(text: str, spec: ParsedSpec) -> None:
    marks = [(int(m.group(1)), m.start()) for m in _PAPER_CONTENT_RE.finditer(text)]
    if not marks:
        raise ValueError("no 'N.3 Paper content' heading found")
    end_m = _CONTENT_END_RE.search(text, marks[-1][1])
    global_end = end_m.start() if end_m else len(text)
    entries = _paper_entry_codes(text)
    names = _paper_names(text, {paper: start for paper, start in marks})
    qual = _qual_code(text)

    for i, (paper, start) in enumerate(marks):
        seg_end = marks[i + 1][1] if i + 1 < len(marks) else global_end
        div = re.search(rf"(?m)^Paper {paper + 1}: ", text[start:seg_end])
        if div:  # 下一卷的卷首页不属于本卷内容区
            seg_end = start + div.start()
        region = text[start:seg_end]
        boundaries, masked = _scan_columns(region)
        heads = {code: head for _off, code, head, _end in boundaries}
        head_offs = {code: off for off, code, _head, _end in boundaries}
        known_topics = set(heads)

        key = _unit_key(spec, paper, entries.get(paper, ""), qual)
        unit = SpecUnit(code=str(paper), name=names.get(paper) or f"Paper {paper}", unit_key=key)

        matches = list(_POINT_LINE_RE.finditer(masked))
        entries_pt: list[tuple[str, str, str, int]] = []
        for idx, m in enumerate(matches):
            body_start = m.end()
            body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(masked)
            entries_pt.append((m.group(1), m.group(2), masked[body_start:body_end], m.start()))

        # 主题归属：印出的前缀是已知主题就按前缀；否则（编号有缺陷）归到最近的左栏
        # 标题块，编号再由 _normalize_codes 规范化。
        topic_seq: list[str] = []
        for raw_code, _inline, _body, off in entries_pt:
            prefix = raw_code.rpartition(".")[0]
            enclosing = ""
            for b_off, b_code, _head, _end in boundaries:
                if b_off <= off:
                    enclosing = b_code
                else:
                    break
            topic_seq.append(prefix if prefix in known_topics or not enclosing else enclosing)
        fixed = _normalize_codes(
            [code for code, _inline, _body, _off in entries_pt],
            topic_seq,
            spec.issues,
            where=f"Paper {paper}",
        )

        # 首个知识点之前、最后一个被抹掉的标题块之后若有正文（无编号的分组标题），
        # 归入首个知识点，避免丢失。
        lead = ""
        if boundaries and matches:
            lead = clean_block(masked[boundaries[0][3]:matches[0].start()])

        topics: dict[str, SpecNode] = {}
        for (raw_code, inline, body, off), code in zip(entries_pt, fixed):
            topic_code = code.rpartition(".")[0]
            parent = topics.get(topic_code)
            if parent is None:
                head = heads.get(topic_code, "")
                if not head:
                    spec.issues.append(
                        f"Paper {paper}: topic {topic_code!r} has no printed heading in the "
                        f"'Subject content' column; title falls back to the code"
                    )
                parent = SpecNode(
                    code=topic_code,
                    label=f"{key}-{topic_code}",
                    title=head or f"Topic {topic_code}",
                    text=clean_block(head),
                    page=page_of_offset(text, start + head_offs.get(topic_code, off)),
                )
                topics[topic_code] = parent
                unit.nodes.append(parent)
            own = clean_block(inline + body)
            block = f"{lead}\n{own}".strip() if lead and off == matches[0].start() else own
            parent.children.append(
                SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=first_sentence(own) or f"Point {code}",
                    text=block,
                    page=page_of_offset(text, start + off),
                )
            )
        if not unit.nodes:
            spec.issues.append(f"Paper {paper} ({key}): no numbered content points parsed")
        spec.units.append(unit)


# --------------------------------------------------------------------------
# 分节表版式（ial-law-1）
# --------------------------------------------------------------------------


def _section_block(body: str) -> tuple[str, str]:
    """节正文：拆出左栏 "Subject content" 行，其余（要点）转成块文本。"""
    lines = body.splitlines()
    heading = ""
    kept: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or _TABLE_HEAD_B_RE.match(s):
            i += 1
            continue
        m = _ROW_RE.match(s) if not heading else None
        if m and m.group(2).strip() != "Content":
            head = m.group(2).strip()
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or _BULLET in nxt or PAGE_MARK_RE.match(nxt):
                    break
                if _continues(head, nxt):
                    head = f"{head} {nxt}".strip()
                    j += 1
                    continue
                break
            heading = head
            i = j
            continue
        if s == _BULLET:  # 单独成行的项目符号残片
            i += 1
            continue
        kept.append(lines[i].replace(_BULLET, "•", 1) if _BULLET in lines[i] else lines[i])
        i += 1
    parts = ([heading] if heading else []) + kept
    return heading, clean_block("\n".join(parts))


def _parse_sections(text: str, spec: ParsedSpec) -> None:
    marks = [(int(m.group(1)), m.start()) for m in _SECTION_CONTENT_RE.finditer(text)]
    if not marks:
        raise ValueError("no 'N.3 Content' heading found")
    end_m = _SECTION_END_RE.search(text, marks[-1][1])
    global_end = end_m.start() if end_m else len(text)
    qual = _qual_code(text)

    for i, (paper, start) in enumerate(marks):
        seg_end = marks[i + 1][1] if i + 1 < len(marks) else global_end
        region = text[start:seg_end]
        key = _unit_key(spec, paper, "", qual)
        unit = SpecUnit(code=str(paper), name=f"Paper {paper}", unit_key=key)

        secs = list(_SECTION_RE.finditer(region))
        for j, sm in enumerate(secs):
            sec_end = secs[j + 1].start() if j + 1 < len(secs) else len(region)
            _heading, block = _section_block(region[sm.end():sec_end])
            code = sm.group(1)
            unit.nodes.append(
                SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=sm.group(2).strip() or f"Section {code}",
                    text=block,
                    page=page_of_offset(text, start + sm.start()),
                )
            )
        if secs:
            spec.issues.append(
                f"Paper {paper} ({key}): the spec numbers only the sections "
                f"({secs[0].group(1)}–{secs[-1].group(1)}); their 'What students need to learn' "
                f"points are unnumbered bullets, so no deeper nodes are created and the bullets "
                f"stay in the section text"
            )
        else:
            spec.issues.append(f"Paper {paper} ({key}): no numbered sections parsed")
        spec.units.append(unit)


# --------------------------------------------------------------------------


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    if _SECTION_RE.search(text):
        _parse_sections(text, spec)
    elif _PAPER_CONTENT_RE.search(text):
        _parse_columns(text, spec)
        spec.issues.append(
            "the 'What students need to learn' column also carries unnumbered group headings "
            "(e.g. Legislation, Judicial law making, The law of contract); the spec gives them no "
            "codes, so they are not separate nodes: they stay in source order inside the text of "
            "the point block they fall into (at the end of the preceding point, or at the start of "
            "a paper's first point)"
        )
    else:
        raise ValueError("unrecognized IAL Law spec layout")
    return spec
