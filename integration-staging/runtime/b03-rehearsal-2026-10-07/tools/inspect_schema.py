import json
import sys
from pathlib import Path

CANDIDATE = Path(__file__).resolve().parents[3] / \
    "runtime" / "b02-rehearsal-20261006" / "candidates" / "b02-shared-config-v1"

sys.path.insert(0, str(CANDIDATE / "src"))
sys.dont_write_bytecode = True

qt = json.loads((CANDIDATE / "contracts" / "quality-transitions.json").read_text(encoding="utf-8"))
ik = json.loads((CANDIDATE / "contracts" / "identity-keys.json").read_text(encoding="utf-8"))

print("quality-transitions.json top keys:", sorted(qt.keys()))
print("quality-transitions.dimensions type:", type(qt.get("dimensions")).__name__)
if isinstance(qt.get("dimensions"), dict):
    dims = qt["dimensions"]
    print("dimension names:", sorted(dims.keys()))
    for name, spec in sorted(dims.items()):
        if isinstance(spec, dict):
            print("  ", name, "keys:", sorted(spec.keys()), "values:", spec.get("values"))
        else:
            print("  ", name, "->", spec)

print()
print("identity-keys.json top keys:", sorted(ik.keys()))
print("kind names:", sorted((ik.get("kinds") or {}).keys()) if isinstance(ik.get("kinds"), dict) else ik.get("kinds"))

print()
from examdata.integration.contracts import enums as enums_mod
print("enums module names:", [n for n in dir(enums_mod) if not n.startswith("_")])
from examdata.integration.contracts import quality as quality_mod
print("quality module names:", [n for n in dir(quality_mod) if not n.startswith("_")])
print("quality.DIMENSIONS:", getattr(quality_mod, "DIMENSIONS", None))

for name in dir(enums_mod):
    obj = getattr(enums_mod, name)
    if isinstance(obj, type) and hasattr(obj, "__members__"):
        print("Enum", name, "->", list(obj.__members__.keys()))
