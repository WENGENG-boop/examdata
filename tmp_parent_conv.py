import sqlite3
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
# all geo parents with children
parents = list(c.execute("""
select distinct q.parent_id from question q
join paper p on p.id=q.paper_id join document d on d.id=p.document_id join subject s on s.id=d.subject_id
where s.slug='ial-geography' and q.parent_id is not null"""))
parents = [r[0] for r in parents]
print("parents with children:", len(parents))
def labs(qid):
    return [r[0].split('-')[-1] for r in c.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=? order by tn.code", (qid,))]
same = 0; diff = 0
examples = []
for pid in parents:
    pl = labs(pid)
    kids = list(c.execute("select id from question where parent_id=? order by id", (pid,)))
    kl = [labs(k[0]) for k in kids]
    flat = [x for sub in kl for x in sub]
    if len(pl)==1 and pl[0] in flat and len(set(flat))==1 and set(flat)==set(pl):
        same += 1
    else:
        diff += 1
        if len(examples) < 25:
            examples.append((pid, pl, [(kids[i][0], kl[i]) for i in range(len(kids))]))
print(f"uniform parents: {same}  mixed parents: {diff}")
for pid, pl, kl in examples:
    print(f"parent {pid} label={pl}")
    for kid, l in kl:
        print(f"   child {kid} {l}")
