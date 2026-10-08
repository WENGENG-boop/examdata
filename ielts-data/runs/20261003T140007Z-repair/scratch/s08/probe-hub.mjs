import fs from "node:fs";
import { parseHubLinks } from "../../../../../ielts-api/pte.mjs";
const raw = fs.readFileSync("C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-301.txt", "utf8");
const parsed = parseHubLinks(raw, 20);
console.log("slots:", JSON.stringify(parsed.slots, null, 1).slice(0, 2000));
console.log("provenance writing:", JSON.stringify(parsed.provenance.writing));
console.log("provenance speaking:", JSON.stringify(parsed.provenance.speaking));
