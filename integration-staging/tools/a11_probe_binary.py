#!/usr/bin/env python3
"""A11 binary transport probe: exercise the five staged binary rows offline.

In-process only: the app is built from the staged package with a content store
rooted in the frozen synthetic fixtures, and Starlette's TestClient never opens
a socket. The crop pipeline's private temp copies are pinned under
`integration-staging/runtime/tmp/` so the probe never writes outside the Phase A
writable roots. Prints a stable transcript to stdout; the closing-checks tool
captures it to `docs/integration/execution/evidence/A11/binary_stdout.txt`.
Exits non-zero if any scenario fails.

Nothing original is read, no database or network is touched, no upstream URL is
requested, and no document hash, byte size, identity or quality state is ever
fabricated or promoted past its evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
FIXTURE_DIR = STAGING / "fixtures" / "synthetic" / "binary"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
PROVENANCE_PATH = FIXTURE_DIR / "PROVENANCE.json"
SECTIONS = ("documents", "syllabuses", "materials", "crops")
PLACEHOLDERS = {digit * 64 for digit in "0123456789"}

sys.path.insert(0, str(SRC))
# R04: product code resolves its deployment root explicitly (never by directory name).
os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", str(STAGING))

from fastapi.testclient import TestClient  # noqa: E402

from examdata_integration.api import binary, dataset, links, openapi  # noqa: E402
from examdata_integration.api.app import create_app  # noqa: E402

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


def finish() -> int:
    print(f"\nA11_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    for name in failures:
        print(f"  failing: {name}")
    return 0 if not failures else 1


def question_id(ds, system: str, native_id: str) -> str:
    for entry in ds.entries("question"):
        if entry.system != system:
            continue
        if (entry.identity_fields.get("native_id") == native_id
                or entry.native_locator.get("native_id") == native_id):
            return entry.public_id
    raise AssertionError(f"no {system!r} question fixture with native id {native_id!r}")


def main() -> int:
    print("=== A11 binary content probe ===")
    tmp_root = STAGING / "runtime" / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    store = binary.ContentStore(FIXTURE_DIR, MANIFEST_PATH, temp_root=tmp_root)
    app = create_app(content_store=store)
    client = TestClient(app)
    ds = dataset.default_dataset()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    # ------------------------------------------------------- route inventory --
    print("\n-- route registration --")
    binary_specs = [s for s in links.ROUTE_SPECS if s.binary]
    served = openapi.runtime_pairs(app)
    documented = openapi.spec_pairs(app)
    expect("routes.five_binary_rows", len(binary_specs) == 5,
           str([s.capability for s in binary_specs]))
    expect("routes.runtime_equals_spec", served == documented,
           f"{len(served)} vs {len(documented)}")
    expect("routes.runtime_equals_advertised", served == set(links.advertised_pairs()),
           f"{len(served)} vs {len(links.advertised_pairs())}")
    expect("routes.implemented_count", len(links.IMPLEMENTED_SPECS) == 34,
           str(len(links.IMPLEMENTED_SPECS)))
    expect("routes.deferred_count", links.DEFERRED_SPECS == ())
    expect("routes.head_pairs_are_the_binary_rows",
           openapi.runtime_head_pairs(app) == {("HEAD", s.full_path) for s in binary_specs})
    expect("routes.openapi_agreement", openapi.agreement_problems(app) == [],
           str(openapi.agreement_problems(app)))
    for spec in binary_specs:
        expect(f"routes.{spec.capability}.get_registered",
               (spec.method, spec.full_path) in served, spec.full_path)

    # ----------------------------------------------------- openapi document --
    print("\n-- openapi document --")
    document = app.openapi()
    statuses_ok, media_ok, no_json_ok, failure_envelope_ok = True, True, True, True
    for spec in binary_specs:
        for method in ("get", "head"):
            operation = document["paths"][spec.full_path][method]
            if not {"200", "206", "304", "413", "416"} <= set(operation["responses"]):
                statuses_ok = False
            for code in ("200", "206"):
                content = set(operation["responses"][code].get("content", {}))
                if content != set(spec.media_types):
                    media_ok = False
                if "application/json" in content:
                    no_json_ok = False
            for code in ("413", "416"):
                if "application/json" not in operation["responses"][code].get("content", {}):
                    failure_envelope_ok = False
    expect("openapi.binary_rows_document_statuses", statuses_ok)
    expect("openapi.binary_rows_document_media", media_ok)
    expect("openapi.binary_rows_have_no_json_success_body", no_json_ok)
    expect("openapi.binary_rows_failures_are_envelopes", failure_envelope_ok)
    expect("openapi.spec_head_pairs_match_runtime",
           openapi.spec_head_pairs(app) == {("HEAD", s.full_path) for s in binary_specs})
    expect("openapi.non_binary_rows_keep_json",
           "application/json" in document["paths"]["%s" % links.spec_for("info").full_path]
           ["get"]["responses"]["200"]["content"])

    # ------------------------------------------------------- store integrity --
    print("\n-- store integrity --")
    expect("store.loads_without_problems", store.problems == [], str(store.problems))
    expect("store.ok", store.ok)
    expect("store.eleven_samples", len(store.all_samples) == 11,
           str(len(store.all_samples)))
    for section in SECTIONS:
        agree = all(
            hashlib.sha256((FIXTURE_DIR / entry["file"]).read_bytes()).hexdigest()
            == entry["sha256"]
            and len((FIXTURE_DIR / entry["file"]).read_bytes()) == entry["byte_size"]
            for entry in manifest[section])
        expect(f"store.{section}_match_disk", agree)
    real = {entry["sha256"] for section in SECTIONS for entry in manifest[section]}
    declared = ({entry.get("declared_sha256") for entry in manifest["documents"]}
                | {entry["declared_document_sha256"] for entry in manifest["crops"]})
    expect("store.real_hashes_are_not_placeholders", not (real & PLACEHOLDERS))
    expect("store.declared_identities_are_placeholders",
           declared <= PLACEHOLDERS and len(declared) == 6, str(sorted(declared)))
    documents = {(entry["system"], entry["role"]): entry["declared_sha256"]
                 for entry in manifest["documents"]}
    expect("store.declared_documents_frozen", documents == {
        ("cie", "qp"): "2" * 64, ("cie", "ms"): "3" * 64,
        ("cie", "graph"): "4" * 64, ("edexcel", "qp"): "5" * 64,
        ("edexcel", "ms"): "6" * 64, ("ielts", "diagram"): "0" * 64})
    crops = [(entry["system"], entry["native_id"], entry["page"],
              entry["declared_document_sha256"]) for entry in manifest["crops"]]
    expect("store.crop_pages_frozen", crops == [
        ("cie", "1", 2, "2" * 64), ("cie", "2", 3, "2" * 64),
        ("cie", "3", 4, "2" * 64)])
    generator = STAGING / "tools" / "build_binary_fixtures.py"
    expect("store.generator_hash_matches_manifest",
           hashlib.sha256(generator.read_bytes()).hexdigest()
           == manifest["generator_sha256"])

    print("\n-- provenance --")
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    expect("provenance.twelve_entries",
           provenance["schema"] == "fixture-provenance/1"
           and len(provenance["entries"]) == 12)
    covered = {entry["path"] for entry in provenance["entries"]}
    on_disk = {f"integration-staging/fixtures/synthetic/binary/{p.name}"
               for p in FIXTURE_DIR.iterdir() if p.is_file()}
    expect("provenance.covers_every_fixture_file",
           covered == on_disk - {"integration-staging/fixtures/synthetic/binary/"
                                 "PROVENANCE.json"})
    expect("provenance.hashes_match_disk", all(
        hashlib.sha256((WS / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
        and (WS / entry["path"]).stat().st_size == entry["bytes"]
        for entry in provenance["entries"]))
    expect("provenance.all_labelled_synthetic", all(
        entry["kind"] == "synthetic" and entry["label"] == "synthetic_fixture"
        for entry in provenance["entries"]))

    # --------------------------------------------------------- asset transport --
    print("\n-- asset transport --")
    revision = body(client.get("/api/v2/info"))["data"]["dataset_revision"]
    asset = ds.entries("asset")[0]
    sample = store.for_asset(asset.system, asset.identity_fields.get("sha256"))
    expect("asset.has_verified_sample",
           sample is not None and sample.media_type == "image/png")
    if sample is None:
        return finish()
    blob = sample.path.read_bytes()
    url = f"/api/v2/assets/{asset.public_id}/content"
    got = client.get(url, headers={"x-request-id": "req-a11-probe"})
    expect("asset.get_200", got.status_code == 200)
    expect("asset.body_is_verified_bytes", got.content == blob)
    expect("asset.served_hash_verifies",
           hashlib.sha256(got.content).hexdigest() == sample.sha256)
    expect("asset.content_type", got.headers.get("content-type") == "image/png")
    expect("asset.accept_ranges", got.headers.get("accept-ranges") == "bytes")
    expect("asset.etag_is_strong_sha", got.headers.get("etag") == f'"{sample.sha256}"')
    expect("asset.x_content_sha256_is_real",
           got.headers.get("x-content-sha256") == sample.sha256
           and got.headers.get("x-content-sha256") != sample.declared_sha256)
    expect("asset.evidence_header", got.headers.get("x-evidence") == "synthetic_fixture")
    expect("asset.dataset_revision_header",
           got.headers.get("x-dataset-revision") == revision)
    expect("asset.request_id_echoed", got.headers.get("x-request-id") == "req-a11-probe")
    expect("asset.content_disposition",
           got.headers.get("content-disposition")
           == f'inline; filename="{asset.public_id}.png"')
    expect("asset.content_length",
           got.headers.get("content-length") == str(sample.byte_size))
    head = client.head(url)
    expect("asset.head_matches_get",
           head.status_code == 200 and head.content == b""
           and head.headers.get("content-length") == str(sample.byte_size)
           and head.headers.get("etag") == sample.etag)
    alias = client.get(f"/api/v2/resources/{asset.public_id}/content")
    expect("asset.resources_alias", alias.status_code == 200 and alias.content == blob)

    # ------------------------------------------------------------ byte ranges --
    print("\n-- byte ranges --")
    first = client.get(url, headers={"range": "bytes=0-9"})
    expect("range.206_first_ten",
           first.status_code == 206 and first.content == blob[:10]
           and first.headers.get("content-range") == f"bytes 0-9/{sample.byte_size}")
    tail = client.get(url, headers={"range": "bytes=-10"})
    expect("range.suffix", tail.status_code == 206 and tail.content == blob[-10:])
    rest = client.get(url, headers={"range": f"bytes=10-{sample.byte_size - 1}"})
    expect("range.parts_join", first.content + rest.content == blob)
    unsatisfiable = client.get(url, headers={"range": f"bytes={sample.byte_size + 1}-"})
    payload = body(unsatisfiable)
    expect("range.416",
           unsatisfiable.status_code == 416
           and payload.get("error", {}).get("code") == "range_not_satisfiable"
           and payload.get("data") is None)
    expect("range.416_content_range_header",
           unsatisfiable.headers.get("content-range") == f"bytes */{sample.byte_size}")
    expect("range.416_envelope_valid", openapi.validate_response(payload) == [])
    zero = client.get(url, headers={"range": "bytes=-0"})
    expect("range.bare_zero_416", zero.status_code == 416)
    ignored = client.get(url, headers={"range": "bytes=5-3"})
    expect("range.inverted_ignored_200",
           ignored.status_code == 200 and ignored.content == blob)

    # ------------------------------------------------------- conditional ----
    print("\n-- conditional requests --")
    matches = 0
    for value in (f'"{sample.sha256}"', f'W/"{sample.sha256}"',
                  f'"other", "{sample.sha256}"'):
        response = client.get(url, headers={"if-none-match": value})
        if (response.status_code == 304 and response.content == b""
                and "content-length" not in response.headers):
            matches += 1
    expect("conditional.304_three_forms", matches == 3, str(matches))
    fresh = client.get(url, headers={"if-none-match": '"other"'})
    expect("conditional.other_etag_200", fresh.status_code == 200)

    # ---------------------------------------------------------- failure modes --
    print("\n-- failure modes --")
    post = client.post(url)
    expect("errors.post_405",
           post.status_code == 405
           and body(post).get("error", {}).get("code") == "method_not_allowed")
    filtered = client.get(url, params={"limit": 1})
    expect("errors.query_422",
           filtered.status_code == 422
           and body(filtered).get("error", {}).get("code") == "unsupported_filter")
    unknown = client.get("/api/v2/assets/asset_probe_missing/content")
    expect("errors.unknown_asset_404",
           unknown.status_code == 404
           and body(unknown).get("error", {}).get("code") == "not_found"
           and body(unknown).get("data") is None)

    # -------------------------------------------------- syllabus / material --
    print("\n-- syllabus and material content --")
    syllabus = client.get("/api/v2/syllabuses/syl_synthetic_cie_0580/content")
    expect("syllabus.200_pdf",
           syllabus.status_code == 200 and syllabus.content.startswith(b"%PDF-")
           and syllabus.headers.get("content-type") == "application/pdf")
    expect("syllabus.content_disposition",
           syllabus.headers.get("content-disposition")
           == 'inline; filename="syl_synthetic_cie_0580.pdf"')
    no_syllabus = client.get("/api/v2/syllabuses/syl_synthetic_ielts_book/content")
    expect("syllabus.no_sample_404",
           no_syllabus.status_code == 404
           and body(no_syllabus).get("error", {}).get("code") == "content_not_available")
    missing_syllabus = client.get("/api/v2/syllabuses/syl_probe_missing/content")
    expect("syllabus.unknown_404",
           missing_syllabus.status_code == 404
           and body(missing_syllabus).get("error", {}).get("code") == "not_found")
    material = client.get("/api/v2/materials/mat_synthetic_cie_ins/content")
    expect("material.200_pdf",
           material.status_code == 200 and material.content.startswith(b"%PDF-"))
    no_material = client.get("/api/v2/materials/mat_synthetic_edexcel_gt/content")
    expect("material.no_sample_404",
           no_material.status_code == 404
           and body(no_material).get("error", {}).get("code") == "content_not_available")

    # ------------------------------------------------------------ question crops --
    print("\n-- question crops --")
    crop_sample = store.crop_for("cie", "1")
    expect("crop.has_verified_sample", crop_sample is not None)
    if crop_sample is None:
        return finish()
    q1 = question_id(ds, "cie", "1")
    crop = client.get(f"/api/v2/questions/{q1}/crop")
    crop_blob = crop_sample.path.read_bytes()
    expect("crop.200_png",
           crop.status_code == 200 and crop.content == crop_blob
           and crop.headers.get("content-type") == "image/png")
    expect("crop.served_hash_verifies",
           hashlib.sha256(crop.content).hexdigest() == crop_sample.sha256)
    expect("crop.provenance_headers",
           crop.headers.get("x-document-sha256") == "2" * 64
           and crop.headers.get("x-page") == "2")
    expect("crop.content_disposition",
           crop.headers.get("content-disposition") == f'inline; filename="{q1}.png"')
    ranged = client.get(f"/api/v2/questions/{q1}/crop", headers={"range": "bytes=0-99"})
    expect("crop.range_206",
           ranged.status_code == 206 and ranged.content == crop_blob[:100]
           and ranged.headers.get("content-range")
           == f"bytes 0-99/{crop_sample.byte_size}")
    no_crop = question_id(ds, "cie", "1(a)")
    missing = client.get(f"/api/v2/questions/{no_crop}/crop")
    expect("crop.missing_sample_404",
           missing.status_code == 404
           and body(missing).get("error", {}).get("code") == "crop_not_available")
    regionless = question_id(ds, "ielts", "Q1")
    unsupported = client.get(f"/api/v2/questions/{regionless}/crop")
    expect("crop.regionless_422",
           unsupported.status_code == 422
           and body(unsupported).get("error", {}).get("code") == "unsupported_capability")
    unknown_question = client.get("/api/v2/questions/q_probe_missing/crop")
    expect("crop.unknown_question_404",
           unknown_question.status_code == 404
           and body(unknown_question).get("error", {}).get("code") == "not_found")

    # --------------------------------------------------------- response budgets --
    print("\n-- response budgets --")
    small_store = binary.ContentStore(
        FIXTURE_DIR, MANIFEST_PATH,
        limits=binary.ContentLimits(max_total_bytes=100, max_crop_bytes=50),
        temp_root=tmp_root)
    small = TestClient(create_app(content_store=small_store))
    over = small.get(url)
    over_body = body(over)
    expect("budget.asset_413",
           over.status_code == 413
           and over_body.get("error", {}).get("code") == "response_budget_exceeded")
    expect("budget.413_details",
           over_body.get("error", {}).get("details")
           == {"limit": 100, "byte_size": sample.byte_size})
    expect("budget.413_envelope_valid", openapi.validate_response(over_body) == [])
    over_crop = small.get(f"/api/v2/questions/{q1}/crop")
    expect("budget.crop_413",
           over_crop.status_code == 413
           and body(over_crop).get("error", {}).get("code") == "crop_budget_exceeded")

    # -------------------------------------------------------- evidence conflicts --
    print("\n-- evidence conflicts --")

    def conflict_copy(change: dict) -> tuple:
        root = Path(tempfile.mkdtemp(prefix="a11-conflict-", dir=str(tmp_root)))
        try:
            shutil.copytree(FIXTURE_DIR, root / "binary")
            manifest_path = root / "binary" / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            target = next(entry for entry in data["crops"]
                          if entry["system"] == "cie" and entry["native_id"] == "1")
            target.update(change)
            manifest_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            broken = binary.ContentStore(root / "binary", manifest_path,
                                         temp_root=tmp_root)
            return root, broken
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    for change, code in (({"declared_document_sha256": "9" * 64}, "hash_conflict"),
                         ({"page": 7}, "region_conflict")):
        root, broken = conflict_copy(change)
        try:
            expect(f"conflict.{code}.store_ok", broken.ok, str(broken.problems))
            response = TestClient(create_app(content_store=broken)).get(
                f"/api/v2/questions/{q1}/crop")
            expect(f"conflict.{code}.409",
                   response.status_code == 409
                   and body(response).get("error", {}).get("code") == code
                   and body(response).get("data") is None)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # --------------------------------------------------------- generated check --
    print("\n-- fixture generator --check --")
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "tools/build_binary_fixtures.py", "--check"],
        cwd=str(STAGING), capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=120)
    expect("generator.check_rc0", result.returncode == 0, (result.stdout or "")[-200:])
    expect("generator.check_pass_line",
           "BINARY_FIXTURES: PASS (13 files match a fresh render)" in result.stdout
           and "[FAIL]" not in result.stdout)

    # ------------------------------------------------------------ containment --
    print("\n-- containment --")
    stragglers = sorted(p.name for p in tmp_root.iterdir()
                        if p.name.startswith(("crop-", "a11-conflict-")))
    expect("containment.no_temp_leftovers", stragglers == [], str(stragglers))

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
