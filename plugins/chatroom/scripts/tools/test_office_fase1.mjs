// Tests of the office of 0.12 that need no browser: node tools/test_office_fase1.mjs (exit 0 when all pass, one PASS/FAIL line each, the last line N/N passed).
// What a browser must see (the look, the first-person view on a wall) is checked by hand in the dev preview: the first-person guard here only reads the source.
import {readFileSync} from 'node:fs';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url)), S = path.resolve(HERE, '..');
const url = f => pathToFileURL(path.join(S, f)).href;
const src = f => readFileSync(path.join(S, f), 'utf8');
let passed = 0, total = 0;
const test = (name, fn) => {
  total++;
  try { const bad = fn(); if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } }
  catch (e) { console.log(`FAIL ${name}: ${e.stack || e}`); }
};
const near = (a, b, tol = 1e-3) => Math.abs(a - b) <= tol;
globalThis.I18N = {tables: () => ({}), table: () => ({}), text: k => k, t: k => k};          // the modules read their texts when they are used, not when they load

// ------------------------------------------------------------------ the door in front of the arcade (T1)
const {DEFAULT_LAYOUT, resolve, floorPlan} = await import(url('office-layout.js'));
const {ARCADE_AT} = await import(url('office-arcade.js'));
{
  const placed = resolve(DEFAULT_LAYOUT);
  test('arcade: the west door of the common room has no leaf and no box', () => {
    const leaf = placed.doors.filter(d => d.hinge[0] === 0 && d.hinge[1] > 5 && d.hinge[1] < 10);
    const boxes = placed.boxes.filter(b => b.hd === 0.04 && b.x < 1.5 && b.z > 5.5 && b.z < 8);
    return leaf.length || boxes.length ? `${leaf.length} leaf, ${boxes.length} boxes` : '';
  });
  placed.boxes.push({x: ARCADE_AT.x, z: ARCADE_AT.z, hw: ARCADE_AT.hw, hd: ARCADE_AT.hd, rot: ARCADE_AT.rot});
  const fp = floorPlan(DEFAULT_LAYOUT, placed), A = ARCADE_AT;
  const sides = {left: {x: A.x - A.hw - 0.4, z: A.z}, frontLeft: {x: A.x - A.hw - 0.3, z: A.z + A.hd + 0.3}, front: {x: A.x, z: A.z + A.hd + 0.3},
                 frontRight: {x: A.x + A.hw + 0.3, z: A.z + A.hd + 0.3}, right: {x: A.x + A.hw + 0.4, z: A.z}};
  for (const [from, f] of Object.entries({plaza: {x: -3, z: 7.1}, room: {x: 4, z: 8}})) for (const [side, p] of Object.entries(sides)) {
    test(`arcade: ${side} side reachable from the ${from}`, () => {
      const r = fp.route(f, p), end = r && r[r.length - 1];
      return !r || !end ? 'no route' : Math.hypot(end.x - p.x, end.z - p.z) > 0.01 ? `the route ends ${Math.hypot(end.x - p.x, end.z - p.z).toFixed(2)} m short` : '';
    });
  }
}

