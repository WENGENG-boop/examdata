// S11 wrap-up live smoke：aggregate 非剑21 路径（book 1 / book 20），验证 B4 重构后的 listening_script 槽位
const api = await import("file:///C:/Users/weo/Desktop/api/ielts-api/ielts-api.mjs");

function compact(ag) {
  const ls = ag.parts.listening_script;
  const la = ag.parts.listening_audio;
  return {
    book: ag.book, test: ag.test,
    completeness: ag.completeness,
    score: ag.score,
    warnings: ag.warnings,
    part_keys: Object.keys(ag.parts).map((k) => `${k}:${ag.parts[k] && ag.parts[k].ok ? "ok" : "no"}`),
    listening_script: ls ? {
      ok: ls.ok, source: ls.source, format: ls.format, parts: ls.parts,
      completeness: ls.completeness ? {
        complete_basis: ls.completeness.complete_basis,
        missing: ls.completeness.missing,
      } : undefined,
      conflicts: (ls.conflicts || []).length,
      warning: ls.warning,
    } : null,
    listening_audio: Array.isArray(la)
      ? { n: la.length, ok: la.filter((a) => a.ok).length, sections: la.map((a) => a.section || a.section_id || null) }
      : (la ? { ok: la.ok, source: la.source } : null),
  };
}

for (const [b, t] of [[1, 1], [20, 2]]) {
  const ag = await api.aggregate({ book: b, test: t });
  console.log("=== aggregate(" + b + "," + t + ") ===");
  console.log(JSON.stringify(compact(ag), null, 1));
}
console.log("SMOKE_AGG_DONE");
