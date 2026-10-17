// What the chat room knows and the office did not show, made visible in the normal office (a research room has its own, office-research.js):
// the CHECK panel on the north wall, a line between who tags and who is tagged, the "everyone is idle" lamp on the command table, a bar
// for the call budget on each desk, parcels that travel when a piece of a task is lent, the language flag by the control room sign, and
// two flags over a head ("!!! #N": it posted without reading a message for it; 💡: it shared a finding).
// The rules (how serious a check is, who waits for whom, which colour a budget has) are plain functions at the top: tools/test_office_fase1.mjs
// runs them. office.js installs the rest with createViz() and calls refresh() when the chat or the board changed and update() once a frame.

export const COL = {ok: '#43a047', err: '#e53935', warn: '#ffb74d', run: '#4dd0e1', off: '#90a4ae'};

// ------------------------------------------------------------------ the rules
const ERR = new Set(['noproof', 'noartifact', 'flip', 'claim', 'consensus', 'stall', 'loop']);          // keys of failures() in chat.py
const INFO = new Set(['allidle', 'checkpoint']);
const SEV_ORDER = {err: 0, warn: 1, info: 2};
/** 'err', 'warn' or 'info' for the key of a CHECK ("noproof:T3", "tag:12:BETA") */
export const sevOf = key => { const k = String(key).split(':')[0]; return ERR.has(k) ? 'err' : INFO.has(k) ? 'info' : 'warn'; };
/** the message a CHECK is about: the first #n of its text, else the number in its key; null when it is about no message */
export function refOf({key, text}) {
  const m = /#(\d+)/.exec(text || '');
  if (m) return +m[1];
  const p = String(key).split(':'), last = +p[p.length - 1];
  if (p[0] === 'tag' || p[0] === 'consensus') return +p[1] || null;
  return (p[0] === 'claim' || p[0] === 'flip' || p[0] === 'loop') && last ? last : null;
}
/** the checks of /check.json, the serious first (the order the server gave is kept inside a kind), each with sev and ref */
export const sortChecks = list => (list || []).map((c, i) => ({...c, sev: sevOf(c.key), ref: refOf(c), i}))
  .sort((a, b) => SEV_ORDER[a.sev] - SEV_ORDER[b.sev] || a.i - b.i);
/** green under 60% of the budget, amber up to it, red from it; grey when there is no limit */
export const budgetColor = (used, budget) => !budget ? COL.off : used >= budget ? COL.err : used >= budget * 0.6 ? COL.warn : COL.ok;

const AT = /(^|[^\w@])@([\w-]+)/g;
/** who tagged whom in the last `window` seconds: [{from, to, n, answeredTs}] — answeredTs 0 while the tagged one has said nothing since (a message, a
 *  status or a board line; a break does not answer). Only the unanswered ones (the newest `max`) and those answered less than `fade` seconds ago stay.
 *  `who`: Map of lower-case name -> name for the figures that can be tagged. */
export function tagLinks(all, who, now, {window = 600, max = 8, fade = 25} = {}) {
  const recent = [];
  for (let i = all.length - 1; i >= 0 && recent.length < 80; i--) { if (now - (all[i].ts || now) > window) break; recent.push(all[i]); }
  recent.reverse();
  const links = [];
  recent.forEach((m, i) => {
    if (m.kind && m.kind !== 'status') return;
    const seen = new Set();
    for (const g of String(m.text || '').matchAll(AT)) {
      const to = who.get(g[2].toLowerCase());
      if (!to || to === m.from || seen.has(to)) continue;
      seen.add(to);
      const ans = recent.slice(i + 1).find(x => x.from === to && x.kind !== 'idle');
      links.push({from: m.from, to, n: m.n, answeredTs: ans ? (ans.ts || now) : 0});
    }
  });
  const open = links.filter(l => !l.answeredTs).slice(-max), done = links.filter(l => l.answeredTs && now - l.answeredTs < fade).slice(-max);
  return [...open, ...done].slice(-max);
}
/** the pieces lent and not yet given back: [{id, from, to, accepted}] (the board's tasks: `lender` is who lent, `owner` who works on it) */
export const loans = tasks => (tasks || []).filter(t => t.lender && t.state === 'taken' && t.owner && t.owner !== t.lender)
  .map(t => ({id: t.id, from: t.lender, to: t.owner, accepted: t.accepted !== false}));
