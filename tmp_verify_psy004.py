"""Verify ial-psychology batch-004 landed correctly."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"

CHANGES = {
    64737: "WPS03-7.3.3", 64746: "WPS02-4.2.8", 64776: "WPS03-5.3.4",
    64778: "WPS03-5.3.4", 64779: "WPS03-5.3.1", 64781: "WPS03-5.3.4",
    64783: "WPS03-5.3.1", 64784: "WPS03-5.3.1", 64791: "WPS03-6.3.3",
    64796: "WPS03-6.3.3", 64809: "WPS03-7.3.3", 64818: "WPS02-3.1.3",
    64826: "WPS02-3.1.5", 64865: "WPS01-2.2.11", 64890: "WPS04-9.1.6",
    64897: "WPS03-5.3.4", 64898: "WPS03-5.3.4", 64899: "WPS03-5.3.4",
    64900: "WPS03-5.4.2", 64907: "WPS03-6.3.3", 64908: "WPS03-6.3.3",
    64910: "WPS03-5.4.2", 64918: "WPS03-7.3.3", 64919: "WPS03-7.3.3",
    64921: "WPS03-5.4.2", 64940: "WPS01-2.2.11", 64941: "WPS01-2.2.11",
    64987: "WPS01-1.4.1", 64989: "WPS01-1.2.3", 64990: "WPS01-1.2.3",
    65005: "WPS02-3.3.3", 65007: "WPS02-3.3.3", 65048: "WPS04-9.1.11",
    65049: "WPS04-9.1.11", 65060: "WPS04-9.3.1", 65067: "WPS01-1.2.5",
    65071: "WPS01-2.3.3", 65072: "WPS01-2.3.3", 65073: "WPS01-2.3.3",
    65094: "WPS04-9.1.13", 65101: "WPS04-9.1.11", 65103: "WPS04-9.1.11",
    65106: "WPS02-3.1.1", 65111: "WPS02-3.2.7", 65140: "WPS03-5.3.4",
    65144: "WPS03-5.3.1",
}

KEEPS = [64760, 64822, 64906, 64952, 64968, 65008, 65021, 65122, 65124]

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
