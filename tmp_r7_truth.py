"""r7 truth: extract printed unit/paper code from PDF pages for all affected docs.

Writes tmp_r7_truth.json: {doc_id: {unit, print_code, evidence, source, pages_checked}}
Law: printed YLA0/01 -> YLA0-P1 etc. Others: unit = code's unit part (aliases for GCE codes).
Reference docs (not fixed, only checked): 1754.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import pymupdf

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

AFFECTED = {
    'ial-accounting': [1728, 1737, 1752, 1753],
    'ial-geography': [2342],
    'ial-german': [2378],
    'ial-maths': [3250, 3255, 3256, 3257, 3263, 3268, 3270, 3271, 3273, 3274,
                  3290, 3291, 3294, 3297, 3318, 3319],
    'ial-law': [3106, 3107, 3108, 3109, 3112, 3113, 3115, 3116, 3117, 3118,
                3120, 3121, 3122, 3123, 3130, 3131, 3138, 3139, 3142, 3143,
                3146, 3147, 3150, 3155, 3156, 3157, 3163, 3164, 3167, 3168],
}
REFERENCE = [1754]

# printed code -> DB unit code
LAW_MAP = {'YLA0/01': 'YLA0-P1', 'YLA0/02': 'YLA0-P2',
           'YLA1/01': 'YLA1-01', 'YLA1/02': 'YLA1-02'}
ALIAS = {'6663A': 'WMA01', '6664A': 'WMA01', '6667A': 'WFM01',
         'P61129A': None, 'P61903A': None}  # GCE codes -> unit (None = needs title fallback)

RE_UNIT = re.compile(r'\b([A-Z]{3})\s*(\d{1,2})\s*/\s*(\d{1,2})\b')
RE_GCE = re.compile(r'\b(\d{4}[A-Z])\s*/\s*(\d{1,2})\b')
RE_BARE = re.compile(r'\b(666[3-7]A|P61\d{3}A)\b')
RE_LAW = re.compile(r'\bYLA\s*([01])\s*/\s*(0[12])\b')


def pdf_for_doc(s: Session, doc_id: int):
    r = s.execute(text("""
      SELECT a.storage_key FROM document d
      JOIN document_revision dr ON dr.document_id = d.id
      JOIN artifact a ON a.id = dr.artifact_id
      WHERE d.id = :d ORDER BY dr.revision_no DESC LIMIT 1"""), {'d': doc_id}).fetchone()
    if not r:
        return None
    return ROOT / '.data' / 'artifacts' / r[0]


def line_containing(txt: str, needle: str) -> str:
    for line in txt.splitlines():
        if needle in line:
            return line.strip()[:220]
    return ''


def extract(path: Path, subject: str, doc_id: int):
    doc = pymupdf.open(path)
    n = doc.page_count
    maxp = min(n, 4)
    pages = [doc[i].get_text() for i in range(maxp)]
    full = '\n'.join(pages)
    out = {'pages_checked': maxp, 'total_pages': n, 'matches': [], 'law_matches': [], 'gce': []}
    seen = set()
    for m in RE_UNIT.finditer(full):
        code = f'{m.group(1)}{m.group(2)}/{m.group(3)}'
        if code in seen:
            continue
        seen.add(code)
        out['matches'].append({'code': code, 'line': line_containing(full, m.group(0))})
    seen_g = set()
    for m in RE_GCE.finditer(full):
        code = f'{m.group(1)}/{m.group(2)}'
        if code in seen_g:
            continue
        seen_g.add(code)
        out['gce'].append({'code': code, 'line': line_containing(full, m.group(0))})
    seen_l = set()
    for m in RE_LAW.finditer(full):
        code = f'YLA{m.group(1)}/{m.group(2)}'
        if code in seen_l:
            continue
        seen_l.add(code)
        out['law_matches'].append({'code': code, 'line': line_containing(full, m.group(0))})
    return out


def decide(subject: str, doc_id: int, ext: dict):
    """Pick the printed unit for the doc, with evidence."""
    if subject == 'ial-law':
        for mm in ext['law_matches']:
            code = mm['code']
            if code in LAW_MAP:
                return LAW_MAP[code], code, mm['line'], 'printed-law'
        # fall back: generic matches that look like YLA
        for mm in ext['matches']:
            code = mm['code']
            if code.startswith('YLA') and code in LAW_MAP:
                return LAW_MAP[code], code, mm['line'], 'printed-law'
        return None, None, '', 'none'
    # non-law: look at unit-style matches (WACxx/yy, WGExx, WGNxx, WMAxx, ...)
    cands = [mm for mm in ext['matches']
             if mm['code'][:3] in ('WAC', 'WGE', 'WGN', 'WMA', 'WFM', 'WST', 'WME', 'WDM')]
    if cands:
        code = cands[0]['code']
        unit = code.split('/')[0]
        return unit, code, cands[0]['line'], 'printed'
    # GCE-style
    for mm in ext['gce']:
        base = mm['code'].split('/')[0]
        if base in ALIAS and ALIAS[base]:
            return ALIAS[base], mm['code'], mm['line'], 'printed-gce'
    return None, None, '', 'none'


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)
    truth = {}
    for subject, docs in AFFECTED.items():
        for did in docs:
            row = s.execute(text("SELECT title FROM document WHERE id=:d"), {'d': did}).fetchone()
            title = row[0] if row else '?'
            path = pdf_for_doc(s, did)
            if path is None or not path.exists():
                truth[str(did)] = {'subject': subject, 'title': title, 'unit': None,
                                   'print_code': None, 'evidence': '', 'source': 'no-pdf'}
                continue
            ext = extract(path, subject, did)
            unit, code, ev, src = decide(subject, did, ext)
            truth[str(did)] = {'subject': subject, 'title': title, 'unit': unit,
                               'print_code': code, 'evidence': ev, 'source': src,
                               'matches': ext['matches'], 'gce': ext['gce'],
                               'law_matches': ext['law_matches'],
                               'pages_checked': ext['pages_checked']}
    refs = {}
    for did in REFERENCE:
        row = s.execute(text("SELECT title FROM document WHERE id=:d"), {'d': did}).fetchone()
        title = row[0] if row else '?'
        path = pdf_for_doc(s, did)
        if path is None or not path.exists():
            refs[str(did)] = {'title': title, 'unit': None, 'print_code': None}
            continue
        ext = extract(path, 'ial-accounting', did)
        unit, code, ev, src = decide('ial-accounting', did, ext)
        refs[str(did)] = {'title': title, 'unit': unit, 'print_code': code,
                          'evidence': ev, 'matches': ext['matches'], 'gce': ext['gce']}
    out = {'truth': truth, 'reference': refs}
    (ROOT / 'tmp_r7_truth.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    # human-readable table
    print('=== AFFECTED DOCS: printed unit vs title ===')
    for subject, docs in AFFECTED.items():
        print(f'--- {subject} ---')
        for did in docs:
            t = truth[str(did)]
            print(f"  doc{did} [{t['source']}] unit={t['unit']} pc={t['print_code']} | {t['title']}")
            if t['evidence']:
                print(f"      ev: {t['evidence'][:160]}")
            if subject == 'ial-law' and t.get('law_matches'):
                codes = [mm['code'] for mm in t['law_matches']]
                print(f"      law codes: {codes}")
    print('=== REFERENCE ===')
    for did, t in refs.items():
        print(f"  doc{did} unit={t['unit']} pc={t['print_code']} | {t['title']}")
        if t.get('evidence'):
            print(f"      ev: {t['evidence'][:160]}")


if __name__ == '__main__':
    main()
