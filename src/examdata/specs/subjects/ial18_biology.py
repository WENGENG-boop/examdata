"""IAL Biology (2018, Issue 2) spec 解析器。

结构（页 13-43 内容区）：
  Unit N: <name>            → 单元；unit_key 取自附录 "Unit N: WBI1N/01"
    Topic M – <name>        → 主题（编号 1-8 全局连续）
      M.K <text...>         → 编号知识点；块文本含说明/guidance，供标注用
单元 3/6 为实践技能单元，spec 用无编号小节描述可评估技能；按印刷小节
（Planning / Implementation and measurements / Processing results / Analysis）
产出小节级节点，code 取小节短名（planning / implementation / processing / analysis），
spec 未印编号故不伪造编号，差异记入 issues。
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

SLUG = "ial18-biology"
SUBJECT = "International A Level Biology (2018)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
TOPIC_RE = re.compile(r"^Topic (\d+) [–-] (.+)$", re.M)
POINT_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s*$", re.M)

# 单元标题换行续接的停止词：遇到这些行说明标题已结束
_SECTION_STOP_RE = re.compile(
    r"^(IAS|IA2|Externally assessed|Unit description|Introduction|Practical|Mathematical|"
    r"Assessment information|Topic \d)"
)
_DANGLING_WORDS = {"and", "or", "of", "the", "in", "to", "with", "for"}

# 实践技能单元（3/6）：spec 用无编号小节描述可评估技能；按印刷小节标题取节点，
# code 用稳定短名（spec 未印编号，不伪造编号）。
_PRACTICAL_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Planning", "planning"),
    ("Implementation and measurements", "implementation"),
    ("Processing results", "processing"),
    ("Analysis", "analysis"),
)


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _full_name(region: str, m: re.Match) -> str:
    """合并单元标题的换行续接（如 "Unit 5: Respiration, Internal Environment," + "Coordination ..."）。"""
    name = m.group(2).strip()
    for line in region[m.end() :].lstrip("\r\n").splitlines()[:4]:
        line = line.strip()
        if not line or _SECTION_STOP_RE.match(line):
            break
        last_word = name.rsplit(" ", 1)[-1].strip(",").lower()
        if name.endswith(",") or last_word in _DANGLING_WORDS or line[:1].islower():
            name = f"{name} {line}".strip()
            if len(name) > 140:
                break
        else:
            break
    return name


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录页列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _practical_nodes(
    spec: ParsedSpec,
    unit: SpecUnit,
    num: str,
    ubody: str,
    *,
    full_text: str,
    body_offset: int,
    key: str,
) -> bool:
    """实践技能单元：按印刷小节产出小节级节点；返回是否产出。"""
    lines = ubody.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    found: list[tuple[int, str, str]] = []
    for title, code in _PRACTICAL_SECTIONS:
        for i, line in enumerate(lines):
            stripped = line.strip()
            ok = stripped == title
            if not ok and title == "Implementation and measurements":
                # PDF 文本层可能把标题拆成两行
                ok = stripped == "Implementation and" and any(
                    lines[j].strip() == "measurements"
                    for j in range(i + 1, min(i + 3, len(lines)))
                )
            if ok:
                found.append((starts[i], title, code))
                break
    if not found:
        return False
    found.sort(key=lambda x: x[0])
    for i, (off, title, code) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(ubody)
        block = ubody[off:end]
        cut = block.find("\nAssessment information")
        if cut != -1:
            block = block[:cut]
        unit.nodes.append(
            SpecNode(
                code=code,
                label=f"{key}-{code}",
                title=title,
                text=clean_block(block),
                page=page_of_offset(full_text, body_offset + off),
            )
        )
    spec.issues.append(
        f"Unit {num} ({key}): practical skills unit has no numbered content points; "
        f"produced {len(found)} section-level node(s) from the printed assessment "
        f"sections ({', '.join(t for _o, t, _c in found)}) with descriptive codes"
    )
    return True


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"Biology content", r"Assessment requirements")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        num = header.group(1)
        name = _full_name(region, header)
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, f"U{num}")

        markers: list[tuple[int, str, str, str]] = []
        for tm in TOPIC_RE.finditer(ubody):
            markers.append((tm.start(), "topic", tm.group(1), tm.group(2).strip()))
        for pm in POINT_RE.finditer(ubody):
            markers.append((pm.start(), "point", pm.group(1), ""))
        markers.sort(key=lambda x: x[0])
        entries = marker_blocks(ubody, markers)

        points = [e for e in entries if e[0] == "point"]
        topic_seq: list[Optional[str]] = []
        cur: Optional[str] = None
        for kind, code, _h, _t, _o in entries:
            if kind == "topic":
                cur = code
            else:
                topic_seq.append(cur)
        fixed = resolve_code_conflicts(
            [e[1] for e in points], topic_seq, spec.issues, where=f"Unit {num}"
        )
        fixed_by_offset = {e[4]: f for e, f in zip(points, fixed)}

        unit = SpecUnit(code=num, name=name, unit_key=key)
        topic_nodes: dict[str, SpecNode] = {}
        for kind, code, heading, btext, off in entries:
            page = page_of_offset(text, start + ustart + off)
            if kind == "topic":
                node = SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=heading or f"Topic {code}",
                    text=clean_block(btext),
                    page=page,
                )
                topic_nodes[code] = node
                unit.nodes.append(node)
            else:
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
                    spec.issues.append(f"Unit {num}: point {fcode!r} has no topic parent")
                    unit.nodes.append(node)

        if not unit.nodes:
            produced = _practical_nodes(
                spec,
                unit,
                num,
                ubody,
                full_text=text,
                body_offset=start + ustart,
                key=key,
            )
            if not produced:
                spec.issues.append(
                    f"Unit {num} ({key}): practical skills unit has no numbered content points"
                )
        spec.units.append(unit)

    return spec
