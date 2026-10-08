"""IAL Chemistry (2018, Issue 1) spec 解析器。

结构（内容区 "Chemistry content" → "Assessment requirements"，页 16-75）：
  Unit N: <name>            → 单元；unit_key 取自 Appendix 1 "Unit N: WCH1N/01"
    Topic M: <name>         → 主题（1-20 全局连续，单元 1/2/4/5 各 5 个）
      MA: <name>            → 子主题标题（3A-3D/4A-4B/8A-8C/9A-9B/10A-10D/12A-12B/15A-15E）
        M.K <text...>       → 编号知识点；块文本含 CORE PRACTICAL、Further suggested
                              practicals、guidance 说明，供后续标注用

单元 3/6 为实践技能单元，spec 无编号内容点（只有 Unit description + 能力表），
按最细可负责层级产出单元级内容节点（code="intro"），限制记入 issues。
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

SLUG = "ial18-chemistry"
SUBJECT = "International A Level Chemistry (2018)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
TOPIC_RE = re.compile(r"^Topic (\d+): (.+)$", re.M)
SUBSECTION_RE = re.compile(r"^(\d{1,2}[A-Z]): (.+)$", re.M)
POINT_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s*$", re.M)

# 标题续接的停止行：遇到这些行说明标题已结束
_STOP_RE = re.compile(
    r"^(IAS|IA2|Externally assessed|Unit description|Unit content|Introduction|Practical|"
    r"Mathematical|Assessment information|Topic \d|\d{1,2}[A-Z]: |\d{1,2}\.\d{1,2}\s*$|"
    r"Students will be|Knowledge of|Related topics|Application of ideas|The question paper|"
    r"Further suggested|CORE PRACTICAL|•)",
    re.M,
)
# 标题行末为这些词 / 下一行以这些词开头时，视为跨行续接
_CONNECTORS = {
    "and", "or", "of", "the", "in", "to", "with", "for", "from", "into", "on", "at", "a", "an", "as",
}

# 实践单元：正文截到 "Assessment information"（其后是考试信息，非内容）
_ASSESSMENT_RE = re.compile(r"^Assessment information", re.M)
_UNIT_DESCRIPTION_RE = re.compile(r"^Unit description", re.M)


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录/Units 列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _join_heading(
    heading: str, raw_body: str, *, hard: bool
) -> tuple[str, int]:
    """把跨行的标题续接到 heading 上。

    hard=True 用于单元名（一直续接到停止行，如 "Unit 5: Transition Metals and
    Organic Nitrogen" + "Chemistry"）；hard=False 用于主题/子主题标题，只在
    行末逗号、悬空词或下一行以连接词/小写开头时续接。
    返回 (标题, 应从块首丢弃的行数)。
    """
    title = re.sub(r"\s+", " ", heading).strip()
    consumed = 0
    for raw in raw_body.splitlines():
        line = raw.strip()
        if not line:
            if consumed:
                break
            continue
        if _STOP_RE.match(line) or len(title) > 140:
            break
        if not hard:
            last_word = title.rsplit(" ", 1)[-1].strip(",;:").lower()
            first_word = line.split(" ", 1)[0].strip("(").lower()
            if not (
                title.endswith(",")
                or last_word in _CONNECTORS
                or first_word in _CONNECTORS
                or line[:1].islower()
            ):
                break
        title = f"{title} {line}"
        consumed += 1
    return re.sub(r"\s+", " ", title).strip(), consumed


def _drop_leading_lines(raw: str, count: int) -> str:
    """丢弃块首被标题续接吃掉的前 count 个非空行。"""
    if count <= 0:
        return raw
    lines = raw.splitlines()
    dropped = 0
    i = 0
    while i < len(lines) and dropped < count:
        if lines[i].strip():
            dropped += 1
        i += 1
    return "\n".join(lines[i:])


def _clean(text: str) -> str:
    """块文本清理：去页眉页脚/页标记，保留 spec 原文（含 guidance 说明）。"""
    return clean_block(text)


def _practical_unit_node(
    spec: ParsedSpec,
    unit: SpecUnit,
    num: str,
    body: str,
    *,
    full_text: str,
    body_offset: int,
) -> None:
    """实践技能单元：无编号内容点，产出单元级内容节点（code='intro'）。"""
    m = _UNIT_DESCRIPTION_RE.search(body)
    node_start = m.start() if m else 0
    text = body[node_start:]
    end = _ASSESSMENT_RE.search(text)
    if end:
        text = text[: end.start()]
    cleaned = _clean(text)
    # 标题取正文首句，跳过 "Unit description / Introduction" 这类栏目名
    lead = re.sub(r"^(Unit description\s*)?(Introduction\s*)?", "", cleaned)
    node = SpecNode(
        code="intro",
        label=f"{unit.unit_key}-intro",
        title=first_sentence(lead) or f"Unit {num} practical skills",
        text=cleaned,
        page=page_of_offset(full_text, body_offset + node_start),
    )
    unit.nodes.append(node)
    spec.issues.append(
        f"Unit {num} ({unit.unit_key}): practical skills unit has no numbered content "
        f"points; produced one unit-level content node (code='intro') from the unit "
        f"description and assessed-abilities table"
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
    start, end = content_span(text, r"Chemistry content", r"Assessment requirements")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        num = header.group(1)
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        name, _ = _join_heading(header.group(2), ubody[header.end() - ustart:], hard=True)
        key = keys.get(num, f"U{num}")
        unit = SpecUnit(code=num, name=name, unit_key=key)

        markers: list[tuple[int, str, str, str]] = []
        for tm in TOPIC_RE.finditer(ubody):
            markers.append((tm.start(), "topic", tm.group(1), tm.group(2)))
        for sm in SUBSECTION_RE.finditer(ubody):
            markers.append((sm.start(), "section", sm.group(1), sm.group(2)))
        for pm in POINT_RE.finditer(ubody):
            markers.append((pm.start(), "point", pm.group(1), ""))
        markers.sort(key=lambda x: x[0])
        entries = marker_blocks(ubody, markers)

        prepared: list[tuple[str, str, str, str, int]] = []
        for kind, code, heading, btext, off in entries:
            if kind == "point":
                # 编号知识点：块首即正文，不做标题续接
                prepared.append((kind, code, "", btext, off))
                continue
            title, dropped = _join_heading(heading, btext, hard=False)
            prepared.append((kind, code, title, _drop_leading_lines(btext, dropped), off))

        points = [e for e in prepared if e[0] == "point"]
        topic_seq: list[Optional[str]] = []
        cur: Optional[str] = None
        for kind, mcode, _t, _b, _o in prepared:
            if kind == "topic":
                cur = mcode
            elif kind == "point":
                topic_seq.append(cur)
        fixed = resolve_code_conflicts(
            [e[1] for e in points], topic_seq, spec.issues, where=f"Unit {num}"
        )
        fixed_by_offset = {e[4]: f for e, f in zip(points, fixed)}

        topic_nodes: dict[str, SpecNode] = {}
        section_nodes: dict[str, SpecNode] = {}
        cur_topic: Optional[SpecNode] = None
        cur_section: Optional[SpecNode] = None
        for kind, mcode, title, btext, off in prepared:
            page = page_of_offset(text, start + ustart + off)
            if kind == "topic":
                node = topic_nodes.get(mcode)
                if node is None:
                    node = SpecNode(
                        code=mcode,
                        label=f"{key}-{mcode}",
                        title=title or f"Topic {mcode}",
                        text=_clean(btext),
                        page=page,
                    )
                    topic_nodes[mcode] = node
                    unit.nodes.append(node)
                else:
                    node.text = (node.text + "\n" + _clean(btext)).strip()
                    spec.issues.append(
                        f"Unit {num}: topic {mcode!r} header appears more than once; "
                        f"block texts merged"
                    )
                cur_topic, cur_section = node, None
                continue
            if kind == "section":
                node = section_nodes.get(mcode)
                if node is None:
                    node = SpecNode(
                        code=mcode,
                        label=f"{key}-{mcode}",
                        title=title or f"Section {mcode}",
                        text=_clean(btext),
                        page=page,
                    )
                    section_nodes[mcode] = node
                    if cur_topic is not None:
                        cur_topic.children.append(node)
                    else:
                        spec.issues.append(
                            f"Unit {num}: section {mcode!r} has no topic parent"
                        )
                        unit.nodes.append(node)
                else:
                    node.text = (node.text + "\n" + _clean(btext)).strip()
                    spec.issues.append(
                        f"Unit {num}: section {mcode!r} header appears more than once; "
                        f"block texts merged"
                    )
                cur_section = node
                continue

            fcode = fixed_by_offset[off]
            node = SpecNode(
                code=fcode,
                label=f"{key}-{fcode}",
                title=first_sentence(_clean(btext)) or f"Point {fcode}",
                text=_clean(btext),
                page=page,
            )
            parent = cur_section or cur_topic
            if parent is not None:
                parent.children.append(node)
            else:
                spec.issues.append(f"Unit {num}: point {fcode!r} has no topic parent")
                unit.nodes.append(node)

        if not prepared:
            body_start = header.end() - ustart
            _practical_unit_node(
                spec,
                unit,
                num,
                ubody[body_start:],
                full_text=text,
                body_offset=start + ustart + body_start,
            )
        else:
            for tcode, tnode in topic_nodes.items():
                if not tnode.children:
                    spec.issues.append(
                        f"Unit {num}: topic {tcode!r} ({tnode.title!r}) has no content points"
                    )
        spec.units.append(unit)

    trailing = sum(
        1
        for unit in spec.units
        for node in unit.walk()
        if "Further suggested practical" in node.text
    )
    if trailing:
        spec.issues.append(
            f"{trailing} unnumbered 'Further suggested practicals' sections follow the last "
            f"numbered point of their topic; they stay in that point's text because the spec "
            f"prints no code for them"
        )

    return spec
