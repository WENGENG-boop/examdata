# -*- coding: utf-8 -*-
# 独立审查：Python 交叉计数（与 Node vm 解析独立实现）
import re, json, io, sys

DIR = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/cam21/"

def biggest_script(html):
    blocks = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, re.I)
    return max(blocks, key=len) if blocks else ""

def extract_literal(src, name, open_ch="{"):
    close_ch = "}" if open_ch == "{" else "]"
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*" + re.escape(open_ch), src)
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    in_str = None
    esc = False
    start = i
    while i < len(src):
        ch = src[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return src[start:]

def count_top_level_keys(lit):
    """统计 depth==1 处的 ':' 个数（顶层键值对数量），字符串感知"""
    if not lit:
        return 0
    depth = 0
    in_str = None
    esc = False
    n = 0
    for ch in lit:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == ":" and depth == 1:
            n += 1
    return n

out = {"reading": {}, "listening": {}, "totals": {}}
r_total = l_total = t_total = a_total = 0
for t in [1, 2, 3, 4]:
    rh = open(DIR + f"t{t}-reading.html", encoding="utf-8").read()
    rs = biggest_script(rh)
    answers_lit = extract_literal(rs, "ANSWERS")
    questions_lit = extract_literal(rs, "QUESTIONS", "[")
    r_keys = count_top_level_keys(answers_lit)
    q_count = len(re.findall(r"\{id:\d+", questions_lit or ""))
    out["reading"][t] = {"answers_top_keys": r_keys, "questions_by_id": q_count}
    r_total += r_keys

    lh = open(DIR + f"t{t}-listening.html", encoding="utf-8").read()
    ls = biggest_script(lh)
    ca = extract_literal(ls, "correctAnswers")
    mc = extract_literal(ls, "multiCorrect")
    tr = extract_literal(ls, "TRANSCRIPTS")
    at = extract_literal(ls, "audioTracks")
    ca_n = count_top_level_keys(ca)
    mc_n = count_top_level_keys(mc)
    tr_lines = len(re.findall(r'"sp"\s*:', tr or ""))
    tr_time = len(re.findall(r'"t"\s*:', tr or ""))
    audio_n = len(re.findall(r"C21T\d_Section_\d\.mp3", at or ""))
    out["listening"][t] = {"correctAnswers": ca_n, "multiCorrect": mc_n, "transcript_sp": tr_lines,
                           "transcript_t": tr_time, "audio_files": audio_n}
    l_total += ca_n + mc_n
    t_total += tr_lines
    a_total += audio_n

out["totals"] = {"reading_answers": r_total, "listening_ca_plus_mc": l_total,
                 "transcript_lines": t_total, "audio_files": a_total}
print(json.dumps(out, indent=2))
json.dump(out, open(DIR + "py_count_result.json", "w"), indent=2)
