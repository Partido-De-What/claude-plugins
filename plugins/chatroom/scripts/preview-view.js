/* The Previews view (0.19, D4): what the agents build, live, without a single token. An agent declares ONE thing (chat.py preview
   PATH_OR_URL): the server watches the disk and answers GET preview.json (per agent: kind, src, mtime). This page shows one tile per
   agent that has a preview, in a grid of 1, 2, 3 or 4 by how many there are; a click on a tile focuses it, a click on its header (or
   Esc) goes back to the grid. A tile reloads only when its mtime changes. HTML runs in a sandboxed iframe, images and textures sit on
   a checkerboard with a sharp zoom, video and audio start muted. Opened by the 🖼 button or ?view=preview; ?mock=1 shows made-up
   previews. Same look as skills-view.js (the D5 tokens). */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const MOCK = new URLSearchParams(location.search).get('mock') === '1';
  const PV = {open: false, data: null, err: '', focus: null, tiles: new Map(), hash: ''};

  // needs the --d-* tokens: skills-view.js (loaded just before this file) puts them on the page
  const ICON = p => `<svg class="pv-i" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
  const IC = {view: ICON('<rect x="3" y="4" width="18" height="13" rx="2.5"/><path d="M8 21h8M12 17v4"/>'), zoom: ICON('<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2M11 8.5v5M8.5 11h5"/>'),
    on: ICON('<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M15.5 9a4 4 0 010 6M18 6.5a7.5 7.5 0 010 11"/>'), off: ICON('<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>'),
    reload: ICON('<path d="M20 12a8 8 0 10-2.5 5.8"/><path d="M20 5v5h-5"/>'), lens: ICON('<circle cx="10" cy="10" r="6.5"/><path d="M20 20l-5.2-5.2"/><circle cx="10" cy="10" r="2.2"/>'),
    snap: ICON('<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>'), out: ICON('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/>')};
  const css = document.createElement('style');
  css.textContent = `
  #previewView { --pv-chk1: color-mix(in oklab, var(--d-text) 9%, transparent); --pv-chk2: color-mix(in oklab, var(--d-text) 3%, var(--d-card2));
    position: fixed; inset: 0; z-index: 60; display: none; flex-direction: column; background: var(--d-bg); color: var(--d-text);
    font: 15px/1.5 "Inter", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif; padding: 18px 26px 22px; gap: 14px; box-sizing: border-box; overflow: clip; }
  #previewView::before { content: ""; position: absolute; inset: -20%; pointer-events: none; z-index: 0;
    background: radial-gradient(40% 35% at 12% 8%, color-mix(in oklab, var(--d-accent) 22%, transparent), transparent 70%), radial-gradient(38% 34% at 92% 92%, rgba(109,93,252,.16), transparent 70%);
    animation: pv-drift 24s ease-in-out infinite alternate; }
  #previewView > * { position: relative; z-index: 1; }
  body.pv-open #previewView { display: flex; animation: pv-open var(--d-t-enter) var(--d-ease); }
  svg.pv-i { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: none; vertical-align: -3px; }
  .pv-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .pv-logo { width: 44px; height: 44px; border-radius: 15px; background: var(--d-grad); display: grid; place-items: center; color: #fff; border: 0; cursor: pointer; padding: 0;
    box-shadow: 0 8px 20px -6px var(--d-accent); transition: transform var(--d-t) var(--d-spring); }
  .pv-logo:hover { transform: rotate(-6deg) scale(1.06); } .pv-logo svg { width: 24px; height: 24px; }
  .pv-title { font-size: 19px; font-weight: 650; letter-spacing: -.01em; margin-right: 10px; }
  .pv-pill { border: 1px solid var(--d-line); background: var(--d-card); backdrop-filter: blur(14px); color: var(--d-text); border-radius: var(--d-r-pill); padding: 6px 16px; cursor: pointer; font: inherit; font-size: 14px; font-weight: 550; }
  .pv-pill.on { background: color-mix(in oklab, var(--d-accent) 14%, var(--d-card)); color: var(--d-accent); border-color: var(--d-accent); }
  .pv-sp { flex: 1; } .pv-sub { color: var(--d-muted); font-size: 13.5px; }
  .pv-grid { flex: 1; min-height: 0; display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr); grid-auto-rows: minmax(0, 1fr); }
  .pv-grid[data-n="2"] { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pv-grid[data-n="3"] { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pv-grid[data-n="4"] { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pv-grid[data-n="5"] { grid-template-columns: repeat(3, minmax(0, 1fr)); grid-auto-rows: minmax(260px, 1fr); overflow-y: auto; }
  .pv-grid.focus { grid-template-columns: minmax(0, 1fr); } .pv-grid.focus .pv-tile:not(.focus) { display: none; }
  .pv-tile { background: var(--d-card); border: 1px solid var(--d-line); border-radius: var(--d-r-lg); backdrop-filter: blur(14px); box-shadow: var(--d-shadow); display: flex; flex-direction: column; min-height: 0; min-width: 0; overflow: hidden;
    animation: pv-enter var(--d-t-enter) var(--d-ease) both; transition: border-color var(--d-t-fast), box-shadow var(--d-t); }
  .pv-tile:hover { border-color: color-mix(in oklab, var(--d-accent) 45%, var(--d-line)); }
  .pv-tile.focus { border-color: var(--d-accent); }
  .pv-tile.fresh { animation: pv-flash 1.1s var(--d-ease); }                       /* the page just changed on disk */
  .pv-head { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-bottom: 1px solid var(--d-line); cursor: pointer; min-width: 0; transition: background-color var(--d-t-fast); }
  .pv-head:hover { background: var(--d-hover); }
  .pv-av { --c: oklch(.72 .15 var(--h, 200)); width: 28px; height: 28px; border-radius: 50%; flex: none; display: grid; place-items: center; font-weight: 700; font-size: 12px; color: #fff;
    background: linear-gradient(135deg, var(--c), oklch(.58 .17 calc(var(--h, 200) + 40))); }
  .pv-name { font-weight: 650; font-size: 15px; } .pv-file { color: var(--d-muted); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1; }
  .pv-ic { background: none; border: 0; color: var(--d-muted); cursor: pointer; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 10px; text-decoration: none; flex: none;
    transition: background-color var(--d-t-fast), color var(--d-t-fast), transform var(--d-t) var(--d-spring); }
  .pv-ic:hover { color: var(--d-text); background: var(--d-hover); transform: translateY(-1px); } .pv-ic:active { transform: scale(.9); } .pv-ic.on { color: var(--d-accent); }
  .pv-pill:focus-visible, .pv-ic:focus-visible, .pv-logo:focus-visible { outline: 2px solid var(--d-accent); outline-offset: 2px; }
  .pv-body { flex: 1; min-height: 0; position: relative; background: var(--d-card2); display: flex; }
  .pv-body iframe { border: 0; width: 100%; height: 100%; background: #fff; }
  .pv-body video { width: 100%; height: 100%; object-fit: contain; background: #000; }
  .pv-body audio { margin: auto; width: 90%; }
  .pv-img { flex: 1; overflow: auto; display: flex; background-color: var(--pv-chk2); background-image: conic-gradient(var(--pv-chk1) 25%, transparent 0 50%, var(--pv-chk1) 0 75%, transparent 0); background-size: 20px 20px; }
  .pv-img img { margin: auto; width: 100%; height: 100%; object-fit: contain; }   /* fit: small textures grow, pixels stay sharp (set on load) */
  .pv-img.z img { width: auto; height: auto; }                                   /* 1:1 */
  .pv-cover { position: absolute; inset: 0; cursor: zoom-in; }
  .pv-tile.focus .pv-cover { display: none; }
  .pv-empty { margin: auto; color: var(--d-muted); text-align: center; padding: 40px 20px; max-width: 520px; line-height: 1.5; }
  .pv-empty code { background: color-mix(in oklab, var(--d-accent) 14%, transparent); padding: 2px 10px; border-radius: var(--d-r-pill); font-size: 13px; }
  .pv-bad { margin: auto; color: var(--d-muted); padding: 20px; text-align: center; }
  @keyframes pv-drift { to { transform: translate3d(2%, -2%, 0) scale(1.06); } }
  @keyframes pv-open { from { opacity: 0; transform: translateY(14px) scale(.985); } to { opacity: 1; transform: none; } }
  @keyframes pv-enter { from { opacity: 0; transform: translateY(14px) scale(.97); } to { opacity: 1; transform: none; } }
  @keyframes pv-flash { 0% { box-shadow: 0 0 0 0 color-mix(in oklab, var(--d-accent) 55%, transparent), var(--d-shadow); } 100% { box-shadow: 0 0 0 14px transparent, var(--d-shadow); } }
  @media (prefers-reduced-motion: reduce) { #previewView, #previewView *, #previewView::before { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; } }
  @media (max-width: 820px) {
    #previewView { padding: 12px; gap: 10px; }
    .pv-grid, .pv-grid[data-n] { grid-template-columns: minmax(0, 1fr); grid-auto-rows: minmax(60vh, 1fr); overflow-y: auto; }
  }`;
  document.head.appendChild(css);

  const main = document.createElement('main');
  main.id = 'previewView';
  document.body.appendChild(main);

  // ---- data ----
  const mockData = () => {
    const now = Date.now() / 1000;
    const svg = c => 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" shape-rendering="crispEdges"><rect width="16" height="16" fill="${c}" opacity=".0"/><rect x="2" y="2" width="12" height="12" fill="${c}"/><rect x="5" y="5" width="3" height="3" fill="#fff"/><rect x="9" y="9" width="3" height="3" fill="#000"/></svg>`);
    const page = t => 'data:text/html,' + encodeURIComponent(`<body style="font:16px system-ui;display:grid;place-items:center;height:100vh;margin:0;background:linear-gradient(135deg,#6a5acd,#00a884);color:#fff"><div style="text-align:center"><h1>${t}</h1><p>mock page, mtime ${Math.round(Date.now() / 1000)}</p></div></body>`);
    return {v: 1, previews: [{agent: 'UI', kind: 'html', src: page('UI panel'), title: 'panel.html', mtime: now - 20, at: now - 900},
      {agent: 'VOXEL', kind: 'html', src: page('Voxel office'), title: 'office.html', mtime: now - 5, at: now - 800},
      {agent: 'CORE', kind: 'image', src: svg('#e0653a'), title: 'texture.svg', mtime: now - 60, at: now - 700},
      {agent: 'SEARCHER', kind: 'image', src: svg('#2f6fc4'), title: 'icon.svg', mtime: now - 90, at: now - 600}].slice(0, Number(new URLSearchParams(location.search).get('n')) || 4)};
  };
  async function load(force) {
    try {
      let d;
      if (MOCK) d = PV.mock || (PV.mock = mockData());
      else { const r = await fetch('preview.json', {cache: 'no-store'}); if (!r.ok) throw new Error('HTTP ' + r.status); d = await r.json(); }
      PV.err = '';
      const h = JSON.stringify((d.previews || []).map(p => [p.agent, p.kind, p.src, p.mtime]));
      if (!force && h === PV.hash && PV.data) return;
      PV.hash = h; PV.data = d;
    } catch (e) { PV.err = String(e); }
    sync();
  }

  // ---- tiles ----
  const SAFE = /^(preview\/[^?#]*|https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d+)?([\/?#][^]*)?|data:(text\/html|image\/[a-z+.-]+)[,;][^]*)$/i;   // the server's own route or a local server (data: only in the mock)
  const withV = (src, p) => (p.kind === 'url' || /^data:/i.test(src)) ? src : src + (src.includes('?') ? '&' : '?') + 'v=' + encodeURIComponent(p.mtime);
  const hue = n => [...String(n)].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);   // agent color: a hue 0-360 for the token recipe
  const ago = ts => {
    const s = Math.max(0, Date.now() / 1000 - ts);
    return s < 90 ? I18N.text('previewv.agoNow') : s < 5400 ? I18N.text('previewv.agoMin', {n: Math.round(s / 60)}) : I18N.text('previewv.agoHour', {n: Math.round(s / 3600)});
  };
  function bodyHtml(p, st) {
    if (p.missing) return `<div class="pv-bad">${esc(I18N.text('previewv.missing'))}</div>`;
    if (!SAFE.test(String(p.src || '')) || (/^data:/i.test(p.src) && !MOCK)) return `<div class="pv-bad">${esc(I18N.text('previewv.blocked'))}</div>`;
    const src = esc(withV(p.src, p));
    if (p.kind === 'image') return `<div class="pv-img${st.z ? ' z' : ''}"><img alt="" src="${src}" onload="this.style.imageRendering = this.naturalWidth <= 512 ? 'pixelated' : 'auto'"></div>`;
    if (p.kind === 'video') return `<video src="${src}" autoplay loop muted playsinline controls></video>`;
    if (p.kind === 'audio') return `<audio src="${src}" controls muted></audio>`;
    // a page of the server's own route runs without its own origin (no cookies, no storage); a local server of the agent has its own origin already
    return `<iframe src="${src}" sandbox="allow-scripts${p.kind === 'url' ? ' allow-same-origin allow-forms' : ''}" referrerpolicy="no-referrer" title="${esc(p.agent)}"></iframe>`;
  }
  function tileHtml(p, st) {
    const z = p.kind === 'image' ? `<button class="pv-ic${st.z ? ' on' : ''}" data-pv="zoom" title="${esc(I18N.text('previewv.zoom'))}">${IC.zoom}</button>` : '';
    const snd = p.kind === 'video' || p.kind === 'audio' ? `<button class="pv-ic${st.snd ? ' on' : ''}" data-pv="snd" title="${esc(I18N.text('previewv.sound'))}">${st.snd ? IC.on : IC.off}</button>` : '';
    const tools = p.kind === 'audio' || p.missing ? '' : `<button class="pv-ic${st.lens ? ' on' : ''}" data-pv="lens" title="${esc(I18N.text('previewv.lensTip'))}">${IC.lens}</button>`
      + `<button class="pv-ic" data-pv="snap" title="${esc(I18N.text('previewv.snapTip'))}">${IC.snap}</button>`;
    return `<div class="pv-head" data-pv="focus" title="${esc(I18N.text('previewv.focusTip'))}"><span class="pv-av" style="--h:${hue(p.agent)}">${esc(String(p.agent).charAt(0).toUpperCase())}</span><span class="pv-name">${esc(p.agent)}</span>`
      + `<span class="pv-file">${esc(p.title || '')}</span><span class="pv-sub" data-ago>${esc(ago(p.mtime))}</span>${z}${snd}${tools}`
      + `<button class="pv-ic" data-pv="reload" title="${esc(I18N.text('previewv.reload'))}">${IC.reload}</button><a class="pv-ic" data-pv="out" target="_blank" rel="noopener noreferrer" href="${SAFE.test(String(p.src || '')) && !/^data:/i.test(p.src) ? esc(p.src) : '#'}" title="${esc(I18N.text('previewv.open'))}">${IC.out}</a></div>`
      + `<div class="pv-body">${bodyHtml(p, st)}<div class="pv-cover" data-pv="focus"></div></div>`;
  }
  function sync() {
    if (!PV.open) return;
    if (!main.querySelector('#pvGrid')) { shell(); return; }
    const list = (PV.data && PV.data.previews) || [], grid = $('pvGrid');
    const names = new Set(list.map(p => p.agent));
    for (const [n, t] of PV.tiles) if (!names.has(n)) { t.el.remove(); PV.tiles.delete(n); if (PV.focus === n) PV.focus = null; }
    for (const p of list) {
      let t = PV.tiles.get(p.agent);
      if (!t) { t = {el: document.createElement('div'), z: false, snd: false, key: ''}; t.el.className = 'pv-tile'; t.el.dataset.agent = p.agent; grid.appendChild(t.el); PV.tiles.set(p.agent, t); }
      const key = p.kind + '|' + p.src + '|' + p.mtime + '|' + (p.missing ? 1 : 0);
      if (t.key !== key) {
        const again = !!t.p; t.p = p; t.key = key; t.el.innerHTML = tileHtml(p, t); applySound(t);
        if (t.lens && window.previewStudio) window.previewStudio.lens(t.el, p, true);       // the lens survives a live reload
        if (again) { t.el.classList.remove('fresh'); void t.el.offsetWidth; t.el.classList.add('fresh'); }   // a live reload: the ring flashes once
      }
      else { const a = t.el.querySelector('[data-ago]'); if (a) a.textContent = ago(p.mtime); }
    }
    grid.dataset.n = Math.min(5, Math.max(1, list.length));
    grid.classList.toggle('focus', !!PV.focus);
    for (const [n, t] of PV.tiles) t.el.classList.toggle('focus', n === PV.focus);
    const cnt = main.querySelector('.pv-count'); if (cnt) cnt.textContent = I18N.text('previewv.count', {n: list.length});
    const em = $('pvEmpty'); if (em) em.style.display = list.length ? 'none' : '';
    grid.style.display = list.length ? '' : 'none';
    strip();
  }
  function applySound(t) {            // muted unless the user turns a tile's sound on
    t.el.querySelectorAll('video,audio').forEach(m => { m.muted = !t.snd; });
  }
  function strip() {                  // in focus: a chip per agent to jump to
    const el = $('pvStrip'); if (!el) return;
    const names = ((PV.data && PV.data.previews) || []).map(p => p.agent);
    el.innerHTML = PV.focus ? names.map(n => `<button class="pv-pill${n === PV.focus ? ' on' : ''}" data-chip="${esc(n)}">${esc(n)}</button>`).join('')
      + `<button class="pv-pill" data-pv="grid">${esc(I18N.text('previewv.grid'))}</button>` : '';
  }
  function shell() {
    main.innerHTML = `<div class="pv-top"><button class="pv-logo" data-close="1" title="${esc(I18N.text('previewv.back'))}">${IC.view}</button><span class="pv-title">${esc(I18N.text('previewv.title'))}</span><span class="esc-hint" title="${esc(I18N.text('view.esc_title'))}">${esc(I18N.text('view.esc'))}</span>`
      + `<span id="pvStrip" class="pv-top" style="gap:8px"></span><span class="pv-sp"></span><span class="pv-sub pv-count"></span></div>`
      + (PV.err && !PV.data ? `<div class="pv-empty">${esc(I18N.text('previewv.loadErr', {why: PV.err}))}</div>` : `<div class="pv-empty" id="pvEmpty">${esc(I18N.text('previewv.empty'))}<br><br><code>chat.py preview PATH --as NAME</code></div>`)
      + `<div class="pv-grid" id="pvGrid" data-n="1"></div>`;
    PV.tiles = new Map();
    sync();
  }

  // ---- events ----
  main.addEventListener('click', e => {
    const chip = e.target.closest('[data-chip]');
    if (chip) { PV.focus = chip.dataset.chip; sync(); return; }
    const t = e.target.closest('[data-close],[data-pv]');
    if (!t) return;
    if (t.dataset.close) return open(false);
    const tile = t.closest('.pv-tile'), st = tile && PV.tiles.get(tile.dataset.agent), a = t.dataset.pv;
    if (a === 'grid') { PV.focus = null; sync(); }
    else if (a === 'focus' && tile) { PV.focus = PV.focus === tile.dataset.agent ? null : tile.dataset.agent; sync(); }
    else if (a === 'reload' && st) { st.key = ''; sync(); }
    else if (a === 'zoom' && st) { st.z = !st.z; st.key = ''; sync(); }
    else if (a === 'lens' && st && window.previewStudio) {
      st.lens = !st.lens; t.classList.toggle('on', st.lens);
      window.previewStudio.lens(st.el, st.p, st.lens).then(ok => { if (!ok && st.lens) { st.lens = false; t.classList.remove('on'); } });
    }
    else if (a === 'snap' && st && window.previewStudio) window.previewStudio.snap(st.el, st.p, t);
    else if (a === 'snd' && st) { st.snd = !st.snd; st.el.querySelector('[data-pv=snd]').innerHTML = st.snd ? IC.on : IC.off; st.el.querySelector('[data-pv=snd]').classList.toggle('on', st.snd); applySound(st); }
  });
  addEventListener('keydown', e => {
    if (!PV.open) return;
    if (window.previewStudio && window.previewStudio.key(e)) { e.preventDefault(); return; }
    if (e.key !== 'Escape') return;
    if (PV.focus) { PV.focus = null; sync(); } else open(false);
  });

  function open(on) {
    PV.open = !!on;
    if (!PV.open && window.previewStudio) window.previewStudio.stop();   // the tab capture ends with the view
    document.body.classList.toggle('pv-open', PV.open);
    btn.classList.toggle('on', PV.open);
    const u = new URL(location.href);
    if (PV.open) u.searchParams.set('view', 'preview'); else if (u.searchParams.get('view') === 'preview') u.searchParams.delete('view');
    history.replaceState(null, '', u);
    if (PV.open) { shell(); load(true); }
  }
  const btn = document.createElement('button');
  btn.className = 'icon-btn'; btn.id = 'previewBtn'; btn.innerHTML = IC.view;
  btn.addEventListener('click', () => open(!PV.open));
  const ob = document.getElementById('officeBtn');
  if (ob) ob.insertAdjacentElement('beforebegin', btn);
  window.previewView = {open, toggle: () => open(!PV.open), tiles: () => [...PV.tiles.keys()]};
  (typeof I18N_READY !== 'undefined' ? I18N_READY : Promise.resolve()).then(() => {
    try { btn.title = I18N.text('previewv.btn'); } catch (e) {}
    if (new URLSearchParams(location.search).get('view') === 'preview') open(true);
  });
  setInterval(() => { if (PV.open && !document.hidden) load(); }, 3000);
})();
