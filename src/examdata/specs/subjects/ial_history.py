"""IAL History (2015, Issue 6) spec 解析器。

结构（内容区 = "History content" 起，到 "Assessment requirements" 止，页 17-62）：
  Unit N: <name>            → 单元；unit_key 取自 Appendix 1: Codes 的 "Unit N: WHI0N/01"
    Option 1X: <name>       → 主题（选项），code 用 spec 印刷的选项号 "1A".."1D"
      Overview ...          → 选项说明（含禁止组合提示），作为选项节点的 text
      1X.N <heading>        → 编号知识点（key topic area，spec 印 "1".."5"，标题常跨行）
                              块文本 = 该 area 的项目符号正文，保留供后续标注

编号与限制（均写入 issues，不静默）：
  - 每个选项的 key topic area 都从 1 重新编号，同一单元内四个选项重号；code 取
    "{option}.{n}"（如 "1A.1"），保留印刷数字并与选项号对齐（即编号规范化）。
  - 本 spec 的 key topic area 编号连续、无重号/缺号；resolve_code_conflicts 作兜底。
  - Unit 3 选项 Overview 的五个 "themes that span the period" 同样印成 1-5，与
    key topic area 编号冲突；属说明性内容，保留在选项 text，不单独编号。
  - key topic area 下的 bullet 在 spec 中无编号，保留在该知识点 text 中。
  - 单元级 Unit introduction / Assessment information 无编号，不产出节点。
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

SLUG = "ial-history"
SUBJECT = "International A Level History (2015)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+)$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (WHI\d+)/\d+\s*$", re.M)
OPTION_RE = re.compile(r"^Option (1[A-D]): (.+)$", re.M)
OVERVIEW_RE = re.compile(r"^Overview\s*$", re.M)
LEARN_RE = re.compile(r"^What students need to learn\s*$", re.M)
# 编号知识点行：行首 1-2 位数字 + 空格 + 标题首行（标题续行由后面的 bullet 行界定）
POINT_RE = re.compile(r"^(\d{1,2}) (\S.*)$", re.M)
BULLET_RE = re.compile(r"^[•●]\s*$", re.M)
# 选项体终止：最后一个选项后面紧跟的收尾栏目
_OPTION_END_RE = re.compile(r"^(?:Assessment information|Sample assessment materials)\s*$", re.M)
# 选项 Overview 里出现的编号清单（Unit 3 的 period themes）
OVERVIEW_LIST_RE = re.compile(r"^\d{1,2} \S", re.M)
_UNIT_STOP_RE = re.compile(
    r"^(?:IAS compulsory unit|IA2 compulsory unit|Externally assessed|Unit introduction|"
    r"Assessment information|The options in this unit)"
)


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录页列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _unit_name(name: str, tail: str) -> str:
    """单元名 + 换行续接（Unit 4 标题跨两行）；tail 为标题行之后的文本。"""
    for line in tail.lstrip("\r\n").splitlines()[:3]:
        text = line.strip()
        if not text or _UNIT_STOP_RE.match(text):
            break
        name = f"{name} {text}"
    return re.sub(r"\s+", " ", name).strip()


def _option_name(name: str, tail: str) -> str:
    """选项名 + 换行续接：续行一直取到 "Overview" 行为止。"""
    overview = OVERVIEW_RE.search(tail)
    zone = clean_block(tail[: overview.start()]) if overview else ""
    parts = [name] + [l.strip() for l in zone.splitlines() if l.strip()]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _point_entries(
    tail: str, spec: ParsedSpec, where: str
) -> list[tuple[str, str, int, int]]:
    """取 "What students need to learn" 之后的编号知识点。

    返回 [(印刷编号, 标题, 块起点, 正文起点), ...]。编号行后面必须出现 "•" 行
    才算知识点（否则是 Overview 式清单，留在上一块的 text 里，并记 issue）。
    """
    heads = list(POINT_RE.finditer(tail))
    found: list[tuple[str, str, int, int]] = []
    for i, head in enumerate(heads):
        seg_end = heads[i + 1].start() if i + 1 < len(heads) else len(tail)
        seg = tail[head.end() : seg_end]
        bullet = BULLET_RE.search(seg)
        if bullet is None:
            spec.issues.append(
                f"{where}: numbered line {head.group(1)!r} has no bulleted body; "
                "kept in the previous key topic's text"
            )
            continue
        title = re.sub(
            r"\s+", " ", " ".join([head.group(2)] + seg[: bullet.start()].splitlines())
        ).strip()
        # 正文从该知识点首个 "•" 行起（保留标记行，块文本与 clean_block 结果一致）
        found.append((head.group(1), title, head.start(), head.end() + bullet.start()))
    return found


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    start, end = content_span(text, r"History content", r"(?m)^Assessment requirements\s*$")
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
            spec.issues.append(
                f"Unit {num}: unit code not found in Appendix 1; unit_key set to {key!r}"
            )

        unit = SpecUnit(
            code=num,
            name=_unit_name(header.group(2).strip(), ubody[header.end() - header.start() :]),
            unit_key=key,
        )
        options = list(OPTION_RE.finditer(ubody))
        if not options:
            spec.issues.append(f"Unit {num} ({key}): no options found in the unit content")
            spec.units.append(unit)
            continue

        for j, om in enumerate(options):
            oend = options[j + 1].start() if j + 1 < len(options) else len(ubody)
            obody = ubody[om.start() : oend]
            cut = _OPTION_END_RE.search(obody)
            if cut is not None:
                obody = obody[: cut.start()]
            ocode = om.group(1)
            head_len = om.end() - om.start()  # 选项标题行在 obody 中的结束位置
            obase = start + ustart + om.start()
            where = f"Unit {num} ({key}) option {ocode}"
            opt_node = SpecNode(
                code=ocode,
                label=f"{key}-{ocode}",
                title=_option_name(om.group(2).strip(), obody[head_len:]) or f"Option {ocode}",
                text="",
                page=page_of_offset(text, obase),
            )

            learn = LEARN_RE.search(obody)
            overview = OVERVIEW_RE.search(obody)
            text_start = overview.start() if overview else head_len
            if learn is None:
                spec.issues.append(
                    f"{where}: 'What students need to learn' not found; no numbered key topics"
                )
                opt_node.text = clean_block(obody[text_start:])
                unit.nodes.append(opt_node)
                continue

            opt_text = obody[text_start : learn.start()]
            opt_node.text = clean_block(opt_text)
            if OVERVIEW_LIST_RE.search(opt_text):
                spec.issues.append(
                    f"{where}: overview carries its own numbered list (period themes) that "
                    "collides with the key topic numbering; kept in the option text, "
                    "no codes assigned"
                )

            tail = obody[learn.end() :]
            entries = _point_entries(tail, spec, where=where)
            if not entries:
                spec.issues.append(f"{where}: no numbered key topic areas found")
            fixed = resolve_code_conflicts(
                [f"{ocode}.{cnum}" for cnum, _t, _s, _b in entries],
                [ocode] * len(entries),
                spec.issues,
                where=where,
            )
            for k, (cnum, title, bstart, bstart_body) in enumerate(entries):
                bend = entries[k + 1][2] if k + 1 < len(entries) else len(tail)
                opt_node.children.append(
                    SpecNode(
                        code=fixed[k],
                        label=f"{key}-{fixed[k]}",
                        title=title or f"Key topic {fixed[k]}",
                        text=clean_block(tail[bstart_body:bend]),
                        page=page_of_offset(text, obase + learn.end() + bstart),
                    )
                )
            unit.nodes.append(opt_node)

        spec.issues.append(
            f"Unit {num} ({key}): each option's key topic areas restart at 1; codes "
            "namespaced as '<option>.<n>' (e.g. '1A.1') to stay unique within the unit"
        )
        spec.issues.append(
            f"Unit {num} ({key}): unit introduction and assessment information are "
            "unnumbered; not emitted as nodes"
        )
        spec.units.append(unit)

    spec.issues.append(
        "key topic area bullets are unnumbered in the spec; retained in each key topic's text"
    )
    return spec
