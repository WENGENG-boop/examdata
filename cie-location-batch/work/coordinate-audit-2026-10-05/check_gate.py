"""只读复算 cleanup_paper 的门槛条件（六项），打印 JSON 供人工核对。

用法：python check_gate.py "8386/2025/Jun/11" "0495/2026/Jun/11"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BATCH_TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(BATCH_TOOLS))

import cleanup_paper as C  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="复算清理门槛条件（只读）")
    parser.add_argument("keys", nargs="+")
    args = parser.parse_args()
    out = {}
    for key in args.keys:
        problems, info = C.check_conditions(key)
        out[key] = {"pass": not problems, "problems": problems, "info": info}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
