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

// ------------------------------------------------------------------ a new desk shuts no passage (the office grows with the agents)
{
  const {workstation, findWorkstation} = await import(url('office-layout.js'));
  const grow = (target, rule) => {                                       // the pod blocks and single desks as office.js adds them, until `target` desks stand
    const placed = resolve(DEFAULT_LAYOUT), floor = floorPlan(DEFAULT_LAYOUT, placed), at = (x, z, r = 0) => ({x: x + Math.sin(r) * 0.78, z: z + Math.cos(r) * 0.78});
    const desks = placed.desks.map(d => ({g: {position: {x: d.x, z: d.z}}, seat: at(d.x, d.z, d.rot)}));
    const addPod = () => {
      for (const [x, z] of DEFAULT_LAYOUT.podSlots) {
        let free = true;
        for (let dx = -2; dx <= 2 && free; dx += 0.25) for (let dz = -2; dz <= 2; dz += 0.25) if (floor.blocked(x + dx, z + dz, 0.05)) { free = false; break; }
        if (!free) continue;
        const r = resolve({items: [{type: 'pod', x, z}], pods: DEFAULT_LAYOUT.pods}); floor.addBoxes(r.boxes);
        for (const d of r.desks) desks.push({g: {position: {x: d.x, z: d.z}}, seat: at(d.x, d.z, d.rot)});
        return true;
      }
      return false;
    };
    const greedy = () => {                                               // the rule of 0.11: the free spot nearest to the desks, whatever it shuts
      const cx = desks.reduce((a, d) => a + d.g.position.x, 0) / desks.length, cz = desks.reduce((a, d) => a + d.g.position.z, 0) / desks.length;
      const fits = (x, z) => { for (let dx = -1.0; dx <= 1.0; dx += 0.25) for (let dz = -0.6; dz <= 1.3; dz += 0.25) if (floor.blocked(x + dx, z + dz, 0.05)) return false; return true; };
      let best = null;
      for (let x = -DEFAULT_LAYOUT.size[0] / 2 + 1.5; x < DEFAULT_LAYOUT.size[0] / 2 - 1.5; x += 0.5) for (let z = -DEFAULT_LAYOUT.size[1] / 2 + 1; z < DEFAULT_LAYOUT.size[1] / 2 - 1.5; z += 0.5)
        if (fits(x, z) && (!best || Math.hypot(x - cx, z - cz) < best.d)) best = {x, z, d: Math.hypot(x - cx, z - cz)};
      if (!best) return false;
      const out = {boxes: [], desks: []}; workstation(out, best.x, best.z, 0); floor.addBoxes(out.boxes); desks.push({g: {position: {x: best.x, z: best.z}}, seat: at(best.x, best.z)});
      return true;
    };
    const careful = () => { const f = findWorkstation(floor, {size: DEFAULT_LAYOUT.size, desks, seats: desks.map(d => d.seat)}); if (!f) return false; desks.push({g: {position: {x: f.x, z: f.z}}, seat: at(f.x, f.z)}); return true; };
    while (desks.length < target) if (!addPod() && !(rule === 'greedy' ? greedy() : careful())) break;
    return {desks: desks.length, shut: floor.shutOff({x: -1, z: 3}, desks.map(d => d.seat))};
  };
  test('desks: the rule of 0.11 shuts seats off at 20 desks (the case the new rule is for)', () => { const r = grow(20, 'greedy'); return r.shut > 0 ? '' : `${r.shut} seats shut`; });
  for (const n of [20, 26]) test(`desks: with ${n} desks every seat can still be walked to from the plaza`, () => { const r = grow(n, 'careful'); return r.desks === n && r.shut === 0 ? '' : `${r.desks} desks, ${r.shut} seats shut`; });
  test('desks: shutOff counts what route() cannot reach', () => {
    const placed = resolve(DEFAULT_LAYOUT), fp = floorPlan(DEFAULT_LAYOUT, placed), from = {x: -1, z: 3};
    const pts = [{x: 4, z: 8}, {x: 12, z: -7.7}, {x: 0.4, z: 5.5}, {x: -12, z: 4}];
    const byRoute = pts.filter(p => !fp.route(from, p)).length;
    return fp.shutOff(from, pts) === byRoute ? '' : `flood ${fp.shutOff(from, pts)}, route ${byRoute}`;
  });
  test('desks: office.js puts a new desk only where findWorkstation keeps the seats reachable', () => (/findWorkstation\(FLOOR,/.test(src('office.js')) ? '' : 'addWorkstation does not use findWorkstation'));
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
  test('tag links: an answer that tags the tagger back closes the link and opens none; a later ping from the same pair is the one line, open again', () => {
    const one = viz.tagLinks([m(1, 'ALFA', '@BETA question', 990), m(2, 'BETA', '@ALFA ok', 995)], who, now);
    const two = viz.tagLinks([m(1, 'ALFA', '@BETA question', 990), m(2, 'BETA', '@ALFA ok', 995), m(3, 'ALFA', '@BETA and one more', 997)], who, now);
    return one.length === 1 && one[0].from === 'ALFA' && one[0].answeredTs === 995 && two.length === 1 && two[0].answeredTs === 0 && two[0].n === 3 ? '' : JSON.stringify({one, two});
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
  test('tag links: two people who tag each other are one line, in the state of the latest tag', () => {
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
test('bridge: a request comes in while it waits and goes out once approved; an ask goes out while it waits and comes in once approved', () => {
  const seen = new Map(), share = {requests: [{id: 1, status: 'pending'}, {id: 2, status: 'approved'}, {id: 3, status: 'denied'}], asks: [{id: 1, status: 'pending'}, {id: 2, status: 'approved'}]};
  const f = viz.bridgeFlights(share, 100, seen).map(x => x.dir + (x.accepted ? '+' : '-')).join(' ');
  return f === 'in- out+ out- in+' ? '' : f;
});
test('bridge: an approved flight lasts 20 s from the moment it was first seen; at most four fly', () => {
  const seen = new Map(), share = {requests: [{id: 2, status: 'approved'}], asks: []};
  const a = viz.bridgeFlights(share, 100, seen).length, b = viz.bridgeFlights(share, 119, seen).length, c = viz.bridgeFlights(share, 121, seen).length;
  const many = viz.bridgeFlights({requests: Array.from({length: 9}, (_, i) => ({id: i, status: 'pending'})), asks: []}, 0, new Map()).length;
  return a === 1 && b === 1 && c === 0 && many === 4 ? '' : `${a} ${b} ${c} ${many}`;
});
test('bridge: nothing flies when the common room is not shared or there is no bridge', () => (viz.bridgeFlights(null, 0, new Map()).length === 0 && viz.bridgeFlights({}, 0, new Map()).length === 0 ? '' : 'a flight with no share'));
test('lamp: everyone idle, and at least one agent', () => (viz.allIdle(['A', 'B'], {A: {idle: true}, B: {idle: true}}) && !viz.allIdle(['A', 'B'], {A: {idle: true}, B: {idle: false}}) && !viz.allIdle([], {}) ? '' : 'wrong'));
test('head flags: "!!! #N" for 3 minutes, a finding for one', () => {
  const f = viz.flagsOf({missed: [41, 42, 43], ts: 900, kind: 'status'}, 1000), g = viz.flagsOf({missed: [41], ts: 700}, 1000), h = viz.flagsOf({kind: 'finding', ts: 950}, 1000), k = viz.flagsOf({kind: 'finding', ts: 900}, 1000);
  return f.length === 1 && f[0][1] === '!!! #41 +2' && g.length === 0 && h.length === 1 && h[0][0] === 'find' && k.length === 0 ? '' : JSON.stringify({f, g, h, k});
});

console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
