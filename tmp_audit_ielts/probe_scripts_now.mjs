const m = await import('file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs');
for (const b of [2, 11, 17, 19, 20]) {
  const s = await m.listeningScript(b);
  console.log('===== book', b, '| src:', s.source, '| parts:', s.parts, '| format:', s.format, '| ok:', s.ok);
  const tests = s.tests || {};
  for (const [tn, parts] of Object.entries(tests)) {
    const p4 = parts['part4'] || parts[Object.keys(parts).pop()];
    const p1 = parts['part1'];
    if (tn === 'test1') {
      console.log('  [%s] part keys: %s', tn, Object.keys(parts).join(','));
      console.log('  part1 head120: %j', String(p1||'').slice(0,120));
      console.log('  last part tail200: %j', String(p4||'').slice(-200));
    }
  }
}
