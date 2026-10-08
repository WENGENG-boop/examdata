#!/usr/bin/env python3
"""A10 isolated v2 API probe: exercise the staged app offline.

Offline and in-process only. The app is built from the staged package and the
frozen synthetic fixtures; requests go through Starlette's TestClient, which
never opens a socket. Prints a stable transcript to stdout; the closing-checks
tool captures it to `docs/integration/execution/evidence/A10/api_stdout.txt`.
Exits non-zero if any scenario fails.

Nothing original is read, no database or network is touched, no upstream URL is
requested, and no identity, quality state, answer, region or revision is ever
fabricated or promoted past its evidence.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"

sys.path.insert(0, str(SRC))
# R04: product code resolves its deployment root explicitly (never by directory name).
os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", str(STAGING))

from fastapi.testclient import TestClient  # noqa: E402

from examdata_integration.api import dataset, links, openapi, pagination  # noqa: E402
from examdata_integration.api.app import create_app  # noqa: E402
from examdata_integration.api.envelope import (  # noqa: E402
    ERROR_MAP,
    FRAMEWORK_STATUSES,
)

failures: list[str] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}{(' :: ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def body(response) -> dict:
    try:
        return response.json()
    except Exception:  # noqa: BLE001 - a non-JSON body is itself a finding
        return {}


def main() -> int:
    print("=== A10 isolated v2 API probe ===")
    app = create_app()
    client = TestClient(app)
    ds = dataset.default_dataset()

    # ------------------------------------------------------- route inventory --
    print("\n-- route inventory --")
    runtime = openapi.runtime_pairs(app)
    specs = openapi.spec_pairs(app)
    advertised = links.advertised_pairs()
    expect("routes.runtime_equals_spec", runtime == specs, f"{len(runtime)} vs {len(specs)}")
    expect("routes.spec_equals_advertised", specs == advertised,
           f"{len(specs)} vs {len(advertised)}")
    expect("routes.implemented_count", len(links.IMPLEMENTED_SPECS) == 34,
           str(len(links.IMPLEMENTED_SPECS)))
    expect("routes.deferred_count", len(links.DEFERRED_SPECS) == 0,
           str(len(links.DEFERRED_SPECS)))
    expect("routes.all_implemented_are_get",
           all(s.method == "GET" for s in links.IMPLEMENTED_SPECS))
    expect("routes.openapi_agreement", openapi.agreement_problems(app) == [],
           str(openapi.agreement_problems(app)))
    expect("routes.openapi_builds", isinstance(app.openapi(), dict))
    expect("routes.no_doc_routes_served",
           all(path.startswith(links.PREFIX) for _m, path in runtime))

    # ------------------------------------------------------------- envelope --
    print("\n-- envelope contract --")
    r = client.get("/api/v2/info")
    payload = body(r)
    expect("envelope.info_200", r.status_code == 200)
    expect("envelope.valid_schema", openapi.validate_response(payload) == [],
           str(openapi.validate_response(payload)))
    expect("envelope.error_null_on_success", payload.get("error") is None)
    expect("envelope.schema_version", payload.get("schema_version") == "examdata.v2/1")
    expect("envelope.request_id_present", str(payload.get("request_id", "")).startswith("req_"))
    expect("envelope.retrieved_at_present", bool(payload.get("meta", {}).get("retrieved_at")))
    expect("envelope.dataset_revision_present",
           payload["meta"]["dataset_revision"] == ds.revision)
    echo = client.get("/api/v2/info", headers={"X-Request-ID": "trace-abc"})
    expect("envelope.request_id_echoed_safe", body(echo)["request_id"] == "trace-abc")
    unsafe = client.get("/api/v2/info", headers={"X-Request-ID": "bad id!"})
    expect("envelope.request_id_replaced_unsafe",
           body(unsafe)["request_id"].startswith("req_"))

    print("\n-- info discovery --")
    data = payload["data"]
    expect("info.counts_match_snapshot", data["counts"] == dict(ds.snapshot.counts))
    expect("info.evidence_synthetic", data["evidence"] == "synthetic_fixture")
    expect("info.systems_are_all_known_systems",
           data["systems"] == ["cie", "edexcel", "gaokao", "ielts", "toefl"])
    available = {row["path"] for row in data["capabilities"]["available"]}
    deferred = {row["path"] for row in data["capabilities"]["deferred"]}
    expect("info.available_paths_are_full_paths",
           available == {s.full_path for s in links.IMPLEMENTED_SPECS})
    expect("info.deferred_paths_listed", deferred == {s.full_path for s in links.DEFERRED_SPECS})
    expect("info.error_map_matches_constant",
           {int(k): v for k, v in data["error_map"].items()} == ERROR_MAP)

    # ---------------------------------------------------------------- errors --
    print("\n-- error map --")
    not_found = client.get("/api/v2/nothing-here")
    expect("error.unknown_path_404",
           not_found.status_code == 404
           and body(not_found)["error"]["code"] == "route_not_found")
    missing_id = client.get("/api/v2/courses/does-not-exist")
    expect("error.unknown_identity_404",
           missing_id.status_code == 404
           and body(missing_id)["error"]["code"] == "not_found")
    bad_limit = client.get("/api/v2/questions", params={"limit": "x"})
    expect("error.bad_limit_400",
           bad_limit.status_code == 400
           and body(bad_limit)["error"]["code"] == "invalid_limit")
    big_limit = client.get("/api/v2/questions", params={"limit": 100000})
    expect("error.over_budget_limit_422",
           big_limit.status_code == 422
           and body(big_limit)["error"]["code"] == "limit_exceeded")
    bad_filter = client.get("/api/v2/courses", params={"nope": "1"})
    expect("error.unsupported_filter_422",
           bad_filter.status_code == 422
           and body(bad_filter)["error"]["code"] == "unsupported_filter")
    wrong_method = client.post("/api/v2/info")
    expect("error.wrong_method_405_framework",
           wrong_method.status_code in FRAMEWORK_STATUSES
           and body(wrong_method)["error"]["code"] == "method_not_allowed")
    for response in (not_found, missing_id, bad_limit, big_limit, bad_filter):
        expect(f"error.{response.request.url.path}.envelope_valid",
               openapi.validate_response(body(response)) == [])
    expect("error.every_emitted_status_is_mapped",
           {not_found.status_code, missing_id.status_code, bad_limit.status_code,
            big_limit.status_code, bad_filter.status_code} <= set(ERROR_MAP))

    # ------------------------------------------------------------- identity --
    print("\n-- identity + hierarchy --")
    container = next(e for e in ds.entries("container") if e.system == "cie")
    c_detail = body(client.get(f"/api/v2/containers/{container.public_id}"))["data"]["item"]
    expect("identity.container_native_identity_preserved",
           c_detail["native_identity"] == container.native_locator["native_identity"])
    c_q = body(client.get(f"/api/v2/containers/{container.public_id}/questions"))["data"]
    order = [row["public_id"] for row in c_q["items"]]
    native_order = [row["native_id"] for row in c_q["items"]]
    expect("identity.container_question_order_is_native",
           native_order == ["1", "1(a)", "1(b)", "2", "3"], str(native_order))
    expect("identity.question_public_ids_are_catalog_ids",
           all(pid.startswith("q_") for pid in order), str(order))

    question = next(e for e in ds.entries("question")
                    if e.identity_fields.get("native_id") == "3" and e.system == "cie")
    q_detail = body(client.get(f"/api/v2/questions/{question.public_id}"))["data"]["item"]
    expect("identity.question_hierarchy_kept",
           q_detail["native_id"] == "3"
           and q_detail["number_path"] == ["3"]
           and str(q_detail["container_ref"]).startswith("container_")
           and q_detail["parent_native_id"] == "__unknown__")
    expect("identity.question_public_id_is_catalog",
           q_detail["public_id"] == question.public_id)

    # -------------------------------------------------- answers / conflicts --
    print("\n-- answers: conflicts and missing slots --")
    answers = body(client.get(f"/api/v2/questions/{question.public_id}/answers"))["data"]
    codes = {gap["code"] for gap in answers["gaps"]}
    expect("answers.conflict_surfaced", "answer_conflict" in codes, str(codes))
    items = answers["items"]
    expect("answers.conflict_candidates_kept",
           len(items) == 1 and len(items[0]["conflicts"]) == 2, str(items))
    expect("answers.conflict_candidates_unresolved",
           all(c["decision"] is None for c in items[0]["conflicts"]))
    expect("answers.manual_decision_absent", items[0]["manual_decision"] is None)
    expect("answers.never_promoted_to_verified",
           items[0]["verification"] != "verified")

    ielts_q = next(e for e in ds.entries("question")
                   if e.system == "ielts" and e.identity_fields.get("native_id") == "Q41")
    ielts_answers = body(
        client.get(f"/api/v2/questions/{ielts_q.public_id}/answers"))["data"]
    expect("answers.missing_slot_is_empty_with_gap",
           ielts_answers["items"] == []
           and "missing_answer_slot" in {g["code"] for g in ielts_answers["gaps"]})

    # ------------------------------------------------------------- regions --
    print("\n-- regions: document hash + evidence status --")
    regions = body(client.get(f"/api/v2/questions/{question.public_id}/regions"))["data"]
    expect("regions.item_present", len(regions["items"]) == 1)
    region = regions["items"][0]
    expect("regions.document_sha256_preserved", bool(region.get("document_sha256")))
    expect("regions.document_role_qp", region.get("document_role") == "qp")
    expect("regions.evidence_status_unverified", region.get("evidence_status") == "unverified")
    expect("regions.missing_region_gap",
           "missing_region" in {g["code"] for g in regions["gaps"]})
    ielts_regions = client.get(f"/api/v2/questions/{ielts_q.public_id}/regions")
    expect("regions.unsupported_capability_422",
           ielts_regions.status_code == 422
           and body(ielts_regions)["error"]["code"] == "unsupported_capability")

    print("\n-- audio never dispatches --")
    audio = body(client.get(f"/api/v2/questions/{question.public_id}/audio"))["data"]
    expect("audio.empty_and_unassociated",
           audio["items"] == [] and audio["association"] is None
           and audio["alignment"] is None)

    # ---------------------------------------------------------- pagination --
    print("\n-- pagination + cursors --")
    page1 = body(client.get("/api/v2/questions", params={"limit": 2}))
    expect("pagination.limit_honoured", len(page1["data"]["items"]) == 2)
    cursor = page1["meta"]["pagination"]["next_cursor"]
    expect("pagination.next_cursor_present", bool(cursor))
    page2 = body(client.get("/api/v2/questions", params={"limit": 2, "cursor": cursor}))
    ids1 = [r["public_id"] for r in page1["data"]["items"]]
    ids2 = [r["public_id"] for r in page2["data"]["items"]]
    expect("pagination.no_overlap_and_stable", not set(ids1) & set(ids2))
    expect("pagination.revision_in_envelope",
           page2["meta"]["dataset_revision"] == ds.revision)
    stale_cursor = pagination.make_cursor(
        dataset_revision="rev-gone", query={}, sort="public_id",
        last_key=ids1[-1], limit=2)
    stale = client.get("/api/v2/questions", params={"cursor": stale_cursor})
    expect("pagination.stale_cursor_409", stale.status_code == 409)
    tampered_body = cursor[:-3] + ("A" if cursor[-3] != "A" else "B") + cursor[-2:]
    tampered = client.get("/api/v2/questions", params={"cursor": tampered_body})
    expect("pagination.tampered_cursor_400", tampered.status_code == 400)

    # --------------------------------------------------- deferred families --
    print("\n-- deferred families are labelled, never fabricated --")
    for path, label in (("/api/v2/materials", "materials"),
                        ("/api/v2/timetables", "timetables"),
                        ("/api/v2/timetables/events", "timetable_events"),
                        ("/api/v2/timetables/windows", "timetable_windows"),
                        ("/api/v2/syllabuses", "syllabuses")):
        got = body(client.get(path))
        items = got["data"].get("items") or got["data"].get("seasons") or []
        expect(f"deferred.{label}_200_and_unknown",
               got["error"] is None and got["meta"]["completeness"] == "unknown")
        expect(f"deferred.{label}_rows_labelled",
               all(row.get("evidence") == "synthetic_fixture"
                   and row.get("integration_status") == "deferred_active_owner"
                   for row in items), label)
        expect(f"deferred.{label}_warns", bool(got["meta"]["warnings"]))
    tags = body(client.get("/api/v2/tags"))
    expect("deferred.tags_empty_with_gap",
           tags["data"]["items"] == []
           and "deferred_source" in {g["code"] for g in tags["data"]["gaps"]})
    tag_q = body(client.get("/api/v2/tags/any_scheme/questions"))
    expect("deferred.tags_questions_explicit",
           tag_q["data"]["items"] == []
           and "deferred_source" in {g["code"] for g in tag_q["data"]["gaps"]})
    job = client.get("/api/v2/jobs/job_synthetic_coverage")
    expect("deferred.job_fixture_200", job.status_code == 200)
    missing_job = client.get("/api/v2/jobs/nope")
    expect("deferred.job_unknown_404",
           missing_job.status_code == 404
           and body(missing_job)["error"]["code"] == "not_found")

    # ------------------------------------------------------------- coverage --
    print("\n-- coverage never invents a denominator --")
    cov = body(client.get("/api/v2/coverage"))["data"]["items"]
    expect("coverage.rows_present", bool(cov))
    expect("coverage.unknown_denominator_has_no_percentage",
           all(row["percentage"] is None for row in cov if not row["denominator_known"]))

    # ------------------------------------------------------------- leaks ----
    print("\n-- sanitization + containment --")
    blob = json.dumps(body(client.get("/api/v2/info")))
    expect("leak.no_original_path_in_info",
           "Desktop" not in blob and "examdata/" not in blob.replace("examdata_integration", ""))
    hostile = client.get("/api/v2/courses", params={"nope": "C:\\Users\\weo\\secret"})
    expect("leak.filter_detail_is_sanitized",
           hostile.status_code == 422
           and "weo" not in hostile.text and "secret" not in hostile.text)

    print(f"\nA10_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    if failures:
        for name in failures:
            print(f"  failing: {name}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
