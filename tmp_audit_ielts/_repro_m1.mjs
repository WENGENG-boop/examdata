const api = await import('file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/cam21.mjs');
for (const t of [999, "x", 3.7, -1, 0]) {
  const t0 = Date.now();
  const r = await api.cam21Reading(t);
  console.log(`cam21Reading(${JSON.stringify(t)}) -> ok=${r.ok} err=${r.error || ""} ${Date.now()-t0}ms`);
}
