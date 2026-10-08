"""`examdata.materials.catalog` / `fetch` 纯函数单测。

只覆盖不依赖网络与数据库的内部工具函数：目录读取与过滤、条目投影、
版本选择、文件名派生、CIE 镜像清单解析与参数校验、取回守卫。端到端
HTTP 契约（状态码、二进制/base64 出口、robots 403）已由
`test_api_materials.py` 覆盖，此处不重复。

`examdata.materials` 包的 `__init__` 会加载 `router`（依赖 fastapi），
因此先做 `importorskip`，与 `test_api_materials.py` 同一约定。
"""

from __future__ import annotations

import hashlib
import json

import pytest

pytest.importorskip("fastapi")

from examdata.core.fetch import FetchResult, RobotsDisallowed  # noqa: E402
from examdata.materials import catalog as C  # noqa: E402
from examdata.materials import fetch as F  # noqa: E402
from examdata.paperqa.errors import (  # noqa: E402
    AccessDenied,
    InvalidRequest,
    NotFound,
    UpstreamError,
)
from examdata.paperqa.models import Document  # noqa: E402

# ---------------------------------------------------------------------------
# 替身与工具
# ---------------------------------------------------------------------------


class _ManifestFetcher:
    """resolve 用的假抓取器：只实现 post_form，记录调用并返回预置响应。"""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_form(self, url, data, **kwargs):
        self.calls.append((url, dict(data), dict(kwargs)))
        return self.response


class _RobotsFetcher:
    """按开关拒绝 robots 的假抓取器，用于守卫路径；记录被预检的 URL。"""

    def __init__(self, blocked: bool = False):
        self.blocked = blocked
        self.allowed = []

    def assert_allowed(self, url):
        self.allowed.append(url)
        if self.blocked:
            raise RobotsDisallowed(f"robots.txt 禁止抓取 {url}")


def _manifest(rows, total=None):
    """镜像目录接口的 JSON 响应（total 默认与 rows 一致）。"""
    payload = {"total": len(rows) if total is None else total, "rows": rows}
    return FetchResult(F.CIE_RENUM_URL, 200, text=json.dumps(payload))


def _item(**overrides):
    """item_summary 用的合成条目：字段齐全，可逐项覆盖。"""
    item = {
        "id": "demo",
        "board": "cie",
        "title": "Demo",
        "title_zh": "演示",
        "kind": "insert",
        "candidate_facing": True,
        "delivery": "standalone",
        "access": "public",
        "subjects": ["9709"],
        "subjects_kind": "applicable",
        "applies_to": "演示用",
        "versions": [
            {
                "label": "v1",
                "url": "https://example.com/v1.pdf",
                "sha256": "S",
                "verification": "实测细节不进入摘要",
            }
        ],
        "evidence": [{"kind": "k"}, {"kind": "k"}],
        "note": "备注",
        "unit_codes": ["WCH12"],
        "dynamic": {"endpoint": "/api/v1/materials/cie/in-paper", "params": ["subject"]},
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------------------
# catalog：目录读取与过滤
# ---------------------------------------------------------------------------


def test_load_catalog_shape_and_cache():
    data = C.load_catalog()
    assert data["schema_version"] == C.SCHEMA_VERSION == "1"
    items = data["items"]
    assert isinstance(items, list) and len(items) >= 8
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))
    assert {
        "cie-mf19-formulae-and-statistical-tables",
        "cie-periodic-table",
        "cie-inserts",
        "cie-confidential-instructions",
        "cie-additional-materials-list",
        "cie-mc-answer-sheet",
        "edexcel-ial-maths-formula-book",
        "edexcel-ial-chemistry-data-booklet",
    } <= set(ids)
    for item in items:
        assert item["board"] in {"cie", "edexcel"}
        assert item["title"] and item["title_zh"] and item["kind"]
        assert isinstance(item.get("evidence"), list) and item["evidence"]
    assert C.load_catalog() is data  # 进程内缓存：同一对象


def test_list_items_filters_board_and_subject():
    assert all(item["board"] == "cie" for item in C.list_items(board="cie"))
    assert {item["id"] for item in C.list_items(board="edexcel")} == {
        "edexcel-ial-maths-formula-book",
        "edexcel-ial-chemistry-data-booklet",
    }

    mf19 = ["cie-mf19-formulae-and-statistical-tables"]
    assert [item["id"] for item in C.list_items(subject="9709")] == mf19
    assert [item["id"] for item in C.list_items(subject=" 9709 ")] == mf19
    assert [item["id"] for item in C.list_items(subject=9709)] == mf19
    assert [item["id"] for item in C.list_items(subject="ial18-chemistry")] == [
        "edexcel-ial-chemistry-data-booklet"
    ]
    assert C.list_items(subject="9999") == []


