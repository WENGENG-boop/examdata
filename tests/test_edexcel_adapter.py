"""Pearson Edexcel 适配器测试。

重点覆盖几处最容易静默出错的地方：
1. **完整性**：servlet 的 hitsPerPage 硬上限 1000，page 参数被忽略。
   截断响应里的 facet 不能证明分片穷尽，撞上限必须显式失败。
2. **门禁判定**：gating 字段实测恒为 false，必须用 URL 前缀判定。
3. **URL 白名单**：servlet 返回的 url 是不可信输入，站外地址必须被丢弃，
   否则下载环节就成了 SSRF 通道。
4. **身份键**：同一份文档换路径（公开 <-> 门禁）后身份必须不变，
   否则会重复入库。
"""

from __future__ import annotations

import json

import httpx
import pytest

from examdata.adapters.edexcel.adapter import (
    CQ_PAGE_PAGE_SIZE,
    FAMILIES,
    HITS_CAP,
    MAX_SHARD_DEPTH,
    ORIGIN,
    ShardExhausted,
    EdexcelAdapter,
)
from examdata.adapters.edexcel.servlet import ServletError, fetch_records
from examdata.adapters.edexcel.classify import (
    extract_metadata,
    identity_parts,
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
    """按 URL 里的 fq 参数回放预置记录，不发网络请求。"""

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


class ResponseFetcher:
    def __init__(self, response: _R) -> None:
        self.response = response
        self.calls: list[str] = []

    def get_text(self, url: str, **kwargs):
        self.calls.append(url)
        return self.response


# --------------------------------------------------------------------------
# 完整性
# --------------------------------------------------------------------------


def test_small_result_is_not_sharded():
    """不到上限时不应触发分片（避免无谓请求）。"""
    recs = [_rec(f"/content/dam/pdf/a{i}.pdf", ["Pearson-UK:Document-Type/Question-paper"]) for i in range(5)]
    f = ScriptedFetcher(lambda url: recs)
    adapter = EdexcelAdapter(f)
    out = list(adapter._query_all(["T"], label="t"))
    assert len(out) == 5
    assert len(f.calls) == 1, "未撞上限就不该分片"


def test_at_cap_fails_closed():
    """正好撞上限必须失败，不能从截断响应推断完整的分片范围。"""
    recs = [
        _rec(f"/content/dam/pdf/a{i}.pdf", ["Pearson-UK:Exam-Series/June 2022"])
        for i in range(HITS_CAP)
    ]
    f = ScriptedFetcher(lambda url: recs)
    with pytest.raises(ShardExhausted, match="limit"):
        list(EdexcelAdapter(f)._query_all(["T"], label="t"))
    assert len(f.calls) == 1


def test_small_result_deduplicates_by_url():
    """合法的小结果里重复 URL 也不能重复产出。"""
    recs = [
        _rec("/content/dam/pdf/shared.pdf", []),
        _rec("/content/dam/pdf/shared.pdf", []),
        _rec("/content/dam/pdf/other.pdf", []),
    ]
    f = ScriptedFetcher(lambda url: recs)
    out = list(EdexcelAdapter(f)._query_all(["T"], label="t"))
    assert [r["url"] for r in out] == [
        "/content/dam/pdf/shared.pdf",
        "/content/dam/pdf/other.pdf",
    ]


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


def test_truncated_result_does_not_guess_shard_facets():
    """截断响应即使带多个 facet，也必须拒绝猜测缺失分片。"""
    recs = [
        _rec(
            f"/content/dam/pdf/a{i}.pdf",
            [f"Pearson-UK:Exam-Series/June {2020 + i % 2}"],
        )
        for i in range(HITS_CAP)
    ]
    f = ScriptedFetcher(lambda url: recs)
    with pytest.raises(ShardExhausted):
        list(EdexcelAdapter(f)._query_all(["T"], label="t"))
    assert len(f.calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        _R(500, "{}"),
        _R(200, "not-json"),
        _R(200, json.dumps({"searchResults": []})),
        _R(200, json.dumps({"searchResults": {"algoliaRecords": {}}})),
        _R(200, json.dumps({"searchResults": {"algoliaRecords": [None]}})),
    ],
)
def test_servlet_errors_are_not_silent(response):
    with pytest.raises(ServletError):
        fetch_records(ResponseFetcher(response), ["T"])


