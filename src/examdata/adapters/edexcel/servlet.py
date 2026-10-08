"""Pearson 站内 Algolia servlet 的只读访问层。

资源枚举（adapter）与精确定位（paperqa）共用查询、响应校验和去重。
servlet 忽略 `page` 且 `hitsPerPage` 硬上限为 1000。被截断响应中的
facet 取值不能证明覆盖全部记录，因此即使可按这些取值继续切分，也必须
拒绝饱和响应。命中请求上限或 `nbHits` 表明截断时抛 `ShardExhausted`。

门禁靠 URL 前缀判定；`id` 不是 servlet 的可过滤属性，不能用它排除门禁。
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import quote

import httpx

from ...core.fetch import Fetcher

ORIGIN = "https://qualifications.pearson.com"
ALGOLIA_SERVLET = "/services/pearson/algolia/GET.servlet"

HITS_CAP = 1000
# 保留旧版分片常量的导入契约；截断响应不再用于推断完整的分片范围。
MAX_SHARD_DEPTH = 3
SHARD_DIMENSIONS: tuple[str, ...] = (
    "Pearson-UK:Exam-Series/",
    "Pearson-UK:Document-Type/",
)


class ShardExhausted(RuntimeError):
    """查询可能被截断，无法证明记录完整。"""


class ServletError(RuntimeError):
    """servlet 不可用或响应形状无效。"""


def build_fq(tags: Iterable[str | Sequence[str]]) -> str:
    """把 category 标签压成 servlet 的 fq 表达式。

    每个元素是一个 AND 子句；元素是字符串时要求该标签精确命中，
    是序列时展开成 `(category:"a" OR category:"b")`。

    OR 是必要的：同一科目在 servlet 上有两种标识方式，
    `Qualification-Subject/Economics`（科目名）与
    `Specification-Code/ial18-economics`（规格代码）。用户按哪种写法
    传进来都该命中同一批文件（实测 `Qualification-Subject/ial18-economics`
    命中 0 条，而 `Specification-Code/ial18-economics` 命中 349 条）。
    """
    clauses: list[str] = []
    for tag in tags:
        variants = [tag] if isinstance(tag, str) else [v for v in tag if v]
        if not variants:
            continue
        terms = [f"category:{json.dumps(v)}" for v in variants]
        clauses.append(terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")")
    return " AND ".join(clauses)


def validate_record(record: Any) -> None:
    if not isinstance(record, dict):
        raise ServletError("Invalid Pearson catalogue record: expected an object")
    if not isinstance(record.get("url"), str):
        raise ServletError("Invalid Pearson catalogue record: url must be a string")
    for name in ("title", "objectID", "extension"):
        value = record.get(name)
        if value is not None and not isinstance(value, str):
            raise ServletError(f"Invalid Pearson catalogue record: {name} must be a string")
    categories = record.get("category")
    if categories is not None and (
        not isinstance(categories, list) or any(not isinstance(c, str) for c in categories)
    ):
        raise ServletError("Invalid Pearson catalogue record: category must be a list of strings")


def fetch_records_for_fq(
    fetcher: Fetcher, fq: str, hits: int = HITS_CAP
) -> list[dict[str, Any]]:
    if isinstance(hits, bool) or not isinstance(hits, int) or hits < 1:
        raise ValueError("hits must be a positive integer")
    url = f"{ORIGIN}{ALGOLIA_SERVLET}?fq={quote(fq)}&hitsPerPage={hits}"
    try:
        res = fetcher.get_text(url)
    except (httpx.HTTPError, OSError) as exc:
        raise ServletError("Pearson catalogue request failed") from exc
    if not res.ok or res.status == 206 or not isinstance(res.text, str) or not res.text:
        raise ServletError(f"Pearson catalogue unavailable (HTTP {res.status})")
    try:
        data = json.loads(res.text)
    except ValueError as exc:
        raise ServletError("Invalid Pearson catalogue JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("searchResults"), dict):
        raise ServletError("Invalid Pearson catalogue response: searchResults must be an object")
    results = data["searchResults"]
    records = results.get("algoliaRecords")
    if not isinstance(records, list):
        raise ServletError("Invalid Pearson catalogue response: algoliaRecords must be a list")
    for index, record in enumerate(records):
        try:
            validate_record(record)
        except ServletError as exc:
            raise ServletError(f"Pearson catalogue record {index}: {exc}") from exc
    for container in (data, results):
        if "nbHits" not in container:
            continue
        total = container["nbHits"]
        if isinstance(total, bool) or not isinstance(total, int) or total < len(records):
            raise ServletError("Invalid Pearson catalogue response: nbHits is inconsistent")
        if total > len(records):
            raise ShardExhausted(
                f"Pearson catalogue truncated: returned {len(records)} of {total} records"
            )
    limit = min(hits, HITS_CAP)
    if len(records) >= limit:
        raise ShardExhausted(
            f"Pearson catalogue reached the {limit} record limit; completeness is unproven"
        )
    return records


def fetch_records(
    fetcher: Fetcher, tags: Iterable[str | Sequence[str]], hits: int = HITS_CAP
) -> list[dict[str, Any]]:
    """返回完整的小查询结果；传输、形状或完整性错误均显式失败。"""
    return fetch_records_for_fq(fetcher, build_fq(tags), hits)


def facet_values(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """统计这批记录里各 facet 前缀下的取值分布。"""
    out: dict[str, set[str]] = {}
    for rec in records:
        validate_record(rec)
        for c in rec.get("category") or []:
            if "/" in c:
                prefix, _, value = c.rpartition("/")
                out.setdefault(prefix + "/", set()).add(value)
    return {k: sorted(v) for k, v in out.items()}


def shard_records(
    fetcher: Fetcher,
    tags: Iterable[str | Sequence[str]],
    *,
    depth: int = 0,
    label: str = "",
) -> Iterator[dict[str, Any]]:
    """保留分片入口契约，但不以截断响应推断全部 facet。"""
    try:
        records = fetch_records(fetcher, tags)
    except (ServletError, ShardExhausted) as exc:
        if label:
            raise type(exc)(f"{label}: {exc}") from exc
        raise
    yield from records


def iter_records(
    fetcher: Fetcher, tags: Iterable[str | Sequence[str]], *, label: str = ""
) -> Iterator[dict[str, Any]]:
    """查询并按 URL/objectID 去重。"""
    seen: set[str] = set()
    for rec in shard_records(fetcher, tags, depth=0, label=label):
        key = rec.get("url") or rec.get("objectID") or ""
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        yield rec
