import re, sys
from pathlib import Path

base = Path("tmp_selfjudge/r2/ial18-mathematics")

def pack_qids(pack):
    txt = (base / f"{pack}.txt").read_text(encoding="utf-8")
    return [m[1] for m in re.findall(r"^\[(\d+)\] (\d+) ", txt, flags=re.M)]

def verify(pack, expect_data, expect_changes):
    raw = (base / f"{pack}.ans.txt").read_bytes()
    crlf = raw.count(b"\r\n")
    bare_lf = len(re.findall(rb"(?<!\r)\n", raw))
    text = raw.decode("utf-8").replace("\r\n", "\n")
    lines = text.split("\n")
    trailing = lines[-1] == ""
    body = lines[:-1] if trailing else lines
    header = [l for l in body if l.startswith("#")]
    data = [l for l in body if not l.startswith("#")]
    rows = []
    for l in data:
        parts = l.split(" ")
        assert len(parts) == 2, f"bad data line: {l!r}"
        rows.append((parts[0], parts[1]))

    print(f"== {pack} ==")
    print(f"lines(total)={len(body)} header_comments={len(header)} data={len(data)} crlf={crlf} bare_lf={bare_lf} trailing_empty={trailing}")

    assert len(data) == expect_data, f"expected {expect_data} data rows, got {len(data)}"
    qids = [q for q, c in rows]
    assert len(set(qids)) == len(qids), "duplicate qids!"
    pack_ids = pack_qids(pack)
    assert qids == pack_ids, f"pack order mismatch: ans={len(qids)} pack={len(pack_ids)}"

    # allowed codes from the pack file's unit code list
    pack_txt = (base / f"{pack}.txt").read_text(encoding="utf-8")
    allowed = set(re.findall(r"#\s+(WMA\d\d-\d+\.\d+):", pack_txt))
    bad = [(q, c) for q, c in rows if c != "OK" and c not in allowed]
    assert not bad, f"codes outside unit list: {bad}"

    non_ok = [(q, c) for q, c in rows if c != "OK"]
    print(f"non_ok count={len(non_ok)}")
    for q, c in non_ok:
        print(f"  {q} -> {c}")
    assert len(non_ok) == expect_changes, f"expected {expect_changes} non-OK, got {len(non_ok)}"
    print("ALL CHECKS PASSED")

verify("WMA14-p01", 150, 7)
print()
verify("WMA14-p02", 19, 0)
