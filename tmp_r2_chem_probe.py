"""Read-only helper for r2 chemistry review: precedents + MS by qid or keyword."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")


def show_qids(qids, ms_len=260, stem_len=220):
    with eng.connect() as c:
        for qid in qids:
            row = c.execute(text("""
              SELECT q.id, q.number_label, q.marks,
                     substr(replace(q.stem_text,char(10),' '),1,:sl),
                     (SELECT group_concat(tn.code,'|') FROM question_taxonomy qt
                        JOIN taxonomy_node tn ON tn.id=qt.node_id
                       WHERE qt.question_id=q.id),
                     q.parent_id
                FROM question q WHERE q.id=:q"""), {'q': qid, 'sl': stem_len}).fetchone()
            if not row:
                print(f'Q {qid} NOT FOUND')
                continue
            print(f'== {row[0]} #{row[1]} {row[2]}mk tag={row[4] or "-"} parent={row[5]}')
            print(f'   {row[3]}')
            for ms in c.execute(text("""
              SELECT number_path, substr(replace(answer_text,char(10),' | '),1,:ml)
                FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""),
                    {'q': qid, 'ml': ms_len}):
                print(f'   MS[{ms[0]}] {ms[1]}')


def search_like(pattern, limit=25, stem_len=170, unit=None):
    with eng.connect() as c:
        rows = c.execute(text("""
          SELECT q.id, q.number_label, q.marks,
                 substr(replace(q.stem_text,char(10),' '),1,:sl),
                 (SELECT group_concat(tn.code,'|') FROM question_taxonomy qt
                    JOIN taxonomy_node tn ON tn.id=qt.node_id
                   WHERE qt.question_id=q.id)
            FROM question q
           WHERE q.stem_text LIKE :p
           ORDER BY q.id LIMIT :lim"""),
            {'p': f'%{pattern}%', 'sl': stem_len, 'lim': limit}).fetchall()
    for r in rows:
        tag = r[4] or '-'
        if unit and not any(t.startswith(unit) for t in tag.split('|')):
            continue
        print(f'{r[0]} #{r[1]} {r[2]}mk [{tag}] {r[3]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--like', default=None)
    ap.add_argument('--limit', type=int, default=25)
    ap.add_argument('--unit', default=None)
    ap.add_argument('--ms', type=int, default=260)
    ap.add_argument('--stem', type=int, default=220)
    ap.add_argument('qids', nargs='*', type=int)
    args = ap.parse_args()
    if args.like:
        search_like(args.like, args.limit, unit=args.unit)
    elif args.qids:
        show_qids(args.qids, ms_len=args.ms, stem_len=args.stem)
    else:
        print('usage: --like TEXT | qid...')


if __name__ == '__main__':
    main()
