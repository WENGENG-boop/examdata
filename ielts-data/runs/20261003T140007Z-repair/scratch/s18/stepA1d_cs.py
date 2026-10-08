import re

for fp in (152, 153):
    raw = open(f"ielts-data/runs/20261003T140007Z-repair/scratch/s18/fp{fp}-content.txt", "rb").read()
    # tokenize text ops: track Tf, Tm/Td/TD/T*, and Tj/TJ strings
    # crude approach: split on BT/ET blocks and scan
    txt = raw.decode("latin1")
    print(f"===== fp{fp} content stream (len {len(raw)}) =====")
    # show all Tf ops
    for m in re.finditer(r"/(TT\d|C2_\d)\s+([\d.]+)\s+Tf", txt):
        pass
    # find blocks: locate each '/TTx size Tf' and capture until next Tf
    parts = re.split(r"(/(?:TT\d|C2_\d)\s+[\d.]+\s+Tf)", txt)
    for i in range(1, len(parts), 2):
        head = parts[i]
        body = parts[i+1] if i+1 < len(parts) else ""
        # find string ops in body
        strs = re.findall(r"\((?:[^()\\]|\\.)*\)\s*Tj|\[(?:[^\[\]]*)\]\s*TJ|<([0-9A-Fa-f]+)>\s*Tj", body)
        # collect all parenthesized strings
        allstr = re.findall(r"\(((?:[^()\\]|\\.)*)\)", body)
        if not allstr: continue
        # take first few
        show = allstr[:6]
        # also capture Tm/Td coords before first string
        first = body.find("(")
        pre = body[:first]
        coords = re.findall(r"([-\d.]+)\s+([-\d.]+)\s+(?:Td|TD)|([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+Tm", pre)
        c = coords[-1] if coords else None
        print(f"  {head.strip()[:14]:14s} nstr={len(allstr)} first={show!r} coord={c}")
