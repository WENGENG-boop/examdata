import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parents[2]
engine = create_engine(f'sqlite:///{ROOT / ".data" / "examdata.db"}')
with Session(engine) as s:
    pts = load_points(s)
    for unit in ('WMA13',):
        for p in pts:
            if (p.subject or '').strip().lower() != 'ial18-mathematics' or p.unit_code != unit:
                continue
            text = re.sub(r'\s+', ' ', p.text or '')
            print(f'--- {p.code} ---')
            print(text[:600])
            print()
