"""端到端真调用：CIE 工坊 + Pearson 官方。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from examdata.paperqa import query, resolve  # noqa: E402

OUT = Path(__file__).resolve().parent / "e2e"
OUT.mkdir(exist_ok=True)

_n = 0


def fresh():
    global _n
    _n += 1
    d = OUT / f"r{_n:02d}"
    d.mkdir(exist_ok=True)
    return d


def show(tag, r):
    print(f"--- {tag} ---")
    for d in r.documents:
        print(f"  doc {d.role:3} paper={d.paper:10} {d.name}")
    for f in r.files:
        print(f"  file {f.name}  {len(f.data)} bytes  {f.media_type}  role={f.role}")
    return r


# 1. CIE resolve（不下载）
show("CIE resolve 9709/2026/Mar/12", resolve("cie", "9709", 2026, "Mar", "12", mode="qp"))

# 2. CIE qp
r = show("CIE qp", query("cie", "9709", 2026, "Mar", "12", mode="qp", out_dir=fresh()))
assert r.files[0].data.startswith(b"%PDF-"), "CIE qp 不是 PDF"
print("  magic ok:", r.files[0].data[:8])

# 3. CIE both
r = show("CIE both", query("cie", "9709", 2026, "Mar", "12", mode="both", out_dir=fresh()))
print("  roles:", sorted(f.role for f in r.files))

# 4. Edexcel resolve
show(
    "EDEXCEL resolve Economics/2024/Jun/wec11-01",
    resolve("edexcel", "Economics", 2024, "Jun", "wec11-01", mode="paper"),
)

# 5. Edexcel paper
r = show(
    "EDEXCEL paper",
    query("edexcel", "Economics", 2024, "Jun", "wec11-01", mode="paper", out_dir=fresh()),
)
print("  magic ok:", r.files[0].data[:8], "size:", len(r.files[0].data))

# 6. Edexcel question
for q in ("1", "12(a)", "12"):
    try:
        r = show(
            f"EDEXCEL question {q}",
            query("edexcel", "Economics", 2024, "Jun", "wec11-01", q, "question", out_dir=fresh()),
        )
        print("  PNG magic ok:", r.files[0].data[:8])
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED {type(exc).__name__}: {exc}")

# 7. Edexcel qa
try:
    r = show(
        "EDEXCEL qa 1",
        query("edexcel", "Economics", 2024, "Jun", "wec11-01", "1", "qa", out_dir=fresh()),
    )
    print("  roles:", sorted(f.role for f in r.files))
except Exception as exc:  # noqa: BLE001
    print(f"  FAILED {type(exc).__name__}: {exc}")

print("--- saved ---")
for p in sorted(OUT.iterdir()):
    print(f"  {p.name}  {p.stat().st_size}")
