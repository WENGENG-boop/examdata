import { readFile, writeFile } from 'node:fs/promises';

// Reads an existing local snapshot only; never fetches, syncs or writes backend data.
const source = JSON.parse((await readFile(new URL('../cie_all_discovery.json', import.meta.url), 'utf8')).replace(/^\uFEFF/, ''));
const items = source.resources.filter(r => ['question_paper', 'mark_scheme', 'examiner_report'].includes(r.doc_type)).map(r => {
  const title = r.syllabus_slug.replace(/^cambridge-(?:international-as-and-a-level|igcse|o-level)-/, '').replace(/-\d{4}$/, '').replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const label = r.label.replace(/<[^>]+>/g, '');
  // The original label carries the exam year; numeric syllabus codes are not years.
  const labeledYear = label.match(/\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b/i);
  const qualification = r.syllabus_slug.includes('international-as-and-a-level') ? 'A Level' : r.syllabus_slug.includes('o-level') ? 'O Level' : 'IGCSE';
  return { key: r.url, title, qualification, code: r.subject_code, year: labeledYear ? Number(labeledYear[1]) : r.year, season: r.series, paper: r.paper_code, type: r.doc_type, board: 'cie', label, url: r.url, origin: 'catalog' };
}).sort((a, b) => (b.year || 0) - (a.year || 0) || String(a.code).localeCompare(String(b.code)) || String(a.paper).localeCompare(String(b.paper)) || a.type.localeCompare(b.type));
const pearson = JSON.parse((await readFile(new URL('./edexcel-subjects-source.json',import.meta.url),'utf8')).replace(/^\uFEFF/,''));
const edexcelSubjects = pearson.map(s=>({title:s.title,code:s.category.find(c=>/^Pearson-UK:Specification-Code\/[^/]+$/.test(c))?.split('/').pop(),qualification:'International A Level',board:'edexcel'})).filter(s=>s.code);
await writeFile(new URL('./catalog.json', import.meta.url), JSON.stringify({ generated_from: 'cie_all_discovery.json', snapshot_date: '2026-10-01', edexcelSubjects, items }, null, 2) + '\n');
console.log(`Catalog: ${items.length} resources`);
