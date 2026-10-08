"""只读比较 before/after 两份 MS 索引快照。

用法: python tmp_ms_diff.py <before.json> <after.json> [--verbose]
"""
import json
import sys


def load(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {r["ms_id"]: r for r in data["results"]}


def main() -> None:
    before = load(sys.argv[1])
    after = load(sys.argv[2])
    verbose = "--verbose" in sys.argv

    only_before = sorted(set(before) - set(after))
    only_after = sorted(set(after) - set(before))
    changed = []
    regressions = []
    gains = []
    for ms_id in sorted(set(before) & set(after)):
        b, a = before[ms_id], after[ms_id]
        bn = b.get("n_index", -1)
        an = a.get("n_index", -1)
        bp = set(b.get("paths") or [])
        ap = set(a.get("paths") or [])
        if bn != an or bp != ap or b.get("source") != a.get("source") or b.get("error") != a.get("error"):
            entry = {
                "ms_id": ms_id,
                "ms_doc": b["ms_doc"],
                "qp_doc": b["qp_doc"],
                "before_n": bn,
                "after_n": an,
                "before_src": b.get("source"),
                "after_src": a.get("source"),
                "before_err": b.get("error"),
                "after_err": a.get("error"),
                "added": sorted(ap - bp),
                "removed": sorted(bp - ap),
            }
            changed.append(entry)
            if an < bn:
                regressions.append(entry)
            elif an > bn:
                gains.append(entry)

    print(f"records: before={len(before)} after={len(after)}")
    print(f"only in before: {len(only_before)} {only_before[:20]}")
    print(f"only in after: {len(only_after)} {only_after[:20]}")
    print(f"changed: {len(changed)}  gains: {len(gains)}  regressions: {len(regressions)}")
    print()
    print("== REGRESSIONS (n_index decreased) ==")
    for e in regressions:
        print(
            f"ms={e['ms_id']} doc={e['ms_doc']} qp={e['qp_doc']} "
            f"n {e['before_n']}->{e['after_n']} src {e['before_src']}->{e['after_src']}"
        )
        if e["removed"]:
            print(f"    removed paths: {e['removed']}")
        if e["added"]:
            print(f"    added paths:   {e['added']}")
        if e["before_err"] or e["after_err"]:
            print(f"    err {e['before_err']} -> {e['after_err']}")
    print()
    print("== GAINS (n_index increased) ==")
    for e in gains:
        print(
            f"ms={e['ms_id']} doc={e['ms_doc']} qp={e['qp_doc']} "
            f"n {e['before_n']}->{e['after_n']} src {e['before_src']}->{e['after_src']}"
        )
        if e["added"]:
            print(f"    added paths:   {e['added']}")
        if e["removed"]:
            print(f"    removed paths: {e['removed']}")
    print()
    others = [e for e in changed if e not in gains and e not in regressions]
    print(f"== OTHER CHANGES (same n, paths/src/err differ): {len(others)} ==")
    for e in others:
        print(
            f"ms={e['ms_id']} doc={e['ms_doc']} qp={e['qp_doc']} "
            f"n={e['before_n']} src {e['before_src']}->{e['after_src']}"
        )
        if e["removed"]:
            print(f"    removed paths: {e['removed']}")
        if e["added"]:
            print(f"    added paths:   {e['added']}")
        if e["before_err"] or e["after_err"]:
            print(f"    err {e['before_err']} -> {e['after_err']}")

    if verbose:
        print()
        print("== ALL CHANGED ==")
        for e in changed:
            print(json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    main()