def test_list_items_filters_kind_and_candidate_facing():
    assert [item["id"] for item in C.list_items(kind="periodic-table")] == [
        "cie-periodic-table"
    ]
    assert [item["id"] for item in C.list_items(kind="official-list")] == [
        "cie-additional-materials-list"
    ]

    facing = C.list_items(candidate_facing=True)
    assert facing and all(item["candidate_facing"] for item in facing)
    assert "cie-confidential-instructions" not in {item["id"] for item in facing}

    assert {item["id"] for item in C.list_items(candidate_facing=False)} == {
        "cie-confidential-instructions",
        "cie-additional-materials-list",
    }


def test_list_items_combines_filters_with_and():
    assert {item["id"] for item in C.list_items(board="cie", subject="9701")} == {
        "cie-periodic-table",
        "cie-inserts",
    }
    assert C.list_items(board="edexcel", subject="9701") == []
    assert C.list_items(board="cie", kind="data-booklet") == []
    assert C.list_items(kind="insert", candidate_facing=True) != []
    assert C.list_items(kind="insert", candidate_facing=False) == []


def test_get_item_known_and_missing():
    item = C.get_item("cie-mf19-formulae-and-statistical-tables")
    assert item is not None
    assert item["id"] == "cie-mf19-formulae-and-statistical-tables"
    assert item["versions"] and item["versions"][0]["sha256"]
    assert C.get_item("no-such-material") is None


def test_version_record_keeps_only_present_keys():
    version = {
        "label": "L",
        "url": "https://example.com/f.pdf",
        "sha256": "S",
        "bytes": 1,
        "pages": 2,
        "verified_at": "2026-10-04",
        "verification": "实测细节不进入摘要",
        "extra": 1,
    }
    assert C.version_record(version) == {
        "label": "L",
        "url": "https://example.com/f.pdf",
        "sha256": "S",
        "bytes": 1,
        "pages": 2,
        "verified_at": "2026-10-04",
    }
    assert C.version_record({}) == {}
    # 键存在即保留（哪怕值是 None），只丢弃键本身
    assert C.version_record({"label": None}) == {"label": None}


def test_item_summary_projects_fields_without_evidence():
    item = _item()
    summary = C.item_summary(item)
    assert summary["id"] == "demo"
    assert summary["board"] == "cie"
    assert summary["title"] == "Demo"
    assert summary["title_zh"] == "演示"
    assert summary["kind"] == "insert"
    assert summary["candidate_facing"] is True
    assert summary["delivery"] == "standalone"
    assert summary["access"] == "public"
    assert summary["subjects"] == ["9709"]
    assert summary["subjects_kind"] == "applicable"
    assert summary["applies_to"] == "演示用"
    assert summary["versions"] == [
        {"label": "v1", "url": "https://example.com/v1.pdf", "sha256": "S"}
    ]
    assert summary["evidence_count"] == 2
    assert summary["content_endpoint"] == "/api/v1/materials/demo/content"
    assert summary["note"] == "备注"
    assert summary["unit_codes"] == ["WCH12"]
    assert summary["dynamic"] == item["dynamic"]
    assert "evidence" not in summary


def test_item_summary_optional_fields_are_deep_copies():
    item = _item()
    summary = C.item_summary(item)
    assert summary["subjects"] is not item["subjects"]
    assert summary["versions"][0] is not item["versions"][0]
    assert summary["unit_codes"] is not item["unit_codes"]
    assert summary["dynamic"] is not item["dynamic"]

    summary["subjects"].append("9231")
    summary["versions"][0]["label"] = "changed"
    summary["unit_codes"].append("X")
    summary["dynamic"]["params"].append("year")
    assert item["subjects"] == ["9709"]
    assert item["versions"][0]["label"] == "v1"
    assert item["unit_codes"] == ["WCH12"]
    assert item["dynamic"]["params"] == ["subject"]


def test_item_summary_omits_falsy_optionals_and_endpoint():
    summary = C.item_summary(_item(note="", unit_codes=[], dynamic={}, versions=[]))
    assert "note" not in summary
    assert "unit_codes" not in summary
    assert "dynamic" not in summary
    assert "content_endpoint" not in summary
    assert summary["versions"] == []


