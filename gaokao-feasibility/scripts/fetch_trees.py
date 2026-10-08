"""Fetch recursive git trees for known Gaokao paper collections from GitHub."""

import json
import pathlib
import urllib.request

REPOS = [
    "deekur/gaokaomath",
    "deekur/gaokaophysics",
    "Zaxaerith/GaokaoCHN",
    "Zaxaerith/GaokaoENG",
    "Zaxaerith/GaokaoGEO",
    "qingshuo/China-Gaokao-Papers-Collection",
]
OUT = pathlib.Path(__file__).resolve().parent.parent / "logs" / "trees"


def get(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "gaokao-probe/1.0", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for repo in REPOS:
        info = get(f"https://api.github.com/repos/{repo}")
        branch = info["default_branch"]
        tree = get(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
        slug = repo.replace("/", "__")
        payload = {
            "repo": repo,
            "default_branch": branch,
            "stars": info["stargazers_count"],
            "pushed_at": info["pushed_at"],
            "license": (info.get("license") or {}).get("spdx_id"),
            "truncated": tree.get("truncated"),
            "tree": tree.get("tree", []),
        }
        (OUT / f"{slug}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"{repo}: branch={branch} stars={info['stargazers_count']} "
              f"pushed={info['pushed_at'][:10]} entries={len(tree.get('tree', []))}")


if __name__ == "__main__":
    main()
