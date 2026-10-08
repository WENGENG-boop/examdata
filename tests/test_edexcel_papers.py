"""Edexcel IAL 试卷管道的离线单测。

覆盖：分值解析、题号父子树、servlet 分片退让、QP/MS 过滤与去重、
PDF 守卫、catalog 往返、标签回退、身份键去重（msc/rms 同身份）。
全部离线：网络用 monkeypatch 或 httpx.MockTransport 替身。
"""

from __future__ import annotations

import datetime as _dt
import json
import types

import httpx
import pymupdf
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from examdata.adapters.base import DiscoveredResource
from examdata.adapters.edexcel.adapter import EdexcelAdapter
from examdata.adapters.edexcel.servlet import HITS_CAP, ORIGIN, ServletError, ShardExhausted
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher
from examdata.core.models import (
    Artifact,
    ArtifactRevision,
    Asset,
    Base,
    Board,
    Difficulty,
    Document,
    DocumentRevision,
    ExamSeries,
    Formula,
    GeneratedExplanation,
    MarkScheme,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    ParseRun,
    Qualification,
    Question,
    QuestionAsset,
    QuestionSimilarity,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)
from examdata.edexcel_papers import enumerate as edx_enum
from examdata.edexcel_papers import pipeline as edx_pipe

# -- 工具 -------------------------------------------------------------------


def _settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        min_host_interval_seconds=0.0,
        host_interval_jitter_seconds=0.0,
        max_retries=1,
        respect_robots=False,
    )


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


def _record(
    path: str,
    doc_type: str,
    *,
    series: str = "June-2024",
    unit: str = "Unit-1",
    spec: str = "International-Advanced-Level/2018/ial18-biology",
) -> dict:
    return {
        "url": path,
        "title": f"{unit} {doc_type}",
        "objectID": path,
        "extension": "pdf",
        "gating": False,
        "category": [
            f"Pearson-UK:Document-Type/{doc_type}",
            f"Pearson-UK:Exam-Series/{series}",
            f"Pearson-UK:Unit/{unit}",
            f"Pearson-UK:Specification-Code/{spec}",
            "Pearson-UK:Qualification-Subject/Biology",
        ],
    }


def _resource(url: str, *, series: str = "june 2024", unit: str = "Unit-1") -> DiscoveredResource:
    return DiscoveredResource(
        url=url,
        label="WBI11 01 Question paper",
        doc_type="question_paper",
        confidence=0.95,
        meta={
            "doc_type": "question_paper",
            "raw_doc_type": "Question-paper",
            "year": 2024,
            "series": series,
            "paper_code": unit,
            "unit": unit,
            "level": "IAL",
            "subject_code": "ial18-biology",
            "is_gated": False,
        },
        evidence={"method": "category"},
        page_url=edx_enum.syllabus_ref("ial18-biology").source_url,
    )


# -- 分值解析 ---------------------------------------------------------------


def test_parse_total_marker_for_top_level_question():
    text = "1. Explain the role of mitosis. (Total for Question 1 = 6 marks)"
    assert edx_pipe.parse_question_marks(text, "1") == 6


def test_parse_total_marker_ignores_other_question_numbers():
    text = "(Total for Question 2 = 4 marks)"
    assert edx_pipe.parse_question_marks(text, "1") is None


@pytest.mark.parametrize(
    "tail,expected",
    [
        ("(2)", 2),
        ("(2 marks)", 2),
        ("[2 marks]", 2),
        ("[2]", 2),
        ("(12 marks)", 12),
    ],
)
def test_parse_trailing_marks_for_sub_question(tail, expected):
    assert edx_pipe.parse_question_marks(f"Some working {tail}", "1(a)") == expected


def test_parse_strips_total_line_before_trailing_marks():
    text = "sub answer (2)\n(Total for Question 1 = 6 marks)"
    assert edx_pipe.parse_question_marks(text, "1(a)") == 2


def test_parse_returns_none_without_marker():
    assert edx_pipe.parse_question_marks("no marks here", "1(a)") is None
    assert edx_pipe.parse_question_marks("", "1") is None
    assert edx_pipe.parse_question_marks("plain text", "1") is None


def test_standalone_mark_takes_first_hit():
    assert edx_pipe._standalone_mark("1 (a) (i) choose one\n(1)\nA B C D") == 1
    assert edx_pipe._standalone_mark("(i)\n(1)\n(ii)\n(2)") == 1
    assert edx_pipe._standalone_mark("(i) 1\n(ii) 2") is None
    assert edx_pipe._standalone_mark("no marks") is None
    assert edx_pipe._standalone_mark("") is None


def test_standalone_mark_strips_total_line():
    assert edx_pipe._standalone_mark("(Total for Question 1 = 6 marks)\n(2)") == 2


class _StubPage:
    def __init__(self, text):
        self._text = text

    def get_text(self, *args, **kwargs):
        return self._text


class _StubPdf:
    def __init__(self, texts):
        self._pages = [_StubPage(text) for text in texts]

    def __getitem__(self, index):
        return self._pages[index]

    def __len__(self):
        return len(self._pages)


def test_total_marks_from_pages_finds_match():
    pdf = _StubPdf(["page one", "... (Total for Question 1 = 6 marks) ..."])
    regions = [{"page": 1}, {"page": 2}]
    assert edx_pipe._total_marks_from_pages(pdf, regions, "1") == 6


def test_total_marks_from_pages_scans_beyond_region_pages():
    pdf = _StubPdf(["page one", "page two", "... (Total for Question 1 = 12 marks) ..."])
    assert edx_pipe._total_marks_from_pages(pdf, [{"page": 1}], "1") == 12


def test_total_marks_from_pages_uses_cache():
    pdf = _StubPdf(["page one"])
    cache = {1: "(Total for Question 1 = 6 marks)"}
    assert edx_pipe._total_marks_from_pages(pdf, [], "1", cache) == 6


