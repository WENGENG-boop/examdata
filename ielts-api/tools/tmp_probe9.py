import hashlib, sys
import pymupdf

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

for p in ['tmp_audit_ielts/downloads/book_9.pdf',
          'tmp_audit_ielts/downloads/book_9_22193053_b25f954dd25e058dfc05913c8f3b9ffead6581aa23bb10f8f2e98e6314f7af24_h.pdf']:
    try:
        d = pymupdf.open(p)
        chars = 0
        sample = []
        for i in range(len(d)):
            t = d[i].get_text().strip()
            chars += len(t)
            if len(sample) < 3 and len(t) > 50:
                sample.append((i + 1, t[:200].replace('\n', ' | ')))
        print(p)
        print('  pages=', len(d), 'sha256=', sha(p)[:16], 'text_chars=', chars)
        for pg, s in sample:
            print('  p%d: %s' % (pg, s))
        d.close()
    except Exception as e:
        print(p, 'ERROR', e)
