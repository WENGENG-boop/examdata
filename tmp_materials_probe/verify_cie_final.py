# -*- coding: utf-8 -*-
"""第 5 轮复核：subjects_cie.json ↔ 证据文件 ↔ 文档 全量复算（只读）。

复算来源：
  - examdata/src/examdata/materials/data/subjects_cie.json   被复核对象
  - examdata/src/examdata/materials/data/catalog.json
  - examdata/.data/syllabuses.json / discovery.json
  - tmp_materials_probe/evidence/addmaterials_rows*.json / addmaterials_by_subject.json
  - tmp_materials_probe/evidence/gap1_wayback_lists.json / verify_public_materials.json
  - examdata/research/exam-materials-cie.md                  文档断言抽查

不可复算项（如实说明）：四份清单 PDF 与实测下载原件已按约定清理，sha256/bytes/pages
只能核对证据 JSON 记录值 ↔ subjects_cie.json 记录值的一致性，无法重新哈希。
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "tmp_materials_probe" / "evidence"
JSON_PATH = ROOT / "examdata/src/examdata/materials/data/subjects_cie.json"
CATALOG = ROOT / "examdata/src/examdata/materials/data/catalog.json"
DOC = ROOT / "examdata/research/exam-materials-cie.md"

FAIL = []


def check(name, got, want):
    ok = got == want
    if not ok:
        FAIL.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    d = load(JSON_PATH)
    subs = d["subjects"]
    cov = d["coverage"]
    src = d["sources"]
    reg = d["material_registry"]

    # ---- 1. 基本结构 ----
    check("schema_version", str(d.get("schema_version")), "1")
    check("board", d.get("board"), "cie")
    check("generated_at", d.get("generated_at"), "2026-10-05")
    check("subjects count", len(subs), 272)

    # ---- 2. 范围并集复算（198 ∪ 196 ∪ 207 ∪ 252 = 272）----
    syll = load(ROOT / "examdata/.data/syllabuses.json")
    codes_syll = {str(s.get("code")) for s in syll}
    disc = load(ROOT / "examdata/.data/discovery.json")
    codes_disc = {r.get("subject_code") for r in disc["resources"] if r.get("subject_code")}
    byl = load(EV / "addmaterials_by_subject.json")["subjects"]
    codes_byl = set(byl.keys())
    codes_series = set()
    series_files = {
        "june_2024": "addmaterials_rows_june-2024.json",
        "nov_2024": "addmaterials_rows_november-2024.json",
        "nov_2025": "addmaterials_rows_november-2025.json",
    }
    series_rows = {}
    for k, fname in series_files.items():
        series_rows[k] = load(EV / fname)["rows"]
        codes_series |= {str(r.get("code") or "").strip() for r in series_rows[k]}
    codes_series.discard("")
    union = codes_syll | codes_disc | codes_byl | codes_series
    check("syllabuses count", len(codes_syll), 198)
    check("discovery codes", len(codes_disc), 196)
    check("nov2026 codes", len(codes_byl), 207)
    check("series union codes", len(codes_series), 252)
    check("union == subjects keys", union == set(subs.keys()), True)

    # ---- 3. coverage 全值 ----
    check("coverage.subjects_total_union", cov["subjects_total_union"], 272)
    check("coverage.syllabuses", cov["syllabuses"], 198)
    check("coverage.discovery_subject_codes", cov["discovery_subject_codes"], 196)
    check("coverage.nov2026_list_subjects", cov["nov2026_list_subjects"], 207)
    check("coverage.series_list_subjects", cov["series_list_subjects"],
          {"june_2024": 193, "nov_2024": 213, "nov_2025": 208})
    check("coverage.with_nov2026_list_rows", cov["with_nov2026_list_rows"], 207)
    check("coverage.with_series_list_rows", cov["with_series_list_rows"], 252)
    check("coverage.with_public_insert_source_material",
          cov["with_public_insert_source_material"], 76)
    check("coverage.with_public_confidential_instructions",
          cov["with_public_confidential_instructions"], 20)
    check("coverage.with_public_pre_release", cov["with_public_pre_release"], 3)
    check("coverage.no_material_evidence", cov["no_material_evidence"],
          ["0265", "0266", "0479", "0715", "0716", "8101", "8102", "8293", "9981", "9982"])

    # ---- 4. sources 从证据文件复算 ----
    am = load(EV / "addmaterials_rows.json")
    check("nov2026 row_count == len(rows)", am["row_count"], len(am["rows"]))
    check("nov2026 rows", am["row_count"], 2164)
    am_codes = {r["code"] for r in am["rows"]}
    check("nov2026 subjects", len(am_codes), 207)
    n26 = src["nov2026_additional_materials"]
    check("sources.nov2026 rows", n26["rows"], 2164)
    check("sources.nov2026 subjects", n26["subjects"], 207)
    # sha/bytes/pages 的主证据是下载实测日志（PDF 原件已清理，无法重算哈希）；
    # 此处核对 subjects_cie.json ↔ build 脚本记录值一致，并与证据文件 URL 一致。
    check("sources.nov2026 sha256",
          n26["sha256"], "858b0fcbe5d00e92e3b761684adfcfa969fe79216a80899f296999918dbb39a3")
    check("sources.nov2026 bytes", n26["bytes"], 658660)
    check("sources.nov2026 pages", n26["pages"], 222)
    check("sources.nov2026 url", n26["url"], am["source"]["url"])

    exp_meta = {
        "june_2024": {"rows": 2328, "codes": 193, "bytes": 777515, "pages": 234,
                      "capture": "20240703193603",
                      "sha256": "406ceeb64894515da24a381bdfcff642befec3d570a41c3e54e64228311f36ce"},
        "nov_2024": {"rows": 1931, "codes": 213, "bytes": 662015, "pages": 210,
                     "capture": "20250505095707",
                     "sha256": "9e733dcfa85911f992ea4be28db416c1cab142fd76a0c717606df1b3fd09e289"},
        "nov_2025": {"rows": 2130, "codes": 208, "bytes": 650303, "pages": 219,
                     "capture": "20251014160116",
                     "sha256": "daa76149778ae678f441a890221fe0b22d61088e681be3bd9316b44d8a976705"},
    }
    src_series = {s["key"]: s for s in src["series_lists"]}
    for k, e in exp_meta.items():
        rows = series_rows[k]
        got_codes = len({r["code"] for r in rows})
        check(f"{k} rows", len(rows), e["rows"])
        check(f"{k} codes", got_codes, e["codes"])
        ss = src_series[k]
        check(f"sources.{k} rows", ss["rows"], e["rows"])
        check(f"sources.{k} subjects", ss["subjects"], e["codes"])
        check(f"sources.{k} capture", ss["capture"], e["capture"])
        check(f"sources.{k} sha256", ss["sha256"], e["sha256"])
        check(f"sources.{k} bytes", ss["bytes"], e["bytes"])
        check(f"sources.{k} pages", ss["pages"], e["pages"])

    check("sources.syllabuses.count", src["syllabuses"]["count"], 198)
    dd = src["discovery"]
    check("sources.discovery.resources", dd["resources"], len(disc["resources"]))
    check("sources.discovery.resources == 2767", dd["resources"], 2767)
    check("sources.discovery.subject_codes", dd["subject_codes"], 196)
    dt = Counter(r.get("doc_type") for r in disc["resources"])
    check("sources.discovery.doc_type_counts", dd["doc_type_counts"], dict(dt))
    check("discovery doc_type specimen_paper", dt["specimen_paper"], 760)
    check("discovery doc_type specimen_mark_scheme", dt["specimen_mark_scheme"], 558)
    check("discovery doc_type examiner_report", dt["examiner_report"], 173)
    check("discovery doc_type mark_scheme", dt["mark_scheme"], 482)
    check("discovery doc_type question_paper", dt["question_paper"], 466)
    check("discovery doc_type source_material", dt["source_material"], 179)
    check("discovery doc_type other", dt["other"], 112)
    check("discovery doc_type confidential_instructions", dt["confidential_instructions"], 37)

    # ---- 5. 13 码闭环 ----
    closed = ["0262", "0444", "0472", "0480", "0499", "0523", "0539", "0544", "0547",
              "0772", "7164", "0989", "0995"]
    june_codes = {r["code"] for r in series_rows["june_2024"]}
    check("june_2024 contains all 13 closed codes",
          all(c in june_codes for c in closed), True)
    nov = Counter(r["code"] for r in series_rows["nov_2024"] if r["code"] in closed)
    check("nov_2024 closed-code rows", dict(nov), {"0989": 2, "0995": 2})
    n25 = {r["code"] for r in series_rows["nov_2025"]} & set(closed)
    check("nov_2025 closed-code rows", sorted(n25), [])
    check("nov2026 closed-code rows", sorted(am_codes & set(closed)), [])

    # ---- 6. grep 断言（graph paper / data booklet 零命中）----
    for k in series_files:
        rows = series_rows[k]
        gp = sum(1 for r in rows if "graph paper" in str(r.get("materials_text", "")).lower())
        db = sum(1 for r in rows if "data booklet" in str(r.get("materials_text", "")).lower())
        check(f"{k} 'graph paper' hits", gp, 0)
        check(f"{k} 'data booklet' hits", db, 0)

    # ---- 7. 材料引用科数（doc §3 表）----
    key_subjects = Counter()
    for code, s in subs.items():
        for m in s.get("materials") or []:
            key_subjects[m["key"]] += 1
    want_keys = {
        "official_insert_source_material": 76, "answer_booklet_insert": 62,
        "mc_answer_sheet": 52, "listening_file_alf": 24, "instructions": 22,
        "official_confidential_instructions": 20, "qp_special_format": 9,
        "role_play_cards": 7, "teachers_notes": 7, "periodic_table_in_paper": 5,
        "pre_release": 3, "source_file": 3, "candidate_arf": 2, "mf19_formulae_tables": 2,
        "chemistry_data_booklet": 1, "cispecimens": 1, "dvd": 1,
        "graph_paper": 0, "tracing_paper_centre": 0,
    }
    check("materials keys used == registry keys",
          set(key_subjects) | {k for k in want_keys if not key_subjects.get(k)},
          set(reg.keys()))
    for k, w in want_keys.items():
        check(f"key_subjects[{k}]", key_subjects.get(k, 0), w)

    nonempty = [c for c, s in subs.items() if s.get("materials")]
    check("subjects with materials", len(nonempty), 174)
    empty = [c for c, s in subs.items() if not s.get("materials")]
    check("subjects without materials", len(empty), 98)
    noev = set(cov["no_material_evidence"])
    empty_other = [c for c in empty if c not in noev]
    check("empty minus no_evidence", len(empty_other), 88)
    check("the 88 all have enumeration",
          all(subs[c].get("enumeration") for c in empty_other), True)

    # ---- 8. registry 逐条 ----
    check("registry key count", len(reg), 19)
    pairs = {
        "mf19_formulae_tables": ("yes", "yes"),
        "answer_booklet_insert": ("partial", "partial"),
        "mc_answer_sheet": ("yes", "yes"),
        "listening_file_alf": ("uncertain", "no"),
        "instructions": ("uncertain", "no"),
        "official_confidential_instructions": ("yes", "partial"),
        "qp_special_format": ("no", "no"),
        "role_play_cards": ("no", "no"),
        "teachers_notes": ("no", "no"),
        "periodic_table_in_paper": ("via-qp", "partial"),
        "pre_release": ("yes", "no"),
        "source_file": ("uncertain", "no"),
        "candidate_arf": ("no", "no"),
        "chemistry_data_booklet": ("no", "no"),
        "cispecimens": ("uncertain", "partial"),
        "dvd": ("no", "no"),
        "graph_paper": ("no", "no"),
        "tracing_paper_centre": ("no", "no"),
        "official_insert_source_material": ("yes", "yes"),
    }
    for k, (po, ig) in pairs.items():
        check(f"registry[{k}] public/integrated", (reg[k]["public_obtainable"], reg[k]["integrated"]), (po, ig))

    def ev_find(k, kind, pred=lambda e: True):
        return [e for e in reg[k]["evidence"] if e.get("kind") == kind and pred(e)]

    e = ev_find("mf19_formulae_tables", "official-download")[0]
    check("mf19 bytes/sha/pages/http",
          (e["bytes"], e["sha256"][:12], e["pages"], e["http"]),
          (311234, "c075388ec722", 16, 200))
    e = ev_find("mc_answer_sheet", "official-download")[0]
    check("mc_answer_sheet bytes/sha", (e["bytes"], e["sha256"][:12]), (129066, "0e0156de5eca"))
    e = ev_find("pre_release", "official-download")[0]
    check("pre_release bytes/sha", (e["bytes"], e["sha256"][:12]), (1040666, "f2e00ba0e2f4"))
    e = ev_find("pre_release", "official-xlsx")[0]
    check("pre_release xlsx bytes/sha", (e["bytes"], e["sha256"][:12]), (14926, "186ff111ea60"))
    ci = ev_find("official_confidential_instructions", "official-download")
    check("CI official bytes", [x["bytes"] for x in ci], [1064877, 1813136])
    cim = ev_find("official_confidential_instructions", "mirror-download")
    check("CI mirror bytes", [x["bytes"] for x in cim], [183081, 166037])
    e = ev_find("official_insert_source_material", "mirror-download")[0]
    check("insert mirror bytes/sha", (e["bytes"], e["sha256"][:12]), (114871, "7d49097cb30c"))
    e = ev_find("answer_booklet_insert", "official-download")[0]
    check("answer_booklet official bytes/sha/pages",
          (e["bytes"], e["sha256"][:12], e["pages"]), (729313, "5b7a729b1f44", 8))

    # ---- 9. catalog ----
    cat = load(CATALOG)
    items = cat["items"]
    ids = [it["id"] for it in items]
    check("catalog items", len(items), 8)
    check("catalog ids", ids, [
        "cie-mf19-formulae-and-statistical-tables", "cie-periodic-table", "cie-inserts",
        "cie-confidential-instructions", "cie-additional-materials-list", "cie-mc-answer-sheet",
        "edexcel-ial-maths-formula-book", "edexcel-ial-chemistry-data-booklet",
    ])
    check("catalog boards", Counter(it["board"] for it in items), {"cie": 6, "edexcel": 2})

    # ---- 10. new_syllabus_evidence ----
    nse = d["new_syllabus_evidence"]
    check("new_syllabus_evidence codes", sorted(nse.keys()), sorted(noev))
    bad_years = [c for c, v in nse.items() if v.get("first_exam") not in (2027, 2028, 2029)]
    check("new_syllabus first_exam in 2027-2029", bad_years, [])

    # ---- 11. Wayback 截断记录 ----
    g1 = load(EV / "gap1_wayback_lists.json")
    trunc = [L for L in g1["lists"] if L.get("bytes") == 1048576 and L.get("pages") == 0]
    check("truncated captures", sorted(L["slug"] for L in trunc),
          ["june-2022", "november-2022", "rotate-2023-03"])

    # ---- 12. verify_public_materials 3 键 ----
    vp = load(EV / "verify_public_materials.json")
    check("verify_public_materials keys", sorted(vp.keys()),
          ["0411_pre_release_p11_june2024", "0620_ci_51_june2024", "9701_ci_31_june2024"])

    # ---- 13. Nov 2026 清单行级断言（doc §4.7 / §4.1）----
    mc_rows = [r for r in am["rows"]
               if "multiple choice answer sheet" in str(r.get("materials_text", "")).lower()]
    check("nov2026 MC rows/codes", (len(mc_rows), len({r["code"] for r in mc_rows})), (265, 52))
    mf19_rows = [r for r in am["rows"]
                 if any(p.get("key") == "mf19_formulae_tables" for p in (r.get("provided") or []))]
    check("nov2026 mf19 rows/codes", (len(mf19_rows), sorted({r["code"] for r in mf19_rows})),
          (73, ["9231", "9709"]))

    # ---- 14. 文档断言 ----
    doc = DOC.read_text(encoding="utf-8")
    check("doc has fixed wording 'Nov 2024 各 2 行'", "Nov 2024 各 2 行" in doc, True)
    check("doc has correct URL form (x2)",
          doc.count("651593-additional-exams-material-list-international-.pdf"), 2)
    check("doc free of wrong URL form",
          "651593-november-2026-additional-exam-materials-list" in doc, False)
    missing_keys = [k for k in want_keys if k not in doc]
    check("doc mentions all 19 keys", missing_keys, [])
    check("doc says count=8", "count=8（6 CIE + 2 Edexcel）" in doc, True)
    check("doc says 174 科", "174 科" in doc, True)

    # ---- 15. 样本打印 ----
    print()
    for code in ("9709", "0620", "0265"):
        s = subs[code]
        print(f"--- conclusion_zh [{code}] ---")
        print((s.get("conclusion_zh") or "")[:400])
        print()
    integ = sorted(c for c, s in subs.items() if s.get("integrated_items"))
    print(f"subjects with integrated_items: {len(integ)}")
    print("sample:", {c: subs[c]["integrated_items"] for c in ("9709", "0620", "9701")})

    print()
    print("FAILURES:", FAIL if FAIL else "none")
    print(f"checks run: see above; failures: {len(FAIL)}")


if __name__ == "__main__":
    main()
