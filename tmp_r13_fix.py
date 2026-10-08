"""r13 fix: apply 32 adjudicated label corrections (28 new-question + 4 in-paper).

Input: tmp_r13_fix_plan.json  (qid, from, to, note)
  - delete all existing rows not in target; insert missing target rows
  - new/updated rows use source=ai-review / conf=1.0 / assigned_by=ai-review-v1 / reviewed=1
  - refuses to write on unknown code or from-drift (unless --allow-drift)

Default dry-run; --write commits and writes tmp_r13_fix_applied.json.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r13_fix.py [--write] [--allow-drift]
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
    ap.add_argument("--allow-drift", action="store_true")
    args = ap.parse_args()

    plan = json.loads((ROOT / "tmp_r13_fix_plan.json").read_text(encoding="utf-8"))
    fixes = plan["fixes"]
    print(f"plan: {len(fixes)} fixes")

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    try:
        node_by_code = {r.code: r.id for r in session.scalars(select(TaxonomyNode)).all()}
        needed = {c for it in fixes for c in it["to"]}
        needed |= {c for it in fixes for c in it["from"]}
        missing_codes = sorted(c for c in needed if c not in node_by_code)
        if missing_codes:
            print("FATAL: unknown codes:", missing_codes)
            sys.exit(1)

        errors: list[str] = []
        log: list[dict] = []

        for it in fixes:
            qid = it["qid"]
            want = set(it["to"])
            rows = list(session.scalars(
                select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == qid)
            ).all())
            got = {session.get(TaxonomyNode, r.node_id).code for r in rows}

            if got != set(it["from"]):
                msg = f"q{qid}: drift current={sorted(got)} from={sorted(it['from'])}"
                if args.allow_drift:
                    print(f"  note: {msg} (proceeding)")
                else:
                    errors.append(msg)
                    continue

            if got == want:
                all_reviewed = rows and all(
                    r.source == REVIEW_SOURCE and r.confidence == 1.0 and r.reviewed for r in rows
                )
                if all_reviewed:
                    print(f"[noop] q{qid} already at target: {sorted(want)}")
                    log.append({"qid": qid, "action": "noop", "codes": sorted(want)})
                    continue

            del_codes = sorted(got - want)
            ins_codes = sorted(want - got)
            keep_rows = [r for r in rows if session.get(TaxonomyNode, r.node_id).code in want]
            upg_rows = [
                r for r in keep_rows
                if not (r.source == REVIEW_SOURCE and r.confidence == 1.0 and r.reviewed)
            ]
            print(f"{'WROTE' if args.write else '[dry]'} q{qid} del {del_codes} ins {ins_codes} upgrade {len(upg_rows)} kept (was {sorted(got)} -> {sorted(want)})")
            if args.write:
                for r in rows:
                    if session.get(TaxonomyNode, r.node_id).code not in want:
                        session.delete(r)
                session.flush()
                for r in upg_rows:
                    r.source = REVIEW_SOURCE
                    r.confidence = 1.0
                    r.assigned_by = REVIEW_BY
                    r.reviewed = True
                for code in ins_codes:
                    session.add(QuestionTaxonomy(
                        question_id=qid,
                        node_id=node_by_code[code],
                        source=REVIEW_SOURCE,
                        confidence=1.0,
                        assigned_by=REVIEW_BY,
                        reviewed=True,
                    ))
            log.append({
                "qid": qid, "action": "fix", "deleted": del_codes, "inserted": ins_codes,
                "upgraded": len(upg_rows),
                "before": sorted(got), "after": sorted(want), "note": it.get("note", ""),
            })

        if errors:
            print("REFUSING to write: validation errors:")
            for e in errors:
                print("  ERROR", e)
            sys.exit(1)

        if args.write:
            session.commit()
            out = ROOT / "tmp_r13_fix_applied.json"
            out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"committed; log -> {out.name} ({len(log)} items)")
        else:
            print(f"dry-run ok: {len(fixes)} fixes, no errors")
    finally:
        session.close()


if __name__ == "__main__":
    main()
