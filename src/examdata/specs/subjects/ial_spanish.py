"""Pearson Edexcel IAL Spanish (2016, Issue 2) spec 解析器。

结构（页 16-43 内容区，"Spanish unit content" → "Assessment information"）：
  Unit N: <name>                 → 单元；unit_key 取自附录 1 Codes（WSP01-WSP04）
    General topic areas (GTAs)   → 主题：spec 印出编号 1-7 的 GTA（Unit 1/2 为 1-4）
      1 Youth matters            → 主题节点；其下 subtopics 为无编号项目符号，并入 text
    Set topics, literary texts and films（仅 Unit 4）
      1 Geography topic          → 主题节点；编号与同节 GTA 列表冲突，规范为 S1-S4

本 spec 的编号缺陷与结构限制（全部写入 issues，不静默）：
  - Unit 4 的 "Set topics, literary texts and films" 列表编号从 1 重新开始，与同一节
    4.1 的 GTA 列表冲突 → 规范为 S1-S4；
  - Unit 3 内容不规定主题（学生自选议题），最细可负责层级只有内容区 → 产出节点 "3.1"；
  - 各单元 subtopics 为无编号项目符号，不硬编号，保留在所属主题的 text 中；
  - 附录 6 语法表无编号且不隶属任何单元，不产出内容点。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from ..common import clean_block, content_span, page_of_offset
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-spanish"
SUBJECT = "International A Level Spanish (2016)"

_CONTENT_START_RE = r"(?m)^Spanish unit content\s*$"
_CONTENT_END_RE = r"(?m)^Assessment information\s*$"

UNIT_HEADER_RE = re.compile(r"^Unit\s+(\d+)\s*:\s*(\S.*?)\s*$")
UNIT_CODE_RE = re.compile(r"(?m)^Unit\s+(\d+)\s*:\s*(W[A-Z0-9]+)/\d+\s*$")
CONTENT_HEADING_RE = re.compile(r"^(\d+)\.1\s+Unit content\s*$")
ASSESSMENT_HEADING_RE = re.compile(r"^\d+\.2\s+Assessment information\s*$")
ENTRY_RE = re.compile(r"^(\d{1,2})\s+(\S.*)$")

_GTA_HEADER = "General topic areas (GTAs)"
_SUBTOPIC_HEADER = "Subtopics"
_SET_TOPICS_HEADER = "Set topics, literary texts and films"

_PAGE_MARK_RE = re.compile(r"<<<PAGE \d+>>>")
_FURNITURE_RES = (
    re.compile(r"^Pearson Edexcel International (Advanced Subsidiary|Advanced Level).*$"),
    re.compile(r"^Specification\s*[–-]\s*Issue\s+\d+.*$", re.I),
    re.compile(r"^© Pearson Education Limited \d+$"),
    re.compile(r"^Pearson Education Limited \d+$"),
    re.compile(r"^\d{1,3}$"),
)

# 行尾没有句读说明该行是折行，应与下一行合并
_SENTENCE_END = (".", ":", ";", "!", "?", ")", "”", "’", '"')


@dataclass
class _Entry:
    code: str
    title: str
    lines: list[str]
    offset: int


def _is_noise(line: str) -> bool:
    """页眉页脚、页码、页标记、表格栏头等非内容行。"""
    s = line.strip()
    if not s or s in {_GTA_HEADER, _SUBTOPIC_HEADER}:
        return True
    if _PAGE_MARK_RE.fullmatch(s):
        return True
    return any(rx.match(s) for rx in _FURNITURE_RES)


def _lines_with_offsets(region: str, base: int) -> list[tuple[int, str]]:
    """[(绝对 offset, 行文本), ...]，offset 用于回查页码。"""
    out: list[tuple[int, str]] = []
    pos = 0
    for line in region.split("\n"):
        out.append((base + pos, line.rstrip("\r")))
        pos += len(line) + 1
    return out


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _header_indexes(lines: list[tuple[int, str]]) -> list[tuple[str, int]]:
    """[(单元号, 行号), ...]，取每个单元号的最后一次出现（跳过目录页列表）。"""
    last: dict[str, int] = {}
    for idx, (_off, raw) in enumerate(lines):
        m = UNIT_HEADER_RE.match(raw.strip())
        if m:
            last[m.group(1)] = idx
    return sorted(last.items(), key=lambda kv: kv[1])


def _full_name(lines: list[tuple[int, str]], idx: int) -> str:
    """单元名：去掉 "Unit N: " 前缀，并合并换行续接（如 "... written" + "response"）。"""
    header = UNIT_HEADER_RE.match(lines[idx][1].strip())
    name = re.sub(r"\s+", " ", header.group(2)).strip()
    j = idx + 1
    while j < len(lines) and len(name) < 140:
        nxt = lines[j][1].strip()
        if not nxt or not nxt[:1].islower():
            break
        name = f"{name} {nxt}"
        j += 1
    return name


def _unwrap(lines: list[str]) -> str:
    """合并折行：项目符号另起一行，无句读结尾的续行并入上一行。"""
    out: list[str] = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if out and not s.startswith("•") and not out[-1].endswith(_SENTENCE_END):
            out[-1] = f"{out[-1]} {s}"
        else:
            out.append(s)
    return "\n".join(out)


def _parse_entries(
    lines: list[tuple[int, str]], start: int, end: int
) -> list[_Entry]:
    """按 `N <标题>` 切分编号条目；标题折行（下一行小写开头）并入标题。"""
    entries: list[_Entry] = []
    i = start
    while i < end:
        s = lines[i][1].strip()
        m = ENTRY_RE.match(s)
        if _is_noise(s) or not m or s.startswith("•"):
            i += 1
            continue
        entry_off = lines[i][0]
        title = m.group(2).strip()
        i += 1
        while i < end:
            nxt = lines[i][1].strip()
            if _is_noise(nxt) or nxt.startswith("•") or ENTRY_RE.match(nxt):
                break
            if not nxt[:1].islower():
                break
            title = f"{title} {nxt}"
            i += 1
        body: list[str] = []
        while i < end:
            nxt = lines[i][1].strip()
            if _is_noise(nxt):
                i += 1
                continue
            if ENTRY_RE.match(nxt):
                break
            body.append(nxt)
            i += 1
        entries.append(
            _Entry(
                code=m.group(1),
                title=re.sub(r"\s+", " ", title).strip(),
                lines=body,
                offset=entry_off,
            )
        )
    return entries


def _topic_node(unit_key: str, code: str, title: str, body: list[str], page: int) -> SpecNode:
    return SpecNode(
        code=code,
        label=f"{unit_key}-{code}",
        title=title,
        text=_unwrap(body),
        page=page,
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
    start, end = content_span(text, _CONTENT_START_RE, _CONTENT_END_RE)
    region = text[start:end]
    keys = _unit_key_map(text)
    lines = _lines_with_offsets(region, start)

    headers = _header_indexes(lines)
    for pos, (num, hdr_idx) in enumerate(headers):
        next_idx = headers[pos + 1][1] if pos + 1 < len(headers) else len(lines)
        name = _full_name(lines, hdr_idx)
        key = keys.get(num)
        if not key:
            key = f"U{num}"
            spec.issues.append(
                f"Unit {num}: entry code not found in Appendix 1: Codes; unit_key {key!r} used"
            )

        body = lines[hdr_idx:next_idx]
        c_idx = next(
            (i for i, (_o, raw) in enumerate(body) if CONTENT_HEADING_RE.match(raw.strip())),
            None,
        )
        unit = SpecUnit(code=num, name=name, unit_key=key)
        if c_idx is None:
            spec.issues.append(f"Unit {num} ({key}): 'Unit content' heading not found")
            spec.units.append(unit)
            continue

        a_idx = next(
            (
                i
                for i in range(c_idx + 1, len(body))
                if ASSESSMENT_HEADING_RE.match(body[i][1].strip())
            ),
            len(body),
        )
        content = body[c_idx + 1 : a_idx]
        content_num = CONTENT_HEADING_RE.match(body[c_idx][1].strip()).group(1)

        gta_idx = next(
            (i for i, (_o, raw) in enumerate(content) if raw.strip() == _GTA_HEADER), None
        )
        if gta_idx is None:
            # 仅 Unit 级内容（Unit 3：学生自选议题），不硬编号
            code = f"{content_num}.1"
            spec.issues.append(
                f"Unit {num} ({key}): unit content prescribes no topic list (students "
                f"choose their own issue); emitted the content section as node {code!r}"
            )
            unit.nodes.append(
                SpecNode(
                    code=code,
                    label=f"{key}-{code}",
                    title="Unit content",
                    text=clean_block("\n".join(raw for _o, raw in content)),
                    page=page_of_offset(text, body[c_idx][0]),
                )
            )
            spec.units.append(unit)
            continue

        set_idx = next(
            (
                i
                for i in range(gta_idx + 1, len(content))
                if content[i][1].strip() == _SET_TOPICS_HEADER
            ),
            None,
        )
        gta_entries = _parse_entries(
            content, gta_idx + 1, set_idx if set_idx is not None else len(content)
        )
        for entry in gta_entries:
            unit.nodes.append(
                _topic_node(
                    key,
                    entry.code,
                    entry.title,
                    entry.lines,
                    page_of_offset(text, entry.offset),
                )
            )
        if gta_entries:
            spec.issues.append(
                f"Unit {num} ({key}): GTA subtopics are printed as unnumbered bullets; "
                f"kept in the parent topic text, not emitted as coded points"
            )
        else:
            spec.issues.append(f"Unit {num} ({key}): GTA table has no numbered entries")

        if set_idx is not None:
            set_entries = _parse_entries(content, set_idx + 1, len(content))
            for entry in set_entries:
                unit.nodes.append(
                    _topic_node(
                        key,
                        f"S{entry.code}",
                        entry.title,
                        entry.lines,
                        page_of_offset(text, entry.offset),
                    )
                )
            if set_entries:
                spec.issues.append(
                    f"Unit {num} ({key}): 'Set topics, literary texts and films' list "
                    f"restarts numbering at 1, colliding with the GTA list in section "
                    f"{content_num}.1; codes normalized to "
                    f"{', '.join('S' + e.code for e in set_entries)}"
                )
        spec.units.append(unit)

    spec.issues.append(
        "Grammar list (Appendix 6) is unnumbered and outside the unit structure; "
        "not emitted as content points"
    )
    return spec
