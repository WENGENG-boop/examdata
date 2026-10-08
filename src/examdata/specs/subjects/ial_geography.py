"""IAL Geography (2016, Issue 3) spec 解析器。

结构（页 14-66 内容区，4 个单元）：
  Unit N: <name>                 → 单元；unit_key 取自 Appendix 1 "Unit N: WGE0N/01"
    N.M Topic/Option <name>      → 主题（Unit 1/2 印 Topic 1/2，Unit 3 印 Topic A1..C2，
                                   Unit 4 印 Option 1..4；编号均为 N.3 起的连续号）
      N.M.K <name>               → 编号知识点；块文本含 Enquiry question/Key idea/Detailed content
      N.M.K <name> (continued)   → 跨页续接，同号再次出现，并入前一同号节点（不新建节点）

不进树的内容（记入 issues，不静默）：
  - "N.1 Unit description"、"N.2 Assessment information" 是单元元数据，非内容点；
  - 单元末尾的 "Integrating geographical skills in Unit N"（Unit 1/3）与 Unit 2 的
    "Research and fieldwork" 是技能/fieldwork 指引；后者把 2.3.3/2.3.4/2.4.2/2.4.4
    当作 fieldwork 主题重复引用，必须排除以免产生重复编号。

编号缺陷：本 spec 的编号无实质缺陷——同号重复全部是跨页 "(continued)" 续接（11 处），
已并入前一同号节点；_fix_point_codes / _check_sequence 作为同规则的安全网保留，
若出现"编号与主题号不符 / 重复编号 / 缺号"会规范化并写入 issues。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import (
    PAGE_MARK_RE,
    clean_block,
    content_span,
    first_sentence,
    normalize_code,
    page_of_offset,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-geography"
SUBJECT = "International A Level Geography (2016)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+?)\s*$", re.M)
UNIT_CODE_RE = re.compile(r"^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$", re.M)
SECTION_RE = re.compile(r"^(\d{1,2}\.\d{1,2})[ \t]+(\S.*)$", re.M)
POINT_RE = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{1,2})[ \t]*(\S.*)?$", re.M)

# 单元内容区终止：技能指引 / Unit 2 的 fieldwork 指引 / 单元末尾的 Assessment information
UNIT_END_RE = re.compile(
    r"^(?:Integrating geographical skills in Unit \d+|Research and fieldwork|"
    r"Assessment information)\s*$",
    re.M,
)
# 编号标题的续接行终止条件
_HEADING_STOP_RE = re.compile(
    r"^(?:Enquiry question:|Key idea$|Detailed content$|Overview$|To be studied through|"
    r"\(continued\)|Appendix |Assessment information$|\d+\.\d+)"
)
# 单元元数据小节（非内容点）
_METADATA_SECTIONS = {"Unit description", "Assessment information"}
_CONTINUED = "(continued)"


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in UNIT_CODE_RE.finditer(text)}


def _last_unit_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过 "Geography content" 后的单元页码列表）。"""
    last: dict[str, re.Match] = {}
    for m in UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _read_heading(region: str, m: re.Match, inline: str) -> tuple[str, int, bool]:
    """读编号行的标题（含跨行续接）。

    返回 (标题, 标题后正文起点 offset, 是否 "(continued)" 续接块)。
    """
    parts: list[str] = []
    inline = re.sub(r"\s+", " ", inline).strip()
    if inline:
        parts.append(inline)
    pos = m.end()
    if pos < len(region) and region[pos] == "\n":
        pos += 1
    continued = False
    while pos < len(region):
        nl = region.find("\n", pos)
        line_end = nl if nl != -1 else len(region)
        line = region[pos:line_end].strip()
        if not line:
            break
        if line.endswith(_CONTINUED):
            continued = True
            line = line[: -len(_CONTINUED)].strip()
            pos = line_end + 1
            if not line:
                continue
        if PAGE_MARK_RE.match(line) or _HEADING_STOP_RE.match(line):
            break
        parts.append(re.sub(r"\s+", " ", line))
        pos = line_end + 1
    return " ".join(parts).strip(), pos, continued


