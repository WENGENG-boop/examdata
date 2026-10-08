#!/usr/bin/env python3
"""Run every sample in testdata/manifest.json through the cieparse binary and
write docs/TEST_REPORT.md (plus testdata/report.json).

This is the human-readable companion to `go test ./...` (regression_test.go
holds the assertions). It reports, per sample: cover total, qp marks sum, ms
numeric sum, per-question qp-vs-ms agreement, and the subject fields.

Two different checks appear side by side and must not be confused:

  * 自校验 (self-check): the cover total against the marks the parser summed.
    Both numbers come from the same PDF, so this catches a parser that
    contradicts itself but cannot catch a parser that misreads the document.
  * 跨文档校验 (cross-document check): the question paper's per-question marks
    against the independent mark-scheme PDF. This is the stronger check.

Usage:
  python tools/run_regression.py                 # build if needed, run all
  python tools/run_regression.py --bin path.exe  # use an existing binary
  python tools/run_regression.py --update        # also refresh expect.total_mark
  python tools/run_regression.py 0580 9709       # only these subjects
"""
import json, os, re, subprocess, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, 'testdata', 'manifest.json')
PDFDIR = os.path.join(ROOT, 'testdata', 'pdf')
REPORT = os.path.join(ROOT, 'docs', 'TEST_REPORT.md')
JSONOUT = os.path.join(ROOT, 'testdata', 'report.json')
IS_WIN = os.name == 'nt'
DEFAULT_BIN = os.path.join(ROOT, 'cieparse', 'cieparse.exe' if IS_WIN else 'cieparse')
FN = re.compile(r'^(\d{4})_([msw])(\d{2})_([a-z]+)(?:_(\w+))?\.pdf$')

# Cover fields every parseable document must carry. A blank one means the
# cover was not read, so the document's numbers cannot be trusted.
COVER_FIELDS = ('syllabus', 'component', 'session')
STATUSES = ('PASS', 'WARN', 'FAIL', 'KNOWN', 'DIFF', 'NOC', 'SKIP', 'N/A')


def ensure_bin(path):
    subprocess.run(['go', 'build', '-o', path, '.'], cwd=os.path.join(ROOT, 'cieparse'), check=True)
    return path


def run(binary, pdf):
    out = subprocess.run([binary, pdf], capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode('utf-8', 'replace').strip() or f'exit {out.returncode}')
    return json.loads(out.stdout.decode('utf-8', 'replace'))


def row_marks(s):
    """Sum a mark-scheme `marks` cell: prefer explicit numbers, else code suffixes."""
    parts = [p for p in str(s or '').split(',') if p]
    nums = [int(p) for p in parts if p.isdigit()]
    if nums:
        return sum(nums)
    return sum(int(p[-1]) for p in parts if p and p[-1].isdigit())


def qp_ms_rows(data):
    """Return {question_number: marks} for a qp or ms payload."""
    out = collections.defaultdict(int)
    parts = data.get('part_marks')
    if parts:  # the parser publishes what it counted per part: compare that
        for label, v in parts.items():
            n = re.match(r'\d+', label)
            if n:
                out[n.group()] += v
        return dict(out)
    for q in data.get('questions') or []:
        n = q.get('number')
        if n is not None:  # question paper / multiple choice: numeric number
            out[str(n)] += q.get('marks') or 0
            continue
        # Economics mark schemes key their questions as "3(b)" and put a code
        # string in `marks`, so the number has to be read off the label.
        m = re.match(r'\d+', str(q.get('question') or ''))
        if m:
            out[m.group()] += row_marks(q.get('marks'))
    for r in data.get('rows') or []:  # column-aware mark schemes
        if r.get('alternative'):
            continue
        n = re.match(r'\d+', str(r.get('question') or ''))
        if n:
            out[n.group()] += row_marks(r.get('marks'))
    return dict(out)


def ms_total(d):
    """The mark-scheme sum under either payload spelling (MSData vs EconMS)."""
    v = d.get('numeric_marks_sum')
    return d.get('marks_sum') if v is None else v


