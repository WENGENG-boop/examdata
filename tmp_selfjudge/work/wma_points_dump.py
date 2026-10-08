import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parents[2]
DB_URL = f'sqlite:///{ROOT / ".data" / "examdata.db"}'
engine = create_engine(DB_URL)
with Session(engine) as s:
    pts = load_points(s)
    for unit in ('WMA13', 'WMA14'):
        print(f'===== {unit} =====')
        for p in pts:
            if (p.subject or '').strip().lower() != 'ial18-mathematics':
                continue
            if p.unit_code != unit:
                continue
            name = re.sub(r'\s+', ' ', p.name or '')
            print(f'{p.code}\t{name[:180]}')
