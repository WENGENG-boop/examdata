"""IAL Mathematics/Further Mathematics/Pure Mathematics (2019, Issue 3) spec 解析器。

结构（页 12-70 内容区，14 个单元）：
  Unit P1: <name>           → 单元；unit_key 取自附录 "Unit P1: WMA11/01"
    P1.3 Unit content       → 内容区起点（之前是 Unit description/Assessment information）
      N. <topic name>       → 主题；"N. <name> continued" 为同主题跨页续接
        N.M <text...>       → 编号知识点；块文本含 Guidance 列，供标注用

已知 spec 编号缺陷（规范化并记入 issues）：
  - FP2 §7 两个知识点都印成 7.1 → 第二个规范为 7.2；
  - S1 §6 首个知识点印成 5.1 → 规范为 6.1。
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

SLUG = "ial18-mathematics"
SUBJECT = "International A Level Mathematics (2019)"

_UNIT = r"(P1|P2|P3|P4|FP1|FP2|FP3|M1|M2|M3|S1|S2|S3|D1)"
UNIT_HEADER_RE = re.compile(rf"^Unit {_UNIT}: (.+)$", re.M)
UNIT_CODE_RE = re.compile(rf"^Unit {_UNIT}: (W[A-Z0-9]+)/\d+\s*$", re.M)
TOPIC_RE = re.compile(r"^(\d{1,2})\.\s+([A-Z].+)$", re.M)
POINT_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s*$", re.M)
# 内容区终止：Glossary（D1 有）或 Assessment information（单元末尾）
_CONTENT_END_RE = re.compile(r"^Glossary for|^Assessment information", re.M)


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _content_region(ubody: str) -> tuple[str, int]:
    """单元内容区：最后一个 "Unit content" 起，到 Glossary/Assessment 或单元末尾。"""
    hits = [m.start() for m in re.finditer(r"Unit content", ubody)]
    if not hits:
        return "", 0
    begin = hits[-1]
    tail = ubody[begin:]
    end_m = _CONTENT_END_RE.search(tail)
    end = begin + end_m.start() if end_m else len(ubody)
    return ubody[begin:end], begin


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"Mathematics content", r"(?m)^Appendix 1: Codes")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        code = header.group(1)
        name = header.group(2).strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        cbody, cbegin = _content_region(region[ustart:uend])
        key = keys.get(code, code)

        unit = SpecUnit(code=code, name=name, unit_key=key)
        if not cbody:
            spec.issues.append(f"Unit {code}: 'Unit content' section not found")
            spec.units.append(unit)
            continue

        markers: list[tuple[int, str, str, str]] = []
        for tm in TOPIC_RE.finditer(cbody):
            markers.append((tm.start(), "topic", tm.group(1), tm.group(2).strip()))
        for pm in POINT_RE.finditer(cbody):
            markers.append((pm.start(), "point", pm.group(1), ""))
        markers.sort(key=lambda x: x[0])
        entries = marker_blocks(cbody, markers)

        points = [e for e in entries if e[0] == "point"]
        topic_seq: list[Optional[str]] = []
        cur: Optional[str] = None
        for kind, mcode, _h, _t, _o in entries:
            if kind == "topic":
                cur = mcode
            else:
                topic_seq.append(cur)
        fixed = resolve_code_conflicts(
            [e[1] for e in points], topic_seq, spec.issues, where=f"Unit {code}"
        )
        fixed_by_offset = {e[4]: f for e, f in zip(points, fixed)}

        topic_nodes: dict[str, SpecNode] = {}
        for kind, mcode, heading, btext, off in entries:
            page = page_of_offset(text, start + ustart + cbegin + off)
            if kind == "topic":
                title = re.sub(r"\s+continued\s*$", "", heading).strip()
                node = topic_nodes.get(mcode)
                if node is None:
                    node = SpecNode(
                        code=mcode,
                        label=f"{key}-{mcode}",
                        title=title or f"Topic {mcode}",
                        text=clean_block(btext),
                        page=page,
                    )
                    topic_nodes[mcode] = node
                    unit.nodes.append(node)
                else:
                    node.text = (node.text + "\n" + clean_block(btext)).strip()
                continue
            fcode = fixed_by_offset[off]
            node = SpecNode(
                code=fcode,
                label=f"{key}-{fcode}",
                title=first_sentence(clean_block(btext)) or f"Point {fcode}",
                text=clean_block(btext),
                page=page,
            )
            parent = topic_nodes.get(fcode.partition(".")[0])
            if parent is not None:
                parent.children.append(node)
            else:
                spec.issues.append(f"Unit {code}: point {fcode!r} has no topic parent")
                unit.nodes.append(node)

        # 丢弃没有任何知识点的空主题（如误匹配的栏目标题）；有则记录，不静默
        for tcode in list(topic_nodes):
            tnode = topic_nodes[tcode]
            if not tnode.children:
                unit.nodes.remove(tnode)
                spec.issues.append(
                    f"Unit {code}: dropped topic {tcode!r} ({tnode.title!r}) with no points"
                )
        spec.units.append(unit)

    return spec
