import test from 'node:test';
import assert from 'node:assert/strict';
import { pearsonDocuments, cieDocuments, allSeasonResources, syllabusFor } from '../lib/resources.mjs';

const doc = (name, kind) => ({ url: `/content/dam/pdf/International%20Advanced%20Level/Economics/2018/Exam-materials/${name}`, title: name, category: [`Pearson-UK:Document-Type/${kind}`] });

test('Edexcel variant paper keeps its letter suffix', () => {
  const [d] = pearsonDocuments([doc('wec14-01a-que-20250604.pdf', 'Question-Paper')], { board: 'edexcel' });
  assert.equal(d.paper, 'wec14-01a');
  assert.equal(d.type, 'question_paper');
});
test('Edexcel paper filter matches the base code of a variant', () => {
  const records = [doc('wec14-01a-que-20250604.pdf', 'Question-Paper'), doc('wec14-01-que-20250604.pdf', 'Question-Paper'), doc('wec13-01-que-20250528.pdf', 'Question-Paper')];
  assert.deepEqual(pearsonDocuments(records, { paper: 'wec14-01' }).map(d => d.paper).sort(), ['wec14-01', 'wec14-01a']);
  assert.deepEqual(pearsonDocuments(records, { paper: 'wec13' }).map(d => d.paper), ['wec13-01']);
});
test('Edexcel ignores secure paths and unknown document types', () => {
  const records = [{ url: '/content/dam/pdf/secure/x/wec11-01-que.pdf', category: ['Pearson-UK:Document-Type/Question-Paper'] }, doc('spec.pdf', 'Specification')];
  assert.equal(pearsonDocuments(records, {}).length, 0);
});
test('CIE listing keeps only the requested series and paper', () => {
  const rows = ['9709_s24_qp_11.pdf', '9709_s24_ms_11.pdf', '9709_s24_qp_12.pdf', '9709_w24_qp_11.pdf', '9709_s24_gt.pdf'].map(file => ({ file }));
  const docs = cieDocuments({ rows, total: rows.length }, { subject: '9709', year: '2024', season: 'Jun', paper: '11' });
  assert.deepEqual(docs.map(d => d.title), ['9709_s24_qp_11.pdf', '9709_s24_ms_11.pdf', '9709_s24_gt.pdf']);
});
test('CIE listing rejects an incomplete directory', () => {
  assert.throws(() => cieDocuments({ rows: [], total: 3 }, { subject: '9709', year: '2024', season: 'Jun' }));
});
test('all-season lookup keeps successful seasons and reports failures', async () => {
  const load = async q => { if (q.season === 'Nov') throw new Error('boom'); return { documents: [{ url: `u-${q.season}`, season: q.season }], warning: '' }; };
  const r = await allSeasonResources({ board: 'cie', subject: '9709', year: '2024' }, load, null);
  assert.deepEqual(r.documents.map(d => d.season), ['Mar', 'Jun']);
  assert.match(r.warning, /Nov/);
});
test('all-season lookup fails only when every season fails', async () => {
  await assert.rejects(allSeasonResources({ board: 'cie' }, async () => { throw new Error('down'); }, null));
});
test('syllabus lookup returns links for the board', () => {
  const s = syllabusFor({ cie: { 9709: { title: 'Mathematics', page: 'p', syllabuses: [{ title: 'S', url: 'u' }] } }, edexcel: {} }, { board: 'cie', subject: '9709' });
  assert.equal(s.syllabuses[0].url, 'u');
  assert.equal(syllabusFor({ cie: {}, edexcel: {} }, { board: 'edexcel', subject: 'x' }), null);
});
