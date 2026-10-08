"""Pearson Edexcel International A Level Economics (2018, Issue 2) spec 解析器。

结构（内容区 = 页 15-53，"Economics content" 到 "Assessment information"）：
  Unit N: <name>            → 单元；unit_key 取附录 1 Codes 的 WEC1N/01 → "WEC1N"
    N.3 Unit content        → 单元内容区起点
      N.3.M <topic>         → 主题；跨页的 "(continued)" 标题合并回同一主题
        K <point>           → 编号知识点（spec 在每个主题内从 1 重新编号）
          a) b) c) …        → 保留在知识点 text 内，供后续标注
  N.1 Unit description / N.2 Assessment information 不是内容点，不建节点。

编号处理（全部记入 issues，不静默）：
  - spec 只在主题内印裸编号（1、2、…），跨主题重复，不能直接作为 label 后缀；
    因此 code 取层级全码 "<topic>.<K>"（如 1.3.1.1），label = "{unit_key}-{code}"。
  - 跨页续接（"K <title> (continued)" + 下一页 "(continued)" 主题头）合并到前一个
    知识点，不算重复编号；合并动作记入 issues。
  - 重复编号与缺号由 _unique_codes / 序列检查发现并记录（common.resolve_code_conflicts
    假定两级编号 "主题.次号"，与本 spec 的四级全码不兼容，故在模块内实现等价逻辑）。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import clean_block, content_span, first_sentence, page_of_offset
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial18-economics"
SUBJECT = "International A Level Economics (2018)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+):[ \t]*(\S.*)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+):[ \t]*(W[A-Z0-9]+)/\d+\s*$", re.M)
TOPIC_RE = re.compile(r"^(\d\.3\.\d)[ \t]+(\S.*)$", re.M)
POINT_RE = re.compile(r"^(\d{1,2})[ \t]+(\S.*)$", re.M)
UNIT_CONTENT_RE = re.compile(r"^(\d)\.3[ \t]+Unit content\s*$", re.M)

# 标题续接的停止行：正文起点、编号、字母条目、项目符号、页标记/页码
_STOP_RE = re.compile(r"^(<<<PAGE|What students need to learn|•|[a-z]\)|\d)")
_TABLE_HEADER_RE = re.compile(r"^[ \t]*What students need to learn:?[ \t]*$", re.M)
_CONTINUED_RE = re.compile(r"\(\s*continued\s*\)\s*$")
_CONTINUED_LINE_RE = re.compile(r"^.*\(\s*continued\s*\)[ \t]*$", re.M)
_INLINE_ITEM_RE = re.compile(r"[ \t]+[a-z]\)[ \t]+")


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录/概览页的单元列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _split_inline_item(rest: str) -> tuple[str, int]:
    """标题与首个字母条目印在同一行时（如 "1 Public expenditure a) The …"）切开。

    返回 (标题, 同行条目起点在 rest 中的下标)；无同行条目时为 -1。
    """
    m = _INLINE_ITEM_RE.search(rest)
    if not m:
        return rest.strip(), -1
    return rest[: m.start()].strip(), m.start() + 1


def _take_heading(body: str, start: int, first: str) -> tuple[str, int]:
    """收集换行续接的标题行，返回 (标题, 正文起点 offset)。

    标题行直到出现停止行（正文/编号/条目/页码）为止，最多 6 行。
    """
    parts = [first] if first else []
    pos = start
    if body.startswith("\n", pos):
        pos += 1
    for _ in range(6):
        line_end = body.find("\n", pos)
        if line_end == -1:
            break
        line = body[pos:line_end].strip()
        if not line or _STOP_RE.match(line):
            break
        parts.append(line)
        pos = line_end + 1
    return " ".join(p for p in parts if p).strip(), pos


def _unique_codes(codes: list[str], issues: list[str], *, where: str) -> list[str]:
    """等价于 common.resolve_code_conflicts，适配 "N.3.M.K" 层级全码。

    同一单元内全码重复 → 递增末位直到唯一；每条修正写入 issues。
    """
    out: list[str] = []
    seen: set[str] = set()
    for code in codes:
        fixed = code
        if fixed in seen:
            head, _, tail = fixed.rpartition(".")
            k = int(tail) + 1 if tail.isdigit() else 2
            while f"{head}.{k}" in seen:
                k += 1
            fixed = f"{head}.{k}"
            issues.append(f"{where}: duplicate code {code!r}; normalized to {fixed!r}")
        seen.add(fixed)
        out.append(fixed)
    return out


def _clean_text(text: str, header_re: Optional[re.Pattern] = None) -> str:
    """块文本清理：去内容表重复表头、去本主题续接标题行，再走 clean_block。"""
    if header_re is not None:
        text = header_re.sub("", text)
    text = _CONTINUED_LINE_RE.sub("", text)
    text = _TABLE_HEADER_RE.sub("", text)
    return clean_block(text)


def _scan_points(body: str, issues: list[str], *, where: str) -> list[dict[str, Any]]:
    """在一个主题块内挑出真正的编号知识点。

    返回 [{offset, body_start, number, heading, continued}, …]，offset 相对 body。
    判定规则：
      - 编号 = 上一个编号 + 1 → 新知识点；
      - 编号 = 上一个编号且标题以 "(continued)" 结尾 → 跨页续接，合并进前一个；
      - 其余（正文里以数字开头的行，如 "…in the last 50 years:"）不是知识点，留在原块内。
    """
    accepted: list[dict[str, Any]] = []
    prev = 0
    for m in POINT_RE.finditer(body):
        number = int(m.group(1))
        first, inline_at = _split_inline_item(m.group(2))
        if inline_at >= 0:
            heading = first
            body_start = m.start(2) + inline_at
        else:
            heading, body_start = _take_heading(body, m.end(), first)
        continued = number == prev and bool(_CONTINUED_RE.search(heading))
        if number == prev + 1 or continued:
            accepted.append(
                {
                    "offset": m.start(),
                    "body_start": body_start,
                    "number": number,
                    "heading": heading,
                    "continued": continued,
                }
            )
            if not continued:
                prev = number
        else:
            issues.append(
                f"{where}: ignored stray numbered line {m.group(0).strip()!r} "
                f"inside point {prev!r} (not a learning point)"
            )
    return accepted


def _topic_groups(cbody: str) -> list[tuple[str, list[re.Match]]]:
    """把主题标记按出现顺序分组，同码的 "(continued)" 头并入前一主题。"""
    groups: list[tuple[str, list[re.Match]]] = []
    for tm in TOPIC_RE.finditer(cbody):
        tcode = tm.group(1)
        if groups and groups[-1][0] == tcode:
            groups[-1][1].append(tm)
        else:
            groups.append((tcode, [tm]))
    return groups


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"Economics content", r"(?m)^Assessment information\s*$")
    region = text[start:end]
    keys = _unit_key_map(text)
    if not keys:
        spec.issues.append("unit entry codes not found in Appendix 1: Codes; using 'U<N>'")

    spec.issues.append(
        "learning points are printed as bare numbers inside each N.3.M topic; "
        "codes composed as '<topic>.<K>' (e.g. 1.3.1.1) so labels stay unique"
    )
    spec.issues.append(
        "unit description (N.1) and assessment information (N.2) sections are not "
        "content points; no nodes produced for them"
    )

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        num = header.group(1)
        name = header.group(2).strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, f"U{num}")
        unit = SpecUnit(code=num, name=name, unit_key=key)

        section = None
        for m in UNIT_CONTENT_RE.finditer(ubody):
            section = m
        if section is None:
            spec.issues.append(f"Unit {num} ({key}): 'Unit content' section not found")
            spec.units.append(unit)
            continue
        cbody = ubody[section.end() :]
        cbase = ustart + section.end()

        groups = _topic_groups(cbody)
        if not groups:
            spec.issues.append(f"Unit {num} ({key}): no numbered topics found in Unit content")
        for gi, (tcode, marks) in enumerate(groups):
            where = f"Unit {num} ({key}) {tcode}"
            if tcode.split(".")[0] != num:
                spec.issues.append(
                    f"{where}: topic number does not match Unit {num}; kept as printed"
                )
            raw_title, tbody_start = _take_heading(
                cbody, marks[0].end(), marks[0].group(2).strip()
            )
            title = _CONTINUED_RE.sub("", raw_title).strip()
            tend = groups[gi + 1][1][0].start() if gi + 1 < len(groups) else len(cbody)
            tbody = cbody[tbody_start:tend]
            header_re = re.compile(rf"^{re.escape(tcode)}[ \t].*$", re.M)

            points = _scan_points(tbody, spec.issues, where=where)
            fresh = [p for p in points if not p["continued"]]
            codes = _unique_codes(
                [f"{tcode}.{p['number']}" for p in fresh], spec.issues, where=where
            )
            code_by_offset = {p["offset"]: c for p, c in zip(fresh, codes)}
            numbers = [p["number"] for p in fresh]
            if numbers and numbers != list(range(1, len(numbers) + 1)):
                spec.issues.append(
                    f"{where}: point numbers {numbers} are not 1..{len(numbers)}; "
                    "composed codes keep labels unique"
                )

            topic_text_end = points[0]["offset"] if points else tend
            topic_node = SpecNode(
                code=tcode,
                label=f"{key}-{tcode}",
                title=title or f"Topic {tcode}",
                text=_clean_text(cbody[tbody_start:topic_text_end], header_re),
                page=page_of_offset(text, start + cbase + marks[0].start()),
            )
            unit.nodes.append(topic_node)
            if not points:
                spec.issues.append(f"{where}: topic has no numbered learning points")
                continue

            for idx, p in enumerate(points):
                nxt = points[idx + 1]["offset"] if idx + 1 < len(points) else len(tbody)
                ptext = _clean_text(tbody[p["body_start"] : nxt], header_re)
                page = page_of_offset(text, start + cbase + tbody_start + p["offset"])
                if p["continued"]:
                    prev_node = topic_node.children[-1]
                    prev_node.text = (prev_node.text + "\n" + ptext).strip()
                    spec.issues.append(
                        f"{where}: point {prev_node.code!r} continues on page {page}; "
                        "continuation merged"
                    )
                    continue
                pcode = code_by_offset[p["offset"]]
                topic_node.children.append(
                    SpecNode(
                        code=pcode,
                        label=f"{key}-{pcode}",
                        title=p["heading"] or first_sentence(ptext) or f"Point {pcode}",
                        text=ptext,
                        page=page,
                    )
                )

        spec.units.append(unit)

    return spec
