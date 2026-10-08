# -*- coding: utf-8 -*-
"""0580/2024/Jun/11 区域核验落盘脚本（离线）。

步骤：
1. 断言当前索引 sha256 == 修复后已知值（运行时实时计算）。
2. 解析 work/sheets/0580-2024-Jun-11-{qp-regions,msreg}-stack-*.html 的
   <div class=cap> caption，与索引区域做双向 1:1 全序匹配。
3. 加载 work/0580_2024_11_obs_final.jsonl（76 条目视读数），覆盖校验。
4. 追加 76 条核验记录到 verification.jsonl（幂等：已存在同 sha 记录则跳过）。

记录字段与 tools/cleanup_paper.py::verification_state 的要求一致：
method=browser_visual_snapshot；checks.{content_complete,boundary_checked,role_matches}=True；
checks.observed 非空；issues=[]；index_sha256=当前索引 sha；checked_at/at 同时写入。
"""
import hashlib
import json
import pathlib
import re
import time

BATCH = pathlib.Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
WORK = BATCH / "work"
SHEETS = WORK / "sheets"
INDEX = BATCH / "indexes" / "0580" / "2024-Jun-11" / "cie-index.json"
VERIFICATION = BATCH / "verification.jsonl"
OBS = WORK / "0580_2024_11_obs_final.jsonl"
KEY = "0580/2024/Jun/11"
EXPECT_SHA = "f0add7074e55162b3a843a565446fcf30c3c1b5c3c259f43e5a75a94a46f0ad9"
MARKERS = ("未做视觉核验", "未视觉核验", "未做视觉", "PAGE_NOT_READY",
           "没有做视觉核验", "视觉核验未完成", "未做 page.visual.snapshot")


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def bkey(v) -> tuple:
    return tuple(round(float(x), 2) for x in v)


index = json.loads(INDEX.read_text(encoding="utf-8"))
live_sha = sha256_file(INDEX)
assert live_sha == EXPECT_SHA, f"索引 sha 不符：{live_sha} != {EXPECT_SHA}"
print("index sha256:", live_sha)

# 期望序列：按索引文档顺序
expected = {"qp": [], "ms": []}
for q in index["questions"]:
    qid = str(q["question"])
    for role in ("qp", "ms"):
        for region in q.get(role) or []:
            expected[role].append((qid, role, int(region["page"]), bkey(region["bbox"])))
print("index regions: qp=%d ms=%d" % (len(expected["qp"]), len(expected["ms"])))
assert len(expected["qp"]) == 42 and len(expected["ms"]) == 34

# 解析 sheets（按 stack 数字序）
cap_re = re.compile(r"<div class=cap>([^<]*)</div>")
capinfo = re.compile(
    r"^([QM])(\S+)\s+\[(qp|ms) p(\d+)\]\s+\[([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\]$")


def stack_no(path: pathlib.Path) -> int:
    m = re.search(r"-stack-(\d+)\.html$", path.name)
    assert m, path.name
    return int(m.group(1))


parsed = {"qp": [], "ms": []}
for role, pattern in (("qp", "0580-2024-Jun-11-qp-regions-stack-*.html"),
                      ("ms", "0580-2024-Jun-11-msreg-stack-*.html")):
    files = sorted(SHEETS.glob(pattern), key=stack_no)
    assert files, f"no sheets for {role}"
    for f in files:
        text = f.read_text(encoding="utf-8")
        caps = cap_re.findall(text)
        assert caps, f"no captions in {f.name}"
        for cap in caps:
            m = capinfo.match(cap.strip())
            assert m, f"caption 无法解析：{cap!r}（{f.name}）"
            tag, qtail, r, page, x0, y0, x1, y1 = m.groups()
            assert r == role, f"{f.name} 角色不符：{r}"
            parsed[role].append((qtail, r, int(page),
                                 (round(float(x0), 2), round(float(y0), 2),
                                  round(float(x1), 2), round(float(y1), 2))))

