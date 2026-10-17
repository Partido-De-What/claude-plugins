// The research in the laboratory: what a research room knows (research.json: the contract, the phases, every run, the ideas, the evidence, the auditor's
// verdicts, the lamps) drawn on the lab's walls and floor. office.js loads this file only for research rooms, next to office-lab.js, and calls
// createResearch(ctx) once; the data is asked every 2.5 s while the office is seen (read only: nothing here writes to the room), and a panel is drawn
// again only when its own data changed (a canvas texture is uploaded only then). No imports: three.js, the voxel helpers and the lab's palette come in ctx.
//
// What office.js uses: CLEAR (wall spans the lab's furniture must keep free), createResearch(ctx) -> {update, attach, detach, feed, dispose, ...}.

/** wall spans the research panels use (x0..x1 along the north wall, z0..z1 from it): the laboratory's own pieces stay out of them */
export const CLEAR = [
  {name: 'results', x0: 4.4, x1: 8.95, z0: -10, z1: -8.7},
  {name: 'ideas', x0: -8.95, x1: -4.75, z0: -10, z1: -8.7},      // up to the CHECK panel of the control room (office-viz.js, x -4.6..-3.0)
];
/** where the panels stand: x, y (centre), z (in front of the wall's face, 12.5 cm in), size in metres */
export const AT = {
  results: {x: 6.675, y: 1.8, z: -9.845, w: 4.5, h: 2.2},
  strip: {x0: -12.9, x1: 5.9, z: 1.55, w: 0.8},                  // the phases, on the floor of the aisle in front of the open space (ends before the arena's lift)
  tower: {x: 4.2, z: -9.5},                                       // the stack light: GPU held, evaluation running
  ideas: {x: -8.0, y: 1.85, z: -9.845, w: 1.9, h: 1.95},
  verdicts: {x: -5.95, y: 1.85, z: -9.845, w: 1.9, h: 1.95},
  bin: {x: -8.0, z: -9.45},                                       // the refuted ideas' bin under the ideas board
  trophy: {x: 6.3, z: 1.55},                                      // at the end of the strip, where the arena's lift (x 6.65..8.55) begins
};
const FONT = '"Segoe UI", sans-serif';
const SS = 2;                                                    // canvases at twice their logical size: crisp text
const FALLBACK = {white: '#eef3f6', steel: '#aeb8c2', resin: '#8c969f', ink: '#0e1a22', cyan: '#4dd0e1', amber: '#ffb74d',
                  keep: '#43a047', discard: '#90a4ae', crash: '#e53935', run: '#4dd0e1', warn: '#ffb74d'};
const FORCE = /[?&]force\b/.test(location.search);               // the same switch as office.js: the debug hooks only with it

/** metrics for the eye: 4 digits at most, no trailing zeros */
const num = v => v == null ? '—' : String(+Number(v).toPrecision(4));
/** round values for an axis: 1, 2 or 5 times a power of ten */
function ticks(lo, hi) {
  const raw = (hi - lo) / 4, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p, step = (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p, out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
  return out;
}
/** how much better than the best a new run must be: the contract's minimum gain, absolute or a percentage */
function minGain(d, best) {
  const g = String(d.contract.min_gain || '0'), v = g.endsWith('%') ? Math.abs(best) * parseFloat(g) / 100 : parseFloat(g);
  return v > 0 ? v : 0;
}
/** "gpu_clock=1810MHz temp=59C" -> [{k: 'gpu_clock', v: 1810, u: 'MHz'}, ...] */
function readEnv(lines) {
  const out = [];
  for (const l of lines || []) for (const m of String(l).matchAll(/([A-Za-z_][\w.]*)\s*[=:]\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z%°]*)/g)) out.push({k: m[1], v: +m[2], u: m[3]});
  return out;
}
function wrap(g, text, x, y, maxW, lh, maxLines) {
  const words = String(text).split(/\s+/); let line = '', n = 0;
  for (const w of words) {
    const test = line ? line + ' ' + w : w;
    if (g.measureText(test).width > maxW && line) { if (++n >= maxLines) { g.fillText(line.replace(/.$/, '…'), x, y + (n - 1) * lh); return n; } g.fillText(line, x, y + (n - 1) * lh); line = w; }
    else line = test;
  }
  if (line) g.fillText(line, x, y + n * lh);
  return n + 1;
}
const fit = (g, text, w) => { let s = String(text); if (g.measureText(s).width <= w) return s; while (s.length > 1 && g.measureText(s + '…').width > w) s = s.slice(0, -1); return s + '…'; };

/** ctx: THREE, V (office-voxel.js), scene, renderer, camera, dom (the canvas pointer events come from), raycastables, lang(), paused(), pov() (first person
 *  with the mouse captured), lab (office-lab.js: PALETTE), url, every (ms between asks) */
