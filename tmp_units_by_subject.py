import sys
sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from examdata.core import models as m
from examdata.tagging.corpus import load_points
from collections import defaultdict

eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)
pts = load_points(s)
by_subj = defaultdict(lambda: defaultdict(int))
for p in pts:
    by_subj[(p.subject or '').strip().lower()][p.unit_code] += 1
for subj in sorted(by_subj):
    units = sorted(by_subj[subj])
    print(f"{subj}: {len(units)} units -> {units}")
