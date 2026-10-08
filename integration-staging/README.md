# Integration Staging — Phase A (PHASE_A_ISOLATED_ONLY)

Staged work for the API integration. **This tree is not merged work**: nothing here has been
applied to the original application, and nothing here may be pointed at original data or services.

## Boundary

Phase A may write in exactly two roots:

| Root | Role |
| --- | --- |
| `integration-staging/` | staged implementation, tools, fixtures, tests |
| `docs/integration/execution/` | ownership record, execution ledger, evidence, reports |

Everything else under `C:/Users/weo/Desktop/api` is read-only for this executor
(see `../docs/integration/execution/ownership.json`).

## Key records

- Ownership and boundary record: `../docs/integration/execution/ownership.json`
- Execution ledger: `../docs/integration/execution/execution-ledger.json`
- A00 initial report: `../docs/integration/execution/A00_INITIAL_REPORT.md`
- Governing plan: `../docs/integration/MASTER_EXECUTION_PLAN_EN.md`

## Conventions

- Source `tools/_env.sh` before running staged commands (no bytecode, UTF-8 IO, no git locks).
- Use the project virtual-env Python for read-only inspection; never install into it:
  `C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe`
- Tests run only inside the private staging harness, with private fixtures and offline transports
  (the network guard is part of the harness, packet A02).
