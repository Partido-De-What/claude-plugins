/* The Spawn view (0.13): a full-window page of the viewer instead of cards in the chat. Three tabs: Keys, Models
   (the list on the left, the chosen model on the right: its strongest benchmarks first), Roles. Data from
   /spawn/state.json and /spawn/model.json, clicks to /spawn/do (spawn/panel.py). Opened by the 🛸 button or ?view=spawn;
   Esc or the 🛸 in its own bar goes back to the chat. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const SV = {open: false, tab: 'models', data: null, sel: null, model: null, q: '', area: '', replacing: null, form: false,
              busy: false, phoneDetail: false, more: '', cmp: null};
  try { Object.assign(SV, (({tab, sel}) => ({tab: tab || SV.tab, sel: sel || null}))(JSON.parse(localStorage.getItem('chatroom.spawnView') || '{}'))); } catch (e) {}
  const keep = () => { try { localStorage.setItem('chatroom.spawnView', JSON.stringify({tab: SV.tab, sel: SV.sel})); } catch (e) {} };

  const css = document.createElement('style');
  css.textContent = `
  #spawnView { --sv-bg: #f7f7f5; --sv-card: #ffffff; --sv-line: #e4e3df; --sv-text: #1d1d1b; --sv-mute: #6b6a65; --sv-acc: #185fa5;
    --sv-acc-bg: #e6f1fb; --sv-bar: #378add; --sv-good: #2f8f1f; --sv-good-bar: #3b9b17; --sv-maker: #b8740a; --sv-track: #ecebe7;
    position: fixed; inset: 0; z-index: 60; display: none; flex-direction: column; background: var(--sv-bg); color: var(--sv-text);
    font-size: 15px; padding: 22px 28px; gap: 16px; box-sizing: border-box; }
  :root[data-theme="dark"] #spawnView { --sv-bg: #1a1a19; --sv-card: #1f1f1e; --sv-line: #3a3a38; --sv-text: #eceae4; --sv-mute: #a9a79f;
    --sv-acc: #85b7eb; --sv-acc-bg: #0c447c; --sv-bar: #378add; --sv-good: #47b31c; --sv-good-bar: #2e9e12; --sv-maker: #e0a030; --sv-track: #2c2c2a; }
  body.sv-open #spawnView { display: flex; }
  .sv-top { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .sv-logo { font-size: 22px; cursor: pointer; background: none; border: 0; color: inherit; padding: 0 2px; }
  .sv-title { font-size: 21px; font-weight: 600; margin-right: 8px; }
  .sv-pill { border: 1px solid var(--sv-line); background: transparent; color: var(--sv-text); border-radius: 10px; padding: 7px 18px; cursor: pointer; font-size: 16px; }
  .sv-pill.on { background: var(--sv-acc-bg); color: var(--sv-acc); border-color: var(--sv-acc-bg); }
  .sv-sp { flex: 1; }
  .sv-upd { color: var(--sv-mute); font-size: 15px; display: flex; align-items: center; gap: 8px; }
  .sv-icon { background: none; border: 0; color: var(--sv-mute); cursor: pointer; font-size: 17px; padding: 2px 4px; }
  .sv-icon:hover { color: var(--sv-text); }
  .sv-main { flex: 1; min-height: 0; display: flex; gap: 20px; }
  .sv-card { background: var(--sv-card); border: 1px solid var(--sv-line); border-radius: 16px; min-height: 0; display: flex; flex-direction: column; }
  .sv-list { width: 400px; flex: none; padding: 16px; gap: 12px; }
  .sv-list input { width: 100%; box-sizing: border-box; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--sv-line); background: transparent; color: var(--sv-text); font-size: 16px; }
  .sv-chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .sv-chip { font-size: 14px; padding: 5px 14px; border-radius: 10px; border: 1px solid var(--sv-line); cursor: pointer; background: transparent; color: var(--sv-text); }
  .sv-chip.on { background: var(--sv-acc-bg); color: var(--sv-acc); border-color: var(--sv-acc-bg); }
  .sv-rows { overflow-y: auto; min-height: 0; flex: 1; margin: 0 -4px; padding: 0 4px; }
  .sv-row { padding: 12px 14px; border-bottom: 1px solid var(--sv-line); cursor: pointer; border-radius: 0; }
  .sv-row:hover:not(.on) { background: color-mix(in srgb, var(--sv-acc-bg) 35%, transparent); }
  .sv-row.on { background: var(--sv-acc-bg); color: var(--sv-acc); border-radius: 12px; border-bottom-color: transparent; }
  .sv-row .n { display: flex; justify-content: space-between; gap: 10px; font-size: 17px; }
  .sv-row.on .n { font-weight: 600; }
  .sv-row .aa { white-space: nowrap; color: var(--sv-mute); } .sv-row.on .aa { color: var(--sv-acc); font-weight: 600; }
  .sv-row .trk { height: 6px; border-radius: 3px; background: var(--sv-track); margin: 9px 0 8px; }
  .sv-row .trk i { display: block; height: 6px; border-radius: 3px; background: var(--sv-bar); }
  .sv-row .s { font-size: 14.5px; color: var(--sv-mute); margin-top: 3px; } .sv-row.on .s { color: var(--sv-acc); }
  .sv-detail { flex: 1; min-width: 0; padding: 22px 28px; overflow-y: auto; display: block; }
  .sv-h { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
  .sv-h h2 { margin: 0; font-size: 24px; font-weight: 600; }
  .sv-h .sub { color: var(--sv-mute); font-size: 16px; }
  .sv-btn { border: 1px solid var(--sv-line); background: transparent; color: var(--sv-text); border-radius: 10px; padding: 9px 20px; cursor: pointer; font-size: 16px; }
  .sv-btn:hover { border-color: var(--sv-acc); }
  .sv-btn.pri { background: var(--sv-acc-bg); color: var(--sv-acc); border-color: var(--sv-acc-bg); }
  .sv-btn.small { padding: 5px 12px; font-size: 14px; }
  .sv-strong { margin: 18px 0 8px; font-size: 17px; }
  .sv-lbl { color: var(--sv-mute); font-size: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--sv-line); }
  .sv-b { padding: 14px 0; border-bottom: 1px solid var(--sv-line); }
  .sv-b .top { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
  .sv-b .name { font-weight: 600; font-size: 17px; }
  .sv-b .rank { font-size: 17px; color: var(--sv-mute); white-space: nowrap; } .sv-b .rank.good { color: var(--sv-good); }
  .sv-b .what { font-size: 15.5px; margin: 4px 0 8px; }
  .sv-bar { display: flex; align-items: center; gap: 14px; }
  .sv-bar .t { flex: 1; height: 8px; border-radius: 4px; background: var(--sv-track); }
  .sv-bar .t i { display: block; height: 8px; border-radius: 4px; background: var(--sv-good-bar); }
  .sv-bar .t.maker i { background: var(--sv-bar); }
  .sv-src { font-size: 15px; color: var(--sv-mute); white-space: nowrap; } .sv-src.maker { color: var(--sv-maker); }
  .sv-src a { color: inherit; text-decoration: none; } .sv-src a:hover { text-decoration: underline; }
  .sv-links { margin-top: 16px; color: var(--sv-acc); font-size: 16px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .sv-links button { background: none; border: 0; color: inherit; font: inherit; cursor: pointer; padding: 0; }
  .sv-links button.on, .sv-links button:hover { text-decoration: underline; }
  .sv-links .dot { color: var(--sv-mute); }
  .sv-more { margin-top: 8px; }
  .sv-prof { margin: 14px 0 4px; font-size: 16px; line-height: 1.45; max-width: 760px; }
  .sv-prof .lvl { margin-top: 6px; font-weight: 600; } .sv-prof .mute, .sv-prof.mute { color: var(--sv-mute); font-weight: 400; }
  .sv-tag { display: inline-block; font-size: 13px; padding: 2px 10px; border-radius: 8px; margin-bottom: 6px; background: var(--sv-acc-bg); color: var(--sv-acc); }
  .sv-tag.bad { background: color-mix(in srgb, #e5484d 18%, transparent); color: #e5484d; }
  .sv-host .lim { color: var(--sv-mute); }
  .sv-host { display: flex; gap: 14px; font-size: 15px; padding: 9px 0; border-bottom: 1px solid var(--sv-line); flex-wrap: wrap; align-items: center; }
  .sv-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; background: var(--sv-mute); flex: none; }
  .sv-dot.ok { background: #3fb950; } .sv-dot.bad { background: #e5484d; } .sv-dot.warn { background: #e0a030; }
  .sv-form { margin-top: 16px; padding: 16px; border: 1px solid var(--sv-line); border-radius: 12px; display: grid; gap: 10px; max-width: 620px; }
  .sv-form input[type=text], .sv-form textarea, .sv-pad input, .sv-more select { padding: 9px 11px; border-radius: 10px; border: 1px solid var(--sv-line); background: transparent; color: var(--sv-text); font: inherit; }
  .sv-form label { font-size: 14px; color: var(--sv-mute); }
  .sv-banner { margin: 0 0 14px; padding: 12px 14px; border-radius: 12px; background: color-mix(in srgb, #e0a030 22%, transparent); display: flex; gap: 10px; align-items: center; }
  .sv-pad { padding: 22px 28px; overflow-y: auto; flex: 1; }
  .sv-prov { display: grid; grid-template-columns: 18px minmax(140px, 1fr) minmax(180px, 1.3fr) auto; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--sv-line); }
  .sv-prov .o { font-size: 14px; color: var(--sv-mute); } .sv-prov .o a { color: var(--sv-acc); }
  .sv-prov .act { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
  .sv-prov input { width: 190px; }
  .sv-role { display: grid; grid-template-columns: 18px 1fr auto; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--sv-line); align-items: center; }
  .sv-role .r1 { font-weight: 600; font-size: 17px; } .sv-role .r2 { font-size: 14.5px; color: var(--sv-mute); margin-top: 2px; }
  .sv-role.blink .sv-dot { animation: svBlink 1s steps(2) infinite; }
  @keyframes svBlink { 50% { opacity: .15; } }
  .sv-toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%); background: var(--sv-card, #222); color: var(--sv-text, #eee); border: 1px solid var(--sv-line, #444); padding: 10px 16px; border-radius: 12px; z-index: 70; font-size: 15px; max-width: 90vw; }
  .sv-empty { color: var(--sv-mute); padding: 40px 20px; text-align: center; }
  .sv-backlist { display: none; }
  .sv-cmp { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 15px; }
  .sv-cmp td, .sv-cmp th { padding: 8px 6px; border-bottom: 1px solid var(--sv-line); text-align: left; }
  .sv-cmp td.v { text-align: right; white-space: nowrap; } .sv-cmp td.win { color: var(--sv-good); font-weight: 600; }
  @media (max-width: 820px) {
    #spawnView { padding: 12px 12px; gap: 10px; }
    .sv-pill { padding: 6px 12px; font-size: 14px; }
    .sv-list { width: 100%; }
    .sv-main.detail .sv-list { display: none; } .sv-main:not(.detail) .sv-detail { display: none; }
    .sv-backlist { display: inline-block; margin-bottom: 12px; }
    .sv-detail, .sv-pad { padding: 16px; }
    .sv-prov { grid-template-columns: 18px 1fr; } .sv-prov .o, .sv-prov .act { grid-column: 2; justify-content: flex-start; }
    .sv-prov input { width: 100%; }
  }`;
  document.head.appendChild(css);

  const main = document.createElement('main');
  main.id = 'spawnView';
  document.body.appendChild(main);

  function toast(text) {
    if (!text) return;
    const el = document.createElement('div'); el.className = 'sv-toast'; el.textContent = text;
    main.appendChild(el); setTimeout(() => el.remove(), 3800);
  }
  async function act(body) {
    try {
      const r = await fetch('spawn/do', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      const txt = await r.text();
      if (!r.ok) { toast(I18N.text('spawnv.err', {why: txt})); return null; }
      const d = JSON.parse(txt); toast(d.note); if (d.open) window.open(d.open, '_blank');
      if (SV.sel) SV.model = null;
      await load(true); return d;
    } catch (e) { toast(I18N.text('spawnv.err', {why: String(e)})); return null; }
  }
  const fmt = v => v == null ? '—' : Math.abs(v) >= 100 ? String(Math.round(v)) : String(Math.round(v * 10) / 10);
  const ago = ts => { if (!ts) return ''; const s = Date.now() / 1000 - ts; return s < 90 ? '1 min' : s < 3600 ? Math.round(s / 60) + ' min' : Math.round(s / 3600) + ' h'; };
  const area = a => ((SV.data && SV.data.areas && SV.data.areas[a]) || a);
  const areaLow = a => area(a).toLowerCase();
  const MAIN_AREAS = ['code', 'agents', 'security', 'long_context'];
  const ALIAS = {coding: 'code', coder: 'code', cyber: 'security', agent: 'agents', long: 'long_context'};   // English words typed in the search

  function top() {
    const d = SV.data || {}, L = d.catalog || {};
    const label = {keys: `${I18N.text('spawnv.tab.keys')} ${d.ready || 0} ${I18N.text('spawnv.ready')}`, models: `${I18N.text('spawnv.tab.models')} ${(L.lines || []).length}`, roles: `${I18N.text('spawnv.tab.roles')} ${(d.roles || []).length}`};
    const upd = L.updating ? I18N.text('spawnv.updating') : L.updated ? I18N.text('spawnv.updated', {when: ago(L.updated)}) : I18N.text('spawnv.never');
    const pr = L.probing || {};
    const probe = pr.running ? `<span>${esc(I18N.text('spawnv.probeRun', {done: pr.done || 0, total: pr.total || 0}))}</span>`
                             : `<button class="sv-btn small" data-do="probe" title="${esc(I18N.text('spawnv.probeTip'))}">${esc(I18N.text('spawnv.probeAll'))}</button>`;
    return `<div class="sv-top"><button class="sv-logo" data-close="1" title="${esc(I18N.text('spawnv.back'))}">🛸</button><span class="sv-title">Spawn</span>
      ${['keys', 'models', 'roles'].map(k => `<button class="sv-pill ${SV.tab === k ? 'on' : ''}" data-tab="${k}">${esc(label[k])}</button>`).join('')}
      <span class="sv-sp"></span><span class="sv-upd">${probe}${esc(upd)}<button class="sv-icon" data-do="update" title="${esc(I18N.text('spawnv.update'))}">↻</button></span></div>`;
  }

  function keysTab() {
    const d = SV.data, dot = {ok: 'ok', saved: 'ok', bad: 'bad', none: '', skipped: 'warn'}, order = ['none', 'bad', 'skipped', 'saved', 'ok'];
    const rows = d.providers.slice().sort((a, b) => order.indexOf(a.state) - order.indexOf(b.state));
    const tool = (k, name) => `<div class="sv-prov"><span class="sv-dot ${d.tools[k] ? 'ok' : 'bad'}"></span><span>${name}</span><span class="o">${esc((d.tools[k] ? I18N.text('spawnv.tools.ok') : I18N.text('spawnv.tools.missing')))}</span>
      <span class="act">${!d.tools[k] && k === 'headroom' ? `<button class="sv-btn small" data-do="install_headroom">${esc(I18N.text('spawnv.tools.install'))}</button>` : ''}</span></div>`;
    return `<div class="sv-main"><div class="sv-card" style="flex:1"><div class="sv-pad">
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:6px"><b style="font-size:18px">${esc(I18N.text('spawnv.keys.ready', {n: d.ready}))}</b><span class="sv-sp"></span>
      ${rows.some(p => p.state === 'none') ? `<button class="sv-btn small" data-do="skip_rest">${esc(I18N.text('spawnv.keys.skipRest'))}</button>` : ''}</div>
      ${rows.map(p => `<div class="sv-prov"><span class="sv-dot ${dot[p.state]}"></span>
        <span><b>${esc(p.name)}</b><br><span class="o">${esc(I18N.text('spawnv.st.' + p.state))}</span></span>
        <span class="o">${esc(p.offer)} · <a href="${esc(p.signup)}" target="_blank" rel="noopener">${esc(I18N.text('spawnv.keys.get'))}</a></span>
        <span class="act">${p.state === 'ok' || p.state === 'saved' ? `<button class="sv-btn small" data-do="check_key" data-p="${esc(p.id)}">${esc(I18N.text('spawnv.keys.check'))}</button>`
          : p.state === 'skipped' ? `<button class="sv-btn small" data-do="unskip" data-p="${esc(p.id)}">${esc(I18N.text('spawnv.keys.unskip'))}</button>`
          : `${p.pkce ? `<button class="sv-btn small" data-do="login" data-p="${esc(p.id)}">${esc(I18N.text('spawnv.keys.login'))}</button>` : ''}
             <input type="password" autocomplete="off" placeholder="${esc(I18N.text('spawnv.keys.ph'))}" data-key="${esc(p.id)}">
             ${(p.extra || []).map(x => `<input type="text" placeholder="${esc(x)}" data-extra="${esc(p.id)}" data-name="${esc(x)}">`).join('')}
             <button class="sv-btn small pri" data-do="save_key" data-p="${esc(p.id)}">${esc(I18N.text('spawnv.keys.save'))}</button>
             <button class="sv-btn small" data-do="skip" data-p="${esc(p.id)}">${esc(I18N.text('spawnv.keys.skip'))}</button>`}</span></div>`).join('')}
      <div style="font-size:18px;font-weight:600;margin:24px 0 4px">${esc(I18N.text('spawnv.tools.head'))}</div>${tool('headroom', 'Headroom')}${tool('rtk', 'RTK')}</div></div></div>`;
  }

  function listRows() {
    const L = (SV.data.catalog || {}).lines || [], q = SV.q.trim().toLowerCase(), qa = ALIAS[q];
    const hit = m => !q || (qa && (m.areas || []).includes(qa)) || (m.name + ' ' + m.c + ' ' + (m.maker || '') + ' ' + (m.areas || []).map(areaLow).join(' ')).toLowerCase().includes(q);
    const rows = L.filter(m => hit(m) && (!SV.area || (m.areas || []).includes(SV.area)));
    if (!rows.length) return `<div class="sv-empty">${esc((L.length ? I18N.text('spawnv.noMatch') : I18N.text('spawnv.never')))}</div>`;
    return rows.map(m => {
      const on = SV.sel === m.c;
      const sub = [m.status === 'deprecated' ? I18N.text('spawnv.deprecated') : '', (m.areas || []).slice(0, 2).map(areaLow).join(' · ') || m.level,
                   on ? I18N.text('spawnv.hosts', {n: m.hosts}) : I18N.text('spawnv.hostsShort', {n: m.hosts})].filter(Boolean).join(' · ');
      return `<div class="sv-row ${on ? 'on' : ''}" data-m="${esc(m.c)}"><div class="n"><span>${probeDot(m.probe)}${esc(m.name)}</span><span class="aa">${m.aa == null ? esc(I18N.text('spawnv.noAA')) : 'AA ' + Math.round(m.aa)}</span></div>
        ${on ? `<div class="trk"><i style="width:${Math.max(3, Math.min(100, (m.aa || 0) / 70 * 100))}%"></i></div>` : ''}<div class="s">${esc(sub)}</div></div>`;
    }).join('');
  }

  const probeDot = p => `<span class="sv-dot ${!p ? '' : p.ok ? 'ok' : /rate|quota|overload/.test(p.error || '') ? 'warn' : 'bad'}" style="margin-right:8px"></span>`;
  const WHY = {payment: () => I18N.text('spawnv.why.payment'), quota: () => I18N.text('spawnv.why.quota'), rate_limit: () => I18N.text('spawnv.why.rate'),
               busy: () => I18N.text('spawnv.why.rate'), not_found: () => I18N.text('spawnv.why.notFound'), auth: () => I18N.text('spawnv.why.auth'),
               forbidden: () => I18N.text('spawnv.why.auth'), timeout: () => I18N.text('spawnv.why.slow'), upstream: () => I18N.text('spawnv.why.down'),
               overloaded: () => I18N.text('spawnv.why.down'), no_host: () => I18N.text('spawnv.why.noHost')};
  const why = p => (WHY[p.error] || (() => String(p.error || '').replace(/_/g, ' ')))();
  const probeText = p => !p ? I18N.text('spawnv.probe.none') : p.ok ? I18N.text('spawnv.probe.ok', {ms: p.ms}) : I18N.text('spawnv.probe.bad', {why: why(p)});
  const tried = (m, host) => { const t = ((m.probe || {}).tries || {})[host]; return t ? (t === 'ok' ? {ok: true, ms: m.probe.ms} : {ok: false, error: t}) : null; };
  const LIMS = [['rpm', n => I18N.text('spawnv.lim.rpm', {n})], ['rpd', n => I18N.text('spawnv.lim.rpd', {n})],
                ['tpm', n => I18N.text('spawnv.lim.tpm', {n})], ['tpd', n => I18N.text('spawnv.lim.tpd', {n})]];
  const limits = x => x ? [...LIMS.filter(([k]) => x[k] != null).map(([k, f]) => f(Number(x[k]).toLocaleString())), x.note].filter(Boolean).join(' · ') : '';

  function profile(m) {
    const p = m.profile;
    if (!p) return `<div class="sv-prof mute">${esc(I18N.text('spawnv.noProfile'))}</div>`;
    const tag = p.status === 'deprecated' ? `<span class="sv-tag bad">${esc(I18N.text('spawnv.deprecated'))}${p.successor ? ' · ' + esc(I18N.text('spawnv.successor', {name: p.successor})) : ''}</span>`
      : p.status === 'preview' ? `<span class="sv-tag">${esc(I18N.text('spawnv.preview'))}</span>` : '';
    return `<div class="sv-prof">${tag}<div>${esc(p.what)}</div>
      ${p.level ? `<div class="lvl">${esc(I18N.text('spawnv.level', {level: p.level}))}${p.basis ? ` <span class="mute">(${esc(p.basis)})</span>` : ''}</div>` : ''}</div>`;
  }

  function bench(b) {
    const pct = b.frontier != null ? Math.max(3, Math.min(100, b.frontier * 100)) : null;
    const good = b.rank && b.of && (b.rank <= 5 || b.rank / b.of <= 0.1);
    const maker = b.source.kind === 'maker';
    return `<div class="sv-b"><div class="top"><span class="name">${esc(b.name)} ${esc(fmt(b.value))}${b.unit === '%' ? '%' : ''}</span>
      ${b.rank ? `<span class="rank ${good ? 'good' : ''}">${esc(I18N.text('spawnv.rank', {rank: b.rank, of: b.of}))}</span>` : ''}</div>
      ${b.what ? `<div class="what">${esc(b.what)}</div>` : ''}
      <div class="sv-bar">${pct != null ? `<div class="t ${maker ? 'maker' : ''}"><i style="width:${pct}%"></i></div>` : '<span class="sv-sp"></span>'}
      <span class="sv-src ${maker ? 'maker' : ''}">${b.source.url ? `<a href="${esc(b.source.url)}" target="_blank" rel="noopener">${esc(b.source.label)}</a>` : esc(b.source.label)}</span></div></div>`;
  }

  function compare() {
    const m = SV.model, o = SV.cmp;
    const pickList = ((SV.data.catalog || {}).lines || []).filter(x => x.c !== m.c);
    const head = `<select id="svCmp"><option value="">${esc(I18N.text('spawnv.cmpPick'))}</option>${pickList.map(x => `<option value="${esc(x.c)}" ${o && o.c === x.c ? 'selected' : ''}>${esc(x.name)}${x.aa == null ? '' : ' · AA ' + Math.round(x.aa)}</option>`).join('')}</select>`;
    if (!o) return head;
    const all = b => Object.fromEntries([...b.strong, ...b.others].map(x => [x.bench, x]));
    const a = all(m), b = all(o), shared = Object.keys(a).filter(k => b[k]);
    if (!shared.length) return head + `<div class="sv-empty">${esc(I18N.text('spawnv.cmpNone'))}</div>`;
    const better = (x, y) => (x.better === 'lower' ? x.value < y.value : x.value > y.value);
    return head + `<table class="sv-cmp"><tr><th></th><th style="text-align:right">${esc(m.name)}</th><th style="text-align:right">${esc(o.name)}</th></tr>
      ${shared.map(k => `<tr><td>${esc(a[k].name)}</td><td class="v ${better(a[k], b[k]) ? 'win' : ''}">${esc(fmt(a[k].value))}</td><td class="v ${better(b[k], a[k]) ? 'win' : ''}">${esc(fmt(b[k].value))}</td></tr>`).join('')}</table>`;
  }

  function detail() {
    const m = SV.model;
    if (!SV.sel) return `<div class="sv-empty">${esc(I18N.text('spawnv.pick'))}</div>`;
    if (!m || m.c !== SV.sel) return `<div class="sv-empty">…</div>`;
    const ctx = Math.max(0, ...m.hosts.map(h => h.ctx || 0)), rep = SV.replacing;
    const tools = m.hosts.some(h => h.tools) ? I18N.text('spawnv.tools') : m.hosts.length && m.hosts.every(h => h.tools === false) ? I18N.text('spawnv.noTools') : '';
    const sub = [m.maker, ctx ? I18N.text('spawnv.ctx', {k: Math.round(ctx / 1000)}) : '', tools, probeText(m.probe)].filter(Boolean).join(' · ');
    const lim = Object.fromEntries(((m.profile || {}).limits || []).map(x => [x.host, x]));
    const action = rep ? `<button class="sv-btn pri" data-do="replace_go">${esc(I18N.text('spawnv.replaceWith', {name: rep}))}</button>`
                       : `<button class="sv-btn" data-form="1">${esc(I18N.text('spawnv.role.go'))}</button>`;
    const form = SV.form && !rep ? `<div class="sv-form"><label>${esc(I18N.text('spawnv.role.name'))}<br><input type="text" id="svName" placeholder="ARCH" maxlength="20" style="width:100%;box-sizing:border-box"></label>
      <label>${esc(I18N.text('spawnv.role.mission'))}<br><textarea id="svMission" rows="3" style="width:100%;box-sizing:border-box"></textarea></label>
      <label><input type="checkbox" id="svShell"> ${esc(I18N.text('spawnv.role.shell'))}</label>
      <div style="display:flex;gap:10px"><button class="sv-btn pri" data-do="create">${esc(I18N.text('spawnv.role.go'))}</button><button class="sv-btn" data-form="0">${esc(I18N.text('spawnv.cancel'))}</button></div></div>` : '';
    const best = (m.areas || []).slice(0, 3).map(areaLow).join(', ');
    const links = [['all', I18N.text('spawnv.allBench', {n: m.strong.length + m.others.length})], ['cmp', I18N.text('spawnv.cmp')],
                   ...(m.versions.length ? [['ver', I18N.text('spawnv.versions', {n: m.versions.length})]] : []), ['hosts', I18N.text('spawnv.hostsHead')]];
    const more = SV.more === 'all' ? m.others.map(bench).join('') || `<div class="sv-empty">${esc(I18N.text('spawnv.noOthers'))}</div>`
      : SV.more === 'cmp' ? compare()
      : SV.more === 'ver' ? m.versions.map(v => `<div class="sv-row" data-m="${esc(v.c)}"><div class="n"><span>${esc(v.name)}</span><span class="aa">${v.aa == null ? '' : 'AA ' + Math.round(v.aa)}</span></div></div>`).join('')
      : SV.more === 'hosts' ? m.hosts.map(h => `<div class="sv-host">${probeDot(tried(m, h.adapter))}<b>${esc(h.adapter)}</b><span>${esc(h.model_id)}</span>
          <span>${tried(m, h.adapter) ? esc(probeText(tried(m, h.adapter))) : ''}</span>
          <span>${h.ping_ms ? h.ping_ms + ' ms' : ''}</span><span>${h.left != null && h.limit ? esc(I18N.text('spawnv.quota', {left: h.left, limit: h.limit})) : ''}</span>
          <span class="lim">${esc(limits(lim[h.adapter]))}</span></div>`).join('')
          + `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:14px"><span class="sub" style="color:var(--sv-mute)">${esc(I18N.text('spawnv.line', {line: m.line}))}</span>
          ${m.near.length ? `<select id="svLine">${m.near.map(l => `<option>${esc(l)}</option>`).join('')}</select><button class="sv-btn small" data-do="move">${esc(I18N.text('spawnv.move'))}</button>` : ''}
          <button class="sv-btn small" data-do="split">${esc(I18N.text('spawnv.split'))}</button></div>` : '';
    return `<button class="sv-btn small sv-backlist" data-back="1">← ${esc(I18N.text('spawnv.tab.models'))}</button>
      ${rep ? `<div class="sv-banner">📟 ${esc(I18N.text('spawnv.replacing', {name: rep}))}<span class="sv-sp"></span><button class="sv-btn small" data-do="replace_cancel">${esc(I18N.text('spawnv.cancel'))}</button></div>` : ''}
      <div class="sv-h"><h2>${esc(m.name)}</h2><span class="sub">${esc(sub)}</span><span class="sv-sp"></span>${action}</div>${form}
      ${profile(m)}
      ${best ? `<div class="sv-strong">${esc(I18N.text('spawnv.bestIn', {areas: best}))}</div>` : ''}
      ${m.partial ? `<div style="color:var(--sv-mute);font-size:14px;margin-bottom:6px">${esc(I18N.text('spawnv.partial'))}</div>` : ''}
      <div class="sv-lbl">${esc(I18N.text('spawnv.strongLbl'))}</div>
      ${m.strong.length ? m.strong.map(bench).join('') : `<div class="sv-empty">${esc(I18N.text('spawnv.noStrong'))}</div>`}
      <div class="sv-links">${links.map(([k, l], i) => `${i ? '<span class="dot">·</span>' : '<span>⌄</span>'}<button class="${SV.more === k ? 'on' : ''}" data-more="${k}">${esc(l)}</button>`).join('')}
        <span class="dot">·</span><button data-do="study">${esc(I18N.text('spawnv.study'))}</button></div>
      <div class="sv-more">${more}</div>`;
  }

  function modelsTab() {
    const have = new Set(((SV.data.catalog || {}).lines || []).flatMap(m => m.areas || []));
    const chips = MAIN_AREAS.filter(a => have.has(a));
    return `<div class="sv-main ${SV.phoneDetail ? 'detail' : ''}"><div class="sv-card sv-list">
      <input id="svQ" type="search" placeholder="${esc(I18N.text('spawnv.search'))}" value="${esc(SV.q)}">
      <div class="sv-chips">${chips.map(a => `<button class="sv-chip ${SV.area === a ? 'on' : ''}" data-area="${esc(a)}">${esc(area(a))}</button>`).join('')}</div>
      <div class="sv-rows" id="svList">${listRows()}</div></div>
      <div class="sv-card sv-detail" id="svDetail">${detail()}</div></div>`;
  }

  function rolesTab() {
    const rs = SV.data.roles, dot = {service: 'ok', switch: 'warn', notokens: 'bad', stopped: 'bad'};
    return `<div class="sv-main"><div class="sv-card" style="flex:1"><div class="sv-pad">${rs.length ? rs.map(r => `<div class="sv-role ${r.state === 'notokens' ? 'blink' : ''}">
      <span class="sv-dot ${dot[r.state] || ''}"></span><div><div class="r1">${r.state === 'notokens' ? '📟 ' : ''}${esc(r.name)} · ${esc(I18N.text('spawnv.roles.st.' + r.state))}</div>
      <div class="r2">${esc([r.model, r.host, r.usage && r.usage.in ? I18N.text('spawnv.roles.usage', {i: r.usage.in, o: r.usage.out || 0}) : '', r.compact ? I18N.text('spawnv.compact') : '', r.error].filter(Boolean).join(' · '))}</div>
      <div class="r2">${esc(r.mission)}</div></div>
      <div style="display:flex;gap:8px"><button class="sv-btn small ${r.state === 'notokens' ? 'pri' : ''}" data-do="replace_pick" data-r="${esc(r.name)}">${esc(I18N.text('spawnv.roles.replace'))}</button>
      ${r.state !== 'stopped' ? `<button class="sv-btn small" data-do="stop" data-r="${esc(r.name)}">${esc(I18N.text('spawnv.roles.stop'))}</button>` : ''}</div></div>`).join('')
      : `<div class="sv-empty">${esc(I18N.text('spawnv.roles.none'))}</div>`}</div></div></div>`;
  }

  function render() {
    if (!SV.open) return;
    if (!SV.data) { main.innerHTML = top() + `<div class="sv-empty">…</div>`; return; }
    const listScroll = $('svList') ? $('svList').scrollTop : 0, detScroll = $('svDetail') ? $('svDetail').scrollTop : 0;
    const focus = document.activeElement && document.activeElement.id === 'svQ';
    const sel = i => i.id ? '#' + i.id : i.dataset.key ? `input[data-key="${i.dataset.key}"]` : `input[data-extra="${i.dataset.extra}"][data-name="${i.dataset.name}"]`;
    const typed = [...main.querySelectorAll('input[data-key], input[data-extra], #svName, #svMission, #svShell')].map(i => [sel(i), i.type === 'checkbox' ? i.checked : i.value]);
    main.innerHTML = top() + (SV.tab === 'keys' ? keysTab() : SV.tab === 'roles' ? rolesTab() : modelsTab());
    for (const [s, v] of typed) { const i = main.querySelector(s); if (i && v) { if (i.type === 'checkbox') i.checked = true; else i.value = v; } }
    if ($('svList')) $('svList').scrollTop = listScroll;
    if ($('svDetail')) $('svDetail').scrollTop = detScroll;
    if (focus && $('svQ')) { const q = $('svQ'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
  }

  async function load(force = false) {
    if (SV.busy && !force) return;
    SV.busy = true;
    try {
      const d = await (await fetch('spawn/state.json', {cache: 'no-store'})).json();
      const fresh = JSON.stringify(d) !== JSON.stringify(SV.data);
      SV.data = d;
      if ((!SV.sel || !d.catalog.lines.some(m => m.c === SV.sel || (m.older || []).some(o => o.c === SV.sel))) && d.catalog.lines.length) SV.sel = d.catalog.lines[0].c;
      const typing = document.activeElement && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) && main.contains(document.activeElement);
      if (SV.sel && (!SV.model || SV.model.c !== SV.sel)) await pick(SV.sel, false);
      else if (force || (fresh && !typing)) render();            // never redrawn under the user's fingers while they type
    } catch (e) {}
    SV.busy = false;
  }
  async function getModel(c) {
    const r = await fetch('spawn/model.json?c=' + encodeURIComponent(c), {cache: 'no-store'});
    return r.ok ? r.json() : null;
  }
  async function pick(c, show = true) {
    SV.sel = c; SV.form = false; SV.cmp = null; if (SV.more === 'cmp' || SV.more === 'ver') SV.more = ''; keep();
    if (show) { SV.phoneDetail = true; render(); }
    try { SV.model = await getModel(c) || SV.model; } catch (e) {}
    render();
    if ($('svDetail')) $('svDetail').scrollTop = 0;
  }

  main.addEventListener('click', async e => {
    const el = e.target.closest('[data-tab],[data-m],[data-area],[data-do],[data-form],[data-close],[data-back],[data-more]');
    if (!el) return;
    if (el.dataset.tab) { SV.tab = el.dataset.tab; keep(); return render(); }
    if (el.dataset.close) return open(false);
    if (el.dataset.back) { SV.phoneDetail = false; return render(); }
    if (el.dataset.more) { SV.more = SV.more === el.dataset.more ? '' : el.dataset.more; return render(); }
    if (el.dataset.m) return pick(el.dataset.m);
    if (el.dataset.area !== undefined && el.classList.contains('sv-chip')) { SV.area = SV.area === el.dataset.area ? '' : el.dataset.area; return render(); }
    if (el.dataset.form) { SV.form = el.dataset.form === '1'; render(); if (SV.form && $('svName')) $('svName').focus(); return; }
    const d = el.dataset.do, p = el.dataset.p, r = el.dataset.r;
    if (d === 'save_key') {
      const key = (main.querySelector(`input[data-key="${p}"]`) || {}).value || '';
      const extra = {}; main.querySelectorAll(`input[data-extra="${p}"]`).forEach(i => { extra[i.dataset.name] = i.value; });
      el.disabled = true; await act({action: 'save_key', provider: p, key, extra}); return;
    }
    if (['check_key', 'skip', 'unskip', 'login'].includes(d)) return act({action: d, provider: p});
    if (d === 'skip_rest' && !confirm(I18N.text('spawn.prep.skipRestConfirm', {n: SV.data.providers.filter(x => x.state === 'none').length}))) return;
    if (['skip_rest', 'install_headroom', 'study', 'probe'].includes(d)) return act({action: d});
    if (d === 'update') return act({action: 'update', force: true});
    if (d === 'create') {
      const name = ($('svName').value || '').trim().toUpperCase();
      if (!/^[A-Z][A-Z0-9_]{1,19}$/.test(name)) { $('svName').focus(); return toast(I18N.text('spawnv.badName')); }
      const res = await act({action: 'create', name, mission: $('svMission').value, model: SV.sel, shell: $('svShell').checked});
      if (res) { SV.form = false; SV.tab = 'roles'; keep(); render(); }
      return;
    }
    if (d === 'replace_pick') { SV.replacing = r; SV.tab = 'models'; return render(); }
    if (d === 'replace_cancel') { SV.replacing = null; return render(); }
    if (d === 'replace_go') {
      const res = await act({action: 'replace', role: SV.replacing, model: SV.sel});
      if (res) { SV.replacing = null; SV.tab = 'roles'; render(); }
      return;
    }
    if (d === 'stop') return act({action: 'stop', role: r});
    if (d === 'move') return act({action: 'move', model: SV.sel, line: $('svLine').value});
    if (d === 'split') { if (confirm(I18N.text('spawn.sheet.splitConfirm', {model: SV.sel}))) await act({action: 'split', model: SV.sel}); }
  });
  main.addEventListener('input', e => {
    if (e.target.id === 'svQ') { SV.q = e.target.value; const l = $('svList'); if (l) l.innerHTML = listRows(); }
  });
  main.addEventListener('change', async e => {
    if (e.target.id === 'svCmp') { SV.cmp = e.target.value ? await getModel(e.target.value) : null; render(); }
  });
  addEventListener('keydown', e => { if (SV.open && e.key === 'Escape' && !/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || '')) open(false); });

  function open(on) {
    SV.open = !!on;
    document.body.classList.toggle('sv-open', SV.open);
    btn.classList.toggle('on', SV.open);
    const u = new URL(location.href);
    if (SV.open) u.searchParams.set('view', 'spawn'); else if (u.searchParams.get('view') === 'spawn') u.searchParams.delete('view');
    history.replaceState(null, '', u);
    if (SV.open) { render(); load(true); }
  }
  const btn = document.createElement('button');
  btn.className = 'icon-btn'; btn.id = 'spawnBtn'; btn.textContent = '🛸';
  btn.addEventListener('click', () => open(!SV.open));
  const ob = document.getElementById('officeBtn');
  if (ob) ob.insertAdjacentElement('beforebegin', btn);
  window.spawnView = {open, toggle: () => open(!SV.open)};
  (typeof I18N_READY !== 'undefined' ? I18N_READY : Promise.resolve()).then(() => {
    try { btn.title = I18N.text('spawnv.btn'); } catch (e) {}
    if (new URLSearchParams(location.search).get('view') === 'spawn') open(true);
  });
  setInterval(() => { if (SV.open && !document.hidden) load(); }, 4000);
})();
