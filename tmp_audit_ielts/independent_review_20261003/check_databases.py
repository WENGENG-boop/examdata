import sqlite3, json
from pathlib import Path
base = Path('C:/Users/weo/Desktop/api/examdata')
results = []
for relative in ['.pytest_cache/callable-api/examdata.db', '.data/examdata.db']:
    path = base / relative
    entry = {'path': str(path), 'exists': path.exists()}
    if path.exists():
        try:
            conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            conn.execute('PRAGMA temp_store=MEMORY')
            entry['board_question_counts'] = conn.execute('select board.key,count(*) from question join paper on paper.id=question.paper_id join document on document.id=paper.document_id join board on board.id=document.board_id group by board.key').fetchall()
            conn.close()
        except Exception as e:
            entry['error'] = str(e)
    results.append(entry)
print(json.dumps(results, indent=2))
Path(__file__).with_name('database_readonly_checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
