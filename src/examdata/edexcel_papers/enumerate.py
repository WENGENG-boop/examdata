"""Edexcel IAL 资源枚举。

servlet 单查询硬上限 1000 条：命中上限即抛 ``ShardExhausted``。为了拿到
完整清单，按「全查 -> doc-type 分片 -> 考季网格」逐级退让；任何一级仍
饱和就显式失败，绝不把截断结果当成完整清单。

只保留 ``Question-paper`` 与 ``Mark-scheme`` 两类：``Modified-question-paper``
（给教师改题用的版本）与 ``Pre-release-material`` 等一概排除。

catalog 落在 ``<data_dir>/edexcel_papers/catalog/<slug>.json``：
一次枚举、多次使用；``run`` 缺 catalog 时会自动补一次。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from ..adapters.base import DiscoveredResource, SyllabusRef
from ..adapters.edexcel.adapter import EdexcelAdapter
from ..adapters.edexcel.classify import category_value
from ..adapters.edexcel.servlet import (
    ORIGIN,
    ServletError,
    ShardExhausted,
    fetch_records,
)
from ..core.config import Settings, get_settings
from ..core.fetch import Fetcher

# IAL 21 个科目：slug -> 英文名。slug 与库内 subject.code 一致。
IAL_SUBJECTS: dict[str, str] = {
    "ial-accounting": "Accounting",
    "ial-arabic": "Arabic",
    "ial-englang": "English Language",
    "ial-englit": "English Literature",
    "ial-french": "French",
    "ial-geography": "Geography",
    "ial-german": "German",
    "ial-greek": "Greek",
    "ial-history": "History",
    "ial-law": "Law",
    "ial-maths": "Mathematics",
    "ial-psychology": "Psychology",
    "ial-spanish": "Spanish",
    "ial18-biology": "Biology",
    "ial18-business": "Business",
    "ial18-chemistry": "Chemistry",
    "ial18-economics": "Economics",
    "ial18-it": "Information Technology",
    "ial18-mathematics": "Mathematics",
    "ial18-physics": "Physics",
    "ial26-computer-science": "Computer Science",
}

# servlet 的 Document-Type 取值（原样，比较前 lower）。
DOC_TYPES: tuple[str, ...] = ("Question-paper", "Mark-scheme")
_KEEP: frozenset[str] = frozenset({"question-paper", "mark-scheme"})

# 考季网格：IAL 的考季取值。年份上限留出未来两年。
SEASONS: tuple[str, ...] = ("January", "June", "October", "November")
SEASON_YEARS: range = range(2015, 2028)

CATALOG_DIRNAME = "edexcel_papers"


def syllabus_ref(slug: str) -> SyllabusRef:
    """构造一个 IAL 科目的 SyllabusRef（不联网）。"""
    title = IAL_SUBJECTS.get(slug, slug)
    page_url = f"{ORIGIN}/en/qualifications/edexcel-international-advanced-levels/{slug}.html"
    return SyllabusRef(
        slug=slug,
        code=slug,
        title=title,
        qualification_key="edexcel-ial",
        qualification_name="Pearson Edexcel International A Level",
        source_url=page_url,
        attrs={"subject_page_url": page_url, "level": "IAL"},
    )


def resolve_tags(
    adapter: EdexcelAdapter, ref: SyllabusRef
) -> tuple[list[str], str, list[str]]:
    """取 servlet 查询标签。

    首选科目页的 facet 元数据；页面改版/失效时退回
    ``Pearson-UK:Specification-Code/<slug>``（实测该标签能命中该科全部文件）。
    """
    notes: list[str] = []
    try:
        raw = adapter.subject_facet_tags(ref)
        selected = EdexcelAdapter.select_facet_tags(list(raw or []))
        if selected:
            return selected, "subject_page", notes
        notes.append("subject page facet list was empty; used specification-code fallback")
    except Exception as exc:  # 页面改版、网络、解析失败一律退让到兜底标签
        notes.append(f"subject facet lookup failed: {exc}")
    return [f"Pearson-UK:Specification-Code/{ref.slug}"], "fallback", notes


def _fetch(fetcher: Fetcher, tags: list[str], *extra: str) -> list[dict[str, Any]]:
    """单次查询。extra 的每个元素都是独立的 AND 子句。

    不能把 extra 合并成一个 list：``build_fq`` 会把 list 元素展开成 OR 组，
    语义完全不同。
    """
    return fetch_records(fetcher, [*tags, *extra])


def query_records(
    fetcher: Fetcher, tags: list[str], *, label: str = ""
) -> tuple[list[dict[str, Any]], str]:
    """查询并返回 (records, mode)，mode ∈ {"full", "doc-type", "season-grid"}。"""
    try:
        return _fetch(fetcher, tags), "full"
    except ShardExhausted:
        pass

    sharded: list[dict[str, Any]] = []
    try:
        for doc_type in DOC_TYPES:
            sharded.extend(_fetch(fetcher, tags, f"Pearson-UK:Document-Type/{doc_type}"))
    except ShardExhausted:
        pass
    else:
        return dedup_records(sharded), "doc-type"

    grid: list[dict[str, Any]] = []
    for season in SEASONS:
        for year in SEASON_YEARS:
            series = f"Pearson-UK:Exam-Series/{season}-{year}"
            for doc_type in DOC_TYPES:
                try:
                    grid.extend(
                        _fetch(fetcher, tags, series, f"Pearson-UK:Document-Type/{doc_type}")
                    )
                except ShardExhausted as exc:
                    prefix = f"{label}: " if label else ""
                    raise ShardExhausted(
                        f"{prefix}season grid exhausted at {season} {year} ({doc_type}): {exc}"
                    ) from exc
    return dedup_records(grid), "season-grid"


def dedup_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 url（缺失时用 objectID）去重，保留首次出现。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for rec in records:
        key = rec.get("url") or rec.get("objectID")
        if key:
            if key in seen:
                continue
            seen.add(key)
        out.append(rec)
    return out


def keep_qp_ms(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """只保留 Question-paper / Mark-scheme，排除 modified-question-paper 等。"""
    out: list[dict[str, Any]] = []
    for rec in records:
        raw = category_value(rec.get("category") or [], "Pearson-UK:Document-Type")
        if raw and raw.strip().lower() in _KEEP:
            out.append(rec)
    return out


def enumerate_subject(
    fetcher: Fetcher,
    slug: str,
    *,
    adapter: Optional[EdexcelAdapter] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """枚举一个 IAL 科目，返回可直接落盘的 catalog 字典。"""
    if slug not in IAL_SUBJECTS:
        raise ValueError(
            f"unknown IAL subject slug: {slug!r}; expected one of {sorted(IAL_SUBJECTS)}"
        )
    ref = syllabus_ref(slug)
    adapter = adapter or EdexcelAdapter(fetcher)
    page_url = ref.attrs["subject_page_url"]

    tags, tags_source, notes = resolve_tags(adapter, ref)
    records, mode = query_records(fetcher, tags, label=slug)
    kept = keep_qp_ms(dedup_records(records))

    resources: list[DiscoveredResource] = []
    for rec in kept:
        res = adapter.build_resource(rec, ref, page_url)
        if res is None:
            notes.append(f"skipped unrepresentable record: {rec.get('url')}")
            continue
        resources.append(res)
    if limit is not None and limit > 0:
        resources = resources[:limit]

    counts = {
        "records": len(kept),
        "resources": len(resources),
        "question_papers": sum(1 for r in resources if r.doc_type == "question_paper"),
        "mark_schemes": sum(1 for r in resources if r.doc_type == "mark_scheme"),
        "gated": sum(1 for r in resources if r.meta.get("is_gated")),
    }
    spec_variants = sorted(
        {
            value
            for rec in kept
            for value in [
                category_value(rec.get("category") or [], "Pearson-UK:Specification-Code")
            ]
            if value
        }
    )
    return {
        "slug": slug,
        "code": ref.code,
        "title": ref.title,
        "qualification_key": ref.qualification_key,
        "qualification_name": ref.qualification_name,
        "source_url": ref.source_url,
        "tags": tags,
        "tags_source": tags_source,
        "spec_variants": spec_variants,
        "query_mode": mode,
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
        "counts": counts,
        "resources": [asdict(r) for r in resources],
    }


def catalog_path(settings: Settings, slug: str) -> Path:
    return settings.data_dir / CATALOG_DIRNAME / "catalog" / f"{slug}.json"


def save_catalog(catalog: dict[str, Any], settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    path = catalog_path(settings, catalog["slug"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def load_catalog(settings: Settings, slug: str) -> Optional[dict[str, Any]]:
    path = catalog_path(settings, slug)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_resources(catalog: dict[str, Any]) -> list[DiscoveredResource]:
    return [DiscoveredResource(**d) for d in catalog.get("resources") or []]
