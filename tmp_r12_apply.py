"""r12 apply: KEEP/FIX for the 49 adjudicated low-conf questions.

Input: tmp_r12_verdicts.json
  keep: upgrade existing rows in place -> source=ai-review / conf=1.0 /
        assigned_by=ai-review-v1 / reviewed=True (node set must match verdict)
  fix : delete ALL existing rows, insert one ai-review row per target node

Default dry-run; --write commits and writes tmp_r12_applied.json.
Refuses to write if any validation error (unknown code, keep-drift, missing rows).

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r12_apply.py [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from examdata.core.db import (  # noqa: E402
    enable_immediate_writes,
    get_session_factory,
    init_db,
)
from examdata.core.models import QuestionTaxonomy, TaxonomyNode  # noqa: E402
from sqlalchemy import select  # noqa: E402

REVIEW_SOURCE = "ai-review"
REVIEW_BY = "ai-review-v1"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    verdicts = json.loads((ROOT / "tmp_r12_verdicts.json").read_text(encoding="utf-8"))
    keeps = verdicts["keep"]
    fixes = verdicts["fix"]
    print(f"verdicts: keep={len(keeps)} fix={len(fixes)}")

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    try:
        node_by_code = {
            r.code: r.id
            for r in session.scalars(select(TaxonomyNode)).all()
        }
        needed = {c for it in keeps for c in it["nodes"]}
        needed |= {c for it in fixes for c in it["to"]}
        missing_codes = sorted(c for c in needed if c not in node_by_code)
        if missing_codes:
            print("FATAL: unknown codes:", missing_codes)
            sys.exit(1)

        errors: list[str] = []
        log: list[dict] = []

        def rows_of(qid: int):
            return list(session.scalars(
                select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == qid)
            ).all())

        # ---- KEEP: upgrade in place ----
        for it in keeps:
            qid = it["qid"]
            want = set(it["nodes"])
            rows = rows_of(qid)
            got = {session.get(TaxonomyNode, r.node_id).code for r in rows}
            if got != want:
                errors.append(f"KEEP q{qid}: node set drift got={sorted(got)} want={sorted(want)}")
                continue
            all_reviewed = all(
                r.source == REVIEW_SOURCE and r.confidence == 1.0 and r.reviewed for r in rows
            )
            if all_reviewed:
                print(f"[noop] KEEP q{qid} already ai-review: {sorted(want)}")
                log.append({"qid": qid, "action": "keep-noop", "codes": sorted(want)})
                continue
            print(f"{'WROTE' if args.write else '[dry]'} KEEP q{qid} upgrade {len(rows)} row(s) -> {sorted(want)}")
            if args.write:
                for r in rows:
                    r.source = REVIEW_SOURCE
                    r.confidence = 1.0
                    r.assigned_by = REVIEW_BY
                    r.reviewed = True
            log.append({"qid": qid, "action": "keep-upgrade", "n_rows": len(rows), "codes": sorted(want)})

        # ---- FIX: delete all, insert target ----
        for it in fixes:
            qid = it["qid"]
            to = it["to"]
            want = set(to)
            rows = rows_of(qid)
            got = {session.get(TaxonomyNode, r.node_id).code for r in rows}
            all_reviewed = rows and all(
                r.source == REVIEW_SOURCE and r.confidence == 1.0 and r.reviewed for r in rows
            )
            if got == want and all_reviewed:
                print(f"[noop] FIX q{qid} already at target: {sorted(want)}")
                log.append({"qid": qid, "action": "fix-noop", "codes": sorted(want)})
                continue
            if got != set(it["from"]):
                print(f"  note: FIX q{qid} current={sorted(got)} != from={sorted(it['from'])} (proceeding)")
            print(f"{'WROTE' if args.write else '[dry]'} FIX q{qid} del {sorted(got)} -> {to}")
            if args.write:
                for r in rows:
                    session.delete(r)
                session.flush()
                for code in to:
                    session.add(QuestionTaxonomy(
                        question_id=qid,
                        node_id=node_by_code[code],
                        source=REVIEW_SOURCE,
                        confidence=1.0,
                        assigned_by=REVIEW_BY,
                        reviewed=True,
                    ))
            log.append({
                "qid": qid, "action": "fix-delete-insert",
                "deleted": sorted(got), "inserted": to,
            })

        if errors:
            print("REFUSING to write: validation errors:")
            for e in errors:
                print("  ERROR", e)
            sys.exit(1)

        if args.write:
            session.commit()
            out = ROOT / "tmp_r12_applied.json"
            out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"committed; log -> {out.name}")
        else:
            print(f"dry-run ok: keep={len(keeps)} fix={len(fixes)} no errors")
    finally:
        session.close()


if __name__ == "__main__":
    main()
