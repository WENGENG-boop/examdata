"""IAL Computer Science (2026, Issue 1) spec 解析器。

结构（内容区 "Unit 1: Principles of Computer Science" → "Assessment availability"，页 14-70）：
  Unit N: <name>                → 单元；unit_key 取自 "Unit code: WCP0N/01"
    Topic M: <name>             → 主题（编号 1-21 全局连续）
      M.K [title]               → 子主题（标题同行或次行；"(continued)" 页头跳过）
        M.K.J [title...]        → 编号知识点；块文本含 Know and understand / Be able to 说明

PDF 文本层在 Unit 4 把 17.2 排在 Topic 17 标题之前（视觉顺序正常）；
节点按编号前缀挂接，不依赖文本先后，该异常记入 issues。
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..common import clean_block, content_span, page_of_offset
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial26-computer-science"
SUBJECT = "International A Level Computer Science (2026)"

UNIT_HEADER_RE = re.compile(r"^Unit (\d+): (.+?)\s*$", re.M)
UNIT_CODE_RE = re.compile(r"\(\*Unit code: (W[A-Z0-9]+)/\d+")
TOPIC_RE = re.compile(r"^Topic (\d+): (.+?)\s*$", re.M)
SUB_SAME_RE = re.compile(r"^(\d{1,2}\.\d{1,2})[ \t]+(\S.*?)\s*$", re.M)
SUB_CODE_RE = re.compile(r"^(\d{1,2}\.\d{1,2})[ \t]*$", re.M)
POINT_RE = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{1,2})[ \t]*(.*?)\s*$", re.M)

# 标题结束行：遇到这些行说明标题已收集完
_TITLE_STOP_RE = re.compile(
    r"^(Content$|Learners should:|Know and understand:|Be able to:|Further details|"
    r"Assessment|Overview$|Centres|Sample assessment|•|[a-z]\.([\t ]|$)|[0-9]+\.[0-9]+)"
)
_DANGLING = {
    "a", "an", "the", "and", "or", "of", "in", "to", "with", "for", "from",
    "into", "on", "at", "as", "by", "using", "use",
}

_NOISE_RE = re.compile(
    r"^(<<<PAGE \d+>>>|\d{1,3}|Pearson Edexcel International.*|Issue \d+.*DCL1.*)$"
)
_FOOTER_RE = re.compile(r"^Issue \d+\s*[–-]\s*DCL1\s*[–-].*$")
_HEADER_RE = re.compile(r"^Pearson Edexcel International.*$")


def _strip_ctrl(line: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", line)


def _clean_text(body: str) -> str:
    """块文本清理：去页眉页脚、页码、页标记噪声。"""
    out = clean_block(body)
    lines = []
    for line in out.splitlines():
        s = line.strip()
        if _FOOTER_RE.match(s) or _HEADER_RE.match(s):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _title_lines(body: str):
    for raw in body.splitlines():
        line = _strip_ctrl(raw).strip()
        if not line or _NOISE_RE.match(line):
            continue
        yield line


def _merge_title(head: str, body: str, limit: int = 140) -> str:
    """标题合并：同行标题 + 次行续接（悬空词 / 小写开头），遇到内容行停止。"""
    parts: list[str] = []
    if head and head.strip():
        parts.append(_strip_ctrl(head).strip())
    for line in _title_lines(body):
        if _TITLE_STOP_RE.match(line):
            break
        if not parts:
            parts.append(line)
            continue
        cur = parts[-1]
        last_word = re.sub(r"[^A-Za-z0-9]+$", "", cur).rsplit(" ", 1)[-1].lower()
        merge = (
            last_word in _DANGLING
            or cur.endswith((",", "-", "&", "(", "/"))
            or line[:1].islower()
        )
        if not merge:
            break
        parts.append(line)
        if sum(len(p) + 1 for p in parts) > limit:
            break
    title = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return title[:limit]


def _toc_unit_names(text: str) -> dict[str, str]:
    """每个单元的第一处完整名称（目录页单行；正文标题在文本层可能折行截断）。"""
    out: dict[str, str] = {}
    for m in UNIT_HEADER_RE.finditer(text):
        num, name = m.group(1), m.group(2).strip()
        if num not in out and name:
            out[num] = name
    return out


def _unit_key_map(text: str) -> dict[str, str]:
    """从 "Unit code: WCP0N/01" 反查最近的 Unit N 标题，映射 N → 单元码。"""
    out: dict[str, str] = {}
    for m in UNIT_CODE_RE.finditer(text):
        before = text[: m.start()]
        hm = None
        for hm2 in UNIT_HEADER_RE.finditer(before):
            hm = hm2
        if hm is None:
            continue
        num = hm.group(1)
        if num not in out:
            out[num] = m.group(1)
    return out


def _header_name_fallback(ubody: str) -> str:
    m = UNIT_HEADER_RE.match(ubody)
    if not m:
        return ""
    name = m.group(2).strip()
    rest = ubody[m.end():].lstrip("\r\n").splitlines()
    if rest:
        nxt = rest[0].strip()
        last = name.rsplit(" ", 1)[-1].strip(",.").lower()
        if nxt and (last in _DANGLING or len(nxt.split()) == 1) and not _NOISE_RE.match(nxt):
            name = f"{name} {nxt}"
    return name


def _entries(ubody: str) -> list[tuple[str, str, str, str, int]]:
    """切块：[(kind, code, head, body, offset), ...]，按出现位置排序。"""
    markers: list[tuple[int, int, str, str, str]] = []
    for m in TOPIC_RE.finditer(ubody):
        markers.append((m.start(), m.end(), "topic", m.group(1), m.group(2).strip()))
    for m in SUB_SAME_RE.finditer(ubody):
        markers.append((m.start(), m.end(), "sub", m.group(1), m.group(2).strip()))
    for m in SUB_CODE_RE.finditer(ubody):
        markers.append((m.start(), m.end(), "sub", m.group(1), ""))
    for m in POINT_RE.finditer(ubody):
        markers.append((m.start(), m.end(), "point", m.group(1), m.group(2).strip()))
    markers.sort(key=lambda x: x[0])
    out = []
    for i, (st, en, kind, code, head) in enumerate(markers):
        nxt = markers[i + 1][0] if i + 1 < len(markers) else len(ubody)
        out.append((kind, code, head, ubody[en:nxt], st))
    return out


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
        text,
        r"(?m)^Unit 1: Principles of Computer Science\s*$",
        r"(?m)^Assessment availability\s*$",
    )
    region = text[start:end]
    names = _toc_unit_names(text)
    keys = _unit_key_map(text)
    headers = [
        (m.group(1), m.start()) for m in re.finditer(r"(?m)^Unit (\d+): ", region)
    ]

    for i, (num, hstart) in enumerate(headers):
        uend = headers[i + 1][1] if i + 1 < len(headers) else len(region)
        ubody = region[hstart:uend]
        key = keys.get(num)
        if not key:
            key = f"U{num}"
            spec.issues.append(f"Unit {num}: no printed unit code found; using {key!r}")
        name = names.get(num) or _header_name_fallback(ubody)
        unit = SpecUnit(code=num, name=name, unit_key=key)
        entries = _entries(ubody)

        topic_nodes: dict[str, SpecNode] = {}
        topic_offsets: dict[str, int] = {}
        for kind, code, head, body, off in entries:
            if kind != "topic":
                continue
            if code in topic_nodes:
                spec.issues.append(f"Unit {num}: duplicate topic header {code!r} skipped")
                continue
            node = SpecNode(
                code=code,
                label=f"{key}-{code}",
                title=head or f"Topic {code}",
                text=_clean_text(body),
                page=page_of_offset(text, start + hstart + off),
            )
            topic_nodes[code] = node
            topic_offsets[code] = off
            unit.nodes.append(node)

        sub_nodes: dict[str, SpecNode] = {}
        for kind, code, head, body, off in entries:
            if kind != "sub":
                continue
            title = _merge_title(head, body)
            if "(continued)" in title or code in sub_nodes:
                continue
            major = code.split(".")[0]
            node = SpecNode(
                code=code,
                label=f"{key}-{code}",
                title=title or f"Section {code}",
                text=_clean_text(body),
                page=page_of_offset(text, start + hstart + off),
            )
            parent = topic_nodes.get(major)
            if parent is None:
                spec.issues.append(f"Unit {num}: section {code} has no topic {major!r} parent")
                unit.nodes.append(node)
            else:
                if topic_offsets.get(major, 0) > off:
                    spec.issues.append(
                        f"Unit {num}: section {code} appears before its topic header in the "
                        f"PDF text layer; attached by number"
                    )
                parent.children.append(node)
            sub_nodes[code] = node

        seen_points: dict[str, SpecNode] = {}
        for kind, code, head, body, off in entries:
            if kind != "point":
                continue
            title = _merge_title(head, body)
            if code in seen_points:
                base, _, minor = code.rpartition(".")
                k = int(minor) + 1 if minor.isdigit() else 2
                while f"{base}.{k}" in seen_points:
                    k += 1
                fixed = f"{base}.{k}"
                spec.issues.append(
                    f"Unit {num}: duplicate point code {code!r}; normalized to {fixed!r}"
                )
                code = fixed
            node = SpecNode(
                code=code,
                label=f"{key}-{code}",
                title=title or f"Point {code}",
                text=_clean_text((head + "\n" if head else "") + body),
                page=page_of_offset(text, start + hstart + off),
            )
            prefix = code.rsplit(".", 1)[0]
            parent = sub_nodes.get(prefix)
            if parent is not None:
                parent.children.append(node)
            else:
                spec.issues.append(f"Unit {num}: point {code} has no section {prefix!r} parent")
                tparent = topic_nodes.get(prefix.split(".")[0])
                if tparent is not None:
                    tparent.children.append(node)
                else:
                    unit.nodes.append(node)
            seen_points[code] = node

        if not unit.nodes:
            spec.issues.append(f"Unit {num}: no content nodes parsed")
        spec.units.append(unit)

    return spec
