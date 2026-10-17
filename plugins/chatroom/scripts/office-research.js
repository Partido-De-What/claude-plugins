// The research in the laboratory: what a research room knows (research.json: the contract, the phases, every run, the ideas, the evidence, the auditor's
// verdicts, the lamps) drawn on the lab's walls and floor. office.js loads this file only for research rooms, next to office-lab.js, and calls
// createResearch(ctx) once; the data is asked every 2.5 s while the office is seen (read only: nothing here writes to the room), and a panel is drawn
// again only when its own data changed (a canvas texture is uploaded only then). No imports: three.js, the voxel helpers and the lab's palette come in ctx.
//
// What office.js uses: CLEAR (wall spans the lab's furniture must keep free), createResearch(ctx) -> {update, attach, detach, feed, dispose, ...}.

/** wall spans the research panels use (x0..x1 along the north wall, z0..z1 from it): the laboratory's own pieces stay out of them */
export const CLEAR = [
  {name: 'results', x0: 4.4, x1: 8.95, z0: -10, z1: -8.7},
  {name: 'ideas', x0: -8.9, x1: -2.7, z0: -10, z1: -8.7},
];
/** where the panels stand: x, y (centre), z (in front of the wall's face, 12.5 cm in), size in metres */
export const AT = {
  results: {x: 6.675, y: 1.8, z: -9.845, w: 4.5, h: 2.2},
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
  const root = new THREE.Group(); root.name = 'research'; scene.add(root);
  const raycaster = new THREE.Raycaster(), ndc = new THREE.Vector2(), tmp = new THREE.Vector3();
  const aniso = renderer.capabilities.getMaxAnisotropy();
  let data = null, key = '', skew = 0, drawnLang = '', hoverN = null, busy = false, disposed = false;
  const panels = {};

  // ------------------------------------------------------------------ panels
  /** a flat screen of w x h metres drawn in a canvas of ppm pixels a metre (twice that in device pixels), with a steel frame behind it */
  function panel(name, at, ppm, draw) {
    const lw = Math.round(at.w * ppm), lh = Math.round(at.h * ppm), c = document.createElement('canvas');
    c.width = lw * SS; c.height = lh * SS;
    const g = c.getContext('2d'); g.scale(SS, SS);
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = aniso;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(at.w, at.h), new THREE.MeshBasicMaterial({map: tex, toneMapped: false}));
    mesh.position.set(at.x, at.y, at.z); mesh.rotation.y = at.rot || 0; root.add(mesh);
    const nx = Math.round(at.w * 10) + 2, ny = Math.round(at.h * 10) + 2;             // the frame: a steel slab 10 cm deeper than the screen on every side
    const frame = V.mesh(new V.Vox().box(0, 0, 0, nx - 1, ny - 1, 0, PAL.resin), {pivot: [nx / 2, ny / 2, 1], scale: 0.1, jitter: 0.02});
    frame.position.copy(mesh.position); frame.rotation.y = mesh.rotation.y; frame.translateZ(-0.02); root.add(frame);
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
    g.fillStyle = PAL.white; g.font = `600 22px ${FONT}`;
    const head = `${c.metric} (${c.direction === 'max' ? I18N.text('office.research.higher', {}, lang()) : I18N.text('office.research.lower', {}, lang())}) · ${I18N.text('office.research.best', {}, lang())} ${d.best ? num(d.best.metric) : '—'} · ${I18N.text('office.research.baseline', {}, lang())} ${d.baseline ? num(d.baseline.metric) : '—'} · ${d.evals}/${c.max_evals}`;
    g.fillText(fit(g, head, lw - 330), 232, 30);
    // the chart
    const L = 74, R = 770, Tp = 78, B = 398, plotH = B - Tp, N = Math.max(4, ...runs.map(a => a.n), d.pending ? d.pending.n : 0);
    let lo = Math.min(...(vals.length ? vals : [0])), hi = Math.max(...(vals.length ? vals : [1]));
    if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }
    const padv = (hi - lo) * 0.08; lo -= padv; hi += padv;
    const x = n => L + (n - 0.5) / N * (R - L), y = v => Tp + (up ? hi - v : v - lo) / (hi - lo) * plotH;
    g.font = `500 18px ${FONT}`; g.textAlign = 'right';
    for (const v of ticks(lo, hi)) { g.strokeStyle = '#27414c'; g.lineWidth = 1; g.beginPath(); g.moveTo(L, y(v)); g.lineTo(R, y(v)); g.stroke(); g.fillStyle = PAL.steel; g.fillText(num(v), L - 8, y(v)); }
    g.textAlign = 'center'; const step = Math.max(1, Math.ceil(N / 12));
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
    for (const e of env.slice(0, 5)) {
      const isT = /temp/i.test(e.k), isC = /clock|mhz|freq/i.test(e.k), frac = isT ? Math.max(0, Math.min(1, (e.v - 30) / 65)) : isC && clockMax ? Math.min(1, e.v / clockMax) : null;
      g.fillStyle = PAL.steel; g.font = `500 18px ${FONT}`; g.fillText(fit(g, `${e.k}`, W0 - 110), X0, yy);
      g.fillStyle = PAL.white; g.font = `700 20px ${FONT}`; g.textAlign = 'right'; g.fillText(`${num(e.v)}${e.u ? ' ' + e.u : ''}`, X0 + W0, yy); g.textAlign = 'left';
      if (frac !== null) { const hot = isT ? (e.v >= 85 ? PAL.crash : e.v >= 75 ? PAL.warn : PAL.keep) : (frac < 0.85 ? PAL.crash : frac < 0.95 ? PAL.warn : PAL.keep);
        g.fillStyle = '#27414c'; g.fillRect(X0, yy + 11, W0, 7); g.fillStyle = hot; g.fillRect(X0, yy + 11, W0 * frac, 7); yy += 38; } else yy += 28;
    }
    if (!env.length) { g.fillStyle = PAL.discard; g.font = `500 18px ${FONT}`; wrap(g, I18N.text('office.research.noEnv', {}, lang()), X0, 272, W0, 22, 3); }
    // the foot: contract changes after the baseline
    g.fillStyle = '#16303a'; g.fillRect(6, lh - 62, lw - 12, 56);
    g.fillStyle = PAL.amber; g.font = `800 20px ${FONT}`; g.fillText(I18N.text('office.research.amends', {}, lang()), 20, lh - 44);
    g.fillStyle = PAL.white; g.font = `500 18px ${FONT}`;
    const last = d.amends[d.amends.length - 1];
    g.fillText(fit(g, last ? I18N.text('office.research.amendLine', {n: last.after_run, by: last.by, what: last.what, reason: last.reason}, lang()) : I18N.text('office.research.amendNone', {}, lang()), lw - 40), 20, lh - 20);
  }
  panel('results', AT.results, 240, drawResults);

  // ------------------------------------------------------------------ the detail of a run, under the pointer
  const tip = {c: document.createElement('canvas'), n: null};
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
  function setHover(n) {
    if (n === hoverN) return; hoverN = n;
    const p = panels.results, a = n != null && data ? data.attempts.find(x => x.n === n) : null, at = a && p.pointAt && p.pointAt[n];
    if (!a || !at) { tip.mesh.visible = false; return; }
    drawTip(a);
    toLocal(p, at.x, at.y, tmp);                                                    // above the point, inside the wall's screen
    const hx = Math.max(-p.at.w / 2 + 0.85, Math.min(p.at.w / 2 - 0.85, tmp.x)), hy = Math.max(-p.at.h / 2 + 0.4, Math.min(p.at.h / 2 - 0.45, tmp.y + 0.45));
    tip.mesh.position.set(p.at.x + hx, p.at.y + hy, p.at.z + 0.03); tip.mesh.visible = true;
  }
  let moveAt = 0, lastCenter = 0;
  function pick(ev) {
    const p = panels.results; if (!p || !data || paused()) return;
    if (pov()) ndc.set(0, 0); else { const r = dom.getBoundingClientRect(); ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1); }
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObject(p.mesh, false)[0];
    if (!hit || !hit.uv) return setHover(null);
    const px = hit.uv.x * p.lw, py = (1 - hit.uv.y) * p.lh;
    let near = null, dist = 26;                                                       // within 26 canvas pixels of a point
    for (const h of p.hit) { const dd = Math.hypot(h.x - px, h.y - py); if (dd < dist) { dist = dd; near = h.n; } }
    setHover(near);
  }
  const onMove = ev => { const now = performance.now(); if (now - moveAt < 40) return; moveAt = now; pick(ev); };
  dom.addEventListener('pointermove', onMove, {passive: true});

  // ------------------------------------------------------------------ the marker of the run in progress (a ring on the wall, pulsing)
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.05, 0.07, 32), new THREE.MeshBasicMaterial({color: PAL.run, transparent: true, toneMapped: false, depthWrite: false}));
  ring.visible = false; ring.renderOrder = 4; root.add(ring);

  // ------------------------------------------------------------------ the data
  function feed(d) {
    const k = JSON.stringify(d, (kk, v) => kk === 'now' ? undefined : v);
    if (d && d.now) skew = Date.now() / 1000 - d.now;
    if (k === key) return; key = k; data = d && d.enabled ? d : null;
    for (const p of Object.values(panels)) p.dirty = true;
    if (hoverN != null) { const n = hoverN; hoverN = null; setHover(n); }
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
    const p = panels.results;
    if (p.next && !disposed) {
      toLocal(p, p.next.x, p.next.y, tmp); ring.position.set(p.at.x + tmp.x, p.at.y + tmp.y, p.at.z + 0.02);
      const s = 1 + 0.25 * Math.sin(t * 4.2); ring.scale.setScalar(s); ring.material.opacity = 0.55 + 0.35 * Math.sin(t * 4.2); ring.visible = true;
    } else ring.visible = false;
  }
  const api = {
    update, feed, data: () => data, panels, root, hover: setHover,
    attach() {}, detach() {},
    dispose() {
      disposed = true; clearInterval(timer); dom.removeEventListener('pointermove', onMove);
      for (const p of Object.values(panels)) { p.tex.dispose(); p.mesh.geometry.dispose(); p.mesh.material.dispose(); p.frame.geometry.dispose(); }
      tip.tex.dispose(); tip.mesh.geometry.dispose(); tip.mesh.material.dispose(); ring.geometry.dispose(); ring.material.dispose();
      scene.remove(root);
    },
  };
  if (FORCE) window.__officeResearch = api;
  return api;
}
