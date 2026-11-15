// Tests of the skills bookcase of the office (office-skills.js) that need no browser: node tools/test_skills.mjs (exit 0 when all pass, one PASS/FAIL line
// each, the last line N/N passed). What a browser must see (the look of the shelf, the panel, the flags over the agents) is checked in the preview.
import {readFileSync} from 'node:fs';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const url = f => pathToFileURL(path.join(S, f)).href;
let passed = 0, total = 0;
const test = (name, fn) => {
  total++;
  try { const bad = fn(); if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } }
  catch (e) { console.log(`FAIL ${name}: ${e.stack || e}`); }
};
globalThis.I18N = {text: k => k, t: k => k, tables: () => ({}), table: () => ({})};
const K = await import(url('office-skills.js'));
const {DEFAULT_LAYOUT, CATALOG, SKILL_SHELF_ITEM, resolve} = await import(url('office-layout.js'));

const skills = [
  {id: 'plugin:p:b', name: 'b', brief: 'Merge PDF files', description: 'Merge several PDFs', origin: 'plugin', agents: ['A']},
  {id: 'user:-:a', name: 'a', brief: 'Cloud stacks', description: 'Deploy with CDK', origin: 'user', agents: []},
  {id: 'added:-:c', name: 'c', brief: 'Terse replies', description: '', origin: 'added', agents: ['A', 'B']},
];
const data = {skills, agents: [{name: 'A', skills: [{id: 'plugin:p:b', via: ['brief'], count: 0}, {id: 'gone:-:x', via: ['type'], count: 0}]}, {name: 'B', skills: []}]};

