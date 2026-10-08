"""A06 component manifest validation tests (plan 6.3).

Every validation problem carries a stable code, an invalid component is never
admitted to the runner whitelist, and the doctor renders problems without
creating a directory or leaking a secret.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examdata_integration.runtime import (
    MANIFEST_VERSION,
    ManifestError,
    load_manifest_set,
    parse_component,
)
from examdata_integration.runtime.doctor import build_report
from examdata_integration.testing import runtime_support

STAGING = runtime_support.STAGING
MANIFEST_PATH = runtime_support.MANIFEST_PATH


def _codes(problems) -> set[str]:
    return {p.code for p in problems}


# -- the staged manifest ------------------------------------------------------

def test_staged_manifest_admits_fake_cli():
    result = load_manifest_set(MANIFEST_PATH, deployment_root=STAGING)
    assert result.problems == []
    manifest = result.get("fake_cli")
    assert manifest is not None
    assert manifest.runtime == "node"
    assert manifest.read_write_policy == "read_only"
    assert "ok" in manifest.supported_commands
    assert result.allows("fake_cli", "ok") is True
    assert result.allows("fake_cli", "not-a-command") is False
    assert result.ids() == ["fake_cli"]
    report = result.report()
    assert report and report[0]["component_id"] == "fake_cli"


# -- one case per problem code ------------------------------------------------

PROBLEM_CASES = [
    ("missing_field", "missing_field", lambda s: s.pop("version"), True),
    ("wrong_type", "wrong_type", lambda s: s.update(name=123), False),
    ("bad_identifier", "bad_identifier", lambda s: s.update(component_id="Bad Id!"), False),
    ("empty", "empty", lambda s: s.update(supported_commands=[]), False),
    ("bad_command", "bad_command", lambda s: s.update(supported_commands=["ok", "Bad Cmd"]), False),
    ("duplicate_command", "duplicate_command",
     lambda s: s.update(supported_commands=["ok", "ok"]), False),
    ("not_relative_parent", "not_relative_path",
     lambda s: s.update(code_location="../escape"), False),
    ("not_relative_absolute", "not_relative_path",
     lambda s: s.update(code_location="/abs/path"), False),
    ("unknown_runtime", "unknown_runtime", lambda s: s.update(runtime="ruby"), False),
    ("unknown_policy", "unknown_policy",
     lambda s: s.update(read_write_policy="yolo"), False),
    ("bad_env_name", "bad_env_name",
     lambda s: s.update(environment_allowlist=["1BAD"]), False),
    ("bad_role", "bad_role", lambda s: s.update(data_roots={"Bad-Role": "x"}), False),
    ("health_probe_unknown_command", "health_probe_unknown_command",
     lambda s: s.update(health_probe={"command": "nope"}), False),
]


@pytest.mark.parametrize("case,code,mutate,expect_none", PROBLEM_CASES,
                         ids=[c[0] for c in PROBLEM_CASES])
def test_problem_code_reported(case, code, mutate, expect_none):
    spec = runtime_support.component_spec()
    mutate(spec)
    manifest, problems = parse_component(spec, deployment_root=STAGING)
    assert code in _codes(problems)
    assert (manifest is None) is expect_none


def test_entry_point_missing_when_required():
    spec = runtime_support.component_spec(entry_point="nope.mjs")
    manifest, problems = parse_component(spec, deployment_root=STAGING,
                                         require_entry_point=True)
    assert manifest is not None
    assert "entry_point_missing" in _codes(problems)
    # Without the strict flag the declaration is still admitted (the runner
    # reports missing_component at call time instead).
    _, relaxed = parse_component(spec, deployment_root=STAGING)
    assert relaxed == []


def test_relative_escape_is_blocked_before_root_check():
    # ``path_escapes_root`` is defensive: any '..' or drive/root prefix is
    # already rejected as ``not_relative_path``, so a relative declaration
    # cannot reach the root-escape branch.
    spec = runtime_support.component_spec(code_location="components/../../escape")
    _, problems = parse_component(spec, deployment_root=STAGING)
    assert "not_relative_path" in _codes(problems)
    assert "path_escapes_root" not in _codes(problems)


# -- document-level failures --------------------------------------------------

def test_bad_manifest_version_raises(tmp_path):
    path = runtime_support.write_manifest(
        tmp_path, [runtime_support.component_spec()],
        manifest_version="examdata.component-manifest/9")
    with pytest.raises(ManifestError):
        load_manifest_set(path, deployment_root=STAGING)


def test_bad_manifest_json_raises(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest_set(path, deployment_root=STAGING)


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest_set(tmp_path / "absent.json", deployment_root=STAGING)


def test_empty_component_list_raises(tmp_path):
    path = runtime_support.write_manifest(tmp_path, [])
    with pytest.raises(ManifestError):
        load_manifest_set(path, deployment_root=STAGING)


def test_invalid_component_is_not_admitted(tmp_path):
    good = runtime_support.component_spec()
    bad = runtime_support.component_spec(component_id="bad_one", runtime="ruby")
    path = runtime_support.write_manifest(tmp_path, [good, bad])
    result = load_manifest_set(path, deployment_root=STAGING)
    assert result.ids() == ["fake_cli"]
    assert result.get("bad_one") is None
    assert "unknown_runtime" in _codes(result.problems)
    assert result.warnings and "admitted" in result.warnings[0]


def test_duplicate_component_id_not_admitted_twice(tmp_path):
    first = runtime_support.component_spec()
    second = runtime_support.component_spec()
    path = runtime_support.write_manifest(tmp_path, [first, second])
    result = load_manifest_set(path, deployment_root=STAGING)
    assert "duplicate_component_id" in _codes(result.problems)
    assert result.ids() == ["fake_cli"]


# -- doctor (read-only) -------------------------------------------------------

def test_doctor_creates_nothing(tmp_path):
    sentinel = tmp_path / "doctor-catalog"
    report = build_report(env={"EXAMDATA_CATALOG_ROOT": str(sentinel)},
                          manifest_path=MANIFEST_PATH, deployment_root=STAGING)
    assert report["creates_directories"] is False
    assert report["schema"] == "examdata.doctor/1"
    assert report["mode"] == "PHASE_A_ISOLATED_ONLY"
    assert not sentinel.exists()


def test_doctor_reports_runtime_and_network():
    report = build_report(env={}, manifest_path=MANIFEST_PATH, deployment_root=STAGING)
    node = runtime_support.node_executable()
    assert report["runtime"]["found"] is (node is not None)
    assert report["network"]["mode"] == "offline"
    assert report["network"]["compliant"] is True


def test_doctor_redacts_secret():
    secret = "doctor-secret-value"
    report = build_report(env={"EXAMDATA_API_KEY": secret},
                          manifest_path=MANIFEST_PATH, deployment_root=STAGING)
    assert secret not in json.dumps(report)
    rows = {row["key"]: row for row in report["settings"]}
    assert rows["api_key"]["value"] == "set"


def test_doctor_reports_component_problems(tmp_path):
    bad = runtime_support.component_spec(component_id="bad_one", read_write_policy="yolo")
    path = runtime_support.write_manifest(tmp_path, [bad])
    report = build_report(env={}, manifest_path=path, deployment_root=STAGING)
    assert report["components"] == []
    assert "unknown_policy" in {p["code"] for p in report["component_problems"]}


def test_doctor_reports_admitted_component_paths():
    report = build_report(env={}, manifest_path=MANIFEST_PATH, deployment_root=STAGING)
    assert len(report["components"]) == 1
    component = report["components"][0]
    assert component["component_id"] == "fake_cli"
    assert component["entry_point_exists"] is True
    assert component["valid"] is True
    assert component["data_roots"]["fake_data"].endswith(
        str(Path("runtime") / "data" / "fake-cli"))
