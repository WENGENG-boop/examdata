"""Convert `qid TOKEN  # comment` lines in ans files to two lines:
   # qid: comment
   qid TOKEN
so that tmp_selfjudge_ingest.parse_answers (requires exactly 2 tokens) accepts them.
Usage: python ans_comment_fix.py <dir-with-ans-files>
"""
import sys
from pathlib import Path

d = Path(sys.argv[1])
for f in sorted(d.glob('*.ans.txt')):
    out = []
    changed = 0
    for raw in f.read_text(encoding='utf-8').splitlines():
        line = raw.rstrip()
        if line.startswith('#'):
            out.append(line)
            continue
        if '#' in line:
            code, _, comment = line.partition('#')
            parts = code.split()
            if len(parts) == 2 and parts[0].isdigit():
                out.append(f'# {parts[0]}: {comment.strip()}')
                out.append(f'{parts[0]} {parts[1]}')
                changed += 1
                continue
        out.append(line)
    if changed:
        f.write_text('\n'.join(out) + '\n', encoding='utf-8')
    print(f'{f.name}: converted {changed} inline comments')
