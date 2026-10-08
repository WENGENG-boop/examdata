import json, os, sys

def load(path):
    raw = open(path, 'rb').read()
    d = json.loads(raw.decode('utf-8'))
    baseline = (json.dumps(d, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    assert baseline == raw, f'roundtrip mismatch for {path}'
    return d

def save(path, d):
    out = (json.dumps(d, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    tmp = path + '.tmp-edit'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, path)

STD = 'text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声'

def sanity(d, tag):
    for q in d['questions']:
        for role in ('qp', 'ms'):
            for r in q[role]:
                b = r['bbox']
                assert b[0] < b[2] and b[1] < b[3], (tag, q['question'], role, b)
    print(tag, 'questions:', len(d['questions']),
          'regions:', sum(len(q['qp']) + len(q['ms']) for q in d['questions']))

# ================= Volume A (21) =================
PA = 'indexes/0472/2026-Jun-21/cie-index.json'
dA = load(PA)
qsA = dA['questions']
byA = {q['question']: q for q in qsA}

if '6(h)(i)' not in byA:
    print('A already edited, skipping')
else:
    q6h = byA['6(h)']
    assert q6h['qp'] == [{'page': 13, 'bbox': [92.4, 278.8, 540.4, 402.4]}], q6h['qp']
    assert q6h['ms'] == [{'page': 8, 'bbox': [76.4, 546.0, 534.0, 569.2]}], q6h['ms']
    t = q6h['text']
    print('A 6(h) text repr tail:', repr(t[-60:]))
    assert '\uff08 0' in t, repr(t)
    h_part, i_part = t.split('\uff08 0', 1)
    h_part = h_part.rstrip()
    assert h_part == '(h) H ow did Martha feel about the cat she made?', repr(h_part)
    i_new = '(i)' + i_part
    assert i_new == '(i) What did Martha and her grandma b0th enj oy most about their day? [TOta \u4e0a 11 ]', repr(i_new)
    q6h['qp'][0]['bbox'] = [92.4, 278.8, 540.4, 340.0]
    q6h['text'] = h_part

    q6i = byA['6(h)(i)']
    assert q6i['parent'] == '6(h)'
    assert q6i['qp'] == [{'page': 13, 'bbox': [92.4, 340.0, 540.4, 402.4]}], q6i['qp']
    assert q6i['ms'] == []
    q6i['question'] = '6(i)'
    q6i['parent'] = '6'
    q6i['text'] = i_new
    q6i['ms'] = [{'page': 8, 'bbox': [76.4, 569.2, 534.0, 583.2]}]
    q6i['uncertain'] = False
    q6i['notes'] = STD + '（说明继承自父题 6）'

    save(PA, dA)
    print('A saved')
sanity(dA, 'A')

# ================= Volume B (22) =================
PB = 'indexes/0472/2026-Jun-22/cie-index.json'
dB = load(PB)
qsB = dB['questions']
byB = {q['question']: q for q in qsB}

if '6(h)(i)' not in byB:
    print('B already edited, skipping')
else:
    # 1. parent 1: qp p3 x0 112.8 -> 92.4
    q1 = byB['1']
    r3 = [x for x in q1['qp'] if x['page'] == 3][0]
    assert r3['bbox'] == [112.8, 16.4, 540.4, 734.4], r3
    r3['bbox'][0] = 92.4

    # 2. 1(a): drop p3 region; ms bottom -> 110.5; split text at ' DFD '
    qa = byB['1(a)']
    assert qa['qp'][1]['page'] == 3 and qa['qp'][1]['bbox'] == [112.8, 16.4, 540.4, 403.7], qa['qp']
    qa['qp'] = [x for x in qa['qp'] if x['page'] == 2]
    assert qa['qp'] == [{'page': 2, 'bbox': [71.2, 83.6, 393.6, 444.0]}], qa['qp']
    assert qa['ms'] == [{'page': 6, 'bbox': [76.4, 87.6, 472.8, 190.4]}], qa['ms']
    qa['ms'][0]['bbox'][3] = 110.5
    t = qa['text']
    assert ' DFD ' in t, repr(t)
    ap, bp = t.split(' DFD ', 1)
    assert ap.endswith('D the staff'), repr(ap[-40:])
    assert bp.startswith('Tomorrow S match:'), repr(bp[:40])
    assert bp.endswith('D Parents can watch their children play.'), repr(bp[-50:])
    qa['text'] = ap
    b_text = '(b) ' + bp
    print('B 1(b) text len:', len(b_text))

    # 3. new 1(b) after 1(a)
    new_b = {
      'question': '1(b)',
      'parent': '1',
      'text': b_text,
      'marks': None,
      'qp': [{'page': 3, 'bbox': [92.4, 58.7, 540.4, 403.7]}],
      'ms': [{'page': 6, 'bbox': [76.4, 110.5, 472.8, 133.5]}],
      'uncertain': False,
      'notes': STD + '（说明继承自父题 1）',
    }
    i = qsB.index(qa)
    qsB.insert(i + 1, new_b)

    # 4. 1(c): qp x0 -> 92.4; ms fill; uncertain false; notes standard
    qc = byB['1(c)']
    assert qc['qp'] == [{'page': 3, 'bbox': [112.8, 403.7, 540.4, 734.4]}], qc['qp']
    qc['qp'][0]['bbox'][0] = 92.4
    assert qc['ms'] == []
    qc['ms'] = [{'page': 6, 'bbox': [76.4, 133.5, 472.8, 190.4]}]
    qc['uncertain'] = False
    qc['notes'] = STD + '（说明继承自父题 1）'

    # 5. 3(a): qp bottom -> 447.4; split text at ' A arranges '
    q3a = byB['3(a)']
    assert q3a['qp'] == [{'page': 6, 'bbox': [70.8, 302.3, 527.6, 592.7]}], q3a['qp']
    q3a['qp'][0]['bbox'][3] = 447.4
    t = q3a['text']
    assert ' A arranges ' in t, repr(t)
    ap, bp = t.split(' A arranges ', 1)
    assert ap == '(a) A correct B useful C favourite D usual', repr(ap)
    assert bp == 'B sta rts C prepares D makes', repr(bp)
    q3a['text'] = ap

    # 6. new 3(b) after 3(a)
    new_3b = {
      'question': '3(b)',
      'parent': '3',
      'text': '(b) A arranges ' + bp,
      'marks': None,
      'qp': [{'page': 6, 'bbox': [70.8, 447.4, 527.6, 592.7]}],
      'ms': [{'page': 6, 'bbox': [76.4, 408.0, 472.8, 430.8]}],
      'uncertain': False,
      'notes': STD + '（说明继承自父题 3）',
    }
    i = qsB.index(q3a)
    qsB.insert(i + 1, new_3b)

    # 7. 3(c): drop p7 region; split text
    q3c = byB['3(c)']
    assert q3c['qp'] == [{'page': 6, 'bbox': [70.8, 592.7, 527.6, 698.4]},
                         {'page': 7, 'bbox': [92.4, 16.4, 540.4, 494.4]}], q3c['qp']
    q3c['qp'] = [x for x in q3c['qp'] if x['page'] == 6]
    t = q3c['text']
    assert ' DFD ' in t, repr(t)
    cp, rest = t.split(' DFD ', 1)
    assert cp == '(c) A place B route C method D reason', repr(cp)
    d_part, rest2 = rest.split(' A exact ', 1)
    e_part, f_part = rest2.split(' A enter ', 1)
    assert d_part == 'A just B ever C already D rather', repr(d_part)
    assert e_part == 'B accu rate C perfect D SerlOUS', repr(e_part)
    assert f_part == 'B belong C appear D continue', repr(f_part)
    q3c['text'] = cp

    # 8. new 3(d)(e)(f) after 3(c)
    new_3d = {
      'question': '3(d)', 'parent': '3', 'text': '(d) ' + d_part, 'marks': None,
      'qp': [{'page': 7, 'bbox': [92.4, 58.6, 540.4, 203.8]}],
      'ms': [{'page': 6, 'bbox': [76.4, 454.0, 472.8, 477.2]}],
      'uncertain': False, 'notes': STD + '（说明继承自父题 3）',
    }
    new_3e = {
      'question': '3(e)', 'parent': '3', 'text': '(e) A exact ' + e_part, 'marks': None,
      'qp': [{'page': 7, 'bbox': [92.4, 203.8, 540.4, 349.0]}],
      'ms': [{'page': 6, 'bbox': [76.4, 477.2, 472.8, 500.0]}],
      'uncertain': False, 'notes': STD + '（说明继承自父题 3）',
    }
    new_3f = {
      'question': '3(f)', 'parent': '3', 'text': '(f) A enter ' + f_part, 'marks': None,
      'qp': [{'page': 7, 'bbox': [92.4, 349.0, 540.4, 494.4]}],
      'ms': [{'page': 6, 'bbox': [76.4, 500.0, 472.8, 522.8]}],
      'uncertain': False, 'notes': STD + '（说明继承自父题 3）',
    }
    i = qsB.index(q3c)
    qsB[i + 1:i + 1] = [new_3d, new_3e, new_3f]

    # 9. 4(h): qp bottom -> 401.2; split text
    q4h = byB['4(h)']
    assert q4h['qp'] == [{'page': 9, 'bbox': [92.4, 340.0, 540.4, 462.4]}], q4h['qp']
    q4h['qp'][0]['bbox'][3] = 401.2
    t = q4h['text']
    print('B 4(h) text repr tail:', repr(t[-50:]))
    assert '\uff08 0' in t, repr(t)
    h_part, i_part = t.split('\uff08 0', 1)
    h_part = h_part.rstrip()
    assert h_part == "(h) What is Pedro's mother's jOb?", repr(h_part)
    i_new = '(i)' + i_part
    assert i_new == '(i) H OW is Rosa going tO help Pedro?', repr(i_new)
    q4h['text'] = h_part

    # 10. 4(h)(i) -> 4(i)
    q4i = byB['4(h)(i)']
    assert q4i['parent'] == '4(h)'
    assert q4i['qp'] == [{'page': 9, 'bbox': [92.4, 401.2, 540.4, 462.4]}], q4i['qp']
    assert q4i['ms'] == []
    q4i['question'] = '4(i)'
    q4i['parent'] = '4'
    q4i['text'] = i_new
    q4i['ms'] = [{'page': 7, 'bbox': [76.0, 426.4, 534.0, 461.2]}]
    q4i['uncertain'] = False
    q4i['notes'] = STD + '（说明继承自父题 4）'

    # 11. 6(h): qp bottom -> 401.2; split text
    q6hB = byB['6(h)']
    assert q6hB['qp'] == [{'page': 13, 'bbox': [92.4, 340.0, 540.4, 463.6]}], q6hB['qp']
    assert q6hB['ms'] == [{'page': 8, 'bbox': [76.4, 570.0, 534.0, 604.8]}], q6hB['ms']
    q6hB['qp'][0]['bbox'][3] = 401.2
    t = q6hB['text']
    print('B 6(h) text repr tail:', repr(t[-60:]))
    assert '\uff08 0' in t, repr(t)
    h_part, i_part = t.split('\uff08 0', 1)
    h_part = h_part.rstrip()
    assert h_part == '(h) What problem did Nancie have at the restau ra nt?', repr(h_part)
    i_new = '(i)' + i_part
    assert i_new == '(i) What did Liza dO tO thank her friends for the surprise? [TOta \u4e0a 11 ]', repr(i_new)
    q6hB['text'] = h_part

    # 12. 6(h)(i) -> 6(i)
    q6iB = byB['6(h)(i)']
    assert q6iB['parent'] == '6(h)'
    assert q6iB['qp'] == [{'page': 13, 'bbox': [92.4, 401.2, 540.4, 463.6]}], q6iB['qp']
    assert q6iB['ms'] == []
    q6iB['question'] = '6(i)'
    q6iB['parent'] = '6'
    q6iB['text'] = i_new
    q6iB['ms'] = [{'page': 8, 'bbox': [76.4, 604.8, 534.0, 630.4]}]
    q6iB['uncertain'] = False
    q6iB['notes'] = STD + '（说明继承自父题 6）'

    save(PB, dB)
    print('B saved')
sanity(dB, 'B')

print('B order:', [q['question'] for q in dB['questions']][:12])
print('B order mid:', [q['question'] for q in dB['questions']][12:24])
print('B order tail:', [q['question'] for q in dB['questions']][-10:])
print('A order tail:', [q['question'] for q in dA['questions']][-4:])
