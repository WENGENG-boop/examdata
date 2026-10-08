// End-to-end flows against the private fixture server: the same requests the
// staged page makes in a browser (page, modules, snapshots, /api/v2/resources,
// content bytes, failure injection), plus the honesty scans. Offline: the
// server binds 127.0.0.1 on an ephemeral port and never touches the network.

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile, readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createServer} from '../fixture-server.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');

async function withServer(run) {
  const server = createServer({});
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const {port} = server.address();
  assert.notEqual(port, 5188);
  assert.notEqual(port, 8000);
  const base = `http://127.0.0.1:${port}`;
  try {
    await run(base);
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
}

test('the staged page, modules and snapshots are served', async () => {
  await withServer(async base => {
    const page = await fetch(`${base}/`);
    assert.equal(page.status, 200);
    const html = await page.text();
    assert.match(html, /id="staged-banner"/);
    assert.match(html, /集成暂存副本/);
    assert.match(html, /staged fixture validation/);
    for (const [route, type] of [['/app.js', /javascript/], ['/client.mjs', /javascript/], ['/search.mjs', /javascript/], ['/styles.css', /css/]]) {
      const res = await fetch(base + route);
      assert.equal(res.status, 200);
      assert.match(res.headers.get('content-type'), type);
    }
    const catalog = await (await fetch(`${base}/catalog.json`)).json();
    assert.equal(catalog.fixture_kind, 'synthetic');
    assert.ok(Array.isArray(catalog.items));
    assert.ok(Array.isArray(catalog.edexcelSubjects));
    const syllabi = await (await fetch(`${base}/syllabi.json`)).json();
    assert.equal(syllabi.fixture_kind, 'synthetic');
  });
});

test('the staged app.js uses the v2 client, keeps both selector sets and no /gateway', async () => {
  await withServer(async base => {
    const text = await (await fetch(`${base}/app.js`)).text();
    assert.match(text, /from '\.\/client\.mjs'/);
    assert.doesNotMatch(text, /\/gateway/);
    assert.doesNotMatch(text, /fetch\('\/resources\?'/);
    assert.match(text, /\['Jun','Nov','Mar'\]/);
    assert.match(text, /\['January','June','October','November'\]/);
    assert.match(text, /staged fixture validation/);
  });
});

test('the resources list responds with the examdata.v2/1 envelope', async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/v2/resources?system=cie&query=${encodeURIComponent('9709 2026 Jun')}`);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.schema_version, 'examdata.v2/1');
    assert.equal(body.error, null);
    assert.ok(Array.isArray(body.data.items));
    assert.ok(body.meta.warnings.includes('staged_fixture_validation'));
    assert.ok(body.data.items.length > 0);
    assert.ok(body.data.items.every(entry => entry.evidence.includes('synthetic_fixture')));
    assert.ok(body.data.items.every(entry => entry.discovery.board === 'cie' && entry.discovery.season === 'Jun'));
    assert.ok(body.data.items.every(entry => String(entry.discovery.subject) === '9709'));
    const detail = await (await fetch(`${base}/api/v2/resources/${body.data.items[0].public_id}`)).json();
    assert.equal(detail.data.item.public_id, body.data.items[0].public_id);
  });
});

test('staged content bytes match the declared hash and evidence headers', async () => {
  await withServer(async base => {
    const list = await (await fetch(`${base}/api/v2/resources?system=cie&query=${encodeURIComponent('9709 2026 Jun')}`)).json();
    const item = list.data.items.find(entry => entry.public_id === 'asset_syn_cie_9709_2026_jun_qp21');
    assert.ok(item);
    const res = await fetch(base + item.content_link);
    assert.equal(res.status, 200);
    assert.equal(res.headers.get('content-type'), 'application/pdf');
    assert.equal(res.headers.get('x-content-sha256'), item.sha256);
    assert.equal(res.headers.get('x-evidence'), 'synthetic_fixture');
    const bytes = Buffer.from(await res.arrayBuffer());
    assert.equal(bytes.length, item.byte_size);
  });
});

test('the failure map produces the staged error envelope', async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/v2/resources?system=cie&query=${encodeURIComponent('9709 2026 Mar')}`);
    assert.equal(res.status, 503);
    const body = await res.json();
    assert.equal(body.schema_version, 'examdata.v2/1');
    assert.equal(body.data, null);
    assert.equal(body.error.code, 'upstream_unavailable');
    const edx = await fetch(`${base}/api/v2/resources?system=edexcel&query=${encodeURIComponent('wec11 2026 October')}`);
    assert.equal(edx.status, 503);
  });
});

test('unknown api routes answer with the route_not_found envelope', async () => {
  await withServer(async base => {
    const res = await fetch(`${base}/api/v2/nope`);
    assert.equal(res.status, 404);
    const body = await res.json();
    assert.equal(body.error.code, 'route_not_found');
  });
});

test('no key material appears in the staged files', async () => {
  const pattern = /(api[_-]?key|apikey|secret|bearer|password)/i;
  const targets = ['index.html', 'app.js', 'client.mjs', 'search.mjs', 'styles.css', 'fixture-server.mjs', 'README.md'];
  for (const name of targets) {
    const text = await readFile(path.join(ROOT, name), 'utf8');
    assert.doesNotMatch(text, pattern, `${name} must not carry key material`);
  }
  const fixturesDir = path.join(ROOT, 'fixtures');
  for (const name of await readdir(fixturesDir)) {
    if (!name.endsWith('.json')) continue;
    const text = await readFile(path.join(fixturesDir, name), 'utf8');
    assert.doesNotMatch(text, pattern, `fixtures/${name} must not carry key material`);
  }
});
