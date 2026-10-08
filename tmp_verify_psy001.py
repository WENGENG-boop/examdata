"""Verify ial-psychology batch-001 landed correctly."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"

CHANGES = {
    61225: "WPS03-5.3.4", 61238: "WPS03-6.3.3", 61240: "WPS03-6.3.1",
    61250: "WPS03-7.3.3", 61251: "WPS03-7.3.3", 61252: "WPS03-7.3.1",
    61265: "WPS04-8.1.2", 61268: "WPS04-8.3.4", 61275: "WPS04-9.1.11",
    61319: "WPS01-1.2.6", 61322: "WPS01-1.2.6", 61328: "WPS01-2.2.6",
    61329: "WPS01-2.4.1", 61359: "WPS02-4.1.4", 61385: "WPS02-3.1.6",
    61395: "WPS02-4.2.5", 61396: "WPS02-4.2.5", 61397: "WPS02-4.2.5",
    61416: "WPS01-1.2.6", 61423: "WPS01-2.2.12", 61516: "WPS02-4.2.1",
    61581: "WPS04-9.1.11", 61582: "WPS04-8.3.4", 61592: "WPS04-9.1.11",
    61593: "WPS04-9.1.11", 61605: "WPS03-5.4.2", 61607: "WPS03-5.4.5",
    61611: "WPS03-6.3.1", 61612: "WPS03-5.4.2", 61620: "WPS03-6.3.1",
    61621: "WPS03-5.4.2", 61641: "WPS01-2.2.11", 61644: "WPS01-2.2.6",
    61770: "WPS02-4.2.5", 61771: "WPS02-4.2.5", 61777: "WPS02-4.1.3",
    61788: "WPS04-9.1.11", 61790: "WPS04-8.3.4",
}

KEEPS = [61371, 61372, 61389, 61392, 61408, 61409, 61503, 61509, 61530,
         61531, 61586, 61608, 61617, 61638, 61639, 61756, 61810]

engine = create_engine(f"sqlite:///{DB}")
with Session(engine) as s:
    def rows_of(qid):
        return s.execute(
            select(m.QuestionTaxonomy, m.TaxonomyNode.code)
            .join(m.TaxonomyNode, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
            .where(m.QuestionTaxonomy.question_id == qid)
            .order_by(m.TaxonomyNode.code)
        ).all()

    bad = 0
    for qid, code in CHANGES.items():
        rows = rows_of(qid)
        codes = [r[1] for r in rows]
        ok = codes == [code] and all(
            r[0].assigned_by == "ai-review-v1" and r[0].reviewed
            and abs((r[0].confidence or 0) - 1.0) < 1e-9 and r[0].source == "ai-review"
            for r in rows
        )
        if not ok:
            bad += 1
            print("BAD", qid, "expected", code, "got", codes,
                  [(r[0].assigned_by, r[0].reviewed, r[0].confidence, r[0].source) for r in rows])
    print(f"CHANGES verified: {len(CHANGES) - bad}/{len(CHANGES)}")

    print("--- KEEPS (print) ---")
    kbad = 0
    for qid in KEEPS:
        rows = rows_of(qid)
        codes = [r[1] for r in rows]
        allrev = all(r[0].reviewed for r in rows)
        if not allrev:
            kbad += 1
        print(qid, codes, "reviewed=", allrev)
    print(f"KEEPS all reviewed: {len(KEEPS) - kbad}/{len(KEEPS)}")
