"""注册适配器的离线契约：回放各自传输形状，验证真实发现结果而非站点可达性。"""

from __future__ import annotations

import inspect
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from examdata.adapters import registry
from examdata.adapters.base import BoardAdapter, DiscoveredResource, SyllabusRef
from examdata.core.fetch import FetchResult


@pytest.fixture(params=registry.available_adapters())
def adapter_cls(request):
    return registry.get_adapter_class(request.param)


class FakeFetcher:
    def __init__(self, responder=None):
        self.responder = responder
        self.calls = []

    def get_text(self, url, **kwargs):
        self.calls.append(url)
        text = self.responder(url) if self.responder else None
        return FetchResult(url, 200 if text is not None else 503, text=text)

    get = get_text


def _replay(adapter_cls, *, empty=False):
    if adapter_cls.key == "cambridge":
        from examdata.adapters.cambridge.adapter import BASE, FAMILIES

        slug = "cambridge-igcse-mathematics-0580"
        subjects = {fam["subjects_url"] for fam in FAMILIES}
        link = f'<a href="/programmes-and-qualifications/{slug}/">Mathematics</a>'
        pdf = '<a href="/Images/123456-june-2024-question-paper-11.pdf">June 2024 Question Paper 11</a>'

        def responder(url):
            if url in subjects:
                return "<html></html>" if empty else link + link
            if url == f"{BASE}/programmes-and-qualifications/{slug}/past-papers":
                return "<html></html>" if empty else pdf + pdf
            raise AssertionError(f"Unexpected replay URL: {url}")

    elif adapter_cls.key == "edexcel":
        from examdata.adapters.edexcel.adapter import ORIGIN

        subject = "/en/qualifications/edexcel-international-advanced-levels/mathematics-2018.html"
        tags = "Pearson-UK:Qualification-Family/International-Advanced-Level,Pearson-UK:Qualification-Subject/Mathematics"
        record = {
            "url": "/content/dam/pdf/ial/maths-que.pdf", "title": "Question Paper",
            "category": ["Pearson-UK:Document-Type/Question-paper", "Pearson-UK:Exam-Series/June 2024"],
            "objectID": "maths-que", "extension": "pdf",
        }

        def responder(url):
            if "/GET.servlet?" in url:
                fq = parse_qs(urlsplit(url).query)["fq"][0]
                if 'type:"cq:Page"' in fq:
                    records = [] if empty else [{"url": subject, "title": "Mathematics"}] * 2
                else:
                    records = [] if empty else [record, record]
                return json.dumps({"searchResults": {"algoliaRecords": records}})
            if url == ORIGIN + subject:
                return f'''<div data-ng-controller="facetListCtrl" data-ng-init="init('', '[{tags}]')"></div>'''
            raise AssertionError(f"Unexpected replay URL: {url}")

    else:
        pytest.fail(f"Add an offline discovery replay for registered adapter {adapter_cls.key}")
    fetcher = FakeFetcher(responder)
    return adapter_cls(fetcher), fetcher


def _check_attributes(cls):
    assert cls.key and cls.key == cls.key.lower()
    assert cls.board_name
    assert urlsplit(cls.homepage).scheme in {"http", "https"}
    assert urlsplit(cls.homepage).netloc
    assert cls.accessibility in {"public", "partial_public", "login_walled", "unsupported_public"}


def _check_sources(adapter):
    sources = list(adapter.index_sources())
    assert sources
    for item in sources:
        assert isinstance(item, tuple) and len(item) == 2
        kind, url = item
        assert isinstance(kind, str) and kind
        assert urlsplit(url).scheme in {"http", "https"} and urlsplit(url).netloc


def _check_syllabuses(refs):
    assert refs, "Successful replay must exercise non-empty discovery"
    for ref in refs:
        assert isinstance(ref, SyllabusRef)
        assert ref.slug and ref.code and ref.title
        assert ref.qualification_key and ref.qualification_name
        assert urlsplit(ref.source_url).netloc
        assert isinstance(ref.attrs, dict)
    assert len({ref.slug for ref in refs}) == len(refs)


def _check_resources(resources):
    assert resources, "Successful replay must exercise non-empty resources"
    for res in resources:
        assert isinstance(res, DiscoveredResource)
        assert urlsplit(res.url).scheme in {"http", "https"} and urlsplit(res.url).netloc
        assert res.doc_type and 0 <= res.confidence <= 1
        assert isinstance(res.meta, dict)
        assert isinstance(res.evidence, dict) and res.evidence
        assert res.page_url and urlsplit(res.page_url).netloc
    assert len({res.url for res in resources}) == len(resources)


