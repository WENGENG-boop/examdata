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
# criteria bytes per unit = sum(len(code) + len(desc)) where desc = f'{name} [{hier}]'[:600]
crit = defaultdict(int)
npts = defaultdict(int)
for p in pts:
    key = ((p.subject or '').strip().lower(), p.unit_code)
    hier = ' > '.join(reversed(p.ancestors))
    desc = f'{p.name} [{hier}]'[:600]
    crit[key] += len(p.code) + len(desc) + 40
    npts[key] += 1
# question text estimate ~1800 chars max + 1500 context = ~3.4KB worst, ~1.5KB typical
for (subj, unit) in sorted(crit, key=lambda k: -crit[k])[:25]:
    c = crit[(subj, unit)]
    print(f"{subj:24s} {unit:10s} pts={npts[(subj,unit)]:3d} criteria≈{c//1024}KB -> chunk(90KB)={max(1, 90*1024//(c+3000))}")
