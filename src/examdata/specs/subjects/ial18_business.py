"""IAL Business (2018, Issue 1) spec 解析器。

结构（内容区 = 页 13 目录 "Business content" 到页 40 "Assessment information"，4 个单元）：
  Unit N: <name>                 → 单元；unit_key 取自附录 1 Codes 的 "Unit N: WBS1N/01"
    N.3.M <topic name>           → 主题；跨页续接的 "<name> (continued)" 合并进同一节点
      k <item heading>           → 知识点；spec 内每个主题重新从 1 编号，可跨续接页连续
        x) <sub-item>            → 子条目；spec 内每个知识点重新从 a) 编号

编号规范化（每条修正写入 issues，不静默）：
  - spec 的编号是主题内相对编号，直接落库会重号，故按印刷路径限定：
    主题码 = 印刷值 "N.3.M"，知识点码 = "N.3.M.k"，子条目码 = "N.3.M.k(x)"；
  - 1.3.3 / 1.3.4 的主题标题在续接页重复印刷（第二次带 "(continued)"）→ 合并为一个节点；
  - 3.3.6 标题印刷为 "Manging change"（Content overview 为 "Managing change"）→ 保留印刷值，
    由 overview 核对自动记 issue。
  - 知识点序号与子条目字母若出现缺号/重号/乱序，按出现位置重排并逐条记 issue
    （common.resolve_code_conflicts 只按带点编号与主题号比对，处理不了本 spec 的相对编号）。

未编号结构：4 个单元均有编号内容点，无需降级到 Unit 级。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    clean_block,
    content_span,
    first_sentence,
    page_of_offset,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial18-business"
SUBJECT = "International A Level Business (2018)"

_CONTENT_START_RE = r"(?m)^Business content[ \t]*$"
_CONTENT_END_RE = r"(?m)^Assessment information[ \t]*$"

UNIT_HEADER_RE = re.compile(r"(?m)^Unit (\d+):[ \t]+(\S.*)$")
UNIT_CODE_RE = re.compile(r"(?m)^Unit (\d+):[ \t]*(W[A-Z0-9]+)/\d+[ \t]*$")
TOPIC_RE = re.compile(r"(?m)^(\d{1,2}\.\d{1,2}\.\d{1,2})[ \t]+(\S.*)$")
ITEM_RE = re.compile(r"(?m)^(\d{1,2})[ \t]+(\S.*)$")
LINE_SUB_RE = re.compile(r"(?m)^([a-z])\)[ \t]*")
INLINE_SUB_RE = re.compile(r"(?<=\S )[a-z]\)")
_CONTINUED_RE = re.compile(r"[ \t]*\(continued\)[ \t]*$")

# clean_block 未覆盖的残留：带前导破折号的版式页脚与表头行
_FOOTER_RE = re.compile(r"^[–-][ \t]*Specification[ \t]*[–-][ \t]*Issue[ \t]+\d+.*$")
_TABLE_HEAD_RE = re.compile(r"^What students need to learn:[ \t]*$")

_CONVENTION_NOTE = (
    "numbering is topic-scoped in this spec (items restart at 1 in every topic, sub-items at a) "
    "in every item); codes are qualified to the printed path: topic 'N.3.M', item 'N.3.M.k', "
    "sub-item 'N.3.M.k(x)'"
)

_OVERVIEW_RE = re.compile(r"(?m)^Content overview[ \t]*$")
_OVERVIEW_END_RE = re.compile(r"(?m)^Assessment overview[ \t]*$")
_ANY_UNIT_RE = re.compile(r"(?m)^Unit (\d+):")


def _overview_topics(text: str) -> dict[str, list[str]]:
    """Qualification at a glance 的 "Content overview" 主题名，按单元号归集（用于核对）。"""
    out: dict[str, list[str]] = {}
    for m in _OVERVIEW_RE.finditer(text):
        units = list(_ANY_UNIT_RE.finditer(text, 0, m.start()))
        if not units:
            continue
        end = _OVERVIEW_END_RE.search(text, m.end())
        seg = text[m.end() : end.start() if end else len(text)]
        bullets = [ln.lstrip("• ").strip() for ln in seg.splitlines() if ln.startswith("•")]
        if bullets:
            out[units[-1].group(1)] = bullets
    return out


def _clean(text: str) -> str:
    """clean_block 之上再剔除版式页脚与表头行。"""
    out: list[str] = []
    for line in clean_block(text).splitlines():
        stripped = line.strip()
        if _FOOTER_RE.match(stripped) or _TABLE_HEAD_RE.match(stripped):
            continue
        out.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录页列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _split_subs(block: str) -> tuple[str, list[tuple[str, int, str]]]:
    """拆出 (heading, [(letter, offset, body), ...])。

    子条目标记通常是行首 "x)"，但当页时首个标记会与知识点标题同行
    （如 "4 Pricing strategies a) Types of pricing strategy:"）。
    """
    line_marks = list(LINE_SUB_RE.finditer(block))
    head_limit = line_marks[0].start() if line_marks else len(block)
    marks: list[tuple[int, int, str]] = []
    inline = INLINE_SUB_RE.search(block[:head_limit])
    if inline:
        marks.append((inline.start(), inline.end(), inline.group(0)[0]))
    marks.extend((m.start(), m.end(), m.group(1)) for m in line_marks)
    marks.sort()
    heading = block[: marks[0][0]] if marks else block
    subs: list[tuple[str, int, str]] = []
    for i, (start, end, letter) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(block)
        subs.append((letter, start, block[end:stop]))
    return heading, subs


def _fix_sequence(raw: list[str], where: str, issues: list[str], *, kind: str) -> list[str]:
    """按出现位置重排编号序列（缺号/重号/乱序都逐条记 issue）。"""
    out: list[str] = []
    seen: set[str] = set()
    for i, value in enumerate(raw):
        expected = str(i + 1) if kind == "item" else chr(ord("a") + i)
        fixed = value
        if value != expected or value in seen:
            fixed = expected
            while fixed in seen:
                fixed = str(int(fixed) + 1) if kind == "item" else chr(ord(fixed) + 1)
            issues.append(
                f"{where}: {kind} number {value!r} out of sequence "
                f"(expected {expected!r}); normalized to {fixed!r}"
            )
        seen.add(fixed)
        out.append(fixed)
    return out


def _check_overview(spec: ParsedSpec, text: str) -> None:
    """用 Content overview 核对单元主题数/主题名（不一致记 issue，不静默）。"""
    overview = _overview_topics(text)
    for unit in spec.units:
        expected = overview.get(unit.code)
        if not expected:
            spec.issues.append(
                f"Unit {unit.code}: no 'Content overview' bullet list found for cross-check"
            )
            continue
        titles = [node.title for node in unit.nodes]
        if len(titles) != len(expected):
            spec.issues.append(
                f"Unit {unit.code}: 'Content overview' lists {len(expected)} topics but "
                f"{len(titles)} were parsed"
            )
        for node, name in zip(unit.nodes, expected):
            if node.title != name:
                spec.issues.append(
                    f"Unit {unit.code}: topic {node.code!r} title {node.title!r} differs from "
                    f"the 'Content overview' entry {name!r}; printed value kept"
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
    spec.issues.append(_CONVENTION_NOTE)

    start, end = content_span(text, _CONTENT_START_RE, _CONTENT_END_RE)
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        num = header.group(1)
        name = header.group(2).strip()
        key = keys.get(num)
        if not key:
            key = f"U{num}"
            spec.issues.append(
                f"Unit {num}: no entry code in Appendix 1: Codes; unit_key falls back to {key!r}"
            )
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]

        order: list[str] = []
        segs: dict[str, list[tuple[str, str, int]]] = {}
        topic_marks = list(TOPIC_RE.finditer(ubody))
        for j, tm in enumerate(topic_marks):
            tcode = tm.group(1)
            tname = _CONTINUED_RE.sub("", tm.group(2)).strip()
            tstop = topic_marks[j + 1].start() if j + 1 < len(topic_marks) else len(ubody)
            tseg = ubody[tm.end() : tstop]
            if tcode not in segs:
                order.append(tcode)
                segs[tcode] = []
                if tcode.split(".")[0] != num:
                    spec.issues.append(
                        f"Unit {num}: topic {tcode!r} does not match the unit number; "
                        f"kept in Unit {num}"
                    )
            else:
                spec.issues.append(
                    f"Unit {num}: topic {tcode!r} printed again on a continuation page "
                    f"({tname!r}); merged into the first node"
                )
            segs[tcode].append((tname, tseg, tm.start()))

        unit = SpecUnit(code=num, name=name, unit_key=key)
        for tcode in order:
            parts = segs[tcode]
            node = SpecNode(
                code=tcode,
                label=f"{key}-{tcode}",
                title=parts[0][0] or f"Topic {tcode}",
                text="",
                page=page_of_offset(text, start + ustart + parts[0][2]),
            )
            unit.nodes.append(node)

            items: list[tuple[str, str, int]] = []
            for _tname, tseg, toff in parts:
                node.text = "\n".join(p for p in (node.text, _clean(tseg)) if p)
                marks = list(ITEM_RE.finditer(tseg))
                for k, im in enumerate(marks):
                    stop = marks[k + 1].start() if k + 1 < len(marks) else len(tseg)
                    # 块从编号行本身开始（标题可能续行，或与首个 a) 同行）
                    body = re.sub(r"^\d{1,2}[ \t]+", "", tseg[im.start() : stop])
                    items.append((im.group(1), body, toff + im.start()))

            where = f"Unit {num} topic {tcode}"
            item_codes = _fix_sequence(
                [raw for raw, _b, _o in items], where, spec.issues, kind="item"
            )
            for (_raw, ibody, ioff), iseq in zip(items, item_codes):
                icode = f"{tcode}.{iseq}"
                heading, subs = _split_subs(ibody)
                item_node = SpecNode(
                    code=icode,
                    label=f"{key}-{icode}",
                    title=_flat(heading) or first_sentence(_clean(ibody)) or f"Item {icode}",
                    text=_clean(ibody),
                    page=page_of_offset(text, start + ustart + ioff),
                )
                node.children.append(item_node)

                letters = _fix_sequence(
                    [letter for letter, _o, _b in subs],
                    f"{where} item {iseq}",
                    spec.issues,
                    kind="sub",
                )
                for (letter, soff, sbody), sseq in zip(subs, letters):
                    scode = f"{icode}({sseq})"
                    item_node.children.append(
                        SpecNode(
                            code=scode,
                            label=f"{key}-{scode}",
                            title=first_sentence(_clean(sbody)) or f"Sub-item {scode}",
                            text=_clean(sbody),
                            page=page_of_offset(text, start + ustart + ioff + soff),
                        )
                    )

        if not unit.nodes:
            spec.issues.append(f"Unit {num} ({key}): no numbered content points found")
        spec.units.append(unit)

    _check_overview(spec, text)
    return spec
