"""IAL English Language (2015, Issue 4) spec 解析器。

结构（"English Language content" 起，到 "Assessment information" 止）：
  Unit N: <name>            → 单元；unit_key 取附录 1 的入口码 WEN01-WEN04
    N.M <heading>           → 编号知识点（每单元 3 节：Unit description /
                               Assessment information / 内容小节）

本 spec 没有更深的印刷编号：内容小节里的 Learning outcomes、What students
need to learn、Pre-release、Research、Synopticity，以及 Unit 4 的四个
topic area 都是无编号小节，所以不造编号，保留在所属编号块的 text 中，
并把限制写进 issues。概述页把 Unit 4 的入口码印成 WEN04/04（附录 1 为
WEN04/01）、目录把 Unit 2 名称拼成 "Language in Tranisition"，均记入 issues。
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

SLUG = "ial-englang"
SUBJECT = "International A Level English Language (2015)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
SECTION_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s+(.+)$", re.M)
ENTRY_CODE_RE = re.compile(r"\b(WEN\d{2})/(\d{2})\b")
_CONTENT_END_RE = r"(?m)^Assessment information"
_TERMINATORS = (".", ":", "?", "!")


def _unit_key_map(text: str) -> dict[str, str]:
    """附录 1 的单元入口码（同一单元取最后一次出现，附录在正文之后）。"""
    keys: dict[str, str] = {}
    for m in UNIT_CODE_RE.finditer(text):
        keys[m.group(1)] = m.group(2)
    return keys


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过 "English Language content" 前的目录列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _entry_code_issues(text: str, issues: list[str]) -> None:
    """同一单元入口码出现多个序号（概述页 WEN04/04 vs 附录 WEN04/01）时报出来。"""
    seen: dict[str, set[str]] = {}
    for m in ENTRY_CODE_RE.finditer(text):
        seen.setdefault(m.group(1), set()).add(m.group(2))
    for prefix, suffixes in sorted(seen.items()):
        if len(suffixes) > 1:
            issues.append(
                f"entry code {prefix}: spec prints conflicting variants "
                f"{sorted(suffixes)}; unit_key uses {prefix} (Appendix 1)"
            )


def _name_variants(region: str, issues: list[str]) -> None:
    """同一单元标题出现多种写法（目录拼写错误）时报出来。"""
    names: dict[str, set[str]] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        names.setdefault(m.group(1), set()).add(re.sub(r"\s+", " ", m.group(2)).strip())
    for num, variants in sorted(names.items(), key=lambda kv: int(kv[0])):
        if len(variants) > 1:
            issues.append(
                f"Unit {num}: spec prints {len(variants)} name variants "
                f"{sorted(variants)}; used the unit header spelling"
            )


def _looks_like_heading(line: str) -> bool:
    return (
        len(line) <= 45
        and len(line.split()) <= 6
        and not any(ch in line for ch in ".,;:()•●–")
    )


def _subheadings(block: str) -> list[str]:
    """找出块内无编号小节标题（spec 用独立短行排版，前后是句末标点或块首）。

    仅用于在 issues 里说明未建节点的无编号结构，不用于造编号。
    """
    lines = [l.strip() for l in clean_block(block).splitlines()]
    lines = [l for l in lines if l]
    out: list[str] = []
    for i, line in enumerate(lines):
        if not _looks_like_heading(line):
            continue
        if i > 0 and not lines[i - 1].endswith(_TERMINATORS):
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if nxt and _looks_like_heading(nxt):
            continue  # 表格/列表里的短行，不是小节标题
        out.append(line)
    return out


def _numbering_gaps(numbers: list[str], issues: list[str], *, where: str) -> None:
    """编号缺号检查：主号已由 resolve_code_conflicts 归一，这里只报缺号，不改印号。"""
    minors = sorted(int(n.partition(".")[2]) for n in numbers if n.partition(".")[2].isdigit())
    if not minors:
        return
    missing = [k for k in range(1, max(minors) + 1) if k not in minors]
    if missing:
        issues.append(
            f"{where}: printed numbering has gaps {missing}; codes kept as printed"
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
    start, end = content_span(text, r"(?m)^English Language content", _CONTENT_END_RE)
    region = text[start:end]
    keys = _unit_key_map(text)
    _entry_code_issues(text, spec.issues)
    _name_variants(region, spec.issues)

    headers = _last_headers(region)
    unit_nums = [h.group(1) for h in headers]
    max_unit = max((int(n) for n in unit_nums), default=0)
    missing_units = [n for n in range(1, max_unit + 1) if str(n) not in unit_nums]
    if missing_units:
        spec.issues.append(f"spec content region has no unit header for Unit {missing_units}")

    for i, header in enumerate(headers):
        num = header.group(1)
        name = re.sub(r"\s+", " ", header.group(2)).strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]

        key = keys.get(num)
        if not key:
            key = f"U{num}"
            spec.issues.append(
                f"Unit {num}: no entry code in Appendix 1; unit_key fallback {key!r}"
            )

        markers = [
            (m.start(), "section", m.group(1), m.group(2).strip())
            for m in SECTION_RE.finditer(ubody)
        ]
        entries = marker_blocks(ubody, markers)
        fixed = resolve_code_conflicts(
            [e[1] for e in entries], [num] * len(entries), spec.issues, where=f"Unit {num}"
        )
        _numbering_gaps(fixed, spec.issues, where=f"Unit {num}")

        unit = SpecUnit(code=num, name=name, unit_key=key)
        for (_kind, _mcode, heading, btext, off), fcode in zip(entries, fixed):
            page = page_of_offset(text, start + ustart + off)
            block = clean_block(btext)
            node = SpecNode(
                code=fcode,
                label=f"{key}-{fcode}",
                title=heading or first_sentence(block) or f"Section {fcode}",
                text=block,
                page=page,
            )
            unit.nodes.append(node)

        if not unit.nodes:
            spec.issues.append(
                f"Unit {num} ({key}): no printed numbered sections; unit-level content only"
            )
        else:
            # 内容小节 = 无编号小节最多的那一节；只说明限制，不建无编号节点
            content = max(unit.nodes, key=lambda n: len(_subheadings(n.text)))
            subs = _subheadings(content.text)
            if len(subs) >= 2:
                spec.issues.append(
                    f"Unit {num} ({key}): section {content.code} ({content.title}) contains "
                    f"{len(subs)} unnumbered sub-sections ({'; '.join(subs)}); spec prints no "
                    f"codes for them, so they stay in the {content.code} block text"
                )
        spec.units.append(unit)

    return spec