def _fix_point_codes(
    codes: list[str], topic_codes: list[Optional[str]], issues: list[str], *, where: str
) -> list[str]:
    """修正知识点编号缺陷，返回修正后的编号（与输入等长）。

    与 common.resolve_code_conflicts 同规则，但按 N.M.K 三段号处理：
      - 主号（前两段）与所在主题号不符 → 改成 `{topic}.{末段}`；
      - 同一单元内编号重复 → 递增末段直到唯一。
    每条修正写入 issues。
    """
    out: list[str] = []
    seen: set[str] = set()
    for code, topic in zip(codes, topic_codes):
        new = normalize_code(code)
        head, _, last = new.rpartition(".")
        if topic and head and head != topic:
            fixed = f"{topic}.{last}"
            issues.append(
                f"{where}: code {new!r} does not match its topic {topic!r}; "
                f"normalized to {fixed!r}"
            )
            new = fixed
        if new in seen:
            head, _, last = new.rpartition(".")
            k = int(last) + 1 if last.isdigit() else 2
            while f"{head}.{k}" in seen:
                k += 1
            fixed = f"{head}.{k}"
            issues.append(f"{where}: duplicate code {new!r}; normalized to {fixed!r}")
            new = fixed
        seen.add(new)
        out.append(new)
    return out


