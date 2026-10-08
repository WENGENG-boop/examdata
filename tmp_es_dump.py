import sqlite3, sys, json

DB = '.data/examdata.db'

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    args = sys.argv[1:]
    mode = args[0] if args else 'paper'
    cur.execute("""select tn.code from taxonomy_node tn where tn.code like 'WSP%'""")
    # question -> tag
    tagmap = {}
    cur.execute("""select qt.question_id, tn.code from question_taxonomy qt
                   join taxonomy_node tn on tn.id = qt.node_id
                   where tn.code like 'WSP%'""")
    for qid, code in cur.fetchall():
        tagmap.setdefault(qid, []).append(code)

    if mode == 'paper':
        paper_ids = [int(a) for a in args[1:]]
        for pid in paper_ids:
            cur.execute("""select d.title from paper p join document d on d.id=p.document_id where p.id=?""", (pid,))
            title = cur.fetchone()[0]
            print(f"===== paper {pid}: {title}")
            cur.execute("""select q.id, q.number_path, q.number_label, q.marks, q.kind, q.stem_text
                           from question q where q.paper_id=? order by q.display_order, q.id""", (pid,))
            for qid, np, nl, marks, kind, stem in cur.fetchall():
                tags = ','.join(tagmap.get(qid, [])) or '-'
                s = ' '.join((stem or '').split())
                if len(s) > 150:
                    s = s[:150] + '…'
                print(f"  {qid} [{np}] {marks}mk {kind} tag={tags} :: {s}")
    elif mode == 'qid':
        qids = [int(a) for a in args[1:]]
        qm = ','.join('?' * len(qids))
        cur.execute(f"""select q.id, q.paper_id, q.parent_id, q.number_path, q.marks, q.stem_text
                        from question q where q.id in ({qm})""", qids)
        rows = {r[0]: r for r in cur.fetchall()}
        for qid in qids:
            r = rows.get(qid)
            if not r:
                print(f"{qid}: NOT FOUND")
                continue
            _, pid, parent, np, marks, stem = r
            print(f"===== {qid} paper={pid} parent={parent} [{np}] {marks}mk tag={','.join(tagmap.get(qid,[])) or '-'}")
            s = ' '.join((stem or '').split())
            print("  " + (s[:400] + '…' if len(s) > 400 else s))
            if parent:
                cur.execute("""select q.id, q.number_path, q.marks, q.stem_text from question q where q.id=?""", (parent,))
                pr = cur.fetchone()
                if pr:
                    ps = ' '.join((pr[3] or '').split())
                    print(f"  PARENT {pr[0]} [{pr[1]}] {pr[2]}mk tag={','.join(tagmap.get(pr[0],[])) or '-'} :: " + (ps[:250] + '…' if len(ps) > 250 else ps))
            # children
            cur.execute("""select q.id, q.number_path, q.marks, q.stem_text from question q where q.parent_id=? order by q.display_order, q.id""", (qid,))
            for cid, cnp, cm, cs in cur.fetchall():
                cs = ' '.join((cs or '').split())
                print(f"    child {cid} [{cnp}] {cm}mk tag={','.join(tagmap.get(cid,[])) or '-'} :: " + (cs[:150] + '…' if len(cs) > 150 else cs))
    con.close()

main()
