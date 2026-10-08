# -*- coding: utf-8 -*-
"""Inventory the 19 validation_partial keys: blocking problems per key (read-only). One-off."""
import json
import sys

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import cleanup_paper as C

KEYS = [
    "0472/2025/Jun/12", "0472/2025/Jun/21", "0472/2025/Jun/22",
    "0472/2026/Jun/12", "0472/2026/Jun/21", "0472/2026/Jun/22",
    "8238/2024/Nov/11", "8238/2024/Nov/12", "8238/2024/Nov/13",
    "8238/2024/Nov/21", "8238/2024/Nov/22",
    "8238/2025/Jun/12",
    "8238/2025/Nov/11", "8238/2025/Nov/12", "8238/2025/Nov/13",
    "8238/2025/Nov/31", "8238/2025/Nov/32", "8238/2025/Nov/33",
    "8238/2026/Jun/22",
]

for key in KEYS:
    problems, info = C.check_conditions(key)
    v = info.get("verification", {})
    print(f"=== {key}  stage={info.get('stage')} ===")
    print(f"  regions={v.get('regions')} verified={v.get('verified')} failed={v.get('failed')} "
          f"missing={v.get('missing')} self_unverified={v.get('self_declared_unverified')} "
          f"numbering={v.get('numbering')}")
    for p in problems:
        print(f"  ! {p}")