def test_total_marks_from_pages_ignores_other_numbers_and_absent():
    pdf = _StubPdf(["(Total for Question 10 = 5 marks)"])
    assert edx_pipe._total_marks_from_pages(pdf, [{"page": 1}], "1") is None
    assert edx_pipe._total_marks_from_pages(pdf, [], "1") is None


def test_question_marks_priority_and_fallbacks():
    nodes = [
        {"number_path": "1", "parent_path": None, "regions": [{"page": 1}]},
        {"number_path": "1(a)", "parent_path": "1", "regions": [{"page": 2}]},
        {"number_path": "1(a)(i)", "parent_path": "1(a)", "regions": [{"page": 2}]},
    ]
    texts = {
        "1": "(Total for Question 1 = 6 marks)",
        "1(a)": "working (2)",
        "1(a)(i)": "choose one\n(1)\nA B C D",
    }
    pdf = _StubPdf(["page one", "page two"])
    marks = edx_pipe._question_marks(pdf, nodes, texts)
    assert marks == {"1": 6, "1(a)": 2, "1(a)(i)": 1}


def test_question_marks_falls_back_to_page_scan():
    nodes = [{"number_path": "2", "parent_path": None, "regions": [{"page": 1}]}]
    texts = {"2": "question text without total"}
    pdf = _StubPdf(["... (Total for Question 2 = 5 marks) ..."])
    marks = edx_pipe._question_marks(pdf, nodes, texts)
    assert marks == {"2": 5}


# -- 题号树 -----------------------------------------------------------------


def test_build_question_tree_links_parents_and_labels():
    index = [
        {"question": "1", "regions": [{"page": 1, "bbox": [0, 0, 1, 1]}]},
        {"question": "1(a)", "regions": [{"page": 1, "bbox": [0, 1, 1, 2]}]},
        {"question": "1(a)(ii)", "regions": [{"page": 2, "bbox": [0, 0, 1, 1]}]},
        {"question": "2", "regions": []},
    ]
    nodes = edx_pipe.build_question_tree(index)
    assert [n["number_path"] for n in nodes] == ["1", "1(a)", "1(a)(ii)", "2"]
    assert nodes[0]["number_label"] == "1"
    assert nodes[0]["parent_path"] is None
    assert nodes[0]["kind"] == "question"
    assert nodes[1]["number_label"] == "(a)"
    assert nodes[1]["parent_path"] == "1"
    assert nodes[1]["kind"] == "sub"
    assert nodes[2]["depth"] == 2
    assert nodes[2]["parent_path"] == "1(a)"
    assert nodes[2]["kind"] == "part"
    assert nodes[3]["depth"] == 0


def test_build_question_tree_skips_blank_paths():
    assert edx_pipe.build_question_tree([{"question": "", "regions": []}]) == []


# -- 文件名 -> paper code ---------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x/y/wbi11-01-que-20240508.pdf", ("wbi11-01", "WBI11")),
        ("WBI11_01_msc_20190307.pdf", ("wbi11-01", "WBI11")),
        ("wbi11-01a-rms-20260305.pdf", ("wbi11-01a", "WBI11")),
        ("https://x/y/ial-wbi11-01-oct19.pdf", ("wbi11-01", "WBI11")),
        ("ial-wbi13-01-oct19.pdf", ("wbi13-01", "WBI13")),
        ("IAL_WBI12_01_QUE_20191017.PDF", ("wbi12-01", "WBI12")),
        ("https://x/y/readme.pdf", (None, None)),
        ("no-extension", ("no-extension", "NO")),
    ],
)
def test_derive_paper_code(url, expected):
    assert edx_pipe.derive_paper_code(url) == expected


# -- servlet 分片退让 -------------------------------------------------------


def test_query_records_full_query_used_when_not_saturated(monkeypatch):
    calls: list[list[str]] = []

    def fake(fetcher, tags, hits=HITS_CAP):
        calls.append(list(tags))
        return [_record("/x/a.pdf", "Question-paper")]

    monkeypatch.setattr(edx_enum, "fetch_records", fake)
    records, mode = edx_enum.query_records(object(), ["tag"])
    assert mode == "full"
    assert len(calls) == 1
    assert len(records) == 1


def test_query_records_falls_back_to_doc_type_shards(monkeypatch):
    calls: list[list[str]] = []

    def fake(fetcher, tags, hits=HITS_CAP):
        calls.append(list(tags))
        if len(calls) == 1:
            raise ShardExhausted("full query saturated")
        return [_record(f"/x/{len(calls)}.pdf", "Question-paper")]

    monkeypatch.setattr(edx_enum, "fetch_records", fake)
    records, mode = edx_enum.query_records(object(), ["tag"])
    assert mode == "doc-type"
    assert len(calls) == 3
    assert calls[1][-1] == "Pearson-UK:Document-Type/Question-paper"
    assert calls[2][-1] == "Pearson-UK:Document-Type/Mark-scheme"
    # 每个 doc-type 分片各返回一条，且标签是独立 AND 子句
    assert len(records) == 2
    assert calls[0] == ["tag"]


def test_query_records_falls_back_to_season_grid(monkeypatch):
    calls: list[list[str]] = []

    def fake(fetcher, tags, hits=HITS_CAP):
        calls.append(list(tags))
        if len(calls) <= 2:
            raise ShardExhausted("saturated")
        return [_record(f"/x/{len(calls)}.pdf", "Question-paper")]

    monkeypatch.setattr(edx_enum, "fetch_records", fake)
    records, mode = edx_enum.query_records(object(), ["tag"], label="ial18-biology")
    # 1 次全查 + doc-type 分片第 1 次即饱和（循环随之中止）+ 整个考季网格
    expected_calls = 2 + len(edx_enum.SEASONS) * len(edx_enum.SEASON_YEARS) * len(
        edx_enum.DOC_TYPES
    )
    assert mode == "season-grid"
    assert len(calls) == expected_calls
    assert len(records) == expected_calls - 2
    # 网格查询带考季 + doc-type 两个独立子句
    grid_call = calls[2]
    assert any(t.startswith("Pearson-UK:Exam-Series/") for t in grid_call)
    assert any(t.startswith("Pearson-UK:Document-Type/") for t in grid_call)


