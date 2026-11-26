/* The frame studio of the Previews view (1.3.5): a lens, a frame picker, a pen, and the chosen frames sent to the chat.
   Frames come from the tile itself. A picture is one frame. A video is paused and stepped by seeking, 15 frames before and 15
   after the current one (exact, nothing kept in memory while it plays). A page (a sandboxed iframe or an agent's local server)
   cannot be read by the viewer, so it is filmed through the browser's own tab capture (getDisplayMedia: the user picks this tab
   once, the capture stops when the Previews view closes) for 2 s at 15 fps, cropped to the tile. "Sharper" looks at the frame
   before and the frame after, keeps the sharpest of the three (variance of the Laplacian) and sharpens it a little (unsharp
   mask). Pen and highlighter draw on each frame in seven colours; Send puts the chosen frames, drawings included, among the
   chat's attachments as PNG (the composer takes six). Loaded before preview-view.js, which calls window.previewStudio. */
(() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const COLORS = ['#ff3b30', '#ffcc00', '#34c759', '#0a84ff', '#bf5af2', '#ffffff', '#111111'];
  const LENS = 180, PAGE_FRAMES = 30, PAGE_FPS = 15, VIDEO_SIDE = 15, VIDEO_FPS = 30, SEND_MAX = 6;
  const S = {cap: null, capVideo: null, frames: [], cur: 0, sel: new Set(), tool: 'pen', color: COLORS[0], zoom: 3, el: null, busy: false, agent: ''};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const view = () => document.getElementById('previewView');

  const css = document.createElement('style');
  css.textContent = `
  #previewView > .ps { position: absolute; inset: 0; z-index: 5; display: flex; flex-direction: column; gap: 10px; padding: 14px 18px 16px; background: var(--d-bg); box-sizing: border-box; }
  .ps-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .ps-title { font-weight: 650; font-size: 16px; margin-right: 6px; }
  .ps-sep { width: 1px; height: 24px; background: var(--d-line); margin: 0 4px; }
  .ps-b { border: 1px solid var(--d-line); background: var(--d-card); color: var(--d-text); border-radius: var(--d-r-pill); padding: 6px 13px; cursor: pointer; font: inherit; font-size: 13.5px; font-weight: 550; }
  .ps-b:hover { border-color: color-mix(in oklab, var(--d-accent) 50%, var(--d-line)); }
  .ps-b.on { background: color-mix(in oklab, var(--d-accent) 16%, var(--d-card)); color: var(--d-accent); border-color: var(--d-accent); }
  .ps-b.go { background: var(--d-grad); color: #fff; border-color: transparent; }
  .ps-b:disabled { opacity: .45; cursor: default; }
  .ps-b:focus-visible, .ps-sw:focus-visible, .ps-th:focus-visible { outline: 2px solid var(--d-accent); outline-offset: 2px; }
  .ps-sw { width: 24px; height: 24px; border-radius: 50%; border: 2px solid var(--d-line); cursor: pointer; padding: 0; }
  .ps-sw.on { border-color: var(--d-text); transform: scale(1.15); }
  .ps-sp { flex: 1; }
  .ps-stage { flex: 1; min-height: 0; position: relative; display: grid; place-items: center; border-radius: var(--d-r-lg); overflow: hidden;
    background-color: var(--pv-chk2); background-image: conic-gradient(var(--pv-chk1) 25%, transparent 0 50%, var(--pv-chk1) 0 75%, transparent 0); background-size: 20px 20px; }
  .ps-cv { touch-action: none; box-shadow: var(--d-shadow); }
  .ps-cv.pen, .ps-cv.hl { cursor: crosshair; } .ps-cv.lens { cursor: none; }
  .ps-note { position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%); background: var(--d-card); border: 1px solid var(--d-line); border-radius: var(--d-r-pill);
    padding: 5px 14px; font-size: 13px; color: var(--d-text); pointer-events: none; opacity: 0; transition: opacity .25s; max-width: 90%; text-align: center; }
  .ps-note.show { opacity: 1; }
  .ps-strip { display: flex; gap: 8px; overflow-x: auto; padding: 4px 2px 6px; flex: none; }
  .ps-th { position: relative; flex: none; border: 2px solid transparent; border-radius: 10px; padding: 0; background: var(--d-card2); cursor: pointer; overflow: hidden; }
  .ps-th canvas { display: block; height: 72px; }
  .ps-th.cur { border-color: var(--d-accent); }
  .ps-th span { position: absolute; left: 4px; bottom: 3px; font-size: 10.5px; color: #fff; text-shadow: 0 1px 2px #000; }
  .ps-th i { position: absolute; right: 4px; top: 4px; width: 18px; height: 18px; border-radius: 50%; border: 2px solid #fff; background: rgba(0,0,0,.35); font-style: normal; font-size: 11px; line-height: 14px; color: #fff; text-align: center; }
  .ps-th.sel i { background: var(--d-accent); border-color: var(--d-accent); }
  .ps-th b { position: absolute; left: 4px; top: 3px; font-size: 12px; }
  .ps-lens { position: fixed; z-index: 90; width: ${LENS}px; height: ${LENS}px; border-radius: 50%; pointer-events: none; display: none;
    border: 3px solid var(--d-accent); box-shadow: 0 10px 30px rgba(0,0,0,.45); background: #000; image-rendering: pixelated; }
  .pv-lensov { position: absolute; inset: 0; cursor: none; z-index: 2; }
  .pv-rec { color: #ff3b30 !important; animation: ps-blink 1s steps(2) infinite; }
  @keyframes ps-blink { 50% { opacity: .35; } }
  @media (max-width: 820px) { .ps { padding: 10px; } .ps-th canvas { height: 56px; } }`;
  document.head.appendChild(css);

  // ---- the lens: a round zoom of what is under the pointer, drawn from a source mapped to the screen ----
  const lensCv = document.createElement('canvas');
  lensCv.className = 'ps-lens';
  document.body.appendChild(lensCv);
  const contain = (r, nw, nh) => { const s = Math.min(r.width / nw, r.height / nh), w = nw * s, h = nh * s; return {x: r.left + (r.width - w) / 2, y: r.top + (r.height - h) / 2, w, h}; };
  function drawLens(src, cx, cy) {         // src: {img, map(x, y) -> [sx, sy], k: source pixels per screen pixel}
    if (!src) { lensCv.style.display = 'none'; return; }
    const dpr = devicePixelRatio || 1, side = LENS * dpr;
    if (lensCv.width !== side) { lensCv.width = side; lensCv.height = side; }
    const [sx, sy] = src.map(cx, cy), w = LENS / S.zoom * src.k, ctx = lensCv.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, side, side);
    try { ctx.drawImage(src.img, sx - w / 2, sy - w / 2, w, w, 0, 0, side, side); } catch (e) {}
    ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = dpr;
    ctx.beginPath(); ctx.moveTo(side / 2 - 8 * dpr, side / 2); ctx.lineTo(side / 2 + 8 * dpr, side / 2); ctx.moveTo(side / 2, side / 2 - 8 * dpr); ctx.lineTo(side / 2, side / 2 + 8 * dpr); ctx.stroke();
    // beside the pointer, never on it: a tab capture would film the lens itself
    const x = cx + 28 + LENS > innerWidth ? cx - 28 - LENS : cx + 28, y = Math.max(6, Math.min(innerHeight - LENS - 6, cy - LENS - 20 < 0 ? cy + 28 : cy - LENS - 20));
    Object.assign(lensCv.style, {display: 'block', left: x + 'px', top: y + 'px'});
  }
  const hideLens = () => { lensCv.style.display = 'none'; };
  function wheelZoom(e) { e.preventDefault(); S.zoom = Math.max(1.5, Math.min(10, S.zoom * (e.deltaY < 0 ? 1.2 : 1 / 1.2))); }

  // ---- the tab capture, for pages: asked once, stopped when the Previews view closes ----
  async function startCapture() {
    if (S.capVideo) return S.capVideo;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) throw new Error(I18N.text('previewv.capNo'));
    const stream = await navigator.mediaDevices.getDisplayMedia({video: {frameRate: 30}, audio: false, preferCurrentTab: true, selfBrowserSurface: 'include', surfaceSwitching: 'exclude'});
    const track = stream.getVideoTracks()[0];
    track.addEventListener('ended', stop);
    if ((track.getSettings() || {}).displaySurface && track.getSettings().displaySurface !== 'browser') { stream.getTracks().forEach(t => t.stop()); throw new Error(I18N.text('previewv.capOther')); }
    const v = document.createElement('video');
    v.muted = true; v.playsInline = true; v.srcObject = stream;
    await v.play();
    for (let i = 0; i < 40 && !v.videoWidth; i++) await sleep(25);
    S.cap = stream; S.capVideo = v;
    return v;
  }
  function stop() {
    if (S.cap) S.cap.getTracks().forEach(t => t.stop());
    S.cap = null; S.capVideo = null; hideLens();
  }
  function capBox(el) {                      // the element's box inside the captured tab (its frame is the viewport, in device pixels)
    const r = el.getBoundingClientRect(), v = S.capVideo, kx = v.videoWidth / innerWidth, ky = v.videoHeight / innerHeight;
    return {x: Math.max(0, r.left * kx), y: Math.max(0, r.top * ky), w: Math.min(v.videoWidth, r.width * kx), h: Math.min(v.videoHeight, r.height * ky)};
  }

  // ---- the live lens on a tile ----
  function liveSource(tile, kind) {
    const body = tile.querySelector('.pv-body');
    if (!body) return null;
    if (kind === 'image' || kind === 'video') {
      const el = body.querySelector(kind === 'image' ? 'img' : 'video');
      const nw = el && (el.naturalWidth || el.videoWidth), nh = el && (el.naturalHeight || el.videoHeight);
      if (!nw || !nh) return null;
      const r = contain(el.getBoundingClientRect(), nw, nh);
      return {img: el, map: (x, y) => [(x - r.x) * nw / r.w, (y - r.y) * nh / r.h], k: nw / r.w};
    }
    const v = S.capVideo;
    if (!v || !v.videoWidth) return null;
    const kx = v.videoWidth / innerWidth, ky = v.videoHeight / innerHeight;
    return {img: v, map: (x, y) => [x * kx, y * ky], k: kx};
  }
  async function lens(tile, p, on) {
    const body = tile.querySelector('.pv-body');
    let ov = body && body.querySelector('.pv-lensov');
    if (!on) { if (ov) ov.remove(); hideLens(); return true; }
    if (!body || p.kind === 'audio') return false;
    if (p.kind !== 'image' && p.kind !== 'video') {
      try { await startCapture(); } catch (e) { toast(String(e.message || e)); return false; }
    }
    if (!ov) {                               // above the iframe too: a page would swallow the pointer otherwise
      ov = document.createElement('div');
      ov.className = 'pv-lensov';
      body.appendChild(ov);
      ov.addEventListener('pointermove', e => drawLens(liveSource(tile, p.kind), e.clientX, e.clientY));
      ov.addEventListener('pointerleave', hideLens);
      ov.addEventListener('wheel', e => { wheelZoom(e); drawLens(liveSource(tile, p.kind), e.clientX, e.clientY); }, {passive: false});
    }
    return true;
  }

  // ---- frames ----
  const seek = (v, t) => new Promise(res => {          // always a real seek: right after a loop currentTime says 0 while the last frame still shows
    const done = () => { clearTimeout(tm); res(); }, tm = setTimeout(done, 1500);
    v.addEventListener('seeked', done, {once: true});
    v.currentTime = t;
  });
  async function grabVideo(v) {
    v.pause();
    const t0 = v.currentTime, out = [], dur = isFinite(v.duration) ? v.duration : t0, base = Math.floor(t0 * VIDEO_FPS);
    for (let k = -VIDEO_SIDE; k <= VIDEO_SIDE; k++) {
      const t = (base + k + .5) / VIDEO_FPS;               // the middle of a frame: a seek on its edge lands on the neighbour
      if (t < 0 || t > dur) continue;
      await seek(v, t);
      out.push({bmp: await createImageBitmap(v), label: t.toFixed(2) + ' s', mid: k === 0});
    }
    await seek(v, t0);
    return out;
  }
  async function grabPage(body, btn) {
    const v = await startCapture(), out = [], step = 1000 / PAGE_FPS, t0 = performance.now();
    if (btn) btn.classList.add('pv-rec');
    try {
      for (let i = 0; i < PAGE_FRAMES; i++) {
        const wait = t0 + i * step - performance.now();
        if (wait > 0) await sleep(wait);
        const b = capBox(body);
        if (b.w < 2 || b.h < 2) break;
        out.push({bmp: await createImageBitmap(v, b.x, b.y, b.w, b.h), label: (i * step / 1000).toFixed(2) + ' s', mid: i === PAGE_FRAMES / 2});
      }
    } finally { if (btn) btn.classList.remove('pv-rec'); }
    return out;
  }
  async function snap(tile, p, btn) {
    if (S.busy || S.el) return;
    const body = tile.querySelector('.pv-body');
    if (!body || p.kind === 'audio') return;
    S.busy = true;
    try {
      let frames;
      if (p.kind === 'image') { const img = body.querySelector('img'); frames = [{bmp: await createImageBitmap(img), label: p.title || '', mid: true}]; }
      else if (p.kind === 'video') frames = await grabVideo(body.querySelector('video'));
      else frames = await grabPage(body, btn);
      if (!frames.length) throw new Error(I18N.text('previewv.noFrames'));
      openStudio(frames, p.agent);
    } catch (e) { toast(String(e.message || e)); }
    S.busy = false;
  }

  // ---- sharper: the sharpest of the frame and its neighbours, then a light unsharp mask ----
  function canvasOf(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
  function sharpness(bmp) {                 // variance of the Laplacian on a grey copy at most 512 px wide
    const s = Math.min(1, 512 / Math.max(bmp.width, bmp.height)), w = Math.max(8, Math.round(bmp.width * s)), h = Math.max(8, Math.round(bmp.height * s));
    const c = canvasOf(w, h), ctx = c.getContext('2d', {willReadFrequently: true});
    ctx.drawImage(bmp, 0, 0, w, h);
    const d = ctx.getImageData(0, 0, w, h).data, g = new Float32Array(w * h);
    for (let i = 0; i < g.length; i++) g[i] = d[i * 4] * .299 + d[i * 4 + 1] * .587 + d[i * 4 + 2] * .114;
    let sum = 0, sq = 0, n = 0;
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const i = y * w + x, l = 4 * g[i] - g[i - 1] - g[i + 1] - g[i - w] - g[i + w];
      sum += l; sq += l * l; n++;
    }
    return n ? sq / n - (sum / n) ** 2 : 0;
  }
  async function unsharp(bmp, amount = .35) {
    const w = bmp.width, h = bmp.height, c = canvasOf(w, h), ctx = c.getContext('2d', {willReadFrequently: true});
    ctx.drawImage(bmp, 0, 0);
    const src = ctx.getImageData(0, 0, w, h), out = ctx.createImageData(w, h), a = src.data, o = out.data, row = w * 4;
    o.set(a);
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const i = y * row + x * 4;
      for (let ch = 0; ch < 3; ch++) {
        const j = i + ch;
        o[j] = a[j] + amount * (4 * a[j] - a[j - 4] - a[j + 4] - a[j - row] - a[j + row]);   // Uint8ClampedArray clamps
      }
    }
    ctx.putImageData(out, 0, 0);
    return createImageBitmap(c);
  }
  async function sharper() {
    const i = S.cur, near = [i - 1, i, i + 1].filter(k => k >= 0 && k < S.frames.length && !S.frames[k].still);
    if (!near.length) return;
    const score = near.map(k => ({k, v: sharpness(S.frames[k].bmp)}));
    const best = score.reduce((a, b) => b.v > a.v ? b : a), mine = score.find(s => s.k === i).v || 1;
    const f = S.frames[best.k];
    if (!f.fixed) { const old = f.bmp; f.bmp = await unsharp(old); old.close(); f.fixed = true; }
    const gain = Math.round((best.v / mine - 1) * 100);
    toast(best.k === i ? I18N.text('previewv.sharpSame') : best.k < i ? I18N.text('previewv.sharpPrev', {n: gain}) : I18N.text('previewv.sharpNext', {n: gain}));
    S.cur = best.k;
    paint(); strip();
  }

  // ---- the studio ----
  function openStudio(frames, agent) {
    S.frames = frames.map(f => ({...f, strokes: []}));
    S.cur = Math.max(0, S.frames.findIndex(f => f.mid));
    S.sel = new Set(); S.agent = agent;
    const el = document.createElement('div');
    el.className = 'ps';
    el.innerHTML = `<div class="ps-bar"><span class="ps-title">${esc(I18N.text('previewv.studioTitle', {name: agent}))}</span>`
      + `<button class="ps-b" data-t="lens" title="${esc(I18N.text('previewv.lensTip'))}">🔍 ${esc(I18N.text('previewv.lens'))}</button>`
      + `<button class="ps-b on" data-t="pen">✏️ ${esc(I18N.text('previewv.pen'))}</button><button class="ps-b" data-t="hl">🖍️ ${esc(I18N.text('previewv.hl'))}</button>`
      + COLORS.map((c, i) => `<button class="ps-sw${i ? '' : ' on'}" data-c="${c}" style="background:${c}" title="${c}"></button>`).join('')
      + `<span class="ps-sep"></span><button class="ps-b" data-a="undo" title="Ctrl+Z">↶ ${esc(I18N.text('previewv.undo'))}</button><button class="ps-b" data-a="clear">${esc(I18N.text('previewv.clear'))}</button>`
      + `<button class="ps-b" data-a="sharp" title="${esc(I18N.text('previewv.sharpTip'))}">✨ ${esc(I18N.text('previewv.sharp'))}</button>`
      + `<span class="ps-sp"></span><button class="ps-b go" data-a="send"></button><button class="ps-b" data-a="close" title="Esc">${esc(I18N.text('previewv.close'))}</button></div>`
      + `<div class="ps-stage"><canvas class="ps-cv pen"></canvas><div class="ps-note"></div></div>`
      + `<div class="ps-strip" title="${esc(I18N.text('previewv.selTip'))}"></div>`;
    view().appendChild(el);
    S.el = el; S.tool = 'pen';
    const cv = el.querySelector('.ps-cv');
    let drawing = null;
    const toFrame = e => { const r = cv.getBoundingClientRect(), f = S.frames[S.cur]; return [(e.clientX - r.left) * f.bmp.width / r.width, (e.clientY - r.top) * f.bmp.height / r.height]; };
    const kOf = () => S.frames[S.cur].bmp.width / cv.getBoundingClientRect().width;
    cv.addEventListener('pointerdown', e => {
      if (S.tool === 'lens') return;
      cv.setPointerCapture(e.pointerId);
      drawing = {tool: S.tool, color: S.color, w: (S.tool === 'hl' ? 18 : 3.5) * kOf(), pts: [toFrame(e)]};
      S.frames[S.cur].strokes.push(drawing); paint();
    });
    cv.addEventListener('pointermove', e => {
      if (S.tool === 'lens') { const r = cv.getBoundingClientRect(), f = S.frames[S.cur]; drawLens({img: cv, map: (x, y) => [(x - r.left) * cv.width / r.width, (y - r.top) * cv.height / r.height], k: f.bmp.width / r.width}, e.clientX, e.clientY); return; }
      if (drawing) { drawing.pts.push(toFrame(e)); paint(); }
    });
    const end = () => { drawing = null; };
    cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
    cv.addEventListener('pointerleave', hideLens);
    cv.addEventListener('wheel', e => { if (S.tool === 'lens') wheelZoom(e); }, {passive: false});
    el.addEventListener('click', onClick);
    new ResizeObserver(() => S.el && paint()).observe(el.querySelector('.ps-stage'));
    paint(); strip();
  }
  function closeStudio() {
    if (!S.el) return;
    S.el.remove(); S.el = null; hideLens();
    S.frames.forEach(f => f.bmp.close && f.bmp.close());
    S.frames = []; S.sel.clear();
  }
  function compose(f, ctx) {
    ctx.drawImage(f.bmp, 0, 0);
    for (const s of f.strokes) {
      ctx.save();
      ctx.globalAlpha = s.tool === 'hl' ? .38 : 1;
      ctx.strokeStyle = s.color; ctx.lineWidth = s.w; ctx.lineJoin = 'round'; ctx.lineCap = s.tool === 'hl' ? 'square' : 'round';
      ctx.beginPath();
      s.pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
      if (s.pts.length === 1) ctx.lineTo(s.pts[0][0] + .01, s.pts[0][1]);
      ctx.stroke(); ctx.restore();
    }
  }
  function paint() {
    const el = S.el, f = S.frames[S.cur];
    if (!el || !f) return;
    const cv = el.querySelector('.ps-cv'), stage = el.querySelector('.ps-stage').getBoundingClientRect();
    if (cv.width !== f.bmp.width || cv.height !== f.bmp.height) { cv.width = f.bmp.width; cv.height = f.bmp.height; }
    const s = Math.min((stage.width - 24) / f.bmp.width, (stage.height - 24) / f.bmp.height, 4);
    cv.style.width = Math.max(1, f.bmp.width * s) + 'px'; cv.style.height = Math.max(1, f.bmp.height * s) + 'px';
    cv.style.imageRendering = s > 1.5 ? 'pixelated' : 'auto';
    compose(f, cv.getContext('2d'));
    const n = Math.min(S.sel.size || 1, SEND_MAX), send = el.querySelector('[data-a=send]');
    send.textContent = '💬 ' + I18N.text('previewv.send', {n});
  }
  function strip() {
    const box = S.el && S.el.querySelector('.ps-strip');
    if (!box) return;
    if (box.children.length !== S.frames.length) {
      box.innerHTML = S.frames.map((f, i) => `<button class="ps-th" data-f="${i}"><canvas></canvas><span>${esc(f.label)}</span><i>✓</i>${f.fixed ? '<b>✨</b>' : ''}</button>`).join('');
      [...box.children].forEach((b, i) => { const f = S.frames[i], c = b.querySelector('canvas'), h = 72 * (devicePixelRatio || 1); c.height = h; c.width = Math.max(1, Math.round(h * f.bmp.width / f.bmp.height)); c.style.width = (c.width / (devicePixelRatio || 1)) + 'px'; c.getContext('2d').drawImage(f.bmp, 0, 0, c.width, c.height); });
    }
    [...box.children].forEach((b, i) => {
      b.classList.toggle('cur', i === S.cur); b.classList.toggle('sel', S.sel.has(i));
      const f = S.frames[i];
      if (f.fixed && !b.querySelector('b')) { b.insertAdjacentHTML('beforeend', '<b>✨</b>'); const c = b.querySelector('canvas'); c.getContext('2d').drawImage(f.bmp, 0, 0, c.width, c.height); }
    });
    const cur = box.children[S.cur];
    if (cur) cur.scrollIntoView({block: 'nearest', inline: 'nearest'});
  }
  function setTool(t) {
    S.tool = t; hideLens();
    S.el.querySelectorAll('[data-t]').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    S.el.querySelector('.ps-cv').className = 'ps-cv ' + t;
  }
  async function sendFrames() {
    const ids = (S.sel.size ? [...S.sel].sort((a, b) => a - b) : [S.cur]).slice(0, SEND_MAX), files = [];
    for (const i of ids) {
      const f = S.frames[i], c = canvasOf(f.bmp.width, f.bmp.height);
      compose(f, c.getContext('2d'));
      const blob = await new Promise(r => c.toBlob(r, 'image/png'));
      if (blob) files.push(new File([blob], `${S.agent}-frame-${i + 1}.png`, {type: 'image/png'}));
    }
    if (!window.composerAddFiles) return toast(I18N.text('previewv.noComposer'));
    window.composerAddFiles(files);
    closeStudio();
    if (window.previewView) window.previewView.open(false);
    const box = document.getElementById('box');
    if (box) box.focus();
  }
  function onClick(e) {
    const th = e.target.closest('[data-f]');
    if (th) {
      const i = +th.dataset.f;
      if (e.target.closest('i') || e.ctrlKey || e.metaKey || e.shiftKey) { if (S.sel.has(i)) S.sel.delete(i); else S.sel.add(i); }
      else S.cur = i;
      paint(); strip(); return;
    }
    const b = e.target.closest('[data-t],[data-c],[data-a]');
    if (!b) return;
    if (b.dataset.t) setTool(b.dataset.t);
    else if (b.dataset.c) {
      S.color = b.dataset.c;
      S.el.querySelectorAll('[data-c]').forEach(x => x.classList.toggle('on', x === b));
      if (S.tool === 'lens') setTool('pen');
    }
    else if (b.dataset.a === 'undo') { S.frames[S.cur].strokes.pop(); paint(); }
    else if (b.dataset.a === 'clear') { S.frames[S.cur].strokes = []; paint(); }
    else if (b.dataset.a === 'sharp') { b.disabled = true; sharper().finally(() => { b.disabled = false; }); }
    else if (b.dataset.a === 'send') sendFrames().catch(e => toast(String(e.message || e)));   // a picture from another site taints the canvas
    else if (b.dataset.a === 'close') closeStudio();
  }
  function key(e) {                          // preview-view.js asks first: true when the studio took the key
    if (!S.el) return false;
    if (e.key === 'Escape') { closeStudio(); return true; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { S.frames[S.cur].strokes.pop(); paint(); return true; }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { S.cur = Math.max(0, Math.min(S.frames.length - 1, S.cur + (e.key === 'ArrowLeft' ? -1 : 1))); paint(); strip(); return true; }
    if (e.key === ' ' && !e.target.closest('button')) { if (S.sel.has(S.cur)) S.sel.delete(S.cur); else S.sel.add(S.cur); paint(); strip(); return true; }
    return false;
  }
  function toast(text) {
    const host = (S.el && S.el.querySelector('.ps-stage')) || view();
    let n = host && host.querySelector(':scope > .ps-note');
    if (!host) return;
    if (!n) { n = document.createElement('div'); n.className = 'ps-note'; n.style.position = 'absolute'; n.style.zIndex = 6; host.appendChild(n); }
    n.textContent = text; n.classList.add('show');
    clearTimeout(n._t); n._t = setTimeout(() => n.classList.remove('show'), 4200);
  }

  window.previewStudio = {lens, snap, stop: () => { closeStudio(); stop(); }, key, isOpen: () => !!S.el,
    _test: {sharpness, contain, openStudio, state: S}};
})();