/** every agent of this room is on a break (and there is at least one) */
export const allIdle = (names, per) => names.length > 0 && names.every(n => per[n]?.idle);
/** the flags a head shows from its last message: it posted without reading a message for it ("!!! #12 +2"), or shared a finding less than a minute ago */
export function flagsOf(last, now) {
  const out = [];
  if (!last) return out;
  const age = now - (last.ts || now);
  if (last.missed?.length && age < 180) out.push(['miss', `!!! #${last.missed[0]}` + (last.missed.length > 1 ? ` +${last.missed.length - 1}` : '')]);
  if (last.kind === 'finding' && age < 60) out.push(['find', '💡']);
  return out;
}

// ------------------------------------------------------------------ the pictures
const PANEL = {w: 1024, h: 704, head: 92, row: 84, rows: 7};
function wrap(g, text, maxW, maxLines) {
  const words = String(text).replace(/\s+/g, ' ').trim().split(' '), lines = [];
  let line = '';
  for (const w of words) {
    const t = line ? line + ' ' + w : w;
    if (g.measureText(t).width <= maxW || !line) line = t; else { lines.push(line); line = w; }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    lines.length = maxLines;
    let last = lines[maxLines - 1];
    while (last.length > 1 && g.measureText(last + '…').width > maxW) last = last.slice(0, -1);
    lines[maxLines - 1] = last + '…';
  }
  return lines;
}
function drawFlag(lg) {
  const c = document.createElement('canvas'); c.width = 192; c.height = 128; const g = c.getContext('2d');
  if (lg === 'it') {
    g.fillStyle = '#009246'; g.fillRect(0, 0, 64, 128); g.fillStyle = '#f4f5f0'; g.fillRect(64, 0, 64, 128); g.fillStyle = '#ce2b37'; g.fillRect(128, 0, 64, 128);
  } else {
    g.fillStyle = '#012169'; g.fillRect(0, 0, 192, 128);
    g.strokeStyle = '#fff'; g.lineWidth = 26; g.beginPath(); g.moveTo(0, 0); g.lineTo(192, 128); g.moveTo(192, 0); g.lineTo(0, 128); g.stroke();
    g.strokeStyle = '#c8102e'; g.lineWidth = 9; g.beginPath(); g.moveTo(0, 0); g.lineTo(192, 128); g.moveTo(192, 0); g.lineTo(0, 128); g.stroke();
    g.fillStyle = '#fff'; g.fillRect(0, 46, 192, 36); g.fillRect(78, 0, 36, 128);
    g.fillStyle = '#c8102e'; g.fillRect(0, 54, 192, 20); g.fillRect(86, 0, 20, 128);
  }
  g.strokeStyle = '#0006'; g.lineWidth = 4; g.strokeRect(2, 2, 188, 124);
  return c;
}

