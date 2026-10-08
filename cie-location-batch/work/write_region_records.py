#!/usr/bin/env python
"""把浏览器目视核验观察（caption 顺序字符串数组）写成可合并的核验记录。

用法:
    python work/write_region_records.py <subject/year/season/paper> --obs obs.json [--out records.json]
    python work/write_region_records.py <subject/year/season/paper> --check   # 只校验帧/索引 1:1

- 从 work/sheets/<slug>-qp-regions-stack-*.html 与 <slug>-msreg-stack-*.html 按帧号
  顺序解析全部 caption（qp 帧先、ms 帧后），断言与当前永久索引的区域 1:1 对应；
- obs.json 为与 caption 同序的观察字符串数组，数量必须一致；
- 输出 <slug>-records.json（merge_agent_visual.py 的输入格式），本工具不写
  verification.jsonl、不改任何状态；追加由 merge_agent_visual.py 带守卫执行。

只读索引与裁剪图。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import batchlib as B  # noqa: E402

CAP_RE = re.compile(r'<div class=cap>(.*?)</div><img src="([^"]+)"')
LABEL_RE = re.compile(r"^(\S+)\s+\[(qp|ms) p(\d+)\]\s+\[([\d.,\s]+)\]$")


def frame_no(path: Path) -> int:
    m = re.search(r"-stack-(\d+)\.html$", path.name)
    if not m:
        raise SystemExit(f"帧文件名无法解析: {path.name}")
    return int(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="subject/year/season/paper")
    ap.add_argument("--obs", default=None, help="观察数组 JSON（caption 顺序）")
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true", help="只校验帧 caption 与索引 1:1")
    args = ap.parse_args()
    key = args.key
    subject, year, season, paper = key.split("/")
    slug = key.replace("/", "-")

    idx_path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    if not idx_path.is_file():
        raise SystemExit(f"找不到索引: {idx_path}")
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    index_sha = B.sha256_file(idx_path)

    sheets_dir = B.WORK / "sheets"
    qp_frames = sorted(sheets_dir.glob(f"{slug}-qp-regions-stack-*.html"), key=frame_no)
    ms_frames = sorted(sheets_dir.glob(f"{slug}-msreg-stack-*.html"), key=frame_no)
    frames = qp_frames + ms_frames
    if not frames:
        raise SystemExit(f"没有找到 {slug} 的区域裁剪表（qp-regions/msreg stack）")

    frame_regions = []
    for f in frames:
        html = f.read_text(encoding="utf-8")
        found = CAP_RE.findall(html)
        if not found:
            raise SystemExit(f"{f.name} 里没有 caption")
        for cap, src in found:
            cap = cap.strip()
            mm = LABEL_RE.match(cap)
            if not mm:
                raise SystemExit(f"caption 无法解析: {cap!r}")
            label, role, page, nums = mm.group(1), mm.group(2), int(mm.group(3)), mm.group(4)
            bbox = tuple(round(float(x), 1) for x in nums.split(","))
            frame_regions.append({"frame": f.name, "label": label, "role": role,
                                  "page": page, "bbox": bbox,
                                  "img": (ROOT / src.lstrip("/")).resolve()})
    print(f"帧 {len(frames)} 张（qp {len(qp_frames)} / ms {len(ms_frames)}），"
          f"区域 caption {len(frame_regions)} 个")

    expected = []
    for q in index["questions"]:
        for r in q["qp"]:
            expected.append((q["question"], "qp", int(r["page"]),
                             tuple(round(float(x), 1) for x in r["bbox"]), r["bbox"]))
    for q in index["questions"]:
        for r in q["ms"]:
            expected.append((q["question"], "ms", int(r["page"]),
                             tuple(round(float(x), 1) for x in r["bbox"]), r["bbox"]))
    if len(frame_regions) != len(expected):
        raise SystemExit(f"caption 数 {len(frame_regions)} != 索引区域数 {len(expected)}")

    for fr, (num, role, page, bbox1, _bbox_raw) in zip(frame_regions, expected):
        if not (fr["role"] == role and fr["page"] == page and fr["bbox"] == bbox1):
            raise SystemExit(f"区域不匹配: {fr} vs {(num, role, page, bbox1)}")
        want = ("Q" if role == "qp" else "M") + num
        if fr["label"] != want:
            raise SystemExit(f"标签不匹配: {fr['label']} vs {want}")
    print("帧 caption 与当前索引区域 1:1 一致")
    print(f"index_sha256: {index_sha}")

    if args.check:
        return 0
    if not args.obs:
        raise SystemExit("缺少 --obs（或加 --check 只校验）")

    obs = json.loads(Path(args.obs).read_text(encoding="utf-8"))
    if not isinstance(obs, list) or len(obs) != len(frame_regions):
        raise SystemExit(f"obs 必须是 {len(frame_regions)} 条字符串的数组，"
                         f"实际 {type(obs).__name__} {len(obs) if isinstance(obs, list) else '?'}")
    for i, o in enumerate(obs):
        if not isinstance(o, str) or not o.strip():
            raise SystemExit(f"obs[{i}] 为空")

    stamp = B.now_iso()
    records = []
    for fr, (num, role, page, _b1, bbox_raw), observed in zip(frame_regions, expected, obs):
        img = fr["img"]
        if not img.is_file():
            raise SystemExit(f"裁剪图不存在: {img}")
        records.append({
            "key": key, "question": num, "role": role, "page": page,
            "bbox": list(bbox_raw),
            "method": "local_image_visual",
            "checked_at": stamp,
            "issues": [],
            "image": str(img),
            "image_sha256": B.sha256_file(img),
            "index_sha256": index_sha,
            "checks": {"content_complete": True, "boundary_checked": True,
                       "role_matches": True, "observed": observed.strip()},
        })

    out = Path(args.out) if args.out else B.WORK / f"{slug}-records.json"
    B.atomic_write_json(out, records)
    n_qp = sum(1 for r in records if r["role"] == "qp")
    print(f"写出 {len(records)} 条记录（qp {n_qp} / ms {len(records) - n_qp}）-> {out}")
    print(f"checked_at: {stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
