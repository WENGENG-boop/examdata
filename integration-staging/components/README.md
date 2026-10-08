# Staged runtime components (A06)

This directory is the staging analogue of the installed runtime component
bundle described in `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §6.3. The
runner resolves a component's `code_location` and `entry_point` relative to the
deployment root (`integration-staging/`) and refuses anything that resolves
outside it.

## Contents

| Path | What it is |
| --- | --- |
| `manifest.json` | Component manifest (`examdata.component-manifest/1`) listing the staged components. |
| `fake-node-cli/fake-cli.mjs` | A synthetic, zero-dependency Node CLI written for the harness. |

## Provenance

`fake-cli.mjs` is **authored for the staging harness**. It is not a copy of, and
not derived from, the original `ielts-api/` or `toefl-api/` Node aggregators.
It performs no network, filesystem, or data-root access; it only writes
controlled JSON to stdout, controlled lines to stderr, and controlled exit
codes. The original Node components are never executed or imported in Phase A
(plan §11/A06: "Do not execute original Node components").

Every behaviour it can produce is a deliberate test fixture:

| Command | Behaviour |
| --- | --- |
| `ok` | one JSON object on stdout, exit 0 |
| `echo` | JSON object echoing `argv` (argv is never shell-interpolated) |
| `env` | JSON object reporting selected environment variables (present/`null`) |
| `bad-json` | non-JSON text on stdout |
| `two-values` | two JSON values on stdout |
| `nonzero` | two stderr lines (one absolute path, one secret) then exit 3 |
| `noisy` | three stderr lines (including a path and a secret) plus valid JSON |
| `flood` | ~8 MiB on stdout (output-budget overflow) |
| `slow` | stays alive for 10 minutes (timeout / cancellation) |
| `business-fail` | valid JSON with `ok: false` (business failure) |
| `no-stdout` | exit 0 with empty stdout |
| `crash` | exit 1 with no output |
