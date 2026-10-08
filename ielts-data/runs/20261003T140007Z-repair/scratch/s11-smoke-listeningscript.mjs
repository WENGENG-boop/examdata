// S11 live smoke：listeningScript 单套/整本 + aggregate 剑21（真实网络，逐 Part 比对）
const api = await import("file:///C:/Users/weo/Desktop/api/ielts-api/ielts-api.mjs");

function summarize(r, test) {
  if (!r || !r.ok) {
    return {
      ok: false, source: r?.source, error: r?.error, format: r?.format, parts: r?.parts,
      unsegmented: !!(r && r.unsegmented), skips: r?.provenance?.skips,
      warnings: r?.warning ? [r.warning] : undefined,
    };
  }
  const ps = test ? (r.part_status || {})["test" + test] || {} : (r.part_status || {});
  const perPart = {};
  for (const [k, v] of Object.entries(ps)) {
    perPart[k] = { status: v.status, basis: v.complete_basis, chosen: v.chosen_source };
  }
  const out = {
    ok: true, source: r.source, format: r.format, parts: r.parts, bytes: r.bytes,
    perPart, conflicts: (r.conflicts || []).length, skips: r.provenance?.skips,
    completeness: r.completeness,
  };
  const p4 = ps.part4;
  if (p4 && p4.dimensions) out.dimensions_b20t2p4 = p4.dimensions;
  return out;
}

for (const [b, t] of [[1, 1], [3, 2], [10, 1], [19, 4], [20, 2], [21, 1]]) {
  const r = await api.listeningScript(b, t);
  console.log("=== listeningScript(" + b + "," + t + ") ===");
  console.log(JSON.stringify(summarize(r, t), null, 1));
}

{
  const r = await api.listeningScript(1);
  console.log("=== listeningScript(1) 整本 ===");
  console.log(JSON.stringify(summarize(r, null), null, 1));
}

{
  const ag = await api.aggregate({ book: 21, test: 1 });
  console.log("=== aggregate(21,1) ===");
  const ls = ag.parts.listening_script;
  console.log(JSON.stringify({
    completeness: ag.completeness, score: ag.score, warnings: ag.warnings,
    listening_script: ls ? {
      ok: ls.ok, source: ls.source, parts: ls.parts,
      basis: ls.completeness?.complete_basis, conflicts: (ls.conflicts || []).length,
    } : null,
    listening_audio: Array.isArray(ag.parts.listening_audio)
      ? ag.parts.listening_audio.map((a) => ({ ok: a.ok, section: a.section, source: a.source, url: a.url ? "set" : undefined }))
      : null,
  }, null, 1));
}
console.log("SMOKE_DONE");
