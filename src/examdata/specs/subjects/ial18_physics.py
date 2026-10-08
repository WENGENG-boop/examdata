"""IAL Physics (2018, Issue 3) spec 解析器。

结构（内容区页 12-41，6 个单元）：
  Unit N: <name>              → 单元；unit_key 取自附录 1 "Unit N: WPH1N/01"
    N.M <name>                → 主题（内容节）
      K <text...>             → 编号知识点；K 为 spec 全篇连续编号（1-171），
                                块文本保留 guidance / CORE PRACTICAL 说明，供标注用

约定与限制：
  - 知识点跨主题、跨单元连续编号（1..171），故 code 用 spec 上印的裸编号（"1"、"171"），
    label 形如 "WPH11-1"；编号连续性由本模块的序列检查保证，重复/缺号会写入 issues
    （本 spec 实测连续无缺号），resolve_code_conflicts 作兜底去重。
  - "N.1 Unit description" / "N.2 Assessment information" 为行政节，不产出节点（记入 issues）。
  - 单元 3/6 为实践技能单元，主题 3.3-3.5 / 6.3-6.5 只有项目符号要点、spec 上无编号；
    不硬编号，只产出主题级节点（要点保留在 text 内），并记入 issues。
  - 知识点 25、29 的 a/b 分条为缩进子条，保留在点文本内、不另立节点（记入 issues）。
  - PDF 文本层把公式抽成竖排碎片（如 "as u v at ..."），块文本按原文保留，不做重排。
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
    title_from_block,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial18-physics"
SUBJECT = "International A Level Physics (2018)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (WPH\d{2})/\d+\s*$", re.M)
SECTION_RE = re.compile(r"^(\d)\.(\d{1,2})\s+(\S.*)$", re.M)
ANCHOR_RE = re.compile(r"Candidates\s+will be assessed on their ability to:")
_POINT_LINE_RE = re.compile(r"\d{1,3} *")
_PAGE_HEADER_RE = re.compile(
    r"^(Specification\s*[–-]\s*Issue|Pearson Edexcel International Advanced)"
)
_PROSE_RE = re.compile(r"[A-Za-z]{2,}")
_NAME_STOP_RE = re.compile(
    r"^(IAS|IA2|Externally assessed|Introduction|Practical|Mathematical|Assessment information)"
)
_ADMIN_SECTIONS = {"Unit description", "Assessment information"}


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录/Units 列表页）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _full_name(region: str, m: re.Match) -> str:
    """合并单元标题的换行续接（如 "Unit 5: Thermodynamics, Radiation, Oscillations" + "and Cosmology"）。"""
    name = m.group(2).strip()
    for line in region[m.end() :].lstrip("\r\n").splitlines()[:3]:
        line = line.strip()
        if not line or _NAME_STOP_RE.match(line):
            break
        if line[:1].islower() or name.endswith(","):
            name = f"{name} {line}"
        else:
            break
    return re.sub(r"\s+", " ", name).strip()


def _is_prose(line: str) -> bool:
    return " " in line and bool(_PROSE_RE.search(line))


def _point_candidates(sbody: str, from_off: int) -> list[tuple[int, int]]:
    """锚点之后的编号行候选：[(在 sbody 中的 offset, 数值), ...]。

    过滤两类误报：页眉后的页码（前一行是页眉），以及公式竖排碎片
    （下一行不是成句文本）。
    """
    tail = sbody[from_off:]
    lines = tail.split("\n")
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    out: list[tuple[int, int]] = []
    for k, line in enumerate(lines):
        if not _POINT_LINE_RE.fullmatch(line):
            continue
        prev = next((lines[x].strip() for x in range(k - 1, -1, -1) if lines[x].strip()), "")
        nxt = next((lines[x].strip() for x in range(k + 1, len(lines)) if lines[x].strip()), "")
        if _PAGE_HEADER_RE.match(prev):
            continue
        if not _is_prose(nxt):
            continue
        out.append((from_off + starts[k], int(line.strip())))
    return out


def _sequence_points(
    cands: list[tuple[int, int]], expected: int
) -> tuple[list[tuple[int, str]], list[int]]:
    """按连续序列筛编号行：只接受 == expected 的，返回 (接受项, 跳过的数值)。"""
    accepted: list[tuple[int, str]] = []
    skipped: list[int] = []
    for off, val in cands:
        if val == expected:
            accepted.append((off, str(val)))
            expected = val + 1
        else:
            skipped.append(val)
    return accepted, skipped


def _sub_item_letters(block: str) -> list[str]:
    """点文本以 a/b/c 分条开头时返回字母序列（如 ["a", "b"]），否则空。"""
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines or not re.match(r"^a\s+\S", lines[0]):
        return []
    letters: list[str] = []
    for line in lines:
        m = re.match(r"^([a-d])\s+\S", line)
        if m and m.group(1) == "abcd"[len(letters)]:
            letters.append(m.group(1))
    return letters if len(letters) >= 2 else []


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"Physics content", r"(?m)^Assessment information")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    next_point = 1  # 知识点编号全篇连续
    for i, header in enumerate(headers):
        num = header.group(1)
        name = _full_name(region, header)
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, f"U{num}")
        if num not in keys:
            spec.issues.append(
                f"Unit {num}: entry code not found in Appendix 1; using fallback key {key!r}"
            )

        unit = SpecUnit(code=num, name=name, unit_key=key)
        sections = list(SECTION_RE.finditer(ubody))
        markers: list[tuple[int, str, str, str]] = []
        admin_codes: list[str] = []
        for j, sec in enumerate(sections):
            sec_code = f"{sec.group(1)}.{sec.group(2)}"
            sec_name = re.sub(r"\s+", " ", sec.group(3)).strip()
            sstart = sec.start()
            send = sections[j + 1].start() if j + 1 < len(sections) else len(ubody)
            sbody = ubody[sstart:send]
            if sec_name in _ADMIN_SECTIONS:
                markers.append((sstart, "admin", sec_code, sec_name))
                admin_codes.append(sec_code)
                continue

            accepted: list[tuple[int, str]] = []
            anchor = ANCHOR_RE.search(sbody)
            if anchor:
                cands = _point_candidates(sbody, anchor.end())
                accepted, skipped = _sequence_points(cands, next_point)
                if not accepted and cands:
                    spec.issues.append(
                        f"Unit {num}: section {sec_code} point numbering does not continue from "
                        f"{next_point} (first detected {cands[0][1]}); printed numbers kept as-is"
                    )
                    accepted, skipped = _sequence_points(cands, cands[0][1])
                if skipped:
                    spec.issues.append(
                        f"Unit {num}: ignored {len(skipped)} number-like line(s) off the point "
                        f"sequence (equation/PDF text-layer artifacts): "
                        + ", ".join(str(v) for v in skipped)
                    )
                if accepted:
                    next_point = int(accepted[-1][1]) + 1
            markers.append((sstart, "topic", sec_code, sec_name))
            for off, code in accepted:
                markers.append((sstart + off, "point", code, ""))
            if not accepted:
                spec.issues.append(
                    f"Unit {num}: section {sec_code} ({sec_name!r}) has no printed point "
                    f"numbering; produced topic-level node only (requirements kept in text)"
                )
        if admin_codes:
            spec.issues.append(
                f"Unit {num}: skipped administrative section(s) {', '.join(admin_codes)} "
                f"(not content topics)"
            )

        markers.sort(key=lambda x: x[0])
        entries = marker_blocks(ubody, markers)

        cur_topic: Optional[SpecNode] = None
        point_nodes: list[SpecNode] = []
        for kind, code, heading, btext, off in entries:
            if kind == "admin":
                continue
            page = page_of_offset(text, start + ustart + off)
            block = clean_block(btext)
            if kind == "topic":
                node = SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title=heading or f"Section {code}",
                    text=block,
                    page=page,
                )
                cur_topic = node
                unit.nodes.append(node)
                continue
            node = SpecNode(
                code=code,
                label=f"{key}-{code}",
                title=title_from_block(block) or first_sentence(block) or f"Point {code}",
                text=block,
                page=page,
            )
            point_nodes.append(node)
            letters = _sub_item_letters(block)
            if letters:
                spec.issues.append(
                    f"Unit {num}: point {code} has lettered sub-requirements "
                    f"({', '.join(letters)}) kept inline in the point text"
                )
            if cur_topic is not None:
                cur_topic.children.append(node)
            else:
                spec.issues.append(f"Unit {num}: point {code!r} has no topic parent")
                unit.nodes.append(node)

        fixed = resolve_code_conflicts(
            [n.code for n in point_nodes], [None] * len(point_nodes), spec.issues, where=f"Unit {num}"
        )
        for node, fcode in zip(point_nodes, fixed):
            if fcode != node.code:
                node.code = fcode
                node.label = f"{key}-{fcode}"

        spec.units.append(unit)

    return spec
