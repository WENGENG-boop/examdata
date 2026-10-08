"""Pearson Edexcel 适配器实现。

**与 Cambridge 的根本差异**：Edexcel 的页面是 AngularJS 空壳，
服务端 HTML 里没有任何 PDF 锚点（实测计数为 0）。资源清单只能通过
站内 Algolia servlet 拿 JSON。因此本适配器不复用 Cambridge 的锚点方案。

发现链路（三层，均已在 research/edexcel.md 实测）：
  1. 家族 -> 科目页：Algolia 上的 cq:Page 记录
       fq = type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/{FACET}"
     注意 URL 路径段与 facet 家族名**不同名**，混用会静默返回 0 结果。
  2. 科目页 -> facet 标签：从 .html 页的 facetListCtrl data-ng-init 抽
     （.coursematerials.html 页不含标签）
  3. facet 标签 -> 资源：Algolia servlet 返回结构化记录

合规：
  - robots 由 Fetcher 强制。/content/dam/secure/** 被 robots 禁止，
    适配器不会去抓这些文件；但**资源清单里仍会收录**它们并标记 is_gated，
    因为"知道它存在但需要登录"本身是有价值的信息（需求要求识别登录墙档）。
  - 全程只读公开页面与公开 servlet，无登录、无绕过。
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional
from urllib.parse import urlsplit

import httpx

from ...core.fetch import Fetcher
from ..base import BoardAdapter, DiscoveredResource, SyllabusRef
from ..registry import register
from .classify import extract_metadata
from .servlet import (
    ALGOLIA_SERVLET,
    HITS_CAP,
    MAX_SHARD_DEPTH,
    ORIGIN,
    ServletError,
    ShardExhausted,
    facet_values,
    fetch_records,
    fetch_records_for_fq,
    iter_records,
    shard_records,
    validate_record,
)

# 重新导出，保持既有调用点与测试的导入路径不变。
__all__ = [
    "ALGOLIA_SERVLET",
    "HITS_CAP",
    "MAX_SHARD_DEPTH",
    "ORIGIN",
    "ShardExhausted",
    "EdexcelAdapter",
]

# 家族定义：(URL 路径段, Algolia facet 家族名, 显示名, 落地页)
# URL 段与 facet 名不同名是这个站点最容易踩的坑。
FAMILIES: list[dict[str, str]] = [
    {
        "url_family": "edexcel-international-gcses",
        "facet_family": "International-GCSE",
        "qualification_key": "edexcel-igcse",
        "qualification_name": "Pearson Edexcel International GCSE",
        "level": "IGCSE",
    },
    {
        "url_family": "edexcel-international-advanced-levels",
        "facet_family": "International-Advanced-Level",
        "qualification_key": "edexcel-ial",
        "qualification_name": "Pearson Edexcel International A Level",
        "level": "IAL",
    },
    {
        "url_family": "edexcel-a-levels",
        "facet_family": "A-Level",
        "qualification_key": "edexcel-gce-a-level",
        "qualification_name": "Pearson Edexcel GCE A Level",
        "level": "A Level",
    },
    {
        "url_family": "edexcel-gcses",
        "facet_family": "GCSE",
        "qualification_key": "edexcel-gcse",
        "qualification_name": "Pearson Edexcel GCSE",
        "level": "GCSE",
    },
]

CQ_PAGE_PAGE_SIZE = 2000

RE_NG_INIT_FACETS = re.compile(
    r"""data-ng-controller="facetListCtrl"[^>]*data-ng-init="init\('([^']*)',\s*'\[([^\]]*)\]'""",
    re.I | re.S,
)
RE_SUBJECT_SLUG = re.compile(r"^[a-z0-9\-]+$", re.I)