/** The panel's picture. checks: sortChecks() of the last /check.json, or null before the first answer. texts: {title, ok, more(n)} in the room's language. */
export function drawCheckPanel(c, checks, texts) {
  const g = c.getContext('2d'), {w, h, head, row, rows} = PANEL;
  g.fillStyle = '#0f1218'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#171c26'; g.fillRect(0, 0, w, head - 8);
  g.fillStyle = COL.run; g.fillRect(0, head - 12, w, 4);
  g.textBaseline = 'middle'; g.textAlign = 'left'; g.font = '800 44px "Segoe UI", sans-serif'; g.fillStyle = '#e8eaf0'; g.fillText(texts.title, 34, 40);
  if (!checks) return;
  const worst = checks[0]?.sev, n = checks.length;
  g.beginPath(); g.arc(w - 64, 40, 28, 0, 7); g.fillStyle = n ? (worst === 'err' ? COL.err : worst === 'warn' ? COL.warn : COL.off) : COL.ok; g.fill();
  g.textAlign = 'center'; g.font = '800 32px "Segoe UI", sans-serif'; g.fillStyle = n && worst === 'warn' ? '#222' : '#fff'; g.fillText(n ? String(n) : '✓', w - 64, 42);
  g.textAlign = 'left';
  if (!n) { g.font = '600 34px "Segoe UI", sans-serif'; g.fillStyle = COL.ok; g.fillText(texts.ok, 60, head + 70); return; }
  const shown = n > rows ? rows - 1 : n;
  g.font = '600 26px "Segoe UI", sans-serif';
  for (let i = 0; i < shown; i++) {
    const y = head + i * row, k = checks[i];
    g.fillStyle = k.sev === 'err' ? COL.err : k.sev === 'warn' ? COL.warn : COL.off; g.beginPath(); g.arc(34, y + row / 2, 11, 0, 7); g.fill();
    g.fillStyle = '#e8eaf0';
    const lines = wrap(g, k.text, w - 100, 2), y0 = y + row / 2 - (lines.length - 1) * 15;
    lines.forEach((l, j) => g.fillText(l, 62, y0 + j * 30));
    g.fillStyle = '#ffffff14'; g.fillRect(24, y + row - 2, w - 48, 2);
  }
  if (n > shown) { g.fillStyle = COL.off; g.font = '700 28px "Segoe UI", sans-serif'; g.fillText(texts.more(n - shown), 34, head + shown * row + 40); }
}

// ------------------------------------------------------------------ the office
/**
 * THREE, scene, V (office-voxel.js), raycastables: as in office.js.
 * data(): {all, who (Map lower-case name -> name), names (this room's agents), per, tasks, desks: [{name, g}], where(name) -> Vector3|null}.
 * lang(): 'it' or 'en'; jump(n): open message n; setLang(lg): change the room's language; say(text): a line on the screen;
 * active(): the office is on screen; check, lamp, flag: where the panel, the lamp and the flag go ({x, y, z}).
 */
