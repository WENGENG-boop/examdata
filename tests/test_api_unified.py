"""统一网关（/api/v1）的契约测试：用 TestClient 打真实数据库。

覆盖四件事：

1. `/api/v1/boards` 的能力清单——两个考试局的别名、考季、模式、裁剪能力齐全；
2. `/api/v1/search` 跨局检索——`by_board` 两个 key 都在，且与既有 `/questions`
   的结果自洽（同条件同总数、同 items），board 别名归一等价；
3. `/api/v1/paper` 的清单分支与 `format` 校验——不下载 PDF，只验分支与 schema；
4. `/api/v1/question/{id}` 的单题聚合视图——`source.paper_endpoint` 的形状与
   定位信息（考季已从数据库的 `june` / `june 2025` 归一成 CIE 认的 `Jun`）。

这里刻意**不下载任何 PDF**（不碰上游文件），取卷的 URL 只断言形状；
真正的下载验证在开发时手工做。上游目录接口的连通性由
`test_paper_manifest_against_live_catalogue` 单独覆盖，离线时跳过。
"""

from __future__ import annotations

import importlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from examdata.api.app import app  # noqa: E402
from examdata.api.unified import (  # noqa: E402
    BOARD_ALIASES,
    infer_board,
    normalize_board,
    normalize_season,
)
from examdata.core.fetch import FetchResult  # noqa: E402
from examdata.paperqa import resolve  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class FakeFetcher:
    """假上游：只回 CIE 目录清单，不提供任何文件下载。

    与 `tests/test_paperqa_api.py` 的写法一致（这里自带一份，避免测试模块
    互相 import）。清单里的文件名与真实上游一致，便于比对解析结果。
    """

    def __init__(self, names=("0580_s24_qp_11.pdf",)):
        self.names = list(names)

    def post_form(self, url, data, **kwargs):
        rows = [{"file": name} for name in self.names]
        return FetchResult(
            url, 200, text=json.dumps({"total": len(rows), "rows": rows})
        )


# --------------------------------------------------------------------------
# 能力发现
# --------------------------------------------------------------------------


def test_boards_lists_both_boards_with_full_capabilities(client):
    r = client.get("/api/v1/boards")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "1"

    boards = {b["board"]: b for b in body["boards"]}
    assert set(boards) == {"cie", "edexcel"}
    for canonical, entry in boards.items():
        for field in (
            "aliases",
            "name",
            "upstream",
            "subject_hint",
            "subject_pattern",
            "seasons",
            "modes",
            "default_mode",
        ):
            assert entry[field], f"{canonical} 缺少 {field}"
        assert isinstance(entry["question_crop"], bool)
        assert entry["db_key"] == ("cambridge" if canonical == "cie" else "edexcel")
        assert set(BOARD_ALIASES[canonical]) <= set(entry["aliases"])

    cie, edexcel = boards["cie"], boards["edexcel"]
    assert cie["seasons"] == ["Mar", "Jun", "Nov"]
    assert cie["modes"] == ["qp", "ms", "both"]
    assert cie["question_crop"] is False
    assert cie["default_mode"] == "qp"
    assert cie["upstream"] == "cie.fraft.cn"

    assert edexcel["seasons"] == ["January", "June", "October", "November"]
    assert edexcel["modes"] == ["paper", "question", "qa"]
    assert edexcel["question_crop"] is True
    assert edexcel["default_mode"] == "paper"
    assert edexcel["upstream"] == "qualifications.pearson.com"

    auto = body["auto_detect"]
    assert auto["cie_subject_pattern"] == r"^\d{4}$"
    assert auto["fallback_board"] == "edexcel"
    assert auto["explicit_board_wins"] is True


# --------------------------------------------------------------------------
# 跨考试局检索
# --------------------------------------------------------------------------


