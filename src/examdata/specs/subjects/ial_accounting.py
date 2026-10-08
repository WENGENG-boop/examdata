"""Pearson Edexcel IAL Accounting spec 解析器（该科目有两份 PDF）。

ial-accounting-0（2015/2018 版，Issue 2；节点页码 16-25）：
  Unit N: <name> / "Unit content"           → 单元；unit_key 取附录 "Unit N: WAC1N/01" → WAC1N
    N.M <topic name>                        → 主题（如 "1.1"、"2.9"；标题可能跨行续接）
      <left-column sub-topic heading>       → 左栏分组标题，spec 上无编号，不能作节点
        N.M.K <text...>                     → 编号知识点
  左栏分组标题（如 "Double entry system"）保留在所属主题节点的 text 中（见 issues）。

ial-accounting-1（2013 版，Issue 2；节点页码 18-27）：
  Unit N <name> / "\\tN.3\\t Unit Content"  → 单元；unit_key 取附录 "Unit N: WAC0N" → WAC0N
    N.3.M\\t <topic name>                   → 主题（印出编号 "1.3.1" … "2.3.8"）
      K\\t <left heading>                    → 知识点；spec 只用主题内局部序号（每个主题从 1 重新开始），
                                             规范化为 "<topic>.<K>"（如 "1.3.1.1"），逐单元记入 issues。

单元正文止于下一单元标题行（2015 版 "Unit N: …"、2013 版裸 "Unit N"）：标题页、描述和
评估信息排在 "Unit content" 之前，若截到下一个内容表就会并进本单元最后一个知识点的 text。

编号规范化：两版的编号都比 resolve_code_conflicts 假设的 "{topic}.{minor}" 更深一层
（3 级 / 4 级），直接套用会把 "1.1.3" 误改成 "1.1.1.3"，故在本模块内实现等价逻辑
_normalize_codes：编号前缀与所属主题不符 → 重写为 "<topic>.<末段>"；同一单元内重复 → 递增末段。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    PAGE_MARK_RE,
    clean_block,
    content_span,
    first_sentence,
    marker_blocks,
    normalize_code,
    page_of_offset,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-accounting"
SUBJECT = "International A Level Accounting"

_BULLET_CHARS = "\x84\x07\u2022\u25cf\u25aa"
_UNIT_CODE_RE = re.compile(r"Unit\s+(\d+)\s*:\s*(W[A-Z]{2}\d{2})\b")

# clean_block 未覆盖的页眉页脚变体（如 " – Specification – Issue 2 – …" 前导破折号）
_FURNITURE_RES = (
    re.compile(r"^[–\-—]\s*Specification\s*[–\-—]\s*Issue\s+\d+.*$"),
    re.compile(r"^Specification\s*[–\-—]\s*Issue\s+\d+.*$"),
    re.compile(r"^Pearson Edexcel International.*$"),
    re.compile(r"^© Pearson Education Limited.*$"),
    re.compile(r"^\d{1,3}$"),
    # 2013 版跨页运行页眉（单元名 / 裸单元号）；单元标题行在 "Unit Content" 之前，
    # 不在任何知识点块内，不受影响
    re.compile(r"^The Accounting System and Costing$"),
    re.compile(r"^Corporate and Management Accounting$"),
    re.compile(r"^Unit \d{1,2}$"),
)

# ---------------------------------------------------------------- 2015 版

_UNIT_HEADER_RE = re.compile(r"(?m)^Unit (\d+): (.+)$")
_UNIT_CONTENT_RE = re.compile(r"(?m)^Unit content\s*$")
_TOPIC_RE = re.compile(r"(?m)^(\d{1,2})\.(\d{1,2})\s+(.+)$")
_POINT_RE = re.compile(r"(?m)^(\d{1,2}\.\d{1,2}\.\d{1,2})\s*$")
_CONTENT_END_RE = re.compile(r"(?m)^Assessment information\s*$")
_COL_HEADER = "What students need to learn"

# ---------------------------------------------------------------- 2013 版

_UNIT_CONTENT_2013_RE = re.compile(r"(?m)^\t?(\d{1,2})\.(\d{1,2})\t\s*Unit Content\s*$")
_TOPIC_2013_RE = re.compile(r"(?m)^(\d{1,2})\.(\d{1,2})\.(\d{1,2})\t\s*(.+)$")
_SUBITEM_2013_RE = re.compile(r"(?m)^(\d{1,2})\s*\t\s*(.+)$")
_UNIT_BARE_RE = re.compile(r"(?m)^Unit (\d{1,2})\s*$")


def _is_furniture(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if PAGE_MARK_RE.match(stripped):
        return True
    return any(rx.match(stripped) for rx in _FURNITURE_RES)


def _clean(text: str) -> str:
    """clean_block 后再去残留页眉页脚、bullet 符号；bullet 还原为 "• " 前缀。

    2013 版 bullet 由两行组成（单独一行 bullet 符 + "bullet 符 正文"）；正文折行、
    空行、页眉页脚都不再继承 "• " 前缀（跨页时尤其不能把页眉接成 bullet 正文）。
    """
    out: list[str] = []
    pending_bullet = False
    for raw in clean_block(text).splitlines():
        line = raw.strip()
        if not line or _is_furniture(line):
            pending_bullet = False
            continue
        if line[0] in _BULLET_CHARS:
            rest = line[1:].strip()
            if rest:
                out.append(f"• {rest}")
                pending_bullet = False
            else:
                pending_bullet = True
            continue
        if pending_bullet:
            out.append(f"• {line}")
            pending_bullet = False
            continue
        out.append(line)
    return "\n".join(out)


def _normalize_codes(
    codes: list[str], topic_of: list[Optional[str]], issues: list[str], *, where: str
) -> list[str]:
    """修正编号缺陷（与 resolve_code_conflicts 等价，但支持任意深度编号）。"""
    out: list[str] = []
    seen: set[str] = set()
    for code, topic in zip(codes, topic_of):
        new = normalize_code(code)
        if topic and not new.startswith(f"{topic}."):
            fixed = f"{topic}.{new.rpartition('.')[2]}"
            issues.append(
                f"{where}: code {new!r} does not match its topic {topic!r}; normalized to {fixed!r}"
            )
            new = fixed
        if new in seen:
            head = new.rpartition(".")[0]
            last = new.rpartition(".")[2]
            k = int(last) + 1 if last.isdigit() else 2
            while f"{head}.{k}" in seen:
                k += 1
            fixed = f"{head}.{k}"
            issues.append(f"{where}: duplicate code {new!r}; normalized to {fixed!r}")
            new = fixed
        seen.add(new)
        out.append(new)
    return out


def _line_starts(body: str) -> list[int]:
    starts = [0]
    for m in re.finditer("\n", body):
        starts.append(m.end())
    return starts


def _line_index(starts: list[int], offset: int) -> int:
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= offset:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1


def _label_before(lines: list[str], starts: list[int], idx: int) -> Optional[tuple[int, str]]:
    """判断 point 编号行之前是否为左栏分组标题；是则返回 (起始 offset, 标题文本)。"""
    j = idx - 1
    while j >= 0:
        line = lines[j].strip()
        if line == _COL_HEADER:
            break
        if _is_furniture(line):
            j -= 1
            continue
        if line.endswith("."):
            break
        if _POINT_RE.match(line) or _TOPIC_RE.match(line) or len(line) > 60:
            return None
        j -= 1
    else:
        return None
    seg = [lines[k].strip() for k in range(j + 1, idx) if not _is_furniture(lines[k])]
    if not seg:
        return None
    return starts[j + 1], re.sub(r"\s+", " ", " ".join(seg))


def _topic_title(first: str, lines: list[str], idx: int) -> str:
    """主题标题（不含编号），合并跨行续接（如 "2.9 Information and communication technology (ICT) in"）。"""
    title = re.sub(r"\s+", " ", first.strip())
    j = idx + 1
    while j < len(lines):
        nxt = re.sub(r"\s+", " ", lines[j].strip())
        if not nxt or nxt == _COL_HEADER or _POINT_RE.match(nxt) or _TOPIC_RE.match(nxt):
            break
        if nxt[0].islower() or title.endswith((",", "of", "and", "in", "the", "to")):
            title = f"{title} {nxt}".strip()
            j += 1
            continue
        break
    return title


def _parse_2015(text: str, spec: ParsedSpec) -> None:
    start, end = content_span(text, r"Accounting content", r"(?m)^Appendix 1: Codes")
    region = text[start:end]
    uc_hits = [m.start() for m in _UNIT_CONTENT_RE.finditer(region)]
    if not uc_hits:
        spec.issues.append("2015 spec: no 'Unit content' section found")
        return
    tail = region[uc_hits[-1] :]
    m_end = _CONTENT_END_RE.search(tail)
    content_end = uc_hits[-1] + m_end.start() if m_end else len(region)
    keys = {m.group(1): m.group(2) for m in _UNIT_CODE_RE.finditer(text)}

    # 单元标题行在其 "Unit content" 之前；取每个内容表之前最后一个标题行作为该单元标题
    headers: list[Optional[re.Match]] = []
    for uc_start in uc_hits:
        hm_last = None
        for hm in _UNIT_HEADER_RE.finditer(region, 0, uc_start):
            hm_last = hm
        headers.append(hm_last)

    for u_i, uc_start in enumerate(uc_hits):
        if u_i + 1 < len(uc_hits):
            # 止于下一单元标题行；否则下一单元的标题页/描述/评估信息会并进
            # 本单元最后一个知识点的 text
            nxt = headers[u_i + 1]
            uc_end = nxt.start() if nxt else uc_hits[u_i + 1]
        else:
            uc_end = content_end
        body = region[uc_start:uc_end]
        header = headers[u_i]
        if header is None:
            spec.issues.append(f"2015 spec: no unit header found before offset {uc_start}")
            continue
        num, name = header.group(1), header.group(2).strip()
        key = keys.get(num, "")
        if not key:
            key = f"U{num}"
            spec.issues.append(f"Unit {num}: entry code missing in appendix; using fallback key {key!r}")

        lines = body.split("\n")
        starts = _line_starts(body)
        topics = list(_TOPIC_RE.finditer(body))
        markers: list[tuple[int, str, str, str]] = []
        for t_i, tm in enumerate(topics):
            t_end = topics[t_i + 1].start() if t_i + 1 < len(topics) else len(body)
            markers.append(
                (
                    tm.start(),
                    "topic",
                    f"{tm.group(1)}.{tm.group(2)}",
                    _topic_title(tm.group(3), lines, _line_index(starts, tm.start())),
                )
            )
            for pm in _POINT_RE.finditer(body, tm.start(), t_end):
                label = _label_before(lines, starts, _line_index(starts, pm.start()))
                if label is not None:
                    markers.append((label[0], "label", "", label[1]))
                markers.append((pm.start(), "point", pm.group(1), ""))
        markers.sort(key=lambda item: item[0])
        entries = marker_blocks(body, markers)

        unit = SpecUnit(code=num, name=name, unit_key=key)
        topic_nodes: dict[str, SpecNode] = {}
        topic_labels: dict[str, list[str]] = {}
        cur_topic: Optional[str] = None
        point_codes: list[str] = []
        point_topics: list[Optional[str]] = []
        point_offsets: list[int] = []
        for kind, code, heading, btext, off in entries:
            if kind == "topic":
                node = SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=heading or f"Topic {code}",
                    text="",
                    page=page_of_offset(text, start + uc_start + off),
                )
                topic_nodes[code] = node
                topic_labels[code] = []
                cur_topic = code
                unit.nodes.append(node)
                continue
            if kind == "label":
                if cur_topic is not None:
                    topic_labels[cur_topic].append(_clean(heading))
                continue
            point_codes.append(code)
            point_topics.append(cur_topic)
            point_offsets.append(off)
        fixed = _normalize_codes(point_codes, point_topics, spec.issues, where=f"Unit {num}")
        fixed_by_offset = dict(zip(point_offsets, fixed))

        for kind, code, _heading, btext, off in entries:
            if kind != "point":
                continue
            fcode = fixed_by_offset[off]
            ctext = _clean(btext)
            node = SpecNode(
                code=fcode,
                label=f"{key}-{fcode}",
                title=first_sentence(ctext) or f"Point {fcode}",
                text=ctext,
                page=page_of_offset(text, start + uc_start + off),
            )
            parent = topic_nodes.get(fcode.rpartition(".")[0])
            if parent is None:
                spec.issues.append(f"Unit {num}: point {fcode!r} has no topic parent")
                unit.nodes.append(node)
            else:
                parent.children.append(node)

        for tcode, tnode in list(topic_nodes.items()):
            if not tnode.children:
                unit.nodes.remove(tnode)
                spec.issues.append(
                    f"Unit {num}: dropped topic {tcode!r} ({tnode.title!r}) with no points"
                )
                continue
            tnode.text = "\n".join(label for label in topic_labels[tcode] if label)
        if topic_labels:
            spec.issues.append(
                f"Unit {num} ({key}): left-column sub-topic headings carry no printed codes and are "
                "not nodes; kept in the text of their topic"
            )
        spec.units.append(unit)


# ---------------------------------------------------------------- 2013 版


def _subitem_parts(first_line: str, body: str) -> tuple[str, str]:
    """拆出子知识点标题（编号行 + 续行，到第一个 bullet 为止）与正文。"""
    head = [first_line.strip()]
    content: list[str] = []
    in_head = True
    for raw in body.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if in_head and line[0] not in _BULLET_CHARS:
            head.append(line)
            continue
        in_head = False
        content.append(raw)
    return re.sub(r"\s+", " ", " ".join(head)).strip(), _clean("\n".join(content))


def _unit_name_2013(region: str, num: str, before: int) -> str:
    last: Optional[re.Match] = None
    for m in _UNIT_BARE_RE.finditer(region, 0, before):
        if m.group(1) == num:
            last = m
    if last is None:
        return ""
    for line in region[last.end() :].split("\n")[1:]:
        if line.strip():
            return line.strip()
    return ""


def _parse_2013(text: str, spec: ParsedSpec) -> None:
    start, end = content_span(
        text, r"C\t Accounting unit content", r"(?m)^D\t Assessment"
    )
    region = text[start:end]
    uc_hits = list(_UNIT_CONTENT_2013_RE.finditer(region))
    if not uc_hits:
        spec.issues.append("2013 spec: no 'Unit Content' section found")
        return
    keys = {m.group(1): m.group(2) for m in _UNIT_CODE_RE.finditer(text)}

    for u_i, uc in enumerate(uc_hits):
        num = uc.group(1)
        uc_start = uc.start()
        if u_i + 1 < len(uc_hits):
            # 止于下一单元 "Unit N" 标题行；否则下一单元的标题页/描述会并进
            # 本单元最后一个知识点的 text
            nxt = uc_hits[u_i + 1]
            nxt_num = nxt.group(1)
            m_nxt = None
            for m in _UNIT_BARE_RE.finditer(region, uc_start, nxt.start()):
                if m.group(1) == nxt_num:
                    m_nxt = m
                    break
            uc_end = m_nxt.start() if m_nxt else nxt.start()
        else:
            uc_end = len(region)
        body = region[uc_start:uc_end]
        name = _unit_name_2013(region, num, uc_start)
        if not name:
            spec.issues.append(f"Unit {num}: unit name not found in 2013 spec")
        key = keys.get(num, "")
        if not key:
            key = f"U{num}"
            spec.issues.append(f"Unit {num}: entry code missing in appendix; using fallback key {key!r}")

        topics = list(_TOPIC_2013_RE.finditer(body))
        markers: list[tuple[int, str, str, str]] = []
        for t_i, tm in enumerate(topics):
            t_code = f"{tm.group(1)}.{tm.group(2)}.{tm.group(3)}"
            t_end = topics[t_i + 1].start() if t_i + 1 < len(topics) else len(body)
            markers.append((tm.start(), "topic", t_code, re.sub(r"\s+", " ", tm.group(4)).strip()))
            for sm in _SUBITEM_2013_RE.finditer(body, tm.start(), t_end):
                markers.append((sm.start(), "point", sm.group(1), sm.group(2)))
        markers.sort(key=lambda item: item[0])
        entries = marker_blocks(body, markers)

        unit = SpecUnit(code=num, name=name, unit_key=key)
        topic_nodes: dict[str, SpecNode] = {}
        cur_topic: Optional[str] = None
        point_codes: list[str] = []
        point_topics: list[Optional[str]] = []
        point_offsets: list[int] = []
        for kind, code, _heading, _btext, off in entries:
            if kind == "topic":
                node = SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=_heading or f"Topic {code}",
                    text="",
                    page=page_of_offset(text, start + uc_start + off),
                )
                topic_nodes[code] = node
                cur_topic = code
                unit.nodes.append(node)
                continue
            point_codes.append(f"{cur_topic}.{code}" if cur_topic else code)
            point_topics.append(cur_topic)
            point_offsets.append(off)
        fixed = _normalize_codes(point_codes, point_topics, spec.issues, where=f"Unit {num}")
        fixed_by_offset = dict(zip(point_offsets, fixed))

        for kind, code, heading, btext, off in entries:
            if kind == "topic":
                node = topic_nodes[code]
                node.text = _clean(btext)
                continue
            fcode = fixed_by_offset[off]
            title, ctext = _subitem_parts(heading, btext)
            node = SpecNode(
                code=fcode,
                label=f"{key}-{fcode}",
                title=title or f"Point {fcode}",
                text=ctext,
                page=page_of_offset(text, start + uc_start + off),
            )
            parent = topic_nodes.get(fcode.rpartition(".")[0])
            if parent is None:
                spec.issues.append(f"Unit {num}: point {fcode!r} has no topic parent")
                unit.nodes.append(node)
            else:
                parent.children.append(node)

        for tcode, tnode in list(topic_nodes.items()):
            if not tnode.children:
                unit.nodes.remove(tnode)
                spec.issues.append(
                    f"Unit {num}: dropped topic {tcode!r} ({tnode.title!r}) with no points"
                )
        if point_codes:
            spec.issues.append(
                f"Unit {num} ({key}): content points use per-topic local numbers that restart at 1 "
                "(e.g. '1' under 1.3.1); normalized to '<topic>.<n>'"
            )
        spec.units.append(unit)


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    if "What students need to learn" in text:
        _parse_2015(text, spec)
    elif "Accounting unit content" in text:
        _parse_2013(text, spec)
    else:
        raise ValueError("unrecognized IAL Accounting spec layout")
    return spec
