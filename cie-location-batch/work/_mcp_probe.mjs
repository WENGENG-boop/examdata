// Manual MCP probe: spawn a fresh kimi-cu bridge and talk JSON-RPC over stdio.
import { spawn } from 'node:child_process';

const exe = 'C:/Users/weo/AppData/Local/KimiCU/kimi-cu.exe';
const cp = spawn(exe, ['mcp'], { stdio: ['pipe', 'pipe', 'pipe'] });

cp.stderr.on('data', (d) => process.stderr.write('[bridge-stderr] ' + d.toString()));
cp.stdout.on('data', (d) => process.stdout.write('[bridge-stdout] ' + d.toString()));
cp.on('exit', (code) => console.log('[bridge-exit] code=' + code));

function send(obj) {
  cp.stdin.write(JSON.stringify(obj) + '\n');
  console.log('[sent] ' + JSON.stringify(obj).slice(0, 200));
}

send({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'probe', version: '0.0.1' } } });

setTimeout(() => {
  send({ jsonrpc: '2.0', method: 'notifications/initialized' });
}, 800);

setTimeout(() => {
  send({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} });
}, 1200);

setTimeout(() => {
  send({ jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'list_apps', arguments: {} } });
}, 2000);

setTimeout(() => {
  console.log('--- probe done ---');
  cp.kill();
  process.exit(0);
}, 25000);
