"""IAL English Literature (2015, Issue 7) spec 解析器。

结构（PDF 页 17-31 内容区，4 个单元）：
  Unit N: <name>            → 单元；unit_key 取自 Appendix 1: Codes 的 "Unit N: WETNN/01"
    N.M <heading>           → 编号内容块（N.1 Unit description / N.2 Assessment information /
                              N.3 … / N.4 …）；块文本含 Learning outcomes、Key features、
                              What learners need to learn、Texts 等未编号小节，供标注用

spec 只把内容编到 section 层级（N.M），没有更深编号；单元题头下的
"IAS/IA2 compulsory unit"、"Externally assessed" 也没有编号归属，
这些都保留在所属 section 文本里，不另造编号（限制逐单元记入 issues）。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    clean_block,
    content_span,
    marker_blocks,
    page_of_offset,
    resolve_code_conflicts,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-englit"
SUBJECT = "International A Level English Literature (2015)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
SECTION_RE = re.compile(r"^[ \t]*(\d{1,2}\.\d{1,2})[ \t]+([A-Z].+?)[ \t]*$", re.M)


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过 "English Literature content" 目录页列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


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
        text, r"English Literature content", r"(?m)^Assessment information\s*$"
    )
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    if not headers:
        spec.issues.append("no unit headings found in content region")
        return spec

    for i, header in enumerate(headers):
        num = header.group(1)
        name = header.group(2).strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, "")
        if not key:
            key = f"UNIT{num}"
            spec.issues.append(f"Unit {num}: no entry code in Appendix 1: Codes; using {key!r}")

        markers = [
            (m.start(), "section", m.group(1), m.group(2).strip())
            for m in SECTION_RE.finditer(ubody)
        ]
        entries = marker_blocks(ubody, markers)
        head_end = header.end() - ustart
        preamble = clean_block(ubody[head_end : markers[0][0] if markers else len(ubody)])
        fixed = resolve_code_conflicts(
            [e[1] for e in entries], [num] * len(entries), spec.issues, where=f"Unit {num}"
        )

        unit = SpecUnit(code=num, name=name, unit_key=key)
        for (_kind, _code, heading, btext, off), fcode in zip(entries, fixed):
            unit.nodes.append(
                SpecNode(
                    code=fcode,
                    label=f"{key}-{fcode}",
                    title=heading or f"Section {fcode}",
                    text=clean_block(btext),
                    page=page_of_offset(text, start + ustart + off),
                )
            )

        if not unit.nodes:
            spec.issues.append(f"Unit {num} ({key}): no numbered sections found")
        else:
            spec.issues.append(
                f"Unit {num} ({key}): spec numbers content only to section level "
                f"({unit.nodes[0].code}-{unit.nodes[-1].code}); unnumbered sub-headings inside "
                f"sections (e.g. 'Learning outcomes', 'Texts') stay in the enclosing section text"
            )
        if preamble:
            spec.issues.append(
                f"Unit {num} ({key}): unit-level lines {preamble!r} precede the first numbered "
                f"section and are not emitted as nodes"
            )
        spec.units.append(unit)

    return spec
