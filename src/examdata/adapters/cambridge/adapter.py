"""Cambridge International 适配器实现。

发现链路（三层，均已在 research/cambridge.md 实测）：
  1. 家族 -> syllabus:  /programmes-and-qualifications/{family}/{qualification}/subjects/
  2. syllabus -> 资源:  /{syllabus-slug}/past-papers
  3. 锚文本 -> 元数据:  classify.parse_label + parse_slug 交叉校验

合规要点：
  - robots 由 Fetcher 强制；Cambridge 的 /search 被禁止，本适配器**不使用**站内搜索。
  - 全程只读公开页面，无登录、无绕过。
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Iterator

from ...core.fetch import Fetcher
from ..base import BoardAdapter, DiscoveredResource, SyllabusRef
from ..registry import register
from .classify import (
    DOC_OTHER,
    cross_check,
    normalize_label,
    parse_label,
    parse_slug,
    split_paper_code,
)

BASE = "https://www.cambridgeinternational.org"

# 家族与资格：实测 IGCSE 104 / AS-A Level 59 / O Level 35 个 syllabus。
# Cambridge Primary 与 Lower Secondary 的 /subjects/ 返回 404，入口待 Phase 0 收尾时补。
FAMILIES: list[dict[str, str]] = [
    {
        "qualification_key": "cambridge-igcse",
        "qualification_name": "Cambridge IGCSE",
        "subjects_url": f"{BASE}/programmes-and-qualifications/cambridge-upper-secondary/cambridge-igcse/subjects/",
    },
    {
        "qualification_key": "cambridge-as-a-level",
        "qualification_name": "Cambridge International AS & A Level",
        "subjects_url": f"{BASE}/programmes-and-qualifications/cambridge-advanced/cambridge-international-as-and-a-levels/subjects/",
    },
    {
        "qualification_key": "cambridge-o-level",
        "qualification_name": "Cambridge O Level",
        "subjects_url": f"{BASE}/programmes-and-qualifications/cambridge-upper-secondary/cambridge-o-level/subjects/",
    },
]

# 第一层：从 subjects 页抽取 syllabus slug
_SYLLABUS_LINK = re.compile(
    r'href="(?:' + re.escape(BASE) + r')?/programmes-and-qualifications/'
    r'([a-z0-9\-]+-(\d{4}))/?"[^>]*>(.*?)</a>',
    re.I | re.S,
)
# 兜底：页面里出现的裸 slug（用于链接结构变化时仍能枚举）
_SYLLABUS_BARE = re.compile(r"/programmes-and-qualifications/([a-z0-9\-]+-(\d{4}))/", re.I)

# 第二层：past-papers 页中的 PDF 锚点
_PDF_ANCHOR = re.compile(
    r'<a[^>]+href="(/Images/[^"]+\.pdf)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_ANY_PDF = re.compile(r'href="(/Images/[^"]+\.pdf)"', re.I)
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_tags(html: str) -> str:
    return _WS.sub(" ", _HTML_TAG.sub(" ", html)).strip()


@register
class CambridgeAdapter(BoardAdapter):
    key = "cambridge"
    board_name = "Cambridge International"
    homepage = BASE
    accessibility = "public"

    # -- 入口 ------------------------------------------------------------

    def index_sources(self) -> list[tuple[str, str]]:
        return [("family_index", fam["subjects_url"]) for fam in FAMILIES]

    # -- 第一层：syllabus 枚举 -------------------------------------------

    def discover_syllabuses(self) -> Iterator[SyllabusRef]:
        seen: set[str] = set()
        for fam in FAMILIES:
            res = self.fetcher.get_text(fam["subjects_url"])
            if not res.ok or not res.text:
                # 单个家族失败不影响其他家族
                continue

            found: dict[str, str] = {}
            for m in _SYLLABUS_LINK.finditer(res.text):
                slug, code, title = m.group(1), m.group(2), _strip_tags(m.group(3))
                if slug not in found or (title and not found[slug]):
                    found[slug] = title
            # 链接结构变化时的兜底（仅补 slug，无标题）
            for m in _SYLLABUS_BARE.finditer(res.text):
                slug = m.group(1)
                found.setdefault(slug, "")

            for slug, title in sorted(found.items()):
                if slug in seen:
                    continue
                seen.add(slug)
                code = slug.rsplit("-", 1)[-1]
                yield SyllabusRef(
                    slug=slug,
                    code=code,
                    title=title or slug,
                    qualification_key=fam["qualification_key"],
                    qualification_name=fam["qualification_name"],
                    source_url=f"{BASE}/programmes-and-qualifications/{slug}/",
                    attrs={
                        "past_papers_url": f"{BASE}/programmes-and-qualifications/{slug}/past-papers",
                        "family_subjects_url": fam["subjects_url"],
                    },
                )

    # -- 第二层：资源枚举 -------------------------------------------------

    def past_papers_url(self, syllabus: SyllabusRef) -> str:
        return syllabus.attrs.get(
            "past_papers_url",
            f"{BASE}/programmes-and-qualifications/{syllabus.slug}/past-papers",
        )

    def discover_resources(self, syllabus: SyllabusRef) -> Iterator[DiscoveredResource]:
        url = self.past_papers_url(syllabus)
        res = self.fetcher.get_text(url)
        if not res.ok or not res.text:
            return

        labels: dict[str, str] = {}
        for m in _PDF_ANCHOR.finditer(res.text):
            href, raw_label = m.group(1), m.group(2)
            full = href if href.startswith("http") else BASE + href
            # 同一 URL 多次出现时保留信息量最大的标签
            if full not in labels or len(normalize_label(raw_label)) > len(labels[full]):
                labels[full] = raw_label
        for m in _ANY_PDF.finditer(res.text):
            href = m.group(1)
            full = href if href.startswith("http") else BASE + href
            labels.setdefault(full, "")

        for full, raw_label in sorted(labels.items()):
            yield self.build_resource(full, raw_label, syllabus, page_url=url)

    # -- 第三层：分类与元数据 ---------------------------------------------

    def build_resource(
        self, url: str, raw_label: str, syllabus: SyllabusRef, page_url: str | None = None
    ) -> DiscoveredResource:
        label = normalize_label(raw_label)
        parsed = parse_label(label)
        slug_parsed = parse_slug(url)
        check = cross_check(parsed, slug_parsed)

        confidence = parsed.confidence
        if check.get("agree") is True:
            confidence = min(1.0, confidence + 0.05)
        elif check.get("agree") is False:
            # 交叉校验失败：显著降置信度，交由校验层转人工，不静默采信
            confidence = max(0.0, confidence - 0.4)

        # 锚文本缺失时退化为 slug 判定
        doc_type = parsed.doc_type
        if doc_type == DOC_OTHER and slug_parsed and slug_parsed.doc_type != DOC_OTHER:
            doc_type = slug_parsed.doc_type
            confidence = slug_parsed.confidence

        year = parsed.year if parsed.year is not None else (slug_parsed.year if slug_parsed else None)
        series = (
            parsed.series
            if parsed.series is not None
            else (slug_parsed.series if slug_parsed else None)
        )
        paper_code = (
            parsed.paper_code
            if parsed.paper_code is not None
            else (slug_parsed.paper_code if slug_parsed else None)
        )
        is_specimen = parsed.is_specimen or bool(slug_parsed and slug_parsed.is_specimen)
        component, variant = split_paper_code(paper_code)

        evidence: dict[str, Any] = {
            "label_raw": raw_label,
            "label_normalized": label,
            "label_signals": parsed.evidence,
            "slug_signals": slug_parsed.evidence if slug_parsed else None,
            "cross_check": check,
        }

        meta: dict[str, Any] = {
            "subject_code": syllabus.code,
            "subject_slug": syllabus.slug,
            "subject_title": syllabus.title,
            "qualification_key": syllabus.qualification_key,
            "qualification_name": syllabus.qualification_name,
            "year": year,
            "series": series,
            "paper_code": paper_code,
            "component": component,
            "variant": variant,
            "is_specimen": is_specimen,
            "level": self._level_for(syllabus.qualification_key),
            "doc_type": doc_type,
        }

        return DiscoveredResource(
            url=url,
            label=label or None,
            doc_type=doc_type,
            confidence=round(confidence, 3),
            meta=meta,
            evidence=evidence,
            page_url=page_url,
        )

    @staticmethod
    def _level_for(qualification_key: str) -> str:
        return {
            "cambridge-igcse": "IGCSE",
            "cambridge-as-a-level": "AS/A Level",
            "cambridge-o-level": "O Level",
        }.get(qualification_key, qualification_key)

    # -- 统一概念映射 -----------------------------------------------------

    def normalize_metadata(self, resource: DiscoveredResource) -> dict[str, Any]:
        """统一字段与考试局特有属性并存，不因统一而丢失信息。"""
        m = dict(resource.meta)
        return {
            "doc_type": resource.doc_type,
            "year": m.get("year"),
            "series": m.get("series"),
            "paper_code": m.get("paper_code"),
            "component": m.get("component"),
            "variant": m.get("variant"),
            "level": m.get("level"),
            "subject_code": m.get("subject_code"),
            # Cambridge 特有
            "cambridge": {
                "syllabus_slug": m.get("subject_slug"),
                "is_specimen": m.get("is_specimen"),
                "paper_code_raw": m.get("paper_code"),
            },
        }
