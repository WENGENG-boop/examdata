import sqlite3, re, json
con = sqlite3.connect('.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()

def norm(s): return re.sub(r'\s+', ' ', s or '').strip()

targets = [1351, 782, 2162, 2108, 1927, 889, 1197, 1572, 1327, 1402, 706, 2208]
for pid in targets:
    print("="*100)
    r = cur.execute("SELECT p.id, p.paper_no, p.document_id, p.marks_total, p.question_count, d.current_revision_id FROM paper p JOIN document d ON d.id=p.document_id WHERE p.id=?", (pid,)).fetchone()
    print(f"PAPER {pid} {r['paper_no']} doc={r['document_id']} marks={r['marks_total']} qcount={r['question_count']} rev={r['current_revision_id']}")
    rev = r['current_revision_id']
    if rev:
        sk = cur.execute("SELECT a.storage_key FROM document_revision dr JOIN artifact a ON a.id=dr.artifact_id WHERE dr.id=?", (rev,)).fetchone()
        if sk:
            print(f"  QP pdf: .data/artifacts/{sk['storage_key']}")
    rows = cur.execute("SELECT id,parent_id,kind,number_label,number_path,marks,display_order,stem_text FROM question WHERE paper_id=? ORDER BY display_order", (pid,)).fetchall()
    for rr in rows:
        stem = rr['stem_text'] or ''
        totals = re.findall(r'Total for Question (\d+)', stem)
        own = rr['number_path'] or ''
        m = re.match(r'^(\d+)', own)
        ownN = int(m.group(1)) if m else None
        other = [int(t) for t in totals if ownN and int(t)!=ownN]
        mark = ""
        if other:
            # position of first marker with M != own
            first_other_pos = None
            for t in re.finditer(r'Total for Question (\d+)', stem):
                if int(t.group(1)) != ownN:
                    first_other_pos = t.start()/max(len(stem),1)
                    break
            mark = f" <<FLAG other={other} pos={first_other_pos:.2f}" if first_other_pos is not None else ""
        flat = re.sub(r'\s+',' ',stem)[:80]
        print(f"  id={rr['id']} par={rr['parent_id']} {rr['kind']:8s} {own:12s} m={str(rr['marks']):4s} ord={rr['display_order']:2d} len={len(stem):6d}{mark}  | {flat}")
con.close()
