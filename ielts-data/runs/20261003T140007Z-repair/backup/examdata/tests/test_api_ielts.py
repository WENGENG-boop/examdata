"""IELTS 网关（/api/v1/ielts）的契约测试。

覆盖三件事：

1. `/info` 能力清单——board=ielts、书目范围、路由表齐全；
2. 失败路径的 HTTP 语义——聚合器的 `ok:false` 原样 200 透传；
   找不到 node 时 503（不冒充业务失败）；
3. 真实子进程通道（默认跳过，`EXAMDATA_TEST_LIVE=1` 时执行）——
   经 node 子进程实际调用聚合器，验证桥接可用。

默认离线：第 3 项需要 `EXAMDATA_TEST_LIVE=1` 且可访问外网。
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from examdata.api.app import app  # noqa: E402

LIVE_TESTS = os.environ.get("EXAMDATA_TEST_LIVE") == "1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_info_lists_books_and_routes(client):
    r = client.get("/api/v1/ielts/info")
    assert r.status_code == 200
    data = r.json()
    assert data["board"] == "ielts"
    assert data["books"]["range"] == "1–21"
    paths = [x["path"] for x in data["routes"]]
    assert "/api/v1/ielts/aggregate/{book}/{test}" in paths
    assert "/api/v1/ielts/zhan/reading/{book}/{test}?passage=" in paths


def test_info_states_coverage_limits_and_failure_semantics(client):
    r = client.get("/api/v1/ielts/info")
    assert r.status_code == 200
    text = json.dumps(r.json(), ensure_ascii=False)
    assert "永不抛异常" not in text
    assert "全网红唯一" not in text
    assert "剑1–20" not in text
    assert "剑1–19" in text
    assert "Test1 分册" in text
    assert "社区镜像" in text
    assert "没有顶层 ok" in text
    assert "不代表每题答案正确" in text


def test_business_failure_passthrough_is_200(client):
    # 剑99不在任何源覆盖内：聚合器自身返回 ok:false —— 网关必须 200 原样透传
    r = client.get("/api/v1/ielts/zhan/reading/99/1")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert data["board"] == "ielts"


def test_node_missing_is_503(client, monkeypatch):
    monkeypatch.setenv("EXAMDATA_NODE", "definitely-not-a-real-node-binary-xyz")
    r = client.get("/api/v1/ielts/iprog/coverage")
    assert r.status_code == 503
    assert "detail" in r.json()


@pytest.mark.skipif(not LIVE_TESTS, reason="需要 EXAMDATA_TEST_LIVE=1 且可访问外网")
def test_live_node_subprocess_channel(client):
    r = client.get("/api/v1/ielts/iprog/coverage")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tests_covered"] == "4/4"
    assert data["board"] == "ielts"
