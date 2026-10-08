"""Verify ial-psychology batch-007 landed correctly."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"

CHANGES = {
    65939: "WPS02-4.1.2", 65998: "WPS01-1.2.6", 65999: "WPS01-1.2.6",
    66006: "WPS01-2.2.11", 66030: "WPS04-9.1.2", 66036: "WPS04-9.1.11",
    66040: "WPS04-9.1.13", 66057: "WPS03-6.3.1", 66058: "WPS03-6.3.3",
    66059: "WPS03-6.3.3", 66067: "WPS03-7.3.1", 66068: "WPS03-7.3.3",
    66069: "WPS03-7.3.3", 66103: "WPS03-5.3.1", 66104: "WPS03-5.3.1",
    66106: "WPS03-5.3.1", 66111: "WPS03-6.3.1", 66112: "WPS03-6.3.3",
    66113: "WPS03-6.3.3", 66114: "WPS03-6.3.3", 66115: "WPS03-6.3.3",
    66122: "WPS03-7.3.1", 66123: "WPS03-7.3.3", 66126: "WPS03-7.3.3",
    66150: "WPS04-9.1.11", 66154: "WPS04-8.3.4", 66170: "WPS02-3.3.3",
    66180: "WPS02-4.1.4", 66203: "WPS02-3.1.5", 66214: "WPS02-4.2.1",
    66257: "WPS03-5.3.1", 66258: "WPS03-5.3.1", 66259: "WPS03-5.3.4",
    66262: "WPS03-5.4.1", 66268: "WPS03-6.3.3", 66270: "WPS03-6.3.4",
    66281: "WPS03-7.3.3", 66283: "WPS03-7.3.4",
}

KEEPS = {
    65977: {"WPS02-3.2.5", "WPS02-4.2.2"},
    66042: {"WPS04-9.3.4"},
    66196: {"WPS02-3.2.1"},
    66209: {"WPS02-4.1.2"},
    66241: {"WPS04-9.1.11"},
}

assert len(CHANGES) == 38 and len(KEEPS) == 5

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
    for qid, want in KEEPS.items():
        rows = rows_of(qid)
        codes = {r[1] for r in rows}
        allrev = all(r[0].reviewed for r in rows)
        ok = allrev and codes == want
        if not ok:
            kbad += 1
        print(qid, sorted(codes), "reviewed=", allrev, "ok=", ok)
    print(f"KEEPS all reviewed & unchanged: {len(KEEPS) - kbad}/{len(KEEPS)}")
