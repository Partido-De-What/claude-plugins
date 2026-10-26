// Tests of the Hangar of the Gates (office-hangar.js) that need no browser: node tools/test_hangar.mjs (exit 0 when all pass, one PASS/FAIL line
// each, the last line N/N passed). What a browser must see (the look, the board turning, the easter eggs) is checked in the preview with ?hangar=demo.
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
globalThis.I18N = {text: (k, f = {}) => k.replace('office.hangar.', '') + (Object.keys(f).length ? JSON.stringify(f) : ''), t: k => k, tables: () => ({}), table: () => ({})};
const H = await import(url('office-hangar.js'));
const {DEFAULT_LAYOUT, resolve, floorPlan, CATALOG} = await import(url('office-layout.js'));
const {PX} = await import(url('office-floor.js'));

test('every floor picture draws inside its canvas', () => {
  for (const [name, K] of Object.entries(H.FLOOR.kinds)) {
    const [w, h] = K.fit ? [180, 140] : [K.m * PX, K.h || K.m * PX], rects = [];
    K.draw({set fillStyle(v) {}, fillRect: (x, y, rw, rh) => rects.push([x, y, rw, rh]), beginPath() {}, arc() {}, fill() {}}, w, h);
    if (rects.length < 10) return `${name}: draws nothing`;
    const out = rects.find(([x, y, rw, rh]) => x < 0 || y < 0 || x + rw > w + 1e-9 || y + rh > h + 1e-9);
    if (out) return `${name}: ${out} outside ${w}x${h}`;
  }
  return Object.values(H.FLOOR.alias).every(k => H.FLOOR.kinds[k]) ? '' : 'an alias points nowhere';
});
test('gate colour: the same for the same id, red without quota or down, violet for none', () => {
  const a = H.gateColor({id: 'groq', quota: 0.5}), b = H.gateColor({id: 'groq', quota: 0.9}), c = H.gateColor({id: 'nvidia', quota: 0.5});
  return a === b && a !== c && /^#[0-9a-f]{6}$/.test(a) && H.gateColor({id: 'x', quota: 0}) === H.PALETTE.red && H.gateColor({id: 'x', quota: 1, down: true}) === H.PALETTE.red
    && H.gateColor(null) === H.PALETTE.violet ? '' : `${a} ${b} ${c}`;
});
test('gates: the providers the roles use first, then those with quota, at most n', () => {
  const g = H.assignGates([{id: 'a', name: 'A', quota: 0}, {id: 'b', name: 'B', quota: 1}, {id: 'c', name: 'C', quota: 1}, {id: 'd', name: 'D', quota: 0}],
                          [{provider: 'd'}, {provider: 'd'}, {provider: 'c'}], 3).map(p => p.id).join('');
  return g === 'dcb' ? '' : g;
});
test('role events: a new role comes in, a role that changes host moves', () => {
  const e = H.roleEvents([{name: 'A', provider: 'groq', host: 'groq'}, {name: 'B', provider: 'kilo', host: 'kilo'}],
                         [{name: 'A', provider: 'nvidia', host: 'nvidia'}, {name: 'B', provider: 'kilo', host: 'kilo'}, {name: 'C', provider: 'zen', host: 'zen'}]);
  return JSON.stringify(e) === JSON.stringify([{kind: 'move', name: 'A', from: 'groq', to: 'nvidia'}, {kind: 'in', name: 'C', to: 'zen'}]) ? '' : JSON.stringify(e);
});
test('board rows: fixed widths, upper case, the state in words, the last row says how many more', () => {
  const W = H.COLS.reduce((a, b) => a + b, 0), roles = Array.from({length: 9}, (_, i) => ({name: 'r' + i, model: 'kimi-k3', host: 'groq', state: i ? 'service' : 'notokens'}));
  const rows = H.boardRows(roles, 6, 'en');
  return rows.length === 6 && rows.every(r => r.length === W) && rows[0].startsWith('R0') && rows[0].includes('KIMI-K3') && rows[0].includes('NOTOKENS')
    && rows[5].includes('MORE{"N":4}') && H.boardRows(roles.slice(0, 2), 6, 'en').length === 2 ? '' : JSON.stringify(rows);
});
test('the state column holds the longest state of both languages (CHANGING GATE, CAMBIO PORTA)', () => (H.COLS[3] - 1 >= 'CHANGING GATE'.length && H.COLS.reduce((a, b) => a + b, 0) === 50 ? '' : String(H.COLS)));
test('the board sleeps between midnight and one, a few seconds every ten minutes', () => {
  const at = (h, m, s) => new Date(2026, 9, 26, h, m, s);
  return H.asleep(at(0, 20, 3)) && !H.asleep(at(0, 21, 3)) && !H.asleep(at(0, 20, 9)) && !H.asleep(at(1, 0, 0)) && !H.asleep(at(12, 0, 0)) ? '' : 'wrong hours';
});
test('Konami: the whole sequence completes, a wrong key starts again, a first key restarts', () => {
  const seq = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
  let p = 0; for (const k of seq) p = H.konamiStep(p, k);
  return p === 10 && H.konamiStep(5, 'x') === 0 && H.konamiStep(5, 'ArrowUp') === 1 && H.CREDITS === 'ADRIAN CIPRIAN IANCU · ArtyomITA' ? '' : String(p);
});
test('clean: lists of plain records, quota in 0..1, unknown state is service, at most 3 strong points', () => {
  const d = H.clean({providers: [{id: 'a', quota: 7}, {quota: 1}, {id: 'b', quota: null}], roles: [{name: 'X', state: 'weird', strong: ['1', '2', '3', '4'], aa: 'x'}, {state: 'service'}], saved: {headroom: 'a'}});
  return d.providers.length === 2 && d.providers[0].quota === 1 && d.providers[1].quota === null && d.roles.length === 1 && d.roles[0].state === 'service'
    && d.roles[0].strong.length === 3 && d.roles[0].aa === 0 && d.saved.headroom === 0 && H.clean(null).roles.length === 0 ? '' : JSON.stringify(d);
});
test('demo: every state, a gate without quota, a gate down, a trophy, the machines and the router', () => {
  const d = H.demo(30, ['ALFA', 'BETA', 'GAMMA', 'DELTA']), st = new Set(d.roles.map(r => r.state));
  const later = H.demo(45, ['ALFA', 'BETA', 'GAMMA', 'DELTA']);
  return st.has('notokens') && (st.has('switch') || later.roles.some(r => r.state === 'switch')) && d.providers.some(p => p.quota === 0) && d.providers.some(p => p.down)
    && d.roles.some(r => r.trophy) && d.press + d.funnel === 1 && d.router && H.roleEvents(d.roles, later.roles).some(e => e.kind === 'move') ? '' : JSON.stringify(d.roles);
});
const plan = H.withLab(DEFAULT_LAYOUT.items);
test('the plan: 7 gates, the mysterious one, the table, the press and the funnel, once; the furniture in their place goes', () => {
  const n = t => plan.filter(it => it.type === t).length;
  const gone = ['rack', 'copier', 'corkboard', 'wallGraph'].filter(t => plan.some(it => it.type === t));
  return n('portal') === 7 && n('mysteryPortal') === 1 && n('holoTable') === 1 && n('press') === 1 && n('funnel') === 1 && !gone.length
    && H.withLab(plan).length === plan.length && plan.filter(it => it.type === 'sideChair').length === DEFAULT_LAYOUT.items.filter(it => it.type === 'sideChair').length
    && plan.filter(it => it.type === 'table').length === DEFAULT_LAYOUT.items.filter(it => it.type === 'table').length - 1 ? '' : `${n('portal')} gates; still there: ${gone}`;
});
test('the plan: every seat that could be walked to still can, the gates stand inside the room and clear of each other', () => {
  const L = {...DEFAULT_LAYOUT, items: plan}, P = resolve(L), P0 = resolve(DEFAULT_LAYOUT);
  const seats = P.seats.map(s => ({x: s.x, z: s.z})), seats0 = P0.seats.map(s => ({x: s.x, z: s.z}));
  const shut = floorPlan(L, P).shutOff({x: -1, z: 3}, seats), shut0 = floorPlan(DEFAULT_LAYOUT, P0).shutOff({x: -1, z: 3}, seats0);
  const gates = plan.filter(it => /ortal$/.test(it.type)).map(it => it.x).sort((a, b) => a - b);
  const apart = gates.every((x, i) => !i || x - gates[i - 1] >= 1.0), inside = gates.every(x => Math.abs(x) < 14.4);
  return shut <= shut0 && apart && inside && seats.length === seats0.length ? '' : `shut ${shut} (was ${shut0}), apart ${apart}, inside ${inside}, seats ${seats.length}/${seats0.length}`;
});
test('the catalog knows the new pieces, with their footprints', () => (['portal', 'mysteryPortal', 'holoTable', 'press', 'funnel'].every(t => CATALOG[t]?.foot) ? '' : 'missing'));
// the models, with a fake office-voxel.js that keeps only the bounds
class Vox { constructor() { this.b = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]; this.m = new Map(); }
  set(x, y, z, c) { const b = this.b; b[0] = Math.min(b[0], x); b[1] = Math.min(b[1], y); b[2] = Math.min(b[2], z); b[3] = Math.max(b[3], x); b[4] = Math.max(b[4], y); b[5] = Math.max(b[5], z); return this; }
  del() { return this; }
  box(x0, y0, z0, x1, y1, z1, c) { if (c === null || c === undefined) return this; return this.set(x0, y0, z0).set(x1, y1, z1); } }
