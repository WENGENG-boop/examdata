#!/usr/bin/env python
"""S18: aggregate compare-official.mjs outputs into evidence JSON + Markdown.

Reads scratch/s18/compare/book*-test*-*.json (per-cell compare outputs),
builds:
  - evidence/S18-official-compare.json  (full structured evidence)
  - evidence/S18-official-compare.md    (human-readable summary)
"""
import json
import glob
import os
import re
import datetime

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
R = os.path.abspath(R)  # run dir root: .../20261003T140007Z-repair
COMPARE_DIR = os.path.join(R, 'scratch', 's18', 'compare')
EVID_DIR = os.path.join(R, 'evidence')
os.makedirs(EVID_DIR, exist_ok=True)


def parse_name(fn):
    m = re.match(r'book(\d+)-test(\w+)-(\w+)\.json$', os.path.basename(fn))
    if not m:
        return None
    return int(m.group(1)), m.group(2), m.group(3)


def _norm(s):
    return ' '.join(s.casefold().split())


def classify_conflict(it):
    """Classify a conflict by comparing index-side values vs the PDF value.

    Classes:
      alt_match    - PDF value lists `//` alternatives and an index value matches one
      alt_no_match - PDF value lists `//` alternatives but no index value matches
      nonascii_ocr - PDF value contains non-ASCII (OCR noise, not a real divergence)
      plain_diff   - textual difference worth human review
    """
    pdf_val = (it.get('pdf') or {}).get('value') or ''
    idx_vals = [v for v in ((it.get('answer') or {}).get('values') or []) if isinstance(v, str)]
    if '//' in pdf_val:
        alts = {_norm(a) for a in pdf_val.split('//') if a.strip()}
        klass = 'alt_match' if any(_norm(v) in alts for v in idx_vals) else 'alt_no_match'
    elif any(ord(ch) > 127 for ch in pdf_val):
        klass = 'nonascii_ocr'
    else:
        klass = 'plain_diff'
    return {
        'number': it.get('number'),
        'pdf_value': pdf_val,
        'answer_values': idx_vals,
        'answer_resolved': it.get('answer_resolved'),
        'class': klass,
        'rule_id': it.get('rule_id'),
        'decision': it.get('decision'),
    }


