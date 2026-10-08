import json, sys
sys.path.insert(0, r"C:\Users\weo\Desktop\api\integration-staging\runtime\integration-closure-20261007-c8b4e0c8\tests")
import b07r2_common as c
from examdata.integration.operations.published import build_published
from examdata.integration.contracts.base import UNKNOWN
manifest = c.make_manifest(c.make_scope("cie-questions", expected=2))
entries = [
    c.make_entry("q:cie:top", quality=c.QUALITY_VERIFIED,
                 identity={"native_id": "n-1", "parent_native_id": UNKNOWN}),
    c.make_entry("q:cie:lost", quality=c.QUALITY_VERIFIED,
                 identity={"native_id": UNKNOWN}),
]
view = build_published(entries, manifest)
row = c.row_for_scope(view, "cie-questions")
print(json.dumps({k: row[k] for k in ("derived_status","verified","unknown","partial","missing","unmet","percentage") if k in row}, indent=2))
print("row problems:", json.dumps(row.get("problems"), indent=2))
print("view problems:", json.dumps(view.problems, indent=2))
for e in entries:
    print(e.public_id, "identity:", e.identity_fields, "evidence:", e.evidence_labels)
