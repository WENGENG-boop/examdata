"""Spec 解析共用工具：页切片、内容区定位、块切分、文本清理。

所有科目解析器都从这里取工具函数，保证：
  - 页码标记统一（`<<<PAGE n>>>`，与 .data/specs/text/*.txt 一致）；
  - 页眉页脚、版权行、孤立页码统一剔除；
  - 编号块切分按“下一个编号出现即断块”，块内保留子条目。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

import pymupdf

PAGE_MARK_RE = re.compile(r"<<<PAGE (\d+)>>>")

# 页眉/页脚/版权噪声行
_FURNITURE_RES = [
    re.compile(r"^Pearson Edexcel International (Advanced Subsidiary|Advanced Level).*$"),
    re.compile(r"^Specification\s*[–-]\s*Issue\s+\d+.*$", re.I),
    re.compile(r"^and Pure Mathematics\s*[–-]\s*Specification.*$"),
    re.compile(r"^© Pearson Education Limited \d+$"),
    re.compile(r"^\d{1,3}$"),
    re.compile(r"^Pearson Education Limited \d+$"),
    re.compile(r"^\s*$"),
]


def extract_text(pdf_path: Path) -> str:
    """把 PDF 抽成带 <<<PAGE n>>> 标记的纯文本（与 .data/specs/text 一致）。"""
    doc = pymupdf.open(pdf_path)
    chunks: list[str] = []
    for i, page in enumerate(doc):
        chunks.append(f"\n<<<PAGE {i + 1}>>>\n")
        chunks.append(page.get_text("text"))
    return "".join(chunks)


def page_slices(text: str) -> list[tuple[int, str]]:
    """按页标记切片：[(页码, 该页文本), ...]。"""
    parts = PAGE_MARK_RE.split(text)
    # parts = [前导, page1, text1, page2, text2, ...]
    out: list[tuple[int, str]] = []
    for i in range(1, len(parts), 2):
        out.append((int(parts[i]), parts[i + 1]))
    return out


def page_of_offset(text: str, offset: int) -> int:
    """给定字符 offset，返回所在页码。"""
    page = 1
    for m in PAGE_MARK_RE.finditer(text, 0, offset):
        page = int(m.group(1))
    return page


def clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ").rstrip()
    return line


def clean_block(text: str) -> str:
    """清理块文本：去页眉页脚噪声、去页标记、合并空白。"""
    lines = []
    for raw in text.splitlines():
        line = clean_line(raw)
        if PAGE_MARK_RE.match(line.strip()):
            continue
        if any(rx.match(line.strip()) for rx in _FURNITURE_RES):
            continue
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def content_span(text: str, start_re: str, end_re: str | None = None) -> tuple[int, int]:
    """内容区字符区间 [start, end)：start 取 start_re 的**最后一次**匹配。

    目录里也会出现 "Biology content" 等标题；正文在目录之后，所以从最后一次
    匹配起更稳。end_re 缺省到文末；给了则取 start 之后首次出现处。
    """
    starts = [m.start() for m in re.finditer(start_re, text)]
    if not starts:
        raise ValueError(f"content start not found: {start_re}")
    begin = starts[-1]
    if end_re is None:
        return begin, len(text)
    ends = [m.start() for m in re.finditer(end_re, text[begin:])]
    if not ends:
        raise ValueError(f"content end not found after start: {end_re}")
    return begin, begin + ends[0]


def slice_content(text: str, start_re: str, end_re: str | None = None) -> str:
    """截取内容区（content_span 的字符串版）。"""
    start, end = content_span(text, start_re, end_re)
    return text[start:end]


@dataclass
class Block:
    code: str
    text: str
    offset: int  # 在原始 text 中的起始 offset（用于回查页码）


def split_blocks(region: str, marker_re: re.Pattern, *, base_offset: int = 0) -> list[Block]:
    """按编号标记把区域切成块：每个 marker 匹配处开始新块，直到下一个 marker。

    marker_re 必须带命名组 `code`。marker 行本身从块文本里去掉。
    """
    matches = list(marker_re.finditer(region))
    blocks: list[Block] = []
    for i, m in enumerate(matches):
        code = m.group("code")
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(region)
        body = region[body_start:body_end]
        blocks.append(Block(code=code, text=body, offset=base_offset + m.start()))
    return blocks


def make_node(unit_key: str, code: str, title: str, text: str, page: Optional[int] = None):
    """构造节点的便捷函数（延迟 import 避免环）。"""
    from .models import SpecNode

    label = f"{unit_key}-{code}" if code else unit_key
    return SpecNode(code=code, label=label, title=title, text=text, page=page)


def first_sentence(text: str, limit: int = 120) -> str:
    """取块文本的第一句/首行作为标题。"""
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return ""
    m = re.split(r"(?<=[.;:])\s", flat, maxsplit=1)
    title = m[0] if m else flat
    return title[:limit].strip()


def title_from_block(text: str, limit: int = 120) -> str:
    """块标题：优先第一行（spec 里标题常在首行），否则第一句。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""
    first = re.sub(r"\s+", " ", lines[0])
    if len(lines) > 1 and len(first) < 12:
        first = re.sub(r"\s+", " ", (lines[0] + " " + lines[1]).strip())
    return first[:limit].strip()


