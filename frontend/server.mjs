import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import { resources } from './resources.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));
const upstream = new URL(process.env.EXAMDATA_URL || 'http://127.0.0.1:8000');
const port = Number(process.env.FRONTEND_PORT || 5188);
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/search.mjs', ['search.mjs', 'text/javascript; charset=utf-8']],
  ['/styles.css', ['styles.css', 'text/css; charset=utf-8']],
  ['/catalog.json', ['catalog.json', 'application/json; charset=utf-8']],
  ['/syllabi.json', ['syllabi.json', 'application/json; charset=utf-8']],
]);
const allowed = /^\/(?:health|papers|papers\/\d+\/tree|api\/v1\/(?:boards|search|question\/\d+|paper|ielts\/(?:reading\/\d+\/\d+|listening\/\d+\/\d+)))$/;

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (req.method !== 'GET') {
      res.writeHead(405, { Allow: 'GET' }); return res.end();
    }
    if (url.pathname === '/resources') {
      const query=Object.fromEntries(['board','subject','year','season','paper'].map(k=>[k,url.searchParams.get(k) || '']));
      if(!['cie','edexcel'].includes(query.board) || !/^20\d{2}$/.test(query.year) || query.subject.length>80 || query.paper.length>20) {res.writeHead(400);return res.end(JSON.stringify({detail:'请选择科目、年份与考季'}));}
      const catalog=JSON.parse(await readFile(root+'catalog.json','utf8'));
      const syllabi=await readFile(root+'syllabi.json','utf8').then(JSON.parse).catch(()=>null);
      try {const data=await resources(query,catalog.edexcelSubjects,syllabi);res.writeHead(200,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});return res.end(JSON.stringify(data));}
      catch(error) {res.writeHead(502,{'Content-Type':'application/json; charset=utf-8'});return res.end(JSON.stringify({detail:error.message}));}
    }
    if (url.pathname.startsWith('/gateway/')) {
      const path = url.pathname.slice('/gateway'.length);
      if (!allowed.test(path)) { res.writeHead(404); return res.end(); }
      const target = new URL(upstream);
      target.pathname = upstream.pathname.replace(/\/$/, '') + path;
      target.search = url.search;
      const response = await fetch(target, {
        signal: AbortSignal.timeout(180000), redirect: 'error',
        headers: process.env.EXAMDATA_API_KEY ? { 'X-API-Key': process.env.EXAMDATA_API_KEY } : {},
      });
      const headers = { 'Cache-Control': 'no-store' };
      for (const key of ['content-type', 'content-disposition']) {
        if (response.headers.has(key)) headers[key] = response.headers.get(key);
      }
      res.writeHead(response.status, headers);
      if (!response.body) return res.end();
      Readable.fromWeb(response.body).on('error', () => res.destroy()).pipe(res);
      return;
    }
    const file = files.get(url.pathname);
    if (!file) { res.writeHead(404); return res.end('Not found'); }
    const data = await readFile(root + file[0]);
    res.writeHead(200, { 'Content-Type': file[1], 'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff' });
    res.end(data);
  } catch (error) {
    if (res.headersSent) return res.destroy();
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ detail: error.name === 'TimeoutError' ? '请求超时，请稍后手动重试。' : '暂时无法连接数据服务，请检查前端的 EXAMDATA_URL 配置。' }));
  }
}).listen(port, '127.0.0.1', () => console.log(`Examdata frontend: http://127.0.0.1:${port}`));
