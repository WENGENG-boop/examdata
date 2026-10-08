# A04 — Contracts and identity rules (Phase A, isolated)

**Status:** staged pass. Nothing merged, nothing deployed; every Phase B gate
remains closed. Work is confined to `integration-staging/` and
`docs/integration/execution/`.

## 1. Scope

Freeze the plan §4 shared contracts: the entity models, their JSON schemas, the
identity-canonicalization decision, the quality transition table, the
type-specific completeness rules, and a set of worked examples. The contracts
must round-trip the A03 private synthetic fixtures with **no source-specific
information lost** and a **deterministic** identity.

Inputs (hashed into the ledger): the A03 synthetic fixtures and provenance
manifest, the A03 report/evidence, and the A04 decision record.

## 2. Deliverables

Source (staged package `integration-staging/src/examdata_integration/contracts/`):

| file | role |
| --- | --- |
| `enums.py` | `ExamSystem`, `ContainerKind`, `QuestionType`, `AnswerMatchingMethod`, `ContentClass`, 7 quality enums, `GapScope`, `GapCode`, `EvidenceLabel`, `EntityKind`, `ID_TYPE_PREFIX` |
| `canonical.py` | normalisation classes, `UNKNOWN` sentinel, `IDENTITY_KEYS`, `canonical_identity_string`, `digest_for`, `public_id`, `content_revision`, `is_url_safe_public_id` |
| `base.py` | `ContractModel`, `Gap`, `ContractError`, `plain`, `req` |
| `models.py` | all entity models + payloads + `MODELS` + `REQUIRED_FIELDS` |
| `ids.py` | `IdentityRegistry`, `IdentityRecord`, collision/alias errors |
| `quality.py` | quality dimensions, `TRANSITIONS`, `can_transition`, `Quality`, `FORBIDDEN_BASIS` |
| `completeness.py` | `evaluate_question`, `evaluate_container`, `per_system_coverage`, `project_percentage` |
| `jsonschema_lite.py` | a deliberate JSON-schema subset validator + `unsupported_keywords` |

Generated artefacts (`integration-staging/contracts/`):

* `schema/*.schema.json` — **28** draft-2020-12 (subset) schemas, one per model;
* `identity-keys.json`, `quality-transitions.json` — the machine mirror of the
  frozen identity keys and the transition table;
* `examples/*.json` + `INDEX.json` — **44** worked examples (43 model examples +
  3 identity-registry containers, less overlaps) covering all 14 entity kinds.

Decision record: `docs/integration/execution/A04_IDENTITY_DECISION.md`.

Tools: `integration-staging/tools/a04_generate_schemas.py` (generator, with
`--check`), `integration-staging/tools/a04_roundtrip_fixtures.py` (fixture →
model round-trip), `integration-staging/tools/a04_final_checks.py` (closing
checks).

Tests (staged): `tests/test_contracts_identity.py`,
`tests/test_contracts_quality.py`, `tests/test_contracts_completeness.py`,
`tests/test_contracts_schemas.py`.

## 3. Identity rules (summary; full record in the decision doc)

* `public_id = <prefix>_<base32(sha256(canonical_identity)[:20])>`, deterministic
  and URL-safe; the native identity is never derived from it.
* Per-kind identity keys are frozen in `canonical.IDENTITY_KEYS` and mirrored to
  `contracts/identity-keys.json`.
* `None` (absent) and `UNKNOWN` (explicitly unknown) encode differently
  (`\x00` vs `\x01`), so "no date stated" and "date stated as unknown" cannot
  collide.
* A collision is **recorded and raised** (`IdentityCollisionError`); an alias
  conflict is **recorded and raised** (`AliasConflictError`) and, as of this
  packet, leaves **no half-registered record** behind (aliases are validated
  before the record is committed).
* Similarity, row numbers, HTTP status, filename/title matches, and
  "two unofficial sources agree" are **never** identity or verification rules
  (also in `quality.FORBIDDEN_BASIS`).

## 4. Quality transition table

Seven independent dimensions (`content`, `answer_presence`,
`answer_verification`, `assets`, `audio_integrity`, `audio_alignment`,
`region_verification`) with a single decision point, `can_transition`. Frozen
invariants proven by tests:

