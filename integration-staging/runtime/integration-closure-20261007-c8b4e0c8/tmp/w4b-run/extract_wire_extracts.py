"""W4b evidence: extract raw page.text.snapshot tool results from the agent event log.

Reads specific 1-based line numbers from wire.jsonl (append-only) and writes the
embedded tool-result string to evidence/w4b/extracts/line-<N>.txt.
"""
from __future__ import annotations

import json
import sys
from itertools import islice
from pathlib import Path

WIRE = Path(
    "C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/session_6b1562f5-c2e7-428a-bf9a-72619f246c2b/"
    "agents/agent-962/wire.jsonl"
)
OUT = Path(
    "C:/Users/weo/Desktop/api/integration-staging/runtime/integration-closure-20261007-c8b4e0c8/"
    "evidence/w4b/extracts"
)
LINES = [3433, 3526, 3545, 3564, 3640, 3867, 4239, 4270, 4273, 4275]


def find_texts(obj):
    if isinstance(obj, str):
        if "operation: page.text.snapshot" in obj:
            yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from find_texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from find_texts(v)


def main() -> None:
    sys.dont_write_bytecode = True
    OUT.mkdir(parents=True, exist_ok=True)
    # read the whole file once as lines (it is append-only; line numbers stay stable)
    with WIRE.open("r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    print(f"wire lines: {len(lines)}")
    for n in LINES:
        if n > len(lines):
            print(f"line {n}: OUT OF RANGE")
            continue
        try:
            obj = json.loads(lines[n - 1])
        except json.JSONDecodeError as exc:
            print(f"line {n}: JSON ERROR {exc}")
            continue
        texts = list(find_texts(obj))
        if not texts:
            print(f"line {n}: no text.snapshot string found")
            continue
        text = texts[-1]
        dest = OUT / f"line-{n}.txt"
        dest.write_text(text, encoding="utf-8", newline="\n")
        first = text.splitlines()[0][:60]
        print(f"line {n}: wrote {dest.name} ({len(text)} chars) | {first}")


if __name__ == "__main__":
    main()
