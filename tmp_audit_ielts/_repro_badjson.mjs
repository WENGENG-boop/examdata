// 确定性复现：HTTP 200 但 JSON 解析失败（截断/伪响应）→ req() 返回 ok:true + body:null → 下游取属性崩溃
globalThis.fetch = async () => ({
  status: 200, ok: true,
  headers: { get: () => null },
  json: async () => { throw new SyntaxError("Unexpected token '<'"); },
  text: async () => "<html>error page</html>",
});
const { listeningScript } = await import('./ielts-api.mjs');
try {
  const r = await listeningScript(5);
  console.log("NO-THROW:", JSON.stringify(r).slice(0, 200));
} catch (e) {
  console.log("THREW:", e.constructor.name + ": " + e.message);
  process.exit(2);
}
