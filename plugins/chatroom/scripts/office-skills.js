// The skills bookcase of the office: one spine per skill (the colour says where it comes from, a spine pulled out says an agent has it), a click opens the
// panel (explore, which agent has what, search, add) and every agent carries the number of skills it has. It is the 3D twin of the skills panel of the chat: the
// same data (GET skills.json) and the same actions (POST skills/do), nothing is decided here. Nothing is installed from here either: an add shows what and from
// where, and waits for the confirmation of the user.

// the texts are in locales/<lang>.json (skills.office.*)
const S = I18N.tables('skills.office', {count: ['n'], agentsN: ['n'], asked: ['to'], needSearcher: ['name'], advisedTo: ['to'], searcherBusy: ['name'], searcherIs: ['name'], tempDone: ['name'], forThem: ['who'], fromPlugin: ['name'], fromRepo: ['name'], upInfo: ['a', 'b'], upDone: ['v'], deriveTitle: ['name'], deriveWaiting: ['name'], useLine: ['n', 'rooms'], useOkFail: ['ok', 'fail'], useUnused: ['n'], levelUnder: ['name']});
const CSS = `
#office .o-sk-ov { position: absolute; inset: 0; z-index: 8; display: flex; justify-content: flex-end; align-items: stretch; background: linear-gradient(90deg, #05070f00 0%, #05070f55 55%, #05070fb0 100%); animation: oSkFade .28s ease-out both; }
#office .o-sk { width: min(100%, 760px); height: 100%; overflow: auto; box-sizing: border-box; padding: 16px 18px 22px; color: #e8ecff; font: 14px/1.4 "Segoe UI", system-ui, sans-serif; background: linear-gradient(160deg, #1b1740f2, #0c1024f5 55%, #0a0e1ff7); border-left: 1px solid #b388ff66; backdrop-filter: blur(10px); box-shadow: -18px 0 60px #000a, inset 1px 0 0 #ffffff14; animation: oSkSlide .46s cubic-bezier(.2,1.2,.3,1) both; scrollbar-width: thin; scrollbar-color: #7c4dff66 transparent; }
#office .o-sk h2 { margin: 0 0 12px; font-size: 22px; letter-spacing: .2px; display: flex; align-items: center; gap: 10px; color: #e8dcff; }
#office .o-sk h2 small { font-size: 12.5px; color: #9fb3ff; font-weight: 500; padding: 2px 9px; border-radius: 99px; background: #ffffff12; }
#office .o-sk button, #office .o-sk select, #office .o-sk input { font: inherit; font-size: 13.5px; color: #fff; background: #ffffff12; border: 1px solid #ffffff26; border-radius: 10px; padding: 6px 12px; transition: background .15s, border-color .15s, transform .15s, box-shadow .15s; outline: none; }
#office .o-sk button { cursor: pointer; } #office .o-sk button:hover { background: #ffffff24; transform: translateY(-1px); } #office .o-sk button:active { transform: scale(.96); }
#office .o-sk input:focus, #office .o-sk select:focus { border-color: #b388ff; box-shadow: 0 0 0 3px #b388ff33; }
#office .o-sk button.o-pri { background: linear-gradient(135deg, #7c4dff, #5b7cff); border-color: #b388ff; box-shadow: 0 4px 14px #7c4dff55; } #office .o-sk h2 button { margin-left: auto; }
#office .o-sk input { min-width: 0; flex: 1; } #office .o-sk option { background: #0e1228; }
#office .o-sk .o-tabs, #office .o-sk .o-skbar, #office .o-sk .o-chips { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin: 8px 0; }
#office .o-sk .o-tabs { padding: 4px; background: #ffffff0d; border-radius: 14px; width: fit-content; }
#office .o-sk .o-tabs button { border-color: transparent; background: transparent; }
#office .o-sk .o-tabs button.o-on { background: linear-gradient(135deg, #7c4dff, #5b7cff); box-shadow: 0 3px 12px #7c4dff66; }
#office .o-sk .o-chips button { border-radius: 99px; padding: 3px 12px; font-size: 12.5px; } #office .o-sk .o-chips button.o-on { background: #b388ff33; border-color: #b388ff; color: #f1e8ff; }
#office .o-sk .o-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(215px, 1fr)); gap: 10px; margin-top: 10px; align-items: start; }
#office .o-sk .o-grid .o-card.o-open { grid-column: 1 / -1; }
#office .o-sk .o-card + .o-card { margin-top: 8px; } #office .o-sk .o-grid .o-card + .o-card { margin-top: 0; }
#office .o-sk .o-grid .o-brief { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
#office .o-sk .o-grid .o-card.o-open .o-brief { display: block; }
#office .o-sk .o-chips button i { font-style: normal; opacity: .65; margin-left: 5px; font-size: 11.5px; }
#office .o-sk .o-card { position: relative; padding: 10px 12px 10px 14px; margin: 0; border-radius: 12px; cursor: pointer; background: linear-gradient(135deg, color-mix(in srgb, var(--c, #888) 14%, #ffffff08), #ffffff07); border: 1px solid #ffffff14; transition: transform .18s cubic-bezier(.2,1.3,.4,1), box-shadow .2s, border-color .2s, background .2s; overflow: hidden; }
#office .o-sk .o-card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--c, #888); transition: width .2s, box-shadow .2s; }
#office .o-sk .o-card:hover { transform: translateX(-4px) scale(1.012); border-color: color-mix(in srgb, var(--c, #888) 70%, #fff0); box-shadow: 0 8px 26px #0008, 0 0 0 1px color-mix(in srgb, var(--c, #888) 40%, #0000); }
#office .o-sk .o-card:hover::before, #office .o-sk .o-card.o-open::before { width: 8px; box-shadow: 0 0 14px var(--c, #888); }
#office .o-sk .o-card.o-open { border-color: color-mix(in srgb, var(--c, #888) 80%, #fff0); }
#office .o-sk .o-skhelp { margin: 2px 0 8px; font-size: 12px; color: #9fb0e6; }
#office .o-sk .o-d8 { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 8px; font-size: 12px; color: #b6bfe0; }
#office .o-sk .o-vf { font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; padding: 1px 7px; border-radius: 9px; margin-left: 4px; color: #fff; background: #5c6892; }
#office .o-sk .o-vf-verified { background: #2e9e5b; } #office .o-sk .o-vf-failed { background: #d0475a; }
#office .o-sk .o-src { font-size: 11px; color: #8c97b8; margin-top: 2px; }
#office .o-sk .o-card b { font-size: 15px; } #office .o-sk .o-card .o-brief { color: #b6bfe0; font-size: 13px; margin: 3px 0 2px; }
#office .o-sk .o-pill { display: inline-block; font-size: 10.5px; font-weight: 800; letter-spacing: .4px; text-transform: uppercase; padding: 1px 8px; border-radius: 99px; background: var(--c, #888); color: #10121c; margin-left: 8px; vertical-align: 1px; }
#office .o-sk .o-who { display: inline-block; font-size: 11.5px; padding: 1px 9px; border-radius: 99px; background: #ffffff1a; border: 1px solid #ffffff14; margin: 4px 5px 0 0; }
#office .o-sk .o-det { margin-top: 10px; font-size: 13px; color: #d6defc; cursor: default; animation: oSkOpen .34s cubic-bezier(.2,1,.3,1) both; transform-origin: top; }
#office .o-sk .o-det code { background: #ffffff12; border-radius: 6px; padding: 2px 7px; font-size: 12px; word-break: break-all; }
#office .o-sk .o-empty { color: #8c97b8; font-size: 13.5px; padding: 6px 2px; } #office .o-sk .o-msg { color: #ffab91; font-size: 13.5px; padding: 6px 2px; animation: oSkOpen .3s both; } #office .o-sk .o-ok { color: #7fd6a0; font-size: 13.5px; padding: 6px 2px; animation: oSkOpen .3s both; }
#office .o-sk .o-box { border: 1px solid #b388ff; border-radius: 12px; padding: 10px 12px; margin: 10px 0; background: #b388ff1c; font-size: 13.5px; animation: oSkOpen .3s both; }
#office .o-sk .o-skrow { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
#office .o-sk a { color: #9fd0ff; }
#office .o-sk.o-fresh .o-card { animation: oSkIn .42s cubic-bezier(.2,1.2,.3,1) both; animation-delay: calc(var(--i, 0) * 32ms); }
#office .o-flag.o-skill { background: #7c4dff; color: #fff; }
@keyframes oSkFade { from { opacity: 0; } }
@keyframes oSkSlide { from { transform: translateX(60px); opacity: 0; } }
@keyframes oSkIn { from { transform: translateY(14px) scale(.97); opacity: 0; } }
@keyframes oSkOpen { from { transform: scaleY(.85); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { #office .o-sk-ov, #office .o-sk, #office .o-sk .o-card, #office .o-sk .o-det, #office .o-sk .o-box, #office .o-sk .o-msg, #office .o-sk .o-ok { animation: none !important; transition: none !important; } }
`;
export const ORIGIN_COLOR = {user: '#4fc3f7', project: '#66bb6a', plugin: '#b388ff', account: '#f48fb1', builtin: '#90a4ae', added: '#ffb74d'};
/** D8 on the card, from the fields the server always sends: the state of its check, how it was used, its level and parent (null/0 when there is nothing) */
export const d8Lines = (s, T, all = []) => {
  const vf = s.verified?.state, u = s.usage || {}, parent = s.parent ? (all.find(x => x.id === s.parent)?.name || s.parent) : '';
  return {
    verified: vf === 'verified' || vf === 'failed' ? vf : 'unverified',
    use: u.count ? T.useLine(u.count, u.rooms || 0) + ((u.ok || u.fail) ? ' · ' + T.useOkFail(u.ok || 0, u.fail || 0) : '') : u.unused ? T.useUnused(u.scanned_rooms || 0) : T.useNone,
    level: s.level ? (T.level[s.level] || s.level) + (parent ? ' · ' + T.levelUnder(parent) : '') : '',
  };
};
/** where a skill comes from, in plain words (the id is origin:plugin:name; the server may also send plugin, version) */
export const sourceOf = (s, T) => {
  const src = s.source, v = src?.version ? ' ' + src.version : '';                // D7: the server says where it comes from (kind, label, version)
  if (src?.kind) {
    if (['marketplace', 'local', 'desktop'].includes(src.kind)) return T.fromPlugin((src.label || '?') + v);
    if (src.kind === 'repo') return T.fromRepo((src.label || '?') + v);
    return {you: T.writtenByYou, project: T.fromProject, claude: T.fromAccount, builtin: T.fromBuiltin}[src.kind] || src.kind;
  }
  const plug = s.plugin || (s.id || '').split(':')[1], ver = s.version ? ' ' + s.version : '';
  if (s.origin === 'plugin') return T.fromPlugin(plug && plug !== '-' ? plug + ver : '?');
  return {user: T.writtenByYou, project: T.fromProject, account: T.fromAccount, builtin: T.fromBuiltin, added: T.fromFolder}[s.origin] || s.origin || '';
};
const VIA = {brief: '📝', type: '🧩', used: '✅'};
const esc = x => String(x ?? '').replace(/[&<>"]/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[ch]));

/** the skills that fit the text (name, brief, description) and the origin ('' = every one), as the server's q and origin do, for the panel to filter as you type */
export const filterSkills = (skills, q = '', origin = '') => {
  const t = String(q).trim().toLowerCase();
  return (skills || []).filter(s => (!origin || s.origin === origin) && (!t || `${s.name} ${s.brief || ''} ${s.description || ''}`.toLowerCase().includes(t)));
};
/** the agents on a collapsed card: the first three names and "+N" for the rest (all of them are in the opened card) */
export const agentBadges = (agents, max = 3) => { const a = agents || []; return a.length > max ? [...a.slice(0, max), `+${a.length - max}`] : a; };
/** how many skills an agent has, and which (skill records, with how it got them) */
export const skillsOf = (data, name) => {
  const a = (data?.agents || []).find(x => x.name === name), by = new Map((data?.skills || []).map(s => [s.id, s]));
  return (a?.skills || []).map(r => ({...r, skill: by.get(r.id) || null})).filter(r => r.skill);
};
/** the spines on the shelf: one per skill in the order of the grid, the skills an agent has first from the top row down; out: pulled forward when an agent has it; at most cols*rows */
export function spines(skills, {cols = 18, rows = 4} = {}) {
  const order = [...(skills || [])].sort((a, b) => (b.agents?.length || 0) - (a.agents?.length || 0) || a.id.localeCompare(b.id)).slice(0, cols * rows);
  return order.map((s, i) => {
    let h = 7; for (const c of s.id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return {id: s.id, col: i % cols, row: rows - 1 - Math.floor(i / cols), h: 2 + (h % 3), out: !!s.agents?.length, color: ORIGIN_COLOR[s.origin] || '#9e9e9e', shade: 0.62 + ((h >> 3) % 4) * 0.1 + (i % 2) * 0.12};
  });
}

/** THREE, V (office-voxel.js), shelf: the shelf's mesh (office.js finds it); raycastables: what a click can hit; say: a line for the office's name tag */
export function createSkills({THREE, V, camera = null, shelf, raycastables, root, lang = () => 'en', url = 'skills.json', every = 60000, paused = () => false, onEnabled = () => {}}) {
  const L = () => S[lang()] || S.en;
  const style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
  let data = null, ov = null, timer = 0, busy = false, announced = false, books = null, sig = '';
  let tab = 'explore', q = '', origin = '', openId = '', pending = null, note = null, fresh = true;
  const upd = {};                                                          // skill id -> the answer of update_check, or 'wait'
  if (shelf) shelf.traverse(o => { o.userData.skills = true; if (o.isMesh) raycastables.push(o); });

  // ------------------------------------------------ the shelf
  const G = V.SKILL_SHELF;
  function shelve() {
    const list = spines(data?.skills, G), key = JSON.stringify(list.map(s => [s.id, s.out]));
    if (!shelf || key === sig) return; sig = key;
    const first = !books; spineList = list; highlight('');
    if (books) { shelf.remove(books); books.geometry.dispose(); }
    const v = new V.Vox();
    for (const s of list) {
      const x = 1 + s.col, y = G.rowY[s.row], z = s.out ? 2 : 1, c = new THREE.Color(s.color).multiplyScalar(s.shade).getStyle();
      v.box(x, y, z, x, y + s.h, z + 1, c);
    }
    books = V.mesh(v, {pivot: G.pivot}); if (first) { growAt = 0; books.scale.y = 0.02; } books.traverse(o => { o.userData.skills = true; }); raycastables.push(books); shelf.add(books);
    drawSign();
  }
  // the shelf comes alive: the books grow up when it first fills, and the skill you point at in the panel lights up on its shelf
  let spineList = [], hl = null, hlId = '', growAt = -1, lastT = 0;
  function highlight(id) {
    if (id === hlId) return; hlId = id;
    if (hl) { shelf.remove(hl); hl.geometry.dispose(); hl = null; }
    const s = id && spineList.find(x => x.id === id); if (!s || !shelf) return;
    const v = new V.Vox(), x = 1 + s.col, y = G.rowY[s.row], z = s.out ? 2 : 1;
    v.box(x - 0.3, y - 0.3, z - 0.3, x + 1.3, y + s.h + 0.3, z + 1.3, '#fff3b0');
    hl = V.mesh(v, {pivot: G.pivot}, true); shelf.add(hl);
  }
  /** every frame (t in seconds): the growth of the books, the pulse of the light on the one you point at */
  function update(t) {
    if (!shelf) return;
    const dt = Math.min(0.1, t - (lastT || t)); lastT = t;
    if (books && growAt >= 0) {
      growAt = Math.min(1, growAt + dt / 0.9); const k = growAt - 1, e = 1 + 2.2 * k * k * k + 1.2 * k * k;         // out and back (easeOutBack)
      books.scale.y = Math.max(0.02, e); if (growAt >= 1) { books.scale.y = 1; growAt = -1; }
    }
    if (hl) hl.scale.setScalar(1 + 0.025 * Math.sin(t * 6));
    if (ov) offsetView();
  }
  /** while the panel stands on the right the scene is pushed to the left half, so the shelf you point at is not behind the panel */
  function offsetView() {
    const p = ov?.querySelector('.o-sk'), w = root.clientWidth || 1, h = root.clientHeight || 1, dw = p ? Math.min(p.offsetWidth, w * 0.6) : 0;
    if (!camera || !dw) return;
    if (camera.view?.offsetX !== Math.round(dw / 2) || camera.view?.fullWidth !== w) { camera.setViewOffset(w, h, Math.round(dw / 2), 0, w, h); }
  }
  let sign = null;
  function drawSign() {
    if (!shelf) return;
    if (!sign) {
      const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 128;
      const tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.4), new THREE.MeshBasicMaterial({map: tex, toneMapped: false}));
      m.position.set(0, 2.5, 0.1); m.userData.skills = true; raycastables.push(m); shelf.add(m); sign = {canvas, tex};
    }
    const g = sign.canvas.getContext('2d'), n = data?.skills?.length || 0;
    g.fillStyle = '#1a1030'; g.fillRect(0, 0, 512, 128); g.strokeStyle = '#b388ff'; g.lineWidth = 8; g.strokeRect(4, 4, 504, 120);
    g.fillStyle = '#d1b3ff'; g.font = '800 62px "Segoe UI", sans-serif'; g.textBaseline = 'middle'; g.fillText('SKILLS', 26, 66);
    g.textAlign = 'right'; g.fillStyle = '#9fb3ff'; g.font = '700 50px "Segoe UI", sans-serif'; g.fillText(String(n), 486, 66); g.textAlign = 'left';
    sign.tex.needsUpdate = true;
  }

  // ------------------------------------------------ the data and the actions
  async function load() {
    if (busy) return; busy = true;
    try {
      const r = await fetch(url, {cache: 'no-store'});
      if (r.ok) { data = await r.json(); got(); }
    } catch (e) { /* the viewer is away: the shelf keeps what it had */ }
    busy = false;
  }
  function got() { shelve(); if (!announced && data) { announced = true; onEnabled(); } if (ov) fill(); }
  async function act(body) {
    try {
      const r = await fetch('skills/do', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      return await r.json();
    } catch (e) { return {ok: false, error: String(e.message || e)}; }
  }
  load(); timer = setInterval(() => { if (ov || !paused()) load(); }, every);

  // ------------------------------------------------ the panel
  const chip = (s, key) => `<button data-${key}="${esc(s.v)}" class="${s.on ? 'o-on' : ''}">${esc(s.t)}</button>`;
  const who = (s, T) => (s.agents || []).length ? s.agents.map(n => `<span class="o-who">${esc(n)}</span>`).join('') : `<span class="o-empty">${esc(T.noAgents)}</span>`;
  function d8Html(s, T) {                                                   // D8: only what is read here; the heavy actions (check, activation, cases, improve) are the chat panel's
    const l = d8Lines(s, T, data?.skills);
    return `<div class="o-d8"><span class="o-vf o-vf-${l.verified}">${esc(T.vf[l.verified])}</span><span>${esc(l.use)}</span>${l.level ? `<span>${esc(l.level)}</span>` : ''}</div>`
      + `<div class="o-skrow"><button data-inchat="${esc(s.id)}">${esc(T.openChat)}</button></div>`;
  }
  function updHtml(s, T) {                                                  // D7: only for a skill with an outside creator (the server says updatable); read only until the user confirms
    if (!s.updatable) return '';
    const u = upd[s.id], i = u && u !== 'wait' ? u : null;
    const line = u === 'wait' ? T.upChecking : !i ? '' : i.newer === false ? T.upToDate : i.newer === null ? T.upUnknown : T.upInfo(i.installed, i.available) + (i.changes ? ' · ' + i.changes : '');
    return `<div class="o-skrow"><button data-upcheck="${esc(s.id)}">${esc(T.upCheck)}</button>${i?.newer ? `<button class="o-pri" data-upapply="${esc(s.id)}">${esc(T.upApply)}</button>` : ''}<span class="o-empty">${esc(line)}</span></div>`;
  }
  function exploreHtml(T) {
    const list = filterSkills(data?.skills, q, origin), T0 = (data?.origins || Object.keys(ORIGIN_COLOR));
    const cnt = o => (data?.skills || []).filter(s => !o || s.origin === o).length;
    const names = ['', ...T0].map(o => chip({v: o, t: o ? T.origin[o] || o : T.all, on: origin === o}, 'origin').replace('</button>', `<i>${cnt(o)}</i></button>`)).join('');
    const rows = list.map((s, n) => {
      const open = s.id === openId, c = ORIGIN_COLOR[s.origin] || '#9e9e9e';
      let det = '';
      if (open) {
        const to = ['<option value="all">' + esc(T.everyone) + '</option>', ...(data.agents || []).map(a => `<option>${esc(a.name)}</option>`)].join('');
        det = `<div class="o-det"><div>${esc(s.description || s.brief)}</div><div class="o-skrow"><code>${esc(s.path)}</code></div>`
          + `<div style="margin-top:6px">${who(s, T)}</div>`
          + (s.advised?.length ? `<div class="o-empty">${esc(s.advised.map(a => T.advisedTo(a.to)).join(' · '))}</div>` : '')
          + d8Html(s, T) + updHtml(s, T)
          + `<div class="o-skrow"><select data-to>${to}</select><input data-note placeholder="${esc(T.notePh)}"><button class="o-pri" data-advise="${esc(s.id)}">${esc(T.recommend)}</button></div></div>`;
      }
      return `<div class="o-card ${open ? 'o-open' : ''}" style="--c:${c};--i:${Math.min(n, 12)}" data-id="${esc(s.id)}"><b>${esc(s.name)}</b><span class="o-pill">${esc(T.origin[s.origin] || s.origin)}</span>${['verified', 'failed'].includes(s.verified?.state) ? `<span class="o-vf o-vf-${s.verified.state}">${esc(T.vf[s.verified.state])}</span>` : ''}`
        + `<div class="o-brief">${esc(s.brief)}</div><div class="o-src">${esc(sourceOf(s, T))}</div>${open ? '' : agentBadges(s.agents).map(n => `<span class="o-who">${esc(n)}</span>`).join('')}${det}</div>`;
    }).join('');
    return `<div class="o-skbar"><input data-q value="${esc(q)}" placeholder="${esc(T.filterPh)}"></div><div class="o-chips">${names}</div><div class="o-skhelp">${esc(T.help[origin || 'all'] || '')}</div>`
      + (rows ? `<div class="o-grid">${rows}</div>` : `<div class="o-empty">${esc(T.none)}</div>`);
  }
  function agentsHtml(T) {
    const rows = (data?.agents || []).map(a => {
      const mine = skillsOf(data, a.name);
      return `<div class="o-card" style="--c:#b388ff"><b>${esc(a.name)}</b><span class="o-pill" style="--c:#455a64;color:#fff">${esc(T.count(mine.length))}</span><div>`
        + (mine.map(r => `<span class="o-who" title="${esc((r.via || []).join(' · '))}">${(r.via || []).map(v => VIA[v] || '').join('')} ${esc(r.skill.name)}</span>`).join('') || `<span class="o-empty">${esc(T.noSkills)}</span>`) + '</div></div>';
    }).join('');
    return rows || `<div class="o-empty">${esc(T.none)}</div>`;
  }
  const forOptions = T => ['<option value="">' + esc(T.everyone) + '</option>', ...(data?.agents || []).map(a => `<option>${esc(a.name)}</option>`)].join('');
  function searchHtml(T) {
    const sr = data?.searcher, all = (data?.requests || []).slice().reverse(), reqs = all.filter(r => !r.kind || r.kind === 'search'), jobs = all.filter(r => r.via === 'lead');
    const card = (rq, c) => `<div class="o-card" style="--c:${c.added ? '#43d17a' : '#ffb74d'}"><b>${esc(c.name)}</b>${c.added ? `<span class="o-pill">${esc(T.added)}</span>` : ''}`
      + `<div class="o-brief">${esc(c.what)}</div><div class="o-skrow"><small>${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.source || c.url)}</a>` : esc(c.source)}</small>`
      + (c.trust ? `<small>${esc(c.trust)}</small>` : '') + (c.added ? '' : `<button class="o-pri" data-addcard="${esc(rq.req)}|${esc(c.name)}">${esc(T.add)}</button>`) + '</div></div>';
    const derive = `<div class="o-box"><button class="o-pri" data-derive>${esc(T.deriveBtn)}</button><div class="o-empty">${esc(T.deriveHelp)}</div>`
      + jobs.map(j => `<div class="o-empty">${esc((T.kind[j.kind] || j.kind) + ' ' + j.req + ' · ' + (j.state === 'pending' ? (j.announced ? T.state.working : T.state.waitLead) : T.state[j.state] || j.state))}</div>`).join('') + '</div>';
    return derive + `<div class="o-skbar"><input data-sq placeholder="${esc(T.searchPh)}"><select data-for title="${esc(T.forWho)}">${forOptions(T)}</select><button class="o-pri" data-search>${esc(T.go)}</button></div>`
      + `<div class="o-empty">${esc(sr?.present ? (sr.busy ? T.searcherBusy(sr.name) : T.searcherIs(sr.name)) : T.noSearcher)}</div>`
      + reqs.map(rq => `<h3 style="margin:12px 0 2px;font-size:13px;color:#d1b3ff">“${esc(rq.q)}” <small style="color:#8c97b8">${esc(T.state[rq.state] || rq.state)}${rq.for?.length ? ' · ' + esc(T.forThem(rq.for.join(', '))) : ''}</small></h3>`
        + ((rq.cards || []).map(c => card(rq, c)).join('') || '')).join('')
      + `<div class="o-skbar" style="margin-top:14px"><input data-path placeholder="${esc(T.pathPh)}"><button data-addpath>${esc(T.addFolder)}</button></div>`;
  }
  function noteHtml(T) {
    if (!note) return '';
    if (note.kind === 'preview') {
      const p = note.preview || {};
      return `<div class="o-box"><b>${esc(T.confirmTitle)}</b><div>${esc(p.name)}${p.brief ? ' · ' + esc(p.brief) : ''}</div><div class="o-empty">${esc(T.from)}: <code>${esc(p.from || '')}</code> → <code>${esc(p.to || p.path || '')}</code></div>`
        + `<div class="o-skrow"><button class="o-pri" data-confirm>${esc(T.confirm)}</button><button data-cancel>${esc(T.cancel)}</button></div></div>`;
    }
    if (note.kind === 'upd') {
      const p = note.preview || {};
      return `<div class="o-box"><b>${esc(T.upConfirmTitle)}</b><div>${esc(p.name)} · ${esc(T.upInfo(p.installed || p.from || '?', p.available || p.to || '?'))}</div><div class="o-empty">${esc(T.upHow)}: <code>${esc(p.how || '')}</code>${p.restart ? ' · ' + esc(T.upRestart) : ''}</div>`
        + `<div class="o-skrow"><button class="o-pri" data-confirm>${esc(T.confirm)}</button><button data-cancel>${esc(T.cancel)}</button></div></div>`;
    }
    if (note.kind === 'derive') {
      const p = note.preview || {};
      return `<div class="o-box"><b>${esc(T.deriveTitle(p.name || 'LEAD'))}</b><div class="o-empty">${esc(p.task || '')}</div>`
        + `<div class="o-skrow"><button class="o-pri" data-confirm>${esc(T.confirm)}</button><button data-cancel>${esc(T.cancel)}</button></div></div>`;
    }
    if (note.kind === 'temp') return `<div class="o-box">${esc(T.needSearcher(note.preview?.name || 'SKILLFIND'))}<div class="o-skrow"><button class="o-pri" data-confirm>${esc(T.tempBtn)}</button><button data-cancel>${esc(T.cancel)}</button></div></div>`;
    return `<div class="${note.ok ? 'o-ok' : 'o-msg'}">${esc(note.text)}</div>`;
  }
  function fill() {
    if (!ov) return;
    const T = L(), d = data, box = ov.querySelector('.o-sk');
    const keep = {q: box.querySelector('[data-q]')?.matches(':focus'), sq: box.querySelector('[data-sq]')?.value, path: box.querySelector('[data-path]')?.value, top: box.scrollTop};
    box.classList.toggle('o-fresh', fresh); fresh = false;                           // the cards come in one after the other when the panel opens or the list changes, not at every key typed
    box.innerHTML = `<h2>📚 ${esc(T.title)} <small>${d ? esc(T.count((d.skills || []).length)) + ' · ' + esc(T.agentsN((d.agents || []).length)) : ''}</small><button data-x>${T.close} (Esc)</button></h2>`
      + `<div class="o-tabs">${['explore', 'agents', 'search'].map(k => chip({v: k, t: T[k], on: tab === k}, 'tab')).join('')}</div>` + noteHtml(T)
      + (!d ? `<div class="o-empty">${esc(T.loading)}</div>` : tab === 'explore' ? exploreHtml(T) : tab === 'agents' ? agentsHtml(T) : searchHtml(T));
    const sq = box.querySelector('[data-sq]'), pa = box.querySelector('[data-path]'), fq = box.querySelector('[data-q]');
    if (sq && keep.sq) sq.value = keep.sq; if (pa && keep.path) pa.value = keep.path;
    if (fq && keep.q) { fq.focus(); fq.setSelectionRange(fq.value.length, fq.value.length); }
    box.scrollTop = keep.top;
  }
  const say = (text, ok = true) => { note = {kind: 'msg', ok, text}; fill(); };
  async function run(body, T) {
    const r = await act(body); load();
    if (!r.ok) return r.need === 'temp_searcher' ? (pending = {action: 'temp_searcher', q: body.q, for: body.for}, ask('temp', pending)) : say(r.error || T.error, false);
    return r;
  }
  async function ask(kind, body) {                                          // the preview comes first, nothing is written until the user confirms
    const r = await act({...body, confirm: false});
    if (!r.ok) return say(r.error || L().error, false);
    pending = body; note = {kind, preview: r.preview}; fill();
  }
  async function onClick(e) {
    const T = L(), t = e.target, el = k => t.closest(`[data-${k}]`);
    if (t === ov || el('x')) return close();
    if (el('tab')) { tab = el('tab').dataset.tab; note = null; fresh = true; return fill(); }
    if (el('origin')) { origin = el('origin').dataset.origin; fresh = true; return fill(); }
    if (el('advise')) {
      const row = el('advise').closest('.o-det'), to = row.querySelector('[data-to]').value, nt = row.querySelector('[data-note]').value;
      const r = await act({action: 'advise', skill: el('advise').dataset.advise, to, note: nt}); load();
      return say(r.ok ? T.sent : r.error || T.error, !!r.ok);
    }
    if (el('search')) {
      const q = box().querySelector('[data-sq]').value.trim(), pick = box().querySelector('[data-for]').value;
      if (!q) return; note = null;
      const r = await run({action: 'search', q, for: pick ? [pick] : []}, T); if (r?.ok) say(T.asked(r.searcher || '')); return;
    }
    if (el('upcheck')) {
      const id = el('upcheck').dataset.upcheck; upd[id] = 'wait'; fill();
      const r = await act({action: 'update_check', skill: id}); if (!r.ok) { delete upd[id]; fill(); return say(r.error || T.error, false); }
      upd[id] = r.update; return fill();
    }
    if (el('inchat')) {                                                     // the heavy actions are the chat panel's: open it on this skill
      const id = el('inchat').dataset.inchat; close(); window.skillsView?.show ? window.skillsView.show(id) : window.skillsView?.open?.(true);
      const sv = document.getElementById('skillsView');
      if (sv && getComputedStyle(sv).display === 'none') window.officeMode?.('chat');   // an old viewer hides every page but the office in office-only mode (DESIGN T28 lets this panel show): then go to the chat
      return;
    }
    if (el('upapply')) return ask('upd', {action: 'update_apply', skill: el('upapply').dataset.upapply});
    if (el('derive')) return ask('derive', {action: 'derive', source: {chat: true}});
    if (el('addcard')) { const [req, card] = el('addcard').dataset.addcard.split('|'); return ask('preview', {action: 'add', req, card}); }
    if (el('addpath')) { const v = box().querySelector('[data-path]').value.trim(); return v ? ask('preview', {action: 'add', path: v}) : undefined; }
    if (el('cancel')) { pending = note = null; return fill(); }
    if (el('confirm') && pending) {
      const pendingId = pending.skill, r = await act({...pending, confirm: true}); pending = null; load();
      if (r.ok && r.applied) { delete upd[pendingId]; return say(T.upDone(r.installed || '') + (r.restart ? ' · ' + T.upRestart : '')); }
      return say(r.ok ? (r.via === 'lead' ? T.deriveWaiting(r.name || 'LEAD') : r.name ? T.tempDone(r.name) : T.addedDone) : r.error || T.error, !!r.ok);
    }
    const card = t.closest('.o-card[data-id]');
    if (card && !t.closest('.o-det')) { openId = openId === card.dataset.id ? '' : card.dataset.id; return fill(); }
  }
  const box = () => ov.querySelector('.o-sk');
  const onKey = e => { if (e.key === 'Escape') { e.stopImmediatePropagation(); close(); } };
  function open() {
    if (ov) return close();
    ov = document.createElement('div'); ov.className = 'o-sk-ov'; ov.innerHTML = '<div class="o-sk"></div>';
    for (const ev of ['pointerdown', 'wheel', 'keydown']) ov.addEventListener(ev, e => e.stopPropagation());
    ov.addEventListener('click', onClick);
    ov.addEventListener('pointerover', e => { const c = e.target.closest?.('.o-card[data-id]'); highlight(c ? c.dataset.id : openId); });
    ov.addEventListener('input', e => { if (e.target.matches('[data-q]')) { q = e.target.value; fill(); } });
    ov.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches('[data-sq]')) ov.querySelector('[data-search]').click(); });
    fresh = true; root.appendChild(ov); addEventListener('keydown', onKey, true); fill(); load();
  }
  function close() { if (!ov) return; highlight(''); camera?.clearViewOffset(); removeEventListener('keydown', onKey, true); ov.remove(); ov = null; note = pending = null; }

  /** show this data now (the same shape as skills.json): for tests and demos */
  function feed(d) { data = d; got(); }
  return {feed, open, close, update, active: () => !!ov, enabled: () => !!data, mesh: shelf,
          /** the number of skills an agent has (the badge over its head) */
          count: name => skillsOf(data, name).length, stop: () => clearInterval(timer)};
}