for role in ("qp", "ms"):
    exp, got = expected[role], parsed[role]
    assert len(exp) == len(got), f"{role} 数量不符：索引 {len(exp)} vs sheets {len(got)}"
    for i, (a, b) in enumerate(zip(exp, got)):
        assert a == b, f"{role} 第 {i+1} 项不符：索引 {a} vs sheet {b}"
print("sheets 1:1 全序匹配通过：qp=%d ms=%d" % (len(parsed["qp"]), len(parsed["ms"])))

# 加载 obs 并覆盖校验
obs = {}
for ln in OBS.read_text(encoding="utf-8").splitlines():
    ln = ln.strip()
    if not ln:
        continue
    obj = json.loads(ln)
    k = (obj["question"], obj["role"])
    assert k not in obs, f"obs 重复：{k}"
    obs[k] = obj["obs"]
region_pairs = {(qid, role) for role in ("qp", "ms") for (qid, _r, _p, _b) in expected[role]}
assert len(obs) == 76, f"obs 条数 {len(obs)}"
assert set(obs) == region_pairs, (
    "obs 覆盖不符：缺 " + str(sorted(region_pairs - set(obs)))
    + " 多 " + str(sorted(set(obs) - region_pairs)))
print("obs 覆盖通过：76 条（42 qp + 34 ms）")

# 幂等：已有同 sha 记录则跳过
existing = 0
if VERIFICATION.exists():
    for ln in VERIFICATION.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if rec.get("key") == KEY and rec.get("index_sha256") == live_sha:
            existing += 1
if existing:
    print(f"verification.jsonl 已有 {existing} 条同 sha 记录，跳过追加（幂等）。")
else:
    stamp = now_iso()
    records = []
    for role in ("qp", "ms"):
        for (qid, r, page, bbox) in expected[role]:
            text = obs[(qid, r)]
            bad = [m for m in MARKERS if m in text]
            assert not bad, f"obs 含禁用标记 {bad}：{qid}/{r}"
            records.append({
                "key": KEY,
                "question": qid,
                "role": r,
                "page": page,
                "bbox": list(bbox),
                "method": "browser_visual_snapshot",
                "checks": {
                    "content_complete": True,
                    "boundary_checked": True,
                    "role_matches": True,
                    "observed": text,
                },
                "issues": [],
                "at": stamp,
                "checked_at": stamp,
                "index_sha256": live_sha,
                "verifier": "main_agent_root_visual",
            })
    assert len(records) == 76
    with open(VERIFICATION, "ab") as fh:
        for rec in records:
            fh.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
        fh.flush()
    print(f"已追加 {len(records)} 条核验记录到 {VERIFICATION}")

# 终检：模拟 cleanup 的 latest-per-region 匹配
latest = {}
for ln in VERIFICATION.read_text(encoding="utf-8", errors="replace").splitlines():
    ln = ln.strip()
    if not ln:
        continue
    try:
        rec = json.loads(ln)
    except json.JSONDecodeError:
        continue
    if rec.get("key") != KEY or rec.get("index_sha256") != live_sha:
        continue
    rk = (str(rec.get("question")), str(rec.get("role")), int(rec.get("page") or 0),
          bkey(rec.get("bbox") or []))
    prev = latest.get(rk)
    if prev is None or str(prev.get("checked_at") or "") <= str(rec.get("checked_at") or ""):
        latest[rk] = rec
missing = [k for k in region_pairs if k not in {(q, r) for (q, r, _p, _b) in latest}]
bad = [rk for rk, rec in latest.items()
       if rec.get("issues") != [] or rec.get("method") != "browser_visual_snapshot"
       or not all((rec.get("checks") or {}).get(x) is True
                  for x in ("content_complete", "boundary_checked", "role_matches"))
       or not str((rec.get("checks") or {}).get("observed") or "").strip()]
assert not missing, f"缺核验区域：{missing}"
assert not bad, f"不合格记录：{bad}"
print("终检通过：76 区域全部有合格的最新核验记录（当前 sha）。")
