"""B03 integration probe: contracts, registry and local read catalog (plan 12 / B03).

Runs entirely inside the private target-layout candidate and the two Phase A
write roots. It proves, against the candidate's own modules at the *target
layout*:

* the deployment root comes from the explicit ``EXAMDATA_INTEGRATION_ROOT``
  variable (never a directory-name heuristic, never ``PYTHONPATH``, never the
  staging-root override), and every imported product module lives inside the
  candidate;
* every frozen schema file parses and the quality/identity contract files agree
  with the code enums;
* synthetic Node component discovery is cwd-independent and stays inside the
  candidate;
* the fixture providers build a reproducible catalog whose counts match an
  independent derivation from the raw fixture JSON, whose references all
  resolve, and whose native locators round-trip back through the providers;
* publication is compare-and-swap with an atomic pointer, rollback restores the
  previous revision, refusals leave the pointer bytes unchanged, and cursors are
  integrity-checked and revision-bound;
* decisions and provenance survive publish -> load; the ``UNKNOWN`` sentinel
  round-trips as its reserved token;
* the negative paths stay negative (unsupported capability, rejected filter,
  unknown alias, refused rebind, unavailable provider, sanitized failure,
  duplicate native id, unexplained removal, unexplained quality upgrade,
  unresolved reference) while the positive controls stay positive (empty
  success, explained removal, base fixture build, native round trips).

Nothing here writes to the candidate, the original tree, a database, a service
or frozen evidence. Scratch space is confined to the run directory's
``evidence/tmp``. Real Node execution, real source validation, deployment and
cleanup stay ``not_run`` because their gates are closed.

Exit code 0 = every check passed; 1 = at least one check failed; 2 = the probe
refused to run (missing explicit configuration).
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import os
import re
import shutil
import sys
import traceback
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
RUN_ID = "b03-rehearsal-2026-10-07"

#: Environment this probe refuses to run against by accident.
_REQUIRED_ENV = ("B03_CANDIDATE_ROOT", "B03_WORKSPACE_ROOT", "B03_TMP_DIR",
                 "EXAMDATA_INTEGRATION_ROOT")

SKIP_DIRS = {"__pycache__", ".pytest_cache"}

CHECKS: list[dict] = []
NEGATIVE_CHECKS: list[str] = []
POSITIVE_CHECKS: list[str] = []
NOT_RUN: list[dict] = []
MODULE_ORIGINS: dict[str, str] = {}


def check(name: str, ok: bool, detail: object = "", *, polarity: str = "neutral") -> bool:
    record = {"name": name, "ok": bool(ok), "detail": str(detail)[:600]}
    CHECKS.append(record)
    if polarity == "negative":
        NEGATIVE_CHECKS.append(name)
    elif polarity == "positive":
        POSITIVE_CHECKS.append(name)
    return bool(ok)


def run_section(tag: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - a crashed section must still be reported
        tail = traceback.format_exc(limit=4).strip().splitlines()[-3:]
        check(f"{tag}_section_completed", False,
              f"unexpected {type(exc).__name__}: {exc} | " + " | ".join(tail))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_digest(base: Path, exclude: tuple[str, ...] = ()) -> dict:
    entries: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            entries.append((rel, sha256(p)))
    digest = hashlib.sha256()
    for rel, h in entries:
        digest.update(f"{rel}\0{h}\n".encode("utf-8"))
    return {"files": len(entries), "excludes": list(exclude), "sha256": digest.hexdigest()}


def tree_snapshot(base: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            out[p.relative_to(base).as_posix()] = sha256(p)
    return out


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(json.dumps({"ok": False, "refused": True,
                          "error": f"missing required environment variable(s): {missing}"},
                         ensure_ascii=True, indent=2))
        return 2

    candidate = Path(os.environ["B03_CANDIDATE_ROOT"]).resolve()
    workspace = Path(os.environ["B03_WORKSPACE_ROOT"]).resolve()
    tmp_root = Path(os.environ["B03_TMP_DIR"]).resolve()
    src = candidate / "src"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(src))

    scratch = tmp_root / "publication"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    decisions_scratch = tmp_root / "decisions"
    if decisions_scratch.exists():
        shutil.rmtree(decisions_scratch)
    decisions_scratch.mkdir(parents=True, exist_ok=True)

    before_snapshot = tree_snapshot(candidate)
    fixtures_digest_before = tree_digest(candidate / "fixtures" / "synthetic")
    contracts_digest_before = tree_digest(candidate / "contracts")

    # -- imports (after the candidate src is on the path) -------------------- #
    from examdata.integration.api.dataset import (  # noqa: E402
        Dataset, build_fixture_snapshot, deferred_fixtures, fixture_providers)
    from examdata.integration.api.envelope import ApiError  # noqa: E402
    from examdata.integration.api.view import CatalogView, ProviderView  # noqa: E402
    from examdata.integration.catalog.builder import CatalogBuilder  # noqa: E402
    from examdata.integration.catalog.model import (  # noqa: E402
        UNKNOWN_TOKEN, CatalogEntry, CatalogSource)
    from examdata.integration.catalog.revision import (  # noqa: E402
        InvalidCursorError, PublicationRejected, RevisionPublisher,
        StaleCursorError, StalePublisherError, make_cursor, parse_cursor,
        resolve_cursor)
    from examdata.integration.catalog.store import (  # noqa: E402
        CatalogStore, DuplicateNativeIdError)
    from examdata.integration.contracts.base import UNKNOWN  # noqa: E402
    from examdata.integration.contracts import quality as quality_module  # noqa: E402
    from examdata.integration.contracts.enums import EntityKind  # noqa: E402
    from examdata.integration.providers.capabilities import Capability  # noqa: E402
    from examdata.integration.providers.fixtures import (  # noqa: E402
        FailingProvider, NullProvider, UnavailableProvider)
    from examdata.integration.providers.registry import (  # noqa: E402
        AliasRoutingError, ProviderRegistry, UnknownAliasError)
    from examdata.integration.runtime.manifest import load_manifest_set  # noqa: E402

    fixtures_root = candidate / "fixtures" / "synthetic"

    # ====================================================================== #
    # A: environment, origins, isolation, schema, node discovery
    # ====================================================================== #
    def section_a() -> None:
        root_env = os.environ.get("EXAMDATA_INTEGRATION_ROOT")
        check("A_env_root_is_candidate",
              Path(root_env).resolve() == candidate,
              f"EXAMDATA_INTEGRATION_ROOT={root_env!r} candidate={candidate}")
        check("A_no_staging_override",
              "EXAMDATA_INTEGRATION_STAGING_ROOT" not in os.environ,
              "EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged")
        check("A_no_pythonpath", not os.environ.get("PYTHONPATH"),
              f"PYTHONPATH={os.environ.get('PYTHONPATH')!r}")
        check("A_candidate_src_first_on_path",
              Path(sys.path[0]).resolve() == src.resolve(), f"sys.path[0]={sys.path[0]!r}")

        module_names = [
            "examdata.integration.api.dataset",
            "examdata.integration.api.view",
            "examdata.integration.api.envelope",
            "examdata.integration.catalog.builder",
            "examdata.integration.catalog.model",
            "examdata.integration.catalog.store",
            "examdata.integration.catalog.revision",
            "examdata.integration.providers.registry",
            "examdata.integration.providers.fixtures",
            "examdata.integration.providers.capabilities",
            "examdata.integration.contracts.quality",
            "examdata.integration.contracts.ids",
            "examdata.integration.legacy.bridge",
            "examdata.integration.runtime",
            "examdata.integration.runtime.paths",
            "examdata.integration.runtime.manifest",
        ]
        outside: list[str] = []
        for name in module_names:
            module = importlib.import_module(name)
            file = Path(module.__file__).resolve()
            MODULE_ORIGINS[name] = str(file)
            if not str(file).startswith(str(candidate) + os.sep):
                outside.append(f"{name} -> {file}")
        check("A_module_origins_within_candidate", not outside,
              "all candidate" if not outside else "; ".join(outside))

        venv = workspace / "examdata" / ".venv"
        offenders: list[str] = []
        for name, module in list(sys.modules.items()):
            file = getattr(module, "__file__", None)
            if not file:
                continue
            resolved = Path(file).resolve()
            text = str(resolved)
            if text.startswith(str(workspace / "examdata")):
                if not text.startswith(str(venv)):
                    offenders.append(f"{name} -> {text}")
        check("A_no_original_tree_module_loaded", not offenders,
              "no module from the original tree" if not offenders else "; ".join(offenders[:5]))

        product_root = candidate / "src" / "examdata" / "integration"
        import_hits: list[str] = []
        pattern = re.compile(r"^\s*(?:from|import)\s+.*(?:testing\.guards|testing\.node_guard|"
                             r"testing\s+import\s+(?:guards|node_guard))")
        for path in sorted(product_root.rglob("*.py")):
            if "testing" in path.relative_to(product_root).parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.match(line):
                    import_hits.append(f"{path.relative_to(candidate)}:{lineno}")
        check("A_product_no_testing_guard_imports", not import_hits,
              "no product import of testing guards" if not import_hits else "; ".join(import_hits))

        schema_dir = candidate / "contracts" / "schema"
        schema_files = sorted(schema_dir.glob("*.json"))
        bad: list[str] = []
        for path in schema_files:
            try:
                load_json(path)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{path.name}: {exc}")
        check("A_schema_files_parse", len(schema_files) == 28 and not bad,
              f"{len(schema_files)} schema file(s); malformed: {bad or 'none'}")

        transitions = load_json(candidate / "contracts" / "quality-transitions.json")
        dims = transitions.get("dimensions", {})
        code_dims = quality_module.DIMENSIONS
        dim_problems: list[str] = []
        if set(dims) != set(code_dims):
            dim_problems.append(f"dimension names differ: file={sorted(dims)} code={sorted(code_dims)}")
        for name, values in dims.items():
            cls = code_dims.get(name)
            if cls is None:
                continue
            if {member.value for member in cls} != set(values):
                dim_problems.append(f"{name}: file={sorted(values)} code={sorted(m.value for m in cls)}")
        check("A_quality_dimensions_match_code", not dim_problems, dim_problems or "all dimensions agree")

        identity_keys = load_json(candidate / "contracts" / "identity-keys.json")
        kinds = sorted(identity_keys.get("kinds", {}))
        kind_problems = [name for name in kinds if not _coerce_ok(EntityKind, name)]
        check("A_identity_kinds_match_code",
              len(kinds) == len(list(EntityKind)) and not kind_problems,
              f"{len(kinds)} kind(s); unrecognised: {kind_problems or 'none'}")

        components_manifest = candidate / "components" / "manifest.json"
        manifest_set = load_manifest_set(components_manifest, deployment_root=candidate,
                                         require_entry_point=True)
        entry_ids = manifest_set.ids()
        entry = manifest_set.get("fake_cli")
        entry_path = str(entry.entry_path(candidate)) if entry else None
        problems = [p.to_dict() for p in manifest_set.problems]
        check("A_node_discovery_candidate_root",
              entry_ids == ["fake_cli"] and not problems
              and entry_path is not None
              and Path(entry_path).is_file()
              and Path(entry_path).resolve().is_relative_to(candidate),
              f"ids={entry_ids} problems={problems} entry={entry_path}")
        A_DISCOVERY.update({
            "ids": entry_ids,
            "problems": problems,
            "entry_path": entry_path,
            "deployment_root": str(candidate),
            "cwd": str(Path.cwd()),
        })

        legacy = importlib.import_module("examdata.integration.legacy.bridge")
        check("A_legacy_bridge_entry_imports_within_candidate",
              Path(legacy.__file__).resolve().is_relative_to(candidate),
              str(legacy.__file__))

    A_DISCOVERY: dict = {}
    run_section("A", section_a)

    # ====================================================================== #
    # B: build from the fixture providers + independent derivation
    # ====================================================================== #
    CATALOG: dict = {}
    PROVIDER_DATASET: list = []

    def derived_expected() -> dict:
        cie = load_json(fixtures_root / "cie" / "cie-index-synthetic.json")
        edexcel = load_json(fixtures_root / "edexcel" / "index-synthetic.json")
        ielts = load_json(fixtures_root / "ielts" / "questions-synthetic.json")

        def flatten(rows):
            out = []
            for row in rows:
                out.append(row)
                out.extend(flatten(row.get("parts") or row.get("children") or []))
            return out

        expected: dict[str, dict[str, int]] = {}

        def bump(system, kind, n=1):
            expected.setdefault(system, {})
            expected[system][kind] = expected[system].get(kind, 0) + n

        cie_questions = flatten(cie["questions"])
        bump("cie", "course")
        bump("cie", "container")
        bump("cie", "question", len(cie_questions))
        assets = set()
        for q in cie_questions:
            for image in q.get("required_images") or []:
                assets.add(("cie", None, image.get("sha256"), "external_only"))
        for doc in cie["documents"]:
            assets.add(("cie", "application/pdf", doc["sha256"], "external_only"))
        bump("cie", "asset", len(assets))

        units = [unit for subject in edexcel["subjects"] for unit in subject.get("units", [])]
        bump("edexcel", "course", len(edexcel["subjects"]))
        bump("edexcel", "container", len(units))
        ed_assets = {(doc["sha256"]) for unit in units for doc in unit.get("documents", [])}
        bump("edexcel", "asset", len(ed_assets))

        ielts_questions = flatten(ielts["questions"])
        bump("ielts", "course")
        bump("ielts", "container")
        bump("ielts", "question", len(ielts_questions))
        ielts_assets = {image.get("sha256") for q in ielts_questions
                        for image in q.get("required_images") or []}
        bump("ielts", "asset", len(ielts_assets))
        return expected

    def section_b() -> None:
        registry = fixture_providers()
        provider_ids = registry.provider_ids()
        check("B_fixture_provider_order",
              provider_ids == ["cie_index_fixture", "edexcel_index_fixture", "ielts_questions_fixture"],
              provider_ids)

        snapshot = build_fixture_snapshot(registry)
        second = build_fixture_snapshot(fixture_providers())
        revision = snapshot.dataset_revision
        reproducible = (revision == second.dataset_revision
                        == snapshot.recompute_revision()
                        and re.fullmatch(r"rev-[0-9a-f]{32}", revision) is not None)
        check("B_revision_reproducible", reproducible,
              f"revision={revision} reproducible={reproducible}", polarity="positive")
        if not check("B_snapshot_builds", bool(snapshot.entries),
                     f"{len(snapshot.entries)} entries", polarity="positive"):
            return

        expected = derived_expected()
        per_system: dict[str, dict[str, int]] = {}
        per_kind: dict[str, int] = {}
        for entry in snapshot.entries:
            per_system.setdefault(entry.system, {})
            per_system[entry.system][entry.kind] = per_system[entry.system].get(entry.kind, 0) + 1
            per_kind[entry.kind] = per_kind.get(entry.kind, 0) + 1
        match = per_system == expected
        total_expected = sum(sum(kinds.values()) for kinds in expected.values())
        check("B_counts_match_independent_derivation",
              match and snapshot.counts.get("total") == total_expected
              and snapshot.counts.get("total") == sum(per_kind.values()),
              f"expected={expected} actual={per_system} total={snapshot.counts.get('total')}",
              polarity="positive")

        by_id = snapshot.by_id()
        dangling: list[str] = []
        for entry in snapshot.entries:
            for role, ref in (("container_ref", entry.container_ref), ("course_ref", entry.course_ref)):
                if ref and ref not in by_id:
                    dangling.append(f"{entry.public_id}:{role}->{ref}")
            if entry.kind == "container":
                for ref in entry.searchable.get("question_refs", []):
                    if ref not in by_id:
                        dangling.append(f"{entry.public_id}:question_ref->{ref}")
                for section in entry.searchable.get("sections", []):
                    for ref in section.get("questions", []) or []:
                        if ref not in by_id:
                            dangling.append(f"{entry.public_id}:section->{ref}")
        cie_container = next(e for e in snapshot.entries if e.kind == "container" and e.system == "cie")
        ielts_container = next(e for e in snapshot.entries if e.kind == "container" and e.system == "ielts")
        edexcel_container = next(e for e in snapshot.entries if e.kind == "container" and e.system == "edexcel")
        # ``question_refs`` is only materialised for containers that had at
        # least one question placed into them (dataset.py rewrites the list
        # there); an absent key therefore means "no question refs", which is
        # exactly what the edexcel fixture container expects. The view code
        # reads it with the same gets-default-empty convention.
        edexcel_refs = edexcel_container.searchable.get("question_refs") or []
        check("B_reference_integrity",
              not dangling
              and len(cie_container.searchable.get("question_refs", [])) == 5
              and len(ielts_container.searchable.get("question_refs", [])) == 8
              and edexcel_refs == [],
              f"dangling={dangling[:5] or 'none'} cie_refs={len(cie_container.searchable.get('question_refs', []))} "
              f"ielts_refs={len(ielts_container.searchable.get('question_refs', []))} "
              f"edexcel_refs={len(edexcel_refs)} (absent key means none)",
              polarity="positive")

        dataset = Dataset(snapshot=snapshot, registry=registry,
                          available_revisions=(revision,))
        view = CatalogView(dataset)
        alias_expectations = [
            ("synthetic-subject", "course", "cie"),
            ("WMA", "course", "edexcel"),
            ("synthetic-maths", "course", "edexcel"),
            ("SB1", "course", "ielts"),
            ("synthetic/cambridge-1", "course", "ielts"),
        ]
        alias_problems = []
        for alias, kind, system in alias_expectations:
            found = view.find(alias, kind)
            if found is None or found.system != system or found.kind != kind:
                alias_problems.append(f"{alias}->{found}")
        check("B_alias_lookup_via_view", not alias_problems, alias_problems or "all aliases resolve")

        CATALOG.update({
            "revision": revision,
            "counts": {"total": snapshot.counts.get("total"), "per_kind": per_kind,
                       "per_system": per_system, "expected": expected},
        })
        PROVIDER_DATASET.append((dataset, registry, snapshot))

    run_section("B", section_b)

    # ====================================================================== #
    # C: native locator round trips through the providers
    # ====================================================================== #
    ROUNDTRIP: dict = {}

    def dispatch_one(registry, capability, provider_id, *, filters=None, target=None):
        result = registry.dispatch(capability, provider_ids=[provider_id],
                                   filters=filters, target=target)
        providers = result.results
        if len(providers) != 1:
            return None, result
        return providers[0], result

    def section_c() -> None:
        if not PROVIDER_DATASET:
            check("C_roundtrips_skipped", False, "no provider dataset from section B")
            return
        dataset, registry, snapshot = PROVIDER_DATASET[0]
        by_id = snapshot.by_id()

        cie_course = next(e for e in snapshot.entries if e.kind == "course" and e.system == "cie")
        native_code = cie_course.identity_fields["native_code"]
        item, _ = dispatch_one(registry, Capability.COURSES, "cie_index_fixture",
                               filters={"subject": native_code})
        ok = item is not None and item.ok and len(item.items) == 1 \
            and str(item.items[0].native_code) == str(native_code)
        aliased, _ = dispatch_one(registry, Capability.COURSES, "cie_index_fixture",
                                  filters={"subject": "synthetic-subject"})
        ok = ok and aliased is not None and aliased.ok and len(aliased.items) == 1
        check("C_course_roundtrip_cie", ok,
              f"native_code={native_code} items={len(item.items) if item else None}", polarity="positive")

        cie_container = next(e for e in snapshot.entries if e.kind == "container" and e.system == "cie")
        item, _ = dispatch_one(registry, Capability.CONTAINERS, "cie_index_fixture",
                               filters={"subject": "9999"})
        container_native = dict(cie_container.native_locator["native_identity"])
        ok = item is not None and item.ok and any(
            {k: v for k, v in row.native_identity.items()} == container_native for row in item.items)
        check("C_container_roundtrip_cie", ok,
              f"native_identity={container_native}", polarity="positive")

        cie_question = next(e for e in snapshot.entries
                            if e.kind == "question" and e.system == "cie"
                            and e.identity_fields["native_id"] == "3")
        item, _ = dispatch_one(registry, Capability.QUESTIONS, "cie_index_fixture", target="3")
        ok = item is not None and item.ok and len(item.items) == 1 \
            and item.items[0].native_id == "3" \
            and list(item.items[0].number_path) == list(cie_question.identity_fields["number_path"])
        check("C_question_roundtrip_cie", ok,
              f"number_path={cie_question.identity_fields['number_path']}", polarity="positive")

        ielts_question = next(e for e in snapshot.entries
                              if e.kind == "question" and e.system == "ielts"
                              and e.identity_fields["native_id"] == "Q3.ii")
        item, _ = dispatch_one(registry, Capability.QUESTIONS, "ielts_questions_fixture", target="Q3.ii")
        ok = item is not None and item.ok and len(item.items) == 1 \
            and item.items[0].native_id == "Q3.ii" \
            and list(item.items[0].number_path) == list(ielts_question.identity_fields["number_path"])
        check("C_question_roundtrip_ielts", ok,
              f"number_path={ielts_question.identity_fields['number_path']}", polarity="positive")

        edexcel_container = next(e for e in snapshot.entries
                                 if e.kind == "container" and e.system == "edexcel")
        item, _ = dispatch_one(registry, Capability.CONTAINERS, "edexcel_index_fixture",
                               filters={"unit_code": "WMA11"})
        ed_native = dict(edexcel_container.native_locator["native_identity"])
        ok = item is not None and item.ok and any(
            dict(row.native_identity) == ed_native for row in item.items)
        check("C_container_roundtrip_edexcel", ok,
              f"native_identity={ed_native}", polarity="positive")

        ielts_container = next(e for e in snapshot.entries
                               if e.kind == "container" and e.system == "ielts")
        item, _ = dispatch_one(registry, Capability.CONTAINERS, "ielts_questions_fixture",
                               filters={"book": "synthetic-book-1"})
        ielts_native = dict(ielts_container.native_locator["native_identity"])
        ok = item is not None and item.ok and any(
            dict(row.native_identity) == ielts_native for row in item.items)
        check("C_container_roundtrip_ielts", ok,
              f"native_identity={ielts_native}", polarity="positive")

        asset_checks: list[str] = []
        cie_asset = select_asset(snapshot, "cie", "4" * 64)
        item, _ = dispatch_one(registry, Capability.ASSETS, "cie_index_fixture")
        if not (item and item.ok and any(getattr(row, "sha256", None) == "4" * 64 for row in item.items)):
            asset_checks.append("cie required image sha not found in ASSETS")
        if cie_asset is not None and cie_asset.native_locator.get("sha256") != "4" * 64:
            asset_checks.append("cie catalog asset locator mismatch")
        edexcel_asset = select_asset(snapshot, "edexcel", "5" * 64)
        item, _ = dispatch_one(registry, Capability.RESOURCES, "edexcel_index_fixture")
        if not (item and item.ok and any(getattr(row, "sha256", None) == "5" * 64 for row in item.items)):
            asset_checks.append("edexcel document sha not found in RESOURCES")
        if edexcel_asset is None:
            asset_checks.append("edexcel catalog asset missing")
        ielts_asset = select_asset(snapshot, "ielts", "0" * 64)
        item, _ = dispatch_one(registry, Capability.ASSETS, "ielts_questions_fixture")
        if not (item and item.ok and any(getattr(row, "sha256", None) == "0" * 64 for row in item.items)):
            asset_checks.append("ielts required image sha not found in ASSETS")
        if ielts_asset is None:
            asset_checks.append("ielts catalog asset missing")
        check("C_assets_roundtrip", not asset_checks,
              asset_checks or "cie/edexcel/ielts asset locators round-trip", polarity="positive")

        ROUNDTRIP.update({
            "cie_course": str(native_code),
            "cie_container": container_native,
            "cie_question": cie_question.identity_fields["native_id"],
            "ielts_question": "Q3.ii",
            "edexcel_container": ed_native,
            "ielts_container": ielts_native,
            "asset_hashes": {"cie": "4" * 64, "edexcel": "5" * 64, "ielts": "0" * 64},
        })

    def select_asset(snapshot, system: str, sha: str):
        for entry in snapshot.entries:
            if entry.kind == "asset" and entry.system == system \
                    and entry.native_locator.get("sha256") == sha:
                return entry
        return None

    run_section("C", section_c)

    # ====================================================================== #
    # D: publication, compare-and-swap, rollback, cursors
    # ====================================================================== #
    PUBLICATION: dict = {}
    BASE_SNAPSHOT: list = []

    def section_d() -> None:
        if not PROVIDER_DATASET:
            check("D_publication_skipped", False, "no provider dataset from section B")
            return
        _, _, provider_snapshot = PROVIDER_DATASET[0]

        base_doc = load_json(fixtures_root / "catalog" / "catalog-base-synthetic.json")
        base_sources = [CatalogSource.from_dict(s) for s in base_doc["sources"]]
        base_result = CatalogBuilder().build(
            base_sources, input_revisions=base_doc["input_revisions"], explanations={})
        if not base_result.ok or base_result.snapshot is None:
            check("D_base_snapshot_builds", False,
                  f"problems={[p.get('code') for p in base_result.problems]}")
            return
        BASE_SNAPSHOT.append(base_result.snapshot)

        publisher = RevisionPublisher(scratch)
        revision_a = provider_snapshot.dataset_revision
        revision_b = base_result.snapshot.dataset_revision

        pointer_a = publisher.publish(provider_snapshot, expected_current=None)
        ok_a = (pointer_a.get("schema") == "catalog-pointer/1"
                and pointer_a.get("dataset_revision") == revision_a
                and pointer_a.get("previous") is None
                and publisher.retain(revision_a))
        pointer_b = publisher.publish(base_result.snapshot, expected_current=revision_a)
        ok_b = (pointer_b.get("dataset_revision") == revision_b
                and pointer_b.get("previous") == revision_a
                and publisher.current_revision() == revision_b
                and publisher.retain(revision_a) and publisher.retain(revision_b))
        check("D_publish_a_then_b_cas", ok_a and ok_b,
              f"a={revision_a} b={revision_b}", polarity="positive")

        before = publisher.pointer_path.read_bytes()
        stale_raised = False
        try:
            publisher.publish(provider_snapshot, expected_current=revision_a)
        except StalePublisherError:
            stale_raised = True
        after = publisher.pointer_path.read_bytes()
        check("D_stale_publish_rejected_pointer_unchanged",
              stale_raised and before == after,
              f"StalePublisherError={stale_raised} pointer_bytes_unchanged={before == after}",
              polarity="negative")

        rollback_pointer = publisher.rollback()
        check("D_rollback_restores_previous",
              rollback_pointer.get("dataset_revision") == revision_a
              and rollback_pointer.get("previous") == revision_b
              and publisher.current_revision() == revision_a,
              f"current={publisher.current_revision()} expected={revision_a}", polarity="positive")

        before = publisher.pointer_path.read_bytes()
        rejected_none = False
        try:
            publisher.publish(None, expected_current=revision_a)
        except PublicationRejected:
            rejected_none = True
        after = publisher.pointer_path.read_bytes()
        check("D_publish_none_rejected", rejected_none and before == after,
              f"PublicationRejected={rejected_none} pointer_bytes_unchanged={before == after}",
              polarity="negative")

        tampered = dataclasses.replace(provider_snapshot, dataset_revision="rev-" + "0" * 32)
        before = publisher.pointer_path.read_bytes()
        rejected_tampered = False
        try:
            publisher.publish(tampered, expected_current=revision_a)
        except PublicationRejected:
            rejected_tampered = True
        after = publisher.pointer_path.read_bytes()
        check("D_tampered_snapshot_rejected_pointer_unchanged",
              rejected_tampered and before == after,
              f"PublicationRejected={rejected_tampered} pointer_bytes_unchanged={before == after}",
              polarity="negative")

        cursor = make_cursor(dataset_revision=revision_a, query={"kind": "course"},
                             sort="public_id", last_key="course:0580", limit=10)
        payload = parse_cursor(cursor)
        same_again = make_cursor(dataset_revision=revision_a, query={"kind": "course"},
                                 sort="public_id", last_key="course:0580", limit=10)
        check("D_cursor_roundtrip",
              payload.get("dataset_revision") == revision_a
              and payload.get("query") == {"kind": "course"}
              and cursor == same_again,
              "cursor round-trips deterministically", polarity="positive")

        tampered_cursor = cursor[:-1] + ("0" if cursor[-1] != "0" else "1")
        invalid_raised = False
        try:
            parse_cursor(tampered_cursor)
        except InvalidCursorError:
            invalid_raised = True
        check("D_cursor_tampered_invalid", invalid_raised,
              f"InvalidCursorError={invalid_raised}", polarity="negative")

        stale_cursor_raised = False
        try:
            resolve_cursor(cursor, [revision_b])
        except StaleCursorError:
            stale_cursor_raised = True
        resolved_ok = resolve_cursor(cursor, [revision_a, revision_b])["dataset_revision"] == revision_a
        check("D_cursor_stale_revision_rejected", stale_cursor_raised and resolved_ok,
              f"StaleCursorError={stale_cursor_raised}", polarity="negative")

        PUBLICATION.update({
            "scratch": str(scratch),
            "revision_a": revision_a, "revision_b": revision_b,
            "final_current": publisher.current_revision(),
            "retained": publisher.available_revisions(),
        })

    run_section("D", section_d)

    # ====================================================================== #
    # E: preserved decisions/provenance, UNKNOWN token, deferred honesty
    # ====================================================================== #
    PROVENANCE: dict = {}

    def section_e() -> None:
        if not BASE_SNAPSHOT:
            check("E_provenance_skipped", False, "no base snapshot from section D")
            return
        base_snapshot = BASE_SNAPSHOT[0]

        explanations = {"0580": "synthetic explanation carried through publication"}
        explained = dataclasses.replace(base_snapshot, explanations=dict(explanations))
        explained = dataclasses.replace(
            explained, dataset_revision=explained.recompute_revision())
        publisher = RevisionPublisher(decisions_scratch)
        publisher.publish(explained, expected_current=None)
        loaded = publisher.load_revision(explained.dataset_revision)
        entries_equal = [e.to_dict() for e in loaded.entries] == [e.to_dict() for e in explained.entries]
        check("E_decisions_and_provenance_roundtrip",
              loaded.dataset_revision == explained.dataset_revision
              and loaded.explanations == explanations
              and loaded.counts == explained.counts
              and entries_equal,
              f"entries={len(loaded.entries)} explanations_ok={loaded.explanations == explanations} "
              f"entries_equal={entries_equal}", polarity="positive")

        quality_fields = ("quality_summary", "evidence_labels", "lineage", "content_class",
                          "content_revision", "aliases")
        provenance_kept = all(
            all(a.to_dict()[f] == b.to_dict()[f] for f in quality_fields)
            for a, b in zip(loaded.entries, explained.entries))
        check("E_provenance_fields_preserved", provenance_kept,
              f"fields={quality_fields}", polarity="positive")

        if PROVIDER_DATASET:
            _, _, provider_snapshot = PROVIDER_DATASET[0]
            top = next(e for e in provider_snapshot.entries
                       if e.kind == "question" and e.system == "cie"
                       and e.identity_fields.get("parent_native_id") is UNKNOWN)
            raw = top.to_dict()
            token_in_raw = raw["identity_fields"]["parent_native_id"] == UNKNOWN_TOKEN
            decoded = CatalogEntry.from_dict(raw)
            sentinel_back = decoded.identity_fields["parent_native_id"] is UNKNOWN
            check("E_unknown_token_roundtrip",
                  token_in_raw and sentinel_back
                  and decoded.content_hash() == top.content_hash(),
                  f"token_in_raw={token_in_raw} sentinel_restored={sentinel_back}",
                  polarity="positive")

        if PROVIDER_DATASET:
            dataset, _, _ = PROVIDER_DATASET[0]
            systems = {row["system"]: row for row in dataset.systems()}
            deferred_states: list[str] = []
            for name in ("toefl", "gaokao"):
                row = systems.get(name)
                if not row or row.get("availability") != "unavailable" or not row.get("reason"):
                    deferred_states.append(f"{name}:{row}")
            for name in ("cie", "edexcel", "ielts"):
                row = systems.get(name)
                if not row or row.get("availability") != "available" \
                        or row.get("evidence") != "synthetic_fixture":
                    deferred_states.append(f"{name}:{row}")
            check("E_systems_deferred_honesty", not deferred_states,
                  deferred_states or "systems report availability honestly")

            families = deferred_fixtures()
            items = []
            for key in ("syllabuses", "materials", "timetable_seasons", "timetable_events",
                        "timetable_windows"):
                items.extend(families.get(key, []))
            items.extend(families.get("jobs", {}).values())
            offenders = [item for item in items
                         if item.get("evidence") != "synthetic_fixture"
                         or item.get("integration_status") != "deferred_active_owner"]
            check("E_deferred_fixtures_labelled", not offenders and items,
                  f"{len(items)} labelled fixture item(s); offenders={offenders[:3]}")

        PROVENANCE.update({"loaded_revision": loaded.dataset_revision,
                           "entries": len(loaded.entries)})

    run_section("E", section_e)

    # ====================================================================== #
    # F: registry and dispatch negatives (plus the empty-success control)
    # ====================================================================== #
    REGISTRY: dict = {}

    def api_error_of(view, **kwargs):
        try:
            view.dispatch(**kwargs)
            return None
        except ApiError as exc:
            return {"status": exc.status, "code": exc.code}

    def section_f() -> None:
        if not PROVIDER_DATASET:
            check("F_registry_skipped", False, "no provider dataset from section B")
            return
        dataset, registry, _ = PROVIDER_DATASET[0]
        view = ProviderView(dataset)

        item, _ = dispatch_one(registry, Capability.QUESTIONS, "edexcel_index_fixture")
        ok = item is not None and not item.ok and item.status.value == "unsupported" \
            and item.error_code == "unsupported_capability"
        error = api_error_of(view, capability=Capability.QUESTIONS, system="edexcel")
        check("F_edexcel_questions_unsupported",
              ok and error == {"status": 422, "code": "unsupported_capability"},
              f"result={item.status.value if item else None} view={error}", polarity="negative")

        item, _ = dispatch_one(registry, Capability.COURSES, "cie_index_fixture",
                               filters={"year": 2024})
        ok = item is not None and not item.ok and item.status.value == "filter_rejected" \
            and item.error_code == "unsupported_filter" and item.filter_key == "year"
        error = api_error_of(view, capability=Capability.COURSES, system="cie", filters={"year": 2024})
        check("F_cie_courses_filter_rejected",
              ok and error == {"status": 422, "code": "unsupported_filter"},
              f"result={item.status.value if item else None} view={error}", polarity="negative")

        unknown_raised = False
        try:
            registry.route("no-such-alias-anywhere")
        except UnknownAliasError:
            unknown_raised = True
        check("F_unknown_alias_refused",
              unknown_raised and not registry.owns_alias("no-such-alias-anywhere"),
              f"UnknownAliasError={unknown_raised}", polarity="negative")

        rebind_registry = fixture_providers()
        rebind_registry.register_alias("synthetic-subject", "cie_index_fixture")
        rebind_raised = False
        try:
            rebind_registry.register_alias("synthetic-subject", "edexcel_index_fixture")
        except AliasRoutingError:
            rebind_raised = True
        check("F_alias_rebind_refused",
              rebind_raised and rebind_registry.route("synthetic-subject") == "cie_index_fixture",
              f"AliasRoutingError={rebind_raised}",
              polarity="negative")

        item, _ = dispatch_one(registry, Capability.COURSES, "ghost_provider")
        check("F_unknown_provider_failed",
              item is not None and not item.ok and item.error_code == "unknown_provider",
              f"result={item.to_dict() if item else None}", polarity="negative")

        unavailable_registry = ProviderRegistry()
        unavailable_registry.register(UnavailableProvider())
        item, _ = dispatch_one(unavailable_registry, Capability.COURSES, "optional_unavailable")
        unavailable_ok = item is not None and not item.ok \
            and item.status.value == "unavailable" and item.error_code == "provider_unavailable" \
            and item.retryable
        unavailable_dataset = Dataset(snapshot=PROVIDER_DATASET[0][2],
                                      registry=unavailable_registry,
                                      available_revisions=())
        error = api_error_of(ProviderView(unavailable_dataset), capability=Capability.COURSES,
                             system="cie")
        check("F_unavailable_provider_reported",
              unavailable_ok and error == {"status": 503, "code": "provider_unavailable"},
              f"result={item.status.value if item else None} view={error}", polarity="negative")

        error = api_error_of(view, capability=Capability.COURSES, system="toefl")
        check("F_view_unknown_system_503",
              error == {"status": 503, "code": "provider_unavailable"},
              f"view={error}", polarity="negative")

        failing_registry = ProviderRegistry()
        failing_registry.register(FailingProvider())
        item, result = dispatch_one(failing_registry, Capability.COURSES, "failing_fixture")
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        ok = item is not None and not item.ok and item.status.value == "failed" \
            and "secret.db" not in (item.detail or "") and "<path>" in (item.detail or "") \
            and "secret.db" not in serialized and "C:\\" not in serialized \
            and "private" not in (item.detail or "")
        check("F_failing_provider_sanitized", ok,
              f"detail={item.detail if item else None}", polarity="negative")

        null_registry = ProviderRegistry()
        null_registry.register(NullProvider())
        item, result = dispatch_one(null_registry, Capability.DISCOVERY, "null_fixture")
        ok = item is not None and item.ok and item.count == 0 \
            and result.status == "ok" and result.error is None
        check("F_null_provider_empty_success", ok,
              f"status={result.status} count={result.items and len(result.items)}",
              polarity="positive")

        REGISTRY.update({"negative_probed": len(NEGATIVE_CHECKS)})

    run_section("F", section_f)

    # ====================================================================== #
    # G: build negatives and positives from the catalog fixtures
    # ====================================================================== #
    BUILD_RESULTS: dict = {}

    def sources_from(doc, key="sources"):
        return [CatalogSource.from_dict(s) for s in doc[key]]

    def codes_of(result) -> list[str]:
        return [p.get("code") for p in result.problems]

    def section_g() -> None:
        dup = load_json(fixtures_root / "catalog" / "catalog-duplicate-native-id-synthetic.json")
        dup_sources = sources_from(dup)
        store = CatalogStore()
        store.add(dup_sources[0])
        duplicate_raised = False
        try:
            store.add(dup_sources[1])
        except DuplicateNativeIdError:
            duplicate_raised = True
        check("G_duplicate_native_id_raises",
              duplicate_raised
              and any(p.get("code") == "duplicate_native_id" for p in store.problems),
              f"raised={duplicate_raised} problems={store.problems}", polarity="negative")
        dup_result = CatalogBuilder().build(dup_sources, input_revisions=dup["input_revisions"])
        check("G_duplicate_native_id_build_fails",
              not dup_result.ok and dup_result.snapshot is None
              and "duplicate_native_id" in codes_of(dup_result),
              f"ok={dup_result.ok} codes={codes_of(dup_result)}", polarity="negative")

        removal = load_json(fixtures_root / "catalog" / "catalog-removal-unexplained-synthetic.json")
        previous = CatalogBuilder().build(sources_from(removal, "previous_sources"),
                                          input_revisions=removal["input_revisions"])
        removal_result = CatalogBuilder().build(
            sources_from(removal), previous=previous.snapshot,
            input_revisions=removal["input_revisions"], explanations={})
        removed_ids = removal_result.diff.get("removed", [])
        check("G_unexplained_removal_rejected",
              not removal_result.ok and removal_result.snapshot is None
              and "unexplained_removal" in codes_of(removal_result) and removed_ids,
              f"codes={codes_of(removal_result)} removed={removed_ids}", polarity="negative")

        explained_result = CatalogBuilder().build(
            sources_from(removal), previous=previous.snapshot,
            input_revisions=removal["input_revisions"],
            explanations={pid: "synthetic replacement explanation" for pid in removed_ids})
        check("G_explained_removal_accepted",
              explained_result.ok and explained_result.snapshot is not None
              and explained_result.snapshot.explanations,
              f"ok={explained_result.ok} codes={codes_of(explained_result)}", polarity="positive")

        upgrade = load_json(
            fixtures_root / "catalog" / "catalog-quality-upgrade-unexplained-synthetic.json")
        upgrade_previous = CatalogBuilder().build(
            sources_from(upgrade, "previous_sources"), input_revisions=upgrade["input_revisions"])
        upgrade_result = CatalogBuilder().build(
            sources_from(upgrade), previous=upgrade_previous.snapshot,
            input_revisions=upgrade["input_revisions"], explanations={})
        check("G_unexplained_quality_upgrade_rejected",
              not upgrade_result.ok and upgrade_result.snapshot is None
              and "unexplained_quality_upgrade" in codes_of(upgrade_result),
              f"codes={codes_of(upgrade_result)}", polarity="negative")

        incomplete = load_json(
            fixtures_root / "catalog" / "catalog-incomplete-reference-synthetic.json")
        incomplete_result = CatalogBuilder().build(sources_from(incomplete),
                                                   input_revisions=incomplete["input_revisions"])
        scopes = [p.get("scope") for p in incomplete_result.problems
                  if p.get("code") == "unresolved_identity"]
        check("G_incomplete_reference_rejected",
              not incomplete_result.ok and incomplete_result.snapshot is None
              and "course_ref" in scopes,
              f"codes={codes_of(incomplete_result)} scopes={scopes}", polarity="negative")

        base_doc = load_json(fixtures_root / "catalog" / "catalog-base-synthetic.json")
        base_sources = sources_from(base_doc)
        base_result = CatalogBuilder().build(base_sources, input_revisions=base_doc["input_revisions"],
                                             explanations={})
        base_ok = base_result.ok and base_result.snapshot is not None \
            and base_result.snapshot.counts.get("total") == 5
        check("G_base_fixture_build_ok", base_ok,
              f"ok={base_result.ok} counts={base_result.counts}", polarity="positive")

        base_store = CatalogStore()
        base_store.add_all(base_sources)
        course_id = base_store.resolve("0580")
        container_id = base_store.resolve("0580/41-june-2026")
        question_id = base_store.resolve("S1Q1")
        locator = base_store.native_locator(course_id) if course_id else None
        check("G_base_aliases_resolve",
              course_id is not None and container_id is not None and question_id is not None
              and locator is not None and locator.get("native_code") == "0580",
              f"course={course_id} container={container_id} question={question_id} locator={locator}",
              polarity="positive")

        BUILD_RESULTS.update({
            "duplicate": {"ok": dup_result.ok, "codes": codes_of(dup_result)},
            "removal": {"ok": removal_result.ok, "codes": codes_of(removal_result)},
            "quality_upgrade": {"ok": upgrade_result.ok, "codes": codes_of(upgrade_result)},
            "incomplete": {"ok": incomplete_result.ok, "codes": codes_of(incomplete_result)},
            "base_total": base_result.snapshot.counts.get("total") if base_result.snapshot else None,
        })

    run_section("G", section_g)

    # ====================================================================== #
    # Raw data immutability + payload scan (whole candidate)
    # ====================================================================== #
    def section_h() -> None:
        after_snapshot = tree_snapshot(candidate)
        changed = [rel for rel in set(before_snapshot) | set(after_snapshot)
                   if before_snapshot.get(rel) != after_snapshot.get(rel)]
        check("H_candidate_bytes_unchanged", not changed, changed[:8] or "identical")

        fixtures_digest_after = tree_digest(candidate / "fixtures" / "synthetic")
        contracts_digest_after = tree_digest(candidate / "contracts")
        check("H_fixture_and_contract_digests_unchanged",
              fixtures_digest_after == fixtures_digest_before
              and contracts_digest_after == contracts_digest_before,
              f"fixtures={fixtures_digest_after['sha256'][:12]} contracts={contracts_digest_after['sha256'][:12]}")

        payload_pattern = re.compile(rb"data:[a-zA-Z]+/")
        hits: list[str] = []
        for path in sorted((candidate / "fixtures").rglob("*.json")):
            if payload_pattern.search(path.read_bytes()):
                hits.append(path.relative_to(candidate).as_posix())
        check("H_no_embedded_data_payloads", not hits, hits[:5] or "no data: URIs in fixtures")

    run_section("H", section_h)

    # ====================================================================== #
    # Report
    # ====================================================================== #
    NOT_RUN.extend([
        {"check": "real Node component execution (fake-cli.mjs run via Node runtime)",
         "reason": "gate original_paths_released is closed; only discovery and importability "
                   "of the synthetic component are rehearsed"},
        {"check": "real Node/source validation against the original project",
         "reason": "gate original_paths_released is closed; the original tree was never read"},
        {"check": "real database schema / data migration",
         "reason": "gate real_data_write_authorized is closed; no database is staged or touched"},
        {"check": "live service / upstream provider calls",
         "reason": "gate upstream_requests_authorized is closed; only synthetic fixture "
                   "providers ran"},
        {"check": "deployment to any target",
         "reason": "gate remote_deployment_authorized is closed; this candidate is private-only"},
        {"check": "credential usage of any kind",
         "reason": "no credential gate exists in the seven-gate model and none is needed: no "
                   "credential is used; nothing was read, fabricated or staged; the private "
                   "fixture allowlists a synthetic token name but never a value"},
    ])

    failed = [record["name"] for record in CHECKS if not record["ok"]]
    ok = not failed
    candidate_manifest_path = candidate / "B03_CANDIDATE_MANIFEST.json"
    manifest_doc = load_json(candidate_manifest_path) if candidate_manifest_path.is_file() else {}
    recorded = manifest_doc.get("candidate_tree", {})
    recomputed = tree_digest(candidate, tuple(recorded.get("excludes", []))) if recorded else {}

    report = {
        "schema": "examdata.integration.b03_integration_probe/1",
        "run_id": RUN_ID,
        "packet": "B03",
        "candidate_root": str(candidate),
        "environment": {
            "cwd": str(Path.cwd()),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "pythonpath": os.environ.get("PYTHONPATH"),
            "staging_override": os.environ.get("EXAMDATA_INTEGRATION_STAGING_ROOT"),
            "root_env": os.environ.get("EXAMDATA_INTEGRATION_ROOT"),
            "dont_write_bytecode": sys.dont_write_bytecode,
        },
        "candidate_manifest": {
            "path": str(candidate_manifest_path),
            "sha256": sha256(candidate_manifest_path) if candidate_manifest_path.is_file() else None,
            "recorded_tree": recorded,
            "recomputed_tree": recomputed,
            "digest_matches": bool(recorded) and recomputed == recorded,
            "counts": manifest_doc.get("counts"),
        },
        "module_origins": MODULE_ORIGINS,
        "discovery": {"from_candidate_cwd": A_DISCOVERY},
        "catalog": {
            "revision": CATALOG.get("revision"),
            "counts": CATALOG.get("counts"),
            "roundtrips": ROUNDTRIP,
        },
        "publication": PUBLICATION,
        "provenance": PROVENANCE,
        "registry_checks": REGISTRY,
        "build_checks": BUILD_RESULTS,
        "checks": CHECKS,
        "counts": {
            "checks": len(CHECKS),
            "checks_failed": len(failed),
            "negative_checks": len(NEGATIVE_CHECKS),
            "positive_checks": len(POSITIVE_CHECKS),
        },
        "negative_checks": NEGATIVE_CHECKS,
        "positive_checks": POSITIVE_CHECKS,
        "failed": failed,
        "ok": ok,
        "not_run": NOT_RUN,
        "note": ("private rehearsal only; not merged, not deployed; the original tree was never "
                 "read, imported or written; frozen evidence was not touched; scratch space was "
                 "confined to the run directory's evidence/tmp"),
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if ok else 1


def _coerce_ok(enum_cls, name: str) -> bool:
    try:
        enum_cls.coerce(name)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
