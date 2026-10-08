# -*- coding: utf-8 -*-
# 官方 PDF 答案 vs pte/iprog 抓取答案 逐题比对
# 覆盖：剑3 T1 (pte + iprog), 剑3 T2-T4 (iprog), 剑4 T1-T4 (pte)
import json, re, subprocess, sys
import pymupdf

BASE = 'C:/Users/weo/Desktop/api/tmp_audit_ielts'
IELTS = 'C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api'

# ---------- 1. 从官方 PDF 提取听力答案 ----------
def extract_pdf_listening(book):
    doc = pymupdf.open(f'{BASE}/downloads/book_{book}.pdf')
    pages = []
    for i in range(doc.page_count):
        pages.append((i + 1, doc[i].get_text()))
    doc.close()
    # 找所有 "TEST N" + "LISTENING" 块
    blocks = {}
    for idx, (pno, t) in enumerate(pages):
        for m in re.finditer(r'TEST\s+(\d)\s*\n+\s*LISTENING', t):
            test = int(m.group(1))
            # 块从 m.end() 到下一个 "TEST N"/"ACADEMIC READING" 或页尾
            start = m.end()
            rest = t[start:]
            # 结束标记
            endm = re.search(r'\n\s*(TEST\s+\d|ACADEMIC READING|GENERAL TRAINING)', rest)
            body = rest[:endm.start()] if endm else rest
            # 续到下一页（若本页截断）：若块里题目 < 40，拼接后续页直到出现结束标记
            qs = parse_entries(body)
            j = idx + 1
            while len(qs) < 40 and j < len(pages):
                nxt = pages[j][1]
                endm2 = re.search(r'\n\s*(TEST\s+\d|ACADEMIC READING|GENERAL TRAINING|Answer key)', nxt)
                body2 = nxt[:endm2.start()] if endm2 else nxt
                qs2 = parse_entries(body2)
                for k, v in qs2.items():
                    if k not in qs: qs[k] = v
                j += 1
                if endm2: break
            blocks[test] = qs
    return blocks

def parse_entries(body):
    """解析 'N  value' 条目（含跨行续行）"""
    out = {}
    lines = body.split('\n')
    cur = None
    for ln in lines:
        m = re.match(r'^\s*(\d{1,2})\s{2,}(\S.*)$', ln)
        if m and 1 <= int(m.group(1)) <= 40:
            cur = int(m.group(1))
            out[cur] = m.group(2).strip()
        elif cur is not None and ln.strip() and not re.match(r'^\s*(Section|Reading Passage|If you score)', ln):
            out[cur] += ' ' + ln.strip()
        elif re.match(r'^\s*(Section|Reading Passage)', ln):
            cur = None
    return out

# ---------- 2. 规范化与匹配 ----------
def norm(s):
    s = str(s).lower()
    s = s.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    s = re.sub(r'[^a-z0-9/ ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def variants(raw):
    out = set()
    for p in re.split(r'//|/| accept |\bor\b', raw, flags=re.I):
        p = p.strip()
        if not p: continue
        out.add(norm(p))
        out.add(norm(re.sub(r'\([^)]*\)', ' ', p)))       # 去括号
        out.add(norm(re.sub(r'[()]', '', p)))              # 仅去括号符
    out.add(norm(raw))
    return {v for v in out if v}

def matches(pte_ans, official_raw):
    if pte_ans is None: return None
    p = norm(pte_ans)
    if not p: return False
    vs = variants(official_raw)
    # EITHER ORDER 特例：官方收集所有单字母
    if 'either order' in official_raw.lower():
        letters = set(re.findall(r'\b([A-H])\b', official_raw.upper()))
        pl = set(re.findall(r'\b([A-H])\b', str(pte_ans).upper()))
        return letters == pl and bool(pl)
    for v in vs:
        if p == v or (len(p) >= 2 and p in v) or (len(v) >= 2 and v in p):
            return True
    # 多词时允许 token 子集
    pt = set(p.split())
    if len(pt) > 1:
        for v in vs:
            vt = set(v.split())
            if pt and pt <= vt:
                return True
    return False

# ---------- 3. 取抓取答案（node 实时拉取） ----------
node_code = """
const ielts = await import('file:///""" + IELTS + """/ielts-api.mjs');
const iprog = await import('file:///""" + IELTS + """/iprog.mjs');
const out = { pte: {}, iprog: {} };
for (const b of [3, 4]) for (const t of [1,2,3,4]) {
  const r = await ielts.pteListening(b, t);
  out.pte[`${b}-${t}`] = { ok: r.ok, slug: r.slug || null, answers: r.answer_key || null, count: r.answer_count, err: r.error || null };
}
for (const t of [1,2,3,4]) {
  const r = await iprog.listeningAnswers(3, t);
  out.iprog[`3-${t}`] = { ok: r.ok, answers: r.answer_key || null, count: r.answer_count, url: r.url, err: r.error || null };
}
console.log(JSON.stringify(out));
"""
res = subprocess.run(['node', '--input-type=module', '-e', node_code], capture_output=True, text=True, encoding='utf-8', cwd=BASE)
if res.returncode != 0:
    print('NODE FAIL:', res.stderr[-2000:]); sys.exit(1)
fetched = json.loads(res.stdout.strip().splitlines()[-1])
json.dump(fetched, open(f'{BASE}/official_cmp_fetched.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------- 4. 比对 ----------
def compare(name, official, got_list, n=40):
    match = 0; tot = 0; diffs = []
    for q in range(1, n + 1):
        o = official.get(q)
        g = got_list[q - 1] if got_list and q - 1 < len(got_list) else None
        if o is None or g is None: continue
        tot += 1
        r = matches(g, o)
        if r: match += 1
        else: diffs.append((q, o, g))
    print(f'{name}: {match}/{tot}')
    for q, o, g in diffs[:10]:
        print(f'    Q{q} official={o!r}  got={g!r}')
    return match, tot, diffs

print('===== 剑3 =====')
b3 = extract_pdf_listening(3)
for t in [1, 2, 3, 4]:
    off = b3.get(t, {})
    print(f'-- PDF 剑3 T{t}: {len(off)} answers extracted')
    if t == 1:
        compare(f'pte(3,{t}) vs PDF', off, fetched['pte']['3-1']['answers'])
    compare(f'iprog(3,{t}) vs PDF', off, fetched['iprog'][f'3-{t}']['answers'])

print('===== 剑4 =====')
b4 = extract_pdf_listening(4)
for t in [1, 2, 3, 4]:
    off = b4.get(t, {})
    print(f'-- PDF 剑4 T{t}: {len(off)} answers extracted')
    compare(f'pte(4,{t}) vs PDF', off, fetched['pte'][f'4-{t}']['answers'])
