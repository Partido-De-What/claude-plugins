// Mouse-look smoothness and flicker of the office (T9): node tools/test_pace.mjs
import {readFileSync} from 'node:fs';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';
const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const {pace, lookFilter} = await import(pathToFileURL(path.join(S, 'office-pace.js')).href);
let passed = 0, total = 0;
const test = (name, fn) => { total++; try { const bad = fn(); if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } } catch (e) { console.log(`FAIL ${name}: ${e.stack || e}`); } };
/** the frames drawn in two seconds on a screen of `hz`, with the cap `fps`: their gaps in ms */
const gaps = (hz, fps) => {
  const s = {last: 0, acc: 0, drewAt: 0}, at = []; let now = 0;
  for (let i = 0; i < 2 * hz; i++) { now += 1000 / hz; if (pace(s, now, fps)) at.push(now); }
  const g = at.slice(5).map((t, i) => t - at[i + 4]);
  return {n: at.length, min: Math.min(...g), max: Math.max(...g)};
};
test('the old 60 cap on a 75 Hz screen draws frames of uneven gaps (13 and 27 ms): the judder of the turn', () => {
  const g = gaps(75, 60); return g.max - g.min > 10 ? '' : JSON.stringify(g);
});
test('looking round (cap 144): 75 and 144 Hz screens draw every tick, the gaps are even', () => {
  const a = gaps(75, 144), b = gaps(144, 144), c = gaps(60, 144);
  return a.max - a.min < 0.5 && b.max - b.min < 0.5 && c.max - c.min < 0.5 && a.n >= 149 && b.n >= 287 ? '' : JSON.stringify({a, b, c});
});
test('looking round on a 240 Hz screen does not draw every tick (about 160 frames a second)', () => {
  const g = gaps(240, 144); return g.n > 250 && g.n < 400 ? '' : JSON.stringify(g);
});
test('the cap still holds for the rest (60 on a 60 Hz and a 144 Hz screen, 30 when calm)', () => {
  const a = gaps(60, 60), b = gaps(144, 60), c = gaps(60, 30);
  return a.n >= 118 && b.n >= 110 && b.n <= 130 && c.n >= 58 && c.n <= 62 ? '' : JSON.stringify({a, b, c});
});
test('office.js: the resolution is steered before the drawing, the resize observer draws again at once, the look is uncapped', () => {
  const o = readFileSync(path.join(S, 'office.js'), 'utf8');
  const steer = o.indexOf('  steerResolution(now);'), draw = o.indexOf('  drawScene(dt);');
  if (steer < 0 || draw < 0 || steer > draw) return 'steerResolution must come before drawScene in the frame';
  if (!/new ResizeObserver\(\(\) => \{ resize\(\); if \(framed\) drawScene\(0\); \}\)/.test(o)) return 'resize observer does not redraw';
  return /const look = pov && povLocked && locked\(\)/.test(o) && /pace\(PACE, now, fps\)/.test(o) ? '' : 'look cap';
});
test('the view log is in office.js (spike, lock, jump), for the user to read in the console', () => {
  const o = readFileSync(path.join(S, 'office.js'), 'utf8');
  return ["window.__viewLog", "vlog('spike'", "vlog('lock'", "vlog('jump'"].every(k => o.includes(k)) ? '' : 'missing';
});
test('?viewlog=1 (only then) queues the events with the view state and posts them in batches to /viewlog, stopping on a 404', () => {
  const o = readFileSync(path.join(S, 'office.js'), 'utf8');
  const need = ["VIEWLOG_ON = /[?&]viewlog\\b/", "post('viewlog', {events})", "VQ.splice(0, Math.max(1, n))", "48000", "[403, 404, 413].includes(r.status)", "spy(me, 'yaw'", "__viewSpyBoss?.(boss)", "stack,"];
  const miss = need.filter(k => !o.includes(k));
  return miss.length ? 'missing ' + miss : /if \(VIEWLOG_ON && VQ\.length < 400\)/.test(o) ? '' : 'queue not guarded by the flag';
});
const feed = (f, steps, t0 = 1000, dt = 7) => steps.map((d, i) => f.ok(d[0], d[1], t0 + i * dt));
test('look filter: the jump of the real log (3 events of 700 px after steps of tens, at the capture and in the middle) turns nothing', () => {
  const f = lookFilter(), hand = feed(f, [[12, 3], [30, 5], [22, 4], [40, 9], [35, 8]]);
  const jump = feed(f, [[704, 126], [710, 126], [710, 126]], 1040), back = feed(f, [[-678, -229], [-682, -229], [-684, -230]], 1100);
  const more = feed(f, [[20, 2], [25, 3]], 1200);
  return hand.every(Boolean) && !jump.some(Boolean) && !back.some(Boolean) && more.every(Boolean) ? '' : JSON.stringify([hand, jump, back, more]);
});
test('look filter: a real fast flick, rising (40, 90, 160, 220, 180, 120) and a quick one from steps of tens, passes whole', () => {
  const f = lookFilter(), r = feed(f, [[10, 1], [20, 2], [40, 3], [90, 5], [160, 8], [220, 10], [180, 9], [120, 6], [60, 3]]);
  const g = lookFilter(), q = feed(g, [[5, 0], [8, 1], [30, 2], [110, 4], [190, 6], [250, 9]], 5000);
  return r.every(Boolean) && q.every(Boolean) ? '' : JSON.stringify([r, q]);
});
test('look filter: nothing for 100 ms after a capture change (by time, not by count), then the hand; a rest clears the steps', () => {
  const f = lookFilter(); f.reset(2000);
  const early = [2001, 2010, 2040, 2060, 2090].map(t => f.ok(300, 0, t));         // five events inside 100 ms, all dropped
  const late = f.ok(15, 2, 2105), alone = f.ok(120, 4, 3000);                      // 120 px alone after a rest is a hand (the first step has no history: up to 160)
  return !early.some(Boolean) && late && alone && !f.ok(500, 0, 3010) ? '' : JSON.stringify([early, late, alone]);
});
test('look filter (E2): a real flick that starts from a rest at 300 px passes, the jump of 700 px after the same rest does not', () => {
  const f = lookFilter(), flick = f.ok(300, 10, 5000), g = lookFilter(), jump = g.ok(700, 126, 9000);
  const h = lookFilter(); h.ok(10, 1, 100); h.ok(12, 1, 107); const cut = h.ok(300, 0, 114);        // from steps of ten a 300 px step is still a jump of the cursor
  return flick && !jump && !cut ? '' : JSON.stringify([flick, jump, cut]);
});
test('office.js uses the filter and asks the raw input first, falling back to the normal capture', () => {
  const o = readFileSync(path.join(S, 'office.js'), 'utf8');
  return ['lookF.ok(dx, dy, performance.now())', 'lookF.reset(performance.now())', 'requestPointerLock?.({unadjustedMovement: true})', 'r?.catch?.(() => el.requestPointerLock())', 'lockMouse();'].filter(k => !o.includes(k)).join() || (/lockSkip|> 1500/.test(o) ? 'old filter left' : '');
});
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