def test_item_summary_defaults_for_missing_fields():
    summary = C.item_summary(
        {
            "id": "bare",
            "board": "cie",
            "title": "Bare",
            "kind": "insert",
            "subjects": None,
            "versions": None,
            "evidence": None,
        }
    )
    assert summary["title_zh"] is None
    assert summary["candidate_facing"] is False
    assert summary["delivery"] is None
    assert summary["access"] is None
    assert summary["subjects"] == []
    assert summary["subjects_kind"] is None
    assert summary["applies_to"] is None
    assert summary["versions"] == []
    assert summary["evidence_count"] == 0
    assert "content_endpoint" not in summary


def test_item_summary_on_real_catalog_item():
    item = C.get_item("cie-periodic-table")
    summary = C.item_summary(item)
    assert summary["access"] == "in-paper"
    assert "content_endpoint" not in summary  # 印在试卷内，没有独立文件
    assert summary["evidence_count"] == len(item["evidence"])
    assert summary["note"]  # 官方口径并列的备注保留


def test_content_endpoint_two_branches():
    assert (
        C.content_endpoint({"id": "x", "versions": [{"label": "v"}]})
        == "/api/v1/materials/x/content"
    )
    assert C.content_endpoint({"id": "x", "versions": []}) is None
    assert C.content_endpoint({"id": "x"}) is None


# ---------------------------------------------------------------------------
# fetch：版本选择、文件名与常量
# ---------------------------------------------------------------------------

_VERSIONS = [
    {"label": "A", "url": "https://example.com/a.pdf"},
    {"label": "B", "url": "https://example.com/b.pdf"},
]


def test_cie_urls_derive_from_origin():
    assert F.CIE_RENUM_URL == f"{F.CIE_ORIGIN}/obj/Common/Fetch/renum"
    assert F.CIE_REDIR_URL == f"{F.CIE_ORIGIN}/obj/Common/Fetch/redir/"


def test_select_version_defaults_to_first():
    assert F.select_version({"id": "x", "versions": _VERSIONS}, None) is _VERSIONS[0]


def test_select_version_by_index_and_label():
    item = {"id": "x", "versions": _VERSIONS}
    assert F.select_version(item, "1") is _VERSIONS[1]
    assert F.select_version(item, " 0 ") is _VERSIONS[0]
    assert F.select_version(item, "B") is _VERSIONS[1]
    assert F.select_version(item, " A ") is _VERSIONS[0]


def test_select_version_rejects_empty_versions():
    with pytest.raises(InvalidRequest):
        F.select_version({"id": "x", "versions": []}, None)
    with pytest.raises(InvalidRequest):
        F.select_version({"id": "x"}, None)


def test_select_version_rejects_out_of_range_and_unknown():
    item = {"id": "x", "versions": _VERSIONS}
    with pytest.raises(InvalidRequest):
        F.select_version(item, "2")
    with pytest.raises(InvalidRequest):
        F.select_version(item, "-1")  # 非纯数字 → 按 label 匹配 → 未命中
    with pytest.raises(InvalidRequest) as excinfo:
        F.select_version(item, "C")
    assert "可用" in str(excinfo.value)


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://www.cambridgeinternational.org/Images/417318-list-of-formulae-and-statistical-tables.pdf",
            "417318-list-of-formulae-and-statistical-tables.pdf",
        ),
        (
            "https://qualifications.pearson.com/content/dam/pdf/IAL_Chemistry%202018_Data_booklet_Issue_1_March%202019.pdf",
            "IAL_Chemistry 2018_Data_booklet_Issue_1_March 2019.pdf",
        ),
        ("https://example.com/a.pdf?token=1", "a.pdf"),
        ("https://example.com/dir/", "material.pdf"),
        ("", "material.pdf"),
    ],
)
def test_version_filename(url, expected):
    assert F.version_filename({"url": url}) == expected


def test_version_filename_missing_url():
    assert F.version_filename({}) == "material.pdf"


def test_fetched_static_sha256_match_semantics():
    assert F.FetchedStatic({"sha256": "abc"}, b"", "abc").sha256_match is True
    assert F.FetchedStatic({"sha256": "abc"}, b"", "def").sha256_match is False
    assert F.FetchedStatic({}, b"", "def").sha256_match is False
    assert F.FetchedStatic({"sha256": ""}, b"", "").sha256_match is False


