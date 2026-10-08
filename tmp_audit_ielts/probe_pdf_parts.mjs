import { aggregate } from 'file:///C:/Users/weo/Documents/deepseek-harness/default-workspace/ielts-api/ielts-api.mjs';
for (const [b,t] of [[20,1],[19,1],[1,1]]) {
  const p = await aggregate({ book: b, test: t });
  const pdf = p.parts.pdf;
  console.log(`B${b}T${t} pdf: ok=${pdf.ok} bytes=${pdf.bytes} note="${pdf.note}"`);
  console.log(`  url tail: ...${decodeURIComponent(pdf.url).slice(-40)}`);
  if (p.parts.pdf_book20_tests) {
    const pb = p.parts.pdf_book20_tests;
    console.log(`  pdf_book20_tests: ok=${pb.ok} bytes=${pb.bytes} keys=${Object.keys(pb)}`);
    console.log(`  pb.url tail: ...${decodeURIComponent(pb.url||'').slice(-45)}`);
  }
}
