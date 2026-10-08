"""W1 probe: dump the fixture catalog entries and their identity resolution."""
from __future__ import annotations

import json
import sys

from examdata.integration.api.dataset import build_fixture_snapshot, fixture_providers
from examdata.integration.contracts.base import UNKNOWN
from examdata.integration.contracts.canonical import IDENTITY_KEYS
from examdata.integration.contracts.enums import EntityKind

snapshot = build_fixture_snapshot(fixture_providers())
print("entries:", len(snapshot.entries))
for entry in snapshot.entries:
    kind = EntityKind.coerce(entry.kind)
    keys = IDENTITY_KEYS[kind]
    unresolved = []
    for key in keys:
        if key not in entry.identity_fields:
            unresolved.append(f"{key}=<missing>")
            continue
        value = entry.identity_fields[key]
        if value is UNKNOWN:
            unresolved.append(f"{key}=<UNKNOWN>")
        elif value is None:
            unresolved.append(f"{key}=<None>")
        elif value == "" or value == []:
            unresolved.append(f"{key}=<empty>")
    print(f"{entry.public_id}  {entry.system}/{entry.kind}  "
          f"unresolved={unresolved}  quality={entry.quality_summary}  "
          f"evidence={entry.evidence_labels}")