def test_cie_material_file_regex_groups():
    match = F.CIE_MATERIAL_FILE.fullmatch("0500_s24_in_11.pdf")
    assert match is not None
    assert match.groupdict() == {
        "subject": "0500",
        "season": "s",
        "year": "24",
        "role": "in",
        "paper": "11",
    }
    for name in (
        "9701_s19_in_33.pdf",
        "0620_s16_ir_51.pdf",
        "0620_s24_ci_51.pdf",
        "0500_s24_in_1.pdf",
    ):
        assert F.CIE_MATERIAL_FILE.fullmatch(name)


@pytest.mark.parametrize(
    "name",
    [
        "0500_s24_qp_11.pdf",  # qp 不是发放资料角色
        "0500_s24_ms_11.pdf",
        "0500_s24_in_11.PDF",  # 扩展名区分大小写
        "0500_s24_in_111.pdf",  # 组件号最多两位
        "050_s24_in_11.pdf",  # 科目必须四位
        "0500_x24_in_11.pdf",  # 考季码只能是 m/s/w
        "0500_s24_in_11.pdf.bak",
        "",
    ],
)
def test_cie_material_file_regex_rejects(name):
    assert F.CIE_MATERIAL_FILE.fullmatch(name) is None


# ---------------------------------------------------------------------------
# fetch：CIE 镜像清单解析（resolve_cie_documents）
# ---------------------------------------------------------------------------


def test_resolve_filters_rows_sorts_and_builds_documents():
    rows = [
        {"file": "0500_s24_in_12.pdf"},
        {"file": "0500_s24_in_11.pdf"},
        {"file": "0500_s23_in_11.pdf"},  # 年份不符
        {"file": "0620_s24_in_11.pdf"},  # 科目不符
        {"file": "0500_m24_in_11.pdf"},  # 考季不符
        {"file": "0500_s24_qp_11.pdf"},  # 不是发放资料角色
        {"file": "0500_s24_in_1.pdf"},  # 单位数组件号
        {"file": "0500_s24_ir_51.pdf"},  # 旧 ir 角色（无 role 过滤时保留）
        "0500_s24_in_99.pdf",  # 非字典行 → 跳过
        {"file": 123},  # 文件名非字符串 → 跳过
        {"other": "0500_s24_in_77.pdf"},  # 缺 file 键 → 跳过
        {"file": "0500_s24_in_11.pdf"},  # 重复 → 去重
    ]
    fetcher = _ManifestFetcher(_manifest(rows))
    docs = F.resolve_cie_documents(fetcher, "0500", 2024, "June")

    assert [doc.name for doc in docs] == [
        "0500_s24_in_1.pdf",
        "0500_s24_in_11.pdf",
        "0500_s24_in_12.pdf",
        "0500_s24_ir_51.pdf",
    ]
    assert all(isinstance(doc, Document) for doc in docs)
    assert docs[0].url == f"{F.CIE_REDIR_URL}0500_s24_in_1.pdf"
    assert docs[0].role == "in" and docs[0].paper == "1"
    assert docs[-1].role == "ir" and docs[-1].paper == "51"

    assert len(fetcher.calls) == 1
    url, data, kwargs = fetcher.calls[0]
    assert url == F.CIE_RENUM_URL
    assert data == {"subject": "0500", "year": 2024, "season": "Jun"}
    assert kwargs == {"follow_redirects": False}


def test_resolve_strips_subject_and_accepts_year_string():
    fetcher = _ManifestFetcher(_manifest([{"file": "0500_s24_in_11.pdf"}]))
    docs = F.resolve_cie_documents(fetcher, " 0500 ", "2024", "Jun")
    assert [doc.name for doc in docs] == ["0500_s24_in_11.pdf"]
    assert fetcher.calls[0][1] == {"subject": "0500", "year": 2024, "season": "Jun"}


@pytest.mark.parametrize("season", ["Jun", "june", " JUNE "])
def test_resolve_accepts_season_aliases(season):
    fetcher = _ManifestFetcher(_manifest([{"file": "0500_s24_in_11.pdf"}]))
    docs = F.resolve_cie_documents(fetcher, "0500", 2024, season)
    assert [doc.name for doc in docs] == ["0500_s24_in_11.pdf"]
    assert fetcher.calls[0][1]["season"] == "Jun"


