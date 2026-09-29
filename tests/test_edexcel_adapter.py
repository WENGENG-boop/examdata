"""Pearson Edexcel 适配器测试。

重点覆盖两处最容易静默出错的地方：
1. **分片**：servlet 的 hitsPerPage 硬上限 1000，page 参数被忽略。
   撞上限不切分就会静默丢数据——这是最难发现的一类 bug，
   因为返回的清单看起来完全正常，只是少了一部分。
2. **门禁判定**：gating 字段实测恒为 false，必须用 URL 前缀判定。
"""

from __future__ import annotations

import json

import pytest

from examdata.adapters.edexcel.adapter import (
    HITS_CAP,
    MAX_SHARD_DEPTH,
    ShardExhausted,
    EdexcelAdapter,
)
from examdata.adapters.edexcel.classify import (
    extract_metadata,
    is_gated,
    map_doc_type,
    normalize_exam_series,
    series_year,
)
from examdata.adapters.base import SyllabusRef


def _rec(url: str, categories: list[str], title: str = "T") -> dict:
    return {
        "url": url,
        "title": title,
        "extension": "pdf",
        "category": categories,
        "gating": False,
        "objectID": url,
    }


class ScriptedFetcher:
    """按 URL 里的 fq 参数回放预置记录，用于测试分片逻辑。

    真实 servlet 的行为就是"给定 fq 返回一批记录"，这里精确复现该契约，
    包括 hitsPerPage 上限——否则测不出分片是否正确。
    """

    def __init__(self, responder) -> None:
        self.responder = responder
        self.calls: list[str] = []

    def get_text(self, url: str, **kwargs):
        self.calls.append(url)
        records = self.responder(url)
        return _R(status=200, text=json.dumps({"searchResults": {"algoliaRecords": records}}))

    def get(self, url: str, **kwargs):
        return self.get_text(url, **kwargs)


class _R:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self.text = text
        self.ok = 200 <= status < 300


