import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { parseListeningHtml, parseReadingHtml } from "../../../../../ielts-api/cam21.mjs";

const ROOT = "C:/Users/weo/Desktop/api";
const MIRROR = path.join(ROOT, "tmp_audit_ielts/cam21");
const OUT = path.join(ROOT, "ielts-data/runs/20261003T140007Z-repair/evidence/S06-cam21-crosscheck.json");

const sha = (buf) => crypto.createHash("sha256").update(buf).digest("hex");
const out = { mirror_dir: MIRROR, files: {}, tests: {} };

for (const f of ["t1-listening.html", "t2-listening.html", "t3-listening.html", "t4-listening.html",
                 "t1-reading.html", "t2-reading.html", "t3-reading.html", "t4-reading.html"]) {
  const p = path.join(MIRROR, f);
  const buf = fs.readFileSync(p);
  out.files[f] = { bytes: buf.length, sha256: sha(buf) };
}

let allOk = true;
for (let t = 1; t <= 4; t++) {
  const html = fs.readFileSync(path.join(MIRROR, `t${t}-listening.html`), "utf8");
  const r = parseListeningHtml(html, { test: t });
  const nums = r.questions.map((q) => q.number);
  const missing = Array.from({ length: 40 }, (_, i) => i + 1).filter((n) => !nums.includes(n));
  const mcqNoOptions = r.questions.filter((q) => q.type === "mcq" && (!q.options || !q.options.length)).map((q) => q.number);
  const multiGroups = r.answer_groups.map((g) => ({ key: g.key, slots: g.slots, accept: g.accept, required_count: g.required_count }));
  const multiSlotSet = new Set(multiGroups.flatMap((g) => g.slots));
  const multiNoAccept = multiGroups.filter((g) => !g.accept.length).map((g) => g.key);
  const akNums = r.answer_key.map((a) => a.number);
  const akMissing = Array.from({ length: 40 }, (_, i) => i + 1).filter((n) => !akNums.includes(n));
  out.tests[`t${t}-listening`] = {
    questions: r.questions.length,
    missing_1_40: missing,
    answer_keys: r.answer_key.length,
    ak_missing_1_40: akMissing,
    multi_groups: multiGroups,
    multi_group_count: multiGroups.length,
    multi_member_slots: multiSlotSet.size,
    multi_no_accept: multiNoAccept,
    mcq_no_options: mcqNoOptions,
    counts: r.counts,
    warnings: r.warnings.length,
  };
  if (missing.length || akMissing.length || mcqNoOptions.length || multiNoAccept.length) allOk = false;
}

for (let t = 1; t <= 4; t++) {
  const html = fs.readFileSync(path.join(MIRROR, `t${t}-reading.html`), "utf8");
  const r = parseReadingHtml(html, { test: t });
  const nums = r.questions.map((q) => q.number);
  const missing = Array.from({ length: 40 }, (_, i) => i + 1).filter((n) => !nums.includes(n));
  out.tests[`t${t}-reading`] = {
    questions: r.questions.length,
    missing_1_40: missing,
    answer_keys: r.answer_key.length,
    groups: r.groups.map((g) => ({ id: g.id, slots: g.slots, type: g.type })),
    counts: r.counts,
    warnings: r.warnings.length,
  };
  if (missing.length) allOk = false;
  if (t === 2) {
    const q2021 = r.questions.filter((q) => [20, 21].includes(q.number)).map((q) => ({ n: q.number, type: q.type, group: q.group, group_slots: q.group_slots, accept: q.accept, options: (q.options || []).map((o) => o.label) }));
    out.tests["t2-reading-q20-21"] = q2021;
    if (!q2021.length) allOk = false;
  }
}

out.all_ok = allOk;
fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
console.log("wrote", OUT, "all_ok=", allOk);
for (const [k, v] of Object.entries(out.tests)) {
  if (v && v.questions !== undefined) console.log(k, "q=" + v.questions, "missing=" + ((v.missing_1_40 || []).join(",") || "none"));
}
