"""IAL German (2016, Issue 2) spec 解析器。

结构（内容区 = "German unit content" 起，到 "Assessment information" 止，PDF 页 16-43）：
  Unit N: <name>                 → 单元；unit_key 取自 Appendix 1: Codes 的 "Unit N: WGN0N/01"
    N.1 Unit content             → 单元内容区；节号 N.1 是 spec 印刷编号，作为内容容器节点
      1 <GTA name>               → 一般主题领域（GTA），编号为 spec 印刷编号（Unit 1/2 为 1-4，Unit 4 为 1-7）
      Set topics, literary ...   → Unit 4 的第二张编号表（表标题无编号，赋予分组码 "S"）
        S1 <Geography topic>     → 该表条目；spec 印 "1"，与 GTA "1" 冲突，规范为 "S1"（见 issues）
    N.2 Assessment information / N.3 Assessment criteria → 评估信息与评分标准（mark grids），
      属考评管理而非内容，不产出节点（见 issues）

编号缺陷与限制（均写入 issues，不静默）：
  - Unit 4 的 "Set topics, literary texts and films" 表重新从 1 编号，与 GTA 编号 1-4 冲突；
    条目加分组前缀 S 并保留印刷数字（resolve_code_conflicts 的 `base.k` 兜底会产出 "1.2" 这类编号，
    会被误读为 GTA 1 的第 2 个知识点，故不采用）。
  - GTA 下的 subtopics 在 spec 中是无编号项目符号，不硬编号，保留在所属主题的 text 中。
  - Unit 3 内容为纯散文（议题由学生自选），无编号内容点，仅产出单元内容节点。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    clean_block,
    content_span,
    first_sentence,
    page_of_offset,
    resolve_code_conflicts,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-german"
SUBJECT = "International A Level German (2016)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
# 编号条目行："1 Youth matters"；分隔符限定空格/制表符，避免把跨行页码（"13\nUnit 1: ..."）并进条目
ENTRY_RE = re.compile(r"^(?P<num>\d{1,2})[ \t]+(?P<name>[A-Z][^\n]*)$", re.M)
GROUP_RE = re.compile(r"^Set topics, literary texts and films\s*$", re.M)

# 跨页重复的表格列头（表格结构，不是内容）
TABLE_HEADERS = {"General topic areas (GTAs)", "Subtopics"}
DANGLING_WORDS = {"and", "or", "of", "the", "in", "to", "with", "for", "a", "an"}
# "Set topics, literary texts and films" 表的编号前缀（该表重新从 1 编号）
GROUP_CODE_PREFIX = "S"
# 本项目符号单独占行（PDF 抽取所致），与下一行合并
_BULLET_ONLY_RE = re.compile(r"^[•·▪◦‣\uf0b7]+$")


def _clean(block: str) -> str:
    """clean_block + 去跨页重复的表格列头 + 合并独占一行的项目符号。"""
    lines = [l for l in clean_block(block).splitlines() if l.strip() not in TABLE_HEADERS]
    merged: list[str] = []
    for line in lines:
        if merged and _BULLET_ONLY_RE.match(merged[-1].strip()) and line.strip():
            merged[-1] = f"{merged[-1].strip()} {line.strip()}"
        else:
            merged.append(line)
    out = "\n".join(merged)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _heading(body: str, name: str, limit: int = 160) -> tuple[str, int]:
    """标题行 + 换行续接（如 "5 Technology in the German-speaking" + "world"）。

    返回 (标题, 被并入标题的块前缀字符数)，调用方据此从块文本里去掉续接行。
    """
    title = re.sub(r"\s+", " ", name).strip()
    consumed = 0
    for raw in body.splitlines(keepends=True):
        text = raw.strip()
        if not text:
            consumed += len(raw)
            continue
        if text.startswith("•") or text in TABLE_HEADERS or len(title) >= limit:
            break
        last_word = title.rsplit(" ", 1)[-1].strip(",;:").lower()
        if text[:1].islower() or last_word in DANGLING_WORDS or title.endswith((",", ";")):
            title = f"{title} {text}".strip()
            consumed += len(raw)
        else:
            break
    return re.sub(r"\s+", " ", title).strip(), consumed


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录页与 overview 页的列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _content_region(ubody: str, num: str) -> tuple[str, int]:
    """单元内容区：`N.1 Unit content` 之后，到 `N.2 Assessment information` 或单元末尾。

    返回 (内容文本, 在 ubody 中的起点)。
    """
    sm = re.search(rf"^{re.escape(num)}\.1 Unit content\s*$", ubody, re.M)
    if sm is None:
        return "", 0
    em = re.search(rf"^{re.escape(num)}\.2 Assessment information\s*$", ubody[sm.end():], re.M)
    end = sm.end() + em.start() if em else len(ubody)
    return ubody[sm.end():end], sm.end()


def _entry_nodes(
    part: str,
    base: int,
    key: str,
    text: str,
    codes: list[str],
) -> list[SpecNode]:
    """把一张编号表的条目切成节点；codes 与条目一一对应（已规范化）。"""
    entries = list(ENTRY_RE.finditer(part))
    nodes: list[SpecNode] = []
    for i, (m, code) in enumerate(zip(entries, codes)):
        body_end = entries[i + 1].start() if i + 1 < len(entries) else len(part)
        body = part[m.end():body_end]
        title, consumed = _heading(body, m.group("name"))
        nodes.append(
            SpecNode(
                code=code,
                label=f"{key}-{code}",
                title=title or first_sentence(_clean(body)),
                text=_clean(body[consumed:]),
                page=page_of_offset(text, base + m.start()),
            )
        )
    return nodes


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"German unit content", r"(?m)^Assessment information\s*$")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        num = header.group(1)
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num, "")
        if not key:
            key = f"U{num}"
            spec.issues.append(f"Unit {num}: unit code not found in Appendix 1; unit_key set to {key!r}")

        name, _ = _heading(ubody[header.end() - ustart:], header.group(2))
        unit = SpecUnit(code=num, name=name, unit_key=key)

        content, cbegin = _content_region(ubody, num)
        if not content:
            spec.issues.append(f"Unit {num} ({key}): 'Unit content' section not found")
            spec.units.append(unit)
            continue

        # 单元内容节点（节号 N.1 为 spec 印刷编号）
        sec_code = f"{num}.1"
        sec_node = SpecNode(
            code=sec_code,
            label=f"{key}-{sec_code}",
            title="Unit content",
            text="",
            page=page_of_offset(text, start + ustart + cbegin),
        )
        unit.nodes.append(sec_node)
        page_base = start + ustart + cbegin  # content 在 text 中的起点

        # Unit 4 内容区含第二张编号表（"Set topics, literary texts and films"）
        gm = GROUP_RE.search(content)
        part_a = content[: gm.start()] if gm else content
        part_b = content[gm.start():] if gm else ""

        # 第一张表：GTA，编号即 spec 印刷编号
        entries_a = list(ENTRY_RE.finditer(part_a))
        preamble_end = entries_a[0].start() if entries_a else len(part_a)
        sec_node.text = _clean(part_a[:preamble_end])
        codes_a = [m.group("num") for m in entries_a]

        group_node: Optional[SpecNode] = None
        codes_b: list[str] = []
        if gm:
            entries_b = list(ENTRY_RE.finditer(part_b))
            # 该表从 1 重新编号，与 GTA 编号冲突：加分组前缀 S，保留印刷数字
            for m in entries_b:
                code = f"{GROUP_CODE_PREFIX}{m.group('num')}"
                codes_b.append(code)
                spec.issues.append(
                    f"Unit {num} ({key}): 'Set topics, literary texts and films' item printed "
                    f"{m.group('num')!r} restarts numbering inside section {sec_code} and collides with "
                    f"GTA {m.group('num')!r}; normalized to {code!r}"
                )
            group_node = SpecNode(
                code=GROUP_CODE_PREFIX,
                label=f"{key}-{GROUP_CODE_PREFIX}",
                title=GROUP_RE.search(part_b).group(0).strip(),
                text=_clean(part_b[gm.end(): entries_b[0].start()]) if entries_b else "",
                page=page_of_offset(text, page_base + gm.start()),
            )
            spec.issues.append(
                f"Unit {num} ({key}): group heading 'Set topics, literary texts and films' is "
                f"unnumbered; assigned group code {GROUP_CODE_PREFIX!r} (label {key}-{GROUP_CODE_PREFIX})"
            )

        # 同表内重复/错号由公共规范化逻辑兜底（本 spec 当前无此类缺陷）
        raw_codes = codes_a + codes_b
        fixed = resolve_code_conflicts(
            raw_codes, [None] * len(raw_codes), spec.issues, where=f"Unit {num} section {sec_code}"
        )

        for node in _entry_nodes(part_a, page_base, key, text, fixed[: len(codes_a)]):
            sec_node.children.append(node)
        if group_node is not None:
            for node in _entry_nodes(
                part_b, page_base + gm.start(), key, text, fixed[len(codes_a):]
            ):
                group_node.children.append(node)
            sec_node.children.append(group_node)

        if not sec_node.children:
            spec.issues.append(
                f"Unit {num} ({key}): content is unnumbered prose (student-chosen issue); "
                "no numbered content points, unit content kept as a single node"
            )
        else:
            spec.issues.append(
                f"Unit {num} ({key}): subtopic bullets are unnumbered in the spec; "
                "retained in each topic's text (no codes assigned)"
            )
        spec.units.append(unit)

    if spec.units:
        spec.issues.append(
            "'Assessment information' / 'Assessment criteria' sections (N.2/N.3) describe assessment "
            "administration and mark grids, not content; not emitted as nodes"
        )
    return spec
