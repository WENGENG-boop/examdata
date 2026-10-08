"""Ad-hoc probe (W1): what do the fixture producers actually emit?

Read-only: builds the fixture catalog snapshot in memory and prints each
entry's kind, identity fields, quality summary and evidence labels so the
trust rules can be checked against real producer output.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(root)
os.environ.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
sys.path.insert(0, str(root / "src"))

from examdata.integration.api.dataset import default_dataset  # noqa: E402

dataset = default_dataset(operations_root=None)
rows = []
for entry in dataset.snapshot.entries:
    rows.append({
        "public_id": entry.public_id,
        "kind": entry.kind,
        "system": entry.system,
        "identity_fields": entry.to_dict()["identity_fields"],
        "quality_summary": entry.quality_summary,
        "evidence_labels": entry.evidence_labels,
        "content_class": entry.content_class,
        "native_locator": entry.native_locator,
    })
print(json.dumps({"count": len(rows), "rows": rows}, indent=1, ensure_ascii=False))