def test_search_by_board_covers_both_boards_and_matches_questions(client):
    """by_board 必须两个 key 都在，且与既有 /questions 同条件同结果。"""
    params = {"subject": "0580", "year": 2024, "limit": 5}
    unified = client.get("/api/v1/search", params=params).json()
    legacy = client.get("/questions", params=params).json()

    assert set(unified["by_board"]) == {"cambridge", "edexcel"}
    assert unified["by_board"]["cambridge"] > 0
    assert unified["limit"] == 5 and unified["offset"] == 0
    assert unified["total"] == legacy["total"]
    assert unified["items"] == legacy["items"]
    # 不限考试局时，分局计数不能超过总数（两者同源自同一份条件）
    assert unified["total"] >= unified["by_board"]["cambridge"]
    assert all(item["board"] == "cambridge" for item in unified["items"])
    # 未显式传 board：顶层 board 为空，不假装判定了什么
    assert unified["board"] is None
    assert unified["board_source"] is None


def test_search_board_restricts_total_to_that_board(client):
    params = {"subject": "0580", "year": 2024, "board": "cie", "limit": 5}
    unified = client.get("/api/v1/search", params=params).json()
    legacy = client.get(
        "/questions", params={**params, "board": "cambridge"}
    ).json()
    assert unified["total"] == legacy["total"] == unified["by_board"]["cambridge"]
    assert unified["board"] == "cie"
    assert unified["board_source"] == "explicit"


def test_search_board_aliases_are_equivalent(client):
    base = {"subject": "0580", "limit": 5}
    reference = client.get("/api/v1/search", params={**base, "board": "cambridge"}).json()
    assert reference["total"] > 0
    for alias in ("cie", "CA", " Cambridge "):
        body = client.get("/api/v1/search", params={**base, "board": alias}).json()
        assert body["total"] == reference["total"], alias
        assert body["items"] == reference["items"], alias
        assert body["board"] == "cie"

    edexcel = client.get("/api/v1/search", params={**base, "board": "edexcel"}).json()
    for alias in ("edx", "Pearson", "IAL"):
        body = client.get("/api/v1/search", params={**base, "board": alias}).json()
        assert body["board"] == "edexcel"
        assert body["total"] == edexcel["total"]
        assert body["items"] == edexcel["items"]


def test_search_rejects_unknown_board(client):
    r = client.get("/api/v1/search", params={"subject": "0580", "board": "ocr"})
    assert r.status_code == 422
    assert set(r.json()) == {"detail"}


def test_search_passes_db_level_filters_through(client):
    """leaves_only / has_answer / marks 这些条件必须与 /questions 同语义。"""
    params = {"leaves_only": True, "has_answer": True, "marks_min": 2, "limit": 10}
    unified = client.get("/api/v1/search", params=params).json()
    legacy = client.get("/questions", params=params).json()
    assert unified["total"] == legacy["total"] > 0
    assert unified["items"] == legacy["items"]
    assert all(item["marks"] >= 2 for item in unified["items"])


def test_search_pagination_is_stable(client):
    first = client.get("/api/v1/search", params={"limit": 5, "offset": 0}).json()
    second = client.get("/api/v1/search", params={"limit": 5, "offset": 5}).json()
    assert first["offset"] == 0 and second["offset"] == 5
    assert len(first["items"]) == 5 and len(second["items"]) == 5
    assert [i["question_id"] for i in first["items"]] != [
        i["question_id"] for i in second["items"]
    ]


# --------------------------------------------------------------------------
# 统一取卷
# --------------------------------------------------------------------------


