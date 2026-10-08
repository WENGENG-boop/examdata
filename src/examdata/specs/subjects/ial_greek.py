"""IAL Greek (2016, Issue 4) spec 解析器。

结构（"Greek content" 页 15-34，共 2 个单元）：
  Unit N: <name>          → 单元；unit_key 取自 Appendix 1: Codes（Unit 1: WGK01/01）
    N.M <section name>    → spec 上印的编号节（1.1-1.4、2.1-2.6），文本保留整节内容
      1.3/2.3 内的主题区   → 知识点；spec 只印相对编号（1..7），组合为 N.M.K
                             （组合编号非原样印刷，记入 issues，不静默）

编号缺陷：单元号即节号主号（1.x/2.x），用 resolve_code_conflicts 校验；本 spec 的
1.1-1.4、2.1-2.6 完整且与单元号一致，无重复/错位/缺号。

已知限制（记入 issues）：
  - 1.1/2.1、1.2/2.2、1.4/2.5 是表格，行标签在 spec 上没有编号，不产出子节点；
  - 2.4 的 set topics/texts/films 分组与 2.6 的 straightforward/complex 划分在 spec
    上没有编号，按“不硬编号”处理，保留在节文本中（只能标注到节级）。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    clean_block,
    content_span,
    page_of_offset,
    resolve_code_conflicts,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-greek"
SUBJECT = "International A Level Greek (2016)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
SECTION_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+([A-Z].+)$", re.M)
# 主题区：1.3/2.3 的表格行，spec 只印相对编号（"1 Youth matters"）
TOPIC_AREA_RE = re.compile(r"^(\d{1,2})\s+([A-Z].+)$", re.M)
TOPIC_SECTIONS = frozenset({"1.3", "2.3"})

# 标题换行续接的判定：上一行以这些词结尾，或下一行小写开头，则视为同一标题
_TITLE_STOP_WORDS = {"and", "or", "of", "the", "in", "to", "with", "for", "on", "a", "an"}


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过页 15 的目录列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _take_title_tail(number_title: str, tail: str) -> tuple[str, str]:
    """把编号行之后的换行续接并入标题；返回 (完整标题, 该主题区剩余正文)。"""
    title = number_title
    lines = tail.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines):
        nxt = lines[i].strip()
        if not nxt:
            break
        last = title.rsplit(" ", 1)[-1].strip(",:").lower()
        if not (title.endswith(",") or last in _TITLE_STOP_WORDS or nxt[:1].islower()):
            break
        title = f"{title} {nxt}"
        i += 1
        if len(title) > 140:
            break
    return re.sub(r"\s+", " ", title).strip(), "\n".join(lines[i:])


def _unique_topic_code(code: str, seen: set[str], issues: list[str], where: str) -> str:
    """主题区编号去重：重复时递增最后一段（保留 N.M.K 三段结构）。"""
    if code not in seen:
        seen.add(code)
        return code
    head, _, last = code.rpartition(".")
    k = int(last) + 1 if last.isdigit() else 2
    while f"{head}.{k}" in seen:
        k += 1
    fixed = f"{head}.{k}"
    issues.append(f"{where}: duplicate topic code {code!r}; normalized to {fixed!r}")
    seen.add(fixed)
    return fixed


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"Greek content", r"(?m)^Assessment information")
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_headers(region)
    for i, header in enumerate(headers):
        num = header.group(1)
        name = header.group(2).strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num)
        if not key:
            key = f"UG{num}"
            spec.issues.append(
                f"Unit {num}: no unit code in Appendix 1: Codes; fallback key {key!r} used"
            )

        unit = SpecUnit(code=num, name=name, unit_key=key)

        smarks = list(SECTION_RE.finditer(ubody))
        if not smarks:
            spec.issues.append(f"Unit {num} ({key}): no numbered sections found")
            spec.units.append(unit)
            continue

        fixed = resolve_code_conflicts(
            [f"{m.group(1)}.{m.group(2)}" for m in smarks],
            [num] * len(smarks),
            spec.issues,
            where=f"Unit {num} ({key})",
        )
        topic_seen: set[str] = set()
        for j, m in enumerate(smarks):
            sec_code = fixed[j]
            sec_end = smarks[j + 1].start() if j + 1 < len(smarks) else len(ubody)
            body = ubody[m.end() : sec_end]
            node = SpecNode(
                code=sec_code,
                label=f"{key}-{sec_code}",
                title=re.sub(r"\s+", " ", m.group(3)).strip(),
                text=clean_block(body),
                page=page_of_offset(text, start + ustart + m.start()),
            )
            if sec_code in TOPIC_SECTIONS:
                tmarks = list(TOPIC_AREA_RE.finditer(body))
                if not tmarks:
                    spec.issues.append(
                        f"Unit {num} ({key}): section {sec_code} has no topic areas"
                    )
                for k, tm in enumerate(tmarks):
                    tend = tmarks[k + 1].start() if k + 1 < len(tmarks) else len(body)
                    ttitle, ttail = _take_title_tail(
                        re.sub(r"\s+", " ", tm.group(2)).strip(), body[tm.end() : tend]
                    )
                    tcode = _unique_topic_code(
                        f"{sec_code}.{tm.group(1)}",
                        topic_seen,
                        spec.issues,
                        where=f"Unit {num} ({key})",
                    )
                    node.children.append(
                        SpecNode(
                            code=tcode,
                            label=f"{key}-{tcode}",
                            title=ttitle,
                            text=clean_block(ttail),
                            page=page_of_offset(
                                text, start + ustart + m.end() + tm.start()
                            ),
                        )
                    )
            unit.nodes.append(node)

        topic_secs = [n.code for n in unit.nodes if n.code in TOPIC_SECTIONS and n.children]
        if topic_secs:
            spec.issues.append(
                f"Unit {num} ({key}): topic areas in {', '.join(topic_secs)} are printed "
                "with section-relative numbers on the spec; composed codes N.M.K assigned"
            )
        unnumbered = [n.code for n in unit.nodes if n.code not in TOPIC_SECTIONS]
        if unnumbered:
            spec.issues.append(
                f"Unit {num} ({key}): sections {', '.join(unnumbered)} use unnumbered "
                "tables/lists on the spec; rows kept in the section text, not force-numbered"
            )
        spec.units.append(unit)

    return spec
