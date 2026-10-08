import json
import re
from pathlib import Path

ROOT = Path("C:/Users/weo/Desktop/api")
RAW = ROOT / "ielts-data/raw"

def meta_of(sub, h):
    d_dir = RAW / sub
    cands = [d_dir / f"{h}.meta.json", d_dir / f"{h}.json"]
    for cand in cands:
        if cand.exists():
            try:
                d = json.loads(cand.read_text(encoding="utf-8"))
            except Exception as e:
                return f"unreadable {e}"
            keep = {k: d.get(k) for k in
                    ("url", "source_url", "site", "slug", "page_id", "title",
                     "captured_at", "stored_at", "source_pdf", "book", "test") if k in d}
            return keep or list(d.keys())[:12]
    return "(no meta)"

for sub, hs in {
    "pdf-extract": ["055a11759267f328f5dd95347c75599cb148991f8560ec596844e4b5b24dba49",
                    "199de15e604b687d639eecca32df5169de0916185ab7588651818c49abc23e1f",
                    "78e730826a7cb5585a7708225bc8012a3c1359fe2b8e2c908d201d64d265651f",
                    "bd86f1bcee6d8dc0028c13bbaefb32a9583ce4db22dc756297945e080fddab77"],
    "ieltstrainingonline.com": ["a57bd226ecc49000fdb5af9d082ad3ab3f928506d2735c52602e2bce45217294"],
}.items():
    print("DIR", sub, "entries:", [p.name[:50] for p in (RAW / sub).glob("*") if p.name.startswith(("055a", "199d", "78e7", "bd86", "a57b"))][:20])
    for h in hs:
        print("=", sub, h[:12], "meta:", meta_of(sub, h))

def ctx(path, pat, n=150, limit=8, label=""):
    s = path.read_text(encoding="utf-8", errors="replace")
    print("--", label or path.name, "len", len(s))
    cnt = 0
    for m in re.finditer(pat, s, re.I):
        cnt += 1
        if cnt > limit:
            break
        a, b = max(0, m.start() - n), min(len(s), m.end() + n)
        print("   ...", s[a:b].replace("\n", " ")[:330])
    print("   total matches:", len(re.findall(pat, s, re.I)))

ctx(RAW / "pdf-extract" / "055a11759267f328f5dd95347c75599cb148991f8560ec596844e4b5b24dba49.body",
    r"erosion|beach")
ctx(RAW / "pdf-extract" / "055a11759267f328f5dd95347c75599cb148991f8560ec596844e4b5b24dba49.body",
    r"costwise|argus|holman|743002|pavement")
ctx(RAW / "ieltstrainingonline.com" / "a57bd226ecc49000fdb5af9d082ad3ab3f928506d2735c52602e2bce45217294.body",
    r"erosion|beach")
ctx(RAW / "ieltstrainingonline.com" / "a57bd226ecc49000fdb5af9d082ad3ab3f928506d2735c52602e2bce45217294.body",
    r"costwise|argus|holman|743002|electric wire|wooden post")

p = ROOT / "tmp_audit_ielts/completeness_20261003/pte-11-1-listening.json"
ctx(p, r"erosion", n=180, limit=6)