test('filter: by text (name, brief, description) and by origin, case-insensitive', () => {
  const ids = (q, o) => K.filterSkills(skills, q, o).map(s => s.name).join('');
  return ids('', '') === 'bac' && ids('PDF', '') === 'b' && ids('cdk', '') === 'a' && ids('', 'added') === 'c' && ids('pdf', 'user') === '' && ids('  ', '') === 'bac' ? '' : 'filter wrong';
});
test('agentBadges (D3): up to 3 names, the rest as +N, none for no agents; the origin filter is empty by default', () => {
  const B = K.agentBadges;
  return JSON.stringify(B(['A', 'B', 'C', 'D', 'E'])) === '["A","B","C","+2"]' && JSON.stringify(B(['A', 'B', 'C'])) === '["A","B","C"]' && B([]).length === 0 && B(null).length === 0
    && K.filterSkills(skills).length === skills.length ? '' : 'badges';
});
test('skillsOf: the skills of an agent, one that is not in the index is left out, an unknown agent has none', () => {
  const r = K.skillsOf(data, 'A');
  return r.length === 1 && r[0].skill.name === 'b' && K.skillsOf(data, 'B').length === 0 && K.skillsOf(data, 'nobody').length === 0 && K.skillsOf(null, 'A').length === 0 ? '' : JSON.stringify(r);
});
test('spines: skills that agents have first, from the top row; pulled out when an agent has it; never more than the grid', () => {
  const sp = K.spines(skills, {cols: 18, rows: 4});
  if (sp[0].id !== 'added:-:c' || sp[1].id !== 'plugin:p:b' || sp[2].id !== 'user:-:a') return 'order ' + sp.map(s => s.id);
  if (!sp[0].out || !sp[1].out || sp[2].out) return 'out flags';
  if (sp.some(s => s.row !== 3)) return 'first skills should sit on the top row (3)';
  const many = Array.from({length: 200}, (_, i) => ({id: 'user:-:s' + i, origin: 'user', agents: []})), big = K.spines(many, {cols: 18, rows: 4});
  if (big.length !== 72) return 'capacity ' + big.length;
  const cells = new Set(big.map(s => s.col + ',' + s.row));
  return cells.size === 72 && big.every(s => s.h >= 2 && s.h <= 4 && s.col >= 0 && s.col < 18 && s.row >= 0 && s.row < 4) ? '' : 'cells';
});
test('spine colour follows the origin, and the origins have a colour each', () => {
  const sp = K.spines(skills);
  return ['user', 'project', 'plugin', 'account', 'builtin', 'added'].every(o => /^#[0-9a-f]{6}$/i.test(K.ORIGIN_COLOR[o])) && new Set(Object.values(K.ORIGIN_COLOR)).size === 6
    && sp.find(s => s.id === 'user:-:a').color === K.ORIGIN_COLOR.user ? '' : 'colours';
});
test('the default office has the bookcase, with a catalog entry, a floor footprint, and nothing else on top of it', () => {
  if (!CATALOG.skillShelf || CATALOG.skillShelf.model !== 'skillShelf') return 'no catalog entry';
  if (!DEFAULT_LAYOUT.items.includes(SKILL_SHELF_ITEM)) return 'not in the default layout';
  const r = resolve(DEFAULT_LAYOUT), mine = r.boxes.find(b => Math.abs(b.x - SKILL_SHELF_ITEM.x) < 0.2 && Math.abs(b.z - SKILL_SHELF_ITEM.z) < 0.2);
  if (!mine) return 'no box';
  const half = b => { const c = Math.abs(Math.cos(b.rot || 0)), n = Math.abs(Math.sin(b.rot || 0)); return [b.hw * c + b.hd * n, b.hw * n + b.hd * c]; };    // the box turned, as a rectangle
  const [mx, mz] = half(mine), ov = r.boxes.filter(b => { const [hx, hz] = half(b); return b !== mine && Math.abs(b.x - mine.x) < hx + mx && Math.abs(b.z - mine.z) < hz + mz; });
  return ov.length ? 'overlaps ' + JSON.stringify(ov[0]) : '';
});
test('the shelf model is in office-voxel.js with the grid the module uses (cols x rows fit the frame)', () => {
  const v = readFileSync(path.join(S, 'office-voxel.js'), 'utf8');
  const g = /SKILL_SHELF = \{w: (\d+), cols: (\d+), rows: (\d+), rowY: \[([\d, ]+)\]/.exec(v);
  if (!g || !/export function skillShelf\(/.test(v)) return 'no model';
  const [, w, cols, rows, ys] = g, rowY = ys.split(',').map(Number);
  return +cols + 2 <= +w && rowY.length === +rows && rowY.every((y, i) => i === 0 || y - rowY[i - 1] === 5) ? '' : 'grid does not fit the frame';
});
test('every rule of the panel CSS is scoped under #office (office-ui.js has rules of the same names)', () => {
  const src = readFileSync(path.join(S, 'office-skills.js'), 'utf8'), css = /const CSS = `([\s\S]*?)`;/.exec(src)[1]
    .replace(/@keyframes oSk\w+ \{[^{}]*(\{[^{}]*\}[^{}]*)*\}/g, '').replace(/@media \(prefers-reduced-motion: reduce\) \{(.*)\}\s*$/gm, '$1');   // keyframes have own names (oSk*), the reduced-motion rule wraps scoped ones
  const bad = css.split('\n').filter(l => l.trim() && l.split('}').filter(r => r.trim()).some(r => !r.trim().split('{')[0].split(',').every(sel => sel.trim().startsWith('#office '))));
  if (/#office[^{,]*#office/.test(css)) return 'a selector names #office twice';
  return bad.length ? 'unscoped: ' + bad[0].slice(0, 80) : '';
});
test('office.js wires it: the item survives an old saved office, the bake leaves it alone, the badge and the click are there', () => {
  const o = readFileSync(path.join(S, 'office.js'), 'utf8');
  const need = ['conSkillShelf(', 'userData.skills', "createSkills(", "flags.push(['skill'", 'skills?.open()', 'skills?.update(t)', 'createSkills({THREE, V, camera,'];
  const miss = need.filter(n => !o.includes(n));
  return miss.length ? 'missing ' + miss : /window\.__skills|TMPDEBUG/.test(o) ? 'debug hook left in' : '';
});
test('sourceOf (D7): where a skill comes from in words: plugin name and version, written by you, project, account, built in, folder', () => {
  const T = {fromPlugin: n => 'P:' + n, writtenByYou: 'you', fromProject: 'proj', fromAccount: 'acc', fromBuiltin: 'built', fromFolder: 'dir'}, S = K.sourceOf;
  return S({origin: 'plugin', id: 'plugin:pdfkit:merge'}, T) === 'P:pdfkit' && S({origin: 'plugin', id: 'plugin:x:y', plugin: 'xx', version: '1.2'}, T) === 'P:xx 1.2' && S({origin: 'plugin', id: 'plugin:-:y'}, T) === 'P:?'
    && S({origin: 'user'}, T) === 'you' && S({origin: 'project'}, T) === 'proj' && S({origin: 'account'}, T) === 'acc' && S({origin: 'builtin'}, T) === 'built' && S({origin: 'added'}, T) === 'dir' ? '' : 'wrong';
});
test('the old category words are gone from the locales (tue/plugin/account/integrata do not say what they are): the 6 origins and their help lines exist in en and it', () => {
  const need = ['origin.user', 'origin.project', 'origin.plugin', 'origin.account', 'origin.builtin', 'origin.added', 'help.all', 'help.user', 'help.project', 'help.plugin', 'help.account', 'help.builtin', 'help.added', 'fromPlugin'];
  for (const l of ['en', 'it']) { const j = JSON.parse(readFileSync(path.join(S, '..', 'locales', l + '.json'), 'utf8')); const miss = need.filter(k => !j['skills.office.' + k]); if (miss.length) return l + ' missing ' + miss; }
  const it = JSON.parse(readFileSync(path.join(S, '..', 'locales', 'it.json'), 'utf8'));
  return it['skills.office.origin.user'] === 'Nella tua cartella skill' && it['skills.office.origin.account'] === 'Di Claude, sul tuo account' ? '' : 'it words';
});
test('sourceOf with the source of the server (D7 contract): marketplace/local/desktop plugin with version, repo, you/project/claude/builtin; the guess from the id stays as a fallback', () => {
  const T = {fromPlugin: n => 'P:' + n, fromRepo: n => 'R:' + n, writtenByYou: 'you', fromProject: 'proj', fromAccount: 'acc', fromBuiltin: 'built', fromFolder: 'dir'}, S = K.sourceOf, o = (kind, label, version) => ({origin: 'plugin', id: 'plugin:zz:q', source: {kind, label, version}});
  return S(o('marketplace', 'caveman@caveman', '4.0.1'), T) === 'P:caveman@caveman 4.0.1' && S(o('local', 'mine@mkt', null), T) === 'P:mine@mkt' && S(o('desktop', 'd@x', '1'), T) === 'P:d@x 1'
    && S(o('repo', 'o/n', 'bad48a0'), T) === 'R:o/n bad48a0' && S(o('you'), T) === 'you' && S(o('project'), T) === 'proj' && S(o('claude'), T) === 'acc' && S(o('builtin'), T) === 'built' && S({origin: 'plugin', id: 'plugin:zz:q'}, T) === 'P:zz' ? '' : 'wrong';
});
test('office-skills.js speaks the D7 contract: update_check / update_apply with the preview first, derive with source chat, the requests of the lead (via lead)', () => {
  const o = readFileSync(path.join(S, 'office-skills.js'), 'utf8');
  const need = ["action: 'update_check', skill: id", "ask('upd', {action: 'update_apply'", "ask('derive', {action: 'derive', source: {chat: true}})", "s.updatable", "r.via === 'lead'", "r.applied", "r.via === 'lead' ? T.deriveWaiting"];
  return need.filter(k => !o.includes(k)).join() ? 'missing ' + need.filter(k => !o.includes(k)) : '';
});
test('d8Lines: state of the check, the use (volte, esito, never, unused), the level with its parent; nothing missing breaks it', () => {
  const T = {useLine: (n, r) => n + 'x' + r, useOkFail: (a, b) => a + '/' + b, useUnused: n => 'unused' + n, useNone: 'none', levelUnder: n => '<' + n, level: {function: 'fn'}}, all = [{id: 'p:1', name: 'Boss'}];
  const L = K.d8Lines, a = L({verified: {state: 'verified'}, usage: {count: 3, rooms: 2, ok: 2, fail: 1}, level: 'function', parent: 'p:1'}, T, all);
  return a.verified === 'verified' && a.use === '3x2 · 2/1' && a.level === 'fn · <Boss' && L({verified: {state: 'failed'}}, T).verified === 'failed' && L({verified: {state: 'unverified'}}, T).verified === 'unverified' && L({}, T).verified === 'unverified'
    && L({usage: {count: 0, unused: true, scanned_rooms: 4}}, T).use === 'unused4' && L({usage: {count: 0}}, T).use === 'none' && L({level: 'step', parent: 'x:y'}, T, []).level === 'step · <x:y' && L({}, T).level === '' ? '' : JSON.stringify(a);
});
test('the 3D card shows D8 and sends the heavy actions to the chat panel (skillsView.show if it has it, else open), no logic of its own; the locale words exist', () => {
  const o = readFileSync(path.join(S, 'office-skills.js'), 'utf8'), need = ['d8Html(s, T) + updHtml(s, T)', "el('inchat')", 'window.skillsView?.show ? window.skillsView.show(id) : window.skillsView?.open?.(true)', 'o-vf-${s.verified.state}', "getComputedStyle(sv).display === 'none') window.officeMode?.('chat')"];
  const miss = need.filter(k => !o.includes(k)); if (miss.length) return 'missing ' + miss;
  for (const l of ['en', 'it']) { const j = JSON.parse(readFileSync(path.join(S, '..', 'locales', l + '.json'), 'utf8')); const m = ['vf.verified', 'vf.failed', 'vf.unverified', 'useLine', 'useOkFail', 'useNone', 'useUnused', 'level.strategy', 'level.function', 'level.step', 'levelUnder', 'openChat'].filter(k => !j['skills.office.' + k]); if (m.length) return l + ' missing ' + m; }
  return '';
});
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
