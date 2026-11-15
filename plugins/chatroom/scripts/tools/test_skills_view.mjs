// The Skills view (0.19, D3): every skill is listed with no filter by default, and each row shows on which agents it is active
// (three badges, "+N" for the rest, all of them in the tooltip). A stub page captures what the view writes.
// node plugins/chatroom/scripts/tools/test_skills_view.mjs
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };

const sk = (name, origin, agents) => ({id: `${origin}:-:${name}`, name, brief: name + ' brief', description: name + ' d', origin, plugin: null, version: null, path: '/x/' + name, advised: [], agents});
const DATA = {v: 1, origins: ['user', 'plugin'], skills: [sk('many', 'plugin', ['A', 'B', 'C', 'D']), sk('none', 'user', []), sk('one', 'user', ['A'])],
  agents: ['A', 'B', 'C', 'D'].map(name => ({name, skills: []})), searcher: {present: true, name: 'S', busy: false}, requests: []};
const els = {};
const el = id => (els[id] ??= {id, innerHTML: '', value: '', style: {}, classList: {toggle() {}, add() {}, remove() {}}, querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, insertAdjacentElement() {}});
const stub = () => new Proxy(function () {}, {get: (t, k) => (k === 'classList' ? {toggle() {}, add() {}, remove() {}} : k === 'style' ? {} : k === 'querySelector' ? () => null : k === 'querySelectorAll' ? () => [] : k in t ? t[k] : () => stub()), set: () => true});
globalThis.window = globalThis;
globalThis.document = {createElement: stub, getElementById: id => (id === 'officeBtn' ? null : el(id)), head: {appendChild() {}}, body: {appendChild() {}, classList: {toggle() {}}}, hidden: false};
globalThis.location = {search: '', href: 'http://x/'};
globalThis.history = {replaceState() {}};
globalThis.localStorage = {getItem: () => null, setItem() {}};
globalThis.addEventListener = () => {};
globalThis.setInterval = () => 0;
globalThis.I18N = {text: (k, f) => k + (f ? JSON.stringify(f) : '')};
globalThis.fetch = async () => ({ok: true, json: async () => DATA});
await import(pathToFileURL(path.join(S, 'skills-view.js')).href);
globalThis.skillsView.open(true);
await new Promise(r => setTimeout(r, 50));

const rows = els.skRows ? els.skRows.innerHTML : '';
const chips = els.skChips ? els.skChips.innerHTML : '';
test('no filter by default: all 3 skills listed', (rows.match(/class="sk-row/g) || []).length === 3 ? '' : rows);
test('the "all" chip is the one on, with the full count', /sk-chip on" data-origin=""[^>]*>skillsv\.all<span class="n">3/.test(chips) ? '' : chips);
const many = rows.split('class="sk-row').find(r => r.includes('>many<')) || '';
test('4 agents: three badges and "+1"', /<span>A<\/span><span>B<\/span><span>C<\/span><span>\+1<\/span>/.test(many) && !many.includes('<span>D</span>') ? '' : many);
test('the tooltip lists all four', /title="[^"]*A, B, C, D"/.test(many) ? '' : many);
const none = rows.split('class="sk-row').find(r => r.includes('>none<')) || '';
test('no agent: no badges', none && !none.includes('sk-bd') ? '' : none);
const one = rows.split('class="sk-row').find(r => r.includes('>one<')) || '';
test('one agent: one badge, no "+N"', /<span>A<\/span><\/div>/.test(one) && !one.includes('+') ? '' : one);
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