def test_paper_manifest_branch_matches_resolve_schema(monkeypatch):
    """download=false 走清单分支：schema 与 /paper-qa/resolve 一致，另加 board。"""
    module = importlib.import_module("examdata.api.unified")
    monkeypatch.setattr(
        module, "paperqa_resolve", lambda *a: resolve(*a, fetcher=FakeFetcher())
    )
    params = {"subject": "0580", "year": 2024, "season": "Jun", "paper": "11"}
    with TestClient(app) as client:
        r = client.get("/api/v1/paper", params={**params, "download": False})
        legacy = client.get("/paper-qa/resolve", params={**params, "board": "cie"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "schema_version",
        "request",
        "counts",
        "documents",
        "files",
        "board",
        "board_source",
    }
    assert set(legacy.json()) == set(body) - {"board", "board_source"}
    assert body["board"] == "cie"
    assert body["board_source"] == "inferred"
    assert body["request"]["board"] == "cie"
    assert body["files"] == []
    assert body["counts"] == {"documents": 1, "files": 0, "bytes": 0}
    assert [d["name"] for d in body["documents"]] == ["0580_s24_qp_11.pdf"]


def test_paper_manifest_explicit_board_is_marked_explicit(monkeypatch):
    module = importlib.import_module("examdata.api.unified")
    monkeypatch.setattr(
        module, "paperqa_resolve", lambda *a: resolve(*a, fetcher=FakeFetcher())
    )
    params = {
        "subject": "0580",
        "year": 2024,
        "season": "June",
        "paper": "11",
        "board": "cambridge",
        "download": False,
        "format": "binary",
    }
    with TestClient(app) as client:
        body = client.get("/api/v1/paper", params=params).json()
    assert body["board"] == "cie"
    assert body["board_source"] == "explicit"
    # 考季别名（June）由 paperqa 归一成 CIE 的 Jun，并回显在 request 里
    assert body["request"]["season"] == "Jun"


def test_paper_rejects_invalid_format(client):
    params = {"subject": "0580", "year": 2024, "season": "Jun", "paper": "11"}
    for download in ("true", "false"):
        r = client.get("/api/v1/paper", params={**params, "format": "xml", "download": download})
        assert r.status_code == 422, download
        assert set(r.json()) == {"detail"}


def test_paper_rejects_unknown_board_without_touching_upstream(client):
    r = client.get(
        "/api/v1/paper",
        params={"subject": "0580", "year": 2024, "season": "Jun", "board": "ocr"},
    )
    assert r.status_code == 422
    assert set(r.json()) == {"detail"}


def test_paper_manifest_against_live_catalogue(client):
    """真打一次上游目录接口（只解析清单，不下载 PDF）。

    上游不可达时跳过：这条用例的价值在于确认"清单分支对真实上游可用"，
    而不是把第三方站点的可用性绑进测试结果。
    """
    params = {
        "subject": "0580",
        "year": 2024,
        "season": "Jun",
        "paper": "11",
        "download": False,
    }
    r = client.get("/api/v1/paper", params=params)
    if r.status_code != 200:
        pytest.skip(f"上游不可用（HTTP {r.status_code}）：{r.json().get('detail')}")
    body = r.json()
    assert body["board"] == "cie" and body["board_source"] == "inferred"
    assert body["files"] == []
    assert [d["name"] for d in body["documents"]] == ["0580_s24_qp_11.pdf"]


# --------------------------------------------------------------------------
# 单题聚合视图
# --------------------------------------------------------------------------


def test_question_view_for_real_cambridge_question(client):
    listing = client.get(
        "/api/v1/search",
        params={"subject": "0580", "year": 2024, "paper": "11", "limit": 1},
    ).json()["items"]
    assert listing, "0580 June 2024 Paper 11 应有已解析的题目"
    item = listing[0]

    r = client.get(f"/api/v1/question/{item['question_id']}")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"question_id", "board", "source", "bundle"}
    assert body["question_id"] == item["question_id"]
    assert body["board"] == "cambridge"
    # bundle 必须是既有单题接口的原样结果，不二次包装
    assert body["bundle"] == client.get(f"/questions/{item['question_id']}").json()

    source = body["source"]
    assert source["board"] == "cambridge"
    assert source["board_canonical"] == "cie"
    assert source["subject_code"] == item["subject_code"] == "0580"
    assert source["year"] == item["year"] == 2024
    assert source["paper_code"] == item["paper_code"] == "11"
    # 数据库里这一卷的 session 写作 "june"，必须归一成 CIE 认的 "Jun"
    assert source["session_raw"] == "june"
    assert source["session"] == "Jun"
    assert normalize_season(source["session_raw"], "cie") == source["session"]

    endpoint = source["paper_endpoint"]
    assert endpoint, "定位信息齐全的题必须给出可取回的 URL"
    parts = urlsplit(endpoint)
    assert parts.scheme == "" and parts.netloc == ""
    assert parts.path == "/api/v1/paper"
    query = parse_qs(parts.query)
    assert query["subject"] == ["0580"]
    assert query["year"] == ["2024"]
    assert query["season"] == ["Jun"]
    assert query["paper"] == ["11"]
    assert query["mode"] == ["qp"]


