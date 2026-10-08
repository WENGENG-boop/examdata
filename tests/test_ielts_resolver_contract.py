"""v2 规范化 API（/api/v1/ielts/v2/*）的 FastAPI 网关契约测试（S13 三入口统一）。

CLI（node ielts-cli.mjs）、Node HTTP（ielts-cli.mjs serve）、FastAPI（本网关）共享
同一 resolver/v2-api：全部本地索引解析、零网络请求。本文件经 TestClient 走真实
node 子进程通道（不重启 8000 服务），校验：

- /v2/info /v2/books /v2/test /v2/questions /v2/question /v2/coverage /v2/asset；
- 过滤参数（skill/status/alignment/passage）与失败语义（200 + ok:false）；
- gta/gtb（General Training）variant 选择、variant_mismatch 拒绝、questions 分页（offset/limit）；
- reading-enriched 非法身份零网络请求；
- 回归锚点：剑10 T1 阅读 Q34 空答案保位、剑1 T2 听力 41 题、阅读缺省整卷。

运行：
    cd examdata
    ./.venv/Scripts/python.exe -m pytest tests/test_ielts_resolver_contract.py
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from examdata.api.app import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_v2_info_contract(client):
    r = client.get("/api/v1/ielts/v2/info")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["board"] == "ielts"
    assert d["schema"] == "ielts.v2/1"
    assert d["version"] == "v2/1.0.0"
    assert d["run_id"], "带 run_id 证据"
    paths = [x["path"] for x in d["routes"]]
    assert "/api/ielts/v2/coverage?book=&test=" in paths
    assert "/api/ielts/v2/test/{book}/{test}?variant=academic|general" in paths
    assert "/api/ielts/v2/questions/{book}/{test}?skill=&variant=&part=&passage=&type=&status=&alignment=&offset=&limit=" in paths


def test_v2_books_lists_21_books(client):
    r = client.get("/api/v1/ielts/v2/books")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert len(d["books"]) == 21
    b12 = next(b for b in d["books"] if b["book"] == 12)
    assert b12["tests"]["reading/academic"] == ["5", "6", "7", "8"]


def test_v2_questions_empty_answer_no_shift(client):
    # 剑10 T1 阅读 Q34 空答案保位：status=empty，不移位、不从分母删除
    r = client.get("/api/v1/ielts/v2/questions/10/1", params={"skill": "reading", "status": "empty"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["count"] == 1
    q = d["questions"][0]
    assert q["question_id"] == "q-10-1-reading-academic-34"
    assert q["number"] == 34
    assert q["answer"]["raw"] == ""
    assert q["answer"]["status"] == "empty"


def test_v2_questions_book1_test2_41_questions(client):
    # 剑1 T2 听力 41 题保留（39 答 2 缺），不因抓不到答案删题
    r = client.get("/api/v1/ielts/v2/questions/1/2", params={"skill": "listening"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["count"] == 41
    numbers = [q["number"] for q in d["questions"]]
    assert numbers == list(range(1, 42))


def test_v2_questions_alignment_filter(client):
    r = client.get("/api/v1/ielts/v2/questions/21/1", params={"skill": "listening", "alignment": "verified"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert 0 < d["count"] < 40, "verified 是 40 题的严格子集（其余未验，不冒充）"
    for q in d["questions"]:
        assert q["audio_alignment"]["status"] == "verified"


def test_v2_question_single_and_bad_id(client):
    r = client.get("/api/v1/ielts/v2/question/q-10-1-reading-academic-34")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["question"]["answer"]["raw"] == ""

    bad = client.get("/api/v1/ielts/v2/question/bad-id")
    assert bad.status_code == 200
    assert bad.json()["ok"] is False
    assert bad.json()["code"] == "bad_question_id"


def test_v2_coverage_test_level(client):
    r = client.get("/api/v1/ielts/v2/coverage", params={"book": 20, "test": 4})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["level"] == "test"
    assert d["schema"] == "ielts.coverage/1"
    assert len(d["units"]) == 4
    assert "fully_complete" in d["completion"]


def test_v2_asset_range_and_404(client):
    r = client.get("/api/v1/ielts/v2/asset/book-pdf-20", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert r.headers["content-range"].startswith("bytes 0-99/")
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) == 100

    bad = client.get("/api/v1/ielts/v2/asset/zzz")
    assert bad.status_code == 404


def test_reading_whole_test_default_and_single_passage(client):
    # 缺省整卷：3 篇 40 题；显式 passage=2 单篇 13 题
    whole = client.get("/api/v1/ielts/reading/20/4")
    assert whole.status_code == 200
    w = whole.json()
    assert w["ok"] is True
    assert w["passage"] is None
    assert len(w["passages"]) == 3
    assert len(w["questions"]) == 40

    single = client.get("/api/v1/ielts/reading/10/1", params={"passage": 2})
    assert single.status_code == 200
    s = single.json()
    assert s["passage"] == 2
    assert len(s["questions"]) == 13
    assert s["questions"][0]["number"] == 14


def test_info_lists_reading_enriched_route(client):
    # FastAPI /info 路由清单包含 reading-enriched（三入口一致的一部分）
    r = client.get("/api/v1/ielts/info")
    assert r.status_code == 200
    d = r.json()
    paths = [x["path"] for x in d["routes"]]
    assert "/api/v1/ielts/reading-enriched/{book}/{test}?passage=" in paths


def test_v2_test_general_variant_and_mismatch(client):
    # gta/gtb（General Training）经 variant=general 选择；GT 无听力单元
    r = client.get("/api/v1/ielts/v2/test/1/gta", params={"variant": "general"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["identity"]["variant"] == "general"
    assert d["listening"] is None
    unit_ids = [u["unit_id"] for u in d["completion"]["units"]]
    assert unit_ids == ["cambridge:1:general:reading:gta", "cambridge:1:general:writing:gta"]

    mismatch = client.get("/api/v1/ielts/v2/test/1/gta", params={"variant": "academic"})
    assert mismatch.status_code == 200
    assert mismatch.json()["ok"] is False
    assert mismatch.json()["code"] == "variant_mismatch"


def test_v2_questions_pagination_and_type_filter(client):
    # offset/limit 分页（question 为单位）；非法分页返回 ok:false bad_filter
    r = client.get("/api/v1/ielts/v2/questions/10/1", params={"offset": 39, "limit": 3})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["count"] == 3
    assert d["total"] == 80
    assert [q["number"] for q in d["questions"]] == [40, 1, 2]

    bad = client.get("/api/v1/ielts/v2/questions/10/1", params={"limit": 501})
    assert bad.status_code == 200
    assert bad.json()["ok"] is False
    assert bad.json()["code"] == "bad_filter"


def test_reading_enriched_invalid_identity_no_network(client):
    # reader 源为网络源：非法身份（book=99）不发请求，直接 ok:false
    r = client.get("/api/v1/ielts/reading-enriched/99/1")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False
    assert "book" in d["error"]
    assert d["source"] == "userheyy/ielts-reader"