@pytest.mark.parametrize(
    "season,canonical,code",
    [("Mar", "Mar", "m"), ("March", "Mar", "m"), ("Nov", "Nov", "w")],
)
def test_resolve_maps_season_to_file_code(season, canonical, code):
    name = f"0500_{code}24_in_11.pdf"
    fetcher = _ManifestFetcher(_manifest([{"file": name}]))
    docs = F.resolve_cie_documents(fetcher, "0500", 2024, season)
    assert [doc.name for doc in docs] == [name]
    assert fetcher.calls[0][1]["season"] == canonical


@pytest.mark.parametrize(
    "year,name",
    [
        (2000, "0500_s00_in_11.pdf"),
        (2099, "0500_s99_in_11.pdf"),
        ("2024", "0500_s24_in_11.pdf"),
    ],
)
def test_resolve_year_boundaries(year, name):
    fetcher = _ManifestFetcher(_manifest([{"file": name}]))
    docs = F.resolve_cie_documents(fetcher, "0500", year, "Jun")
    assert [doc.name for doc in docs] == [name]


def test_resolve_filters_by_role_and_paper():
    rows = [
        {"file": "0620_s24_in_11.pdf"},
        {"file": "0620_s24_ci_51.pdf"},
        {"file": "0620_s24_ir_51.pdf"},
    ]

    fetcher = _ManifestFetcher(_manifest(rows))
    docs = F.resolve_cie_documents(fetcher, "0620", 2024, "Jun", role="CI")
    assert [doc.name for doc in docs] == ["0620_s24_ci_51.pdf"]
    assert docs[0].role == "ci"

    fetcher = _ManifestFetcher(_manifest(rows))
    docs = F.resolve_cie_documents(fetcher, "0620", 2024, "Jun", role="ir", paper=" 51 ")
    assert [doc.name for doc in docs] == ["0620_s24_ir_51.pdf"]

    fetcher = _ManifestFetcher(_manifest(rows))
    docs = F.resolve_cie_documents(fetcher, "0620", 2024, "Jun", paper="11")
    assert [doc.name for doc in docs] == ["0620_s24_in_11.pdf"]


def test_resolve_no_match_raises_not_found():
    fetcher = _ManifestFetcher(
        _manifest([{"file": "0500_s24_qp_11.pdf"}, {"file": "0500_s23_in_11.pdf"}])
    )
    with pytest.raises(NotFound):
        F.resolve_cie_documents(fetcher, "0500", 2024, "Jun")


@pytest.mark.parametrize(
    "overrides",
    [
        {"subject": "abc"},
        {"subject": "050"},
        {"subject": None},
        {"year": 1999},
        {"year": 2100},
        {"year": "abc"},
        {"year": None},
        {"season": "Dec"},
        {"season": ""},
        {"season": None},
        {"role": "qp"},
        {"role": ""},
        {"paper": "111"},
        {"paper": ""},
    ],
)
def test_resolve_rejects_bad_params_before_network(overrides):
    kwargs = {"subject": "0500", "year": 2024, "season": "Jun", **overrides}
    fetcher = _ManifestFetcher(_manifest([]))
    with pytest.raises(InvalidRequest):
        F.resolve_cie_documents(fetcher, **kwargs)
    assert fetcher.calls == []


def test_resolve_robots_blocked_raises_access_denied():
    fetcher = _ManifestFetcher(
        FetchResult(url=F.CIE_RENUM_URL, status=0, error="robots", robots_blocked=True)
    )
    with pytest.raises(AccessDenied):
        F.resolve_cie_documents(fetcher, "0500", 2024, "Jun")


def test_resolve_upstream_failure_raises_upstream_error():
    fetcher = _ManifestFetcher(FetchResult(F.CIE_RENUM_URL, 503))
    with pytest.raises(UpstreamError):
        F.resolve_cie_documents(fetcher, "0500", 2024, "Jun")


@pytest.mark.parametrize(
    "text",
    [
        "",  # 空响应体
        "not json",  # 非 JSON
        "{}",  # 缺 rows / total
        '{"total": 2, "rows": [{"file": "0500_s24_in_11.pdf"}]}',  # total 与 rows 不符
        '{"total": "x", "rows": []}',  # total 非整数
        '{"total": 1, "rows": "oops"}',  # rows 非列表
    ],
)
def test_resolve_invalid_manifest_raises_upstream_error(text):
    fetcher = _ManifestFetcher(FetchResult(F.CIE_RENUM_URL, 200, text=text))
    with pytest.raises(UpstreamError):
        F.resolve_cie_documents(fetcher, "0500", 2024, "Jun")


