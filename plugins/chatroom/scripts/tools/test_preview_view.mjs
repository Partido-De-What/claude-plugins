// The Previews view (0.19, D4): one tile per agent with a preview, a grid of 1-4, focus on click, a tile reloads only when its mtime
// changes, html runs sandboxed, a src that is not the server's route or a local server is blocked, video starts muted. A stub page.
// node plugins/chatroom/scripts/tools/test_preview_view.mjs
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };

let DATA = {v: 1, previews: []};
const P = (agent, kind, src, mtime) => ({agent, kind, src, title: 'f', mtime, at: 1});
const made = [], els = {};
const cls = () => { const s = new Set(); return {s, toggle: (c, on) => ((on ?? !s.has(c)) ? s.add(c) : s.delete(c)), add: c => s.add(c), remove: c => s.delete(c), contains: c => s.has(c)}; };
const mk = () => {
  const e = {builds: 0, _h: '', dataset: {}, style: {}, classList: cls(), kids: [], listeners: {}, className: '', textContent: '',
    remove() { e.removed = true; }, querySelectorAll: () => [], appendChild(k) { e.kids.push(k); }, insertAdjacentElement() {},
    addEventListener(t, f) { e.listeners[t] = f; },
    querySelector: sel => (sel[0] === '#' && e._h.includes(`id="${sel.slice(1)}"`) ? (els[sel.slice(1)] ??= mk()) : null)};
  Object.defineProperty(e, 'innerHTML', {get: () => e._h, set: v => { e._h = v; e.builds++; }});
  made.push(e); return e;
};
globalThis.window = globalThis;
globalThis.document = {createElement: mk, getElementById: id => (id === 'officeBtn' ? null : (els[id] ??= mk())), head: {appendChild() {}}, body: {appendChild() {}, classList: {toggle() {}}}, hidden: false};
globalThis.location = {search: '', href: 'http://x/'};
globalThis.history = {replaceState() {}};
globalThis.addEventListener = () => {};
let poll = null;
globalThis.setInterval = f => { poll = f; return 0; };
globalThis.I18N = {text: (k, f) => k + (f ? JSON.stringify(f) : '')};
globalThis.fetch = async () => ({ok: true, json: async () => DATA});
await import(pathToFileURL(path.join(S, 'preview-view.js')).href);
const main = made[1];                         // the module creates: style, main, button
const sleep = () => new Promise(r => setTimeout(r, 20));
const tiles = () => made.filter(e => e.dataset && e.dataset.agent && !e.removed);
const tile = a => tiles().find(e => e.dataset.agent === a);
const grid = () => els.pvGrid;

DATA = {v: 1, previews: [P('A', 'html', 'preview/A/index.html', 10), P('B', 'image', 'preview/B/t.png', 10), P('C', 'video', 'preview/C/v.mp4', 10)]};
globalThis.previewView.open(true); await sleep();
test('3 previews: 3 tiles in a grid of 3', tiles().length === 3 && String(grid().dataset.n) === '3' ? '' : `${tiles().length} ${grid().dataset.n}`);
test('html: sandboxed iframe, no allow-same-origin, versioned by mtime', /<iframe src="preview\/A\/index\.html\?v=10" sandbox="allow-scripts"/.test(tile('A')._h) ? '' : tile('A')._h);
test('video starts muted', /<video[^>]* muted/.test(tile('C')._h) ? '' : tile('C')._h);
test('image tile has the zoom button', tile('B')._h.includes('data-pv="zoom"') ? '' : tile('B')._h);

const b0 = tile('A').builds;
await poll(); await sleep();
test('same mtime: the tile is not rebuilt', tile('A').builds === b0 ? '' : `${b0} -> ${tile('A').builds}`);
DATA = {v: 1, previews: [P('A', 'html', 'preview/A/index.html', 11), P('B', 'image', 'preview/B/t.png', 10), P('C', 'video', 'preview/C/v.mp4', 10)]};
await poll(); await sleep();
test('new mtime: only that tile reloads (?v=11)', tile('A').builds === b0 + 1 && tile('A')._h.includes('?v=11') && tile('B').builds === 1 ? '' : `${tile('A').builds} ${tile('B').builds}`);

const click = t => main.listeners.click({target: {closest: sel => (sel.includes('data-chip') ? null : {dataset: t.dataset ? {pv: 'focus'} : {}, closest: () => t})}});
click(tile('B'));
test('click on a tile: focus on it, the grid goes single', grid().classList.s.has('focus') && tile('B').classList.s.has('focus') && !tile('A').classList.s.has('focus') ? '' : 'no focus');
click(tile('B'));
test('click again: back to the grid', !grid().classList.s.has('focus') ? '' : 'still focus');

DATA = {v: 1, previews: [P('A', 'html', 'javascript:alert(1)', 1), P('B', 'html', 'https://evil.example/x', 1), P('C', 'url', 'http://127.0.0.1:5173/', 1), P('D', 'html', 'preview/D/a.html', 1)]};
await poll(); await sleep();
test('4 previews: grid of 4', String(grid().dataset.n) === '4' ? '' : grid().dataset.n);
test('javascript: src is blocked (no iframe, no link)', !tile('A')._h.includes('<iframe') && tile('A')._h.includes('previewv.blocked') && !tile('A')._h.includes('alert') ? '' : tile('A')._h);
test('a remote host is blocked', !tile('B')._h.includes('<iframe') ? '' : tile('B')._h);
test('a local server url: iframe with its own origin allowed', /<iframe src="http:\/\/127\.0\.0\.1:5173\/" sandbox="allow-scripts allow-same-origin/.test(tile('C')._h) ? '' : tile('C')._h);
DATA = {v: 1, previews: [P('A', 'html', 'http://localhost.evil.com/', 1), P('B', 'html', 'http://127.0.0.1.evil.com/', 1), P('C', 'html', 'http://127.0.0.1@evil.com/x', 1), P('D', 'html', 'http://localhost:5173', 1)]};
await poll(); await sleep();
test('look-alike hosts (localhost.evil.com, 127.0.0.1.evil.com, 127.0.0.1@evil.com) are blocked', ['A', 'B', 'C'].every(a => !tile(a)._h.includes('<iframe')) ? '' : 'one let through');
test('a bare local origin with a port still passes', tile('D')._h.includes('<iframe') ? '' : tile('D')._h);
DATA = {v: 1, previews: [P('D', 'html', 'preview/D/a.html', 1)]};
await poll(); await sleep();
test('an agent that turned its preview off loses its tile; grid of 1', tiles().length === 1 && String(grid().dataset.n) === '1' ? '' : `${tiles().length} ${grid().dataset.n}`);
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
