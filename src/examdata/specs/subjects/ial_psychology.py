"""IAL Psychology（2015，Issue 6 与 Issue 5 两份 PDF）spec 解析器。

内容区（"Psychology content" 之后到 "Assessment information"）：
  Unit N: <name>              → 单元；unit_key 取自附录 1: Codes（Unit 1: WPS01/01 → WPS01）
    N.M Topic X: <name>       → 主题；spec 印 "1.3 Topic A: …"（单元号.节号）
      X.n <section name>      → 主题内节（Content / Research methods / Studies /
                                Practical investigation / Issues and debates / …）
        N.M.K <text…>         → 编号知识点；块文本保留 guidance/说明，供后续标注用

编号缺陷与规范化（写入 issues，不静默）：
  - spec 每个单元同时印两套节号：单元级 "{unit}.{n}"（1.1 Unit description、1.3 Topic A …）
    与主题内 "{topic}.{n}"（Topic A 内 1.1 Content、1.3 Studies …）。Unit 1 里两套字面重复
    （"1.1" 既是 Unit description 又是 Topic A 的 Content）。故主题节点用 spec 印的主题字母
    A–I 作 code，主题内节用 "{字母}.{n}"；知识点保留印出的 "{topic}.{section}.{n}"。
  - 单元级行政节（Unit description / Assessment information）不是内容点，不产出节点。
  - 该科目在 manifest 里有两份 PDF：ial-psychology-1 是 Issue 5（2021），与 Issue 6 共用同一
    套单元入口码 WPS01–WPS04；两份合并后 label 会重复，故旧版 unit_key 加 "I{issue}" 后缀
    （WPS01I5），现行版保留官方码。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from ..common import (
    clean_block,
    content_span,
    first_sentence,
    normalize_code,
    page_of_offset,
)
from ..models import ParsedSpec, SpecNode, SpecUnit

SLUG = "ial-psychology"
SUBJECT = "International A Level Psychology (2015)"

# manifest 中 Issue 6（2024-11，首次评估 2026-01）是现行版；更早的 Issue 用 I{n} 后缀区分
CURRENT_ISSUE = 6

_UNIT_HEADER_RE = re.compile(r"(?m)^Unit (\d+): (.+)$")
_UNIT_CODE_RE = re.compile(r"(?m)^Unit (\d+): (W[A-Z0-9]+)/\d+\s*$")
_ISSUE_RE = re.compile(r"(?m)^Issue (\d+)\s*$")
_TOPIC_RE = re.compile(r"(?m)^(\d{1,2}\.\d{1,2})\s+Topic ([A-I]):\s*(.+)$")
_SECTION_RE = re.compile(r"^(\d{1,2}\.\d{1,2})[ \t]+(\S.*)$")
_POINT_RE = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{1,2})\s*(.*)$")
_POINT_PREFIX_RE = re.compile(r"^\s*\d{1,2}\.\d{1,2}\.\d{1,2}[ \t]*")

# 主题内节的节名（spec 上会换行：如 "Research" + "methods"、"Issues and" + "debates"）
_SECTION_NAMES = frozenset(
    {
        "content",
        "research methods",
        "methods",
        "studies",
        "practical investigation",
        "issues and debates",
        "issues",
        "key questions in society",
    }
)

# 单元标题换行续接的判定
_TITLE_STOP_WORDS = {"and", "or", "of", "the", "in", "to", "with", "for", "on", "a", "an"}


@dataclass
class _Entry:
    offset: int  # 标记行在 topic body 中的起点
    body_offset: int  # 块文本起点（节跳过标题行，知识点含编号行）
    kind: str  # "topic" | "section" | "point"
    code: str  # 主题字母 / 印出的节号 / 印出的知识点号
    title: str  # 主题标题 / 节名 / ""（知识点用块文本首句）
    topic: str = ""  # 知识点所属主题的印出主号（如 "1"），供编号校验


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _unit_key_map(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in _UNIT_CODE_RE.finditer(text)}


def _spec_issue(text: str) -> Optional[int]:
    """封面 "Issue N" → 版本号（找不到返回 None）。"""
    m = _ISSUE_RE.search(text[:4000])
    return int(m.group(1)) if m else None


def _last_headers(region: str) -> list[re.Match]:
    """每个单元号的最后一次出现（跳过目录页的单元列表）。"""
    last: dict[str, re.Match] = {}
    for m in _UNIT_HEADER_RE.finditer(region):
        last[m.group(1)] = m
    return sorted(last.values(), key=lambda m: m.start())


def _unit_name(region: str, header: re.Match) -> str:
    """合并单元标题的换行续接（如 "Unit 2: Biological psychology, learning theories and"）。"""
    name = header.group(2).strip()
    for line in region[header.end() :].lstrip("\r\n").splitlines()[:4]:
        line = line.strip()
        if not line:
            break
        last_word = name.rsplit(" ", 1)[-1].strip(",").lower()
        if not (name.endswith(",") or last_word in _TITLE_STOP_WORDS or line[:1].islower()):
            break
        name = f"{name} {line}".strip()
        if len(name) > 140:
            break
    return re.sub(r"\s+", " ", name).strip()


def _lines(body: str) -> list[tuple[int, str]]:
    """[(行起点 offset, 行文本), …]。"""
    out: list[tuple[int, str]] = []
    offset = 0
    for line in body.split("\n"):
        out.append((offset, line))
        offset += len(line) + 1
    return out


def _section_name(lines: list[tuple[int, str]], idx: int, tail: str) -> Optional[tuple[str, int]]:
    """拼出节名（节名可能跨行）；返回 (节名, 消耗行数) 或 None（不是已知节名）。"""
    joined = re.sub(r"\s+", " ", tail).strip()
    best: Optional[tuple[str, int]] = None
    if _norm(joined) in _SECTION_NAMES:
        best = (joined, 1)
    for extra in (1, 2):
        if idx + extra >= len(lines):
            break
        nxt = lines[idx + extra][1].strip()
        if not nxt:
            break
        joined = f"{joined} {nxt}"
        if _norm(joined) in _SECTION_NAMES:
            best = (joined, extra + 1)
    return best


def _topic_entries(
    tbody: str, topic_title: str, letter: str, issues: list[str], *, where: str
) -> list[_Entry]:
    """把主题正文切成 [主题块, 节块, 知识点块] 的标记序列。"""
    lines = _lines(tbody)
    entries = [_Entry(offset=0, body_offset=0, kind="topic", code=letter, title=topic_title)]
    seen_sections: set[str] = set()
    idx = 0
    while idx < len(lines):
        offset, raw = lines[idx]
        line = raw.strip()
        if not line:
            idx += 1
            continue
        point = _POINT_RE.match(line)
        if point:
            major, _, minor = point.group(1).partition(".")
            entries.append(
                _Entry(
                    offset=offset,
                    body_offset=offset,
                    kind="point",
                    code=point.group(1),
                    title="",
                    topic=major,
                )
            )
            idx += 1
            continue
        section = _SECTION_RE.match(line)
        if section:
            named = _section_name(lines, idx, section.group(2))
            if named is not None:
                name, used = named
                last = lines[idx + used - 1]
                printed = section.group(1)
                major, _, minor = printed.partition(".")
                expected = str(ord(letter) - ord("A") + 1)
                code = f"{letter}.{minor}"
                if major != expected:
                    issues.append(
                        f"{where}: section {printed!r} inside Topic {letter} does not match the "
                        f"topic number; normalized to {code!r}"
                    )
                if code in seen_sections:
                    k = int(minor) + 1
                    while f"{letter}.{k}" in seen_sections:
                        k += 1
                    issues.append(
                        f"{where}: duplicate section {printed!r} inside Topic {letter}; "
                        f"normalized to {letter}.{k!r}"
                    )
                    code = f"{letter}.{k}"
                seen_sections.add(code)
                entries.append(
                    _Entry(
                        offset=offset,
                        body_offset=last[0] + len(last[1]) + 1,
                        kind="section",
                        code=code,
                        title=name,
                        topic=printed,
                    )
                )
                idx += used
                continue
        idx += 1
    return entries


def _normalize_codes(
    codes: list[str], topic_of: list[str], issues: list[str], *, where: str
) -> list[str]:
    """修正编号缺陷（resolve_code_conflicts 的等价逻辑，适配三级编号 N.M.K）。

    resolve_code_conflicts 假设 "{topic}.{minor}" 两级，对 "1.1.1" 这样的三级编号在
    去重时会丢层级；这里保留末段递增、前缀重写为所属主题号。
    """
    out: list[str] = []
    seen: set[str] = set()
    for code, topic in zip(codes, topic_of):
        new = normalize_code(code)
        if topic and not new.startswith(f"{topic}."):
            fixed = f"{topic}.{new.split('.', 1)[1]}" if "." in new else topic
            issues.append(
                f"{where}: code {new!r} does not match its topic {topic!r}; normalized to {fixed!r}"
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


def _unit_level_codes(ubody: str) -> set[str]:
    """单元级印出的节号：首个主题标题之前的行政节号 + 各主题标题行的印出号。"""
    codes: set[str] = set()
    first_topic = _TOPIC_RE.search(ubody)
    head = ubody[: first_topic.start()] if first_topic else ubody
    for raw in head.split("\n"):
        m = _SECTION_RE.match(raw.strip())
        if m:
            codes.add(m.group(1))
    for tm in _TOPIC_RE.finditer(ubody):
        codes.add(tm.group(1))
    return codes


def parse(text: str, meta: Optional[dict[str, Any]] = None) -> ParsedSpec:
    meta = meta or {}
    spec = ParsedSpec(
        subject=SLUG,
        title=meta.get("title") or SUBJECT,
        parser=__name__,
        spec_url=meta.get("url", ""),
        spec_sha256=meta.get("sha256", ""),
    )
    issue = _spec_issue(text)
    suffix = "" if issue is None or issue >= CURRENT_ISSUE else f"I{issue}"
    start, end = content_span(text, r"Psychology content", r"(?m)^Assessment information")
    region = text[start:end]
    keys = _unit_key_map(text)

    spec.issues.append(
        "spec prints two section-number series per unit ('{unit}.{n}' for Unit description / "
        "Assessment information / topic headers and '{topic}.{n}' inside each topic); topic nodes "
        "use the printed topic letter (A–I) and topic-internal sections use '{letter}.{n}'; point "
        "codes keep the printed '{topic}.{section}.{n}'"
    )
    spec.issues.append(
        "unit-level sections 'Unit description' and 'Assessment information' are administrative, "
        "not content points; not emitted as nodes"
    )

    headers = _last_headers(region)
    suffixed: list[str] = []
    for i, header in enumerate(headers):
        num = header.group(1)
        name = _unit_name(region, header)
        ustart = header.start()
        uend = headers[i + 1].start() if i + 1 < len(headers) else len(region)
        ubody = region[ustart:uend]
        key = keys.get(num)
        if not key:
            key = f"UPS{num}"
            spec.issues.append(
                f"Unit {num}: no entry code in Appendix 1: Codes; fallback key {key!r} used"
            )
        if suffix:
            key = f"{key}{suffix}"
            suffixed.append(key)

        unit = SpecUnit(code=num, name=name, unit_key=key)
        topics = list(_TOPIC_RE.finditer(ubody))
        if not topics:
            spec.issues.append(f"Unit {num} ({key}): no 'Topic X' sections found")
            spec.units.append(unit)
            continue

        unit_codes = _unit_level_codes(ubody)
        topic_section_codes: set[str] = set()

        for j, tm in enumerate(topics):
            tend = topics[j + 1].start() if j + 1 < len(topics) else len(ubody)
            tbody = ubody[tm.end() : tend]
            letter = tm.group(2)
            topic_name = re.sub(r"\s+", " ", tm.group(3)).strip()
            title = f"Topic {letter}: {topic_name}"
            entries = _topic_entries(
                tbody, title, letter, spec.issues, where=f"Unit {num} ({key})"
            )

            points = [e for e in entries if e.kind == "point"]
            fixed = _normalize_codes(
                [e.code for e in points],
                [e.topic for e in points],
                spec.issues,
                where=f"Unit {num} ({key})",
            )
            fixed_by_offset = {e.offset: c for e, c in zip(points, fixed)}

            topic_node = SpecNode(
                code=letter,
                label=f"{key}-{letter}",
                title=title,
                text="",
                page=page_of_offset(text, start + ustart + tm.start()),
            )
            unit.nodes.append(topic_node)
            cur_section: Optional[SpecNode] = None
            cur_printed = ""
            for k, entry in enumerate(entries):
                block_end = entries[k + 1].offset if k + 1 < len(entries) else len(tbody)
                raw = tbody[entry.body_offset : block_end]
                if entry.kind == "point":
                    raw = _POINT_PREFIX_RE.sub("", raw, count=1)
                ctext = clean_block(raw)
                page = page_of_offset(text, start + ustart + tm.end() + entry.offset)
                if entry.kind == "topic":
                    topic_node.text = ctext
                    continue
                if entry.kind == "section":
                    cur_printed = entry.topic
                    topic_section_codes.add(entry.topic)
                    cur_section = SpecNode(
                        code=entry.code,
                        label=f"{key}-{entry.code}",
                        title=entry.title,
                        text=ctext,
                        page=page,
                    )
                    topic_node.children.append(cur_section)
                    continue
                fcode = fixed_by_offset[entry.offset]
                node = SpecNode(
                    code=fcode,
                    label=f"{key}-{fcode}",
                    title=first_sentence(ctext) or f"Point {fcode}",
                    text=ctext,
                    page=page,
                )
                major, minor, _n = entry.code.split(".")
                if cur_section is not None and cur_printed == f"{major}.{minor}":
                    cur_section.children.append(node)
                else:
                    spec.issues.append(
                        f"Unit {num} ({key}): point {fcode!r} has no matching section parent"
                    )
                    topic_node.children.append(node)

        duplicates = sorted(
            unit_codes & topic_section_codes, key=lambda c: tuple(int(p) for p in c.split("."))
        )
        if duplicates:
            spec.issues.append(
                f"Unit {num} ({key}): unit-level and topic-internal printed numbers collide "
                f"({', '.join(duplicates)}); the letter-based codes disambiguate the two series"
            )
        spec.units.append(unit)

    if suffixed:
        spec.issues.append(
            f"Issue {issue} spec shares the official unit entry codes with the current Issue "
            f"{CURRENT_ISSUE} spec; unit_keys suffixed ({', '.join(suffixed)}) so labels stay "
            "unique when the runner merges both files"
        )
    return spec
