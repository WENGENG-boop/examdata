import os, json, hashlib, datetime

TARGET = r"C:\Users\weo\Desktop\api\tmp_specprobe"
BATCH = r"C:\Users\weo\Desktop\api\cie-location-batch"
SPECS = r"C:\Users\weo\Desktop\api\examdata\.data\specs\pdfs"
MANIFEST = os.path.join(BATCH, "work", "audit_stray_sweep_manifest.txt")
CLEANUP = os.path.join(BATCH, "cleanup.jsonl")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


pairs = [
    ("ial18-biology-spec.pdf", "ial18-biology-0.pdf"),
    ("ial18-maths-spec.pdf", "ial18-mathematics-0.pdf"),
]
for src_name, dst_name in pairs:
    src = os.path.join(TARGET, src_name)
    dst = os.path.join(SPECS, dst_name)
    assert os.path.isfile(src), src
    assert os.path.isfile(dst), dst
    hs, hd = sha256(src), sha256(dst)
    assert hs == hd, (src, dst, hs, hd)
    print("copy verified:", src_name, hs)

files = []
for name in sorted(os.listdir(TARGET)):
    p = os.path.join(TARGET, name)
    ap = os.path.abspath(p)
    assert ap.startswith(os.path.abspath(TARGET) + os.sep), ap
    st = os.lstat(p)
    assert not os.path.islink(p), p
    if hasattr(st, "st_reparse_tag"):
        assert st.st_reparse_tag == 0, p
    assert os.path.isfile(p), p
    files.append((ap, st.st_size))

total = sum(s for _, s in files)
exts = {}
for ap, _ in files:
    ext = os.path.splitext(ap)[1].lower()
    exts[ext] = exts.get(ext, 0) + 1

deleted, failures = [], []
for ap, s in files:
    try:
        os.remove(ap)
        deleted.append(ap)
    except OSError as e:
        failures.append({"path": ap, "error": str(e)})

deleted_set = set(deleted)
freed = sum(s for ap, s in files if ap in deleted_set)

dirs_removed = 0
if os.path.isdir(TARGET) and not os.listdir(TARGET):
    os.rmdir(TARGET)
    dirs_removed = 1

residual_bytes = 0
if os.path.exists(TARGET):
    for r, d, fs in os.walk(TARGET):
        for f in fs:
            try:
                residual_bytes += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass

status = "deleted" if not failures else ("partial" if deleted else "failed")

with open(MANIFEST, "w", encoding="utf-8") as f:
    for ap, s in files:
        f.write(f"{ap}\t{s}\n")
    f.write(
        f"# total_files={len(files)} total_bytes={total} deleted={len(deleted)} "
        f"freed_bytes={freed} residual_bytes={residual_bytes}\n"
    )

now = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
rec = {
    "stage": "audit_stray_sweep",
    "key": "*",
    "at": now,
    "target": TARGET,
    "label": "tmp_specprobe",
    "note": "临时规格探针残留（2026-10-02 规格 PDF 探查）；两个 PDF 原件副本已确认存在于 examdata/.data/specs/pdfs（SHA256 一致），txt 提取文本副本在 .data/specs/text/",
    "status": status,
    "deleted": len(deleted),
    "freed_bytes": freed,
    "dirs_removed": dirs_removed,
    "exts": exts,
    "failures": failures,
    "residual_bytes": residual_bytes,
    "files_sample": [ap for ap, _ in files],
    "files_manifest": MANIFEST,
}
summary = {
    "stage": "audit_stray_sweep_summary",
    "at": now,
    "targets": 1,
    "sum_deleted": len(deleted),
    "sum_freed_bytes": freed,
    "status_counts": {status: 1},
    "manifest": MANIFEST,
}
with open(CLEANUP, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.write(json.dumps(summary, ensure_ascii=False) + "\n")

print(json.dumps({
    "status": status, "deleted": len(deleted), "freed_bytes": freed,
    "residual_bytes": residual_bytes, "dirs_removed": dirs_removed,
    "failures": failures,
}, ensure_ascii=False))