def test_query_records_raises_when_grid_exhausted(monkeypatch):
    def fake(fetcher, tags, hits=HITS_CAP):
        raise ShardExhausted("saturated")

    monkeypatch.setattr(edx_enum, "fetch_records", fake)
    with pytest.raises(ShardExhausted) as excinfo:
        edx_enum.query_records(object(), ["tag"], label="ial18-biology")
    assert "ial18-biology" in str(excinfo.value)
    assert "season grid exhausted" in str(excinfo.value)


# -- 过滤与去重 -------------------------------------------------------------


def test_keep_qp_ms_excludes_modified_and_other_types():
    records = [
        _record("/x/qp.pdf", "Question-paper"),
        _record("/x/ms.pdf", "Mark-scheme"),
        _record("/x/mod.pdf", "Modified-question-paper"),
        _record("/x/er.pdf", "Examiner-report"),
        {"url": "/x/none.pdf", "category": [], "title": "x", "objectID": "n", "extension": "pdf"},
    ]
    kept = edx_enum.keep_qp_ms(records)
    assert [r["url"] for r in kept] == ["/x/qp.pdf", "/x/ms.pdf"]


def test_keep_qp_ms_is_case_insensitive():
    assert edx_enum.keep_qp_ms([_record("/x/ms.pdf", "Mark-Scheme")])
    assert edx_enum.keep_qp_ms([_record("/x/qp.pdf", "QUESTION-PAPER")])


def test_dedup_records_keeps_first_occurrence():
    records = [
        {"url": "/x/a.pdf", "objectID": "1"},
        {"url": "/x/a.pdf", "objectID": "2"},
        {"url": "/x/b.pdf", "objectID": "2"},
        {"objectID": "3"},
        {"objectID": "3"},
    ]
    deduped = edx_enum.dedup_records(records)
    assert [r.get("url") or r.get("objectID") for r in deduped] == [
        "/x/a.pdf",
        "/x/b.pdf",
        "3",
    ]


# -- PDF 守卫 ---------------------------------------------------------------


def _guard(settings, handler) -> edx_pipe.PdfGuardFetcher:
    fetcher = edx_pipe.PdfGuardFetcher(settings)
    fetcher._client = httpx.Client(transport=httpx.MockTransport(handler))
    return fetcher


def test_pdf_guard_rejects_non_pdf_binary(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            content=b"<html>sign in</html>",
            headers={"content-type": "text/html"},
        )

    fetcher = _guard(_settings(tmp_path), handler)
    try:
        result = fetcher.get(f"{ORIGIN}/x/file.pdf", expect_binary=True)
    finally:
        fetcher.close()
    assert result.ok is False
    assert result.content is None
    assert result.error == "non-PDF response body"