// ------------------------------------------------------------------ the view turns round the eye (T2): the source guard
test('first person: the eye is pinned on the body axis and eyeLead is gone', () => {
  const o = src('office.js');
  if (/eyeLead/.test(o)) return 'eyeLead is back';
  if (!/pos\.x = boss\.pos\.x; pos\.z = boss\.pos\.z/.test(o)) return 'the eye is no longer pinned to boss.pos';
  if (!/if \(pov\) \{ boss\.root\.position\.x -= Math\.sin\(boss\.rot\) \* 0\.32/.test(o)) return 'the body is no longer set behind the eye';
  return '';
});

// ------------------------------------------------------------------ the volumes (T3)
globalThis.addEventListener = () => {};
const tvAt = (store, tag) => {
  globalThis.localStorage = {getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; }};
  return import(url('office-tv.js') + '?' + tag);
};
const camera = {matrixWorld: {elements: Array.from({length: 16}, (_, i) => (i === 10 ? -1 : 0))}};
{
  const fresh = await tvAt({}, 'fresh');
  test('volumes: the defaults are low (master 0.3, TV and arcade 0.5)', () => (near(fresh.mixLevel('tv'), 0.15) && near(fresh.mixLevel('arcade'), 0.15) && near(fresh.mixLevel('radio'), 0.3) ? '' : `tv ${fresh.mixLevel('tv')} arcade ${fresh.mixLevel('arcade')} radio ${fresh.mixLevel('radio')}`));
  const old = await tvAt({'chatroom.mix': '{"master":0.8,"tv":0.7,"mute":{}}'}, 'old');
  test('volumes: the levels saved under the old key are not read (a one-time reset)', () => (near(old.mixLevel('tv'), 0.15) ? '' : `tv ${old.mixLevel('tv')}`));
  const v2 = await tvAt({'chatroom.mix.v2': '{"master":0.8,"mute":{}}'}, 'v2');
  test('volumes: the levels saved under chatroom.mix.v2 are read', () => (near(v2.mixLevel('tv'), 0.4) ? '' : `tv ${v2.mixLevel('tv')}`));
  const area = {x0: -14.8, z0: -4.3, x1: -8.7, z1: 0.8}, src0 = {x: -12, z: -0.5}, gain = d => fresh.hear(area, src0, {x: area.x1 + d, z: -0.5}, camera, 4)[0];
  test('volumes: with reach 4 the sound is 0.563 at 1 m outside its room and gone at 4 m', () => (near(gain(1), 0.5625) && gain(4) === 0 && fresh.hear(area, src0, {x: -12, z: -0.5}, camera, 4)[0] === 1 ? '' : `${gain(1)} ${gain(4)}`));
  test('volumes: the TV is heard with reach 4, like the radio and the lofi', () => (/hear\(area, at, me, camera, 4\)/.test(src('office-tv.js')) ? '' : 'the TV calls hear() without its reach'));
}