def subject_fields(data):
    keys = [k for k in data
            if k not in ('header', 'pages', 'questions', 'rows', 'marks_sum',
                         'numeric_marks_sum', 'marks_match_total', 'checks', 'kind',
                         'question_totals', 'optional_groups', 'effective_total')]
    return ', '.join(f'{k}' for k in sorted(keys)) or '–'


def has_warn(warns, sub):
    return any(sub in str(w) for w in warns)


def classify(t, d, hdr, checks, warns):
    """Map one parsed document to (status, detail).

    Mirrors regression_test.go: a blank cover field is a hard failure, while a
    failed marks check is a failure only when the payload is silent about it.
    An empty total, a mismatched sum and an unparsed mark scheme all arrive
    with a warning saying so, and a warning is the parser answering the check
    rather than ignoring it.

    A payload with no checks block at all (multiple-choice answer keys, the
    economics mark schemes, grade thresholds, examiner reports) builds its own
    type and asserts nothing. Those are reported as NOC rather than PASS: a
    green row has to mean "checked and consistent", not "nothing was checked".
    """
    if hdr is None:
        # Grade thresholds and examiner reports carry no header and no checks
        # block, so there is nothing to assert for them. A paper that does
        # publish a header -- even an empty one -- is held to the cover rules.
        return 'N/A', 'no assertions defined'
    hard = [k for k in COVER_FIELDS if not hdr.get(k)]
    if not hdr.get('total_mark') and not has_warn(warns, 'total mark not found'):
        hard.append('total_mark')
    soft = ''
    if checks:
        tot = hdr.get('total_mark')
        if t in ('qp', 'sp'):
            ok, got, label = checks.get('marks_match_total'), d.get('marks_sum'), 'marks_sum'
        elif t in ('ms', 'sm'):
            ok, got, label = checks.get('ms_match_total'), ms_total(d), 'marks sum'
        else:
            ok = True
        if ok is not True:
            soft = f'{label} {got} != total_mark {tot}' if tot else 'total mark not found on the cover'
    if hard:
        detail = 'cover fields empty: ' + ', '.join(hard)
        return 'FAIL', detail + ('; ' + '; '.join(warns) if warns else '')
    if not checks:
        return 'NOC', 'payload carries no checks block, so no marks check was made'
    if soft and not warns:
        return 'FAIL', soft
    if soft:
        return 'WARN', '; '.join(warns)
    return 'PASS', '; '.join(warns)


