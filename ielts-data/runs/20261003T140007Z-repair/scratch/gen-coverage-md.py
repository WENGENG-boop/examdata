import json, io, hashlib, os

base = r"C:/Users/weo/Desktop/api/ielts-data"
src = os.path.join(base, "manifests/rev-8b21015ab64bb73c/coverage.json")
dst = os.path.join(base, "manifests/rev-8b21015ab64bb73c/coverage.md")

with io.open(src, "rb") as f:
    raw = f.read()
sha = hashlib.sha256(raw).hexdigest()
d = json.loads(raw.decode("utf-8"))
s = d["summary"]

lines = []
w = lines.append

w("# IELTS coverage 全量汇总（coverage.md）")
w("")
w(f"- schema: `{d.get('schema')}` version: `{d.get('version')}`")
w(f"- generated_at_utc: {s.get('generated_at_utc')}")
w(f"- run_id: {d.get('run_id')}")
w(f"- data_dir: {d.get('data_dir')}")
w(f"- dataset_revision: {d.get('dataset_revision')}")
w(f"- source JSON: manifests/rev-8b21015ab64bb73c/coverage.json sha256={sha}")
w(f"- warnings: {d.get('warnings')}")
w("")
w("## 单元状态（370 units = 21 books）")
w("")
w("| status | count |")
w("|---|---|")
for k in ["complete", "partial", "source_missing", "not_extracted", "unverified"]:
    w(f"| {k} | {s['unit_status'].get(k, 0)} |")
w("")
w(f"- units: {s['units']} ｜ books: {s['books']}")
w(f"- fully_complete_units: {s['fully_complete_units']}")
w(f"- units_with_audio_verified: {s['units_with_audio_verified']}")
w(f"- units_with_alignment_complete: {s['units_with_alignment_complete']}")
w(f"- books_pdf_complete: {', '.join(str(x) for x in s['books_pdf_complete'])}")
w("")
w("## by skill/variant")
w("")
w("| key | units | fully_complete | audio_verified | alignment_complete |")
w("|---|---|---|---|---|")
for k, v in s["by_skill"].items():
    w(f"| {k} | {v['units']} | {v['fully_complete']} | {v['audio_verified_units']} | {v['alignment_complete_units']} |")
w("")
w("## by book")
w("")
w("| book | units | fully_complete | pdf_complete |")
w("|---|---|---|---|")
for b in s["by_book"]:
    w(f"| {b['book']} | {b['units']} | {b['fully_complete']} | {str(b['pdf_complete']).lower()} |")
w("")
w("## 全量单元明细（370 units）")
w("")
w("| unit_id | status | status_reasons | expected | observed | missing | extra | source |")
w("|---|---|---|---|---|---|---|---|")
units = []
for b in d["books"]:
    for u in b.get("units", []):
        units.append(u)
units.sort(key=lambda u: (u["book"], str(u["test"]), u["skill"], u["variant"]))
for u in units:
    num = u.get("numbers", {})
    exp = num.get("expected", [])
    obs = num.get("observed", [])
    miss = num.get("missing", [])
    extra = num.get("extra", [])
    reasons = "; ".join(u.get("status_reasons", []) or [])
    src = (u.get("source") or {}).get("kind", "")
    w(f"| {u['unit_id']} | {u['status']} | {reasons} | {len(exp)} | {len(obs)} | {len(miss)} | {len(extra)} | {src} |")
w("")
w(f"- total units rendered: {len(units)}")
w("- 生成方式: ielts-data/runs/20261003T140007Z-repair/scratch/gen-coverage-md.py（读取 manifests/rev-8b21015ab64bb73c/coverage.json 原样渲染，不改数值）")
w("")

with io.open(dst, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))

print("wrote", dst, len("\n".join(lines)), "chars; units:", len(units))
