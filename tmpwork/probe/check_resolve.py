"""单独复现 /paper-qa/resolve 的 edexcel qa 调用，打印状态与 schema。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402
from examdata.api.app import app  # noqa: E402

params = {"board": "edexcel", "subject": "Economics", "year": 2024, "season": "Jun",
          "paper": "wec11-01", "question": "12(a)", "mode": "qa"}

with TestClient(app) as client:
    for attempt in range(3):
        r = client.get("/paper-qa/resolve", params=params)
        body = r.json()
        print(f"attempt {attempt}: {r.status_code} keys={sorted(body)} "
              f"files={body.get('files', 'ABSENT') if isinstance(body.get('files'), list) else body.get('detail')}")
        if r.status_code == 200:
            print("  counts:", body["counts"], "documents:",
                  [d["name"] for d in body["documents"]])
            break
