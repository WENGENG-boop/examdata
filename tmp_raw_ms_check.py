import sqlite3, re
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
# get all ms entries for paper 1579 (2023) containing 'malthus'
rows = list(c.execute("select id, entry_text from mark_scheme_entry where entry_text like '%althus%'"))
print("entries with malthus:", len(rows))
for eid, txt in rows:
    i = txt.lower().find('malthus')
    print(f"--- entry {eid} ---")
    print(txt[max(0,i-300):i+400].replace('\n',' | '))
