"""Edexcel 时间表接口（/api/v1/timetable?board=edexcel）的契约测试。

只读 `examdata.timetable.data.edexcel` 下的离线快照，不联网、不查库。
应用在测试内就地组装：`FastAPI()` + `include_router(timetable.router)`。
"""

from __future__ import annotations

import json
from datetime import date

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from examdata.timetable import router as timetable_router  # noqa: E402
from examdata.timetable.build_edexcel import DATA_DIR  # noqa: E402

AVAILABLE_SEASONS = 106
CANCELLED_SEASONS = 6
UNOBTAINABLE_SEASONS = 15


@pytest.fixture(scope="module")
def client():
    if not (DATA_DIR / "index.json").is_file():
        pytest.skip("Edexcel 时间表快照缺失，先运行 python -m examdata.timetable.build_edexcel")
    app = FastAPI()
    app.include_router(timetable_router)
    with TestClient(app) as c:
        yield c


def test_seasons_lists_all_families(client):
    r = client.get("/api/v1/timetable/seasons", params={"board": "edexcel"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["schema_version"] == "1"
    assert data["board"] == "edexcel"
    assert data["counts"] == {
        "seasons": AVAILABLE_SEASONS,
        "cancelled": CANCELLED_SEASONS,
        "unobtainable": UNOBTAINABLE_SEASONS,
    }
    families = {item["family"] for item in data["seasons"]}
    assert families == {"gcse", "intgcse", "ial", "gce"}
    for item in data["seasons"]:
        assert item["available"] is True
        assert item["events_count"] > 0
        assert item["season"] in {"Jan", "Jun", "Oct", "Nov"}
        assert item["variant"] in {"standard", "R"}
    keys = {item["key"] for item in data["seasons"]}
    assert len(keys) == AVAILABLE_SEASONS
    assert any(key.endswith("|R") for key in keys)
    for item in data["cancelled"]:
        assert item["reason"]
    for item in data["unobtainable"]:
        assert item["reason"]
        assert item["search_exhausted"] is True


def test_family_filter(client):
    r = client.get("/api/v1/timetable/seasons", params={"board": "edexcel", "family": "ial"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["family"] == "ial"
    assert data["counts"]["seasons"] == 34
    assert data["counts"]["cancelled"] == 1
    assert all(item["family"] == "ial" for item in data["seasons"])
    assert all(item["family"] == "ial" for item in data["cancelled"])

    r = client.get("/api/v1/timetable/seasons", params={"board": "edexcel", "family": "gce"})
    data = r.json()
    assert data["counts"]["seasons"] == 13
    assert data["counts"]["unobtainable"] == 0


def test_known_season_events_are_well_formed(client):
    r = client.get(
        "/api/v1/timetable",
        params={"board": "edexcel", "family": "ial", "year": 2026, "season": "June"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["key"] == "ial|2026|06"
    assert payload["family"] == "ial"
    assert payload["variant"] == "standard"
    assert payload["season"] == "Jun"
    assert payload["count"] == len(payload["events"])
    assert payload["total"] >= payload["count"] > 0
    assert payload["source"]["sha256"]
    assert payload["source"]["pages"] > 0

    for event in payload["events"]:
        assert event["date"] == date.fromisoformat(event["date"]).isoformat()
        assert event["session"] in {"AM", "PM"}
        assert event["subject_code"]
        assert event["raw"]
        if event["duration_minutes"] is not None:
            assert event["duration_minutes"] >= 1


def test_r_paper_season(client):
    r = client.get(
        "/api/v1/timetable",
        params={
            "board": "edexcel",
            "family": "intgcse",
            "year": 2018,
            "season": "June",
            "r_paper": "true",
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["key"] == "intgcse|2018|06|R"
    assert payload["variant"] == "R"
    assert payload["total"] > 0


def test_filters_narrow_results(client):
    params = {"board": "edexcel", "family": "ial", "year": 2026, "season": "June", "limit": 2000}
    base = client.get("/api/v1/timetable", params=params)
    assert base.status_code == 200, base.text
    events = base.json()["events"]
    assert events

    paper = events[0]
    by_subject = client.get(
        "/api/v1/timetable", params={**params, "subject": paper["subject_code"]}
    ).json()
    assert 0 < by_subject["total"] <= base.json()["total"]
    assert all(
        str(event["subject_code"]).startswith(paper["subject_code"])
        for event in by_subject["events"]
    )

    by_combined = client.get(
        "/api/v1/timetable",
        params={
            **params,
            "subject": paper["subject_code"],
            "date": paper["date"],
            "session": paper["session"],
        },
    ).json()
    assert by_combined["count"] == len(by_combined["events"])
    for event in by_combined["events"]:
        assert event["subject_code"] == paper["subject_code"]
        assert event["date"] == paper["date"]
        assert event["session"] == paper["session"]


def test_windows_shape(client):
    r = client.get(
        "/api/v1/timetable/windows",
        params={"board": "edexcel", "family": "gce", "year": 2017, "season": "June"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["key"] == "gce|2017|06"
    assert payload["count"] == len(payload["date_windows"]) == 3
    for window in payload["date_windows"]:
        assert window["subject_code"]
        assert window["window_raw"]
        for field in ("window_start", "window_end"):
            value = window[field]
            if value is not None:
                assert date.fromisoformat(value)


def test_cancelled_season_returns_404(client):
    r = client.get(
        "/api/v1/timetable",
        params={"board": "edexcel", "family": "gcse", "year": 2020, "season": "June"},
    )
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["cancelled"] is True
    assert "COVID" in detail["reason"]


def test_unobtainable_season_returns_404_with_evidence(client):
    r = client.get(
        "/api/v1/timetable",
        params={"board": "edexcel", "family": "intgcse", "year": 2019, "season": "June"},
    )
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert detail["reason"]

    r = client.get(
        "/api/v1/timetable",
        params={
            "board": "edexcel",
            "family": "intgcse",
            "year": 2023,
            "season": "June",
            "r_paper": "true",
        },
    )
    assert r.status_code == 404, r.text


def test_bad_params_return_422(client):
    # family 必填
    r = client.get(
        "/api/v1/timetable", params={"board": "edexcel", "year": 2026, "season": "June"}
    )
    assert r.status_code == 422
    # 未知 family
    r = client.get(
        "/api/v1/timetable",
        params={"board": "edexcel", "family": "sat", "year": 2026, "season": "June"},
    )
    assert r.status_code == 422
    # 未知考季写法
    r = client.get(
        "/api/v1/timetable",
        params={"board": "edexcel", "family": "ial", "year": 2026, "season": "Dec"},
    )
    assert r.status_code == 422
    # level 仅 CIE
    r = client.get(
        "/api/v1/timetable",
        params={
            "board": "edexcel",
            "family": "ial",
            "year": 2026,
            "season": "June",
            "level": "AS",
        },
    )
    assert r.status_code == 422
    # CIE 混用 Edexcel 参数
    r = client.get("/api/v1/timetable", params={"family": "ial", "year": 2026, "season": "Jun"})
    assert r.status_code == 422
    r = client.get("/api/v1/timetable", params={"r_paper": "true", "year": 2026, "season": "Jun"})
    assert r.status_code == 422
    # 未知 board
    r = client.get("/api/v1/timetable/seasons", params={"board": "aqa"})
    assert r.status_code == 422


def test_board_aliases(client):
    r = client.get("/api/v1/timetable/seasons", params={"board": "edx", "family": "gce"})
    assert r.status_code == 200, r.text
    assert r.json()["board"] == "edexcel"


def test_events_are_json_clean(client):
    r = client.get("/api/v1/timetable/seasons", params={"board": "edexcel"})
    assert r.status_code == 200
    json.loads(json.dumps(r.json(), allow_nan=False))
