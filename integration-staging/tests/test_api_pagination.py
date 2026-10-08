"""A10 - list limits and revision-bound cursors (plan 5.7).

The plan fixes a default limit of 50 and an initial maximum of 200, and requires
a cursor to bind query, sort, revision and last key. A cursor that does not
belong to the listing is a 400; a cursor whose revision is no longer published is
a 409 and never a silent restart from page one.

The cursor codec is the frozen A09 one, so these tests also prove the v2 layer
reuses exactly one cursor implementation.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from examdata_integration.api.app import create_app
from examdata_integration.api.dataset import default_dataset
from examdata_integration.api.pagination import DEFAULT_LIMIT, MAX_LIMIT, parse_limit
from examdata_integration.catalog.revision import make_cursor
from examdata_integration.api.envelope import ApiError

LIST_PATH = "/api/v2/questions"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def revision() -> str:
    return default_dataset().revision


def _page(client: TestClient, **params: object) -> dict:
    response = client.get(LIST_PATH, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_limits_constants_match_the_plan() -> None:
    assert DEFAULT_LIMIT == 50
    assert MAX_LIMIT == 200


def test_default_limit_is_fifty(client: TestClient) -> None:
    payload = _page(client)
    assert payload["meta"]["pagination"]["limit"] == DEFAULT_LIMIT
    assert len(payload["data"]["items"]) <= DEFAULT_LIMIT


def test_limit_at_the_maximum_is_accepted(client: TestClient) -> None:
    payload = _page(client, limit=MAX_LIMIT)
    assert payload["meta"]["pagination"]["limit"] == MAX_LIMIT


def test_limit_above_the_maximum_is_422(client: TestClient) -> None:
    response = client.get(LIST_PATH, params={"limit": MAX_LIMIT + 1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "limit_exceeded"


@pytest.mark.parametrize("value", ["0", "-3"])
def test_limit_below_one_is_422(client: TestClient, value: str) -> None:
    response = client.get(LIST_PATH, params={"limit": value})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_limit"


@pytest.mark.parametrize("value", ["abc", "1.5", "ten"])
def test_non_numeric_limit_is_400(client: TestClient, value: str) -> None:
    response = client.get(LIST_PATH, params={"limit": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_limit"


def test_parse_limit_defaults_and_bounds() -> None:
    assert parse_limit(None) == DEFAULT_LIMIT
    assert parse_limit("") == DEFAULT_LIMIT
    assert parse_limit("7") == 7
    with pytest.raises(ApiError) as bad:
        parse_limit("nope")
    assert bad.value.status == 400
    with pytest.raises(ApiError) as over:
        parse_limit(str(MAX_LIMIT + 1))
    assert over.value.status == 422


def test_paging_walks_the_whole_listing_once(client: TestClient) -> None:
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 4}
        if cursor:
            params["cursor"] = cursor
        payload = _page(client, **params)
        ids = [item["public_id"] for item in payload["data"]["items"]]
        seen.extend(ids)
        pages += 1
        cursor = payload["meta"]["pagination"]["next_cursor"]
        if not cursor:
            break
        assert pages < 20, "pagination did not terminate"
    total = _page(client, limit=MAX_LIMIT)["data"]["items"]
    assert seen == [item["public_id"] for item in total]
    assert len(seen) == len(set(seen)), "a page boundary repeated an item"


def test_last_page_has_no_next_cursor(client: TestClient) -> None:
    payload = _page(client, limit=MAX_LIMIT)
    assert payload["meta"]["pagination"]["next_cursor"] is None


def test_tampered_cursor_is_400(client: TestClient) -> None:
    cursor = _page(client, limit=3)["meta"]["pagination"]["next_cursor"]
    assert cursor
    tampered = cursor[:-4] + "beef"
    response = client.get(LIST_PATH, params={"limit": 3, "cursor": tampered})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_malformed_cursor_is_400(client: TestClient) -> None:
    response = client.get(LIST_PATH, params={"cursor": "not-a-cursor"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_cursor_from_an_unpublished_revision_is_409(client: TestClient) -> None:
    stale = make_cursor(dataset_revision="rev_not_published_anywhere",
                        query={}, sort="public_id", last_key="q_x", limit=3)
    response = client.get(LIST_PATH, params={"limit": 3, "cursor": stale})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "stale_cursor"
    assert error["retryable"] is True
    assert "restart" in error["details"]


def test_cursor_for_a_different_query_is_400(client: TestClient, revision: str) -> None:
    cursor = make_cursor(dataset_revision=revision, query={"system": "cie"},
                         sort="public_id", last_key="q_x", limit=3)
    response = client.get(LIST_PATH, params={"limit": 3, "system": "ielts",
                                             "cursor": cursor})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "cursor_query_mismatch"


def test_cursor_for_a_different_limit_is_400(client: TestClient, revision: str) -> None:
    cursor = make_cursor(dataset_revision=revision, query={}, sort="public_id",
                         last_key="q_x", limit=9)
    response = client.get(LIST_PATH, params={"limit": 3, "cursor": cursor})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "cursor_limit_mismatch"


def test_cursor_whose_last_key_vanished_is_409(client: TestClient,
                                               revision: str) -> None:
    cursor = make_cursor(dataset_revision=revision, query={}, sort="public_id",
                         last_key="q_absent_from_this_listing", limit=3)
    response = client.get(LIST_PATH, params={"limit": 3, "cursor": cursor})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "cursor_key_conflict"
    assert error["retryable"] is True


def test_cursor_for_a_different_sort_is_400(client: TestClient, revision: str) -> None:
    cursor = make_cursor(dataset_revision=revision, query={}, sort="number_path",
                         last_key="q_x", limit=3)
    response = client.get(LIST_PATH, params={"limit": 3, "cursor": cursor})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "cursor_sort_mismatch"


def test_cursor_survives_a_query_it_was_issued_for(client: TestClient) -> None:
    first = _page(client, limit=3, system="cie")
    cursor = first["meta"]["pagination"]["next_cursor"]
    assert cursor, "the CIE synthetic fixture must have more than three questions"
    second = _page(client, limit=3, system="cie", cursor=cursor)
    ids = {item["public_id"] for item in first["data"]["items"]}
    assert not ids & {item["public_id"] for item in second["data"]["items"]}
    assert all(item["system"] == "cie" for item in second["data"]["items"])


def test_a_cursor_is_not_reusable_across_listings(client: TestClient) -> None:
    cursor = _page(client, limit=3)["meta"]["pagination"]["next_cursor"]
    response = client.get("/api/v2/courses", params={"limit": 3, "cursor": cursor})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cursor_key_conflict"