def main():
    cells = []
    for fn in sorted(glob.glob(os.path.join(COMPARE_DIR, 'book*-test*-*.json'))):
        key = parse_name(fn)
        if key is None:
            continue
        book, test, skill = key
        try:
            d = json.load(open(fn, encoding='utf-8'))
        except Exception as e:
            cells.append({'book': book, 'test': test, 'skill': skill,
                          'error': str(e), 'path': os.path.relpath(fn, R).replace('\\', '/')})
            continue
        s = d.get('summary', {})
        conflicts = []
        pdf_only = []
        answer_only = []
        missing = []
        unverified_items = []
        for it in d.get('items', []):
            num = it.get('number')
            v = it.get('verdict')
            if v == 'conflict':
                conflicts.append(classify_conflict(it))
            elif v == 'pdf_only':
                pdf_only.append({'number': num, 'pdf_value': it.get('pdf', {}).get('value')})
            elif v == 'answer_only':
                answer_only.append({'number': num, 'answer_value': it.get('answer_resolved')})
            elif v == 'missing':
                missing.append({'number': num})
            elif v not in ('match',):
                unverified_items.append({'number': num, 'verdict': v})
        cells.append({
            'book': book, 'test': test, 'skill': skill,
            'path': os.path.relpath(fn, R).replace('\\', '/'),
            'summary': s,
            'conflicts': conflicts,
            'pdf_only': pdf_only,
            'answer_only': answer_only,
            'missing': missing,
            'unverified_items': unverified_items,
        })

    totals = {}
    for c in cells:
        s = c.get('summary', {})
        for k in ('total', 'match', 'conflict', 'pdf_only', 'answer_only', 'missing', 'unverified'):
            totals[k] = totals.get(k, 0) + (s.get(k) or 0)

    class_counts = {}
    for c in cells:
        for it in c.get('conflicts', []):
            cl = it.get('class', 'unknown')
            class_counts[cl] = class_counts.get(cl, 0) + 1

    def _squash(s):
        return re.sub(r'[^a-z0-9]+', '', s)

    sub_counts = {}
    for c in cells:
        for it in c.get('conflicts', []):
            if it.get('class') != 'plain_diff':
                continue
            pdf = it.get('pdf_value') or ''
            idxs = it.get('answer_values') or []
            p = _norm(pdf)
            if not idxs:
                k = 'no_idx'
            elif any(_norm(v) in p for v in idxs):
                k = 'pdf_superset'
            elif any(p in _norm(v) for v in idxs):
                k = 'idx_superset'
            elif _squash(p) and any(_squash(_norm(v)) == _squash(p) for v in idxs):
                k = 'punct_case_only'
            else:
                k = 'disjoint'
            sub_counts[k] = sub_counts.get(k, 0) + 1

    out = {
        'generated_at_utc': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'tool': 'aggregate-compare.py',
        'source_dir': os.path.relpath(COMPARE_DIR, R).replace('\\', '/'),
        'cells': cells,
        'totals': totals,
        'conflict_classes': class_counts,
        'plain_diff_subpatterns': sub_counts,
    }
    outpath = os.path.join(EVID_DIR, 'S18-official-compare.json')
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('wrote', outpath, '| cells:', len(cells), '| totals:', totals, '| classes:', class_counts, '| sub:', sub_counts)

    # Markdown summary
    lines = []
    lines.append('# S18 官方答案逐题核验（PDF 提取 vs 索引答案）')
    lines.append('')
    lines.append('生成时间(UTC): %s' % out['generated_at_utc'])
    lines.append('')
    lines.append('比较工具: `ielts-api/tools/compare-official.mjs`（严格模式，无 --number-word/--date-variants；45 条裁决 + 7 条窄修正默认加载）')
    lines.append('')
    lines.append('| 册 | 测试 | 技能 | total | match | conflict | pdf_only | answer_only | missing | unverified |')
    lines.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for c in cells:
        s = c.get('summary', {})
        if 'error' in c:
            lines.append('| %s | %s | %s | ERROR: %s | | | | | | |' % (c['book'], c['test'], c['skill'], c['error']))
            continue
        lines.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            c['book'], c['test'], c['skill'],
            s.get('total'), s.get('match'), s.get('conflict'),
            s.get('pdf_only'), s.get('answer_only'), s.get('missing'), s.get('unverified')))
    lines.append('')
    lines.append('合计: ' + json.dumps(totals, ensure_ascii=False))
    lines.append('')
    lines.append('冲突分类合计: ' + json.dumps(class_counts, ensure_ascii=False))
    lines.append('')
    lines.append('plain_diff 子模式（辅助口径）: ' + json.dumps(sub_counts, ensure_ascii=False) + ' —— pdf_superset=索引值含于 PDF 值（尾随注释/合并单元格）；idx_superset=PDF 值含于索引值（复数等）；punct_case_only=仅标点/大小写差异；disjoint=其余，需人工复核。')
    lines.append('')
    lines.append('冲突分类口径（聚合层分类，比较器输出原样保留）: alt_match=PDF 值以 `//` 列出备选且索引值命中其一；alt_no_match=`//` 备选但索引值未命中；nonascii_ocr=PDF 值含非 ASCII（OCR 噪声）；plain_diff=其余文本差异，需人工复核。')
    lines.append('')
    lines.append('## 冲突明细（每 cell 前 20 条）')
    for c in cells:
        if c.get('conflicts'):
            lines.append('')
            lines.append('### book%s test%s %s (%d conflicts)' % (c['book'], c['test'], c['skill'], len(c['conflicts'])))
            for it in c['conflicts'][:20]:
                lines.append('- Q%s [%s]: pdf=%r vs ans=%r' % (it['number'], it['class'], it['pdf_value'], it['answer_values']))
    mdpath = os.path.join(EVID_DIR, 'S18-official-compare.md')
    with open(mdpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('wrote', mdpath)


if __name__ == '__main__':
    main()
