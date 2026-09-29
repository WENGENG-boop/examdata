"""Pearson 站内 Algolia servlet 的只读访问层。

Edexcel 的页面是 AngularJS 空壳，服务端 HTML 里没有任何 PDF 锚点，
资源清单只能通过站内 servlet 拿 JSON。本模块把「构造 fq -> 查询 ->
撞上限分片 -> 去重」抽出来，供两处复用：资源枚举（adapter）与
按科目/考季/卷号精确定位（paperqa）。

**为什么必须分片**：servlet 的 `page` 参数被忽略（实测），只有
`hitsPerPage` 有效且硬上限 1000。撞上限不切分就会静默丢数据——这是
最难发现的一类 bug，因为返回的清单看起来完全正常，只是少了一部分。
切到 `MAX_SHARD_DEPTH` 仍饱和、且没有可用切分维度时就抛
`ShardExhausted`，绝不返回可能被截断的结果。

**残余局限（如实记录）**：分片维度取自被截断响应里出现过的 facet 取值，
如果截断恰好整段丢掉了某个考季，该考季不会出现在分片列表里，分片就补不回
来。因此分片降低截断风险但**不能证明穷尽**。paperqa 的查询都带
科目+考季+系列三重条件（实测十几条，远低于上限），不依赖分片；
适配器的全量枚举若命中上限，宁可报错也不返回"看起来完整"的清单。

**为什么不用 `NOT id:"/content/dam/secure*"`**：`id` 不是 servlet 的
可过滤属性，该过滤器静默匹配空集，`NOT 空集` 等于全集（实测 Economics
全量 1533 条，加 `NOT` 后仍 1533 条，且返回里照样混着门禁路径）。
门禁只能靠 URL 前缀在下载时判定，见 `paperqa/sources/pearson.py`。
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import quote

from ...core.fetch import Fetcher

ORIGIN = "https://qualifications.pearson.com"
ALGOLIA_SERVLET = "/services/pearson/algolia/GET.servlet"

# servlet 的 hitsPerPage 硬上限。超过就必须分片，否则静默截断。
HITS_CAP = 1000
# 分片递归的最大深度。到顶仍饱和就抛错，绝不返回被截断的结果。
MAX_SHARD_DEPTH = 3

# 分片维度，按优先级排列：考季基数低、分布均匀，优先按它切。
SHARD_DIMENSIONS: tuple[str, ...] = (
    "Pearson-UK:Exam-Series/",
    "Pearson-UK:Document-Type/",
)


class ShardExhausted(RuntimeError):
    """分片到最大深度仍撞上限——继续下去会静默丢数据，必须显式失败。"""


class ServletError(RuntimeError):
    """servlet 不可用或返回了无法解析的内容。"""


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


def fetch_records(
    fetcher: Fetcher, tags: Iterable[str | Sequence[str]], hits: int = HITS_CAP
) -> list[dict[str, Any]]:
    """查一次 servlet，返回原始记录。

    传输或解析失败一律抛 `ServletError`——静默返回空列表会让调用方
    把"查询失败"当成"这批没有记录"，进而把缺失当成完整性。
    """
    url = f"{ORIGIN}{ALGOLIA_SERVLET}?fq={quote(build_fq(tags))}&hitsPerPage={hits}"
    res = fetcher.get_text(url)
    if not res.ok or not res.text:
        raise ServletError(f"Pearson catalogue unavailable (HTTP {res.status})")
    try:
        data = json.loads(res.text)
        records = ((data or {}).get("searchResults") or {}).get("algoliaRecords")
    except (ValueError, AttributeError) as exc:
        raise ServletError("Invalid Pearson catalogue response") from exc
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ServletError("Invalid Pearson catalogue response")
    return records


def facet_values(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """统计这批记录里各 facet 前缀下的取值分布。"""
    out: dict[str, set[str]] = {}
    for rec in records:
        for c in rec.get("category") or []:
            if isinstance(c, str) and "/" in c:
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
    """递归查询，保证不静默截断。"""
    tags = list(tags)
    records = fetch_records(fetcher, tags)
    if len(records) < HITS_CAP:
        yield from records
        return

    if depth >= MAX_SHARD_DEPTH:
        raise ShardExhausted(
            f"{label}: 分片深度已达 {MAX_SHARD_DEPTH} 仍撞上 {HITS_CAP} 条上限"
            f"（tags={tags}）。拒绝返回可能被截断的结果。"
        )

    facets = facet_values(records)
    for prefix in SHARD_DIMENSIONS:
        values = facets.get(prefix) or []
        if len(values) < 2:
            continue
        for value in sorted(values):
            yield from shard_records(
                fetcher, tags + [prefix + value], depth=depth + 1, label=label
            )
        return

    raise ShardExhausted(
        f"{label}: 命中 {len(records)} 条且无可用切分维度（tags={tags}）。"
        "拒绝返回可能被截断的结果。"
    )


def iter_records(
    fetcher: Fetcher, tags: Iterable[str | Sequence[str]], *, label: str = ""
) -> Iterator[dict[str, Any]]:
    """分片查询并按 URL/objectID 去重（分片之间会重叠）。"""
    seen: set[str] = set()
    for rec in shard_records(fetcher, tags, depth=0, label=label):
        key = rec.get("url") or rec.get("objectID") or ""
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        yield rec
