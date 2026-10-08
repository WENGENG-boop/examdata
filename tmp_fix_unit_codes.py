"""Fix paper.attrs.unit_code for 3 papers blocking review-apply.

2092 -> WPS01, 2093 -> WPS02 (psychology, were 'QP')
1220 -> WMA13 (ial18-mathematics, was 'QUESTION')
"""
import datetime
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
LOG = ROOT / ".data" / "tagging" / "fixups-unit-codes.jsonl"

FIXES = {2092: "WPS01", 2093: "WPS02", 1220: "WMA13"}

engine = create_engine(f"sqlite:///{DB}")
rows = []
with Session(engine) as s:
    for pid, new_unit in FIXES.items():
        p = s.get(m.Paper, pid)
        if p is None:
            print(f"paper {pid}: NOT FOUND")
            continue
        doc = s.get(m.Document, p.document_id)
        before = (p.attrs or {}).get("unit_code")
        print(f"paper {pid} code={doc.paper_code!r} unit_code {before!r} -> {new_unit!r}")
        p.attrs = {**(p.attrs or {}), "unit_code": new_unit}
        rows.append(
            {
                "paper_id": pid,
                "paper_code": doc.paper_code,
                "before": before,
                "after": new_unit,
                "at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        )
    s.commit()
    print("--- readback after commit ---")
    for pid, new_unit in FIXES.items():
        p = s.get(m.Paper, pid)
        s.refresh(p)
        got = (p.attrs or {}).get("unit_code")
        print(f"paper {pid}: unit_code={got!r} ok={got == new_unit}")

with LOG.open("a", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("logged ->", LOG)