def test_nb_hits_proves_truncation():
    body = json.dumps({
        "searchResults": {
            "nbHits": 2,
            "algoliaRecords": [_rec("/content/dam/pdf/a.pdf", [])],
        }
    })
    with pytest.raises(ShardExhausted, match="truncated"):
        fetch_records(ResponseFetcher(_R(200, body)), ["T"])


@pytest.mark.parametrize(
    "response",
    [_R(503, "unavailable"), _R(206, "partial"), _R(200, ""), _R(200, "<html></html>")],
)
def test_subject_page_failure_is_observable(response):
    fetcher = ResponseFetcher(response)
    adapter = EdexcelAdapter(fetcher)
    with pytest.raises(ServletError, match="economics-2017"):
        list(adapter.discover_resources(_syllabus()))
    assert fetcher.calls == [_syllabus().source_url]


@pytest.mark.parametrize(
    "payload",
    [None, [], 0, False, {}, {"searchResults": None}, {"searchResults": {}},
     {"searchResults": {"algoliaRecords": None}}],
)
def test_catalogue_envelope_errors_are_explicit(payload):
    fetcher = ResponseFetcher(_R(200, json.dumps(payload)))
    adapter = EdexcelAdapter(fetcher)
    with pytest.raises(ServletError):
        adapter._fetch(["T"])
    with pytest.raises(ServletError, match="edexcel-igcse"):
        adapter._syllabuses_for_family(FAMILIES[0])


@pytest.mark.parametrize(
    "record",
    [None, [], {}, {"url": None}, {"url": 7}, {"url": []},
     {"url": "/a.pdf", "title": []}, {"url": "/a.pdf", "objectID": []},
     {"url": "/a.pdf", "extension": 7}, {"url": "/a.pdf", "category": "tag"},
     {"url": "/a.pdf", "category": {}}, {"url": "/a.pdf", "category": [None]}],
)
def test_record_shape_errors_are_explicit_before_yield(record):
    records = [_rec("/content/dam/pdf/valid.pdf", []), record]
    adapter = EdexcelAdapter(ScriptedFetcher(lambda url: records))
    with pytest.raises(ServletError, match="record 1"):
        next(adapter._query_all(["T"], label="economics-2017"))
    with pytest.raises(ServletError):
        adapter._syllabuses_for_family(FAMILIES[0])
    with pytest.raises(ServletError):
        adapter.build_resource(record, _syllabus(), _syllabus().source_url)


@pytest.mark.parametrize("status", [0, 206, 403, 404, 500])
def test_family_http_errors_are_not_empty_catalogues(status):
    fetcher = ResponseFetcher(_R(status, json.dumps({"searchResults": {"algoliaRecords": []}})))
    with pytest.raises(ServletError, match=f"HTTP {status}"):
        list(EdexcelAdapter(fetcher).discover_syllabuses())


@pytest.mark.parametrize("at_root", [False, True])
def test_nb_hits_truncation_is_explicit_even_below_cap(at_root):
    results = {"algoliaRecords": [_rec("/content/dam/pdf/a.pdf", [])]}
    payload = {"searchResults": results}
    (payload if at_root else results)["nbHits"] = 2
    adapter = EdexcelAdapter(ResponseFetcher(_R(200, json.dumps(payload))))
    with pytest.raises(ShardExhausted, match="returned 1 of 2"):
        next(adapter._query_all(["T"], label="t"))
    with pytest.raises(ShardExhausted, match="edexcel-igcse"):
        adapter._syllabuses_for_family(FAMILIES[0])


@pytest.mark.parametrize("total", [None, "1", True, -1, 0])
def test_invalid_nb_hits_is_not_a_valid_empty_result(total):
    payload = {"searchResults": {
        "algoliaRecords": [_rec("/content/dam/pdf/a.pdf", [])], "nbHits": total,
    }}
    with pytest.raises(ServletError, match="nbHits"):
        fetch_records(ResponseFetcher(_R(200, json.dumps(payload))), ["T"])


