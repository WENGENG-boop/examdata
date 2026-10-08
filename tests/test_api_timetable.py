"""CIE Zone 5 时间表接口（/api/v1/timetable）的契约测试。

只读 `examdata.timetable.data.zone5` 下的离线快照，不联网、不查库。
应用在测试内就地组装：`FastAPI()` + `include_router(timetable.router)`，
避免依赖 `examdata.api.app` 的启动副作用。
"""

from __future__ import annotations

import json
from datetime import date

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from examdata.timetable import router as timetable_router  # noqa: E402
from examdata.timetable import season_key as _season_key  # noqa: E402
from examdata.timetable.build import DATA_DIR  # noqa: E402

AVAILABLE_SEASONS = 25
UNOBTAINABLE_SEASONS = 2
KNOWN_AVAILABLE = ["2013-11", "2017-06", "2026-06", "2026-11"]
KNOWN_UNOBTAINABLE = ["2019-06", "2020-11"]


@pytest.fixture(scope="module")
def client():
    if not (DATA_DIR / "index.json").is_file():
        pytest.skip("时间表快照缺失，先运行 python -m examdata.timetable.build")
    app = FastAPI()
    app.include_router(timetable_router)
    with TestClient(app) as c:
        yield c


def test_seasons_lists_all_known_and_missing(client):
    r = client.get("/api/v1/timetable/seasons")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["schema_version"] == "1"
    assert data["zone"] == 5
    assert data["board"] == "cie"

    seasons = data["seasons"]
    assert len(seasons) == AVAILABLE_SEASONS
    for item in seasons:
        assert item["year"] >= 2013
        assert item["season"] in {"Jun", "Nov"}
        assert item["key"] == _season_key(item["year"], item["season"])
        assert item["events_count"] > 0
        if item["year"] <= 2014:
            # legacy 版式源 PDF 不含 Test date windows 节
            assert item["date_windows_count"] == 0
        else:
            assert item["date_windows_count"] > 0

    keys = {item["key"] for item in seasons}
    assert set(KNOWN_AVAILABLE) <= keys
    assert len(keys) == AVAILABLE_SEASONS

    unobtainable = data["unobtainable"]
    assert len(unobtainable) == UNOBTAINABLE_SEASONS
    missing_keys = {item["key"] for item in unobtainable}
    assert set(KNOWN_UNOBTAINABLE) <= missing_keys
    for item in unobtainable:
        assert item["reason"]


def test_known_season_events_are_well_formed(client):
    r = client.get("/api/v1/timetable", params={"year": 2026, "season": "Jun"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["key"] == "2026-06"
    assert payload["season"] == "Jun"
    assert payload["count"] == len(payload["events"])
    assert payload["total"] >= payload["count"] > 0
    assert payload["source"]["sha256"]
    assert payload["source"]["pages"] > 0

    for event in payload["events"]:
        assert event["date"] == date.fromisoformat(event["date"]).isoformat()
        assert date(2026, 4, 1) <= date.fromisoformat(event["date"]) <= date(2026, 7, 15)
        assert event["weekday"]
        assert event["session"] in {"AM", "PM", "EV"}
        assert event["level"] in {"IG", "OL", "AS", "AL", "PR"}
        assert event["paper_code"]
        assert 1 <= event["duration_minutes"] <= 400
        assert event["raw"]


def test_legacy_season_serves_events(client):
    r = client.get("/api/v1/timetable", params={"year": 2013, "season": "Nov"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["key"] == "2013-11"
    assert payload["total"] > 0
    assert payload["count"] == len(payload["events"]) > 0
    for event in payload["events"]:
        assert event["date"].startswith("2013-")
        assert event["subject_code"]

    r = client.get(
        "/api/v1/timetable", params={"year": 2013, "season": "Nov", "subject": "9709"}
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["total"] == 7
    first = payload["events"][0]
    assert first["date"] == "2013-10-15"
    assert first["weekday"] == "Tuesday"
    assert first["session"] == "AM"
    assert first["paper_code"] == "13"
    assert first["level"] == "AS"


def test_filters_narrow_results(client):
    base = client.get(
        "/api/v1/timetable", params={"year": 2026, "season": "Jun", "limit": 2000}
    )
    assert base.status_code == 200, base.text
    events = base.json()["events"]
    assert events

    paper = events[0]
    by_subject = client.get(
        "/api/v1/timetable",
        params={"year": 2026, "season": "Jun", "subject": paper["subject_code"], "limit": 2000},
    ).json()
    assert 0 < by_subject["total"] < base.json()["total"]
    assert all(
        str(e["subject_code"]).startswith(paper["subject_code"]) for e in by_subject["events"]
    )

    by_combined = client.get(
        "/api/v1/timetable",
        params={
            "year": 2026,
            "season": "Jun",
            "subject": paper["subject_code"],
            "date": paper["date"],
            "session": paper["session"],
            "level": paper["level"],
            "limit": 2000,
        },
    ).json()
    assert by_combined["count"] == len(by_combined["events"])
    for event in by_combined["events"]:
        assert event["subject_code"] == paper["subject_code"]
        assert event["date"] == paper["date"]
        assert event["session"] == paper["session"]
        assert event["level"] == paper["level"]


def test_pagination_within_bounds(client):
    first = client.get(
        "/api/v1/timetable",
        params={"year": 2026, "season": "Jun", "limit": 5, "offset": 0},
    ).json()
    assert first["count"] == 5 and first["offset"] == 0
    second = client.get(
        "/api/v1/timetable",
        params={"year": 2026, "season": "Jun", "limit": 5, "offset": 5},
    ).json()
    assert second["count"] == 5 and second["offset"] == 5
    assert first["events"][0] != second["events"][0]


def test_windows_shape(client):
    r = client.get("/api/v1/timetable/windows", params={"year": 2026, "season": "Nov"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["key"] == "2026-11"
    assert payload["count"] == len(payload["date_windows"]) > 0
    for window in payload["date_windows"]:
        assert window["syllabus_code"]
        assert window["window_raw"]
        for field in ("window_start", "window_end"):
            value = window[field]
            if value is not None:
                assert date.fromisoformat(value)


def test_unobtainable_season_returns_404_with_evidence(client):
    for key in KNOWN_UNOBTAINABLE:
        year, month = key.split("-")
        r = client.get(
            "/api/v1/timetable", params={"year": int(year), "season": "Jun" if month == "06" else "Nov"}
        )
        assert r.status_code == 404, f"{key}: {r.text}"
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["reason"]


def test_bad_season_token_returns_422(client):
    r = client.get("/api/v1/timetable", params={"year": 2026, "season": "Dec"})
    assert r.status_code == 422

    r = client.get("/api/v1/timetable", params={"year": 2001, "season": "Jun"})
    assert r.status_code == 422


def test_bad_filter_values_return_422(client):
    r = client.get(
        "/api/v1/timetable", params={"year": 2026, "season": "Jun", "session": "XX"}
    )
    assert r.status_code == 422
    r = client.get(
        "/api/v1/timetable", params={"year": 2026, "season": "Jun", "date": "2026/06/01"}
    )
    assert r.status_code == 422
    r = client.get(
        "/api/v1/timetable", params={"year": 2026, "season": "Jun", "limit": 100000}
    )
    assert r.status_code == 422


def test_events_are_json_clean(client):
    r = client.get("/api/v1/timetable/seasons")
    assert r.status_code == 200
    # 快照里不应有 NaN/Infinity 等非标准 JSON 常量
    json.loads(json.dumps(r.json(), allow_nan=False))
