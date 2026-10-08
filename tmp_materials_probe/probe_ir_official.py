"""收尾探测A：ir 文件是什么；顺带把镜像 role 快照存档。

并测试官方站 insert（0990 June 2024）是否公开可下载。"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:/Users/weo/Desktop/api/examdata/src")
from examdata.core.config import Settings
from examdata.core.fetch import Fetcher

OUT = Path(r"C:/Users/weo/Desktop/api/tmp_materials_probe")
fetcher = Fetcher(Settings())

# --- ir 文件 ---
name = "0620_s16_ir_51.pdf"
r = fetcher.get(f"https://cie.fraft.cn/obj/Common/Fetch/redir/{name}", expect_binary=True, follow_redirects=False)
info = {"http": r.status, "bytes": len(r.content or b"")}
if r.content:
    info["sha256"] = hashlib.sha256(r.content).hexdigest()
    (OUT / "downloads" / name).write_bytes(r.content)
    # 抽取 PDF 元数据字符串（不解析文本层，只看 metadata/标题线索）
    head = r.content[:4000].decode("latin-1", errors="replace")
    titles = re.findall(r"/Title\s*\(([^)]{0,120})", head)
    info["pdf_titles"] = titles
    # 全文件里搜关键词
    blob = r.content.decode("latin-1", errors="replace")
    for kw in ["Insert", "Inserted", "Periodic", "Data Booklet", "Formula", "Instructions", "Supervisor"]:
        info[f"kw_{kw}"] = blob.count(kw)
print("ir:", json.dumps(info, ensure_ascii=False, indent=1))

# --- 官方 insert ---
official = ("https://www.cambridgeinternational.org/Images/603004-june-2024-insert-paper-11.pdf")
r2 = fetcher.get(official, expect_binary=True, follow_redirects=False)
o = {"url": official, "http": r2.status, "error": r2.error, "bytes": len(r2.content or b"")}
if r2.content:
    o["sha256"] = hashlib.sha256(r2.content).hexdigest()
    o["magic"] = r2.content[:8].decode("latin-1")
    (OUT / "downloads" / "official_0990_june2024_insert_p11.pdf").write_bytes(r2.content)
print("official insert:", json.dumps(o, ensure_ascii=False))

# --- 快照里 source_material 的科目分布 ---
snap = json.load(open(r"C:/Users/weo/Desktop/api/cie_all_discovery.json", encoding="utf-8"))
sm = [r for r in snap["resources"] if r.get("doc_type") == "source_material"]
subj = {}
for r in sm:
    subj.setdefault(r.get("subject_code"), []).append(r.get("url"))
print("\nsource_material 科目数:", len(subj))
for k, v in sorted(subj.items()):
    print(k, len(v), v[0][:100])