def test_pdf_guard_passes_pdf_and_text(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path.endswith(".pdf"):
            return httpx.Response(
                200, content=b"%PDF-1.4\n%%EOF\n", headers={"content-type": "application/pdf"}
            )
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    fetcher = _guard(_settings(tmp_path), handler)
    try:
        pdf = fetcher.get(f"{ORIGIN}/x/file.pdf", expect_binary=True)
        page = fetcher.get_text(f"{ORIGIN}/x/page.html")
    finally:
        fetcher.close()
    assert pdf.ok and pdf.content.startswith(b"%PDF-")
    assert page.ok and page.text == "<html>ok</html>"


# -- catalog ----------------------------------------------------------------


def test_catalog_round_trip(tmp_path):
    settings = _settings(tmp_path)
    catalog = {
        "slug": "ial18-biology",
        "code": "ial18-biology",
        "title": "Biology",
        "qualification_key": "edexcel-ial",
        "qualification_name": "Pearson Edexcel International A Level",
        "source_url": edx_enum.syllabus_ref("ial18-biology").source_url,
        "tags": ["Pearson-UK:Specification-Code/ial18-biology"],
        "tags_source": "fallback",
        "spec_variants": ["International-Advanced-Level/2018/ial18-biology"],
        "query_mode": "full",
        "queried_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "notes": [],
        "counts": {"records": 1, "resources": 1, "question_papers": 1, "mark_schemes": 0, "gated": 0},
        "resources": [edx_enum.asdict(_resource(f"{ORIGIN}/x/wbi11-01-que-20240508.pdf"))],
    }
    path = edx_enum.save_catalog(catalog, settings)
    assert path == edx_enum.catalog_path(settings, "ial18-biology")
    assert json.loads(path.read_text(encoding="utf-8"))["slug"] == "ial18-biology"

    loaded = edx_enum.load_catalog(settings, "ial18-biology")
    assert loaded is not None
    resources = edx_enum.catalog_resources(loaded)
    assert len(resources) == 1
    assert isinstance(resources[0], DiscoveredResource)
    assert resources[0].url.endswith("wbi11-01-que-20240508.pdf")
    assert edx_enum.load_catalog(settings, "ial18-physics") is None


# -- 标签回退 ---------------------------------------------------------------


class _StubAdapter:
    def __init__(self, tags=None, error=None):
        self._tags = tags
        self._error = error

    def subject_facet_tags(self, ref):
        if self._error is not None:
            raise self._error
        return self._tags


def test_resolve_tags_falls_back_to_specification_code():
    ref = edx_enum.syllabus_ref("ial18-biology")
    tags, source, notes = edx_enum.resolve_tags(_StubAdapter(error=ServletError("no facet")), ref)
    assert tags == ["Pearson-UK:Specification-Code/ial18-biology"]
    assert source == "fallback"
    assert notes and "no facet" in notes[0]


def test_resolve_tags_uses_subject_page_selection():
    ref = edx_enum.syllabus_ref("ial18-biology")
    stub = _StubAdapter(
        tags=[
            "Pearson-UK:Qualification-Family/International-Advanced-Level",
            "Pearson-UK:Qualification-Subject/Biology",
            "Pearson-UK:Specification-Code/International-Advanced-Level/2018/ial18-biology",
            "Pearson-UK:Specification-Code/International-Advanced-Level",
        ]
    )
    tags, source, notes = edx_enum.resolve_tags(stub, ref)
    assert source == "subject_page"
    assert notes == []
    assert "Pearson-UK:Qualification-Family/International-Advanced-Level" in tags
    assert "Pearson-UK:Specification-Code/International-Advanced-Level/2018/ial18-biology" in tags
    # 泛化前缀被 select_facet_tags 丢掉
    assert "Pearson-UK:Specification-Code/International-Advanced-Level" not in tags


# -- 端到端枚举 -------------------------------------------------------------


def test_enumerate_subject_filters_and_counts(tmp_path, monkeypatch):
    records = [
        _record("/content/dam/pdf/qp-1.pdf", "Question-paper"),
        _record("/content/dam/pdf/qp-2.pdf", "Question-paper", unit="Unit-2"),
        _record("/content/dam/pdf/ms-1.pdf", "Mark-scheme"),
        _record("/content/dam/secure/ms-2.pdf", "Mark-scheme", unit="Unit-2"),
        _record("/content/dam/pdf/mod.pdf", "Modified-question-paper"),
        _record("/content/dam/pdf/er.pdf", "Examiner-report"),
    ]

    def fake(fetcher, tags, hits=HITS_CAP):
        return list(records)

    def boom(self, ref):
        raise ServletError("subject page has no facet metadata")

    monkeypatch.setattr(edx_enum, "fetch_records", fake)
    monkeypatch.setattr(EdexcelAdapter, "subject_facet_tags", boom)

    fetcher = Fetcher(_settings(tmp_path))
    try:
        catalog = edx_enum.enumerate_subject(fetcher, "ial18-biology")
    finally:
        fetcher.close()

    assert catalog["query_mode"] == "full"
    assert catalog["tags_source"] == "fallback"
    assert catalog["tags"] == ["Pearson-UK:Specification-Code/ial18-biology"]
    assert catalog["counts"] == {
        "records": 4,
        "resources": 4,
        "question_papers": 2,
        "mark_schemes": 2,
        "gated": 1,
    }
    urls = [r["url"] for r in catalog["resources"]]
    assert f"{ORIGIN}/content/dam/secure/ms-2.pdf" in urls
    assert all("mod.pdf" not in url and "er.pdf" not in url for url in urls)
    assert catalog["spec_variants"] == ["International-Advanced-Level/2018/ial18-biology"]
    assert catalog["notes"] and "no facet" in catalog["notes"][0]


def test_enumerate_subject_rejects_unknown_slug(tmp_path):
    fetcher = Fetcher(_settings(tmp_path))
    try:
        with pytest.raises(ValueError):
            edx_enum.enumerate_subject(fetcher, "ial99-nope")
    finally:
        fetcher.close()


# -- 身份键与下载判定 -------------------------------------------------------


def test_document_identity_is_stable_for_same_meta():
    ref = edx_enum.syllabus_ref("ial18-biology")
    adapter = EdexcelAdapter(Fetcher(_settings_empty()))
    a = _resource(f"{ORIGIN}/content/dam/pdf/wbi11-01-que-20240508.pdf")
    b = _resource(f"{ORIGIN}/content/dam/secure/wbi11-01-que-20240508.pdf")
    assert edx_pipe.document_identity(adapter, ref, a) == edx_pipe.document_identity(adapter, ref, b)


def _settings_empty() -> Settings:
    return Settings(
        min_host_interval_seconds=0.0, host_interval_jitter_seconds=0.0, max_retries=1
    )


def test_needs_download_detects_second_file_of_same_identity():
    """同 unit 的 msc/rms 两个文件共用身份键，第二份也必须下载。"""
    settings = _settings_empty()
    session = _session()
    adapter = EdexcelAdapter(Fetcher(settings))
    ref = edx_enum.syllabus_ref("ial18-biology")
    first = _resource(f"{ORIGIN}/content/dam/pdf/wbi11-01-msc-20210604.pdf")
    second = _resource(f"{ORIGIN}/content/dam/pdf/wbi11-01-rms-20210604.pdf")

    assert edx_pipe._needs_download(session, adapter, ref, first, refresh=False) is True

    doc = Document(
        identity_key=edx_pipe.document_identity(adapter, ref, first),
        board_id=1,
        doc_type="question_paper",
        attrs={},
    )
    session.add(doc)
    session.flush()
    artifact = Artifact(
        sha256="a" * 64,
        size_bytes=10,
        mime="application/pdf",
        storage_key="aa/aa/" + "a" * 64 + ".pdf",
        first_fetched_at=_dt.datetime.now(_dt.timezone.utc),
        attrs={},
    )
    session.add(artifact)
    session.flush()
    revision = DocumentRevision(
        document_id=doc.id,
        artifact_id=artifact.id,
        revision_no=1,
        source_url=first.url,
        status="stored",
        parser_version="test",
        parse_status="pending",
    )
    session.add(revision)
    session.flush()
    doc.current_revision_id = revision.id
    session.add(
        ArtifactRevision(artifact_id=artifact.id, url=first.url, change_kind="initial")
    )
    session.commit()

    assert edx_pipe._needs_download(session, adapter, ref, first, refresh=False) is False
    assert edx_pipe._needs_download(session, adapter, ref, second, refresh=False) is True
    assert edx_pipe._needs_download(session, adapter, ref, second, refresh=True) is True


# -- 同步（MockTransport + 内存库） -----------------------------------------


def _pdf_handler(seen: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200, content=b"%PDF-1.4\n%%EOF\n", headers={"content-type": "application/pdf"}
        )

    return handler


def test_sync_resources_stores_document_and_rewrites_paper_code(tmp_path):
    settings = _settings(tmp_path)
    session = _session()
    ref = edx_enum.syllabus_ref("ial18-biology")
    res = _resource(f"{ORIGIN}/content/dam/pdf/wbi11-01-que-20240508.pdf")
    fetcher = _guard(settings, _pdf_handler([]))
    try:
        summary = edx_pipe.sync_resources(
            session, settings, ref, [res], fetcher=fetcher
        )
    finally:
        fetcher.close()

    assert summary.created == 1
    assert summary.failed == 0
    doc = session.scalar(select(Document))
    assert doc is not None
    # servlet 的 Unit 值不可用：必须换成文件名推导的 code
    assert doc.paper_code == "wbi11-01"
    revision = session.get(DocumentRevision, doc.current_revision_id)
    assert revision is not None and revision.source_url == res.url
    assert revision.parse_status == "pending"


def test_sync_resources_is_idempotent_and_refresh_redownloads(tmp_path):
    settings = _settings(tmp_path)
    session = _session()
    ref = edx_enum.syllabus_ref("ial18-biology")
    res = _resource(f"{ORIGIN}/content/dam/pdf/wbi11-01-que-20240508.pdf")
    seen: list[str] = []
    fetcher = _guard(settings, _pdf_handler(seen))
    try:
        first = edx_pipe.sync_resources(session, settings, ref, [res], fetcher=fetcher)
        second = edx_pipe.sync_resources(session, settings, ref, [res], fetcher=fetcher)
        third = edx_pipe.sync_resources(
            session, settings, ref, [res], fetcher=fetcher, refresh=True
        )
    finally:
        fetcher.close()

    assert (first.created, first.skipped) == (1, 0)
    assert (second.created, second.skipped) == (0, 1)
    assert (third.unchanged, third.failed) == (1, 0)
    assert len(seen) == 2  # 第二次没有发请求


def test_sync_resources_marks_gated_without_fetching(tmp_path):
    settings = _settings(tmp_path)
    session = _session()
    ref = edx_enum.syllabus_ref("ial18-biology")
    res = _resource(f"{ORIGIN}/content/dam/secure/wbi11-01-que-20240508.pdf")
    res.meta["is_gated"] = True
    seen: list[str] = []
    fetcher = _guard(settings, _pdf_handler(seen))
    try:
        summary = edx_pipe.sync_resources(session, settings, ref, [res], fetcher=fetcher)
    finally:
        fetcher.close()
    assert summary.gated == 1
    assert seen == []
    assert session.scalar(select(Document)) is not None


def test_sync_resources_rejects_non_pdf_body(tmp_path):
    settings = _settings(tmp_path)
    session = _session()
    ref = edx_enum.syllabus_ref("ial18-biology")
    res = _resource(f"{ORIGIN}/content/dam/pdf/wbi11-01-que-20240508.pdf")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"<html>login</html>", headers={"content-type": "text/html"})

    fetcher = _guard(settings, handler)
    try:
        summary = edx_pipe.sync_resources(session, settings, ref, [res], fetcher=fetcher)
    finally:
        fetcher.close()
    assert summary.failed == 1
    assert summary.created == 0
    assert any("non-PDF" in e for e in summary.errors)


