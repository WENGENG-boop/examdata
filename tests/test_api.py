"""API 端到端测试：用 TestClient 打真实数据库。

覆盖需求里明确要求的三类读取能力：试卷检索、题目检索、单题完整内容，
以及后台监控视图。这些断言直接对着真实解析结果，一旦解析回归就会失败。
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


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["papers"] > 0


def test_search_papers_by_subject(client):
    r = client.get("/papers", params={"subject": "0580", "limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 8
    assert all(p["subject_code"] == "0580" for p in body["items"])
    first = body["items"][0]
    for key in ("paper_id", "board", "year", "paper_code", "marks_total"):
        assert key in first


def test_search_papers_unknown_board_is_empty(client):
    r = client.get("/papers", params={"board": "no-such-board"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_search_questions_filters(client):
    total = client.get("/questions").json()["total"]
    leaves = client.get("/questions", params={"leaves_only": True}).json()["total"]
    roots = client.get("/questions", params={"roots_only": True}).json()["total"]
    assert total > 0
    assert 0 < leaves <= total
    assert 0 < roots <= total

    with_asset = client.get("/questions", params={"has_asset": True}).json()["total"]
    assert 0 < with_asset < total


def test_question_detail_keeps_assets_and_mark_scheme(client):
    """拆分后不丢内容：单题必须能拿到图形资产与评分条目。"""
    listing = client.get(
        "/questions", params={"has_asset": True, "has_answer": True, "limit": 1}
    ).json()["items"]
    assert listing, "至少应有一道既带图又有官方答案的题"
    qid = listing[0]["question_id"]

    r = client.get(f"/questions/{qid}")
    assert r.status_code == 200
    bundle = r.json()
    assert bundle["question"]["id"] == qid
    assert bundle["assets"], "带图题必须返回资产列表"
    assert bundle["mark_scheme_entries"], "必须有评分条目"
    asset = bundle["assets"][0]
    assert asset["storage_key"] and asset["width"] > 0


def test_question_detail_404(client):
    assert client.get("/questions/99999999").status_code == 404


def test_asset_bytes_are_served(client):
    listing = client.get("/questions", params={"has_asset": True, "limit": 1}).json()["items"]
    qid = listing[0]["question_id"]
    asset_id = client.get(f"/questions/{qid}").json()["assets"][0]["asset_id"]
    r = client.get(f"/assets/{asset_id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert len(r.content) > 100


def test_paper_tree(client):
    paper_id = client.get("/papers", params={"subject": "0580", "limit": 1}).json()["items"][0][
        "paper_id"
    ]
    r = client.get(f"/papers/{paper_id}/tree")
    assert r.status_code == 200
    tree = r.json()
    assert tree["roots"]
    root = tree["roots"][0]
    assert root["number_path"]
    assert isinstance(root["children"], list)


def test_sample_requires_a_target(client):
    assert client.post("/sample", params={"subject": "0580"}).status_code == 422


def test_sample_by_count_is_reproducible(client):
    params = {"subject": "0580", "count": 5, "seed": 1234}
    a = client.post("/sample", params=params).json()
    b = client.post("/sample", params=params).json()
    assert a["question_count"] == 5
    assert [q["question_id"] for q in a["questions"]] == [
        q["question_id"] for q in b["questions"]
    ]


def test_sample_by_marks_target(client):
    body = client.post("/sample", params={"subject": "0580", "marks_target": 20, "seed": 7}).json()
    assert body["marks_total"] >= 20
    assert body["requested_marks"] == 20


def test_taxonomy_tree(client):
    r = client.get("/taxonomy", params={"board": "cambridge"})
    assert r.status_code == 200
    body = r.json()
    assert body["topic_count"] > 0
    root = body["roots"][0]
    for key in ("code", "name", "node_type", "question_count", "children"):
        assert key in root
    assert root["children"], "topic 下应有 subtopic"


def test_similar_questions_are_symmetric(client):
    """相似度按无序对存储，从两端查必须都能查到对方。"""
    listing = client.get("/questions", params={"limit": 200}).json()["items"]
    found = None
    for q in listing:
        items = client.get(f"/questions/{q['question_id']}/similar").json()["items"]
        if items:
            found = (q["question_id"], items)
            break
    assert found, "至少要有一对相似题"
    qid, items = found
    other = items[0]["question_id"]
    back = client.get(f"/questions/{other}/similar").json()["items"]
    assert qid in [i["question_id"] for i in back]


def test_similar_questions_404(client):
    assert client.get("/questions/99999999/similar").status_code == 404


def test_question_detail_includes_similar_and_difficulty(client):
    listing = client.get("/questions", params={"limit": 200}).json()["items"]
    qid = next(
        q["question_id"]
        for q in listing
        if client.get(f"/questions/{q['question_id']}/similar").json()["count"] > 0
    )
    bundle = client.get(f"/questions/{qid}").json()
    assert bundle["similar_questions"]
    assert bundle["difficulty"], "智能层应已给出难度估计"
    assert bundle["difficulty"][0]["source"] == "estimated"


def test_monitor(client):
    r = client.get("/monitor")
    assert r.status_code == 200
    body = r.json()
    assert body["sync"], "至少应有一个考试局的同步状态"
    board = body["sync"][0]
    for key in ("board", "documents", "papers", "questions", "failed", "open_errors"):
        assert key in board
    assert isinstance(body["review_queue"], list)


def test_provenance_coverage_is_complete(client):
    r = client.get("/provenance/coverage")
    assert r.status_code == 200
    body = r.json()
    assert body["complete"] is True, "所有派生数据都必须能追到官方来源"
    assert body["coverage"]["question"]["ratio"] == 1.0


def test_question_provenance_reaches_official_url(client):
    qid = client.get("/questions", params={"limit": 1}).json()["items"][0]["question_id"]
    r = client.get(f"/questions/{qid}/provenance")
    assert r.status_code == 200
    sources = r.json()["sources"]
    assert sources
    assert sources[0]["source_url"].startswith("http")
    assert sources[0]["attrs"]["artifact_sha256"]


def test_question_provenance_404(client):
    assert client.get("/questions/99999999/provenance").status_code == 404


def test_asset_provenance_links_to_question(client):
    assets = client.get("/questions", params={"has_asset": True, "limit": 1}).json()["items"]
    if not assets:
        pytest.skip("没有带图形的题目")
    bundle = client.get(f"/questions/{assets[0]['question_id']}").json()
    aid = bundle["assets"][0]["asset_id"]
    r = client.get(f"/assets/{aid}/provenance")
    assert r.status_code == 200
    assert r.json()["sources"]


def test_review_endpoint_lists_queue(client):
    r = client.get("/review", params={"status": "open"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "open"
    assert isinstance(body["items"], list)


def test_overrides_endpoint_shape(client):
    r = client.get("/overrides")
    assert r.status_code == 200
    body = r.json()
    assert "count" in body and isinstance(body["items"], list)


def test_classifications_endpoint_exposes_evidence(client):
    r = client.get("/classifications")
    assert r.status_code == 200
    body = r.json()
    if body["count"] == 0:
        pytest.skip("尚未跑 classify-content")
    item = body["items"][0]
    assert item["doc_type"]
    assert item["evidence"], "判定必须带证据"
    # 历史上 sync 只写页面级判定（label_grammar+slug_crosscheck），
    # classify-content 会追加内容级判定。两种来源都要能读出。
    assert item["method"] in (
        "label+content",
        "conflict",
        "content",
        "label",
        "label_grammar+slug_crosscheck",
    )


def test_question_explanation_separates_official_from_generated(client):
    """生成内容与官方内容必须在同一个响应里就能区分开。"""
    listing = client.get("/questions", params={"has_answer": True, "limit": 50}).json()["items"]
    if not listing:
        pytest.skip("没有带官方答案的题目")
    qid = listing[0]["question_id"]
    r = client.get(f"/questions/{qid}/explanation")
    assert r.status_code == 200
    body = r.json()
    assert body["question_id"] == qid
    for a in body["official"]:
        assert a["is_official"] is True
    for g in body["generated"]:
        assert g["is_official"] is False, "生成内容绝不能标为官方"
        assert g["provider"] == "rule-based"
        assert g["review_status"] in ("pending", "approved", "rejected")


def test_question_explanation_404(client):
    assert client.get("/questions/99999999/explanation").status_code == 404


def test_explanation_review_queue(client):
    r = client.get("/explanations/review-queue", params={"status": "pending"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["total"] >= body["count"] >= 0


def test_classifications_filter_by_method(client):
    r = client.get("/classifications", params={"method": "conflict"})
    assert r.status_code == 200
    assert all(i["method"] == "conflict" for i in r.json()["items"])


def test_classifications_include_content_method_after_classify(client):
    """跑过 classify-content 之后，必须能读到内容级判定。"""
    r = client.get("/classifications", params={"method": "label+content"})
    assert r.status_code == 200
    body = r.json()
    if body["count"] == 0:
        pytest.skip("尚未跑 classify-content")
    item = body["items"][0]
    assert item["evidence"]["content"]["scores"], "内容级判定必须留下打分证据"
    assert item["evidence"]["label_type"]