def test_question_view_endpoint_is_shaped_like_a_real_request(client):
    """paper_endpoint 的参数必须真的能被 /api/v1/paper 接受（只解析清单）。

    这里不下载文件：把 endpoint 的 query 原样喂给 download=false 的清单分支，
    上游给出 200 才算"可直接调用"。
    """
    listing = client.get(
        "/api/v1/search",
        params={"subject": "0580", "year": 2024, "paper": "11", "limit": 1},
    ).json()["items"]
    endpoint = client.get(f"/api/v1/question/{listing[0]['question_id']}").json()[
        "source"
    ]["paper_endpoint"]
    query = parse_qs(urlsplit(endpoint).query)
    params = {key: values[0] for key, values in query.items()}
    r = client.get("/api/v1/paper", params={**params, "download": False})
    if r.status_code != 200:
        pytest.skip(f"上游不可用（HTTP {r.status_code}）：{r.json().get('detail')}")
    assert r.json()["request"]["paper"] == "11"


def test_question_view_reports_missing_locator_honestly(client):
    """样卷没有考季：不能拼一个取不回来的 URL，宁可为 null。"""
    listing = client.get(
        "/api/v1/search", params={"subject": "0580", "year": 2025, "limit": 50}
    ).json()["items"]
    assert listing, "2025 样卷应有已解析的题目"
    sources = [
        client.get(f"/api/v1/question/{item['question_id']}").json()["source"]
        for item in listing
    ]
    without_season = [s for s in sources if s["session_raw"] is None]
    if not without_season:
        pytest.skip("该年份的题都带考季，没有可验证的样卷题")
    source = without_season[0]
    assert source["session"] is None
    assert source["paper_endpoint"] is None


def test_question_view_404(client):
    r = client.get("/api/v1/question/99999999")
    assert r.status_code == 404
    assert set(r.json()) == {"detail"}


# --------------------------------------------------------------------------
# 归一函数的单元断言（不经过 HTTP）
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("0580", "cie"),
        (" 9709 ", "cie"),
        ("accounting-2023-modular", "edexcel"),
        ("ial18-accounting", "edexcel"),
        ("Economics", "edexcel"),
        ("", "edexcel"),
    ],
)
def test_infer_board(subject, expected):
    assert infer_board(subject) == expected


def test_normalize_board_is_case_insensitive_and_strict():
    assert normalize_board("CAMBRIDGE") == "cie"
    assert normalize_board(" Pearson ") == "edexcel"
    assert normalize_board(None) is None
    with pytest.raises(HTTPException) as exc:
        normalize_board("ocr")
    assert exc.value.status_code == 422


def test_normalize_season_handles_dirty_database_values():
    assert normalize_season("june", "cie") == "Jun"
    assert normalize_season("june 2024", "cie") == "Jun"
    assert normalize_season("november 2025", "cie") == "Nov"
    assert normalize_season("june 2025", "edexcel") == "June"
    assert normalize_season("november 2024", "edexcel") == "November"
    # 该考试局不认的考季与缺失考季都返回 None，不猜
    assert normalize_season("january 2024", "cie") is None
    assert normalize_season(None, "cie") is None
    assert normalize_season("june 2025", None) is None
