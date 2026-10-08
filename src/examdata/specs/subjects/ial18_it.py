"""IAL Information Technology (2018, Issue 2) spec 解析器。

结构（PDF 页 17-54 内容区，4 个单元）：
  Unit N                  → 单元；unit_key 取自 Appendix 1: Codes 的 "Unit N: WITNN/01"
    N.M Unit content      → 内容区起点（之前是 N.1 Unit description / N.2 Assessment information）
      Topic N: <name>     → 主题；块文本为主题导语（去掉重复的 "What students need to learn" 栏题）
        N.M <heading>     → 小节；标题可印在编号同行，也可印在下一行
          N.M.K <text...> → 编号知识点；块文本含 a./b./c. 子条目，供标注用

spec 把单元级 N.1 Unit description / N.2 Assessment information / N.3 Unit content 与
主题小节放在同一编号空间（Unit 1 同时印出 "1.1 Unit description" 和 "1.1 Hardware"），
因此内容树只取 "N.3 Unit content" 之后的编号，冲突记入 issues。
spec 不印单元标题，单元 name 由印出的 "IAS/IA2 compulsory unit" 行与 Content overview
的主题名合成，记入 issues。

编号检查：19 个主题、60 个小节、218 个知识点编号连续、无重复、无错位，
resolve_code_conflicts 在本 spec 上不会触发修正（仍保留调用，防后续 Issue 变化）；
缺号只报告不重排，以免改动印出的编号。

块文本清理：clean_block 之后，把独占一行的列表标记（"a."、"(i)"）并回下一行，
这是 PDF 双栏版式造成的换行差异（同一份 spec 内 "a. speed" 与 "a.\\nportability" 混用）；
编号行末尾的断词连字符直接接回（"WAI-" + "ARIA" → "WAI-ARIA"）。
知识点 title 取首句、limit=200（最长 177 字符，保证 218 个知识点标题不被截断）。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    clean_block,
    content_span,
    first_sentence,
    marker_blocks,
    page_of_offset,
    resolve_code_conflicts,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial18-it"
SUBJECT = "International A Level Information Technology (2018)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+)\s*$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
UNIT_CONTENT_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+Unit content\s*$", re.M)
LEVEL_RE = re.compile(r"^(IAS|IA2) compulsory unit\s*$", re.M)
TOPIC_RE = re.compile(r"^Topic (\d+): (.+)$", re.M)
SECTION_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?!\.\d)[ \t]*(.*)$", re.M)
POINT_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{1,2})[ \t]*(.*)$", re.M)
LEARN_HEADER_RE = re.compile(r"^What students need to learn\s*$", re.M)
MARKER_LINE_RE = re.compile(r"^(?:[a-z]\.|\([a-z0-9ivx]+\))$")


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过 "Information Technology content" 目录页列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _tidy(text: str) -> str:
    """clean_block + 把独占一行的列表标记并回下一行。"""
    merged: list[str] = []
    for line in clean_block(text).splitlines():
        stripped = line.strip()
        if (
            merged
            and stripped
            and not MARKER_LINE_RE.fullmatch(stripped)
            and MARKER_LINE_RE.fullmatch(merged[-1].strip())
        ):
            merged[-1] = f"{merged[-1].strip()} {stripped}"
        else:
            merged.append(line)
    return "\n".join(merged).strip()


def _section_parts(inline: str, body: str) -> tuple[str, str]:
    """小节标题与正文：标题优先取编号同行文本，否则取块首行。"""
    if inline:
        return inline, _tidy(body)
    cleaned = _tidy(body)
    lines = cleaned.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            return line.strip(), "\n".join(lines[i + 1 :]).strip()
    return "", cleaned


def _unit_name(level: str, topic_titles: list[str]) -> str:
    """spec 不印单元标题：用印出的 IAS/IA2 行 + Content overview 的主题名合成。"""
    base = f"{level} compulsory unit" if level else "compulsory unit"
    return f"{base}: {'; '.join(topic_titles)}" if topic_titles else base


def _note_gaps(codes: list[str], spec: ParsedSpec, where: str) -> None:
    """缺号/重复检查：只报告，不重排印出的编号。

    主题号在整份 spec 内连续（1-19，跨单元），所以按最小值起算；
    小节/知识点号在各自父级下从 1 起算。
    """
    seqs: dict[str, list[int]] = {}
    for code in codes:
        head, _, tail = code.rpartition(".")
        if tail.isdigit():
            seqs.setdefault(head, []).append(int(tail))
    for head, vals in seqs.items():
        low = 1 if head else min(vals)
        if sorted(vals) != list(range(low, max(vals) + 1)):
            spec.issues.append(
                f"{where}: {head or 'topic'} numbering is not contiguous: {sorted(vals)}"
            )


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(
        text, r"Information Technology content", r"(?m)^Assessment information\s*$"
    )
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    if not headers:
        spec.issues.append("no unit headings found in content region")
        return spec

    spec.issues.append(
        "spec prints no unit titles; unit names are composed from the printed "
        "'IAS/IA2 compulsory unit' line and the Content overview topic list"
    )
    spec.issues.append(
        "unit-level 'N.1 Unit description' / 'N.2 Assessment information' / 'N.3 Unit content' "
        "share the numbering space with the topic sections (Unit 1 prints both "
        "'1.1 Unit description' and '1.1 Hardware'); the content tree is scoped to the "
        "'N.3 Unit content' region and those unit-level sections are not emitted as nodes"
    )

    for i, header in enumerate(headers):
        num = header.group(1)
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, "")
        if not key:
            key = f"WIT1{num}"
            spec.issues.append(
                f"Unit {num}: no entry code in Appendix 1: Codes; using {key!r}"
            )
        level_m = LEVEL_RE.search(ubody)
        level = level_m.group(1) if level_m else ""

        content_marks = list(UNIT_CONTENT_RE.finditer(ubody))
        topic_titles: list[str] = []
        unit = SpecUnit(code=num, name="", unit_key=key)
        if not content_marks:
            spec.issues.append(f"Unit {num} ({key}): 'Unit content' section not found")
            unit.name = _unit_name(level, topic_titles)
            spec.units.append(unit)
            continue

        cbegin = content_marks[-1].end()
        cbody = ubody[cbegin:]

        markers: list[tuple[int, str, str, str]] = []
        for m in TOPIC_RE.finditer(cbody):
            topic_titles.append(m.group(2).strip())
            markers.append((m.start(), "topic", m.group(1), m.group(2).strip()))
        for m in SECTION_RE.finditer(cbody):
            code = f"{m.group(1)}.{m.group(2)}"
            markers.append((m.start(), "section", code, m.group(3).strip()))
        for m in POINT_RE.finditer(cbody):
            code = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
            markers.append((m.start(), "point", code, m.group(4).strip()))
        markers.sort(key=lambda x: x[0])
        entries = marker_blocks(cbody, markers)

        topic_of: dict[int, Optional[str]] = {}
        cur_topic: Optional[str] = None
        for kind, code, _heading, _btext, off in entries:
            if kind == "topic":
                cur_topic = code
            topic_of[off] = cur_topic

        fixed_by_offset: dict[int, str] = {}
        for kind in ("section", "point"):
            picked = [e for e in entries if e[0] == kind]
            fixed = resolve_code_conflicts(
                [e[1] for e in picked],
                [topic_of[e[4]] for e in picked],
                spec.issues,
                where=f"Unit {num}",
            )
            for entry, fcode in zip(picked, fixed):
                fixed_by_offset[entry[4]] = fcode

        topic_nodes: dict[str, SpecNode] = {}
        section_nodes: dict[str, SpecNode] = {}
        for kind, code, heading, btext, off in entries:
            page = page_of_offset(text, start + ustart + cbegin + off)
            if kind == "topic":
                if code in topic_nodes:
                    spec.issues.append(
                        f"Unit {num} ({key}): duplicate topic {code!r}; text merged into first"
                    )
                    merged = (topic_nodes[code].text + "\n" + _tidy(btext)).strip()
                    topic_nodes[code].text = merged
                    continue
                node = SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=heading or f"Topic {code}",
                    text=_tidy(LEARN_HEADER_RE.sub("", btext)),
                    page=page,
                )
                topic_nodes[code] = node
                unit.nodes.append(node)
            elif kind == "section":
                fcode = fixed_by_offset[off]
                title, stext = _section_parts(heading, btext)
                node = SpecNode(
                    code=fcode,
                    label=f"{key}-{fcode}",
                    title=title or f"Section {fcode}",
                    text=stext,
                    page=page,
                )
                section_nodes[fcode] = node
                parent = topic_nodes.get(fcode.partition(".")[0])
                if parent is None:
                    spec.issues.append(
                        f"Unit {num} ({key}): section {fcode!r} has no topic parent"
                    )
                    unit.nodes.append(node)
                else:
                    parent.children.append(node)
            else:
                fcode = fixed_by_offset[off]
                body = _tidy(btext)
                # 编号行末尾的 "-" 是 PDF 断词（如 "WAI-" + "ARIA"），直接接回
                join = "" if heading.endswith("-") else "\n"
                full = f"{heading}{join}{body}".strip() if heading else body
                node = SpecNode(
                    code=fcode,
                    label=f"{key}-{fcode}",
                    title=first_sentence(full, limit=200) or f"Point {fcode}",
                    text=full,
                    page=page,
                )
                parent = section_nodes.get(fcode.rpartition(".")[0])
                if parent is None:
                    spec.issues.append(
                        f"Unit {num} ({key}): point {fcode!r} has no section parent"
                    )
                    topic = topic_nodes.get(fcode.partition(".")[0])
                    (topic.children if topic is not None else unit.nodes).append(node)
                else:
                    parent.children.append(node)

        for tcode, tnode in topic_nodes.items():
            if not tnode.children:
                spec.issues.append(
                    f"Unit {num} ({key}): topic {tcode!r} ({tnode.title!r}) has no sections"
                )
        for scode, snode in section_nodes.items():
            if not snode.children:
                spec.issues.append(
                    f"Unit {num} ({key}): section {scode!r} ({snode.title!r}) has no points"
                )

        _note_gaps(list(topic_nodes), spec, f"Unit {num} ({key})")
        _note_gaps(list(section_nodes), spec, f"Unit {num} ({key})")
        _note_gaps(
            [n.code for snode in section_nodes.values() for n in snode.children],
            spec,
            f"Unit {num} ({key})",
        )

        unit.name = _unit_name(level, topic_titles)
        spec.units.append(unit)

    return spec