def test_family_query_checks_the_actual_hard_cap_and_preserves_fq():
    records = [
        _rec(f"/en/qualifications/edexcel-international-gcses/subject-{i}.html", [])
        for i in range(HITS_CAP)
    ]
    fetcher = ScriptedFetcher(lambda url: records)
    with pytest.raises(ShardExhausted, match="limit"):
        EdexcelAdapter(fetcher)._syllabuses_for_family(FAMILIES[0])
    assert f"hitsPerPage={CQ_PAGE_PAGE_SIZE}" in fetcher.calls[0]
    assert _fq_of(fetcher.calls[0]) == (
        'type:"cq:Page" AND category:"Pearson-UK:Qualification-Family/International-GCSE"'
    )


def test_legal_empty_catalogue_is_preserved():
    adapter = EdexcelAdapter(ScriptedFetcher(lambda url: []))
    assert adapter._fetch(["T"]) == []
    assert list(adapter.discover_syllabuses()) == []
    assert list(EdexcelAdapter(ReplayFetcher([], ["Pearson-UK:Qualification-Subject/Economics"]))
                .discover_resources(_syllabus())) == []


def test_explicit_empty_facets_do_not_query_unfiltered_catalogue():
    fetcher = ReplayFetcher([], [])
    assert list(EdexcelAdapter(fetcher).discover_resources(_syllabus())) == []
    assert fetcher.calls == [_syllabus().source_url]


def test_unusable_facets_do_not_query_unfiltered_catalogue():
    fetcher = ReplayFetcher([], ["Pearson-UK:Accreditation-From-date/2017"])
    with pytest.raises(ServletError, match="no usable facet"):
        list(EdexcelAdapter(fetcher).discover_resources(_syllabus()))
    assert fetcher.calls == [_syllabus().source_url]


@pytest.mark.parametrize("family", FAMILIES)
def test_family_pages_are_filtered_deduplicated_and_sorted(family):
    prefix = f"/en/qualifications/{family['url_family']}/"
    records = [
        _rec(prefix + "zoology-2022.html", []),
        _rec(prefix + "economics-2017.html", [], "Economics"),
        _rec(prefix + "economics-2017.html", [], "duplicate"),
        _rec(prefix + "economics-2017/subpage.html", []),
        _rec(prefix + "economics-2017.coursematerials.html", []),
        _rec("/en/qualifications/unrelated/subject.html", []),
    ]
    refs = EdexcelAdapter(ScriptedFetcher(lambda url: records))._syllabuses_for_family(family)
    assert [r.slug for r in refs] == ["economics-2017", "zoology-2022"]
    assert refs[0].title == "Economics"
    assert refs[0].qualification_key == family["qualification_key"]
    assert refs[0].attrs["version_year"] == 2017


