"""Dump review entries for the remaining undecided low-confidence questions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "tmp_r11_lowconf_review.json").read_text(encoding="utf-8"))
qids = [68324, 68343, 68412, 68414, 68440, 68471, 68472, 68555, 68563, 68494]
for item in data:
    if item.get("question_id") in qids:
        print("=" * 70)
        print(json.dumps(item, ensure_ascii=False, indent=1))
