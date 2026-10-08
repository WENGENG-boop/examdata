"""IAL Mathematics/Further Mathematics/Pure Mathematics (2013, Issue 3) spec 解析器。

结构（正文单元区，页 15-85）：
  Unit <KEY>                      → 单元；unit_key 取 "Summary of assessment requirements"
                                    表的入口码（C12→WMA01, C34→WMA02, F1→WFM01, F2→WFM02,
                                    F3→WFM03, M1→WME01, M2→WME02, M3→WME03, S1→WST01,
                                    S2→WST02, S3→WST03, D1→WDM01）
    <KEY>.1 Unit description      → 单元说明（非内容点，跳过）
    <KEY>.2 Assessment information→ 评估信息（非内容点，跳过）
      N. <topic name>             → 主题（本 spec 最细的印刷编号层级）
        左栏 "What students need to learn" 条目 + 右栏 guidance/example 说明

限制：本 spec 不给单条内容点编号（PDF 左栏条目无编号，全文无 "N.M" 形式编号），
内容树止于主题层，该限制记入 issues。
编号缺陷：S1 主题 4 印作 "4\t Correlation and regression"（缺点号）→ 规范为 "4"。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import clean_block, page_of_offset, slice_content
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-maths"
SUBJECT = "International A Level Mathematics, Further Mathematics and Pure Mathematics (2013)"

# 单元区起点：正文每单元一个 "<KEY>.1 Unit description"（目录页无此串）
UNIT_ANCHOR_RE = re.compile(r"(?m)^[ \t]*([A-Z]\d+)\.1[ \t]+Unit description\b")
# 主题标题："1.\t Algebra and functions"；S1 主题 4 印作 "4\t Correlation and regression"（缺点号）
TOPIC_RE = re.compile(r"(?m)^[ \t]*(\d{1,2})(\.|\t)[ \t]*([A-Z][^\n]*?)[ \t]*$")
# 单元入口码表（"Summary of assessment requirements" 表格）
SUMMARY_START_RE = r"(?m)^[ \t]*Summary of assessment requirements[ \t]*$"
SUMMARY_END_RE = r"(?m)^\*See Appendix 2"
ENTRY_CODE_RE = re.compile(r"^W[A-Z]{2}\d{2}$")
GLOSSARY_RE = re.compile(r"(?m)^[ \t]*Glossary for\b")
# 本 spec 版式的页眉/页脚（common.clean_block 未覆盖的部分）
_FURNITURE_RES = [
    re.compile(r"^Specification\s*[–-]\s*Pearson Edexcel International Advanced (Level|Subsidiary)\b.*$"),
    re.compile(r"^.*[–-]\s*Issue \d+\s*[–-]\s*November \d+\s*© Pearson Education Limited \d+$"),
]


def _unit_key_map(text: str, unit_ids: list[str], issues: list[str]) -> dict[str, str]:
    """从 "Summary of assessment requirements" 表取单元入口码（如 C12→WMA01）。"""
    try:
        region = slice_content(text, SUMMARY_START_RE, SUMMARY_END_RE)
    except ValueError:
        issues.append("unit entry code table not found; unit_key falls back to the unit number")
        return {}
    lines = region.splitlines()
    wanted = set(unit_ids)
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        uid = line.strip()
        if uid not in wanted or uid in out:
            continue
        for cand in lines[i + 1 : i + 8]:
            cand = cand.strip()
            if ENTRY_CODE_RE.fullmatch(cand):
                out[uid] = cand
                break
            if cand in wanted:
                break
    return out


def _unit_header(text: str, unit_id: str, anchor: int) -> tuple[Optional[int], str]:
    """单元首页运行页眉：返回 (offset, 单元名)。

    页眉形如 "Unit C12\t Core Mathematics 12" 或 "Unit F2" + 次行名称；
    offset 同时用作单元区边界（上一单元的正文在此结束）。
    """
    pattern = re.compile(rf"(?m)^Unit {re.escape(unit_id)}(?:[ \t]*(.*))?$")
    last: Optional[re.Match] = None
    for m in pattern.finditer(text, 0, anchor):
        last = m
    if last is None:
        return None, unit_id
    name = (last.group(1) or "").strip()
    if not name:
        for line in text[last.end() : anchor].splitlines()[:3]:
            if line.strip():
                name = line.strip()
                break
    return last.start(), (re.sub(r"\s+", " ", name) or unit_id)


def _fix_topic_codes(
    entries: list[tuple[str, str, str]], issues: list[str], where: str
) -> list[str]:
    """规范主题号：期望按 1..N 顺序；缺点号/重复/错位时修正并记入 issues。"""
    out: list[str] = []
    seen: set[str] = set()
    for idx, (num, sep, title) in enumerate(entries, start=1):
        code = num
        if sep != ".":
            issues.append(
                f"{where}: topic heading {title!r} printed as {num!r} without a full stop; "
                f"normalized to {code!r}"
            )
        if code in seen or code != str(idx):
            fixed = str(idx)
            issues.append(
                f"{where}: topic number {code!r} out of sequence (expected {idx!r}); "
                f"normalized to {fixed!r}"
            )
            code = fixed
        seen.add(code)
        out.append(code)
    return out


def _unit_description(region: str, unit_id: str) -> str:
    """<KEY>.1 Unit description 段落（用于与主题标题核对，如 F3/D1 的印刷错字）。"""
    pattern = re.compile(
        rf"(?m)^[ \t]*{re.escape(unit_id)}\.1[ \t]+Unit description[^\n]*\n"
        rf"(.*?)(?=\n[ \t]*{re.escape(unit_id)}\.2[ \t]+Assessment information)",
        re.S,
    )
    m = pattern.search(region)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _clean_topic(block: str, unit_id: str, name: str) -> str:
    """清块：先剔本 spec 的运行页眉/页脚，再走 common.clean_block。"""
    headers = [
        re.compile(rf"^Unit {re.escape(unit_id)}[ \t]*$"),
        re.compile(rf"^Unit {re.escape(unit_id)}[ \t]+{re.escape(name)}$"),
        re.compile(rf"^{re.escape(name)}[ \t]*$"),
        re.compile(rf"^{re.escape(name)}[ \t]+Unit {re.escape(unit_id)}$"),
    ]
    lines: list[str] = []
    for raw in block.splitlines():
        line = raw.replace("\u00a0", " ").strip()
        if line and (any(rx.match(line) for rx in _FURNITURE_RES) or any(rx.match(line) for rx in headers)):
            continue
        lines.append(raw.replace("\u00a0", " ").rstrip())
    return clean_block("\n".join(lines))


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    anchors = [(m.start(), m.group(1)) for m in UNIT_ANCHOR_RE.finditer(text)]
    if not anchors:
        raise ValueError("no '<unit>.1 Unit description' anchors found")
    keys = _unit_key_map(text, [uid for _, uid in anchors], spec.issues)
    # 单元区边界取运行页眉 "Unit <KEY>"：下一个单元首页的标题块（单元名/评估类型）不属于上一单元
    bounds = []
    for astart, uid in anchors:
        hoff, hname = _unit_header(text, uid, astart)
        bounds.append((hoff if hoff is not None else astart, uid, hname))
    spec.issues.append(
        "spec prints unit content as unnumbered 'What students need to learn' statements "
        "(no N.M codes anywhere in the PDF); content tree stops at topic level"
    )

    for i, (bstart, uid, name) in enumerate(bounds):
        bend = bounds[i + 1][0] if i + 1 < len(bounds) else len(text)
        key = keys.get(uid, uid)
        if key == uid:
            spec.issues.append(
                f"Unit {uid}: unit entry code not found in the codes table; "
                f"unit_key falls back to {uid!r}"
            )
        unit = SpecUnit(code=uid, name=name, unit_key=key)

        region = text[bstart:bend]
        first_topics = list(TOPIC_RE.finditer(region))
        if not first_topics:
            spec.issues.append(f"Unit {uid} ({key}): no numbered topics found")
            spec.units.append(unit)
            continue
        cstart = first_topics[0].start()
        cend = len(region)
        glossary = GLOSSARY_RE.search(region, cstart)
        if glossary:
            cend = glossary.start()
            spec.issues.append(
                f"Unit {uid} ({key}): 'Glossary for {uid}' section (unnumbered definitions) "
                f"excluded from unit content"
            )
        content = region[cstart:cend]
        topics = list(TOPIC_RE.finditer(content))
        entries = [(m.group(1), m.group(2), m.group(3).strip()) for m in topics]
        codes = _fix_topic_codes(entries, spec.issues, f"Unit {uid} ({key})")
        for j, m in enumerate(topics):
            body_end = topics[j + 1].start() if j + 1 < len(topics) else len(content)
            unit.nodes.append(
                SpecNode(
                    code=codes[j],
                    label=f"{key}-{codes[j]}",
                    title=re.sub(r"\s+", " ", m.group(3)).strip(),
                    text=_clean_topic(content[m.end() : body_end], uid, name),
                    page=page_of_offset(text, bstart + cstart + m.start()),
                )
            )
        # 与 <KEY>.1 Unit description 的提纲核对：标题不在其中说明单元内容与提纲措辞不一致（如印刷错字）
        description = _unit_description(region, uid).lower()
        if description:
            for node in unit.nodes:
                if node.title.lower() not in description:
                    spec.issues.append(
                        f"Unit {uid} ({key}): topic {node.code} title {node.title!r} "
                        f"does not appear in the unit description; kept as printed"
                    )
        spec.units.append(unit)

    return spec