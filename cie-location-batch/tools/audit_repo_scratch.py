# -*- coding: utf-8 -*-
"""Read-only audit of repo scratch candidates (post-batch cleanup phase).

Checks, for each candidate dir:
  - exists / is reparse point (junction/symlink)
  - file count, total bytes, top extensions, mtime range, inner reparse points
Also: hash+fileid compare between one basetemp copy and .data/artifacts source,
root stray files of examdata/, batch + old-pilot + service media counts.
Writes a JSON report to BATCH_ROOT/work/audit_repo_scratch.json. Deletes nothing.
"""
import os, sys, json, glob, hashlib, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batchlib as B

E = "C:/Users/weo/Desktop/api/examdata"
A = "C:/Users/weo/Desktop/api"
SVC = E + "/.pytest_cache/callable-api"
PILOT = A + "/cie-index-batch-2026-10-01"
MEDIA = {".pdf", ".png", ".jpg", ".jpeg", ".zip", ".part", ".webp", ".gif"}


def iso(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def lmeta(p):
    try:
        st = os.lstat(p)
    except OSError:
        return None
    return {
        "mtime": iso(st.st_mtime),
        "is_dir": os.path.isdir(p),
        "reparse": bool(getattr(st, "st_file_attributes", 0) & 0x400),
    }


def walk_stats(root):
    if not os.path.exists(root):
        return {"exists": False}
    st0 = os.lstat(root)
    n = 0
    total = 0
    exts = {}
    mn = None
    mx = None
    reparse = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for d in list(dirnames):
            p = os.path.join(dirpath, d)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if getattr(st, "st_file_attributes", 0) & 0x400:
                reparse.append(p)
                dirnames.remove(d)
        for f in filenames:
            p = os.path.join(dirpath, f)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if getattr(st, "st_file_attributes", 0) & 0x400:
                reparse.append(p)
                continue
            n += 1
            total += st.st_size
            e = os.path.splitext(f)[1].lower() or "(none)"
            exts[e] = exts.get(e, 0) + 1
            if mn is None or st.st_mtime < mn:
                mn = st.st_mtime
            if mx is None or st.st_mtime > mx:
                mx = st.st_mtime
    return {
        "exists": True,
        "root_reparse": bool(getattr(st0, "st_file_attributes", 0) & 0x400),
        "files": n,
        "bytes": total,
        "exts": sorted(exts.items(), key=lambda kv: -kv[1])[:10],
        "mtime_min": iso(mn) if mn is not None else None,
        "mtime_max": iso(mx) if mx is not None else None,
        "inner_reparse_count": len(reparse),
        "inner_reparse_sample": reparse[:5],
    }


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def find_basename(root, name):
    for dirpath, dirnames, filenames in os.walk(root):
        if name in filenames:
            return os.path.join(dirpath, name)
    return None


report = {"generated_at": B.now_iso(), "targets": {}, "compare": {}, "batch": {}, "service": {}, "root_files": {}, "pilot": {}}

targets = sorted(glob.glob(E + "/.pytest_cache/examdata-tests-*"))
targets += [
    E + "/tmp_dl",
    E + "/tmp_sample_crops",
    E + "/tmp_final_crop",
    E + "/tmp_check_crops",
    E + "/tmp_selfjudge",
    E + "/pytest-of-weo",
    E + "/.pytest_cache/remaining-corpus",
    E + "/.pytest_cache/accept-corpus-final",
    E + "/.pytest_cache/remaining-portable",
    E + "/.pytest_cache/accept-portable-final",
    E + "/.pytest_cache/accept-portable",
    E + "/.data/artifacts",
    E + "/.data/specs",
    E + "/.data/samples",
    A + "/tmp_dl",
    A + "/cie-question-crops",
]

for t in targets:
    lm = lmeta(t)
    if lm is None:
        report["targets"][t] = {"exists": False}
        continue
    ws = walk_stats(t)
    ws["dir_mtime"] = lm["mtime"]
    ws["dir_reparse"] = lm["reparse"]
    report["targets"][t] = ws

# --- compare one basetemp copy against .data/artifacts (hardlink? copy? same content?) ---
art = E + "/.data/artifacts"
bts = sorted(glob.glob(E + "/.pytest_cache/examdata-tests-*"))
if bts and os.path.exists(art):
    bt = bts[0]
    # index artifact files by basename
    art_by_name = {}
    for dirpath, dirnames, filenames in os.walk(art):
        for f in filenames:
            art_by_name.setdefault(f, os.path.join(dirpath, f))
    pairs = []
    for dirpath, dirnames, filenames in os.walk(bt):
        for f in filenames:
            if f in art_by_name:
                pairs.append((os.path.join(dirpath, f), art_by_name[f]))
                break
        if pairs:
            break
    if pairs:
        p_copy, p_src = pairs[0]
        try:
            st_c = os.stat(p_copy)
            st_s = os.stat(p_src)
            report["compare"] = {
                "copy_path": p_copy,
                "src_path": p_src,
                "same_size": st_c.st_size == st_s.st_size,
                "same_file_id": (st_c.st_ino == st_s.st_ino and st_c.st_dev == st_s.st_dev),
                "sha_copy": sha256(p_copy),
                "sha_src": sha256(p_src),
            }
            report["compare"]["sha_equal"] = report["compare"]["sha_copy"] == report["compare"]["sha_src"]
        except OSError as e:
            report["compare"] = {"error": str(e), "copy_path": p_copy, "src_path": p_src}

# --- batch media / indexes / tmp bytes ---
batch = {"media": 0, "media_bytes": 0, "indexes": 0, "tmp_bytes": 0, "media_sample": []}
for dirpath, dirnames, filenames in os.walk(A + "/cie-location-batch"):
    for f in filenames:
        p = os.path.join(dirpath, f)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        dp = dirpath.replace("\\", "/")
        if os.path.splitext(f)[1].lower() in MEDIA:
            batch["media"] += 1
            batch["media_bytes"] += st.st_size
            if len(batch["media_sample"]) < 10:
                batch["media_sample"].append(p)
        if f == "cie-index.json" and "/indexes/" in dp + "/":
            batch["indexes"] += 1
        if "/tmp/" in dp + "/":
            batch["tmp_bytes"] += st.st_size
report["batch"] = batch

# --- service dir ---
svc = {"indexes_cie": len(glob.glob(SVC + "/question_indexes/cie/*.json")), "media": 0, "media_bytes": 0}
for dirpath, dirnames, filenames in os.walk(SVC):
    for f in filenames:
        if os.path.splitext(f)[1].lower() in MEDIA:
            p = os.path.join(dirpath, f)
            try:
                svc["media"] += 1
                svc["media_bytes"] += os.lstat(p).st_size
            except OSError:
                pass
report["service"] = svc

# --- old pilot media ---
pilot = {"files_total": 0, "media": 0, "media_bytes": 0, "media_sample": []}
if os.path.exists(PILOT):
    for dirpath, dirnames, filenames in os.walk(PILOT):
        for f in filenames:
            pilot["files_total"] += 1
            if os.path.splitext(f)[1].lower() in MEDIA:
                p = os.path.join(dirpath, f)
                try:
                    pilot["media"] += 1
                    pilot["media_bytes"] += os.lstat(p).st_size
                    if len(pilot["media_sample"]) < 10:
                        pilot["media_sample"].append(p)
                except OSError:
                    pass
report["pilot"] = pilot

# --- examdata root stray files + api root scratch ---
def top_files(root, limit=40):
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        if os.path.isfile(p):
            out.append({"name": name, "size": st.st_size, "mtime": iso(st.st_mtime)})
        if len(out) >= limit:
            break
    return out

report["root_files"]["examdata"] = top_files(E)
report["root_files"]["api"] = top_files(A)

# --- save + print ---
out = str(B.WORK) + "/audit_repo_scratch.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("saved:", out)
for k, v in report["targets"].items():
    print(k.replace(A + "/", ""), "|", json.dumps(v, ensure_ascii=False)[:300])
print("COMPARE:", json.dumps(report["compare"], ensure_ascii=False))
print("BATCH:", json.dumps(batch, ensure_ascii=False))
print("SERVICE:", json.dumps(svc, ensure_ascii=False))
print("PILOT:", json.dumps(pilot, ensure_ascii=False))
print("ROOT examdata:", json.dumps(report["root_files"]["examdata"], ensure_ascii=False))
print("ROOT api:", json.dumps(report["root_files"]["api"], ensure_ascii=False))
