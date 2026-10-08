# -*- coding: utf-8 -*-
"""Final verification of subjects_edexcel.json (post fix-1 regeneration).

Recomputes from the OUTPUT JSON itself (not the evidence files):
  - material rows: main 1160 + variant 331 = 1491; dedup 1479; unique urls 1449;
    gated rows 370; gated unique urls 366  (must equal coverage.materials_merged)
  - n_records total + public/gated split; per-row public+gated==n_records
  - registry observed_count for the 9 entries
  - subjects with non-empty materials (incl. variants) = 112; main-only = 107;
    variant-only subjects = the 5 known slugs; variants non-empty = 17
  - integrated_items subjects = chemistry-2018, mathematics-2018
  - sample conclusion_zh (capped + live) printed for template inspection
"""
import json
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "examdata/src/examdata/materials/data/subjects_edexcel.json"

FAIL = []


def check(name, got, want):
    ok = got == want
    if not ok:
        FAIL.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")


def norm_url(raw):
    s = unquote(str(raw or "").strip()).lower()
    for scheme in ("https://qualifications.pearson.com", "http://qualifications.pearson.com"):
        if s.startswith(scheme):
            s = s[len(scheme):]
            break
    return s.split("#", 1)[0].split("?", 1)[0]


def main():
    d = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    subs = d["subjects"]
    cov = d["coverage"]

    # ---- 1. row counts ----
    # output rows carry no `slug` field; restore it (main & variant rows both
    # belong to the subject slug — matches build script add_rows(slug, ...))
    main_rows = []
    variant_rows = []
    for slug, s in subs.items():
        for r in s.get("materials") or []:
            main_rows.append((slug, r))
        for v in s.get("variants") or []:
            for r in v.get("materials") or []:
                variant_rows.append((slug, r))
    rows = main_rows + variant_rows

    check("main rows", len(main_rows), 1160)
    check("variant rows", len(variant_rows), 331)
    check("total rows", len(rows), 1491)

    seen = set()
    dedup = []
    for slug, r in rows:
        k = (slug, norm_url(r.get("url") or "") or str(r.get("title")))
        if k in seen:
            continue
        seen.add(k)
        dedup.append(r)

    check("rows_dedup", len(dedup), 1479)
    check("unique_urls", len({norm_url(r.get("url")) for r in dedup if r.get("url")}), 1449)
    check("gated_rows", sum(1 for r in dedup if r.get("gated")), 370)
    check(
        "gated_unique_urls",
        len({norm_url(r.get("url")) for r in dedup if r.get("gated") and r.get("url")}),
        366,
    )

    mm = cov["materials_merged"]
    check("coverage.materials_merged", mm, {
        "rows": 1491, "rows_dedup": 1479, "unique_urls": 1449,
        "gated_rows": 370, "gated_unique_urls": 366,
    })

    # ---- 2. n_records (main-only口径 = 40304 / 34192 / 6112) ----
    n_main = sum(s.get("n_records") or 0 for s in subs.values())
    n_var = sum((v.get("n_records") or 0) for s in subs.values() for v in s.get("variants") or [])
    print(f"n_records: main={n_main} variant={n_var} total={n_main + n_var}")
    p_main = sum(s.get("public_count") or 0 for s in subs.values())
    g_main = sum(s.get("gated_count") or 0 for s in subs.values())
    p_var = sum((v.get("public_count") or 0) for s in subs.values() for v in s.get("variants") or [])
    g_var = sum((v.get("gated_count") or 0) for s in subs.values() for v in s.get("variants") or [])
    print(f"public: main={p_main} variant={p_var} total={p_main + p_var}")
    print(f"gated:  main={g_main} variant={g_var} total={g_main + g_var}")
    check("n_records main total", n_main, 40304)
    check("public main total", p_main, 34192)
    check("gated main total", g_main, 6112)

    bad = []
    for slug, s in subs.items():
        if s.get("public_count") is not None and s.get("gated_count") is not None:
            if (s.get("public_count") or 0) + (s.get("gated_count") or 0) != (s.get("n_records") or 0):
                bad.append(slug)
        for i, v in enumerate(s.get("variants") or []):
            if (v.get("public_count") or 0) + (v.get("gated_count") or 0) != (v.get("n_records") or 0):
                bad.append(f"{slug}#v{i}")
    check("public+gated==n_records violations", bad, [])

    # ---- 3. registry observed_count ----
    reg = d["material_registry"]
    want = {
        "ial18_maths_formula_book": 1,
        "ial18_chemistry_data_booklet": 1,
        "al15_chemistry_data_booklet": 2,
        "chemistry_periodic_table": 1,
        "physics_data_formulae_list": 2,
        "statistics_formulae_tables": 4,
        "source_booklet_insert": 83,
        "pre_release_materials": 99,
        "gated_policy_note": 0,
    }
    for k, w in want.items():
        e = reg.get(k)
        if e is None:
            FAIL.append(f"registry missing {k}")
            print(f"[FAIL] registry missing {k}")
            continue
        check(f"registry[{k}].observed_count", e.get("observed_count"), w)

    # ---- 4. subjects with materials ----
    with_any = [s for s, v in subs.items() if (v.get("materials") or []) or any(
        (vv.get("materials") or []) for vv in v.get("variants") or [])]
    main_only = [s for s, v in subs.items() if (v.get("materials") or [])]
    variant_only = sorted(set(with_any) - set(main_only))
    variants_nonempty = sorted(
        s for s, v in subs.items() if any((vv.get("materials") or []) for vv in v.get("variants") or []))
    check("subjects with any material rows", len(with_any), 112)
    check("subjects with main material rows", len(main_only), 107)
    check("variant-only subjects", variant_only,
          ["gujarati-2018", "persian-2018", "portuguese-2018", "turkish-2018", "urdu-2009"])
    check("subjects with non-empty variant rows", len(variants_nonempty), 17)

    # ---- 5. integrated_items ----
    integ = sorted(s for s, v in subs.items() if v.get("integrated_items"))
    check("subjects with integrated_items", integ, ["chemistry-2018", "mathematics-2018"])

    # ---- 5b. source distribution / capped count ----
    from collections import Counter
    src = Counter(v.get("source") for v in subs.values())
    check("source distribution", dict(src), {
        "first_pass": 147, "recovery_dead_ok": 56, "recovery_live": 25,
        "capped_final": 3, "recovery_dead_gap": 2,
    })
    capped_slugs = sorted(s for s, v in subs.items() if v.get("source") == "capped_final")
    print("capped subjects:", capped_slugs)

    # ---- 6. conclusion samples ----
    print()
    for slug in ("mathematics-2018", "chemistry-2018"):
        s = subs.get(slug)
        if s:
            print(f"--- conclusion_zh [{slug}] ---")
            print(s.get("conclusion_zh"))
    # a capped subject and a live subject
    capped_slug = next(s for s, v in subs.items() if v.get("source") == "capped_final")
    print(f"--- conclusion_zh [capped: {capped_slug}] ---")
    print(subs[capped_slug].get("conclusion_zh"))
    live_slug = next(s for s, v in subs.items() if v.get("source") == "recovery_live")
    print(f"--- conclusion_zh [live: {live_slug}] ---")
    print(subs[live_slug].get("conclusion_zh"))

    print()
    print("FAILURES:", FAIL if FAIL else "none")


if __name__ == "__main__":
    main()