@pytest.mark.parametrize("subject_page", [False, True])
def test_transport_errors_are_wrapped_with_a_cause(subject_page):
    def handler(request):
        raise httpx.ConnectError("offline failure", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        class TransportFetcher:
            def get_text(self, url, **kwargs):
                response = client.get(url)
                return _R(response.status_code, response.text)

        adapter = EdexcelAdapter(TransportFetcher())
        with pytest.raises(ServletError, match="request failed") as caught:
            if subject_page:
                list(adapter.discover_resources(_syllabus()))
            else:
                adapter._fetch(["T"])
        assert isinstance(caught.value.__cause__, httpx.ConnectError)


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
# URL 白名单（servlet 的 url 是不可信输入）
# --------------------------------------------------------------------------

# 这些地址若被写进资源清单，下载环节就会变成 SSRF 通道。
_UNTRUSTED_URLS = [
    "https://evil.test/x.pdf",
    "http://qualifications.pearson.com/x.pdf",  # 本站主机但非 https
    "//evil.test/x.pdf",  # 协议相对地址会解析到站外主机
    "javascript:alert(1)",
    "/content/dam/pdf/back\\slash.pdf",
    "/content/dam/pdf/a\r.pdf",
    "/content/dam/pdf/a\n.pdf",
    "/content/dam/pdf/a\t.pdf",
    "https://qualifications.pearson.com.evil.test/x.pdf",  # 后缀伪装
]


@pytest.mark.parametrize("raw", _UNTRUSTED_URLS)
def test_resource_url_rejects_untrusted_input(raw):
    assert EdexcelAdapter._resource_url(raw) is None


def test_resource_url_keeps_relative_path_verbatim():
    """相对路径拼 ORIGIN，且不做归一化——实测存在带空格的路径。"""
    raw = "/content/dam/pdf/International GCSE/x.pdf"
    assert EdexcelAdapter._resource_url(raw) == ORIGIN + raw


def test_resource_url_accepts_absolute_pearson_url():
    raw = "https://qualifications.pearson.com/content/dam/pdf/a.pdf"
    assert EdexcelAdapter._resource_url(raw) == raw


def test_resource_url_host_check_is_case_insensitive():
    """主机比较前必须 lower()，否则大小写变体会绕过白名单。"""
    raw = "https://QUALIFICATIONS.PEARSON.COM/content/dam/pdf/a.pdf"
    assert EdexcelAdapter._resource_url(raw) == raw


# --------------------------------------------------------------------------
# build_resource
# --------------------------------------------------------------------------


def _syllabus() -> SyllabusRef:
    return SyllabusRef(
        slug="economics-2017",
        code="4EC1",
        title="Economics",
        qualification_key="edexcel-igcse",
        qualification_name="Pearson Edexcel International GCSE",
        source_url=f"{ORIGIN}/en/qualifications/edexcel-international-gcses/economics-2017.html",
        attrs={"level": "IGCSE"},
    )


def test_build_resource_returns_none_for_untrusted_url():
    """被污染的记录不能进清单——清单里出现站外 URL 就等于 SSRF 通道。"""
    adapter = EdexcelAdapter(ScriptedFetcher(lambda url: []))
    rec = _rec("https://evil.test/x.pdf", ["Pearson-UK:Document-Type/Question-paper"])
    assert adapter.build_resource(rec, _syllabus(), f"{ORIGIN}/p.html") is None


def test_build_resource_returns_none_for_empty_url():
    adapter = EdexcelAdapter(ScriptedFetcher(lambda url: []))
    rec = _rec("", [])
    assert adapter.build_resource(rec, _syllabus(), f"{ORIGIN}/p.html") is None


def test_build_resource_builds_public_resource():
    adapter = EdexcelAdapter(ScriptedFetcher(lambda url: []))
    rec = _rec(
        "/content/dam/pdf/International GCSE/Economics/4EC1-01-que.pdf",
        [
            "Pearson-UK:Document-Type/Question-paper",
            "Pearson-UK:Exam-Series/June 2022",
            "Pearson-UK:Unit/4EC1 01",
        ],
    )
    page_url = f"{ORIGIN}/en/qualifications/economics-2017.html"
    res = adapter.build_resource(rec, _syllabus(), page_url)
    assert res is not None
    assert res.url == ORIGIN + rec["url"]
    assert res.doc_type == "question_paper"
    assert res.label == "T"
    assert res.page_url == page_url
    assert res.meta["subject_code"] == "4EC1"
    assert res.meta["level"] == "IGCSE"
    assert res.meta["is_gated"] is False


def test_build_resource_keeps_gated_but_marks_it():
    """门禁档仍要收录（知道它存在本身有价值），但必须标记 is_gated。"""
    adapter = EdexcelAdapter(ScriptedFetcher(lambda url: []))
    rec = _rec(
        "/content/dam/secure/silver/igcse-economics/4ec1-01-que.pdf",
        ["Pearson-UK:Document-Type/Question-paper"],
    )
    res = adapter.build_resource(rec, _syllabus(), f"{ORIGIN}/p.html")
    assert res is not None
    assert res.url == ORIGIN + rec["url"]
    assert res.meta["is_gated"] is True
    assert res.evidence["gated"] is True


class ReplayFetcher:
    """subject 页回 HTML、servlet 回预置记录，用于验证整条发现链路的过滤。"""

    def __init__(self, records: list[dict], tags: list[str]) -> None:
        self.records = records
        self.tags = tags
        self.calls: list[str] = []

    def get_text(self, url: str, **kwargs):
        self.calls.append(url)
        if "algolia" in url:
            return _R(200, json.dumps({"searchResults": {"algoliaRecords": self.records}}))
        tags = ",".join(self.tags)
        html = (
            '<div data-ng-controller="facetListCtrl" data-ng-init="init('
            "'x', '[" + tags + "]')\"></div>"
        )
        return _R(200, html)


def test_discover_resources_filters_polluted_records():
    """整条链路：被污染的 url 不得出现在产出清单里。"""
    records = [
        _rec("/content/dam/pdf/ok.pdf", ["Pearson-UK:Document-Type/Question-paper"]),
        _rec("https://evil.test/steal.pdf", ["Pearson-UK:Document-Type/Question-paper"]),
        _rec("//evil.test/steal2.pdf", []),
        _rec("http://qualifications.pearson.com/x.pdf", []),
    ]
    fetcher = ReplayFetcher(records, ["Pearson-UK:Qualification-Subject/Economics"])
    out = list(EdexcelAdapter(fetcher).discover_resources(_syllabus()))
    assert [r.url for r in out] == [ORIGIN + "/content/dam/pdf/ok.pdf"]


# --------------------------------------------------------------------------
# 身份键
# --------------------------------------------------------------------------


def test_identity_parts_is_callable_and_stable():
    """identity_parts 曾因相对导入层级写错而无法调用，这里守住可调用性。"""
    meta = {
        "qualification_name": "International-GCSE",
        "spec_code": "igcse-economics-2017",
        "series": "june 2022",
        "unit": "4EC1 01",
        "doc_type": "question_paper",
    }
    url = f"{ORIGIN}/content/dam/pdf/igcse-economics/4ec1-01-que.pdf"
    first = identity_parts(meta, url)
    assert first
    assert identity_parts(dict(meta), url) == first


def test_identity_parts_same_meta_different_url_is_same_key():
    """手写 meta（不经过 extract_metadata）时身份键同样只看结构化字段。"""
    meta = {
        "qualification_name": "International-GCSE",
        "spec_code": "igcse-economics-2017",
        "series": "june 2022",
        "unit": "4EC1 01",
        "doc_type": "question_paper",
    }
    public = f"{ORIGIN}/content/dam/pdf/igcse-economics/4ec1-01-que.pdf"
    gated = f"{ORIGIN}/content/dam/secure/silver/igcse-economics/4ec1-01-que.pdf"
    assert identity_parts(meta, public) == identity_parts(meta, gated)


def test_identity_parts_ignores_directory_change():
    """同一份文档的公开路径与门禁路径不同，身份必须相同，否则会重复入库。"""
    cats = [
        "Pearson-UK:Document-Type/Question-paper",
        "Pearson-UK:Exam-Series/June 2022",
        "Pearson-UK:Unit/4EC1 01",
        "Pearson-UK:Specification-Code/igcse-economics-2017",
    ]
    public = "/content/dam/pdf/igcse-economics/4ec1-01-que.pdf"
    gated = "/content/dam/secure/silver/igcse-economics/4ec1-01-que.pdf"
    meta_public = extract_metadata(cats, public)
    meta_gated = extract_metadata(cats, gated)
    assert meta_public["is_gated"] is False and meta_gated["is_gated"] is True
    assert identity_parts(meta_public, public) == identity_parts(meta_gated, gated)


def test_identity_parts_tracks_structured_fields():
    """结构化字段必须真的参与身份键，否则不同卷/不同考季会撞键。"""
    meta = extract_metadata(
        ["Pearson-UK:Document-Type/Question-paper", "Pearson-UK:Unit/4EC1 01"],
        "/content/dam/pdf/a.pdf",
    )
    base = identity_parts(meta, "/content/dam/pdf/a.pdf")
    assert identity_parts(dict(meta, unit="4EC1 02"), "/content/dam/pdf/a.pdf") != base
    assert identity_parts(dict(meta, series="june 2021"), "/content/dam/pdf/a.pdf") != base
    assert identity_parts(dict(meta, doc_type="mark_scheme"), "/content/dam/pdf/a.pdf") != base


def test_identity_parts_distinguishes_filenames():
    """URL 基名也参与身份键：同一目录下的不同文件不能撞键。"""
    meta = extract_metadata(["Pearson-UK:Document-Type/Question-paper"], "/content/dam/pdf/a.pdf")
    assert identity_parts(meta, "/content/dam/pdf/4ec1-01-que.pdf") != identity_parts(
        meta, "/content/dam/pdf/4ec1-01-rms.pdf"
    )


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
