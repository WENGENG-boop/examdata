import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def q(label, like, extra=''):
    print(f'===== {label} =====')
    sql = ("SELECT n.code, count(*), substr(group_concat(q.id),1,150) FROM question q "
           "JOIN question_taxonomy t ON q.id=t.question_id "
           "JOIN taxonomy_node n ON t.node_id=n.id "
           "WHERE q.stem_text LIKE ? AND n.code LIKE 'WCH15%' " + extra +
           " GROUP BY n.code ORDER BY count(*) DESC LIMIT 7")
    try:
        for code, cnt, ids in cur.execute(sql, (like,)):
            print(f'{code}: {cnt}  [{ids}]')
    except Exception as e:
        print('ERR', e)
    print()

q('chemical shift', '%chemical shift%')
q('dissociat', '%dissociat%')
q('silver nitrate', '%silver nitrate%')
q('dimethyldithiocarbamate', '%dimethyldithiocarbamate%')
q('wedge', '%wedge%')
q('absorbance', '%absorbance%')
q('anthranilic', '%anthranilic%')
q('chromatogram', '%chromatogram%')
q('hydrogen peroxide', '%hydrogen peroxide%')
q('half-life', '%half-life%')
q('coordination number', '%oordination number%')
q('hydration isomerism', '%hydration isomerism%')
