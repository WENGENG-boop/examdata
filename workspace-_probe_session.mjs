import fs from 'node:fs';
import zlib from 'node:zlib';

const file = process.argv[2];
const buf = fs.readFileSync(file);
const magic = Buffer.from([0x28, 0xb5, 0x2f, 0xfd]);
const offsets = [];
for (let i = 0; i + 4 <= buf.length; i++) {
  if (buf.compare(magic, 0, 4, i, i + 4) === 0) offsets.push(i);
}
console.log('file bytes', buf.length, 'frames found', offsets.length);
console.log('first offsets', offsets.slice(0, 12).join(','));

const out = [];
let ok = 0, bad = 0;
for (let k = 0; k < offsets.length; k++) {
  const start = offsets[k];
  const end = k + 1 < offsets.length ? offsets[k + 1] : buf.length;
  try {
    out.push(zlib.zstdDecompressSync(buf.subarray(start, end)));
    ok++;
  } catch (e) {
    bad++;
    if (bad <= 3) console.log('frame', k, 'failed:', e.code, 'size', end - start);
  }
}
const text = Buffer.concat(out).toString('utf8');
console.log('decoded frames ok', ok, 'bad', bad, 'text bytes', text.length);
const lines = text.split('\n').filter(Boolean);
console.log('lines', lines.length);
const needle = new RegExp(process.argv[3] ?? 'reasoningEffort');
for (const l of lines) {
  if (needle.test(l)) { console.log(l.slice(0, 1200)); console.log('---'); }
}