# ---------------------------------------------------------------------------
# fetch：取回守卫（download_cie_document / fetch_material）
# ---------------------------------------------------------------------------


def test_download_cie_document_rejects_untrusted_name():
    fetcher = _RobotsFetcher()
    doc = Document("evil.pdf", f"{F.CIE_REDIR_URL}evil.pdf", "in", "11")
    with pytest.raises(AccessDenied):
        F.download_cie_document(fetcher, doc)
    assert fetcher.allowed == []  # 信任检查在网络之前


def test_download_cie_document_rejects_mismatched_url():
    fetcher = _RobotsFetcher()
    doc = Document("0500_s24_in_11.pdf", "https://evil.example/0500_s24_in_11.pdf", "in", "11")
    with pytest.raises(AccessDenied):
        F.download_cie_document(fetcher, doc)
    assert fetcher.allowed == []


def test_download_cie_document_fetches_trusted_url(monkeypatch):
    seen = {}

    def fake_download_pdf(fetcher, document):
        seen["document"] = document
        return b"%PDF-1.4 unit"

    monkeypatch.setattr(F, "download_pdf", fake_download_pdf)
    fetcher = _RobotsFetcher()
    doc = Document("0500_s24_in_11.pdf", f"{F.CIE_REDIR_URL}0500_s24_in_11.pdf", "in", "11")

    assert F.download_cie_document(fetcher, doc) == b"%PDF-1.4 unit"
    assert fetcher.allowed == [doc.url]
    assert seen["document"] is doc


def test_download_cie_document_robots_blocked(monkeypatch):
    def fake_download_pdf(fetcher, document):
        raise AssertionError("robots 拒绝时不应发起下载")

    monkeypatch.setattr(F, "download_pdf", fake_download_pdf)
    fetcher = _RobotsFetcher(blocked=True)
    doc = Document("0500_s24_in_11.pdf", f"{F.CIE_REDIR_URL}0500_s24_in_11.pdf", "in", "11")
    with pytest.raises(AccessDenied):
        F.download_cie_document(fetcher, doc)


def test_fetch_material_missing_url_raises_before_fetching():
    fetcher = _RobotsFetcher()
    with pytest.raises(InvalidRequest):
        F.fetch_material(fetcher, {"label": "无 url 的版本"})
    with pytest.raises(InvalidRequest):
        F.fetch_material(fetcher, {"label": "空白 url", "url": "   "})
    assert fetcher.allowed == []


def test_fetch_material_hashes_bytes_and_copies_version(monkeypatch):
    seen = {}
    data = b"%PDF-1.4 unit"

    def fake_download_pdf(fetcher, document):
        seen["document"] = document
        return data

    monkeypatch.setattr(F, "download_pdf", fake_download_pdf)
    version = {
        "label": "v1",
        "url": "https://example.com/dir/a%20b.pdf",
        "sha256": "0" * 64,
    }
    fetcher = _RobotsFetcher()
    fetched = F.fetch_material(fetcher, version)

    assert fetched.data == data
    assert fetched.sha256 == hashlib.sha256(data).hexdigest()
    assert fetched.sha256_match is False  # 快照不符：如实告知，不报错
    assert fetched.version == version and fetched.version is not version
    fetched.version["label"] = "mutated"
    assert version["label"] == "v1"
    assert fetcher.allowed == [version["url"]]
    assert seen["document"].name == "a b.pdf"
    assert seen["document"].url == version["url"]
    assert seen["document"].role == "material" and seen["document"].paper == ""


def test_fetch_material_robots_blocked(monkeypatch):
    def fake_download_pdf(fetcher, document):
        raise AssertionError("robots 拒绝时不应发起下载")

    monkeypatch.setattr(F, "download_pdf", fake_download_pdf)
    version = {"label": "v1", "url": "https://example.com/a.pdf"}
    with pytest.raises(AccessDenied):
        F.fetch_material(_RobotsFetcher(blocked=True), version)


def test_select_version_and_filename_on_real_catalog_item():
    item = C.get_item("cie-mf19-formulae-and-statistical-tables")
    version = F.select_version(item, None)
    assert version["url"].startswith("https://www.cambridgeinternational.org/Images/417318")
    assert F.version_filename(version) == "417318-list-of-formulae-and-statistical-tables.pdf"
    assert version["sha256"] and version["bytes"] > 0 and version["pages"] > 0