# -- 考季过滤 ---------------------------------------------------------------


def test_series_ids_matches_normalized_name():
    session = _session()
    session.add(ExamSeries(year=2024, session="june 2024", month=None, attrs={}))
    session.add(ExamSeries(year=2025, session="january 2025", month=None, attrs={}))
    session.commit()
    assert len(edx_pipe._series_ids(session, "June-2024")) == 1
    assert len(edx_pipe._series_ids(session, "june 2024")) == 1
    assert edx_pipe._series_ids(session, "june 2030") == []


# -- MS 自愈 ----------------------------------------------------------------


def _ms_selfheal_scene(
    session,
    *,
    ms_entries: int = 0,
    qp_questions: int = 1,
    index_qp: bool = True,
    ms_url_variant: bool = False,
) -> tuple[Document, dict]:
    """搭最小现场：MS 当前 revision 已有本模块的 completed 解析，QP 可按需带题。

    返回 ``(ms_doc, qp_index)``。测试把 ``_artifact_path`` 换成返回 None，
    用来区分「跳过」与「落入重切」两条路径：重切必然撞上文件缺失。
    """
    board = Board(key="edexcel", name="Pearson Edexcel")
    session.add(board)
    session.flush()
    qualification = Qualification(board_id=board.id, key="edexcel-ial", name="IAL")
    session.add(qualification)
    session.flush()
    subject = Subject(qualification_id=qualification.id, code="ial18-test", title="Biology")
    session.add(subject)
    session.flush()
    series = ExamSeries(year=2021, session="june 2021", month=6, attrs={})
    session.add(series)
    session.flush()

    def _artifact(sha_char: str) -> Artifact:
        artifact = Artifact(
            sha256=sha_char * 64,
            size_bytes=10,
            mime="application/pdf",
            storage_key=f"{sha_char * 2}/{sha_char * 2}/{sha_char * 64}.pdf",
            attrs={},
        )
        session.add(artifact)
        session.flush()
        return artifact

    qp_doc = Document(
        identity_key="qp-wbi11-01-june-2021",
        board_id=board.id,
        subject_id=subject.id,
        series_id=series.id,
        doc_type=edx_pipe.DOC_QUESTION_PAPER,
        paper_code="wbi11-01",
        attrs={},
    )
    session.add(qp_doc)
    session.flush()
    qp_revision = DocumentRevision(
        document_id=qp_doc.id,
        artifact_id=_artifact("a").id,
        revision_no=1,
        source_url=f"{ORIGIN}/content/dam/pdf/wbi11-01-que-20210604.pdf",
        status="active",
        parse_status="parsed",
    )
    session.add(qp_revision)
    session.flush()
    qp_doc.current_revision_id = qp_revision.id

    paper = Paper(document_id=qp_doc.id, attrs={})
    session.add(paper)
    session.flush()
    for order in range(qp_questions):
        session.add(
            Question(
                paper_id=paper.id,
                number_label=str(order + 1),
                number_path=str(order + 1),
                display_order=order,
                depth=0,
                kind="question",
                attrs={},
            )
        )

    ms_doc = Document(
        identity_key="ms-wbi11-01-june-2021",
        board_id=board.id,
        subject_id=subject.id,
        series_id=series.id,
        doc_type=edx_pipe.DOC_MARK_SCHEME,
        paper_code="wbi11-01",
        attrs={},
    )
    session.add(ms_doc)
    session.flush()
    ms_name = (
        "wbi11-01a-rms-20210604.pdf" if ms_url_variant else "wbi11-01-msc-20210604.pdf"
    )
    ms_revision = DocumentRevision(
        document_id=ms_doc.id,
        artifact_id=_artifact("b").id,
        revision_no=1,
        source_url=f"{ORIGIN}/content/dam/pdf/{ms_name}",
        status="active",
        parse_status="parsed",
    )
    session.add(ms_revision)
    session.flush()
    ms_doc.current_revision_id = ms_revision.id

    run = ParseRun(
        document_revision_id=ms_revision.id,
        parser_version=edx_pipe.PARSER_VERSION,
        params={"doc_type": edx_pipe.DOC_MARK_SCHEME, "subject": "ial18-test"},
        status="completed",
        started_at=_dt.datetime.now(_dt.timezone.utc),
        finished_at=_dt.datetime.now(_dt.timezone.utc),
        stats={"entries": 0},
    )
    session.add(run)
    session.flush()
    mark_scheme = MarkScheme(
        document_id=ms_doc.id,
        matched_paper_document_id=qp_doc.id,
        match_confidence=1.0,
        match_method="filename+series",
        match_evidence={},
        parse_run_id=run.id,
    )
    session.add(mark_scheme)
    session.flush()
    for order in range(ms_entries):
        session.add(
            MarkSchemeEntry(
                mark_scheme_id=mark_scheme.id,
                number_label=str(order + 1),
                number_path=str(order + 1),
                answer_text="mark",
                acceptable_answers=[],
                raw={},
            )
        )
    session.commit()

    qp_index = {}
    if index_qp:
        qp_index[(subject.id, series.id, "wbi11-01")] = qp_doc
    return ms_doc, qp_index