* synthetic fixtures can never reach `source_verified`;
* `audio_integrity` may reach `hash_verified` from hash evidence while
  `audio_alignment` stays `unverified` — a hash proves integrity, not
  association;
* every `FORBIDDEN_BASIS` key is refused;
* a context gate (`requires=…`) must be satisfied (e.g. `denominator_known`);
* `Quality.validate` flags verified alignment with unverified integrity.

## 5. Completeness rules

Requirements are built per question type, so an essay needs no options while a
diagram-label question needs its image and a table-choice question needs columns,
rows **and** answer cells. Unknown expected coverage yields no percentage;
`project_percentage` always raises `CrossSystemAggregationError` (unrelated
systems are never averaged).

## 6. Evidence

| check | result | evidence |
| --- | --- | --- |
| Fixture → model round-trip, 61 checks | **PASS** | `evidence/A04/roundtrip_stdout.txt` |
| Staged suite, offline | **75 passed**, exit 0 | `evidence/A04/pytest_run_stdout.txt` |
| Generator `--check` byte-stable | **CHECK: PASS (30/30)** | run inside the suite; `evidence/A04/final_checks.txt` |
| Examples validate against their schemas | **PASS** | `tests/test_contracts_schemas.py` |
| Identity/quality/completeness rules | **PASS** | `tests/test_contracts_{identity,quality,completeness}.py` |
| Closing checks | see `final_checks.txt` | `evidence/A04/final_checks.txt` |

Round-trip preservation asserted for: IELTS alias resolution (case-insensitive),
Q41 missing answer slot, Q2 grouped alternatives, Q3 parent + children hierarchy,
Q4 table structure, Q5 conflict + required image + lineage; CIE hierarchy, table
structure, unknown date, conflict, "synthetic never verified"; Edexcel unknown
sessions and alias resolution; native-locator round-trip.

### Recorded `validate()` facts (kept visible, never cleared)

These are honest gaps the fixtures declare, not defects:

* an answer with two conflicting candidates and **no manual decision** — the
  conflict is preserved, not resolved by the importer;
* an asset with a hash but **no byte size** (external-only);
* CIE Q1 with **no answer recorded** (the slot is kept, the gap reported);
* timetable events with an **unknown date** and a session without a timezone —
  the date is never invented.

## 7. Corrections made in this packet

1. `completeness.CompletenessResult.to_coverage` produced a `Coverage` whose
   `observed` did not equal the sum of its buckets, so every coverage example
   failed its own `Coverage.validate()`. Fixed: the buckets now partition
   `observed` (satisfied → `verified`, unsatisfied → `missing`), and the mapping
   is documented as a **requirement-satisfaction count, not content
   verification** (content quality stays in the `Quality` dimensions). A test
   asserts `to_coverage(...).validate() == []`.
2. `IdentityRegistry.register` could leave a **half-registered record** when an
   alias conflicted (the record was committed before alias binding raised).
   Fixed: aliases are validated first, then committed; a conflicting alias
   raises with no state change. A test asserts the rejected identity is absent.

## 8. Deliberate limitations

* `jsonschema_lite` implements a **subset** of JSON Schema (types, `enum`,
  `const`, `required`, `properties`, `items`, `$ref`, `allOf`/`anyOf`/`oneOf`,
  numeric/string constraints). The A04 tests assert `unsupported_keywords == []`
  for all 28 generated schemas, so the subset is sufficient for the generated
  artefacts — but it is not a general-purpose validator.
* `identity-registry/1` has **no generated JSON schema**: it is a container of
  `IdentityRecord`s, not a plan §4 model. Its round-trip is asserted by
  `test_contracts_identity.py`.
* No real data, network, database or original code was used: everything runs
  against the A03 synthetic fixtures. Real-data behaviour is Phase B work.

## 9. Remaining gaps / deferred

* Real-data round-trip and cross-source identity reconciliation stay Phase B
  behind the `real_data_write_authorized` gate.
* The examination-material and timetable content Kimi owns remains
  `deferred_active_owner` (A01/A03); A04 does not read it.
* The contracts are frozen for A05+ to consume; any later change to a model,
  identity key or transition must re-run the generator `--check` and re-open A04.

## 10. Next action

A05 — provider protocol and registry (plan §11): a typed provider protocol, a
capability-filtered registry, and typed unsupported results, built on the A04
contracts and exercised against the A03 synthetic fixtures with offline
transports.