def test_adapter_has_required_class_attributes(adapter_cls):
    _check_attributes(adapter_cls)


def test_adapter_key_matches_registry(adapter_cls):
    assert registry.get_adapter_class(adapter_cls.key) is adapter_cls


def test_adapter_is_constructible_with_fetcher(adapter_cls):
    assert isinstance(adapter_cls(FakeFetcher()), BoardAdapter)


def test_adapter_implements_all_abstract_methods(adapter_cls):
    for name in ("index_sources", "discover_syllabuses", "discover_resources"):
        assert getattr(adapter_cls, name) is not getattr(BoardAdapter, name)


def test_registry_has_at_least_one_adapter_and_no_load_failures():
    assert registry.available_adapters()
    assert not registry.LOAD_FAILURES, registry.LOAD_FAILURES


def test_unknown_adapter_key_raises():
    with pytest.raises(KeyError):
        registry.get_adapter_class("no-such-board")


def test_index_sources_returns_kind_url_pairs(adapter_cls):
    _check_sources(adapter_cls(FakeFetcher()))


def test_index_sources_is_deterministic(adapter_cls):
    assert adapter_cls(FakeFetcher()).index_sources() == adapter_cls(FakeFetcher()).index_sources()


def test_discovery_reports_transport_failure(adapter_cls):
    adapter = adapter_cls(FakeFetcher())
    if adapter_cls.key == "edexcel":
        from examdata.adapters.edexcel.servlet import ServletError

        with pytest.raises(ServletError):
            list(adapter.discover_syllabuses())
    else:
        assert list(adapter.discover_syllabuses()) == []


def test_discover_syllabuses_yields_well_formed_refs(adapter_cls):
    adapter, fetcher = _replay(adapter_cls)
    assert fetcher.calls == []
    refs = list(adapter.discover_syllabuses())
    _check_syllabuses(refs)
    assert fetcher.calls


def test_discover_syllabuses_is_lazy(adapter_cls):
    adapter, fetcher = _replay(adapter_cls)
    iterator = adapter.discover_syllabuses()
    assert iter(iterator) is iterator
    assert fetcher.calls == []
    next(iterator)
    assert fetcher.calls


def test_discover_syllabuses_accepts_valid_empty_results(adapter_cls):
    adapter, _ = _replay(adapter_cls, empty=True)
    assert list(adapter.discover_syllabuses()) == []


def test_discover_resources_yields_well_formed_items(adapter_cls):
    adapter, fetcher = _replay(adapter_cls)
    syllabus = next(adapter.discover_syllabuses())
    resources = list(adapter.discover_resources(syllabus))
    _check_resources(resources)
    for resource in resources:
        normalized = adapter.normalize_metadata(resource)
        assert normalized["doc_type"] == resource.doc_type
        assert normalized["year"] == 2024
        assert normalized["subject_code"] == syllabus.code
    assert fetcher.calls


def test_discover_resources_accepts_valid_empty_results(adapter_cls):
    adapter, _ = _replay(adapter_cls)
    syllabus = next(adapter.discover_syllabuses())
    adapter.fetcher = _replay(adapter_cls, empty=True)[1]
    assert list(adapter.discover_resources(syllabus)) == []


def test_normalize_metadata_handles_empty_meta(adapter_cls):
    adapter = adapter_cls(FakeFetcher())
    resource = DiscoveredResource("https://example.invalid/a.pdf", None, "other", 0.1)
    out = adapter.normalize_metadata(resource)
    assert isinstance(out, dict) and out["doc_type"] == "other"
    assert any(isinstance(value, dict) for value in out.values())


def test_adapter_does_not_hardcode_credentials_or_disable_tls(adapter_cls):
    src = inspect.getsource(adapter_cls)
    for bad in ("password", "api_key", "apikey", "secret", "token=", "authorization:"):
        assert bad not in src.lower()
    assert "verify=False" not in src and "verify = False" not in src


@pytest.mark.parametrize("check", [_check_attributes, _check_sources, _check_syllabuses, _check_resources])
def test_suite_rejects_a_broken_adapter(check):
    class BrokenAdapter(BoardAdapter):
        key = ""
        board_name = ""
        homepage = "not-a-url"
        accessibility = "whatever"

        def index_sources(self):
            return [("only-one-element",)]

        def discover_syllabuses(self):
            return []

        def discover_resources(self, syllabus):
            return []

    target = BrokenAdapter if check is _check_attributes else (
        BrokenAdapter(FakeFetcher()) if check is _check_sources else []
    )
    with pytest.raises(AssertionError):
        check(target)