def main():
    args = sys.argv[1:]
    update = '--update' in args
    if update:
        args.remove('--update')
    binary = DEFAULT_BIN
    if '--bin' in args:
        i = args.index('--bin')
        binary = args[i + 1]
        del args[i:i + 2]
    binary = ensure_bin(binary)

    man = json.load(open(MANIFEST, encoding='utf-8'))
    want = set(args)
    rows, parsed = [], {}
    for code, sub in man['subjects'].items():
        if want and code not in want:
            continue
        for s in sub['samples']:
            fn = s['file']
            path = os.path.join(PDFDIR, code, fn)
            m = FN.match(fn)
            t = m.group(4) if m else '?'
            rec = {'subject': code, 'file': fn, 'type': t, 'status': 'SKIP', 'detail': '',
                   'total': '', 'qp_sum': '', 'ms_sum': '', 'per_q': '', 'fields': ''}
            if not os.path.exists(path):
                rec['detail'] = 'PDF not downloaded'
                rows.append(rec)
                continue
            try:
                res = run(binary, path)
            except Exception as e:
                rec['status'], rec['detail'] = 'FAIL', f'parse error: {e}'
                rows.append(rec)
                continue
            if res.get('error'):
                rec['status'], rec['detail'] = 'FAIL', res['error']
                rows.append(rec)
                continue
            d = res.get('data') or {}
            hdr = d.get('header')          # None when the payload has no header
            checks = d.get('checks') or {}
            warns = checks.get('warnings') or []
            rec['total'] = (hdr or {}).get('total_mark', '')
            rec['fields'] = subject_fields(d)
            parsed[(code, fn)] = d
            if t in ('qp', 'sp'):
                rec['qp_sum'] = d.get('marks_sum', '')
            elif t in ('ms', 'sm'):
                rec['ms_sum'] = ms_total(d)
            rec['status'], rec['detail'] = classify(t, d, hdr, checks, warns)
            if update and t in ('qp', 'ms') and rec['total']:
                s.setdefault('expect', {})['total_mark'] = rec['total']
            rows.append(rec)

    # cross-document check: per-question qp vs ms agreement
    for rec in rows:
        if rec['type'] not in ('qp', 'ms'):
            continue
        m = FN.match(rec['file'])
        if not m:
            continue
        code, sea, yy, t, comp = m.groups()
        qp = parsed.get((code, f'{code}_{sea}{yy}_qp_{comp}.pdf'))
        ms = parsed.get((code, f'{code}_{sea}{yy}_ms_{comp}.pdf'))
        if not qp or not ms:
            continue
        qm, mm = qp_ms_rows(qp), qp_ms_rows(ms)
        # A multiple-choice paper prints no [n] in the body, and an unparsed
        # mark scheme carries no numeric column: with either side empty there
        # is nothing to compare, which is not the same as a disagreement.
        if sum(qm.values()) == 0 or sum(mm.values()) == 0:
            rec['per_q'] = '–'
            continue
        diff = {k: (qm.get(k, 0), mm.get(k, 0)) for k in set(qm) | set(mm)
                if qm.get(k, 0) != mm.get(k, 0)}
        rec['per_q'] = '✔' if not diff else '✘ ' + ','.join(
            f'{k}:qp{v[0]}/ms{v[1]}' for k, v in sorted(diff.items(), key=lambda x: int(x[0])))
        if diff and rec['status'] in ('PASS', 'NOC'):
            rec['status'] = 'DIFF'
            rec['detail'] = (rec['detail'] + '; ' if rec['detail'] else '') + 'qp/ms per-question mismatch'

    known = {kf['file'] for sub in man['subjects'].values() for kf in sub.get('known_failures', [])}
    for rec in rows:
        if rec['file'] in known and rec['status'] in ('FAIL', 'DIFF'):
            rec['status'] = 'KNOWN'

    counts = collections.Counter(r['status'] for r in rows)
    prev = {}
    if os.path.exists(JSONOUT):
        try:
            prev = {r['file']: r['status'] for r in json.load(open(JSONOUT, encoding='utf-8'))}
        except Exception:
            prev = {}
    lines = ['# CIE cieparse 回归报告', '',
             f'样本：{len(rows)}  生成方式：`python tools/run_regression.py`', '',
             '状态含义：',
             '',
             '- `PASS`：封面总分与解析出的分值合计一致。注意这是**自校验**——总分和合计都来自同一份 PDF 的解析结果。',
             '- `WARN`：不一致，或封面读不到总分，但解析器已在 `checks.warnings` 中说明原因（不是静默通过）。',
             '- `FAIL`：校验不通过且没有任何 warning，属于必须修的缺陷。',
             '- `KNOWN`：已登记在 `testdata/manifest.json` 的 `known_failures` 中的已知缺陷。',
             '- `DIFF`：自校验通过或未做自校验，但**跨文档**逐题对照 qp 与 ms 时对不上。',
             '- `NOC`：payload 没有 `checks` 块，解析器**没有做分值校验**（选择题答案表 `mcq_key`、经济结构化评分标准）。既不是通过也不是失败——`PASS` 只用于「校验过且一致」。',
             '- `SKIP`：PDF 未下载。`N/A`：gt/er 类文档没有 header，无分值可比对。',
             '',
             '`逐题一致` 列是**跨文档校验**：把 qp 与 ms 两份独立 PDF 的逐题分值对照，比上面的自校验更有说服力。'
             '`–` 表示两侧至少有一侧没有数值分值（选择题卷正文不印 `[n]`，或 MS 的分值列未解析），因此不可比，不算不一致。'
             '经济卷的 ms 逐题分值是分级给分（Level 制），与 qp 的逐题满分本就不是同一口径，因此经济样本的 `DIFF` 需另行判断。',
             '',
             '| 科目 | 文件 | 类型 | 封面总分 | qp合计 | ms合计 | 逐题一致 | 学科字段 | 状态 | 备注 |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append('| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |'.format(
            r['subject'], r['file'].replace('.pdf', ''), r['type'], r['total'],
            r['qp_sum'], r['ms_sum'], r['per_q'], r['fields'], r['status'], r['detail']))
    lines += ['', '## 汇总', '', '| 状态 | 数量 |', '|---|---|']
    for k in STATUSES:
        lines.append(f'| {k} | {counts.get(k, 0)} |')
    lines += ['', '## 分科汇总', '',
              '| 科目 | 样本 | PASS | WARN | FAIL | KNOWN | DIFF | NOC | SKIP | N/A | 通过率 |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
    for code in man['subjects']:
        sub_rows = [r for r in rows if r['subject'] == code]
        c = collections.Counter(r['status'] for r in sub_rows)
        denom = len(sub_rows) - c.get('SKIP', 0) - c.get('N/A', 0) - c.get('NOC', 0)
        rate = f'{100.0 * c.get("PASS", 0) / denom:.0f}%' if denom else '–'
        lines.append('| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |'.format(
            code, len(sub_rows), c.get('PASS', 0), c.get('WARN', 0), c.get('FAIL', 0),
            c.get('KNOWN', 0), c.get('DIFF', 0), c.get('NOC', 0), c.get('SKIP', 0),
            c.get('N/A', 0), rate))
    lines += ['', '通过率 = `PASS` / (样本 − `SKIP` − `N/A` − `NOC`)：只在**真正做过校验**的样本上计算，`NOC` 与 `N/A` 不拉低也不抬高。']

    fails = [r for r in rows if r['status'] == 'FAIL']
    lines += ['', '## FAIL 明细', '']
    if fails:
        lines += ['| 科目 | 文件 | 期望 | 实际 | 备注 |', '|---|---|---|---|---|']
        for r in fails:
            lines.append('| {} | {} | {} | {} | {} |'.format(
                r['subject'], r['file'].replace('.pdf', ''),
                r['total'] or '–', r['qp_sum'] if r['qp_sum'] != '' else (r['ms_sum'] or '–'), r['detail']))
    else:
        lines.append('无。')
    nocs = [r for r in rows if r['status'] == 'NOC']
    lines += ['', '## 未做分值校验（NOC）', '',
              '这些样本的 payload 没有 `checks` 块，解析器没有做任何分值校验，因此不能当作通过：',
              '',
              '| 科目 | 文件 | 类型 | 封面总分 | 解析出的合计 |', '|---|---|---|---|---|']
    for r in nocs:
        lines.append('| {} | {} | {} | {} | {} |'.format(
            r['subject'], r['file'].replace('.pdf', ''), r['type'],
            r['total'] or '–', r['qp_sum'] if r['qp_sum'] != '' else (r['ms_sum'] or '–')))
    if not nocs:
        lines.append('| – | – | – | – | – |')
    diffs = [r for r in rows if r['status'] == 'DIFF']
    lines += ['', '## 跨文档逐题不一致（DIFF）', '']
    if diffs:
        for r in diffs:
            lines.append(f"- `{r['subject']}/{r['file'].replace('.pdf', '')}`：{r['per_q']}")
    else:
        lines.append('无。')
    new_fail = sorted(r['file'] for r in rows
                      if r['status'] == 'FAIL' and prev.get(r['file'], 'PASS') != 'FAIL')
    lines += ['', '## 与上次报告对比', '',
              f'- 上次报告样本数：{len(prev) or "无（首次运行）"}',
              f'- 新增 FAIL：{len(new_fail)}' + (f' → {", ".join(new_fail)}' if new_fail else '')]
    lines.append('')
    if update:
        json.dump(man, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    json.dump(rows, open(JSONOUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'wrote {REPORT}  ({dict(counts)})')


if __name__ == '__main__':
    main()
