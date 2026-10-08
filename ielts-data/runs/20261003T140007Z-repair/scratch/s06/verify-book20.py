# verify-book20.py — 校验剑20 4 个分册：magic/页数/Test 身份/题号范围/sha256
import hashlib, json, os, re, shutil, sys
import fitz

ROOT = "C:/Users/weo/Desktop/api"
SRC = os.path.join(ROOT, "ielts-data/raw/pdf-source")
OUT = os.path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair/evidence/S06-book20-verify.json")

# test1 复制进受控位置（来源为历史目录，只读复制）
t1_src = os.path.join(ROOT, "tmp_audit_ielts/downloads/book_20.pdf")
t1_dst = os.path.join(SRC, "book20-test1.pdf")
if not os.path.exists(t1_dst) and os.path.exists(t1_src):
    shutil.copyfile(t1_src, t1_dst)

out = {"files": {}, "all_ok": True}
for k in ["test1", "test2", "test3", "test4"]:
    p = os.path.join(SRC, f"book20-{k}.pdf")
    rec = {"path": p}
    try:
        buf = open(p, "rb").read()
        rec["bytes"] = len(buf)
        rec["sha256"] = hashlib.sha256(buf).hexdigest()
        rec["magic"] = buf[:5].decode("latin1")
        doc = fitz.open(p)
        rec["pages"] = doc.page_count
        text_head = "".join(doc[i].get_text() for i in range(min(4, doc.page_count)))
        rec["test_title_hits"] = sorted(set(re.findall(r"Test\s*[1-4]", text_head)))
        full = "".join(doc[i].get_text() for i in range(doc.page_count))
        rec["text_chars"] = len(full)
        qs = sorted(set(int(m) for m in re.findall(r"(?m)^\s*(\d{1,2})\s*$", full) if 1 <= int(m) <= 42))
        rec["max_q_seen"] = max(qs) if qs else None
        rec["has_listening"] = bool(re.search(r"LISTENING|Listening", full))
        rec["has_reading"] = bool(re.search(r"READING|Reading", full))
        rec["has_writing"] = bool(re.search(r"WRITING|Writing", full))
        rec["has_speaking"] = bool(re.search(r"SPEAKING|Speaking", full))
        # Test 身份：从首几页找 "Test N"
        rec["ok"] = rec["magic"].startswith("%PDF") and rec["pages"] > 0
    except Exception as e:
        rec["ok"] = False
        rec["error"] = str(e)
    out["files"][k] = rec
    out["all_ok"] = out["all_ok"] and rec.get("ok", False)
    print(k, json.dumps({kk: rec.get(kk) for kk in ["pages", "test_title_hits", "max_q_seen", "has_listening", "has_reading", "has_writing", "has_speaking", "sha256"]}, ensure_ascii=False))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ALL_OK=", out["all_ok"], "->", OUT)