def _check_sequence(nums: list[int], issues: list[str], *, where: str, kind: str) -> None:
    """缺号检查（spec 自身跳号时记入 issues；不重编号）。"""
    if not nums:
        return
    present = set(nums)
    missing = [k for k in range(min(nums), max(nums) + 1) if k not in present]
    if missing:
        issues.append(
            f"{where}: printed {kind} numbering skips "
            f"{', '.join(str(k) for k in missing)} (present: {min(nums)}-{max(nums)})"
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
    start, end = content_span(
        text, r"(?m)^Geography content\s*$", r"(?m)^Assessment information\s*$"
    )
    region = text[start:end]
    keys = _unit_key_map(text)

    headers = _last_unit_headers(region)
    unit_numbers = [int(h.group(1)) for h in headers]
    _check_sequence(unit_numbers, spec.issues, where="spec", kind="unit")
    excluded_metadata = False

    for i, header in enumerate(headers):
        num = header.group(1)
        name = header.group(2).strip()
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        body = region[ustart:uend]
        key = keys.get(num, "")
        if not key:
            key = f"U{num}"
            spec.issues.append(
                f"Unit {num}: unit entry code not found in Appendix 1: Codes; "
                f"using fallback unit_key {key!r}"
            )
        unit = SpecUnit(code=num, name=name, unit_key=key)

        # 单元内容区：到技能/fieldwork 指引或 Assessment information 为止
        end_m = UNIT_END_RE.search(body)
        content = body[: end_m.start()] if end_m else body
        if end_m:
            heading = body[end_m.start() : end_m.end()].strip()
            page = page_of_offset(text, start + ustart + end_m.start())
            spec.issues.append(
                f"Unit {num}: trailing section {heading!r} (p.{page}) is guidance, "
                f"not a numbered content point; excluded from the tree"
            )

        markers: list[tuple[int, str, str, str, re.Match]] = []
        for sm in SECTION_RE.finditer(content):
            markers.append((sm.start(), "section", sm.group(1), sm.group(2), sm))
        for pm in POINT_RE.finditer(content):
            markers.append((pm.start(), "point", pm.group(1), pm.group(2) or "", pm))
        markers.sort(key=lambda x: x[0])

        # 逐块读标题与正文：主题/元数据小节的标题整行印出，知识点的标题可能跨行续接
        entries: list[tuple[str, str, str, str, int, bool]] = []
        for j, (off, kind, code, inline, m) in enumerate(markers):
            nxt = markers[j + 1][0] if j + 1 < len(markers) else len(content)
            if kind == "section":
                title = re.sub(r"\s+", " ", inline).strip()
                nl = content.find("\n", m.end())
                hend = nl + 1 if nl != -1 else len(content)
                entries.append(("section", code, title, content[hend:nxt], ustart + off, False))
                continue
            title, hend, continued = _read_heading(content, m, inline)
            entries.append(("point", code, title, content[hend:nxt], ustart + off, continued))

        topic_entries = [
            e for e in entries if e[0] == "section" and e[2] not in _METADATA_SECTIONS
        ]
        if any(e[0] == "section" and e[2] in _METADATA_SECTIONS for e in entries):
            excluded_metadata = True
        point_entries = [e for e in entries if e[0] == "point" and not e[5]]

        # 主题号缺号检查
        topic_nums = []
        for e in topic_entries:
            head, _, tail = e[1].partition(".")
            if head == num and tail.isdigit():
                topic_nums.append(int(tail))
        _check_sequence(topic_nums, spec.issues, where=f"Unit {num}", kind="topic")

        # 编号规范化：知识点主号须与所在主题号一致，重复号递增
        topic_seq: list[Optional[str]] = []
        cur: Optional[str] = None
        for e in entries:
            if e[0] == "section" and e[2] not in _METADATA_SECTIONS:
                cur = e[1]
            elif e[0] == "point" and not e[5]:
                topic_seq.append(cur)
        fixed = _fix_point_codes(
            [e[1] for e in point_entries], topic_seq, spec.issues, where=f"Unit {num}"
        )
        fixed_by_offset = {e[4]: f for e, f in zip(point_entries, fixed)}

        merged: list[str] = []
        topic_nodes: dict[str, SpecNode] = {}
        point_nodes: dict[str, SpecNode] = {}
        for kind, code, title, btext, off, continued in entries:
            page = page_of_offset(text, start + off)
            clean = clean_block(btext)
            if kind == "section":
                if title in _METADATA_SECTIONS:
                    continue
                node = topic_nodes.get(code)
                if node is None:
                    node = SpecNode(
                        code=code,
                        label=f"{key}-{code}",
                        title=title or f"Topic {code}",
                        text=clean,
                        page=page,
                    )
                    topic_nodes[code] = node
                    unit.nodes.append(node)
                else:
                    node.text = (node.text + "\n" + clean).strip()
                continue
            if continued:
                target = point_nodes.get(code)
                if target is None:
                    spec.issues.append(
                        f"Unit {num}: continuation block {code!r} has no preceding point; "
                        f"kept as a standalone node"
                    )
                    fcode = _fix_point_codes([code], [code.rpartition(".")[0]], spec.issues,
                                             where=f"Unit {num}")[0]
                    node = SpecNode(
                        code=fcode,
                        label=f"{key}-{fcode}",
                        title=title or f"Point {fcode}",
                        text=clean,
                        page=page,
                    )
                    point_nodes[code] = node
                    parent = topic_nodes.get(fcode.rpartition(".")[0])
                    (parent.children if parent is not None else unit.nodes).append(node)
                else:
                    target.text = (target.text + "\n" + clean).strip()
                merged.append(code)
                continue
            fcode = fixed_by_offset[off]
            node = SpecNode(
                code=fcode,
                label=f"{key}-{fcode}",
                title=title or first_sentence(clean) or f"Point {fcode}",
                text=clean,
                page=page,
            )
            point_nodes[code] = node
            parent = topic_nodes.get(fcode.rpartition(".")[0])
            if parent is not None:
                parent.children.append(node)
            else:
                spec.issues.append(
                    f"Unit {num}: point {fcode!r} has no topic parent; attached to unit"
                )
                unit.nodes.append(node)

        if merged:
            spec.issues.append(
                f"Unit {num}: page-break '(continued)' repeats merged into the preceding "
                f"nodes: {', '.join(merged)}"
            )

        # 主题内编号缺号检查（用规范化后的编号）
        by_topic: dict[str, list[int]] = {}
        for (kind, _code, _title, _btext, _off, cont), fcode in zip(point_entries, fixed):
            head, _, last = fcode.rpartition(".")
            if last.isdigit():
                by_topic.setdefault(head, []).append(int(last))
        for head, nums in sorted(by_topic.items()):
            _check_sequence(nums, spec.issues, where=f"Unit {num} topic {head}", kind="point")

        for tcode, tnode in topic_nodes.items():
            if not tnode.children:
                spec.issues.append(
                    f"Unit {num}: topic {tcode!r} ({tnode.title!r}) has no numbered points"
                )

        spec.units.append(unit)

    if excluded_metadata:
        spec.issues.append(
            "units 1-4: 'N.1 Unit description' and 'N.2 Assessment information' are unit "
            "metadata, not content points; excluded from the tree"
        )

    return spec
