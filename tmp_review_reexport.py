"""Re-export review batches with per-subject batch sizes tuned so each batch stays readable (~<=130KB)."""
import pathlib
import shutil
import subprocess
import sys

SIZES = {
    "ial-accounting": 25, "ial-englang": 100, "ial-englit": 60, "ial-french": 90,
    "ial-geography": 36, "ial-german": 63, "ial-greek": 100, "ial-history": 18,
    "ial-law": 22, "ial-maths": 26, "ial-psychology": 55, "ial-spanish": 100,
    "ial18-biology": 50, "ial18-business": 15, "ial18-chemistry": 100,
    "ial18-economics": 16, "ial18-it": 100, "ial18-mathematics": 24, "ial18-physics": 69,
}


def main() -> None:
    root = pathlib.Path(".data/tagging/review-export")
    for slug, size in SIZES.items():
        d = root / slug
        if (d / "batches").exists():
            shutil.rmtree(d / "batches")
        proc = subprocess.run(
            [sys.executable, "-m", "examdata.tagging", "review-export", "--subject", slug,
             "--out", str(d), "--batch-size", str(size), "--json"],
            capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            print("FAIL", slug, proc.stderr[-500:])
            continue
    items = []
    total = 0
    for slug in sorted(SIZES):
        bs = sorted((root / slug / "batches").glob("batch-*.jsonl"))
        n = sum(sum(1 for _ in f.open(encoding="utf-8")) for f in bs)
        total += n
        mx = max((f.stat().st_size for f in bs), default=0)
        print(f"{slug:28s} batches={len(bs):3d} items={n:5d} maxKB={mx // 1024:4d}")
        items += [f"{slug}/{f.stem}" for f in bs]
    pathlib.Path("tmp_review_items.txt").write_text("\n".join(items) + "\n", encoding="utf-8")
    print("TOTAL batches:", len(items), "items:", total)


if __name__ == "__main__":
    main()
