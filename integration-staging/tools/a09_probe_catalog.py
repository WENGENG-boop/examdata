#!/usr/bin/env python3
"""A09 catalog probe: exercise the mapping store, builder and publisher offline.

Offline, stdlib-only, private synthetic fixtures under
``fixtures/synthetic/catalog/`` plus in-memory edge cases. Prints a stable
transcript to stdout; the closing-checks tool captures it to
`docs/integration/execution/evidence/A09/catalog_stdout.txt`. Exits non-zero if
any scenario fails.

Nothing original is read, no database or network is touched, no upstream URL is
requested, and no identity, quality state or revision is ever fabricated or
promoted past its evidence.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
FIXTURES = STAGING / "fixtures" / "synthetic" / "catalog"
SCRATCH = STAGING / "runtime" / "tmp" / "a09-probe"

sys.path.insert(0, str(SRC))

from examdata_integration.catalog.builder import (  # noqa: E402
    CatalogBuilder,
    diff_snapshots,
    has_authoritative_evidence,
)
from examdata_integration.catalog.model import (  # noqa: E402
    CatalogSnapshot,
    CatalogSource,
    UNKNOWN_TOKEN,
    compute_revision,
    decode_unknown,
)
from examdata_integration.catalog.revision import (  # noqa: E402
    InvalidCursorError,
    PublicationRejected,
    RevisionPublisher,
    StaleCursorError,
    StalePublisherError,
    make_cursor,
    parse_cursor,
    resolve_cursor,
)
from examdata_integration.catalog.store import (  # noqa: E402
    CatalogStore,
    DuplicateNativeIdError,
    to_gap,
)
from examdata_integration.contracts.base import UNKNOWN  # noqa: E402

BASE = FIXTURES / "catalog-base-synthetic.json"
DUP = FIXTURES / "catalog-duplicate-native-id-synthetic.json"
INCOMPLETE = FIXTURES / "catalog-incomplete-reference-synthetic.json"
REMOVAL = FIXTURES / "catalog-removal-unexplained-synthetic.json"
UPGRADE = FIXTURES / "catalog-quality-upgrade-unexplained-synthetic.json"
PROVENANCE = FIXTURES / "PROVENANCE.json"

failures: list[str] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}{(' :: ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sources(data: dict) -> list[CatalogSource]:
    return [CatalogSource.from_dict(s) for s in data.get("sources", [])]


def previous(data: dict):
    if not data.get("previous_sources"):
        return None
    result = CatalogBuilder().build([CatalogSource.from_dict(s) for s in data["previous_sources"]])
    assert result.ok, result.problems
    return result.snapshot


def codes(result) -> list[str]:
    return sorted({p["code"] for p in result.problems})


def main() -> int:
    print("=== A09 catalog probe ===")
    print("synthetic fixtures:", FIXTURES)
    required = [BASE, DUP, INCOMPLETE, REMOVAL, UPGRADE, PROVENANCE]
    if not all(p.is_file() for p in required):
        print("A09_PROBE: FAIL (a staged fixture is missing)")
        return 1
    SCRATCH.mkdir(parents=True, exist_ok=True)
    builder = CatalogBuilder()

    # ------------------------------------------------------------- identity --
    print("\n-- identity mapping --")
    store = CatalogStore()
    base = load(BASE)
    entries = store.add_all(sources(base))
    expect("identity.stable_ids",
           all(e is not None and e.public_id for e in entries)
           and len({e.public_id for e in entries if e}) == len(entries))
    course = next(e for e in store.sorted_entries() if e.kind == "course")
    expect("identity.native_locator_round_trips",
           store.native_locator(course.public_id)["native_code"] == "0580"
           and store.resolve("0580") == course.public_id)
    again = CatalogStore()
    same = again.add(CatalogSource.from_dict(base["sources"][0]))
    expect("identity.deterministic_across_stores", same.public_id == course.public_id)

    print("\n-- duplicates, collisions, aliases --")
    dup = CatalogStore()
    dup.add(CatalogSource.from_dict(load(DUP)["sources"][0]))
    raised = False
    try:
        dup.add(CatalogSource.from_dict(load(DUP)["sources"][1]))
    except DuplicateNativeIdError:
        raised = True
    expect("store.duplicate_native_id_recorded_and_raised",
           raised and [p["code"] for p in dup.problems] == ["duplicate_native_id"]
           and dup.duplicates and dup.duplicates[0]["benign"] is False)

    benign = CatalogStore()
    first = benign.add(CatalogSource.from_dict(base["sources"][0]))
    second = benign.add(CatalogSource.from_dict(base["sources"][0]))
    expect("store.benign_duplicate_deduplicates",
           first is second and len(benign.entries) == 1 and benign.duplicates[0]["benign"] is True)

    import examdata_integration.catalog.store as store_mod
    import examdata_integration.contracts.ids as ids_mod

    real_store_pid = store_mod.derive_public_id
    real_ids_pid = ids_mod.derive_public_id
    forced = "c_" + "a" * 32
    store_mod.derive_public_id = lambda kind, fields: forced
    ids_mod.derive_public_id = lambda kind, fields: forced
    try:
        coll = CatalogStore()
        coll.add(CatalogSource.from_dict(base["sources"][1]))     # container 0580/41
        coll.add(CatalogSource(
            kind="container", system="cie",
            identity_fields={"system": "cie", "kind": "paper",
                             "native_identity": {"native_id": "0580/42",
                                                 "session": "June", "year": 2026}},
            native_locator={"kind": "container",
                            "native_identity": {"native_id": "0580/42",
                                                "session": "June", "year": 2026}},
            content_class="synthetic", evidence_labels=["synthetic_fixture"],
            content_revision="rev-other"))
        expect("store.identity_collision_recorded",
               [p["code"] for p in coll.problems] == ["identity_collision"]
               and len(coll.entries) == 1)
    finally:
        store_mod.derive_public_id = real_store_pid
        ids_mod.derive_public_id = real_ids_pid

    alias = CatalogStore()
    s1 = CatalogSource.from_dict(base["sources"][0])
    s1.aliases = ["shared-alias"]
    alias.add(s1)
    s2 = CatalogSource(kind="course", system="cie",
                       identity_fields={"system": "cie", "qualification": "igcse",
                                        "native_code": "0581", "specification_version": "2026"},
                       native_locator={"kind": "course", "native_code": "0581"},
                       aliases=["SHARED-ALIAS"], content_class="synthetic",
                       evidence_labels=["synthetic_fixture"], content_revision="rev-0581")
    alias.add(s2)
    expect("store.alias_conflict_recorded_atomic",
           [p["code"] for p in alias.problems] == ["alias_conflict"]
           and len(alias.entries) == 1 and alias.resolve("0581") is None)

    # ---------------------------------------------------------- references --
    print("\n-- reference completeness --")
    incomplete = builder.build(sources(load(INCOMPLETE)))
    expect("build.incomplete_reference_rejected",
           not incomplete.ok and incomplete.snapshot is None
           and codes(incomplete) == ["unresolved_identity"])
    gap = to_gap(incomplete.problems[0])
    expect("build.incomplete_reference_maps_to_gap",
           gap is not None and gap.code == "unresolved_identity")

    # -------------------------------------------------------------- build --
    print("\n-- build: reproducibility + diff --")
    ok1 = builder.build(sources(base), created_at="2026-10-05T18:30:00+08:00")
    ok2 = builder.build(sources(base), created_at="2099-01-01T00:00:00+00:00")
    expect("build.valid_snapshot",
           ok1.ok and ok1.snapshot is not None and ok1.counts["total"] == 5)
    expect("build.reproducible_revision",
           ok1.candidate_revision == ok2.candidate_revision
           and ok1.snapshot.recompute_revision() == ok1.snapshot.dataset_revision)
    empty = diff_snapshots(ok1.snapshot, ok1.snapshot.entries)
    expect("build.diff_of_identical_is_empty",
           empty["counts"] == {"added": 0, "removed": 0, "changed": 0, "quality_upgrades": 0})

    print("\n-- build: removal must be explained --")
    removal = builder.build(sources(load(REMOVAL)), previous=previous(load(REMOVAL)),
                            explanations=load(REMOVAL).get("explanations") or {})
    expect("build.unexplained_removal_rejected",
           not removal.ok and removal.snapshot is None
           and "unexplained_removal" in codes(removal))
    removed_pid = CatalogSource.from_dict(load(REMOVAL)["previous_sources"][1]).entry_public_id()
    explained = builder.build(sources(load(REMOVAL)), previous=previous(load(REMOVAL)),
                              explanations={removed_pid: "withdrawn upstream"})
    expect("build.explained_removal_accepted",
           explained.ok and explained.diff["counts"]["removed"] == 1
           and explained.snapshot.explanations == {removed_pid: "withdrawn upstream"})

    print("\n-- build: quality promotion needs authoritative evidence --")
    upgrade = builder.build(sources(load(UPGRADE)), previous=previous(load(UPGRADE)))
    expect("build.unexplained_quality_upgrade_rejected",
           not upgrade.ok and upgrade.snapshot is None
           and codes(upgrade) == ["unexplained_quality_upgrade"])
    promoted = sources(load(UPGRADE))
    promoted[0].evidence_labels = ["copied_snapshot"]
    allowed = builder.build(promoted, previous=previous(load(UPGRADE)))
    expect("build.authoritative_quality_upgrade_accepted",
           allowed.ok and allowed.diff["counts"]["quality_upgrades"] == 1
           and has_authoritative_evidence(allowed.snapshot.entries[0]))
    synthetic = sources(load(UPGRADE))
    expect("build.synthetic_never_authoritative",
           not has_authoritative_evidence(synthetic[0]))

    # --------------------------------------------------------- unknown sentinel --
    print("\n-- explicit UNKNOWN is lossless --")
    q = CatalogSource(
        kind="question", system="ielts",
        identity_fields={"system": "ielts", "container_native_identity": {"native_id": "book-1"},
                         "native_id": "Q41", "number_path": ["41"], "parent_native_id": UNKNOWN},
        native_locator={"kind": "question", "native_id": "Q41", "container_ref": "book-1"},
        content_class="synthetic", evidence_labels=["synthetic_fixture"])
    payload = q.to_dict()
    restored = CatalogSource.from_dict(payload)
    expect("unknown.token_in_json", payload["identity_fields"]["parent_native_id"] == UNKNOWN_TOKEN)
    expect("unknown.round_trips_to_sentinel",
           restored.identity_fields["parent_native_id"] is UNKNOWN
           and decode_unknown(payload["identity_fields"])["parent_native_id"] is UNKNOWN
           and restored.entry_public_id() == q.entry_public_id())

    # ----------------------------------------------------------- publication --
    print("\n-- publication: immutable revision, atomic pointer, CAS, rollback --")
    root = SCRATCH / "catalog"
    shutil.rmtree(root, ignore_errors=True)
    publisher = RevisionPublisher(root)
    rev_a = ok1.snapshot
    pointer = publisher.publish(rev_a, now="2026-10-05T18:30:00+08:00")
    expect("publish.pointer_and_revision_written",
           pointer["schema"] == "catalog-pointer/1"
           and pointer["dataset_revision"] == rev_a.dataset_revision
           and pointer["previous"] is None
           and publisher.load_revision(rev_a.dataset_revision).to_dict() == rev_a.to_dict())
    before = publisher.pointer_path.read_text(encoding="utf-8")
    try:
        publisher.publish(None)
        rejected = False
    except PublicationRejected:
        rejected = True
    expect("publish.none_leaves_pointer_untouched",
           rejected and publisher.pointer_path.read_text(encoding="utf-8") == before)

    variant_sources = sources(base)
    variant_sources.append(CatalogSource(
        kind="course", system="cie",
        identity_fields={"system": "cie", "qualification": "igcse",
                         "native_code": "0582", "specification_version": "2026"},
        native_locator={"kind": "course", "native_code": "0582", "qualification": "igcse"},
        content_class="synthetic", evidence_labels=["synthetic_fixture"],
        content_revision="rev-syn-course-0582"))
    rev_b = builder.build(variant_sources).snapshot
    publisher.publish(rev_b, expected_current=rev_a.dataset_revision, now="t2")
    stale_refused = False
    try:
        publisher.publish(rev_a, expected_current=rev_a.dataset_revision, now="t3")
    except StalePublisherError:
        stale_refused = True
    expect("publish.compare_and_swap_refuses_stale",
           stale_refused and publisher.current_revision() == rev_b.dataset_revision)
    rolled = publisher.rollback(now="t4")
    expect("publish.rollback_restores_previous",
           rolled["dataset_revision"] == rev_a.dataset_revision
           and publisher.current_revision() == rev_a.dataset_revision
           and set(publisher.available_revisions()) == {rev_a.dataset_revision, rev_b.dataset_revision})

    # --------------------------------------------------------------- cursors --
    print("\n-- cursors --")
    cursor = make_cursor(dataset_revision=rev_a.dataset_revision,
                         query={"kind": "question"}, sort="native_id", last_key="Q1", limit=50)
    parsed = parse_cursor(cursor)
    expect("cursor.round_trips",
           parsed["dataset_revision"] == rev_a.dataset_revision
           and parsed["last_key"] == "Q1" and parsed["limit"] == 50)
    body, _, _tag = cursor.rpartition(".")
    tampered = body[:-1] + ("A" if body[-1] != "A" else "B") + "."
    tamper_refused = False
    try:
        parse_cursor(tampered)
    except InvalidCursorError:
        tamper_refused = True
    expect("cursor.tamper_is_invalid", tamper_refused)
    stale_refused = False
    try:
        resolve_cursor(make_cursor(dataset_revision="rev-gone"), ["rev-other"])
    except StaleCursorError:
        stale_refused = True
    expect("cursor.stale_revision_is_409", stale_refused)
    expect("cursor.bound_to_retained_revision_resolves",
           resolve_cursor(cursor, publisher.available_revisions())["dataset_revision"]
           == rev_a.dataset_revision)

    # ------------------------------------------------------------ provenance --
    print("\n-- provenance --")
    manifest = load(PROVENANCE)
    fixtures = sorted(p for p in FIXTURES.glob("*.json") if p.name != "PROVENANCE.json")
    expect("prov.all_fixtures_listed",
           {e["path"].split("/")[-1] for e in manifest["entries"]}
           == {p.name for p in fixtures})
    expect("prov.all_synthetic",
           all(e["label"] == "synthetic_fixture" and e["kind"] == "synthetic"
               for e in manifest["entries"])
           and all(load(p).get("fixture_kind") == "synthetic" for p in fixtures))
    expect("prov.no_upstream_hash_claim",
           all(e["provider"] == "catalog" for e in manifest["entries"]))

    shutil.rmtree(SCRATCH, ignore_errors=True)

    print(f"\nA09_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    if failures:
        for name in failures:
            print(f"  failing: {name}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