def _fq_of(url: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return (parse_qs(urlparse(url).query).get("fq") or [""])[0]


# --------------------------------------------------------------------------
# 分片
# --------------------------------------------------------------------------


def test_small_result_is_not_sharded():
    """不到上限时不应触发分片（避免无谓请求）。"""
    recs = [_rec(f"/content/dam/pdf/a{i}.pdf", ["Pearson-UK:Document-Type/Question-paper"]) for i in range(5)]
    f = ScriptedFetcher(lambda url: recs)
    adapter = EdexcelAdapter(f)
    out = list(adapter._query_all(["T"], label="t"))
    assert len(out) == 5
    assert len(f.calls) == 1, "未撞上限就不该分片"


def test_at_cap_triggers_sharding():
    """正好撞上限必须分片，否则静默截断。

    模拟真实 servlet：顶层查询返回恰好 HITS_CAP 条（被截断），
    按考季细分后各返回该考季的完整子集。
    """
    per_series = HITS_CAP // 2

    def responder(url: str):
        fq = _fq_of(url)
        for series in ("June 2022", "June 2021"):
            if f"Exam-Series/{series}" in fq:
                return [
                    _rec(f"/content/dam/pdf/{series}-{i}.pdf", [])
                    for i in range(per_series)
                ]
        # 顶层：撞上限的截断结果（只有两个考季各一半）
        out = []
        for series in ("June 2022", "June 2021"):
            out += [
                _rec(
                    f"/content/dam/pdf/{series}-{i}.pdf",
                    [f"Pearson-UK:Exam-Series/{series}"],
                )
                for i in range(per_series)
            ]
        return out

    f = ScriptedFetcher(responder)
    adapter = EdexcelAdapter(f)
    out = list(adapter._query_all(["T"], label="t"))
    assert len(out) == HITS_CAP, "分片后应拿回全部记录"
    assert len(f.calls) > 1, "撞上限必须继续分片"


def test_sharding_deduplicates_overlap():
    """分片之间可能有重叠，必须按 URL 去重。"""
    def responder(url: str):
        fq = _fq_of(url)
        if "Exam-Series" in fq:
            # 两个分片故意返回同一条记录
            return [_rec("/content/dam/pdf/shared.pdf", []), _rec(f"/content/dam/pdf/{fq}.pdf", [])]
        return [
            _rec("/content/dam/pdf/shared.pdf", ["Pearson-UK:Exam-Series/June 2022"]),
            _rec("/content/dam/pdf/x.pdf", ["Pearson-UK:Exam-Series/June 2021"]),
        ] + [_rec(f"/content/dam/pdf/filler{i}.pdf", []) for i in range(HITS_CAP - 2)]

    f = ScriptedFetcher(responder)
    adapter = EdexcelAdapter(f)
    out = list(adapter._query_all(["T"], label="t"))
    urls = [r["url"] for r in out]
    assert len(urls) == len(set(urls)), "分片结果必须去重"


def test_exhausted_sharding_raises_instead_of_truncating():
    """切不动又撞上限时必须报错，绝不返回被截断的结果。

    返回截断清单比报错更糟：上层会以为数据完整。
    """
    recs = [_rec(f"/content/dam/pdf/a{i}.pdf", []) for i in range(HITS_CAP)]
    f = ScriptedFetcher(lambda url: recs)
    adapter = EdexcelAdapter(f)
    with pytest.raises(ShardExhausted):
        list(adapter._query_all(["T"], label="t"))


def test_max_shard_depth_is_bounded():
    """分片深度必须有上界，否则病态数据会导致无限递归。"""
    assert 1 <= MAX_SHARD_DEPTH <= 6


def test_shard_prefers_exam_series_over_document_type():
    """考季基数低、分布均匀，应优先按它切分。"""
    def responder(url: str):
        fq = _fq_of(url)
        if "Exam-Series" in fq:
            return [_rec(f"/content/dam/pdf/{fq}.pdf", [])]
        out = []
        for series in ("June 2022", "June 2021"):
            out += [
                _rec(
                    f"/content/dam/pdf/{series}-{i}.pdf",
                    [f"Pearson-UK:Exam-Series/{series}",
                     "Pearson-UK:Document-Type/Question-paper"],
                )
                for i in range(HITS_CAP // 2)
            ]
        return out

    f = ScriptedFetcher(responder)
    adapter = EdexcelAdapter(f)
    list(adapter._query_all(["T"], label="t"))
    assert any("Exam-Series" in _fq_of(u) for u in f.calls[1:]), "应优先按考季分片"


# --------------------------------------------------------------------------
# facet 标签压缩
# --------------------------------------------------------------------------


def test_select_facet_tags_drops_conflicting_spec_variants():
    """互斥的 Specification-Code 变体不能全 AND——实测会把结果压到 1 条。"""
    tags = [
        "Pearson-UK:Qualification-Family/A-Level",
        "Pearson-UK:Qualification-Subject/Mathematics",
        "Pearson-UK:Specification-Code/A-Level/2017",
        "Pearson-UK:Specification-Code/al17-maths",
        "Pearson-UK:Specification-Code/A-Level/2017/al17-maths",
    ]
    picked = EdexcelAdapter.select_facet_tags(tags)
    spec = [t for t in picked if "Specification-Code" in t]
    assert len(spec) == 1, "只能保留一个 Spec-Code 变体"
    # 最具体 = 斜杠最多
    assert spec[0].count("/") == max(t.count("/") for t in tags if "Specification-Code" in t)


def test_select_facet_tags_keeps_family_and_subject():
    tags = [
        "Pearson-UK:Qualification-Family/International-GCSE",
        "Pearson-UK:Qualification-Subject/Economics",
        "Pearson-UK:Specification-Code/igcse-economics-2017",
        "Pearson-UK:Accreditation-From-date/2017",
    ]
    picked = EdexcelAdapter.select_facet_tags(tags)
    assert any("Qualification-Family" in t for t in picked)
    assert any("Qualification-Subject" in t for t in picked)
    # Accreditation-From-date 单独命中 1000+ 条，必须丢弃
    assert not any("Accreditation" in t for t in picked)


def test_select_facet_tags_handles_no_spec_code():
    tags = ["Pearson-UK:Qualification-Family/GCSE"]
    assert EdexcelAdapter.select_facet_tags(tags) == tags


# --------------------------------------------------------------------------
# 门禁判定
# --------------------------------------------------------------------------


def test_gating_field_is_ignored_in_favour_of_url():
    """实测 gating 恒为 false，判定必须靠 URL 前缀。"""
    secure = "https://qualifications.pearson.com/content/dam/secure/silver/x/4ea1-01-que.pdf"
    meta = extract_metadata([], secure)
    assert meta["is_gated"] is True, "门禁路径必须被识别，即使记录里 gating=false"


def test_public_path_is_not_gated():
    assert is_gated("/content/dam/pdf/International GCSE/Economics/2017/x.pdf") is False


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/content/dam/secure/silver/a.pdf", True),
        ("/content/dam/secure/gold/a.pdf", True),
        ("/content/dam/gold/a.pdf", True),
        ("/content/dam/silver/a.pdf", True),
        ("/content/dam/pdf/a.pdf", False),
    ],
)
def test_is_gated_prefixes(url, expected):
    assert is_gated(url) is expected