export function createViz({THREE, scene, V, raycastables, data, lang, jump, setLang, say, active, check, lamp, flag}) {
  const group = new THREE.Group(); group.name = 'viz'; scene.add(group);
  const basic = (color, extra = {}) => new THREE.MeshBasicMaterial({color, toneMapped: false, ...extra});
  const tex = c => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; };
  const texts = lg => ({title: I18N.text('office.viz.check.title', {}, lg), ok: I18N.text('office.viz.check.ok', {}, lg), more: n => I18N.text('office.viz.check.more', {n}, lg)});

  // --- the CHECK panel
  const PW = 1.6, PH = PW * PANEL.h / PANEL.w;
  const panelCanvas = document.createElement('canvas'); panelCanvas.width = PANEL.w; panelCanvas.height = PANEL.h;
  const panelTex = tex(panelCanvas);
  const panel = new THREE.Mesh(new THREE.PlaneGeometry(PW, PH), basic('#ffffff', {map: panelTex}));
  panel.position.set(check.x, check.y, check.z + 0.03); panel.userData.viz = {kind: 'check'}; group.add(panel); raycastables.push(panel);
  const body = V.mesh(new V.Vox().box(0, 0, 0, Math.round(PW * 20) + 1, Math.round(PH * 20) + 1, 0, '#14161f'), {pivot: [PW * 10 + 1, PH * 10 + 1, 0.5], scale: 0.05, jitter: 0.02});
  body.position.set(check.x, check.y, check.z); group.add(body);
  let checks = null, checkSig = '', shown = [];
  function drawPanel(force) {
    const lg = lang() === 'it' ? 'it' : 'en', sig = lg + JSON.stringify(checks && checks.map(c => c.key + c.text));
    if (sig === checkSig && !force) return;
    checkSig = sig; shown = checks ? checks.slice(0, checks.length > PANEL.rows ? PANEL.rows - 1 : PANEL.rows) : [];
    drawCheckPanel(panelCanvas, checks, texts(lg)); panelTex.needsUpdate = true;
  }
  let calls = {}, inflight = false, timer = 0;
  async function poll() {
    if (inflight || !active()) return;
    inflight = true;
    try {
      const r = await fetch('check.json', {cache: 'no-store'});
      if (r.ok) { const j = await r.json(); checks = sortChecks(j.checks); calls = j.calls || {}; drawPanel(); budgetDirty = true; }
      else if (r.status === 404) clearInterval(timer);           // an older server has no /check.json: the panel stays empty, and nobody asks again
    } catch (e) { /* the server is busy: the next round */ }
    inflight = false;
  }
  timer = setInterval(poll, 3000);

  // --- the call-budget bars: one instanced mesh, two bars (the track and the fill) for each desk that has an agent
  const BAR = {w: 1.1, y: 0.715, z: 0.37, h: 0.012, d: 0.03};
  const bars = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), basic('#ffffff'), 96);
  bars.frustumCulled = false; bars.count = 0; bars.userData.noShot = true; group.add(bars);
  const _m = new THREE.Matrix4(), _p = new THREE.Vector3(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _c = new THREE.Color();
  bars.setColorAt(0, _c.set('#2a2f3a'));                    // the colour buffer exists from the start: made later, it would change the shader in the middle of a frame
  let budgetDirty = true, deskSig = '';
  function drawBars(desks) {
    let i = 0;
    for (const d of desks) {
      const u = calls[d.name]; if (!u || !d.g) continue;
      if (i + 2 > 96) break;
      d.g.updateMatrixWorld();
      const r = u.budget ? Math.min(1, u.used / u.budget) : 0;
      _m.compose(_p.set(0, BAR.y, BAR.z), _q.identity(), _s.set(BAR.w, BAR.h, BAR.d)).premultiply(d.g.matrixWorld); bars.setMatrixAt(i, _m); bars.setColorAt(i++, _c.set('#2a2f3a'));
      const fw = Math.max(0.02, BAR.w * r);
      _m.compose(_p.set(-BAR.w / 2 + fw / 2, BAR.y + 0.004, BAR.z), _q.identity(), _s.set(fw, BAR.h, BAR.d)).premultiply(d.g.matrixWorld); bars.setMatrixAt(i, _m); bars.setColorAt(i++, _c.set(budgetColor(u.used, u.budget)));
    }
    bars.count = i; bars.instanceMatrix.needsUpdate = true; if (bars.instanceColor) bars.instanceColor.needsUpdate = true; bars.visible = i > 0;
  }

  // --- tag links: a line from who tags to who is tagged (amber while open, green for a while once answered)
  const SLOTS = 8, linkMat = {open: basic(COL.warn), done: basic(COL.ok)};
  const ribbons = Array.from({length: SLOTS}, () => { const m = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), linkMat.open); m.visible = false; m.frustumCulled = false; m.userData.noShot = true; group.add(m); return m; });
  let links = [];
  const X = new THREE.Vector3(1, 0, 0), _a = new THREE.Vector3(), _b = new THREE.Vector3();

  // --- the lamp: every agent on a break
  const lampMat = basic('#4a4f5a');
  const lampMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.08, 0.12, 12), lampMat);
  lampMesh.position.set(lamp.x, lamp.y + 0.06, lamp.z); lampMesh.userData.noShot = true; group.add(lampMesh);
  let lampOn = false;

  // --- parcels: a piece of a task lent travels from who lent it to who works on it (amber until accepted, then green)
  const PARCELS = 4, parcelMat = {open: basic(COL.warn), ok: basic(COL.ok)};
  const parcels = Array.from({length: PARCELS}, () => { const m = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.14, 0.2), parcelMat.open); m.visible = false; m.frustumCulled = false; m.userData.noShot = true; group.add(m); return m; });
  let lent = [];

  // --- the language flag, hung by the control room sign: a click changes the room's language
  const flagTex = {it: tex(drawFlag('it')), en: tex(drawFlag('en'))};
  const flagMat = basic('#ffffff', {map: flagTex.en, side: THREE.DoubleSide});
  const flagMesh = new THREE.Mesh(new THREE.PlaneGeometry(0.36, 0.24), flagMat);
  flagMesh.position.set(flag.x, flag.y, flag.z); flagMesh.userData.viz = {kind: 'lang'}; group.add(flagMesh); raycastables.push(flagMesh);
  const rod = new THREE.Mesh(new THREE.BoxGeometry(0.02, 3.0 - flag.y - 0.12, 0.02), basic('#8a929e')); rod.position.set(flag.x, (3.0 + flag.y + 0.12) / 2, flag.z); group.add(rod);
  let flagLang = '';
  const NAMES = {it: 'Italiano', en: 'English'};

  // --- what the heads show
  let heads = new Map(), lastAll = null, lastTasks = null, lastAt = 0;
  /** the chat or the board may have changed: work out again what depends on them (cheap; the ages of things are read again every two seconds) */
  function refresh() {
    const d = data(), now = Date.now() / 1000;
    if (d.all === lastAll && d.tasks === lastTasks && now - lastAt < 2) return;
    lastAll = d.all; lastTasks = d.tasks; lastAt = now;
    links = tagLinks(d.all, d.who, now);
    lent = loans(d.tasks).slice(0, PARCELS);
    heads = new Map();
    const lastBy = new Map();
    for (const m of d.all) lastBy.set(m.from, m);
    for (const [name, m] of lastBy) { const f = flagsOf(m, now); if (f.length) heads.set(name, f); }
    const on = allIdle(d.names, d.per);
    if (on !== lampOn) { lampOn = on; if (!on) lampMat.color.set('#4a4f5a'); }
    const sig = d.desks.map(x => x.name + (x.g ? x.g.id : '')).join();
    if (sig !== deskSig) { deskSig = sig; budgetDirty = true; }
    if (budgetDirty) { budgetDirty = false; drawBars(d.desks); }
    drawPanel();
  }
  const flagsFor = name => heads.get(name) || [];

  // --- once a frame (nothing allocated here)
  function update(dt, t) {
    const lg = lang() === 'it' ? 'it' : 'en';
    if (lg !== flagLang) { flagLang = lg; flagMat.map = flagTex[lg]; flagMat.needsUpdate = true; drawPanel(true); }
    if (lampOn) { const k = 0.65 + 0.35 * Math.sin(t * 2); lampMat.color.setRGB(1 * k, 0.72 * k, 0.28 * k); }
    const d = data(), now = Date.now() / 1000;
    for (let i = 0; i < SLOTS; i++) {
      const l = links[i], m = ribbons[i];
      const from = l && d.where(l.from), to = l && d.where(l.to);
      if (!l || !from || !to) { m.visible = false; continue; }
      _a.copy(from); _b.copy(to); _a.y = _b.y = 1.35;
      const len = _a.distanceTo(_b); if (len < 0.1) { m.visible = false; continue; }
      const k = l.answeredTs ? Math.max(0.15, 1 - (now - l.answeredTs) / 25) : 0.8 + 0.4 * Math.sin(t * 4 + i);
      m.material = l.answeredTs ? linkMat.done : linkMat.open;
      m.position.addVectors(_a, _b).multiplyScalar(0.5); m.scale.set(len, 0.03 * k, 0.03 * k);
      m.quaternion.setFromUnitVectors(X, _b.sub(_a).normalize()); m.visible = true;
    }
    for (let i = 0; i < PARCELS; i++) {
      const p = lent[i], m = parcels[i];
      const from = p && d.where(p.from), to = p && d.where(p.to);
      if (!p || !from || !to) { m.visible = false; continue; }
      const u = ((t * 0.22 + i * 0.37) % 1), e = u * u * (3 - 2 * u);                  // from the lender to the helper, slowly, easing at both ends
      m.position.lerpVectors(from, to, e); m.position.y = 1.1 + 0.5 * Math.sin(Math.PI * e);
      m.rotation.y = t + i; m.material = p.accepted ? parcelMat.ok : parcelMat.open; m.visible = true;
    }
  }

  /** a click on a piece of the panel or on the flag */
  function click(ud, hit) {
    if (ud.kind === 'lang') { const next = lang() === 'it' ? 'en' : 'it'; setLang(next); say(I18N.text('office.viz.lang.set', {lang: NAMES[next]}, next)); return; }
    if (ud.kind === 'check' && hit?.uv) {
      const row = Math.floor(((1 - hit.uv.y) * PANEL.h - PANEL.head) / PANEL.row), k = shown[row];
      if (k?.ref) jump(k.ref);
    }
  }
  poll();
  return {refresh, update, click, flagsFor, poll, group};
}
