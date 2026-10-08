"""从当前 63 份索引 + papers.json + verification.jsonl 重算统计（只读，不联网）。

输出 deliverables/stats-current.json。所有数字均为本次实测。
"""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
BATCH = HERE.parents[1]
OUT = HERE / "deliverables"
TZ = timezone(timedelta(hours=8))
now = datetime.now(TZ).isoformat(timespec="seconds")

papers = json.loads((BATCH / "papers.json").read_text(encoding="utf-8"))
summary = json.loads((BATCH / "summary.json").read_text(encoding="utf-8"))
ck = json.loads((BATCH / "checkpoint.json").read_text(encoding="utf-8"))

INDEXED = {k: v for k, v in papers.items()
           if (BATCH / "indexes" / k.split("/")[0] /
               f"{k.split('/')[1]}-{k.split('/')[2]}-{k.split('/')[3]}" / "cie-index.json").is_file()}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- verification.jsonl ----
ver_records = []
vpath = BATCH / "verification.jsonl"
if vpath.is_file():
    for line in vpath.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ver_records.append(json.loads(line))

ver_by_key_sha = defaultdict(int)
ver_by_key_nosha = defaultdict(int)
for r in ver_records:
    k = r.get("key")
    if r.get("index_sha256"):
        ver_by_key_sha[(k, r["index_sha256"])] += 1
    else:
        ver_by_key_nosha[k] += 1

# ---- per-volume scan ----
volumes = []
tot_q = tot_qp_reg = tot_ms_reg = 0
empty_qp = empty_ms = uncertain_true = schema_bad = 0
for key, entry in sorted(INDEXED.items()):
    subj, year, season, paper = key.split("/")
    ip = BATCH / "indexes" / subj / f"{year}-{season}-{paper}" / "cie-index.json"
    idx = json.loads(ip.read_text(encoding="utf-8"))
    isha = sha256(ip)
    qs = idx.get("questions") or []
    eq = em = unc = 0
    qpr = msr = 0
    for q in qs:
        if not (q.get("qp") or []):
            eq += 1
        if not (q.get("ms") or []):
            em += 1
        if q.get("uncertain") is True:
            unc += 1
        qpr += len(q.get("qp") or [])
        msr += len(q.get("ms") or [])
    ok_schema = (idx.get("coordinate_system") == "unrotated_pdf_points_top_left"
                 and idx.get("page_base") == 1)
    if not ok_schema:
        schema_bad += 1
    tot_q += len(qs); tot_qp_reg += qpr; tot_ms_reg += msr
    empty_qp += eq; empty_ms += em; uncertain_true += unc
    bound = ver_by_key_sha.get((key, isha), 0)
    volumes.append({
        "key": key,
        "stage": entry.get("stage"),
        "question_count": len(qs),
        "qp_regions": qpr,
        "ms_regions": msr,
        "empty_qp": eq,
        "empty_ms": em,
        "uncertain_true": unc,
        "index_sha256": isha,
        "entry_index_sha256": entry.get("index_sha256"),
        "sha_matches_entry": isha == entry.get("index_sha256"),
        "verification_records_bound_to_current_sha": bound,
        "verification_records_total": sum(v for (kk, _), v in ver_by_key_sha.items() if kk == key) + ver_by_key_nosha.get(key, 0),
    })

doc = {
    "generated_at": now,
    "source": "本次实测（重读 63 份索引 + papers.json + verification.jsonl + checkpoint.json）",
    "papers_total": len(papers),
    "stage_counts": dict(Counter(v.get("stage") for v in papers.values())),
    "indexed_volumes": len(INDEXED),
    "indexed_subjects": len({k.split("/")[0] for k in INDEXED}),
    "questions_total": tot_q,
    "qp_regions_total": tot_qp_reg,
    "ms_regions_total": tot_ms_reg,
    "empty_qp_questions": empty_qp,
    "empty_ms_questions": empty_ms,
    "uncertain_true_questions": uncertain_true,
    "schema_declaration_bad": schema_bad,
    "verification_records_total": len(ver_records),
    "verification_records_with_sha": sum(1 for r in ver_records if r.get("index_sha256")),
    "verification_records_no_sha": sum(1 for r in ver_records if not r.get("index_sha256")),
    "coverage": {
        "subject_universe": summary.get("subject_universe"),
        "catalogue_cells": summary.get("catalogue_cells"),
        "checkpoint_totals": ck.get("totals"),
    },
    "volumes": volumes,
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "stats-current.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps({k: doc[k] for k in (
    "papers_total", "stage_counts", "indexed_volumes", "indexed_subjects",
    "questions_total", "qp_regions_total", "ms_regions_total",
    "empty_qp_questions", "empty_ms_questions", "uncertain_true_questions",
    "schema_declaration_bad", "verification_records_total",
    "verification_records_with_sha", "verification_records_no_sha")}, ensure_ascii=False, indent=2))