const V = {Vox, mesh: v => v};
test('item(): the hangar builds its pieces and leaves the rest to the office', () => {
  const ok = ['portal', 'mysteryPortal', 'holoTable', 'press', 'funnel'].every(t => H.item({type: t}, V)?.b);
  return ok && H.item({type: 'plantTall', model: 'plantTall'}, V) === null ? '' : 'wrong';
});
test('the bodies fit their footprints (5 cm voxels): gate 1.0 x 0.3, table 2.6 x 0.9, press and funnel 0.9 x 0.9', () => {
  const size = t => { const b = H.item({type: t}, V).b; return [(b[3] - b[0] + 1) * 0.05, (b[5] - b[2] + 1) * 0.05]; };
  const want = {portal: [1.0, 0.35], holoTable: [2.6, 0.9], press: [0.9, 0.9], funnel: [0.95, 0.95]};
  const bad = Object.entries(want).filter(([t, [w, d]]) => { const [x, z] = size(t); return Math.abs(x - w) > 0.06 || Math.abs(z - d) > 0.06; });
  return bad.length ? bad.map(([t]) => `${t} ${size(t)}`).join('; ') : '';
});
test('the desk keeps the office desk\'s footprint and height (the plan\'s boxes still fit)', () => {
  const b = H.MODELS.workDesk().b;
  return [b[0], b[2], b[3], b[5], b[1], b[4]].join() === '0,0,31,15,0,13' ? '' : String(b);
});
test('office.js: the hangar for spawn rooms, the research walls only in a research room, the harness view kept in the hangar', () => {
  const o = readFileSync(path.join(S, 'office.js'), 'utf8');
  if (!/cfgJson\?\.mode === 'spawn' \? await import\('\.\/office-hangar\.js'\)/.test(o)) return 'no hangar import';
  if (!/const RES = LAB && !HANGAR \?/.test(o)) return 'research walls in the hangar';
  if (!/viz = visit \|\| \(LAB && !HANGAR\) \?/.test(o)) return 'viz switched off in the hangar';
  if (!/hangar\?\.update\(dt, t\)/.test(o) || !/HANGAR\.start\(/.test(o)) return 'live pieces not wired';
  return '';
});

console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
