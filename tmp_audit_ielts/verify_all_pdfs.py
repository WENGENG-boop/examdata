import json, hashlib, os, sys, time

base = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'
dl = os.path.join(base, 'downloads')

pointers = json.load(open(os.path.join(base, 'lfs_pointers.json'), encoding='utf-8'))
by_book = {}
for p in pointers:
    by_book[p['book']] = p

print(f"{'book':>4} {'size_file':>12} {'size_ptr':>12} {'sha256_match':>12} {'magic':>6} {'status':>8}")
t0 = time.time()
ok_all = True
total = 0
for b in range(1, 21):
    f = os.path.join(dl, f'book_{b}.pdf')
    ptr = by_book.get(b)
    if not os.path.exists(f):
        print(f"{b:>4} MISSING FILE")
        ok_all = False
        continue
    size = os.path.getsize(f)
    total += size
    with open(f, 'rb') as fh:
        magic = fh.read(5).decode('latin1')
        fh.seek(0)
        h = hashlib.sha256()
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    sha = h.hexdigest()
    oid = ptr.get('oid', '')
    psize = ptr.get('size', -1)
    match = 'MATCH' if sha == oid else 'MISMATCH'
    if match == 'MISMATCH' or magic != '%PDF-' or (psize not in (-1, size)):
        ok_all = False
    print(f"{b:>4} {size:>12} {psize:>12} {match:>12} {magic:>6} {'OK' if match=='MATCH' else 'FAIL':>8}")

print(f"\nTOTAL bytes: {total} = {total/1048576:.1f} MB")
print(f"ALL OK: {ok_all}  elapsed {time.time()-t0:.1f}s")
