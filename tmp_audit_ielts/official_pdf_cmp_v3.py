# -*- coding: utf-8 -*-
"""
official_pdf_cmp_v3.py — 官方 PDF 听力答案提取器 v3（候选聚类定位 band + 栏内链式号码解析）

相对 v2（对剑4 提取 0 条）的改进:
  1. 号码候选词收集: is_num_cand()（NUM_RE 且 num_value 合法；仅聚类候选排除单字符 I/l/O/o 误报）；
     按 x 区间聚类（gap≤5）定位号码列；丢弃 count<6 的簇；每簇 ys 首尾离群（>25px）修剪（页脚伪号）
  2. band = [ymin-10, max(y1)+20]（y1=词框底边；保证行尾值词纳入、页脚排除）
  3. 栏切分（优先）: 相邻号码簇间隔最大者（gap=min_x0(后簇)-max_x2(前簇)，≥30）作栏边界，横跨词判据
     带 0.5px 容差（防浮点噪声误判，如剑4 p153 'Section' 与边界差 0.05px）；否则回退 x 区间 union
     （gap≤0.5 合并），最大空隙（≥12px 且 b1≥0.15W、a2≤0.9W）
  4. 号码链: 行内 NUM_RE token（x0 ≤ colx0+40）从首个 anchor（x0 ≤ colx0+10）起按邻接（gap≤6）拼接，
     translate 后 num_value → 单号 / '&' 组合 / 连字号范围（b-a≤4，如 26-27、25-27）
  5. 大字号小写 c（='C' 答案的异常渲染）: 行容差 3px 下独立成行；前向合并（≤6.5px）归下一号码行；
     25&26 场景（值在号码下方）走续行（≤15px）
  6. 序列修复同 v2；token 修复 '1Oth'→'10th'、'oO'→'of'；页定位 TEST_RE + KEY_HINT

用法:
  python official_pdf_cmp_v3.py [books...]       默认: 3 4
  python official_pdf_cmp_v3.py 4 --debug        打印每页 band/分栏/entries
  python official_pdf_cmp_v3.py 4 --show         打印提取出的 Q→答案行
  python official_pdf_cmp_v3.py 4 --dump         只提取，不抓取比对
"""
import json, re, subprocess, sys
import pymupdf

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'
IELTS = 'C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api'

NUM_CORE = r'[0-9IlOo]{1,2}'
NUM_RE = re.compile(r'^(?:%s[-–—]%s|%s|&)$' % (NUM_CORE, NUM_CORE, NUM_CORE))
NUM_FIX = str.maketrans('IlOo', '1100')
# 单字符 I/l/O/o 多为正文分隔符（如 'Forest I Forrest'）而非号码，禁止入簇；
# 但入口解析（toks）仍用 NUM_RE 原样保留——剑4 T2 的 Q1 号码渲染为 'I'、Q10 为 'I'+'0' 两个 token
SEP_CHARS = {'I', 'l', 'O', 'o'}


def is_num_cand(t):
    return bool(NUM_RE.match(t)) and t not in SEP_CHARS and num_value(t.translate(NUM_FIX))


STRIP_RE = re.compile(r'^(?:Section|Questions|\d{1,2},|\d{1,2}[-–—]\d{1,2}|\d{1,2}\.\.[^a-z]*\d{1,2})$')
TEST_RE = re.compile(r'TEST\s*([1-4A])\b[^\n]{0,6}\n+\s*LISTENING')
KEY_HINT = re.compile(r'answer\s*key|each\s+question\s+correctly\s+answered', re.I)