// ------------------------------------------------------------------ the windows on the harness (T6)
const viz = await import(url('office-viz.js'));
test('check: severity by key', () => {
  const want = {'noproof:T3': 'err', 'flip:BETA:2:44': 'err', 'tag:12:ALFA': 'warn', 'budget:ALFA:1': 'warn', 'allidle:100': 'info', 'checkpoint:ALFA:1': 'info', 'weird:1': 'warn'};
  const bad = Object.entries(want).filter(([k, v]) => viz.sevOf(k) !== v).map(([k]) => k);
  return bad.length ? 'wrong: ' + bad.join(', ') : '';
});
test('check: the message a CHECK is about', () => {
  const ok = viz.refOf({key: 'tag:12:ALFA', text: 'ALFA has not answered'}) === 12 && viz.refOf({key: 'claim:BETA:44', text: 'BETA says 100% without evidence'}) === 44
    && viz.refOf({key: 'noproof:T3', text: 'T3 closed by X without proof'}) === null && viz.refOf({key: 'x', text: 'see #7 and #9'}) === 7;
  return ok ? '' : 'wrong ref';
});
test('check: the serious come first, the server order is kept inside a kind', () => {
  const s = viz.sortChecks([{key: 'tag:1:A', text: 'a'}, {key: 'noproof:T1', text: 'b'}, {key: 'gaps:T2', text: 'c'}, {key: 'loop:A:5', text: 'd'}]).map(c => c.text).join('');
  return s === 'bdac' ? '' : s;
});
test('budget: green under 60%, amber up to the limit, red from it, grey without a limit', () => {
  const c = viz.COL;
  return viz.budgetColor(10, 100) === c.ok && viz.budgetColor(60, 100) === c.warn && viz.budgetColor(99, 100) === c.warn && viz.budgetColor(100, 100) === c.err && viz.budgetColor(5, 0) === c.off ? '' : 'wrong colour';
});
{
  const who = new Map(['alfa', 'beta', 'gamma', 'lead'].map(n => [n, n.toUpperCase()])), now = 1000;
  const m = (n, from, text, ts, kind) => ({n, from, text, ts, kind});
  test('tag links: a tag with no answer is open; an answer (message, status, board line) closes it; a break does not', () => {
    const open = viz.tagLinks([m(1, 'LEAD', '@ALFA do it', 990), m(2, 'ALFA', '', 995, 'idle')], who, now);
    const done = viz.tagLinks([m(1, 'LEAD', '@ALFA do it', 990), m(2, 'ALFA', 'ok', 995, 'status')], who, now);
    return open.length === 1 && open[0].answeredTs === 0 && done.length === 1 && done[0].answeredTs === 995 ? '' : JSON.stringify({open, done});
  });
  test('tag links: @all, a self tag, a name nobody has and a quoted address are no link; two tags to one person are one link', () => {
    const l = viz.tagLinks([m(1, 'LEAD', '@all hello', 990), m(2, 'ALFA', '@ALFA me', 991), m(3, 'ALFA', '@nobody x', 992), m(4, 'ALFA', 'mail a@beta.org', 993), m(5, 'BETA', '@GAMMA and @gamma', 994)], who, now);
    return l.length === 1 && l[0].to === 'GAMMA' ? '' : JSON.stringify(l);
  });
  test('tag links: an answered link fades after 25 s, an old tag is dropped after 10 minutes', () => {
    const all = [m(1, 'LEAD', '@ALFA x', 900), m(2, 'ALFA', 'ok', 950)];
    const late = viz.tagLinks(all, who, 980), gone = viz.tagLinks(all, who, 990), old = viz.tagLinks([m(1, 'LEAD', '@BETA x', 100)], who, now);
    return late.length === 0 && gone.length === 0 && old.length === 0 ? '' : JSON.stringify({late, gone, old});
  });
  test('tag links: a second tag from the same person to the same person is one line, the newest', () => {
    const l = viz.tagLinks([m(1, 'LEAD', '@ALFA one', 980), m(2, 'LEAD', '@ALFA two', 990), m(3, 'BETA', '@ALFA three', 991)], who, now);
    return l.length === 2 && l[0].n === 2 && l[1].n === 3 ? '' : JSON.stringify(l);
  });
  test('tag links: at most eight, the newest', () => {
    const names = ['A', 'B', 'C', 'D', 'E', 'F'], w2 = new Map([...names.map(n => [n.toLowerCase(), n]), ['x', 'X'], ['y', 'Y'], ['z', 'Z'], ['v', 'V']]);
    const all = Array.from({length: 12}, (_, i) => m(i + 1, names[i % 6], `@${['x', 'y', 'z', 'v'][i % 4]} ${i}`, 990));
    const l = viz.tagLinks(all, w2, now);
    return l.length === 8 && l[7].n === 12 ? '' : `${l.length} links, last #${l[l.length - 1]?.n}`;
  });
}
test('loans: a piece lent and taken by someone else, not given back', () => {
  const l = viz.loans([{id: 'T1', state: 'taken', lender: 'A', owner: 'B'}, {id: 'T2', state: 'taken', lender: 'A', owner: 'A'}, {id: 'T3', state: 'done', lender: 'A', owner: 'B'},
                       {id: 'T4', state: 'taken', owner: 'B'}, {id: 'T5', state: 'taken', lender: 'A', owner: 'C', accepted: false}]);
  return l.length === 2 && l[0].id === 'T1' && l[0].accepted === true && l[1].id === 'T5' && l[1].accepted === false ? '' : JSON.stringify(l);
});
test('lamp: everyone idle, and at least one agent', () => (viz.allIdle(['A', 'B'], {A: {idle: true}, B: {idle: true}}) && !viz.allIdle(['A', 'B'], {A: {idle: true}, B: {idle: false}}) && !viz.allIdle([], {}) ? '' : 'wrong'));
test('head flags: "!!! #N" for 3 minutes, a finding for one', () => {
  const f = viz.flagsOf({missed: [41, 42, 43], ts: 900, kind: 'status'}, 1000), g = viz.flagsOf({missed: [41], ts: 700}, 1000), h = viz.flagsOf({kind: 'finding', ts: 950}, 1000), k = viz.flagsOf({kind: 'finding', ts: 900}, 1000);
  return f.length === 1 && f[0][1] === '!!! #41 +2' && g.length === 0 && h.length === 1 && h[0][0] === 'find' && k.length === 0 ? '' : JSON.stringify({f, g, h, k});
});

console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
