import fs from 'node:fs';
const raw = fs.readFileSync('C:/Users/weo/Desktop/api/tmp_audit_ielts/completeness_20261003/raw-163.txt', 'utf8');
const seg = raw.slice(16600, 24200);
// print with tag-only markers: strip long text runs
const cleaned = seg.replace(/<p[^>]*>/g, '\n<P>').replace(/<\/p>/g, '</P>\n');
console.log(cleaned.slice(0, 6000));