def unit_key_from_codes(text: str, unit_code: str, *, default_prefix: str = "") -> str:
    """从 "Unit N: WXXNN/01" 这类行里抽单元入口码。"""
    m = re.search(
        rf"Unit\s+{re.escape(unit_code)}\s*[:.]?\s*(W[A-Z]{{2}}\d{{2}})\b", text
    )
    if m:
        return m.group(1)
    return default_prefix


def dedupe_codes(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def find_units(
    region: str, unit_re: re.Pattern, *, base_offset: int = 0
) -> list[tuple[str, str, int]]:
    """返回 [(unit_code, unit_name, offset), ...]，用于切分单元。"""
    out = []
    for m in unit_re.finditer(region):
        out.append((m.group("code"), (m.group("name") or "").strip(), base_offset + m.start()))
    return out


def cut_regions(region: str, cuts: list[int]) -> Iterator[tuple[int, int]]:
    """由切点列表生成 (start, end) 区间。"""
    for i, start in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else len(region)
        yield start, end


def marker_blocks(
    region: str, markers: list[tuple[int, str, str, str]]
) -> list[tuple[str, str, str, str, int]]:
    """按标记切块：markers = [(offset, kind, code, heading), ...]，须按 offset 升序。

    每个标记的块文本 = 标记所在行之后 到 下一个标记之前（未清理，含页标记）。
    返回 [(kind, code, heading, text, offset), ...]，offset 为该标记在 region 中的位置。
    """
    out: list[tuple[str, str, str, str, int]] = []
    for i, (off, kind, code, heading) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(region)
        nl = region.find("\n", off, end)
        body_start = nl + 1 if nl != -1 else end
        out.append((kind, code, heading, region[body_start:end], off))
    return out


def resolve_code_conflicts(
    codes: list[str],
    topic_codes: list[Optional[str]],
    issues: list[str],
    *,
    where: str,
) -> list[str]:
    """修正 spec 自身编号缺陷，返回修正后的编号（与输入等长）。

    规则（所有修正写入 issues，不静默）：
      - 编号主号与所在主题号不符 → 改成 `{topic}.{minor}`；
      - 同一单元内编号重复 → 递增次号直到唯一。
    """
    out: list[str] = []
    seen: set[str] = set()
    for code, topic in zip(codes, topic_codes):
        new = normalize_code(code)
        major, _, minor = new.partition(".")
        if topic and minor and major != topic:
            fixed = f"{topic}.{minor}"
            issues.append(
                f"{where}: code {new!r} does not match its topic {topic!r}; normalized to {fixed!r}"
            )
            new = fixed
        if new in seen:
            base, _, minor_s = new.partition(".")
            k = int(minor_s) + 1 if minor_s.isdigit() else 2
            while f"{base}.{k}" in seen:
                k += 1
            fixed = f"{base}.{k}"
            issues.append(f"{where}: duplicate code {new!r}; normalized to {fixed!r}")
            new = fixed
        seen.add(new)
        out.append(new)
    return out


def normalize_code(code: str) -> str:
    """规范编号：去空白、统一连字符。"""
    return re.sub(r"\s+", "", code).replace("–", "-")