def test_split_ms_heals_zero_entry_ms_when_qp_has_questions(tmp_path, monkeypatch):
    """MS 切出 0 条而 QP 已有题：不跳过，落入重切（自愈）。"""
    settings = _settings(tmp_path)
    session = _session()
    ms_doc, qp_index = _ms_selfheal_scene(session, ms_entries=0, qp_questions=1)
    revision_id = ms_doc.current_revision_id
    monkeypatch.setattr(edx_pipe, "_artifact_path", lambda *args, **kwargs: None)

    summary = edx_pipe.SplitSummary()
    edx_pipe._split_ms(
        session, settings, ms_doc, qp_index, summary, {}, force=False, slug="ial18-test"
    )

    assert summary.skipped == 0
    assert summary.failed == 1
    assert any("artifact file missing" in error for error in summary.errors)
    assert session.get(DocumentRevision, revision_id).parse_status == "failed"
    assert session.scalar(select(ParseRun).where(ParseRun.status == "failed")) is not None


def test_split_ms_skips_heal_when_ms_already_has_entries(tmp_path, monkeypatch):
    """MS 已有条目：即使 QP 有题也照旧跳过，不重切。"""
    settings = _settings(tmp_path)
    session = _session()
    ms_doc, qp_index = _ms_selfheal_scene(session, ms_entries=1, qp_questions=1)
    monkeypatch.setattr(edx_pipe, "_artifact_path", lambda *args, **kwargs: None)

    summary = edx_pipe.SplitSummary()
    edx_pipe._split_ms(
        session, settings, ms_doc, qp_index, summary, {}, force=False, slug="ial18-test"
    )

    assert summary.skipped == 1
    assert summary.failed == 0
    assert summary.errors == []
    assert len(session.scalars(select(MarkSchemeEntry)).all()) == 1


def test_split_ms_skips_heal_when_qp_has_no_questions(tmp_path, monkeypatch):
    """MS 0 条但 QP 还没切出题目：不构成自愈条件，照旧跳过。"""
    settings = _settings(tmp_path)
    session = _session()
    ms_doc, qp_index = _ms_selfheal_scene(session, ms_entries=0, qp_questions=0)
    monkeypatch.setattr(edx_pipe, "_artifact_path", lambda *args, **kwargs: None)

    summary = edx_pipe.SplitSummary()
    edx_pipe._split_ms(
        session, settings, ms_doc, qp_index, summary, {}, force=False, slug="ial18-test"
    )

    assert summary.skipped == 1
    assert summary.failed == 0
    assert summary.errors == []


def test_split_ms_skips_heal_when_qp_not_indexed(tmp_path, monkeypatch):
    """MS 0 条但 qp_index 里找不到对应 QP：照旧跳过。"""
    settings = _settings(tmp_path)
    session = _session()
    ms_doc, qp_index = _ms_selfheal_scene(
        session, ms_entries=0, qp_questions=1, index_qp=False
    )
    monkeypatch.setattr(edx_pipe, "_artifact_path", lambda *args, **kwargs: None)

    summary = edx_pipe.SplitSummary()
    edx_pipe._split_ms(
        session, settings, ms_doc, qp_index, summary, {}, force=False, slug="ial18-test"
    )

    assert qp_index == {}
    assert summary.skipped == 1
    assert summary.failed == 0


def test_split_ms_force_reparses_completed_current_run(tmp_path, monkeypatch):
    """force=True 时当前 revision 的 completed MS 也要重切。"""
    settings = _settings(tmp_path)
    session = _session()
    ms_doc, qp_index = _ms_selfheal_scene(session, ms_entries=1, qp_questions=1)
    monkeypatch.setattr(edx_pipe, "_artifact_path", lambda *args, **kwargs: None)

    summary = edx_pipe.SplitSummary()
    edx_pipe._split_ms(
        session, settings, ms_doc, qp_index, summary, {}, force=True, slug="ial18-test"
    )

    assert summary.skipped == 0
    assert summary.failed == 1
    assert any("artifact file missing" in error for error in summary.errors)


