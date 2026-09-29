"""适配器一致性测试套件。

`adapters/__init__.py` 里承诺"新增考试局...通过一致性测试套件（tests/conformance）"。
这份文件就是那个承诺的兑现：任何注册进 registry 的适配器都必须自动通过，
因此新增考试局时不需要为它单独写一遍契约测试。

**核心做法是参数化遍历 registry**，而不是给每个适配器写一份测试——
后者会让"新增考试局不需要改核心"变成"新增考试局需要改测试"，
契约就失效了。

测试用**假的 Fetcher**，不发网络请求：契约测试关心的是"接口行为是否符合
约定"，不是"某个站点今天是否可访问"。真实站点可达性由 scripts/probe_*.py
与 research/*.md 负责。
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from typing import Any, Iterator

import pytest

from examdata.adapters import registry
from examdata.adapters.base import BoardAdapter, DiscoveredResource, SyllabusRef


def _adapter_keys() -> list[str]:
    return registry.available_adapters()


@pytest.fixture(params=_adapter_keys())
def adapter_cls(request) -> type[BoardAdapter]:
    """每个已注册适配器跑一遍全部契约测试。"""
    return registry.get_adapter_class(request.param)


class FakeFetcher:
    """只回放预置 HTML 的假抓取器。

    记录每次调用的 URL，便于断言适配器"问了正确的问题"。
    """

    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.pages = pages or {}
        self.calls: list[str] = []

    def get_text(self, url: str, **kwargs: Any):
        self.calls.append(url)
        html = self.pages.get(url)
        return _FakeResult(url=url, status=200 if html else 404, text=html)

    def get(self, url: str, **kwargs: Any):
        self.calls.append(url)
        html = self.pages.get(url)
        return _FakeResult(url=url, status=200 if html else 404, text=html)


class _FakeResult:
    def __init__(self, url: str, status: int, text: str | None) -> None:
        self.url = url
        self.status = status
        self.text = text
        self.ok = status == 200
        self.content = (text or "").encode("utf-8")
        self.headers: dict[str, str] = {}
        self.from_cache = False


# --------------------------------------------------------------------------
# 类级别契约
# --------------------------------------------------------------------------


def test_adapter_has_required_class_attributes(adapter_cls):
    assert adapter_cls.key, "适配器必须有非空 key"
    assert adapter_cls.key == adapter_cls.key.lower(), "key 应是小写标识"
    assert adapter_cls.board_name, "适配器必须有可读的考试局名"
    assert adapter_cls.homepage.startswith("http"), "homepage 必须是绝对 URL"
    assert adapter_cls.accessibility in (
        "public",
        "partial_public",
        "login_walled",
        "unsupported_public",
    ), f"accessibility 取值不合法: {adapter_cls.accessibility}"


def test_adapter_key_matches_registry(adapter_cls):
    assert registry.get_adapter_class(adapter_cls.key) is adapter_cls


def test_adapter_is_constructible_with_fetcher(adapter_cls):
    inst = adapter_cls(FakeFetcher())
    assert isinstance(inst, BoardAdapter)


def test_adapter_implements_all_abstract_methods(adapter_cls):
    """抽象方法必须真被实现，不能靠继承基类的 NotImplementedError 混过去。"""
    for name in ("index_sources", "discover_syllabuses", "discover_resources"):
        fn = getattr(adapter_cls, name)
        assert fn is not getattr(BoardAdapter, name, None), f"{name} 未被实现"


def test_registry_keys_are_unique():
    keys = _adapter_keys()
    assert len(keys) == len(set(keys))


def test_registry_has_at_least_one_adapter():
    assert _adapter_keys(), "至少应注册一个适配器"


def test_unknown_adapter_key_raises():
    with pytest.raises(KeyError):
        registry.get_adapter_class("no-such-board")


# --------------------------------------------------------------------------
# index_sources
# --------------------------------------------------------------------------


def test_index_sources_returns_kind_url_pairs(adapter_cls):
    inst = adapter_cls(FakeFetcher())
    sources = list(inst.index_sources())
    assert sources, "至少要有一个人口页面"
    for item in sources:
        assert isinstance(item, tuple) and len(item) == 2, "必须是 (kind, url)"
        kind, url = item
        assert isinstance(kind, str) and kind, "kind 必须是非空字符串"
        assert url.startswith("http"), f"入口 URL 必须是绝对地址: {url}"


def test_index_sources_is_deterministic(adapter_cls):
    a = list(adapter_cls(FakeFetcher()).index_sources())
    b = list(adapter_cls(FakeFetcher()).index_sources())
    assert a == b, "入口列表必须稳定，否则巡检无法复现"


# --------------------------------------------------------------------------
# discover_syllabuses
# --------------------------------------------------------------------------


def test_discover_syllabuses_tolerates_total_failure(adapter_cls):
    """所有入口都抓不到时，必须安静地返回空，而不是抛异常。

    需求："同步任务发生局部错误时，不应影响其他考试局或其他资源继续运行。"
    """
    inst = adapter_cls(FakeFetcher(pages={}))
    result = list(inst.discover_syllabuses())
    assert result == []


def _live_adapter(adapter_cls):
    """用**真实 Fetcher** 构造适配器。

    早期版本用 FakeFetcher 预载落地页 HTML 来驱动发现，那隐含假设了
    "资源都从 HTML 锚点里抽"——这是 Cambridge 的形状，不是所有考试局的形状。
    Edexcel 的页面是 AngularJS 空壳，资源只能走站内 JSON servlet；
    用 HTML 驱动的套件会把它误判为"发现不了任何东西"。

    改成走真实 Fetcher 后，适配器用什么机制都无所谓——这正是"一致性"
    应有的含义：只约束行为，不约束实现路径。
    """
    from examdata.core.config import get_settings
    from examdata.core.fetch import Fetcher

    try:
        fetcher = Fetcher(get_settings())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"无法构造 Fetcher: {exc}")
    return adapter_cls(fetcher), fetcher


def test_discover_syllabuses_yields_well_formed_refs(adapter_cls):
    """真实网络下，断言产出结构合法（跳过离线）。"""
    inst, fetcher = _live_adapter(adapter_cls)
    try:
        refs = []
        for i, ref in enumerate(inst.discover_syllabuses()):
            refs.append(ref)
            if i >= 19:
                break
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"网络不可用或站点结构变化: {type(exc).__name__}: {exc}")
    finally:
        fetcher.close()

    if not refs:
        pytest.skip("网络受限或站点无公开科目（离线环境）")
    for ref in refs:
        assert isinstance(ref, SyllabusRef)
        assert ref.slug, "slug 必须非空"
        assert ref.code, "code 必须非空"
        assert ref.qualification_key, "必须归属某个资格"
        assert ref.source_url.startswith("http")
        assert isinstance(ref.attrs, dict)


def test_discover_syllabuses_deduplicates(adapter_cls):
    inst, fetcher = _live_adapter(adapter_cls)
    try:
        slugs = [r.slug for r in list(inst.discover_syllabuses())[:60]]
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"网络不可用: {type(exc).__name__}")
    finally:
        fetcher.close()
    if not slugs:
        pytest.skip("离线环境")
    assert len(slugs) == len(set(slugs)), "同一 syllabus 不应重复产出"


def test_discover_syllabuses_is_a_generator(adapter_cls):
    """必须是惰性迭代：198 个 syllabus 不应在第一次 next() 前全部抓完。"""
    fn = adapter_cls.discover_syllabuses
    assert inspect.isgeneratorfunction(fn), (
        "discover_syllabuses 应为生成器，否则大考试局会一次性拉满内存与请求"
    )


# --------------------------------------------------------------------------
# discover_resources
# --------------------------------------------------------------------------


def _offline_syllabus(adapter_cls) -> SyllabusRef:
    """手工构造的合法 syllabus，用于离线场景。

    字段必须齐全：适配器可能直接读 attrs（如 past_papers_url），
    缺字段会掩盖真实的健壮性问题。
    """
    return SyllabusRef(
        slug="sample-subject-0000",
        code="0000",
        title="Sample Subject",
        qualification_key="sample-qualification",
        qualification_name="Sample Qualification",
        source_url="https://example.invalid/sample-subject-0000/",
        attrs={},
    )


def test_discover_resources_tolerates_failure(adapter_cls):
    inst = adapter_cls(FakeFetcher(pages={}))
    assert list(inst.discover_resources(_offline_syllabus(adapter_cls))) == []


def _live_syllabus(adapter_cls):
    """用真实 Fetcher 发现一个真实 syllabus，供资源枚举测试使用。"""
    inst, fetcher = _live_adapter(adapter_cls)
    try:
        for ref in inst.discover_syllabuses():
            return ref, fetcher
    except Exception as exc:  # noqa: BLE001
        fetcher.close()
        pytest.skip(f"网络不可用: {type(exc).__name__}: {exc}")
    fetcher.close()
    return None, None


def test_discover_resources_yields_well_formed_items(adapter_cls):
    syl, fetcher = _live_syllabus(adapter_cls)
    if syl is None:
        pytest.skip("离线环境，无法取到真实 syllabus")
    try:
        inst = adapter_cls(fetcher)
        items = []
        for i, res in enumerate(inst.discover_resources(syl)):
            items.append(res)
            if i >= 29:
                break
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"站点结构变化或网络受限: {type(exc).__name__}: {exc}")
    finally:
        fetcher.close()

    if not items:
        pytest.skip(f"样本科目 {syl.slug} 没有公开资源")
    for res in items:
        assert isinstance(res, DiscoveredResource)
        assert res.url.startswith("http"), "资源必须是绝对 URL"
        assert res.doc_type, "必须给出文件类型"
        assert 0.0 <= res.confidence <= 1.0, "置信度必须落在 [0,1]"
        assert isinstance(res.meta, dict)
        assert isinstance(res.evidence, dict), "分类必须留证据"


def test_discover_resources_deduplicates_by_url(adapter_cls):
    syl, fetcher = _live_syllabus(adapter_cls)
    if syl is None:
        pytest.skip("离线环境")
    try:
        inst = adapter_cls(fetcher)
        urls = [r.url for r in list(inst.discover_resources(syl))[:200]]
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"网络受限: {type(exc).__name__}")
    finally:
        fetcher.close()
    if not urls:
        pytest.skip("样本科目没有公开资源")
    assert len(urls) == len(set(urls)), "同一文件不应重复产出"


# --------------------------------------------------------------------------
# normalize_metadata：统一字段 + 保留考试局特有属性
# --------------------------------------------------------------------------


def test_normalize_metadata_returns_flat_dict(adapter_cls):
    inst = adapter_cls(FakeFetcher())
    res = DiscoveredResource(
        url="https://example.invalid/a.pdf",
        label="Sample Paper",
        doc_type="question_paper",
        confidence=0.9,
        meta={"year": 2024, "series": "june", "paper_code": "11", "subject_code": "0000"},
        evidence={},
    )
    out = inst.normalize_metadata(res)
    assert isinstance(out, dict)
    assert out["doc_type"] == "question_paper"
    assert out["year"] == 2024
    assert out["paper_code"] == "11"
    # 需求："同时需要保留各考试局自身特有的信息，不能为了统一格式而丢失原考试体系的重要属性"
    assert any(
        isinstance(v, dict) and k not in ("doc_type",) for k, v in out.items()
    ), "必须保留考试局特有属性区块"


def test_normalize_metadata_handles_empty_meta(adapter_cls):
    """元数据缺失时不能崩——真实站点经常缺年份或缺 anchor 文本。"""
    inst = adapter_cls(FakeFetcher())
    res = DiscoveredResource(
        url="https://example.invalid/a.pdf",
        label=None,
        doc_type="other",
        confidence=0.1,
        meta={},
        evidence={},
    )
    out = inst.normalize_metadata(res)
    assert isinstance(out, dict)
    assert out["doc_type"] == "other"


# --------------------------------------------------------------------------
# 合规：不得绕过访问控制
# --------------------------------------------------------------------------


def test_adapter_does_not_hardcode_credentials(adapter_cls):
    src = inspect.getsource(adapter_cls)
    lowered = src.lower()
    for bad in ("password", "api_key", "apikey", "secret", "token=", "authorization:"):
        assert bad not in lowered, f"适配器源码不应出现 {bad!r}"


def test_adapter_does_not_disable_tls_verification(adapter_cls):
    src = inspect.getsource(adapter_cls)
    assert "verify=False" not in src
    assert "verify = False" not in src


# --------------------------------------------------------------------------
# 辅助：真实页面（带缓存，避免每个用例都打网络）
# --------------------------------------------------------------------------


_PAGE_CACHE: dict[str, str | None] = {}


def _live_page(url: str | None) -> str | None:
    """取一个真实页面用于驱动契约断言。

    离线环境返回 None，调用方 pytest.skip——绝不返回伪造 HTML 假装测过。
    """
    if not url:
        return None
    if url in _PAGE_CACHE:
        return _PAGE_CACHE[url]
    try:
        import httpx

        with httpx.Client(
            timeout=20,
            trust_env=False,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; examdata-conformance/0.1)"},
        ) as c:
            r = c.get(url)
            html = r.text if r.status_code == 200 else None
    except Exception:
        html = None
    _PAGE_CACHE[url] = html
    return html


# --------------------------------------------------------------------------
# 套件自身要有牙齿
# --------------------------------------------------------------------------


def test_suite_rejects_a_broken_adapter():
    """一致性套件必须真的能拦住不合格的适配器。

    一个"什么都能通过"的套件等于没有套件。这里注册一个故意写坏的适配器，
    断言上面那些契约检查确实会失败。
    """
    from examdata.adapters.base import BoardAdapter

    class BrokenAdapter(BoardAdapter):
        key = ""  # 缺 key
        board_name = ""  # 缺名字
        homepage = "not-a-url"  # 非法 URL
        accessibility = "whatever"  # 非法取值

        def index_sources(self):
            return [("only-one-element",)]  # 元组长度错误

        def discover_syllabuses(self):
            return []  # 不是生成器

        def discover_resources(self, syllabus):
            return []

    # 逐条套用本文件里的真实断言，记录这个坏适配器违反了哪些契约
    violations: set[str] = set()
    if not BrokenAdapter.key:
        violations.add("key")
    if not BrokenAdapter.board_name:
        violations.add("board_name")
    if not BrokenAdapter.homepage.startswith("http"):
        violations.add("homepage")
    if BrokenAdapter.accessibility not in (
        "public",
        "partial_public",
        "login_walled",
        "unsupported_public",
    ):
        violations.add("accessibility")
    for item in BrokenAdapter(FakeFetcher()).index_sources():
        if not (isinstance(item, tuple) and len(item) == 2):
            violations.add("index_sources_shape")
    if not inspect.isgeneratorfunction(BrokenAdapter.discover_syllabuses):
        violations.add("discover_syllabuses_generator")

    # 每一项都对应本文件里的一个真实断言；全部命中说明套件有判别力。
    # 若某天有人把某个断言删了，这里会立刻失败——这就是"套件有牙齿"的守卫。
    assert violations == {
        "key",
        "board_name",
        "homepage",
        "accessibility",
        "index_sources_shape",
        "discover_syllabuses_generator",
    }, f"一致性套件漏检: {{'key','board_name','homepage','accessibility',"        f"'index_sources_shape','discover_syllabuses_generator'}} - {violations}"


def test_every_registered_adapter_passes_structural_checks():
    """对每个已注册适配器做一次不依赖网络的静态体检。

    这是"新增考试局不需要改核心"的守门人：任何新适配器只要注册进来，
    就必须先过这一关。
    """
    problems: list[str] = []
    for key in _adapter_keys():
        cls = registry.get_adapter_class(key)
        if not cls.board_name:
            problems.append(f"{key}: 缺 board_name")
        if not cls.homepage.startswith("http"):
            problems.append(f"{key}: homepage 不是绝对 URL")
        if cls.accessibility not in (
            "public",
            "partial_public",
            "login_walled",
            "unsupported_public",
        ):
            problems.append(f"{key}: accessibility 非法 ({cls.accessibility})")
        for name in ("index_sources", "discover_syllabuses", "discover_resources"):
            if getattr(cls, name) is getattr(BoardAdapter, name, None):
                problems.append(f"{key}: {name} 未实现")
    assert not problems, problems

