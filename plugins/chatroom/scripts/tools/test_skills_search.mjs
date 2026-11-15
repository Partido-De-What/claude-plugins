// The Skills view (0.19, D6): the Search tab lists only the search requests (the jobs are in the Candidates tab).
// (the Candidates tab: test_skills_cand.mjs)
// node plugins/chatroom/scripts/tools/test_skills_search.mjs
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };

const cand = (name, room, score, extra = {}) => ({id: `cand:${room}:${name}`, room, name, score, why: 'why ' + name, kind: 'derive', tasks: [], criteria: {recurrence: 9}, repeated: [], hard: [], tokens: 100, tokens_saved: null,
  covered_by: null, improves: null, status: 'new', at: 1, req: 'r1', ...extra});
const DATA = {v: 1, origins: ['user'], skills: [], agents: [], searcher: {present: true, name: 'S', busy: false},
  requests: [{req: 'r8', kind: 'derive', q: 'kernel <b>routes</b>', at: 1, state: 'failed', log: 'skills-temp/r8.log'}, {req: 'r1', q: 'a search', at: 1, state: 'done', cards: []}],
  rooms: [{id: 'aa', name: 'room-a', current: true, n: 3}, {id: 'bb', name: 'room-b', current: false, n: 1}],
  candidates: [cand('low', 'aa', 3), cand('<img src=x onerror=1>', 'aa', 9), cand('gone', 'aa', 5, {status: 'dismissed'}), cand('imp', 'bb', 6, {kind: 'improve', improves: 'user:-:imp', covered_by: 'user:-:other'}), cand('done', 'bb', 8, {status: 'added'})]};
const DIFF = {ok: true, diff: '--- a\n+++ b\n@@ -1 +1 @@\n-old <i>x</i>\n+new\n ctx\n', added: 1, removed: 1, target: null};
const els = {}, calls = [], handlers = {};
const el = id => (els[id] ??= {id, innerHTML: '', value: '', style: {}, classList: {toggle() {}, add() {}, remove() {}}, querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, insertAdjacentElement() {}, focus() {}});
const mk = () => ({classList: {toggle() {}, add() {}, remove() {}}, style: {}, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, offsetWidth: 0, insertAdjacentElement() {},
  addEventListener(t, f) { (handlers[t] ??= []).push(f); }, set innerHTML(v) {}, get innerHTML() { return ''; }});
globalThis.window = globalThis;
globalThis.CSS = {escape: s => s};
globalThis.document = {createElement: mk, getElementById: id => (id === 'officeBtn' ? null : el(id)), head: {appendChild() {}}, body: {appendChild() {}, classList: {toggle() {}}}, hidden: false, activeElement: null};
globalThis.location = {search: '', href: 'http://x/'};
globalThis.history = {replaceState() {}};
globalThis.localStorage = {getItem: () => JSON.stringify({tab: 'search'}), setItem() {}};
globalThis.addEventListener = () => {};
globalThis.setInterval = () => 0;
globalThis.I18N = {text: (k, f) => k + (f ? JSON.stringify(f) : '')};
globalThis.fetch = async (url, o) => {
  if (url === 'skills.json') return {ok: true, json: async () => DATA};
  const b = JSON.parse(o.body); calls.push(b);
  const j = b.action === 'diff' ? DIFF : b.action === 'promote' ? {ok: true, preview: {name: 'x', from: 'f', to: 't', backup: null, replaces: false}} : {ok: true};
  return {ok: true, text: async () => JSON.stringify(j)};
};
await import(pathToFileURL(path.join(S, 'skills-view.js')).href);
globalThis.skillsView.open(true);
await new Promise(r => setTimeout(r, 50));

const reqs = els.skReqs ? els.skReqs.innerHTML : '';
test('Search tab: the search request is listed', reqs.includes('a search') ? '' : reqs);
test('Search tab: the derive job is not', !reqs.includes('routes') ? '' : reqs);
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
