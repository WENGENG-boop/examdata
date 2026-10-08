"""核对 11 个 validation_partial 卷的当前状态：索引 mtime、tmp 原件、stage、关键字段。"""
import json
import os
import sys
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
sys.path.insert(0, str(BR / "tools"))
os.chdir(BR)

import batchlib as B  # noqa: E402
import paperlib as P  # noqa: E402
import pipelinestate as S  # noqa: E402

KEYS = [
    "8238/2024/Nov/11", "8238/2024/Nov/12", "8238/2024/Nov/13",
    "8238/2025/Nov/11", "8238/2025/Nov/12", "8238/2025/Nov/13",
    "8238/2026/Jun/22",
    "0472/2025/Jun/21", "0472/2025/Jun/22",
    "0472/2026/Jun/21", "0472/2026/Jun/22",
]

import datetime


def mtime(p: Path) -> str:
    try:
        t = p.stat().st_mtime
        return datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M:%S")
    except OSError:
        return "-"


for key in KEYS:
    subject, year, season, paper = key.split("/")
    idx = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    tmp = P.paper_tmp(key)
    pdfs = sorted(p.name for p in tmp.glob("*.pdf")) if tmp.is_dir() else []
    parts = sorted(p.name for p in tmp.glob("*.part")) if tmp.is_dir() else []
    entry, source = S.entry(key)
    entry = entry or {}
    doc = json.loads(idx.read_bytes().decode("utf-8")) if idx.is_file() else {}
    nq = len(doc.get("questions") or [])
    print(f"== {key}  stage={entry.get('stage')!r}  src={source}")
    print(f"   idx mtime={mtime(idx)}  questions={nq}")
    print(f"   tmp pdf={pdfs}  part={parts}")
    print(f"   import_succeeded={entry.get('import_succeeded')}  readback={entry.get('readback_verified')}  service_index={entry.get('service_index_path')}")
    print(f"   stage_at={entry.get('stage_at')}  service_stage_at={entry.get('service_stage_at')}")