# --------------------------------------------------------------------------
# 类型与考季
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Question-paper", "question_paper"),
        ("Mark-scheme", "mark_scheme"),
        ("Mark-Scheme", "mark_scheme"),  # 实测大小写不统一
        ("Examiner-report", "examiner_report"),
        ("Modified-question-paper", "question_paper"),
        ("Specimen-paper-and-mark-scheme", "specimen_paper"),
    ],
)
def test_map_doc_type_from_category(raw, expected):
    doc_type, conf, method = map_doc_type(raw)
    assert doc_type == expected
    assert method == "category"
    assert conf >= 0.9, "结构化字段是最可信判据"


def test_map_doc_type_falls_back_to_filename():
    doc_type, conf, method = map_doc_type(None, "/x/4ea1-01-rms-20220519.pdf")
    assert doc_type == "mark_scheme"
    assert method == "filename"
    assert conf < 0.9, "文件名兜底的可信度必须低于结构化字段"


def test_map_doc_type_unknown_is_other():
    doc_type, conf, _ = map_doc_type("Something-brand-new")
    assert doc_type == "other"
    assert conf <= 0.3


@pytest.mark.parametrize(
    "raw,expected",
    [("June 2022", "june 2022"), ("June-2022", "june 2022"), ("October 2021", "october 2021")],
)
def test_normalize_exam_series(raw, expected):
    assert normalize_exam_series(raw) == expected


def test_series_year_extracted():
    assert series_year("June 2022") == 2022
    assert series_year(None) is None


def test_metadata_keeps_edexcel_specific_fields():
    """需求：不能为了统一格式而丢失原考试体系的重要属性。"""
    cats = [
        "Pearson-UK:Document-Type/Question-paper",
        "Pearson-UK:Exam-Series/June 2022",
        "Pearson-UK:Unit/4EC1 01",
        "Pearson-UK:Specification-Code/igcse-economics-2017",
    ]
    meta = extract_metadata(cats, "/content/dam/pdf/x.pdf")
    assert meta["doc_type"] == "question_paper"
    assert meta["series"] == "june 2022"
    assert meta["year"] == 2022
    assert meta["unit"] == "4EC1 01"
    assert meta["paper_code"] == "4EC1 01"
    assert meta["edexcel"]["specification_code"] == "igcse-economics-2017"
    assert meta["edexcel"]["unit"] == "4EC1 01"


# --------------------------------------------------------------------------
# 契约：不绕过访问控制
# --------------------------------------------------------------------------


def test_adapter_declares_partial_public():
    """Edexcel 有登录墙（近 12 个月的 QP/MS/ER），不能宣称完全公开。"""
    assert EdexcelAdapter.accessibility == "partial_public"
    assert EdexcelAdapter.key == "edexcel"


def test_adapter_never_fetches_gated_files():
    """适配器只枚举清单，不去抓门禁文件——robots 也会拦。"""
    import inspect

    src = inspect.getsource(EdexcelAdapter)
    # 不应出现对 secure 路径的主动下载逻辑
    assert "dam/secure" not in src, "适配器不应主动访问门禁路径"