def test_split_ms_heals_when_ms_code_variant_differs_from_qp(tmp_path, monkeypatch):
    """MS code 带版本尾字母（wbi11-01a）、QP 索引是规范 code：归一化后仍自愈。"""
    settings = _settings(tmp_path)
    session = _session()
    ms_doc, qp_index = _ms_selfheal_scene(
        session, ms_entries=0, qp_questions=1, ms_url_variant=True
    )
    monkeypatch.setattr(edx_pipe, "_artifact_path", lambda *args, **kwargs: None)

    summary = edx_pipe.SplitSummary()
    edx_pipe._split_ms(
        session, settings, ms_doc, qp_index, summary, {}, force=False, slug="ial18-test"
    )

    assert summary.skipped == 0
    assert summary.failed == 1
    assert any("artifact file missing" in error for error in summary.errors)


# -- Fix A: MS↔QP code 归一化 / 单元家族 ------------------------------------


def test_norm_paper_code_strips_suffix_variants():
    assert edx_pipe._norm_paper_code("wch13-01r") == "wch13-01"
    assert edx_pipe._norm_paper_code("wch15-01a") == "wch15-01"
    assert edx_pipe._norm_paper_code("wbi11-01a-rms") == "wbi11-01"
    assert edx_pipe._norm_paper_code("wph15-rms") == "wph15"
    assert edx_pipe._norm_paper_code("Unit-2") == "unit-2"
    assert edx_pipe._norm_paper_code(None) == ""


def test_paper_families_from_code_and_title():
    assert edx_pipe._paper_families("wma11-01", None) == {"wma11"}
    assert edx_pipe._paper_families("wdm11-01", "WMA11 Pure Mathematics P1") == {
        "wdm11",
        "wma11",
    }
    assert edx_pipe._paper_families(None, None) == set()


def _doc_stub(**kwargs):
    return types.SimpleNamespace(**kwargs)


def test_lookup_qp_exact_match_wins_over_ambiguity():
    qp = _doc_stub(title=None)
    other = _doc_stub(title=None)
    index = {(1, 2, "wbi11-01"): qp, (1, 2, "wbi11-01r"): other}
    doc = _doc_stub(subject_id=1, series_id=2, title=None)
    assert edx_pipe._lookup_qp(index, doc, "wbi11-01") == (qp, 1.0, "filename+series")


def test_lookup_qp_normalized_code_hit():
    qp = _doc_stub(title=None)
    index = {(1, 2, "wbi11-01"): qp}
    doc = _doc_stub(subject_id=1, series_id=2, title=None)
    assert edx_pipe._lookup_qp(index, doc, "wbi11-01r") == (qp, 0.85, "code-normalized")


def test_lookup_qp_unit_family_hit():
    qp = _doc_stub(title=None)
    index = {(1, 2, "wma11-01"): qp}
    doc = _doc_stub(subject_id=1, series_id=2, title="WMA11 Pure Mathematics P1")
    assert edx_pipe._lookup_qp(index, doc, "wdm11-01") == (qp, 0.6, "unit-family")


def test_lookup_qp_returns_none_when_family_ambiguous():
    index = {
        (1, 2, "wma11-01"): _doc_stub(title=None),
        (1, 2, "wma11-02"): _doc_stub(title=None),
    }
    doc = _doc_stub(subject_id=1, series_id=2, title=None)
    assert edx_pipe._lookup_qp(index, doc, "wma11-03") == (None, 0.0, None)


def test_lookup_qp_returns_none_without_same_series():
    index = {(1, 3, "wbi11-01"): _doc_stub(title=None)}
    doc = _doc_stub(subject_id=1, series_id=2, title=None)
    assert edx_pipe._lookup_qp(index, doc, "wbi11-01") == (None, 0.0, None)
    assert edx_pipe._lookup_qp({}, doc, "wbi11-01") == (None, 0.0, None)


# -- Fix B: MS 表格锚点（math 尾点/独立分段/紧凑题号） ----------------------


def test_normalize_ms_token_variants():
    assert edx_pipe._normalize_ms_token("1.") == "1"
    assert edx_pipe._normalize_ms_token("12.") == "12"
    assert edx_pipe._normalize_ms_token("1.(a)") == "1(a)"
    assert edx_pipe._normalize_ms_token("(a)") == "(a)"
    assert edx_pipe._normalize_ms_token("•2") == "2"


def test_ms_notes_question_reads_number_after_keyword():
    words = [(None, "Notes"), (None, "for"), (None, "question"), (None, "7")]
    assert edx_pipe._ms_notes_question(words) == "7"
    assert edx_pipe._ms_notes_question([(None, "Notes")]) is None
    assert edx_pipe._ms_notes_question([(None, "Level"), (None, "1")]) is None


def test_ms_extend_walks_ancestors():
    accepted = lambda candidate: candidate in {"7(b)", "7(c)(ii)"}
    assert edx_pipe._ms_extend("7(c)(i)", "(ii)", accepted) == "7(c)(ii)"
    assert edx_pipe._ms_extend("7(c)", "(b)", accepted) == "7(b)"
    assert edx_pipe._ms_extend("7(c)(i)", "(z)", accepted) is None
    assert edx_pipe._ms_extend(None, "(a)", accepted) is None


class _FakePage:
    """_ms_anchors 的脚本化页面：直接给词框/横线，绕开真实 PDF 版式。"""

    def __init__(self, words, drawings=(), width=595.0, height=842.0):
        self.rect = pymupdf.Rect(0, 0, width, height)
        self.rotation_matrix = pymupdf.Matrix(1, 0, 0, 1, 0, 0)
        self._words = list(words)
        self._drawings = [pymupdf.Rect(d) for d in drawings]

    def get_text(self, kind):
        assert kind == "words"
        return list(self._words)

    def get_drawings(self):
        return [{"rect": rect} for rect in self._drawings]


def _word(text, x, y0, width=30.0):
    return (x, y0, x + width, y0 + 10.0, text)


