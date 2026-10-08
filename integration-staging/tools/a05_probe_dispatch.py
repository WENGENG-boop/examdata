#!/usr/bin/env python3
"""A05 dispatch probe: exercise the provider registry over the A03 synthetic fixtures.

Pure, offline, stdlib-only. Builds the three fixture providers, then runs the
dispatch scenarios the plan names (A05 tests) and prints a stable transcript to
stdout; the closing-checks tool captures it to
`docs/integration/execution/evidence/A05/dispatch_stdout.txt`. Exits non-zero if
any scenario's assertion fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
FIXTURES = STAGING / "fixtures" / "synthetic"
EV = WS / "docs" / "integration" / "execution" / "evidence" / "A05"

sys.path.insert(0, str(SRC))

from examdata_integration.providers import (  # noqa: E402
    AliasRoutingError,
    Capability,
    CIEIndexProvider,
    EdexcelIndexProvider,
    FailingProvider,
    IELTSQuestionsProvider,
    NullProvider,
    ProviderRegistry,
    UnavailableProvider,
    UnknownAliasError,
)

failures: list[str] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}{(' :: ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def build_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(CIEIndexProvider(FIXTURES / "cie" / "cie-index-synthetic.json"))
    registry.register(EdexcelIndexProvider(FIXTURES / "edexcel" / "index-synthetic.json"))
    registry.register(IELTSQuestionsProvider(FIXTURES / "ielts" / "questions-synthetic.json"))
    return registry


def main() -> int:
    print("=== A05 provider dispatch probe ===")
    registry = build_registry()
    print("providers:", registry.provider_ids())

    # 1. discovery across every provider
    d = registry.dispatch(Capability.DISCOVERY)
    expect("discovery.ok", d.status == "ok", f"status={d.status} count={len(d.items)}")

    # 2. CIE questions: ok, hierarchy preserved
    q = registry.dispatch(Capability.QUESTIONS, provider_ids=["cie_index_fixture"])
    expect("cie.questions.ok", q.status == "ok", f"count={len(q.items)}")
    cie_numbers = sorted(item.native_id for item in q.items)
    expect("cie.questions.hierarchy", {"1", "1(a)", "1(b)", "2", "3"} <= set(cie_numbers),
           f"numbers={cie_numbers}")

    # 3. Edexcel does not implement questions -> typed unsupported (not empty success)
    e = registry.dispatch(Capability.QUESTIONS, provider_ids=["edexcel_index_fixture"])
    expect("edexcel.questions.unsupported",
           e.status == "error" and e.error["code"] == "unsupported_capability",
           f"error={e.error['code'] if e.error else None}")
    expect("edexcel.questions.not_empty_success", e.items == [])

    # 4. IELTS with a year filter -> typed filter_rejected (a book number is not a date)
    y = registry.dispatch(Capability.QUESTIONS, provider_ids=["ielts_questions_fixture"],
                          filters={"year": 2024})
    expect("ielts.year.filter_rejected",
           y.status == "error" and y.error["code"] == "unsupported_filter"
           and y.error["details"]["providers"][0]["filter_key"] == "year",
           f"error={y.error['code'] if y.error else None}")

    # 5. IELTS missing answer slot: empty success WITH a gap, never fabricated
    a = registry.dispatch(Capability.ANSWERS, provider_ids=["ielts_questions_fixture"], target="Q41")
    expect("ielts.Q41.empty_success_with_gap",
           a.status == "ok" and a.items == []
           and any(g.code == "missing_answer_slot" for g in a.gaps),
           f"status={a.status} gaps={[g.code for g in a.gaps]}")

    # 6. IELTS answer conflict carried as a gap, verification stays unverified
    c = registry.dispatch(Capability.ANSWERS, provider_ids=["ielts_questions_fixture"], target="Q5")
    conflict_ok = (c.status == "ok" and c.items
                   and c.items[0].verification == "unverified"
                   and any(g.code == "answer_conflict" for g in c.gaps))
    expect("ielts.Q5.conflict_unverified", conflict_ok,
           f"gaps={[g.code for g in c.gaps]}")

    # 7. CIE unknown date preserved as a gap
    ctn = registry.dispatch(Capability.CONTAINERS, provider_ids=["cie_index_fixture"])
    expect("cie.container.unknown_date_gap",
           any(g.code == "unknown_date" for g in ctn.gaps),
           f"gaps={[g.code for g in ctn.gaps]}")

    # 8. alias routing: IELTS alias never routes to CIE
    registry.register_alias("synthetic/cambridge-1", "ielts_questions_fixture")
    registry.register_alias("SB1", "ielts_questions_fixture")
    expect("alias.routes_to_ielts",
           registry.route("synthetic/cambridge-1") == "ielts_questions_fixture"
           and registry.route("sb1") == "ielts_questions_fixture")
    try:
        registry.register_alias("synthetic/cambridge-1", "cie_index_fixture")
        expect("alias.conflict_refused", False, "rebind was allowed")
    except AliasRoutingError:
        expect("alias.conflict_refused", True)
    try:
        registry.route("no-such-alias")
        expect("alias.unknown_raises", False, "unknown alias was routed")
    except UnknownAliasError:
        expect("alias.unknown_raises", True)

    # 9. multi-provider partial success: CIE ok + failing provider
    registry.register(FailingProvider())
    p = registry.dispatch(Capability.COURSES,
                          provider_ids=["cie_index_fixture", "failing_fixture"])
    expect("partial.status", p.status == "partial", f"status={p.status}")
    expect("partial.has_data", len(p.items) == 1)
    expect("partial.failure_sanitized",
           all("private" not in w and "secret" not in w for w in p.warnings))

    # 10. all providers fail -> error, never an empty 200
    f = registry.dispatch(Capability.COURSES, provider_ids=["failing_fixture"])
    expect("all_fail.error", f.status == "error" and f.items == []
           and f.error["code"] == "provider_failed")

    # 11. unavailable optional provider
    registry.register(UnavailableProvider())
    u = registry.dispatch(Capability.COURSES, provider_ids=["optional_unavailable"])
    expect("unavailable.error", u.status == "error" and u.error["code"] == "provider_unavailable")
    u2 = registry.dispatch(Capability.COURSES,
                           provider_ids=["optional_unavailable", "cie_index_fixture"])
    expect("unavailable.partial_with_available", u2.status == "partial" and len(u2.items) == 1)

    # 12. genuine empty success vs unsupported
    registry.register(NullProvider())
    n = registry.dispatch(Capability.DISCOVERY, provider_ids=["null_fixture"])
    expect("null.empty_success", n.status == "ok" and n.items == [])

    # 13. no provider requested -> explicit error
    z = registry.dispatch(Capability.COURSES, provider_ids=[])
    expect("no_provider.error", z.status == "error" and z.error["code"] == "no_provider_requested")

    print(f"\nA05_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    if failures:
        for name in failures:
            print(f"  failing: {name}")

    summary = {
        "probe": "a05_dispatch",
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "providers": registry.provider_ids(),
    }
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
