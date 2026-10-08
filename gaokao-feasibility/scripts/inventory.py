"""Parse fetched repo trees into a flat downloadable inventory (2024-2026 focus)."""

import csv
import json
import pathlib
import re
import urllib.parse
from collections import Counter, defaultdict

BASE = pathlib.Path(__file__).resolve().parent.parent
TREES = BASE / "logs" / "trees"
OUT_CSV = BASE / "logs" / "inventory.csv"
OUT_SUMMARY = BASE / "logs" / "inventory-summary.txt"

SUBJECT_BY_REPO = {
    "deekur/gaokaomath": "数学",
    "deekur/gaokaophysics": "物理",
    "Zaxaerith/GaokaoCHN": "语文",
    "Zaxaerith/GaokaoENG": "英语",
    "Zaxaerith/GaokaoGEO": "地理",
}
SUBJECT_WORDS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理", "日语", "俄语", "技术", "科学"]
YEARS = ("2024", "2025", "2026")


def detect_subject(path: str, repo: str) -> str:
    if repo in SUBJECT_BY_REPO:
        return SUBJECT_BY_REPO[repo]
    parts = path.split("/")
    if repo.startswith("qingshuo") and len(parts) > 3:
        return parts[3]
    for w in SUBJECT_WORDS:
        if w in path:
            return w
    return ""


def main() -> None:
    rows = []
    summary_lines = []
    for tree_file in sorted(TREES.glob("*.json")):
        data = json.loads(tree_file.read_text(encoding="utf-8"))
        repo, branch = data["repo"], data["default_branch"]
        blobs = [t for t in data["tree"] if t["type"] == "blob"]
        recent = [t for t in blobs if any(y in t["path"] for y in YEARS)]
        summary_lines.append(
            f"# {repo} stars={data['stars']} pushed={data['pushed_at'][:10]} "
            f"license={data['license']} blobs={len(blobs)} recent2024-26={len(recent)}"
        )
        for t in recent:
            path = t["path"]
            url = (
                f"https://raw.githubusercontent.com/{repo}/{branch}/"
                + urllib.parse.quote(path)
            )
            m = re.search(r"(20\d\d)", path)
            rows.append(
                {
                    "repo": repo,
                    "path": path,
                    "size": t.get("size", ""),
                    "year": m.group(1) if m else "",
                    "subject": detect_subject(path, repo),
                    "url": url,
                }
            )
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["repo", "year", "subject", "path", "size", "url"])
        writer.writeheader()
        writer.writerows(rows)

    # summary: qingshuo region x subject counts for 2024-2026
    q = [r for r in rows if r["repo"].startswith("qingshuo")]
    grid = defaultdict(Counter)
    for r in q:
        parts = r["path"].split("/")
        region = parts[2] if len(parts) > 2 else "?"
        grid[r["year"]][f"{region}/{r['subject']}"] += 1
    for y in YEARS:
        summary_lines.append(f"\n## qingshuo {y} region/subject counts")
        for key, n in sorted(grid.get(y, {}).items()):
            summary_lines.append(f"  {key}: {n}")

    # deekur recent filenames
    for repo in ("deekur/gaokaomath", "deekur/gaokaophysics"):
        summary_lines.append(f"\n## {repo} 2024-2026 files")
        for r in sorted([r for r in rows if r["repo"] == repo], key=lambda x: (x["year"], x["path"])):
            summary_lines.append(f"  {r['year']} {r['size']:>8} {r['path']}")

    # Zaxaerith recent filenames
    for repo in ("Zaxaerith/GaokaoCHN", "Zaxaerith/GaokaoENG", "Zaxaerith/GaokaoGEO"):
        summary_lines.append(f"\n## {repo} 2024-2026 files")
        for r in sorted([r for r in rows if r["repo"] == repo], key=lambda x: (x["year"], x["path"])):
            summary_lines.append(f"  {r['year']} {r['size']:>8} {r['path']}")

    OUT_SUMMARY.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"inventory rows: {len(rows)} -> {OUT_CSV}")
    print(f"summary -> {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
