"""考试发放资料接口（/api/v1/materials）的契约测试。

应用在测试内就地组装：`FastAPI()` + `include_router(materials.router)`，
上游用 `FakeFetcher`（假 PDF + 假镜像目录响应），不联网、不查库。
覆盖：清单过滤与 board 别名、单条详情、静态取回的二进制/ base64 两种
出口、sha256 漂移语义（不报错、如实告知）、版本选择、动态条目的 422
指引、CIE 镜像清单/下载/多命中/404/422/robots 403。
"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest

pytest.importorskip("fastapi")
import pymupdf  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from examdata.core.fetch import FetchResult, RobotsDisallowed  # noqa: E402
from examdata.materials import router as materials_router  # noqa: E402
from examdata.materials.fetch import fetch_material  # noqa: E402
from examdata.materials.router import get_fetcher  # noqa: E402


def pdf_bytes() -> bytes:
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Materials fixture")
        return pdf.tobytes()


# pymupdf 每次 tobytes() 都会写入新的文档 ID，缓存一份让多次取回字节一致，
# 才能比较响应体与 base64 载荷（与 tests/test_paperqa_api.py 同一做法）。
PDF = pdf_bytes()
PDF_SHA = hashlib.sha256(PDF).hexdigest()


class FakeFetcher:
    """材料取回用的假抓取器：GET 返回 PDF 常量，POST 返回镜像目录 JSON。"""

    def __init__(self, rows=None, status=200):
        self.rows = rows if rows is not None else [{"file": "0500_s24_in_11.pdf"}]
        self.status = status
        self.robots_blocked = False
        self.calls = []

    def assert_allowed(self, url):
        if self.robots_blocked:
            raise RobotsDisallowed(f"robots.txt 禁止抓取 {url}")

    def post_form(self, url, data, **kwargs):
        self.calls.append(("POST", url, data))
        if self.robots_blocked:
            return FetchResult(url=url, status=0, error="robots", robots_blocked=True)
        payload = {"total": len(self.rows), "rows": self.rows}
        return FetchResult(url, 200, text=json.dumps(payload))

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        return FetchResult(url, self.status, content=PDF)


@pytest.fixture()
def fake():
    return FakeFetcher()


@pytest.fixture()
def client(fake):
    app = FastAPI()
    app.include_router(materials_router)
    app.dependency_overrides[get_fetcher] = lambda: fake
    with TestClient(app) as c:
        yield c


def test_list_materials_returns_all_items(client):
    r = client.get("/api/v1/materials")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["schema_version"] == "1"
    assert payload["count"] == len(payload["items"]) >= 7
    assert payload["dynamic_endpoints"]["cie_in_paper"] == "/api/v1/materials/cie/in-paper"
    for item in payload["items"]:
        assert item["id"]
        assert item["board"] in {"cie", "edexcel"}
        assert "evidence" not in item  # 清单不含 evidence 正文


def test_list_materials_board_alias_normalizes(client):
    r = client.get("/api/v1/materials", params={"board": "cambridge"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["board"] == "cie"
    assert payload["items"] and all(item["board"] == "cie" for item in payload["items"])

    r = client.get("/api/v1/materials", params={"board": "nonsense"})
    assert r.status_code == 422


def test_list_materials_filters_by_subject_and_kind(client):
    r = client.get("/api/v1/materials", params={"subject": "9709"})
    ids = {item["id"] for item in r.json()["items"]}
    assert "cie-mf19-formulae-and-statistical-tables" in ids

    r = client.get("/api/v1/materials", params={"subject": "ial18-chemistry"})
    assert [item["id"] for item in r.json()["items"]] == ["edexcel-ial-chemistry-data-booklet"]

    r = client.get("/api/v1/materials", params={"kind": "insert"})
    assert [item["id"] for item in r.json()["items"]] == ["cie-inserts"]

    r = client.get("/api/v1/materials", params={"candidate_facing": "false"})
    assert {item["id"] for item in r.json()["items"]} == {
        "cie-confidential-instructions",
        "cie-additional-materials-list",
    }


def test_material_detail_keeps_evidence_and_content_endpoint(client):
    r = client.get("/api/v1/materials/cie-mf19-formulae-and-statistical-tables")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["schema_version"] == "1"
    assert (
        payload["content_endpoint"]
        == "/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content"
    )
    assert payload["evidence"] and payload["versions"]
    assert payload["versions"][0]["sha256"]

    r = client.get("/api/v1/materials/does-not-exist")
    assert r.status_code == 404


def test_dynamic_item_content_points_to_dynamic_endpoint(client):
    r = client.get("/api/v1/materials/cie-inserts/content")
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["dynamic_endpoint"] == "/api/v1/materials/cie/in-paper"


def test_static_content_binary_returns_pdf_with_headers(client):
    r = client.get("/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == PDF
    assert r.headers["x-material-sha256"] == PDF_SHA
    assert r.headers["x-material-id"] == "cie-mf19-formulae-and-statistical-tables"
    assert r.headers["x-material-sha256-match"] in {"true", "false"}
    assert "attachment" in r.headers["content-disposition"]


def test_static_content_json_round_trips_and_reports_drift(client):
    r = client.get(
        "/api/v1/materials/edexcel-ial-maths-formula-book/content",
        params={"format": "json"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    raw = base64.b64decode(payload["data_base64"])
    assert raw == PDF
    assert payload["sha256"] == PDF_SHA
    # 目录快照的 sha256 与假上游不同：match=false 但绝不报错（漂移是合法事件）
    assert payload["sha256_match"] is False
    assert payload["version"]["label"]


def test_static_content_version_selection_and_errors(client):
    r = client.get(
        "/api/v1/materials/edexcel-ial-maths-formula-book/content",
        params={"version": "0", "format": "json"},
    )
    assert r.status_code == 200, r.text

    r = client.get(
        "/api/v1/materials/edexcel-ial-maths-formula-book/content", params={"version": "1"}
    )
    assert r.status_code == 422

    r = client.get(
        "/api/v1/materials/edexcel-ial-maths-formula-book/content",
        params={"version": "Issue 99"},
    )
    assert r.status_code == 422


def test_fetch_material_reports_snapshot_match_unit():
    version = {
        "label": "fake",
        "url": "https://www.cambridgeinternational.org/Images/417318-list-of-formulae-and-statistical-tables.pdf",
        "sha256": PDF_SHA,
    }
    fetched = fetch_material(FakeFetcher(), version)
    assert fetched.sha256 == PDF_SHA
    assert fetched.sha256_match is True


def test_cie_in_paper_manifest_lists_documents(client):
    r = client.get(
        "/api/v1/materials/cie/in-paper",
        params={"subject": "0500", "year": 2024, "season": "June"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["counts"] == {"documents": 1, "files": 0, "bytes": 0}
    doc = payload["documents"][0]
    assert doc["name"] == "0500_s24_in_11.pdf"
    assert doc["role"] == "in" and doc["paper"] == "11"
    assert doc["url"] == "https://cie.fraft.cn/obj/Common/Fetch/redir/0500_s24_in_11.pdf"
    assert payload["files"] == []
    assert payload["source"]["origin"] == "https://cie.fraft.cn"


def test_cie_in_paper_download_returns_bytes(client):
    r = client.get(
        "/api/v1/materials/cie/in-paper",
        params={"subject": "0500", "year": 2024, "season": "Jun", "download": "true"},
    )
    assert r.status_code == 200, r.text
    assert r.content == PDF
    assert r.headers["x-material-sha256"] == PDF_SHA
    assert "0500_s24_in_11.pdf" in r.headers["content-disposition"]


def test_cie_in_paper_multiple_hits_require_paper(client, fake):
    fake.rows = [{"file": "0620_s24_ci_51.pdf"}, {"file": "0620_s24_ci_52.pdf"}]
    params = {
        "subject": "0620",
        "year": 2024,
        "season": "Jun",
        "role": "ci",
        "download": "true",
    }
    r = client.get("/api/v1/materials/cie/in-paper", params=params)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["papers"] == ["51", "52"]

    r = client.get("/api/v1/materials/cie/in-paper", params={**params, "paper": "51"})
    assert r.status_code == 200, r.text


def test_cie_in_paper_no_match_returns_404(client, fake):
    fake.rows = []
    r = client.get(
        "/api/v1/materials/cie/in-paper",
        params={"subject": "0500", "year": 2024, "season": "Jun"},
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"subject": "abc", "year": 2024, "season": "Jun"},
        {"subject": "0500", "year": 1900, "season": "Jun"},
        {"subject": "0500", "year": 2024, "season": "Dec"},
        {"subject": "0500", "year": 2024, "season": "Jun", "role": "zz"},
        {"subject": "0500", "year": 2024, "season": "Jun", "paper": "x"},
    ],
)
def test_cie_in_paper_bad_params_return_422(client, params):
    r = client.get("/api/v1/materials/cie/in-paper", params=params)
    assert r.status_code == 422, r.text


def test_cie_in_paper_robots_blocked_returns_403(client, fake):
    fake.robots_blocked = True
    r = client.get(
        "/api/v1/materials/cie/in-paper",
        params={"subject": "0500", "year": 2024, "season": "Jun"},
    )
    assert r.status_code == 403


def test_static_content_robots_blocked_returns_403(client, fake):
    fake.robots_blocked = True
    r = client.get("/api/v1/materials/cie-mf19-formulae-and-statistical-tables/content")
    assert r.status_code == 403