def num_value(t):
    """t 已经 translate('IlOo'->'1100')。返回 [n...] 或 None。"""
    m = re.match(r'^(\d{1,2})&(\d{1,2})$', t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return [a, b] if (1 <= a <= 40 and 1 <= b <= 40 and a != b) else None
    m = re.match(r'^(\d{1,2})[-–—](\d{1,2})$', t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return list(range(a, b + 1)) if (1 <= a < b <= 40 and b - a <= 4) else None
    m = re.match(r'^(\d{1,2})$', t)
    if m:
        n = int(m.group(1))
        return [n] if 1 <= n <= 40 else None
    return None


def row_groups(ws, tol=3.0):
    rows = []
    for w in sorted(ws, key=lambda w: (w[1], w[0])):
        if rows and w[1] - rows[-1][0][1] <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def fix_tok(t):
    t = t.replace('oO', 'of')
    return re.sub(r'^(\d+)[Oo]', r'\g<1>0', t)


def extract_page(page, debug=False):
    """返回 entries: list of [nums, value_lines]；按列顺序（左→右）"""
    W = page.rect.width
    words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text('words')]

    # 1. 号码候选收集（跳过含 TEST 的行）
    cands = []
    for row in row_groups(words):
        if any(t == 'TEST' or t.startswith('TEST') for (_, _, _, _, t) in row):
            continue
        for w in row:
            if is_num_cand(w[4]):
                cands.append(w)

    # 2. x 区间聚类（gap≤5），丢弃 count<6 的簇（伪号/分隔符链/标题号）
    clusters = []
    for w in sorted(cands, key=lambda w: (w[0], w[1])):
        if clusters and w[0] - max(x[2] for x in clusters[-1]) <= 5:
            clusters[-1].append(w)
        else:
            clusters.append([w])
    clusters = [c for c in clusters if len(c) >= 6]

    # 3. 每簇 ys 首尾离群修剪（>25px，页脚伪号）
    surv = []
    for c in clusters:
        c = list(c)
        while len(c) >= 2:
            ys = sorted(x[1] for x in c)
            if ys[1] - ys[0] > 25:
                c = [x for x in c if x[1] != ys[0]]
            else:
                break
        while len(c) >= 2:
            ys = sorted(x[1] for x in c)
            if ys[-1] - ys[-2] > 25:
                c = [x for x in c if x[1] != ys[-1]]
            else:
                break
        surv.append(c)
    if not surv:
        return []
    ymin = min(min(x[1] for x in c) for c in surv) - 10
    ymax = max(max(x[3] for x in c) for c in surv) + 20
    band = [w for w in words if ymin <= w[1] <= ymax]

    # 4a. 分栏（优先）: 取相邻号码簇间隔最大者为栏边界（剑3 p153 栏间空隙仅 8.5px，union-gap 判据失效）
    split_x = None
    if len(surv) >= 2:
        cs = sorted(surv, key=lambda c: min(x[0] for x in c))
        gaps = []
        for c1, c2 in zip(cs, cs[1:]):
            gaps.append((min(x[0] for x in c2) - max(x[2] for x in c1), min(x[0] for x in c2) - 0.1))
        g, p = max(gaps, key=lambda t: t[0])
        if g >= 30 and not any(w[0] < p - 0.5 and w[2] > p + 0.5 for w in band):
            split_x = p
    if split_x is not None:
        cols = [[w for w in band if w[0] < split_x], [w for w in band if w[0] >= split_x]]
        cols = [c for c in cols if c]
    else:
        # 4b. 回退: x 区间 union（gap≤0.5），最大空隙（≥12 且 b1≥0.15W、a2≤0.9W）
        ivs = []
        for w in sorted(band, key=lambda w: (w[0], w[1])):
            if ivs and w[0] - ivs[-1][1] <= 0.5:
                ivs[-1][1] = max(ivs[-1][1], w[2])
            else:
                ivs.append([w[0], w[2]])
        best = None
        for a, b in zip(ivs, ivs[1:]):
            gap = b[0] - a[1]
            if a[1] >= 0.15 * W and b[0] <= 0.9 * W and gap >= 12 and (best is None or gap > best[2]):
                best = (a[1], b[0], gap)
        if best:
            split_x = (best[0] + best[1]) / 2
            cols = [[w for w in band if w[0] < split_x], [w for w in band if w[0] >= split_x]]
        else:
            split_x = None
            cols = [band]
    if debug:
        cr = [f'{min(x[0] for x in c):.0f}-{max(x[2] for x in c):.0f}({len(c)})' for c in surv]
        print(f'    [debug] W={W:.1f} clusters={len(surv)} [{", ".join(cr)}] ymin={ymin:.1f} ymax={ymax:.1f} '
              f'split_x={"None" if split_x is None else round(split_x, 1)}')

    entries = []
    for ci, col in enumerate(cols):
        if not col:
            continue
        colx0 = min(w[0] for w in col)
        zone, cap = colx0 + 10, colx0 + 40
        rows = row_groups(col)
        # 头行剥 token（Section/Questions 行），剥空则丢行
        rows2 = []
        for r in rows:
            if any(w[4] in ('Section', 'Questions') for w in r):
                r = [w for w in r if not STRIP_RE.match(w[4])]
                if not r:
                    continue
            rows2.append(r)
        rows = rows2
        # 前向合并: 无号码行 + 下一行有号码 + y 差 ≤6.5 → 合并（值归下一号码）
        blocks = []
        i = 0
        while i < len(rows):
            r = rows[i]
            nt_cur = [w for w in r if w[0] <= cap and NUM_RE.match(w[4])]
            nt_next = [w for w in rows[i + 1] if w[0] <= cap and NUM_RE.match(w[4])] if i + 1 < len(rows) else []
            if not nt_cur and nt_next and (rows[i + 1][0][1] - r[0][1]) <= 6.5:
                blocks.append(r + rows[i + 1])
                i += 2
            else:
                blocks.append(r)
                i += 1
        if debug:
            print(f'    [debug] col{ci}: colx0={colx0:.1f} zone={zone:.1f} cap={cap:.1f} rows={len(rows)}')
        cur, last_y = None, None
        for row in blocks:
            toks = sorted([w for w in row if w[0] <= cap and NUM_RE.match(w[4])], key=lambda w: w[0])
            nums, consumed = None, set()
            if toks and toks[0][0] <= zone:
                chain = [toks[0]]
                for t in toks[1:]:
                    if t[0] - chain[-1][2] <= 6:
                        chain.append(t)
                    else:
                        break
                v = num_value(''.join(t[4] for t in chain).translate(NUM_FIX))
                if v:
                    nums = v
                    consumed = set(id(t) for t in chain)
            if nums:
                vt = [w for w in row if id(w) not in consumed]
                line = ' '.join(fix_tok(w[4]) for w in sorted(vt, key=lambda w: (w[1], w[0]))).strip()
                cur = [nums, [line] if line else []]
                entries.append(cur)
                last_y = max(w[1] for w in row)
                continue
            if cur is not None and last_y is not None and (row[0][1] - last_y) <= 15:
                line = ' '.join(fix_tok(w[4]) for w in sorted(row, key=lambda w: (w[1], w[0]))).strip()
                if line:
                    cur[1].append(line)
                last_y = max(w[1] for w in row)
    if debug:
        for nums, lines in entries:
            print(f'      {nums} -> {lines}')
    return entries


def extract_book(book, debug=False, show=False):
    """扫描整本 PDF, 返回 {test: {'page': n, 'answers': {qnum: [value_lines]}}}

    页定位: KEY_HINT + 'LISTENING' 为听力答案页; 优先 TEST_RE / 宽松 'TEST N' 显式编号,
    无编号页(剑5 T1/T3、剑8/12/15 全无标签)按页序与已定位邻页插值补 1..4。
    """
    doc = pymupdf.open(f'{BASE}/downloads/book_{book}.pdf')
    cands = []
    for i in range(doc.page_count):
        t = doc[i].get_text()
        if not KEY_HINT.search(t) or 'LISTENING' not in t:
            continue
        m = TEST_RE.search(t)
        if not m:
            m = re.search(r'TEST\s*([1-4A])\b', t)  # 宽松: 页内任意位置
        test = (4 if m.group(1) == 'A' else int(m.group(1))) if m else None
        cands.append((i, test))
    taken = {}
    for i, test in cands:
        if test is not None and test not in taken:
            taken[test] = i
    unlabeled = [i for i, test in cands if test is None]
    for test in range(1, 5):
        if test in taken or not unlabeled:
            continue
        lo, hi = taken.get(test - 1), taken.get(test + 1)
        if lo is None and hi is None:
            pick = unlabeled[0]
        elif lo is None:
            mid = [i for i in unlabeled if i < hi]
            if not mid:
                continue
            pick = mid[-1]
        elif hi is None:
            mid = [i for i in unlabeled if i > lo]
            if not mid:
                continue
            pick = mid[0]
        else:
            mid = [i for i in unlabeled if lo < i < hi]
            if not mid:
                continue
            pick = mid[0] if len(mid) == 1 else min(mid, key=lambda i: abs(2 * i - (lo + hi)))
        taken[test] = pick
        unlabeled.remove(pick)
    per_test = {}
    for test in sorted(taken):
        i = taken[test]
        page = doc[i]
        if debug:
            print(f'--- book{book} p{i + 1} (T{test})')
        raw = extract_page(page, debug=debug)
        out, expected, seen = {}, 1, set()
        for nums, vlines in raw:
            fixed = []
            for n in nums:
                if n in seen and expected not in seen:
                    n = expected  # OCR 重复号修复
                fixed.append(n)
                seen.add(n)
            expected = max(seen) + 1
            for n in fixed:
                out[n] = vlines
        per_test[test] = {'page': i + 1, 'answers': out}
        if show:
            for q in range(1, 41):
                lines = out.get(q)
                if lines is not None:
                    print(f'  Q{q}: {lines}')
    doc.close()
    return per_test


# ---------- 2. 规范化与匹配 ----------
def norm(s):
    s = str(s).lower()
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    s = re.sub(r'(\d),(\d)', r'\1\2', s)
    s = re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', s)
    s = re.sub(r'[^a-z0-9/ ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def variants(raw):
    raw = str(raw)
    stripped = re.sub(r'\s+NOT\s+.*$', '', raw)  # 大写 NOT 之后是官方拒绝项（如 '7.30pm (to/and) 5.30am NOT 7.30 to 5.30'）
    if stripped.strip():
        raw = stripped
    out = set()
    m = re.search(r'\(([^()/]*)/([^()/]*)\)', raw)  # 括号内斜杠展开: '(to/and)' → 'to' / 'and'
    if m and m.group(1).strip() and m.group(2).strip():
        for alt in (m.group(1).strip(), m.group(2).strip()):
            out |= variants(raw[:m.start()] + alt + raw[m.end():])
    for p in re.split(r'//|/| accept |\bor\b| I | \| ', raw, flags=re.I):
        p = p.strip()
        if not p:
            continue
        out.add(norm(p))
        out.add(norm(re.sub(r'\([^)]*\)', ' ', p)))
        out.add(norm(re.sub(r'[()]', '', p)))
        out.add(norm(re.sub(r'[()\-]', '', p)))
        out.add(norm(re.sub(r'-', ' ', p)))
    out.add(norm(raw))
    out.add(norm(raw.replace('/', ' ')))
    return {v for v in out if v}


def match_one(pte_ans, official_raw):
    if pte_ans is None:
        return None
    pv = {p for p in variants(str(pte_ans)) if p}   # 两侧都生成 variants（pte '6/Six' → '6'、'six'）
    if not pv:
        return False
    ov = {v for v in variants(official_raw) if v}
    for p in pv:
        for v in ov:
            if p == v or (len(p) >= 2 and p in v) or (len(v) >= 2 and v in p):
                return True
            pd, vd = p.replace(' ', ''), v.replace(' ', '')  # 空格差异（'7.30 pm' vs '7.30pm'）
            if len(pd) >= 4 and (pd == vd or pd in vd or vd in pd):
                return True
        pt = set(p.split())
        if len(pt) > 1:
            for v in ov:
                vt = set(v.split())
                if pt and pt <= vt:
                    return True
    return False


INSTR_RE = re.compile(r'either\s*order|any\s*order|both\s*required|for\s+one\s+mark|inanyorder', re.I)
EITHER_RE = re.compile(r'either\s*order|any\s*order|inanyorder', re.I)


def compare_one(official_lines, pte_ans):
    """official_lines: list[str]; pte_ans: str 或 list[str]（组合号）"""
    if pte_ans is None:
        return None
    official = ' '.join(official_lines)
    if EITHER_RE.search(official) or isinstance(pte_ans, list):
        if isinstance(pte_ans, list):
            parts = [str(p) for p in pte_ans]
        else:
            parts = re.split(r'\s+and\s+|\s*&\s*|,|\s+or\s+', str(pte_ans))
        parts = [p for p in parts if p and p.strip()]
        if not parts:
            return False
        if EITHER_RE.search(official):
            cands = []
            for ln in official_lines:
                ln2 = INSTR_RE.sub(' ', ln)
                for part in re.split(r'\s*//\s*|\s+I\s+|\s*\|\s*', ln2):
                    part = part.strip()
                    if part and re.search(r'[a-z0-9]', part, re.I):
                        cands.append(part)
            if not cands:
                return False
        else:
            cands = [official]
        return all(any(match_one(p, c) for c in cands) for p in parts)
    return match_one(pte_ans, official)


# ---------- 3. 抓取比对源（node 实时拉取） ----------
def fetch_answers(books):
    node_code = """
const ielts = await import('file:///%s/ielts-api.mjs');
const iprog = await import('file:///%s/iprog.mjs');
const books = %s;
const out = { pte: {}, iprog: {} };
for (const b of books) for (const t of [1,2,3,4]) {
  const r = await ielts.pteListening(b, t);
  out.pte[`${b}-${t}`] = { ok: r.ok, slug: r.slug || null, answers: r.answer_key || null, count: r.answer_count, err: r.error || null };
  if (b === 3) {
    const r2 = await iprog.listeningAnswers(3, t);
    out.iprog[`3-${t}`] = { ok: r2.ok, answers: r2.answer_key || null, count: r2.answer_count, url: r2.url, err: r2.error || null };
  }
}
console.log(JSON.stringify(out));
""" % (IELTS, IELTS, json.dumps(books))
    res = subprocess.run(['node', '--input-type=module', '-e', node_code],
                         capture_output=True, text=True, encoding='utf-8', cwd=BASE)
    if res.returncode != 0:
        print('NODE FAIL:', res.stderr[-2000:])
        sys.exit(1)
    return json.loads(res.stdout.strip().splitlines()[-1])


# ---------- 4. 主流程 ----------
def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dump_only = '--dump' in sys.argv
    debug = '--debug' in sys.argv
    show = '--show' in sys.argv
    books = [int(a) for a in args] if args else [3, 4]

    extraction = {}
    for b in books:
        per_test = extract_book(b, debug=debug, show=show)
        extraction[b] = per_test
        for t in [1, 2, 3, 4]:
            if t not in per_test:
                print(f'[book {b} T{t}] 未找到答案页!')
                continue
            ans = per_test[t]['answers']
            missing = [q for q in range(1, 41) if q not in ans]
            print(f'[book {b} T{t}] page {per_test[t]["page"]}: {len(ans)} 条'
                  + (f', 缺失 {missing}' if missing else ''))
    json.dump({str(b): {str(t): {'page': v['page'], 'answers': {str(k): vv for k, vv in v['answers'].items()}}
                        for t, v in per_test.items()} for b, per_test in extraction.items()},
              open(f'{BASE}/official_v3_extracted.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'提取结果已存: {BASE}/official_v3_extracted.json')

    if dump_only:
        return

    fetched = fetch_answers(books)
    json.dump(fetched, open(f'{BASE}/official_cmp_fetched_v3.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    report = {}
    for b in books:
        print(f'\n===== 剑{b} =====')
        for t in [1, 2, 3, 4]:
            if t not in extraction[b]:
                continue
            off = extraction[b][t]['answers']
            sources = []
            pte = fetched['pte'].get(f'{b}-{t}')
            if pte and pte['ok']:
                sources.append(('pte', pte['answers']))
            else:
                print(f'-- T{t}: pte 不可用: {pte}')
            ip = fetched['iprog'].get(f'3-{t}')
            if b == 3 and ip and ip['ok']:
                sources.append(('iprog', ip['answers']))
            # 组合号（提取阶段多个号共享同一 value_lines 对象）
            groups = {}
            for q, lines in off.items():
                groups.setdefault(id(lines), []).append(q)
            for name, ans_list in sources:
                match = tot = 0
                diffs = []
                for q in range(1, 41):
                    lines = off.get(q)
                    if lines is None:
                        continue
                    g = groups[id(lines)]
                    if len(g) > 1:
                        pa = [ans_list[x - 1] for x in sorted(g) if x - 1 < len(ans_list)]
                    else:
                        pa = ans_list[q - 1] if q - 1 < len(ans_list) else None
                    r = compare_one(lines, pa)
                    if r is None:
                        continue
                    tot += 1
                    if r:
                        match += 1
                    else:
                        diffs.append([q, ' '.join(lines), pa])
                print(f'-- 剑{b} T{t} [{name}]: {match}/{tot} 匹配')
                for q, o, p in diffs:
                    print(f'    Q{q} PDF={o!r}  {name}={p!r}')
                report[f'{b}-{t}-{name}'] = {'page': extraction[b][t]['page'], 'extracted': len(off),
                                              'missing': [q for q in range(1, 41) if q not in off],
                                              'match': match, 'total': tot, 'diffs': diffs}
    json.dump(report, open(f'{BASE}/official_v3_diffs.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n比对结果已存: {BASE}/official_v3_diffs.json')


if __name__ == '__main__':
    main()
