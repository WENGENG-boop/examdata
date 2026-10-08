// 临时桩服务：只为验证 node_client.mjs 的 --api-key 头与 --timeout 行为。
// 不接触 .data/ 数据库，也不碰 8126 上的真实服务。
import http from "node:http";

const port = Number(process.argv[2] || 8127);
const delayMs = Number(process.argv[3] || 0);
const key = "test-key-123";

const server = http.createServer((req, res) => {
  const send = (status, body, headers = {}) => {
    const payload = JSON.stringify(body);
    res.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload), ...headers });
    res.end(payload);
  };
  const answer = () => {
    if (req.url.startsWith("/api/v1/boards")) {
      if (req.headers["x-api-key"] !== key) {
        send(401, { detail: "缺少或无效的 X-API-Key 请求头" }, { "WWW-Authenticate": "X-API-Key" });
        return;
      }
      send(200, {
        schema_version: "stub",
        auto_detect: { rule: "stub" },
        boards: [{ board: "cie", aliases: ["cie"], name: "stub", upstream: "stub", subject_hint: "stub", seasons: [], modes: [], question_crop: false, default_mode: "qp" }],
      });
      return;
    }
    send(404, { detail: "Not Found" });
  };
  if (delayMs > 0) setTimeout(answer, delayMs);
  else answer();
});

server.listen(port, "127.0.0.1", () => console.log(`stub listening on ${port} delay=${delayMs}ms`));