@register
class EdexcelAdapter(BoardAdapter):
    key = "edexcel"
    board_name = "Pearson Edexcel"
    homepage = ORIGIN
    accessibility = "partial_public"

    def __init__(self, fetcher: Fetcher) -> None:
        super().__init__(fetcher)

    # -- 入口 ------------------------------------------------------------

    def index_sources(self) -> list[tuple[str, str]]:
        return [
            ("family_landing", f"{ORIGIN}/en/qualifications/{f['url_family']}.html")
            for f in FAMILIES
        ]

    # -- 第一层：科目枚举 ------------------------------------------------

    def discover_syllabuses(self) -> Iterator[SyllabusRef]:
        seen: set[str] = set()
        for fam in FAMILIES:
            for ref in self._syllabuses_for_family(fam):
                if ref.slug in seen:
                    continue
                seen.add(ref.slug)
                yield ref

    def _syllabuses_for_family(self, fam: dict[str, str]) -> list[SyllabusRef]:
        fq = (
            'type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/%s"'
            % fam["facet_family"]
        )
        try:
            records = fetch_records_for_fq(self.fetcher, fq, CQ_PAGE_PAGE_SIZE)
        except (ServletError, ShardExhausted) as exc:
            raise type(exc)(f"{fam['qualification_key']}: {exc}") from exc
        prefix = f"/en/qualifications/{fam['url_family']}/"
        out: dict[str, SyllabusRef] = {}
        for rec in records:
            url = (rec.get("url") or "").strip()
            if not url.startswith(prefix) or not url.endswith(".html"):
                continue
            tail = url[len(prefix):]
            if "/" in tail:  # 只要一级科目页
                continue
            slug = tail[: -len(".html")]
            if not RE_SUBJECT_SLUG.match(slug):
                continue
            title = (rec.get("title") or slug).strip()
            # slug 末尾 4 位是资格版本年，不是科目代码
            m = re.search(r"-(\d{4})(?:-|$)", slug)
            out.setdefault(
                slug,
                SyllabusRef(
                    slug=slug,
                    code=slug,
                    title=title or slug,
                    qualification_key=fam["qualification_key"],
                    qualification_name=fam["qualification_name"],
                    source_url=f"{ORIGIN}{url}",
                    attrs={
                        "url_family": fam["url_family"],
                        "facet_family": fam["facet_family"],
                        "level": fam["level"],
                        "version_year": int(m.group(1)) if m else None,
                        # .coursematerials.html 页不含 facet 标签，必须用 .html
                        "subject_page_url": f"{ORIGIN}{url}",
                    },
                ),
            )
        return sorted(out.values(), key=lambda r: r.slug)

    # -- 第二层：科目页 -> facet 标签 ------------------------------------

    def subject_facet_tags(self, syllabus: SyllabusRef) -> Optional[list[str]]:
        url = syllabus.attrs.get("subject_page_url") or syllabus.source_url
        try:
            res = self.fetcher.get_text(url)
        except (httpx.HTTPError, OSError) as exc:
            raise ServletError(f"{syllabus.slug}: Pearson subject page request failed") from exc
        if not res.ok or res.status == 206 or not isinstance(res.text, str) or not res.text:
            raise ServletError(
                f"{syllabus.slug}: Pearson subject page unavailable (HTTP {res.status})"
            )
        m = RE_NG_INIT_FACETS.search(res.text)
        if not m:
            raise ServletError(f"{syllabus.slug}: Pearson subject page has no facet metadata")
        return [t.strip() for t in m.group(2).split(",") if t.strip()]

    @staticmethod
    def select_facet_tags(tags: list[str]) -> list[str]:
        """把科目页给的标签压缩成一组互不冲突的查询条件。

        科目页会给出多个**互斥**的 Specification-Code 变体
        （实测 A Level 数学 2017 有 6 个）。全部 AND 起来只剩 1 条记录
        （只匹配到科目页自身），因为没有任何文档同时带全部变体。
        实测：全 AND = 1 条，压缩后 = 27 条。

        规则：保留 Family + Subject，外加最具体的单个 Specification-Code
        （斜杠最多者；同段数取最短，避开 A-Level/2017 这类泛化前缀）。
        """
        family = [t for t in tags if t.startswith("Pearson-UK:Qualification-Family/")]
        subject = [t for t in tags if t.startswith("Pearson-UK:Qualification-Subject/")]
        spec = [t for t in tags if t.startswith("Pearson-UK:Specification-Code/")]
        picked = list(family) + list(subject)
        if spec:
            picked.append(max(spec, key=lambda t: (t.count("/"), -len(t))))
        return picked

    # -- 第三层：资源枚举 ------------------------------------------------

    def discover_resources(self, syllabus: SyllabusRef) -> Iterator[DiscoveredResource]:
        tags = self.subject_facet_tags(syllabus)
        if not tags:
            return
        selected = self.select_facet_tags(tags)
        if not selected:
            raise ServletError(f"{syllabus.slug}: Pearson subject page has no usable facet metadata")
        page_url = syllabus.attrs.get("subject_page_url") or syllabus.source_url

        for rec in self._query_all(selected, label=syllabus.slug):
            res = self.build_resource(rec, syllabus, page_url)
            if res is not None:
                yield res

    def _query_all(self, tags: list[str], *, label: str) -> Iterator[dict[str, Any]]:
        yield from iter_records(self.fetcher, tags, label=label)

    def _shard(
        self, tags: list[str], *, depth: int, label: str
    ) -> Iterator[dict[str, Any]]:
        yield from shard_records(self.fetcher, tags, depth=depth, label=label)

    def _fetch(self, tags: list[str]) -> list[dict[str, Any]]:
        return fetch_records(self.fetcher, tags)

    @staticmethod
    def _facet_values(records: list[dict[str, Any]]) -> dict[str, list[str]]:
        return facet_values(records)

    @staticmethod
    def _resource_url(raw: str) -> Optional[str]:
        """servlet 的 url 是外部输入：只接受站内相对路径或本站 https 地址。

        绝对地址必须过 scheme + 主机白名单——否则被污染的 servlet 数据
        会把任意外部 URL 写进资源清单，下载环节就成了 SSRF 通道。
        """
        if any(ch in raw for ch in "\\\r\n\t"):
            return None
        if raw.startswith("//"):
            return None
        if raw.startswith("/"):
            return ORIGIN + raw
        try:
            parts = urlsplit(raw)
        except ValueError:
            return None
        host = parts.netloc.lower()
        if parts.scheme == "https" and host == "qualifications.pearson.com":
            return raw
        return None

    # -- 分类与元数据 ----------------------------------------------------

    def build_resource(
        self, rec: dict[str, Any], syllabus: SyllabusRef, page_url: str
    ) -> Optional[DiscoveredResource]:
        validate_record(rec)
        raw_url = rec["url"].strip()
        if not raw_url:
            return None
        url = self._resource_url(raw_url)
        if url is None:
            return None

        meta = extract_metadata(rec.get("category") or [], url)
        meta["subject_code"] = syllabus.code
        meta["qualification_key"] = syllabus.qualification_key
        meta["level"] = syllabus.attrs.get("level")

        return DiscoveredResource(
            url=url,
            label=(rec.get("title") or "").strip() or None,
            doc_type=meta["doc_type"],
            confidence=meta["confidence"],
            meta=meta,
            evidence={
                "method": meta["classify_method"],
                "raw_document_type": meta["raw_doc_type"],
                "categories": rec.get("category") or [],
                "gated": meta["is_gated"],
                "extension": rec.get("extension"),
                "object_id": rec.get("objectID"),
                # 实测 gating 字段不可信，如实记录以便审计
                "raw_gating_field": rec.get("gating"),
            },
            page_url=page_url,
        )

    def classify(self, label: str, url: str) -> tuple[str, float, dict[str, Any]]:
        """兜底分类：只在没有 category 时使用。"""
        meta = extract_metadata([], url)
        return meta["doc_type"], meta["confidence"], {"method": meta["classify_method"]}

    def normalize_metadata(self, resource: DiscoveredResource) -> dict[str, Any]:
        m = dict(resource.meta)
        return {
            "doc_type": resource.doc_type,
            "year": m.get("year"),
            "series": m.get("series"),
            # Edexcel 的 unit 就是试卷标识（如 4WAC1/01），映射到统一字段 paper_code
            "paper_code": m.get("paper_code") or m.get("unit"),
            "component": None,
            "variant": None,
            "level": m.get("level"),
            "subject_code": m.get("subject_code"),
            # Edexcel 特有
            "edexcel": m.get("edexcel") or {},
        }
