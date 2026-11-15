// The Skills view (0.19, D6): the Candidates tab. Dismissed candidates are hidden, the list is by score, each card has a score ring,
// the room chips count, a click opens the card and loads its diff (colored lines, escaped), Apply/Add start with a preview.
// node plugins/chatroom/scripts/tools/test_skills_cand.mjs
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
globalThis.localStorage = {getItem: () => JSON.stringify({tab: 'cand'}), setItem() {}};
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

const rows = () => els.skCandRows ? els.skCandRows.innerHTML : '';
const cards = rows().split('class="sk-row').slice(1);
test('4 cards: the dismissed one is hidden', cards.length === 4 && !rows().includes('>gone<') ? '' : cards.length);
test('sorted by score, high first', /9<\/b>[\s\S]*8<\/b>[\s\S]*6<\/b>[\s\S]*3<\/b>/.test(rows()) ? '' : rows().slice(0, 400));
test('the score ring: --p and the high / low class', /sk-score hi" style="--p:90"/.test(rows()) && /sk-score lo" style="--p:30"/.test(rows()) ? '' : rows().slice(0, 600));
test('a name is escaped', !rows().includes('<img') && rows().includes('&lt;img') ? '' : rows().slice(0, 400));
test('covered_by and added are shown', /sk-warn/.test(rows()) && /sk-ok/.test(rows()) ? '' : rows());
const chips = els.skRoomChips ? els.skRoomChips.innerHTML : '';
test('room chips count the visible candidates', /allRooms[^<]*<span class="n">4/.test(chips) && /room-a[^<]*[^]*?<span class="n">2/.test(chips) && /room-b[^<]*<span class="n">2/.test(chips) ? '' : chips);
const jobs = els.skJobs ? els.skJobs.innerHTML : '';
test('jobs: only derive/suggest/improve requests, the text escaped, the failure shows its log', jobs.includes('failed') && jobs.includes('skills-temp/r8.log') && !jobs.includes('<b>') && !jobs.includes('a search') ? '' : jobs);

// click on a card: it opens and its diff is fetched
const click = t => handlers.click.forEach(f => f({target: {classList: {contains: () => false}, closest: () => t}}));
const id = 'cand:bb:imp';
click({dataset: {cand: id}});
await new Promise(r => setTimeout(r, 20));
const open = rows();
test('the card opens and asks for the diff once', open.includes('sk-more') && calls.filter(c => c.action === 'diff' && c.id === id).length === 1 ? '' : JSON.stringify(calls));
test('the diff lines are colored and escaped', /class="a">\+new/.test(open) && /class="d">-old &lt;i&gt;x&lt;\/i&gt;/.test(open) && /class="h">@@/.test(open) && !open.includes('<i>') ? '' : open.slice(open.indexOf('sk-diff'), open.indexOf('sk-diff') + 500));
test('an improvement offers "apply", not "add"', open.includes('skillsv.cand.apply') && !open.includes('skillsv.cand.add"') ? '' : open.slice(-400));

// apply: a preview first (no confirm), then nothing is written
click({dataset: {act: 'cpromote', cid: id}});
await new Promise(r => setTimeout(r, 20));
const pr = calls.filter(c => c.action === 'promote');
test('apply asks for a preview (confirm false) and does not confirm by itself', pr.length === 1 && pr[0].confirm === false ? '' : JSON.stringify(pr));
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