def test_ms_anchors_scans_table_left_column():
    """第 1 页跳过；尾点题号、独立分段、紧凑题号合并、x 超限/裸数字/Level 拒绝。"""
    page0 = _FakePage(
        words=[_word("99", 50, 100)],
        drawings=[(40, 99, 400, 99)],
    )
    page1 = _FakePage(
        words=[
            _word("Notes", 50, 60, 40),
            _word("for", 95, 60, 20),
            _word("question", 120, 60, 50),
            _word("7", 175, 60, 8),
            _word("(a)", 60, 90, 16),
            _word("(i)", 70, 120, 12),
            _word("1", 50, 150, 8),
            _word("5", 50, 180, 8),
            _word("2.", 60, 210, 14),
            _word("(a)", 84, 210, 16),
            _word("3d", 60, 240, 14),
            _word("ii", 84, 240, 10),
            _word("9(a)", 130, 270, 26),
            _word("2nd", 50, 300, 22),
            _word("Level", 50, 330, 30),
            _word("3", 90, 330, 8),
            _word("4(b)", 50, 360, 24),
            _word("(ii)", 60, 390, 12),
            _word("(z)", 60, 420, 12),
        ],
        drawings=[(40, 149, 400, 149)],
    )
    wanted = {
        "1",
        "2(a)",
        "3(d)(ii)",
        "4(b)",
        "4(b)(ii)",
        "7(a)",
        "7(a)(i)",
        "9(a)",
    }
    anchors = edx_pipe._ms_anchors([page0, page1], wanted)
    assert [(index, number) for index, number, _rect in anchors] == [
        (1, "7(a)"),
        (1, "7(a)(i)"),
        (1, "1"),
        (1, "2(a)"),
        (1, "3dii"),
        (1, "4(b)"),
        (1, "4(b)(ii)"),
    ]


def test_ms_anchors_column_match_exception():
    """裸数字超页校准列时，该 x 处全文档带括号题号 ≥5 则例外放行；容差外仍拒绝。"""
    page0 = _FakePage(words=[_word("99", 50, 100)])
    page1 = _FakePage(
        words=[
            _word("2(a)", 60, 90, 26),
            _word("8", 91, 150, 8),
            _word("9", 95, 180, 8),
        ],
        drawings=[(40, 149, 400, 149), (40, 179, 400, 179)],
    )
    page2 = _FakePage(
        words=[
            _word("(a)", 91, 60, 16),
            _word("(b)", 91, 90, 16),
            _word("(c)", 91, 120, 16),
            _word("(d)", 91, 150, 16),
            _word("(e)", 91, 180, 16),
        ],
    )
    got = [
        (index, number)
        for index, number, _rect in edx_pipe._ms_anchors([page0, page1, page2])
    ]
    assert got == [(1, "2(a)"), (1, "8")]


# -- force 重切删除路径 -------------------------------------------------------


def _session_fk():
    """sqlite 默认不强制外键；生产库（core/db.py）开启，这里保持一致。"""
    engine = create_engine("sqlite://", future=True)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):  # pragma: no cover - 驱动细节
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)()


def test_delete_paper_data_clears_question_child_rows():
    """force 重切先清 FK 子表：biology 打标后重切曾撞 FOREIGN KEY constraint failed。"""
    session = _session_fk()
    board = Board(key="edexcel", name="Pearson Edexcel")
    session.add(board)
    session.flush()
    qualification = Qualification(board_id=board.id, key="edexcel-ial", name="IAL")
    session.add(qualification)
    session.flush()
    subject = Subject(qualification_id=qualification.id, code="ial18-test", title="Biology")
    session.add(subject)
    session.flush()
    series = ExamSeries(year=2021, session="june 2021", month=6, attrs={})
    session.add(series)
    session.flush()
    doc = Document(
        identity_key="qp-fk-delete",
        board_id=board.id,
        subject_id=subject.id,
        series_id=series.id,
        doc_type=edx_pipe.DOC_QUESTION_PAPER,
        paper_code="wbi11-01",
        attrs={},
    )
    session.add(doc)
    session.flush()
    paper = Paper(document_id=doc.id, attrs={})
    session.add(paper)
    session.flush()

    def _question(label: str, order: int) -> Question:
        question = Question(
            paper_id=paper.id,
            number_label=label,
            number_path=label,
            display_order=order,
            depth=0,
            kind="question",
            attrs={},
        )
        session.add(question)
        session.flush()
        return question

    q1 = _question("1", 0)
    q2 = _question("2", 1)

    node = TaxonomyNode(
        board_id=board.id,
        code="1.2",
        name="Cells",
        node_type="topic",
        source="official",
        attrs={},
    )
    session.add(node)
    session.flush()
    session.add(
        QuestionTaxonomy(
            question_id=q1.id,
            node_id=node.id,
            source="auto",
            confidence=0.9,
            assigned_by="test",
        )
    )
    session.add(
        Difficulty(question_id=q1.id, source="estimated", value=0.5, scale="0-1", features={})
    )
    session.add(
        QuestionSimilarity(
            question_a_id=q1.id, question_b_id=q2.id, method="hybrid", score=0.9, features={}
        )
    )
    asset = Asset(
        sha256="a" * 64, storage_key=f"aa/aa/{'a' * 64}.png", kind="figure", attrs={}
    )
    session.add(asset)
    session.flush()
    session.add(QuestionAsset(question_id=q1.id, asset_id=asset.id, role="figure", reading_order=0))
    session.add(Formula(question_id=q1.id, source="inline_text", confidence=0.5))
    session.add(OfficialAnswer(question_id=q1.id, source="mark_scheme", content="answer", attrs={}))
    session.add(GeneratedExplanation(question_id=q1.id, provider="test", prompt_version="v1"))
    session.commit()

    edx_pipe._delete_paper_data(session, doc, paper)
    session.commit()

    for model in (
        QuestionTaxonomy,
        QuestionAsset,
        Formula,
        OfficialAnswer,
        GeneratedExplanation,
        Difficulty,
        QuestionSimilarity,
    ):
        assert session.scalars(select(model)).all() == [], model.__name__
    assert session.scalars(select(Question)).all() == []
    assert session.get(Paper, paper.id) is None