export function createResearch(ctx) {
  const {THREE, V, scene, renderer, camera, dom, lang = () => 'en', paused = () => false, pov = () => false, url = 'research.json', every = 2500} = ctx;
  const PAL = ctx.lab?.PALETTE || FALLBACK;
  const root = new THREE.Group(); root.name = 'research'; root.visible = false; scene.add(root);          // shown when the room has a research to show (a room in research mode may not have started one)
  const raycaster = new THREE.Raycaster(), ndc = new THREE.Vector2(), tmp = new THREE.Vector3();
  const aniso = renderer.capabilities.getMaxAnisotropy();
  let lastT = 0, armAngle = 0, ver = 0, refutedN = 0, data = null, key = '', skew = 0, drawnLang = '', busy = false, disposed = false;
  const panels = {};

  // ------------------------------------------------------------------ panels
  /** a flat screen of w x h metres drawn in a canvas of ppm pixels a metre (twice that in device pixels), with a steel frame behind it */
  function panel(name, at, ppm, draw) {
    const lw = Math.round(at.w * ppm), lh = Math.round(at.h * ppm), c = document.createElement('canvas');
    c.width = lw * SS; c.height = lh * SS;
    const g = c.getContext('2d'); g.scale(SS, SS);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = aniso;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(at.w, at.h), new THREE.MeshBasicMaterial({map: tex, toneMapped: false}));
    mesh.position.set(at.x, at.y, at.z); mesh.rotation.set(at.tilt || 0, at.rot || 0, 0, 'YXZ'); root.add(mesh);
    const nx = Math.round(at.w * 10) + 2, ny = Math.round(at.h * 10) + 2;             // the frame: a steel slab 10 cm deeper than the screen on every side
    const frame = V.mesh(new V.Vox().box(0, 0, 0, nx - 1, ny - 1, 0, PAL.resin), {pivot: [nx / 2, ny / 2, 1], scale: 0.1, jitter: 0.02});
    frame.position.copy(mesh.position); frame.rotation.copy(mesh.rotation); frame.translateZ(-0.02); root.add(frame);
    const p = {name, at, lw, lh, g, tex, mesh, frame, draw, dirty: true, hit: []};
    mesh.userData.research = name;
    panels[name] = p; return p;
  }
  const redraw = p => { p.g.save(); p.g.clearRect(0, 0, p.lw, p.lh); p.draw(p, data); p.g.restore(); p.tex.needsUpdate = true; p.dirty = false; };
  /** canvas pixels -> metres on the wall (the panel's own axes), and back */
  const toLocal = (p, x, y, out) => out.set((x - p.lw / 2) / (p.lw / p.at.w), (p.lh / 2 - y) / (p.lh / p.at.h), 0);

  // ------------------------------------------------------------------ the results wall
  function drawResults(p, d) {
    const {g, lw, lh} = p;
    g.fillStyle = PAL.ink; g.fillRect(0, 0, lw, lh);
    g.strokeStyle = PAL.cyan; g.lineWidth = 3; g.strokeRect(2, 2, lw - 4, lh - 4);
    g.textBaseline = 'middle';
    if (!d) { g.fillStyle = PAL.steel; g.font = `600 26px ${FONT}`; g.fillText('…', 24, 30); return; }
    const c = d.contract, up = c.direction === 'max', runs = d.attempts.filter(a => a.kind === 'attempt'), vals = runs.map(a => a.metric).filter(v => v != null);
    if (d.baseline) vals.push(d.baseline.metric);
    // header: what is measured, how it stands
    g.fillStyle = '#16303a'; g.fillRect(6, 6, lw - 12, 46);
    g.fillStyle = PAL.cyan; g.font = `800 28px ${FONT}`; g.fillText(I18N.text('office.research.results', {}, lang()), 22, 30);
    g.fillStyle = PAL.white; g.font = `600 20px ${FONT}`;
    const head = `${c.metric} · ${I18N.text('office.research.best', {}, lang())} ${d.best ? num(d.best.metric) : '—'} · ${I18N.text('office.research.baseline', {}, lang())} ${d.baseline ? num(d.baseline.metric) : '—'} · ${d.evals}/${c.max_evals}`;
    g.fillText(fit(g, head, lw - 560), 232, 30);
    const lamp = (xx, yy, on, col, text) => { g.fillStyle = on ? col : '#2b3a43'; g.beginPath(); g.arc(xx, yy, 7, 0, 7); g.fill(); g.fillStyle = on ? PAL.white : PAL.discard; g.font = `500 18px ${FONT}`; g.fillText(fit(g, text, 300), xx + 14, yy); };
    const gpu = d.lamps.gpu, lock = d.lamps.lock;
    lamp(lw - 560 + 232 + 6, 20, !!gpu, PAL.warn, gpu ? I18N.text('office.research.gpuHeld', {by: gpu.by}, lang()) : I18N.text('office.research.gpuFree', {}, lang()));
    lamp(lw - 560 + 232 + 6, 42, !!(lock && lock.alive), PAL.run, lock && lock.alive ? I18N.text('office.research.lockBusy', {who: lock.who}, lang()) : I18N.text('office.research.lockFree', {}, lang()));
    // the chart
    const L = 74, R = 770, Tp = 78, B = 398, plotH = B - Tp, N = Math.max(4, ...runs.map(a => a.n), d.pending ? d.pending.n : 0);
    let lo = Math.min(...(vals.length ? vals : [0])), hi = Math.max(...(vals.length ? vals : [1]));
    if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }
    const padv = (hi - lo) * 0.08; lo -= padv; hi += padv;
    const x = n => L + (n - 0.5) / N * (R - L), y = v => Tp + (up ? hi - v : v - lo) / (hi - lo) * plotH;
    g.font = `500 18px ${FONT}`; g.textAlign = 'right';
    for (const v of ticks(lo, hi)) { g.strokeStyle = '#27414c'; g.lineWidth = 1; g.beginPath(); g.moveTo(L, y(v)); g.lineTo(R, y(v)); g.stroke(); g.fillStyle = PAL.steel; g.fillText(num(v), L - 8, y(v)); }
    g.textAlign = 'left'; g.fillStyle = PAL.discard; g.font = `500 16px ${FONT}`; g.fillText(c.direction === 'max' ? I18N.text('office.research.higher', {}, lang()) : I18N.text('office.research.lower', {}, lang()), L + 6, Tp - 9);   // which way is better (up)
    g.font = `500 18px ${FONT}`; g.textAlign = 'center'; const step = Math.max(1, Math.ceil(N / 12));
    for (let n = 1; n <= N; n += step) { g.fillStyle = PAL.steel; g.fillText(String(n), x(n), B + 38); }
    g.textAlign = 'left';
    const alive = runs.filter(a => a.state !== 'revoked' && a.status === 'keep' && a.metric != null);
    let best = null, bestAt = null; const stepPts = [];
    for (const a of alive) if (best === null || (up ? a.metric > best : a.metric < best)) { best = a.metric; bestAt = a.n; stepPts.push([a.n, a.metric]); }
    if (best !== null) {                                                                     // the band a new run has to clear: the minimum gain above the best
      const gain = minGain(d, best);
      if (gain) { const y0 = y(best), y1 = Math.max(Tp, y(up ? best + gain : best - gain)); g.fillStyle = PAL.amber + '66'; g.fillRect(L, Math.min(y0, y1), R - L, Math.max(3, Math.abs(y0 - y1))); }
    }
    if (d.baseline) { g.strokeStyle = PAL.discard; g.lineWidth = 2; g.setLineDash([12, 8]); g.beginPath(); g.moveTo(L, y(d.baseline.metric)); g.lineTo(R, y(d.baseline.metric)); g.stroke(); g.setLineDash([]);
      g.fillStyle = PAL.discard; g.font = `600 18px ${FONT}`; g.textAlign = 'right'; g.fillText(I18N.text('office.research.baseline', {}, lang()), R - 4, y(d.baseline.metric) - 12); g.textAlign = 'left'; }
    if (stepPts.length) { g.strokeStyle = PAL.keep; g.lineWidth = 4; g.lineJoin = 'round'; g.beginPath();
      stepPts.forEach(([n, v], i) => { if (!i) g.moveTo(x(n), y(v)); else { g.lineTo(x(n), y(stepPts[i - 1][1])); g.lineTo(x(n), y(v)); } });
      g.lineTo(R, y(best)); g.stroke(); }
    p.hit.length = 0; p.pointAt = {};
    for (const a of runs) {
      const col = PAL[a.status] || PAL.discard, rev = a.state === 'revoked', cx = x(a.n), cy = a.metric == null ? B + 14 : y(a.metric);
      p.hit.push({n: a.n, x: cx, y: cy}); p.pointAt[a.n] = {x: cx, y: cy};
      g.globalAlpha = rev ? 0.55 : 1; g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 3;
      if (a.metric == null) { g.beginPath(); g.moveTo(cx - 8, cy - 8); g.lineTo(cx + 8, cy + 8); g.moveTo(cx + 8, cy - 8); g.lineTo(cx - 8, cy + 8); g.stroke(); }
      else { g.beginPath(); g.arc(cx, cy, a.n === bestAt ? 11 : 8, 0, 7); if (rev) { g.setLineDash([4, 4]); g.stroke(); g.setLineDash([]); } else g.fill(); }
      g.globalAlpha = 1;
    }
    p.next = d.pending && d.pending.kind === 'attempt' ? {x: x(d.pending.n), y: best !== null ? y(best) : (Tp + B) / 2} : null;
    // the right column: provenance seals and the environment of the last run
    const X0 = 800, W0 = lw - X0 - 14;
    g.fillStyle = '#16303a'; g.fillRect(X0 - 8, 64, W0 + 16, 24);
    g.fillStyle = PAL.cyan; g.font = `800 20px ${FONT}`; g.fillText(I18N.text('office.research.provenance', {}, lang()), X0, 77);
    const sealRuns = runs.filter(a => a.status !== 'crash'), sealed = sealRuns.filter(a => a.built).length, cols = Math.floor(W0 / 22);
    sealRuns.slice(0, cols * 4).forEach((a, i) => { g.fillStyle = a.built ? PAL.keep : '#3a4b55'; g.fillRect(X0 + (i % cols) * 22, 100 + Math.floor(i / cols) * 22, 17, 17); });
    g.fillStyle = PAL.white; g.font = `500 18px ${FONT}`; g.fillText(fit(g, I18N.text('office.research.sealed', {n: sealed, m: sealRuns.length}, lang()), W0), X0, 205);
    g.fillStyle = '#16303a'; g.fillRect(X0 - 8, 226, W0 + 16, 24);
    g.fillStyle = PAL.cyan; g.font = `800 20px ${FONT}`; g.fillText(I18N.text('office.research.environment', {}, lang()), X0, 239);
    const lastEnv = [...d.attempts].reverse().find(a => a.env && a.env.length), env = readEnv(lastEnv && lastEnv.env);
    const clockMax = Math.max(0, ...d.attempts.flatMap(a => readEnv(a.env)).filter(e => /clock|mhz|freq/i.test(e.k)).map(e => e.v));
    let yy = 272;
    for (const e of env.slice(0, 3)) {
      const isT = /temp/i.test(e.k), isC = /clock|mhz|freq/i.test(e.k), frac = isT ? Math.max(0, Math.min(1, (e.v - 30) / 65)) : isC && clockMax ? Math.min(1, e.v / clockMax) : null;
      g.fillStyle = PAL.steel; g.font = `500 18px ${FONT}`; g.fillText(fit(g, `${e.k}`, W0 - 110), X0, yy);
      g.fillStyle = PAL.white; g.font = `700 20px ${FONT}`; g.textAlign = 'right'; g.fillText(`${num(e.v)}${e.u ? ' ' + e.u : ''}`, X0 + W0, yy); g.textAlign = 'left';
      if (frac !== null) { const hot = isT ? (e.v >= 85 ? PAL.crash : e.v >= 75 ? PAL.warn : PAL.keep) : (frac < 0.85 ? PAL.crash : frac < 0.95 ? PAL.warn : PAL.keep);
        g.fillStyle = '#27414c'; g.fillRect(X0, yy + 11, W0, 7); g.fillStyle = hot; g.fillRect(X0, yy + 11, W0 * frac, 7); yy += 38; } else yy += 28;
    }
    if (!env.length) { g.fillStyle = PAL.discard; g.font = `500 18px ${FONT}`; wrap(g, I18N.text('office.research.noEnv', {}, lang()), X0, 272, W0, 22, 3); }
    // the final evaluation: the search's number against the one the sealed final evaluator gave
    g.fillStyle = '#16303a'; g.fillRect(X0 - 8, 394, W0 + 16, 24);
    g.fillStyle = PAL.amber; g.font = `800 20px ${FONT}`; g.fillText(I18N.text('office.research.final', {}, lang()), X0, 407);
    g.fillStyle = PAL.white; g.font = `700 18px ${FONT}`;
    const f = d.final, delta = f && f.metric != null ? f.metric - f.search_metric : 0;
    wrap(g, f && f.metric != null ? I18N.text('office.research.finalLine', {search: num(f.search_metric), final: num(f.metric), delta: (delta >= 0 ? '+' : '') + num(delta)}, lang())
      : d.contract.final ? I18N.text('office.research.finalWait', {}, lang()) : I18N.text('office.research.finalNone', {}, lang()), X0, 434, W0, 22, 2);
    // the foot: contract changes after the baseline
    g.fillStyle = '#16303a'; g.fillRect(6, lh - 62, lw - 12, 56);
    g.fillStyle = PAL.amber; g.font = `800 20px ${FONT}`; g.fillText(I18N.text('office.research.amends', {}, lang()), 20, lh - 44);
    g.fillStyle = PAL.white; g.font = `500 18px ${FONT}`;
    const last = d.amends[d.amends.length - 1];
    g.fillText(fit(g, last ? I18N.text('office.research.amendLine', {n: last.after_run, by: last.by, what: last.what, reason: last.reason}, lang()) : I18N.text('office.research.amendNone', {}, lang()), lw - 40), 20, lh - 20);
  }
  panel('results', AT.results, 240, drawResults);

  // ------------------------------------------------------------------ the detail of a run, or of a worker's bench, under the pointer (nothing stays floating: it shows while you point)
  const tip = {c: document.createElement('canvas')};
  tip.c.width = 400 * SS; tip.c.height = 150 * SS;
  tip.g = tip.c.getContext('2d'); tip.g.scale(SS, SS);
  tip.tex = new THREE.CanvasTexture(tip.c); tip.tex.colorSpace = THREE.SRGBColorSpace; tip.tex.anisotropy = aniso;
  tip.mesh = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.6), new THREE.MeshBasicMaterial({map: tip.tex, toneMapped: false, transparent: true}));
  tip.mesh.visible = false; tip.mesh.renderOrder = 5; root.add(tip.mesh);
  function drawTip(a) {
    const g = tip.g;
    g.clearRect(0, 0, 400, 150);
    g.fillStyle = '#0b1318f2'; g.beginPath(); g.roundRect(2, 2, 396, 146, 12); g.fill();
    g.strokeStyle = PAL[a.status] || PAL.discard; g.lineWidth = 4; g.stroke();
    g.textBaseline = 'middle'; g.fillStyle = PAL.white; g.font = `800 24px ${FONT}`; g.fillText(`att-${a.n} · ${a.worker}`, 16, 28);
    g.fillStyle = PAL[a.status] || PAL.discard; g.font = `800 22px ${FONT}`;
    g.fillText(`${num(a.metric)} · ${I18N.text('office.research.st.' + a.status, {}, lang())}${a.secs != null ? ' · ' + Math.round(a.secs) + ' s' : ''}${a.state === 'revoked' ? ' · ' + I18N.text('office.research.revoked', {}, lang()) : ''}`, 16, 58);
    g.fillStyle = PAL.steel; g.font = `500 19px ${FONT}`; wrap(g, a.revoked_why || a.desc || '', 16, 88, 368, 24, 2);
    tip.tex.needsUpdate = true;
  }
  function drawTipBench(name) {
    const g = tip.g, st = benchState(data, name), col = st.paused ? PAL.warn : st.crashed ? PAL.crash : st.run ? PAL.run : PAL.discard;
    g.clearRect(0, 0, 400, 150);
    g.fillStyle = '#0b1318f2'; g.beginPath(); g.roundRect(2, 2, 396, 146, 12); g.fill();
    g.strokeStyle = col; g.lineWidth = 4; g.stroke();
    g.textBaseline = 'middle'; g.fillStyle = PAL.white; g.font = `800 24px ${FONT}`; g.fillText(fit(g, name, 368), 16, 28);
    g.fillStyle = col; g.font = `700 21px ${FONT}`;
    g.fillText(fit(g, st.paused ? I18N.text('office.research.wPaused', {}, lang()) : st.run ? I18N.text('office.research.wRunning', {n: st.run.n}, lang()) : st.crashed ? I18N.text('office.research.wCrashed', {}, lang()) : I18N.text('office.research.wIdle', {}, lang()), 368), 16, 58);
    g.fillStyle = PAL.steel; g.font = `500 18px ${FONT}`;
    g.fillText(fit(g, `work-${name}${st.w.idea ? ' · ' + st.w.idea : ''}${st.crashes ? ' · ' + I18N.text('office.research.wCrashes', {n: st.crashes}, lang()) : ''}`, 368), 16, 88);
    g.fillText(fit(g, st.w.best ? I18N.text('office.research.wBest', {n: st.w.best.n, v: num(st.w.best.metric)}, lang()) : I18N.text('office.research.wNone', {}, lang()), 368), 16, 116);
    tip.tex.needsUpdate = true;
  }
  let hoverKind = '', hoverId = null;
  function setHover(kind, id) {                                                      // kind: 'run' (id: its number), 'bench' (id: the worker's name) or '' (nothing)
    if (kind === hoverKind && id === hoverId) return; hoverKind = kind; hoverId = id;
    tip.mesh.visible = false; tip.mesh.quaternion.identity();
    if (kind === 'run') {
      const p = panels.results, a = data ? data.attempts.find(x => x.n === id) : null, at = a && p.pointAt && p.pointAt[id];
      if (!a || !at) return;
      drawTip(a);
      toLocal(p, at.x, at.y, tmp);                                                    // above the point, inside the wall's screen
      const hx = Math.max(-p.at.w / 2 + 0.85, Math.min(p.at.w / 2 - 0.85, tmp.x)), hy = Math.max(-p.at.h / 2 + 0.4, Math.min(p.at.h / 2 - 0.45, tmp.y + 0.45));
      tip.mesh.position.set(p.at.x + hx, p.at.y + hy, p.at.z + 0.03); tip.mesh.visible = true;
    } else if (kind === 'bench') {
      const b = benches.get(id); if (!b || !data) return;
      drawTipBench(id); b.desk.g.getWorldPosition(tip.mesh.position); tip.mesh.position.y = 1.6; tip.mesh.visible = true;   // faces the camera: update() turns it
    }
  }
  let moveAt = 0;
  function pick(ev) {
    const p = panels.results; if (!p || !data || paused()) return;
    if (pov()) ndc.set(0, 0); else { const r = dom.getBoundingClientRect(); ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1); }
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObject(p.mesh, false)[0];
    if (hit && hit.uv) {
      const px = hit.uv.x * p.lw, py = (1 - hit.uv.y) * p.lh;
      let near = null, dist = 26;                                                     // within 26 canvas pixels of a point
      for (const h of p.hit) { const dd = Math.hypot(h.x - px, h.y - py); if (dd < dist) { dist = dd; near = h.n; } }
      return near != null ? setHover('run', near) : setHover('', null);
    }
    const bh = benches.size ? raycaster.intersectObjects(benchHits, false)[0] : null;      // a worker's desk: its hit box (invisible)
    setHover(bh ? 'bench' : '', bh ? bh.object.userData.worker : null);
  }
  const onMove = ev => { const now = performance.now(); if (now - moveAt < 40) return; moveAt = now; pick(ev); };
  dom.addEventListener('pointermove', onMove, {passive: true});

  // ------------------------------------------------------------------ the marker of the run in progress (a ring on the wall, pulsing)
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.05, 0.07, 32), new THREE.MeshBasicMaterial({color: PAL.run, transparent: true, toneMapped: false, depthWrite: false}));
  ring.visible = false; ring.renderOrder = 4; root.add(ring);

  // ------------------------------------------------------------------ the phases, on the floor
  const PHASES = ['contract', 'drafting', 'investigation', 'evidence', 'final', 'report', 'closed'];
  const stripLen = AT.strip.x1 - AT.strip.x0, segLen = stripLen / PHASES.length;
  function drawStrip(p, d) {
    const {g, lw, lh} = p, sw = lw / PHASES.length, cur = d ? d.phase : -1;
    g.fillStyle = '#0a1217'; g.fillRect(0, 0, lw, lh);
    PHASES.forEach((k, i) => {
      const x0 = i * sw + 4, x1 = (i + 1) * sw - 4, done = i < cur, now = i === cur;
      g.beginPath(); g.moveTo(x0, 5); g.lineTo(x1 - 26, 5); g.lineTo(x1, lh / 2); g.lineTo(x1 - 26, lh - 5); g.lineTo(x0, lh - 5); g.lineTo(x0 + 26, lh / 2); g.closePath();
      g.fillStyle = done ? '#1c4a27' : now ? PAL.cyan : '#1b262d'; g.fill();
      g.lineWidth = 3; g.strokeStyle = done ? PAL.keep : now ? '#e0f7fa' : '#33444d'; g.stroke();
      g.fillStyle = done ? '#c8f0cd' : now ? PAL.ink : '#6f8591'; g.font = `800 34px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText((done ? '✓ ' : '') + I18N.text('kernel.phase.' + k, {}, lang()).toUpperCase(), (x0 + x1) / 2 + 8, lh / 2 + 2);
    });
    g.textAlign = 'left';
  }
  const stripPanel = (() => {                                                           // a flat strip on the floor: texture only, no frame
    const lw = Math.round(stripLen * 100), lh = Math.round(AT.strip.w * 100), c = document.createElement('canvas');
    c.width = lw * SS; c.height = lh * SS; const g = c.getContext('2d'); g.scale(SS, SS);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = aniso;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(stripLen, AT.strip.w), new THREE.MeshBasicMaterial({map: tex, toneMapped: false, polygonOffset: true, polygonOffsetFactor: -12, polygonOffsetUnits: -24}));   // above every floor zone (office-floor.js pulls the zone of layer n by -n, -2n)
    mesh.rotation.x = -Math.PI / 2; mesh.position.set((AT.strip.x0 + AT.strip.x1) / 2, 0.012, AT.strip.z); root.add(mesh);
    const p = {name: 'strip', lw, lh, g, tex, mesh, draw: drawStrip, dirty: true, at: {w: stripLen, h: AT.strip.w}};
    panels.strip = p; return p;
  })();
  const glowMat = new THREE.MeshBasicMaterial({color: PAL.cyan, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false, polygonOffset: true, polygonOffsetFactor: -16, polygonOffsetUnits: -32});
  const pulse = new THREE.Mesh(new THREE.PlaneGeometry(segLen - 0.16, AT.strip.w - 0.1), glowMat);   // the current phase breathes
  pulse.rotation.x = -Math.PI / 2; pulse.visible = false; pulse.renderOrder = 2; root.add(pulse);

  // the gate: a barrier across the strip where the next phase starts, shut (red and white, a red light) or raised (a green light); beside it a sign with why
  const gate = new THREE.Group(); gate.visible = false; root.add(gate);
  {
    const off = AT.strip.w / 2 + 0.2, post = V.mesh(new V.Vox().box(0, 0, 0, 1, 8, 1, '#e8edf0').box(0, 6, 0, 1, 7, 1, PAL.crash), {pivot: [1, 0, 1], scale: 0.1, jitter: 0.02});
    post.position.set(0, 0, -off); gate.add(post);                                                    // north post: the hinge
    const post2 = V.mesh(new V.Vox().box(0, 0, 0, 1, 8, 1, '#e8edf0').box(0, 6, 0, 1, 7, 1, PAL.crash), {pivot: [1, 0, 1], scale: 0.1, jitter: 0.02});
    post2.position.set(0, 0, off); gate.add(post2);                                                   // south post: the sign above it, readable from the plaza
    gate.arm = new THREE.Group(); gate.arm.position.set(0, 0.62, -off); gate.add(gate.arm);
    const L = Math.round(2 * off * 10), bar = V.mesh(new V.Vox().box(0, 0, 0, 1, 1, L, (x, y, z) => Math.floor(z / 3) % 2 ? '#f4f6f7' : PAL.crash), {pivot: [1, 1, 0], scale: 0.1, jitter: 0.01});
    gate.arm.add(bar);
    gate.lamp = V.mesh(new V.Vox().box(0, 0, 0, 1, 1, 1, '#ffffff'), {pivot: [1, 0, 1], scale: 0.1}, true);
    gate.lamp.position.set(0, 0.9, -off); gate.add(gate.lamp);
    gate.lampMat = gate.lamp.material.clone(); gate.lamp.material = gate.lampMat;                   // MAT.glow is shared: this lamp gets its own colour
  }
  const signAt = {x: 0, y: 1.5, z: AT.strip.z + AT.strip.w / 2 + 0.25, w: 2.0, h: 0.8, tilt: -0.3};
  function drawSign(p, d) {
    const {g, lw, lh} = p; if (!d) return;
    const open = d.gate.open, col = open ? PAL.keep : PAL.crash;
    g.fillStyle = PAL.ink; g.fillRect(0, 0, lw, lh); g.strokeStyle = col; g.lineWidth = 6; g.strokeRect(3, 3, lw - 6, lh - 6);
    g.textBaseline = 'middle'; g.fillStyle = col; g.font = `800 26px ${FONT}`;
    g.fillText(open ? I18N.text('office.research.gateOpen', {}, lang()) : I18N.text('office.research.gateShut', {}, lang()), 16, 28);
    g.fillStyle = PAL.white; g.font = `500 21px ${FONT}`;
    if (d.phase < 6) wrap(g, open ? I18N.text('office.research.gateNext', {}, lang()) : I18N.text('kernel._phase_next.' + d.gate.why, d.gate.args || {}, lang()), 16, 66, lw - 32, 26, 4);
  }
  const sign = panel('sign', signAt, 220, drawSign);
  sign.mesh.visible = sign.frame.visible = false;
  const tower = new THREE.Group(); tower.position.set(AT.tower.x, 0, AT.tower.z); root.add(tower);       // the stack light by the results wall
  {
    tower.add(V.mesh(new V.Vox().box(0, 0, 0, 3, 1, 3, '#6c7680').box(1, 2, 1, 2, 15, 2, '#aeb8c2'), {pivot: [2, 0, 2], scale: 0.1, jitter: 0.02}));
    tower.gpu = V.mesh(new V.Vox().box(0, 0, 0, 3, 2, 3, '#ffffff'), {pivot: [2, 0, 2], scale: 0.1}, true); tower.gpu.position.y = 1.0;
    tower.run = V.mesh(new V.Vox().box(0, 0, 0, 3, 2, 3, '#ffffff'), {pivot: [2, 0, 2], scale: 0.1}, true); tower.run.position.y = 1.3;
    for (const m of [tower.gpu, tower.run]) { m.material = m.material.clone(); tower.add(m); }
    tower.gpu.material.color.set('#3b2f1a'); tower.run.material.color.set('#16303a');
  }

  // ------------------------------------------------------------------ the ideas board and its bin
  const ideaRuns = (d, id) => d.attempts.filter(a => a.idea === id && a.kind === 'attempt' && a.state !== 'revoked');
  const refuted = (d, i) => i.status === 'rejected' || (i.status === 'tried' && ideaRuns(d, i.id).length > 0 && ideaRuns(d, i.id).every(a => a.status !== 'keep'));
  function drawIdeas(p, d) {
    const {g, lw, lh} = p;
    g.fillStyle = PAL.ink; g.fillRect(0, 0, lw, lh); g.strokeStyle = PAL.cyan; g.lineWidth = 3; g.strokeRect(2, 2, lw - 4, lh - 4);
    g.textBaseline = 'middle'; g.fillStyle = '#16303a'; g.fillRect(6, 6, lw - 12, 46);
    g.fillStyle = PAL.cyan; g.font = `800 28px ${FONT}`; g.fillText(I18N.text('office.research.ideas', {}, lang()), 20, 30);
    if (!d) return;
    const live = d.ideas.filter(i => !refuted(d, i)), bin = d.ideas.filter(i => refuted(d, i)), shown = live.slice(-6);
    g.fillStyle = PAL.steel; g.font = `500 18px ${FONT}`; g.textAlign = 'right';
    g.fillText(I18N.text('office.research.ideasCount', {n: d.ideas.length, m: bin.length}, lang()), lw - 18, 30); g.textAlign = 'left';
    shown.forEach((i, k) => {
      const cw = 264, ch = 118, x = 14 + (k % 2) * (cw + 14), y = 64 + Math.floor(k / 2) * (ch + 10), col = i.status === 'accepted' ? PAL.warn : PAL.cyan;
      g.fillStyle = '#e9f1f4'; g.beginPath(); g.roundRect(x, y, cw, ch, 8); g.fill();
      g.fillStyle = col; g.beginPath(); g.roundRect(x, y, cw, 9, [8, 8, 0, 0]); g.fill();
      g.fillStyle = PAL.ink; g.font = `800 20px ${FONT}`; g.fillText(fit(g, `${i.id} · ${i.by}`, cw - 20), x + 12, y + 28);
      g.font = `600 20px ${FONT}`; wrap(g, i.title, x + 12, y + 54, cw - 24, 24, 2);
      const n = ideaRuns(d, i.id).length;
      g.fillStyle = '#53656f'; g.font = `500 16px ${FONT}`;
      g.fillText(fit(g, `${I18N.text('office.research.ideaRuns', {n}, lang())} · ${I18N.text('office.research.idea.' + i.status, {}, lang())}`, cw - 20), x + 12, y + ch - 14);
    });
    if (live.length > shown.length) { g.fillStyle = PAL.steel; g.font = `600 18px ${FONT}`; g.fillText('+' + (live.length - shown.length), lw - 60, 66 + 3 * 128 - 14); }
    g.fillStyle = '#16303a'; g.fillRect(6, 456, lw - 12, 30);
    g.fillStyle = PAL.discard; g.font = `800 18px ${FONT}`; g.fillText(I18N.text('office.research.ideaTrash', {}, lang()), 18, 471);
    g.font = `500 18px ${FONT}`;
    bin.slice(-3).forEach((i, k) => { const y = 506 + k * 28, t = fit(g, `${i.id} ${i.title}`, lw - 70); g.fillStyle = PAL.crash; g.fillText('✕', 18, y); g.fillStyle = PAL.discard; g.fillText(t, 46, y);
      g.strokeStyle = PAL.discard; g.lineWidth = 2; g.beginPath(); g.moveTo(46, y); g.lineTo(46 + g.measureText(t).width, y); g.stroke(); });
    if (!bin.length) { g.fillStyle = '#44565f'; g.fillText(I18N.text('office.research.binEmpty', {}, lang()), 18, 520); }
  }
  panel('ideas', AT.ideas, 300, drawIdeas);
  const bin = new THREE.Group(); bin.position.set(AT.bin.x, 0, AT.bin.z); root.add(bin);
  {
    const v = new V.Vox().box(0, 0, 0, 5, 5, 5, '#6c7680');
    for (let x = 1; x <= 4; x++) for (let y = 1; y <= 5; y++) for (let z = 1; z <= 4; z++) v.del(x, y, z);
    bin.add(V.mesh(v, {pivot: [3, 0, 3], scale: 0.1, jitter: 0.02}));
  }
  let paper = null, paperN = -1;
  function setPaper(n) {                                                                    // one crumpled ball in the bin for each refuted idea (up to 8)
    n = Math.min(8, n); if (n === paperN) return; paperN = n;
    if (paper) { bin.remove(paper); paper.geometry.dispose(); paper = null; }
    if (!n) return;
    const v = new V.Vox();
    for (let i = 0; i < n; i++) { const x = 1 + (i % 3), z = 1 + Math.floor(i / 3) % 3, y = 1 + Math.floor(i / 6) + (i % 2); v.box(x, y, z, x, y, z, i % 2 ? '#f4f6f7' : '#dfe6ea'); }
    paper = V.mesh(v, {pivot: [3, 0, 3], scale: 0.1, jitter: 0.04}); paper.position.y = 0.1; paper.castShadow = false; bin.add(paper);
  }

  // ------------------------------------------------------------------ the verdicts wall: the auditor's stamps and the revocation chain
  const seen = new Map();                                                                  // verdict -> when it first showed (a new one is stamped in, once)
  let seenAll = false;                                                                     // the first drawing shows what was already there without stamping
  const OUT = {pass: PAL.keep, answer_ready: PAL.keep, fail: PAL.crash, search_more: PAL.warn};
  const SEC = {'Result': 'result', 'What changed': 'changed', 'Evidence': 'evidence', 'What did not work': 'failed', 'Limits': 'limits', 'Disclosure': 'disclosure'};
  function drawVerdicts(p, d) {
    const {g, lw, lh} = p;
    g.fillStyle = PAL.ink; g.fillRect(0, 0, lw, lh); g.strokeStyle = PAL.cyan; g.lineWidth = 3; g.strokeRect(2, 2, lw - 4, lh - 4);
    g.textBaseline = 'middle'; g.fillStyle = '#16303a'; g.fillRect(6, 6, lw - 12, 46);
    g.fillStyle = PAL.cyan; g.font = `800 28px ${FONT}`; g.fillText(I18N.text('office.research.verdicts', {}, lang()), 20, 30);
    if (!d) return;
    const last = new Map(); for (const v of d.verdicts) last.set(v.phase, v);                // the latest verdict of each phase
    const rows = [...last.values()].sort((a, b) => a.phase - b.phase).slice(-3), now = performance.now();
    p.animating = false;
    rows.forEach((v, k) => {
      const y = 58 + k * 58, id = `${v.phase}:${v.outcome}:${v.ts}`; if (!seen.has(id)) seen.set(id, seenAll ? now : -1e9);
      const age = (now - seen.get(id)) / 1000, e = age >= 0.5 ? 1 : 1 - Math.pow(1 - age / 0.5, 3);   // ease out: 1.8 times too big and faint, then home
      if (age < 0.5) p.animating = true;
      const phaseName = I18N.text('kernel.phase.' + PHASES[v.phase], {}, lang());
      g.fillStyle = PAL.steel; g.font = `700 18px ${FONT}`; g.fillText(fit(g, I18N.text('office.research.vPhase', {n: v.phase, name: phaseName}, lang()), 250), 18, y + 14);
      g.fillStyle = PAL.discard; g.font = `500 16px ${FONT}`; g.fillText(fit(g, (v.of ? `${num(v.score)}/${v.of} · ` : '') + v.by, 250), 18, y + 38);
      const col = OUT[v.outcome] || PAL.discard, label = I18N.text('office.research.out.' + v.outcome, {}, lang()).toUpperCase();
      g.save(); g.translate(430, y + 24); g.rotate(-0.06); const s = 1.8 - 0.8 * e; g.scale(s, s); g.globalAlpha = 0.25 + 0.75 * e;
      g.font = `800 24px ${FONT}`; const w = Math.min(250, g.measureText(label).width + 36);
      g.strokeStyle = col; g.lineWidth = 5; g.beginPath(); g.roundRect(-w / 2, -24, w, 48, 8); g.stroke(); g.fillStyle = col; g.textAlign = 'center'; g.fillText(label, 0, 2); g.textAlign = 'left';
      g.restore(); g.globalAlpha = 1;
      g.strokeStyle = '#1f333c'; g.lineWidth = 1; g.beginPath(); g.moveTo(14, y + 54); g.lineTo(lw - 14, y + 54); g.stroke();
    });
    if (!rows.length) { g.fillStyle = PAL.discard; g.font = `500 20px ${FONT}`; g.fillText(I18N.text('office.research.vNone', {}, lang()), 18, 90); }
    seenAll = true;
    // the report's gate: which sections are written
    g.fillStyle = '#16303a'; g.fillRect(6, 236, lw - 12, 30);
    g.fillStyle = PAL.cyan; g.font = `800 18px ${FONT}`; g.fillText(I18N.text('office.research.report', {}, lang()), 18, 251);
    if (!d.report.exists) { g.fillStyle = PAL.warn; g.font = `500 16px ${FONT}`; g.textAlign = 'right'; g.fillText(I18N.text('office.research.reportNone', {}, lang()), lw - 16, 251); g.textAlign = 'left'; }
    d.report.sections.forEach((s, i) => {
      const x = 18 + (i % 2) * 272, y = 292 + Math.floor(i / 2) * 32;
      g.strokeStyle = s.ok ? PAL.keep : PAL.discard; g.lineWidth = 3; g.strokeRect(x, y - 11, 22, 22);
      if (s.ok) { g.beginPath(); g.moveTo(x + 4, y); g.lineTo(x + 10, y + 7); g.lineTo(x + 19, y - 8); g.stroke(); }
      g.fillStyle = s.ok ? PAL.white : PAL.discard; g.font = `600 18px ${FONT}`; g.fillText(fit(g, I18N.text('office.research.sec.' + (SEC[s.name] || 'result'), {}, lang()), 224), x + 32, y);
    });
    // the chain: what was revoked, and what rested on it
    g.fillStyle = '#16303a'; g.fillRect(6, 372, lw - 12, 30);
    g.fillStyle = PAL.crash; g.font = `800 18px ${FONT}`; g.fillText(I18N.text('office.research.revs', {}, lang()), 18, 387);
    const gone = new Set(d.attempts.filter(a => a.state === 'revoked').map(a => a.n));
    const kids = n => [...d.attempts.filter(a => gone.has(a.n) && a.parent_n === n).flatMap(a => [`att-${a.n}`, ...kids(a.n)]), ...d.evidence.filter(e => e.state === 'revoked' && e.source.includes('att-' + n)).map(e => e.id)];
    const roots = d.attempts.filter(a => gone.has(a.n) && !gone.has(a.parent_n)).slice(0, 2);
    let yy = 426;
    g.font = `700 18px ${FONT}`;
    for (const r of roots) {
      let x = 18; const chain = [...new Set([`att-${r.n}`, ...kids(r.n)])].slice(0, 12);       // an evidence that rested on two of them shows once
      chain.forEach((label, i) => {
        const w = g.measureText(label).width + 20; if (x + w > lw - 14) { x = 18; yy += 38; }
        if (i) { g.strokeStyle = PAL.crash; g.lineWidth = 3; g.beginPath(); g.moveTo(x - 12, yy); g.lineTo(x, yy); g.stroke(); }   // a link of the chain
        g.fillStyle = i ? '#3a1d1d' : PAL.crash; g.strokeStyle = PAL.crash; g.lineWidth = 3; g.beginPath(); g.roundRect(x, yy - 15, w, 30, 15); g.fill(); g.stroke();
        g.fillStyle = PAL.white; g.fillText(label, x + 10, yy + 1); x += w + 14;
      });
      g.fillStyle = PAL.discard; g.font = `500 16px ${FONT}`; g.fillText(fit(g, r.revoked_why || r.desc, lw - 36), 18, yy + 30); g.font = `700 18px ${FONT}`; yy += 74;
    }
    if (!roots.length) { g.fillStyle = PAL.discard; g.font = `500 18px ${FONT}`; g.fillText(I18N.text('office.research.revNone', {}, lang()), 18, 426); }
  }
  panel('verdicts', AT.verdicts, 300, drawVerdicts);

  // ------------------------------------------------------------------ the end of the strip: the trophy of the final evaluation (its number on a plaque)
  const trophy = new THREE.Group(); trophy.position.set(AT.trophy.x, 0, AT.trophy.z); trophy.visible = true; root.add(trophy);
  {
    trophy.add(V.mesh(new V.Vox().box(0, 0, 0, 5, 7, 5, '#e8edf0').box(0, 7, 0, 5, 7, 5, '#aeb8c2'), {pivot: [3, 0, 3], scale: 0.1, jitter: 0.02}));           // the plinth, 0.8 m
    const cup = new V.Vox().box(1, 0, 1, 4, 0, 4, '#b8860b').box(2, 1, 2, 3, 3, 3, '#d4a017').box(1, 4, 1, 4, 4, 4, '#e8b923');     // base, stem, the cup widening to the rim
    cup.box(0, 5, 0, 5, 6, 5, '#ffca28').box(0, 7, 0, 5, 8, 5, '#ffd54f').box(1, 8, 1, 4, 8, 4, '#8d6e08');                      // the rim is hollow and dark inside
    cup.box(-1, 6, 2, -1, 7, 3, '#ffca28').box(-2, 7, 2, -2, 8, 3, '#ffca28').box(6, 6, 2, 6, 7, 3, '#ffca28').box(7, 7, 2, 7, 8, 3, '#ffca28');   // the handles
    trophy.cup = V.mesh(cup, {pivot: [3, 0, 3], scale: 0.1, jitter: 0.02}); trophy.cup.position.y = 0.85; trophy.add(trophy.cup);
  }
  function drawPlaque(p, d) {
    const {g, lw, lh} = p;
    g.fillStyle = '#3a2f0f'; g.fillRect(0, 0, lw, lh); g.strokeStyle = '#ffca28'; g.lineWidth = 4; g.strokeRect(3, 3, lw - 6, lh - 6);
    if (!d || !d.final || d.final.metric == null) return;
    g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillStyle = '#ffd54f'; g.font = `800 26px ${FONT}`;
    g.fillText(fit(g, `${d.tag} · ${num(d.final.metric)}`, lw - 20), lw / 2, lh / 2 + 1); g.textAlign = 'left';
  }
  const plaque = panel('plaque', {x: AT.trophy.x, y: 0.42, z: AT.trophy.z + 0.312, w: 0.5, h: 0.2}, 400, drawPlaque);

  // ------------------------------------------------------------------ the benches: on each worker's desk a light, a bar for the run's budget, smoke when a run crashed and tape when it is paused (no text: the detail shows when you point at the desk)
  const desks = new Map();                                                                  // agent name -> its desk (office.js attach/detach)
  const benches = new Map();                                                                // worker name -> {desk, light, track, fill, tape, smoke, hit, st, ver, sec}
  const benchHits = [];                                                                     // the invisible boxes a pointer can find
  const hazard = (() => {                                                                   // yellow and black tape: one picture for every bench
    const c = document.createElement('canvas'); c.width = 128; c.height = 16; const g = c.getContext('2d');
    g.fillStyle = '#ffd54f'; g.fillRect(0, 0, 128, 16); g.fillStyle = '#1a1a1a';
    for (let x = -16; x < 144; x += 32) { g.beginPath(); g.moveTo(x, 16); g.lineTo(x + 16, 16); g.lineTo(x + 32, 0); g.lineTo(x + 16, 0); g.closePath(); g.fill(); }
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.wrapS = THREE.RepeatWrapping; tex.repeat.set(5, 1); return tex;
  })();
  const tapeGeo = new THREE.PlaneGeometry(1.25, 0.14), tapeMat = new THREE.MeshBasicMaterial({map: hazard, side: THREE.DoubleSide, toneMapped: false});
  // on the top edge of the worker's monitor, flat and facing up (seen from above, away from the call-budget bar on the desk's front edge, office-viz.js)
  const lightGeo = new THREE.PlaneGeometry(0.9, 0.04), trackGeo = new THREE.PlaneGeometry(0.9, 0.03), fillGeo = new THREE.PlaneGeometry(0.9, 0.03).translate(0.45, 0, 0);
  const trackMat = new THREE.MeshBasicMaterial({color: '#27414c', toneMapped: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -2});
  const hitGeo = new THREE.BoxGeometry(1.3, 1.2, 1.1), hitMat = new THREE.MeshBasicMaterial();
  const puffGeo = new THREE.BoxGeometry(0.07, 0.07, 0.07), puffMat = new THREE.MeshBasicMaterial({color: '#9aa5ab', transparent: true, opacity: 0.5, depthWrite: false, toneMapped: false});
  const benchState = (d, name) => {
    const w = d.workers[name], run = d.pending && d.pending.worker === name ? d.pending : null;
    const mine = d.attempts.filter(a => a.worker === name && a.kind === 'attempt'), last = mine[mine.length - 1];
    const fresh = last && last.status === 'crash' && ((last.ts && (Date.now() / 1000 - skew - last.ts) < 120) || w.paused);       // a crash in the last two minutes smokes, and a paused worker keeps smoking until it is resumed
    return {w, run, paused: !!w.paused, crashed: !!fresh, crashes: w.crashes || 0};
  };
  function makeBench(name, desk) {
    const mat = () => new THREE.MeshBasicMaterial({color: PAL.run, toneMapped: false, transparent: true});
    const light = new THREE.Mesh(lightGeo, mat()), track = new THREE.Mesh(trackGeo, trackMat), fill = new THREE.Mesh(fillGeo, mat());
    light.rotation.x = track.rotation.x = fill.rotation.x = -Math.PI / 2;
    light.position.set(0, 1.492, -0.33); track.position.set(0, 1.488, -0.285); fill.position.set(-0.45, 1.49, -0.285);
    const tape = new THREE.Mesh(tapeGeo, tapeMat); tape.position.set(0, 0.95, 0.55); tape.visible = false;
    const hit = new THREE.Mesh(hitGeo, hitMat); hit.visible = false; hit.position.set(0, 0.85, 0.1); hit.userData.worker = name;       // raycast ignores `visible`: the box is found, never drawn
    desk.g.add(light, track, fill, tape, hit); benchHits.push(hit);
    const b = {name, desk, light, track, fill, tape, hit, smoke: null, st: null, ver: -1, sec: -1};
    benches.set(name, b); return b;
  }
  function dropBench(b) {
    b.desk.g.remove(b.light, b.track, b.fill, b.tape, b.hit); b.light.material.dispose(); b.fill.material.dispose();
    if (b.smoke) { b.desk.g.remove(b.smoke); b.smoke.dispose(); }
    benchHits.splice(benchHits.indexOf(b.hit), 1); benches.delete(b.name);
    if (hoverKind === 'bench' && hoverId === b.name) setHover('', null);
  }
  function syncBenches() {
    for (const b of [...benches.values()]) if (!data || !data.workers[b.name] || desks.get(b.name) !== b.desk) dropBench(b);        // a worker that left, or moved to another desk
    if (!data) return;
    for (const [name, desk] of desks) if (data.workers[name] && !benches.has(name)) makeBench(name, desk);
  }
  const _wp = new THREE.Vector3(), _m4 = new THREE.Matrix4(), _q = new THREE.Quaternion(), _v3 = new THREE.Vector3(), _s3 = new THREE.Vector3();
  function updateBenches(t) {
    const sec = Math.floor(Date.now() / 1000);
    for (const b of benches.values()) {
      if (b.ver !== ver || (sec !== b.sec && b.st && (b.st.run || b.st.crashed))) {                       // the state is read when the data changed, and once a second while a bar moves or smoke may end
        b.ver = ver; b.sec = sec; const st = b.st = benchState(data, b.name);
        const col = st.paused ? PAL.warn : st.crashed ? PAL.crash : st.run ? PAL.run : PAL.discard;
        b.light.material.color.set(col); b.fill.material.color.set(st.run && Date.now() / 1000 - skew - (st.run.child_ts || st.run.ts) > data.contract.budget_s ? PAL.warn : PAL.run);
        b.fill.visible = b.track.visible = !!st.run; b.tape.visible = st.paused;
        if (st.run) b.fill.scale.x = Math.max(0.001, Math.min(1, (Date.now() / 1000 - skew - (st.run.child_ts || st.run.ts)) / data.contract.budget_s));
        if (st.crashed && !b.smoke) { b.smoke = new THREE.InstancedMesh(puffGeo, puffMat, 9); b.smoke.frustumCulled = false; b.desk.g.add(b.smoke); }
        if (b.smoke) b.smoke.visible = st.crashed;
      }
      const st = b.st; if (!st) continue;
      b.light.material.opacity = st.run ? 0.55 + 0.45 * Math.sin(t * 5) : st.paused || st.crashed ? 1 : 0.35;
      if (b.smoke && st.crashed) {
        for (let i = 0; i < 9; i++) {
          const ph = (t * 0.45 + i / 9) % 1; _s3.setScalar(0.5 + ph * 1.6);
          _m4.compose(_v3.set(Math.sin(i * 2.1 + t) * 0.06 * ph, 0.85 + ph * 0.75, -0.25 + Math.cos(i * 1.7) * 0.05), _q, _s3); b.smoke.setMatrixAt(i, _m4);
        }
        b.smoke.instanceMatrix.needsUpdate = true;
      }
    }
    if (hoverKind === 'bench') tip.mesh.quaternion.copy(camera.quaternion);                                 // the detail faces whoever points
  }

  // ------------------------------------------------------------------ the data
  function feed(d) {
    const k = JSON.stringify(d, (kk, v) => kk === 'now' ? undefined : v);
    if (d && d.now) skew = Date.now() / 1000 - d.now;
    if (k === key) return; key = k; data = d && d.enabled ? d : null;
    for (const p of Object.values(panels)) p.dirty = true;
    ver++; refutedN = data ? data.ideas.filter(i => refuted(data, i)).length : 0; root.visible = !!data;
    syncBenches();
    if (hoverKind) { const k = hoverKind, id = hoverId; hoverKind = ''; hoverId = null; setHover(k, id); }
  }
  async function load() {
    if (busy || disposed || paused()) return; busy = true;
    try { const r = await fetch(url, {cache: 'no-store'}); if (r.ok) feed(await r.json()); } catch (e) { /* the viewer is away: the walls keep what they had */ }
    busy = false;
  }
  load(); const timer = setInterval(load, every);

  function update(t) {
    if (!data || paused()) return;
    if (drawnLang !== lang()) { drawnLang = lang(); for (const p of Object.values(panels)) p.dirty = true; }
    for (const p of Object.values(panels)) if (p.dirty) { redraw(p); break; }                  // one panel a frame: a 4 MB upload each is enough work
    const dt = Math.min(0.1, Math.max(0, t - lastT)); lastT = t;
    // the phases: the current one breathes, the gate's barrier eases open or shut, its sign says why, the lamps follow the GPU and the evaluator
    const cur = data.phase, atBoundary = cur < 6;
    pulse.visible = true; pulse.position.set(AT.strip.x0 + segLen * (cur + 0.5), 0.016, AT.strip.z); glowMat.opacity = 0.12 + 0.2 * (0.5 + 0.5 * Math.sin(t * 1.8));
    gate.visible = sign.mesh.visible = sign.frame.visible = atBoundary;
    if (atBoundary) {
      const gx = AT.strip.x0 + segLen * (cur + 1); gate.position.set(gx, 0, AT.strip.z); sign.mesh.position.x = sign.frame.position.x = gx;
      const target = data.gate.open ? -1.4 : 0; armAngle += (target - armAngle) * (1 - Math.exp(-dt * 3.5)); gate.arm.rotation.x = armAngle;
      gate.lampMat.color.set(data.gate.open ? PAL.keep : PAL.crash);
    }
    tower.gpu.material.color.set(data.lamps.gpu ? PAL.warn : '#3b2f1a');
    const busy = !!(data.lamps.lock && data.lamps.lock.alive);
    tower.run.material.color.set(busy ? PAL.run : '#16303a'); if (busy) tower.run.material.color.multiplyScalar(0.7 + 0.3 * Math.sin(t * 5));
    setPaper(refutedN);
    trophy.cup.visible = plaque.mesh.visible = plaque.frame.visible = !!(data.final && data.final.metric != null);
    if (panels.verdicts.animating) panels.verdicts.dirty = true;                       // a new stamp comes in over half a second
    updateBenches(t);
    const p = panels.results;
    if (p.next && !disposed) {
      toLocal(p, p.next.x, p.next.y, tmp); ring.position.set(p.at.x + tmp.x, p.at.y + tmp.y, p.at.z + 0.02);
      const s = 1 + 0.25 * Math.sin(t * 4.2); ring.scale.setScalar(s); ring.material.opacity = 0.55 + 0.35 * Math.sin(t * 4.2); ring.visible = true;
    } else ring.visible = false;
  }
  const api = {
    update, feed, data: () => data, panels, root, hover: setHover,
    /** an agent took a desk (office.js deskLayout), or left it: a worker's desk gets its bench */
    attach(name, desk) { desks.set(name, desk); syncBenches(); },
    detach(name) { desks.delete(name); syncBenches(); },
    dispose() {
      disposed = true; clearInterval(timer); dom.removeEventListener('pointermove', onMove);
      desks.clear(); data = null; syncBenches();
      for (const p of Object.values(panels)) { p.tex.dispose(); p.mesh.geometry.dispose(); p.mesh.material.dispose(); p.frame.geometry.dispose(); }
      tip.tex.dispose(); tip.mesh.geometry.dispose(); tip.mesh.material.dispose(); ring.geometry.dispose(); ring.material.dispose();
      scene.remove(root);
    },
  };
  root.traverse(o => { if (o.isMesh) o.castShadow = false; });                                  // small pieces and flat screens: their shadows cost the shadow pass and show nothing
  if (FORCE) window.__officeResearch = Object.assign(api, {camera, benches, AT});
  return api;
}
