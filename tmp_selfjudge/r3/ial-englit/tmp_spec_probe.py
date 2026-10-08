import sqlite3, json, re
from pathlib import Path

# spec text
spec = json.loads(Path('.data/specs/parsed/ial-englit.json').read_text(encoding='utf-8'))
def walk(o, depth=0):
    if isinstance(o, dict):
        return {k: walk(v, depth+1) for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v, depth+1) for v in o]
    return o

# find WET03 entries
def find_wet03(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            find_wet03(v, path + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            find_wet03(v, path + f'[{i}]')
    else:
        if isinstance(o, str) and 'WET03' in o:
            print('HIT', path, ':', repr(o[:200]))

print('spec top-level keys:', list(spec.keys()) if isinstance(spec, dict) else type(spec))
find_wet03(spec)
