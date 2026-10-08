#!/usr/bin/env python
"""Rebuild logs/commands.log from the append-only session wire log.

Every tool call in the session is listed with timestamp, tool name, target
(cwd for shell commands), arguments, exit code where the runtime reports one,
and the output as returned by the runtime (truncated with an explicit marker;
the full text remains in the session wire log, referenced at the top).

Pre-root recon commands (before the review-fix root existed) are reconstructed
from the same wire log; their "recorded-at" time is this rebuild.

Usage: python build_command_log.py [wire.jsonl]
"""
from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timezone

RUN = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_WIRE = pathlib.Path(
    "C:/Users/weo/.kimi-code/sessions/wd_workspace_84e5c391e01d/"
    "session_137e0ce9-dba9-4c48-92f6-a25d04029325/agents/main/wire.jsonl"
)
OUT = RUN / "logs/commands.log"
BASH_OUTPUT_CAP = 8000
OTHER_OUTPUT_CAP = 400
EXIT_RE = re.compile(r"Command failed with exit code: (\d+)")


def iso(ms: int | None) -> str:
    if ms is None:
        return "unknown"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def brief(value, cap: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= cap else text[: cap - 3] + "..."


def main() -> int:
    import sys

    wire = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WIRE
    calls: dict[str, dict] = {}
    order: list[str] = []
    results: dict[str, dict] = {}

    for line in wire.read_text(encoding="utf-8").splitlines():
        if '"tool.call"' not in line and '"tool.result"' not in line:
            continue
        rec = json.loads(line)
        if rec.get("type") != "context.append_loop_event":
            continue
        ev = rec.get("event", {})
        rec_time = rec.get("time")
        if ev.get("type") == "tool.call":
            cid = ev.get("toolCallId")
            calls[cid] = {"ev": ev, "time": rec_time}
            order.append(cid)
        elif ev.get("type") == "tool.result":
            results[ev.get("toolCallId")] = {"ev": ev, "time": rec_time}

    built = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("COMMAND AUDIT LOG -- run b07-reviewfix-20261007-fzgu78c6")
    lines.append("============================================================")
    lines.append(f"snapshot_built_utc: {built}")
    lines.append(f"source_wire: {wire}")
    lines.append(f"root_created_utc: 2026-10-07T01:04:05Z (mkdir b07-reviewfix-20261007-fzgu78c6)")
    lines.append("note: entries before the root existed are pre-root recon, reconstructed from the")
    lines.append("      append-only session wire; the runtime's returned output is recorded verbatim")
    lines.append("      up to the cap, truncation is marked inline. The rebuilding command itself is")
    lines.append("      not part of its own snapshot; the next rebuild includes it.")
    lines.append("exit_code: parsed from the runtime line 'Command failed with exit code: N'; for")
    lines.append("           shell calls without that line the command succeeded (exit 0); 'n/a' for")
    lines.append("           non-shell tools, whose output is summarized here and fully kept in wire.")
    lines.append("")

    bash_n = other_n = 0
    for cid in order:
        entry = calls[cid]
        ev = entry["ev"]
        name = ev.get("name", "?")
        res_entry = results.get(cid)
        res = (res_entry or {}).get("ev")
        output = (res or {}).get("result", {}).get("output", "")
        ts = iso(entry["time"])
        cid_short = (cid or "?")[:14]
        if name == "Bash":
            bash_n += 1
            cwd = (ev.get("display") or {}).get("cwd", "?")
            command = (ev.get("args") or {}).get("command", brief(ev.get("args")))
            m = EXIT_RE.search(output)
            exit_code = m.group(1) if m else "0"
            shown = output
            truncated = ""
            if len(shown) > BASH_OUTPUT_CAP:
                shown = shown[:BASH_OUTPUT_CAP]
                truncated = f"\n...[truncated {len(output) - BASH_OUTPUT_CAP} chars; full output in session wire log]"
            lines.append(f"--- [{ts}] BASH #{bash_n} (call {cid_short}) exit={exit_code}")
            lines.append(f"cwd: {cwd}")
            lines.append(f"cmd: {command}")
            lines.append("out:")
            lines.append(shown.rstrip("\n") + truncated)
            lines.append("")
        else:
            other_n += 1
            shown = output if len(output) <= OTHER_OUTPUT_CAP else output[:OTHER_OUTPUT_CAP] + "...[cap]"
            lines.append(
                f"--- [{ts}] {name} (call {cid_short}) args={brief(ev.get('args'))} "
                f"out={brief(shown, OTHER_OUTPUT_CAP)}"
            )

    lines.append("")
    lines.append(f"totals: {bash_n} shell commands, {other_n} other tool calls")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({bash_n} shell, {other_n} other)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
