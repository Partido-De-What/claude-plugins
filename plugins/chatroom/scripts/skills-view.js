/* The Skills view (0.19): a full-window page of the viewer, like spawn-view.js. Three tabs: Explore (the list of skills on this
   computer on the left, the chosen one on the right: what it does, where it lives, which agents have it, recommend it),
   Agents (the skills each participant has) and Search (describe a skill, the room's searcher looks for it, the answers come
   back as cards). Data from GET skills.json, actions to POST skills/do (scripts/skills.py). Nothing is installed here without
   the user's confirmation in this page. Opened by the 📚 button or ?view=skills; Esc or the 📚 in its own bar goes back to the
   chat. ?mock=1 shows made-up data (no server needed). */
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const MOCK = new URLSearchParams(location.search).get('mock') === '1';
  const SK = {open: false, tab: 'explore', data: null, err: '', sel: null, q: '', origin: '', form: null, confirm: null,
              searchQ: '', searchFor: [], busy: false, hash: '',
              upd: {}, chk: {}, act: {}, cres: {}, unused: false, scan: '', chatDesc: '', cand: {room: '', sel: null, desc: '', diffs: {}, src: {derive: {k: 'room', v: 'current'}, imp: {k: 'room', v: 'current'}}}};
  try { Object.assign(SK, (({tab, sel}) => ({tab: tab || SK.tab, sel: sel || null}))(JSON.parse(localStorage.getItem('chatroom.skillsView') || '{}'))); } catch (e) {}
  const keep = () => { try { localStorage.setItem('chatroom.skillsView', JSON.stringify({tab: SK.tab, sel: SK.sel})); } catch (e) {} };

  // design tokens of D5 (scratch/DESIGN/tokens.css): defined once for the page; the viewer's own block, when it has one, wins by the same id
  if (!document.getElementById('d-tokens')) { const t = document.createElement('style'); t.id = 'd-tokens'; t.textContent = `
:root {
  --d-accent: var(--accent, #14b8a6);                                   /* room accent, user-chosen */
  --d-accent2: color-mix(in oklab, var(--d-accent) 45%, #6d5dfc);
  --d-grad: linear-gradient(135deg, var(--d-accent), var(--d-accent2));  /* primary buttons, progress, badges, own bubbles */
  --d-bg: #f4f1ec; --d-card: rgba(255,255,255,.78); --d-card2: rgba(255,255,255,.95); /* card2 = popovers/composer (opaque) */
  --d-line: rgba(24,24,48,.09); --d-hover: rgba(24,24,48,.05);
  --d-text: #16181f; --d-muted: #6b7080;
  --d-ok: #1f9d55; --d-no: #d6455d; --d-amber: #c98200; --d-amber-bg: rgba(245,180,0,.14);
  --d-shadow: 0 10px 30px -12px rgba(30,30,70,.28); --d-shadow-pop: 0 24px 60px -16px rgba(0,0,0,.5);
  /* radii */
  --d-r-sm: 10px; --d-r-md: 14px; --d-r-lg: 20px; --d-r-xl: 26px; --d-r-pill: 99px;
  /* motion: enter 450ms ease-out, hover/press 200ms, pop-ups 320ms spring */
  --d-ease: cubic-bezier(.2,.8,.2,1); --d-spring: cubic-bezier(.34,1.56,.64,1);
  --d-t-fast: .18s; --d-t: .3s; --d-t-enter: .45s;
  /* kind colors for cards and chips */
  --d-k-status: var(--d-accent); --d-k-plan: #8b6cff; --d-k-find: var(--d-amber); --d-k-skill: #e0489a; --d-k-cmd: #3b82f6; --d-k-vote: var(--d-ok);
  /* agent color from a hue 0-360: avatar and name use  oklch(.72 .15 H)  and a gradient to  oklch(.58 .17 H+40) */
}
:root[data-theme="dark"] {
  --d-bg: #090b11; --d-card: rgba(255,255,255,.055); --d-card2: rgba(26,30,44,.96);
  --d-line: rgba(255,255,255,.09); --d-hover: rgba(255,255,255,.06);
  --d-text: #eceef6; --d-muted: #8b91a6;
  --d-ok: #4cd27f; --d-no: #ff7088; --d-amber: #ffc84a; --d-amber-bg: rgba(255,200,74,.12);
  --d-shadow: 0 14px 34px -14px rgba(0,0,0,.7);
}
/* Existing convention kept: each view scopes its own prefix (--sv- spawn-view.js, --sk- skills-view.js, --pv- preview-view.js).
   A view maps its prefix onto these, e.g.  #skillsView { --sk-acc: var(--d-accent); --sk-card: var(--d-card); --sk-line: var(--d-line);
   --sk-text: var(--d-text); --sk-mute: var(--d-muted); --sk-good: var(--d-ok); --sk-bad: var(--d-no); --sk-ease: var(--d-ease); }
   so one change here restyles every view. viewer.html defines the --d-* on :root; spawn-view.js stays as it is (the reference). */
  `; document.head.appendChild(t); }
  const ICON = p => `<svg class="sk-i" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
  const IC = {down: ICON('<path d="m6 9 6 6 6-6"/>'), spark: ICON('<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 3v4M17 5h4M5 17v4M3 19h4"/>'), plus: ICON('<path d="M12 5v14M5 12h14"/>'),
    back: ICON('<path d="M19 12H5M12 19l-7-7 7-7"/>'), check: ICON('<path d="M5 13l4 4L19 7"/>')};
  const css = document.createElement('style');
  css.textContent = `
  #skillsView { --o-user: #3b82f6; --o-project: #1f9d55; --o-plugin: #8b6cff; --o-added: #c98200; --o-account: #e0489a; --o-builtin: #6b7080;
    position: fixed; inset: 0; z-index: 60; display: none; flex-direction: column; background: var(--d-bg); color: var(--d-text);
    font: 15px/1.5 "Inter", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif; padding: 18px 26px 22px; gap: 14px; box-sizing: border-box; overflow: clip; }   /* clip, not hidden: the ::before glow must not make the page scrollable (scrollIntoView pushed the top bar away) */
  :root[data-theme="dark"] #skillsView { --o-user: #7fb0f0; --o-project: #4cd27f; --o-plugin: #b799f0; --o-added: #ffc84a; --o-account: #f08ab5; --o-builtin: #9aa7b5; }
  #skillsView::before { content: ""; position: absolute; inset: -20%; pointer-events: none; z-index: 0;
    background: radial-gradient(40% 35% at 12% 8%, color-mix(in oklab, var(--d-accent) 22%, transparent), transparent 70%), radial-gradient(38% 34% at 92% 92%, rgba(109,93,252,.16), transparent 70%);
    animation: sk-drift 24s ease-in-out infinite alternate; }
  #skillsView > * { position: relative; z-index: 1; }
  body.sk-open #skillsView { display: flex; }
  svg.sk-i { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: none; vertical-align: -3px; }
  .sk-top { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .sk-logo { width: 44px; height: 44px; border-radius: 15px; background: var(--d-grad); display: grid; place-items: center; color: #fff; border: 0; cursor: pointer; padding: 0;
    box-shadow: 0 8px 20px -6px var(--d-accent); transition: transform var(--d-t) var(--d-spring); }
  .sk-logo:hover { transform: rotate(-6deg) scale(1.06); } .sk-logo svg { width: 24px; height: 24px; }
  .sk-title { font-size: 19px; font-weight: 650; letter-spacing: -.01em; margin-right: 10px; }
  .sk-pill { border: 1px solid var(--d-line); background: var(--d-card); backdrop-filter: blur(14px); color: var(--d-text); border-radius: var(--d-r-pill); padding: 7px 18px; cursor: pointer; font: inherit; font-size: 14.5px; font-weight: 550; }
  .sk-pill.on { background: color-mix(in oklab, var(--d-accent) 14%, var(--d-card)); color: var(--d-accent); border-color: var(--d-accent); }
  .sk-sp { flex: 1; }
  .sk-upd { color: var(--d-muted); font-size: 13.5px; }
  .sk-main { flex: 1; min-height: 0; display: flex; gap: 18px; }
  .sk-card { background: var(--d-card); border: 1px solid var(--d-line); border-radius: var(--d-r-lg); backdrop-filter: blur(14px); box-shadow: var(--d-shadow); min-height: 0; display: flex; flex-direction: column; }
  .sk-explore { padding: 16px 18px 6px; gap: 14px; flex: 1; min-width: 0; }
  .sk-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .sk-bar input, .sk-find input, .sk-form input, .sk-rec select { box-sizing: border-box; padding: 11px 16px; border-radius: var(--d-r-pill); border: 1px solid var(--d-line);
    background: var(--d-card2); color: var(--d-text); font: inherit; outline: none; transition: border-color var(--d-t-fast), box-shadow var(--d-t); }
  .sk-bar input:focus, .sk-find input:focus, .sk-form input:focus, .sk-rec select:focus { border-color: color-mix(in oklab, var(--d-accent) 60%, transparent); box-shadow: 0 0 0 4px color-mix(in oklab, var(--d-accent) 16%, transparent); }
  .sk-bar input { width: 280px; max-width: 100%; }
  .sk-chips { display: flex; gap: 7px; flex-wrap: wrap; }
  .sk-chip { font: inherit; font-size: 13px; padding: 5px 13px; border-radius: var(--d-r-pill); border: 1px solid var(--d-line); cursor: pointer; background: var(--d-card); color: var(--d-text); }
  .sk-chip.on { background: color-mix(in oklab, var(--d-accent) 14%, var(--d-card)); color: var(--d-accent); border-color: var(--d-accent); }
  .sk-chip .n { color: var(--d-muted); margin-left: 6px; font-variant-numeric: tabular-nums; }
  .sk-rows { overflow-y: auto; min-height: 0; flex: 1; margin: 0 -8px; padding: 4px 8px 16px; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(290px, 100%), 1fr)); gap: 14px; align-content: start; grid-auto-flow: row dense; }
  .sk-row { border: 1px solid var(--d-line); border-radius: var(--d-r-lg); background: var(--d-card); position: relative; overflow: clip; display: flex; flex-direction: column; box-shadow: var(--d-shadow); }
  .sk-row::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: linear-gradient(90deg, var(--o, var(--d-line)), color-mix(in oklab, var(--o, var(--d-line)) 30%, transparent)); }
  .sk-row.off { opacity: .6; }
  .sk-row.on { grid-column: 1 / -1; background: color-mix(in oklab, var(--d-accent) 8%, var(--d-card)); border-color: color-mix(in oklab, var(--d-accent) 55%, var(--d-line)); }
  .sk-hd { display: flex; gap: 13px; align-items: flex-start; padding: 16px 16px 14px; cursor: pointer; outline: none; }
  .sk-hd .tl { width: 42px; height: 42px; border-radius: 14px; flex: none; display: grid; place-items: center; color: #fff; font-weight: 700; font-size: 18px;
    background: linear-gradient(135deg, var(--o, var(--d-accent)), color-mix(in oklab, var(--o, var(--d-accent)) 45%, #6d5dfc)); transition: transform var(--d-t) var(--d-spring); }
  .sk-row.on .tl, .sk-hd:hover .tl { transform: scale(1.08) rotate(-5deg); }
  .sk-hd .rb { min-width: 0; flex: 1; }
  .sk-hd .n { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 16.5px; font-weight: 650; letter-spacing: -.01em; }
  .sk-hd .n > span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sk-hd .s { font-size: 13.5px; color: var(--d-muted); margin-top: 3px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .sk-chev { width: 18px; height: 18px; flex: none; margin-top: 3px; color: var(--d-muted); transition: transform var(--d-t) var(--d-spring); } .sk-row.on .sk-chev { transform: rotate(180deg); color: var(--d-accent); }
  .sk-more { display: grid; grid-template-rows: 1fr; } .sk-mi { min-height: 0; overflow: hidden; }
  .sk-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: 6px 36px; padding: 2px 20px 20px; border-top: 1px solid var(--d-line); }
  .sk-tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 16px 0 4px; }
  .sk-tile { --tc: var(--d-line); position: relative; overflow: hidden; border: 1px solid var(--d-line); border-radius: var(--d-r-md); background: var(--d-card2); padding: 13px 15px 12px; min-height: 88px; display: flex; flex-direction: column; justify-content: center; gap: 3px; transition: transform var(--d-t) var(--d-spring), border-color var(--d-t-fast); }
  .sk-tile::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px; background: var(--tc); }
  .sk-tile:hover { transform: translateY(-2px); border-color: var(--tc); }
  .sk-tile.ok, .sk-tile.verified { --tc: var(--d-ok); } .sk-tile.bad, .sk-tile.failed, .sk-tile.mid { --tc: var(--d-amber); }
  .sk-tile .b { font-size: 26px; font-weight: 780; line-height: 1.1; letter-spacing: -.01em; font-variant-numeric: tabular-nums; display: flex; align-items: center; }
  .sk-tile.verified .b, .sk-tile.ok .b { color: var(--d-ok); } .sk-tile.failed .b, .sk-tile.bad .b, .sk-tile.mid .b { color: var(--d-amber); } .sk-tile.none .b, .sk-tile.unverified .b { color: var(--d-muted); }
  .sk-tile.verified .b { font-size: 20px; } .sk-tile.failed .b, .sk-tile.unverified .b { font-size: 18px; } .sk-tile .b svg { width: 22px; height: 22px; }
  .sk-tile .l { font-size: 12.5px; color: var(--d-muted); line-height: 1.3; }
  .sk-tile .bar { display: flex; height: 6px; border-radius: 3px; overflow: hidden; background: var(--d-hover); margin-top: 8px; } .sk-tile .bar i { display: block; width: var(--w); transform-origin: left; } .sk-tile .bar .ok { background: var(--d-ok); } .sk-tile .bar .bad { background: var(--d-amber); } .sk-tile .bar .nt { background: var(--d-muted); opacity: .5; }
  .sk-tile .row { display: flex; align-items: center; gap: 12px; } .sk-tile .ring { --sc: var(--tc); width: 58px; height: 58px; flex: none; border-radius: 50%; position: relative; display: grid; place-items: center; background: conic-gradient(var(--sc) calc(var(--p) * 1%), var(--d-hover) 0); }
  .sk-tile .ring::before { content: ""; position: absolute; inset: 6px; border-radius: 50%; background: var(--d-card2); } .sk-tile .ring b { position: relative; font-size: 14px; font-weight: 750; font-variant-numeric: tabular-nums; }
  .sk-animd .sk-row.on .sk-tile { animation: sk-pop var(--d-t) var(--d-spring) both; animation-delay: calc(var(--i, 0) * 70ms + 140ms); }
  .sk-animd .sk-row.on .sk-tile .bar i { animation: sk-grow .8s var(--d-ease) both; animation-delay: .35s; }
  @keyframes sk-grow { from { transform: scaleX(0); } to { transform: none; } }
  @media (max-width: 420px) { .sk-tile .b { font-size: 22px; } .sk-tile .ring { width: 48px; height: 48px; } .sk-tile .row { gap: 8px; } }
  .sk-cols > div > .sk-sec:first-child { margin-top: 16px; }
  .sk-bd { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 7px; } .sk-bd span { font-size: 11.5px; font-weight: 600; padding: 1px 9px; border-radius: var(--d-r-pill); background: color-mix(in oklab, var(--d-accent) 14%, transparent); color: var(--d-accent); }
  .sk-o { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 2px 10px; border-radius: var(--d-r-pill); color: var(--o); background: color-mix(in oklab, var(--o) 16%, transparent); }
  .sk-h { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
  .sk-sub { color: var(--d-muted); font-size: 14px; }
  .sk-desc { margin: 12px 0; font-size: 15.5px; line-height: 1.55; max-width: 760px; }
  .sk-path { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: var(--d-muted); word-break: break-all; margin: 4px 0 6px; padding: 6px 12px; border-radius: var(--d-r-sm); background: var(--d-hover); display: inline-block; }
  .sk-sec { margin: 20px 0 8px; font-size: 11.5px; font-weight: 700; color: var(--d-muted); text-transform: uppercase; letter-spacing: .07em; }
  .sk-who { display: flex; gap: 8px; flex-wrap: wrap; }
  .sk-who .w { border: 1px solid var(--d-line); border-radius: var(--d-r-pill); padding: 5px 13px; font: inherit; font-size: 14px; background: var(--d-card2); color: var(--d-text); }
  .sk-who .w small { color: var(--d-muted); margin-left: 6px; }
  .sk-btn { border: 1px solid var(--d-line); background: var(--d-card2); color: var(--d-text); border-radius: var(--d-r-pill); padding: 8px 20px; cursor: pointer; font: inherit; font-size: 14.5px; font-weight: 600; }
  .sk-btn:hover:not(:disabled) { border-color: var(--d-accent); }
  .sk-btn.pri { background: var(--d-grad); color: #fff; border-color: transparent; box-shadow: 0 8px 18px -6px var(--d-accent); }
  .sk-btn.small { padding: 5px 14px; font-size: 13.5px; }
  .sk-btn:disabled { opacity: .5; cursor: default; box-shadow: none; }
  .sk-rec { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .sk-rec select { padding: 9px 14px; }
  .sk-note { color: var(--d-muted); font-size: 13.5px; margin-top: 8px; max-width: 640px; }
  .sk-empty { color: var(--d-muted); padding: 40px 20px; text-align: center; }
  .sk-pad { padding: 22px 28px; overflow-y: auto; flex: 1; }
  .sk-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; align-content: start; }
  .sk-ag { padding: 16px 18px; border: 1px solid var(--d-line); border-radius: var(--d-r-lg); background: var(--d-card); backdrop-filter: blur(14px); position: relative; overflow: hidden; }
  .sk-ag::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--d-grad); }
  .sk-ag h3 { margin: 0 0 2px; font-size: 17px; font-weight: 650; display: flex; align-items: center; gap: 8px; }
  .sk-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; background: var(--d-muted); flex: none; }
  .sk-dot.ok { background: var(--d-ok); } .sk-dot.warn { background: var(--d-amber); } .sk-dot.bad { background: var(--d-no); }
  .sk-ag .none { color: var(--d-muted); font-size: 14px; margin-top: 10px; }
  .sk-ag .who { margin-top: 12px; }
  .sk-find { padding: 18px 22px; gap: 12px; display: flex; flex-direction: column; flex: none; }
  .sk-find .r { display: flex; gap: 10px; flex-wrap: wrap; }
  .sk-find input { flex: 1; min-width: 220px; font-size: 16px; }
  .sk-banner { padding: 11px 16px; border-radius: var(--d-r-md); background: var(--d-amber-bg); display: flex; gap: 12px; align-items: center; flex-wrap: wrap; font-size: 14px; }
  .sk-req { margin-bottom: 22px; }
  .sk-req .rh { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-bottom: 10px; }
  .sk-req .rq { font-size: 17px; font-weight: 650; letter-spacing: -.01em; }
  .sk-st { font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 2px 10px; border-radius: var(--d-r-pill); background: color-mix(in oklab, var(--d-accent) 16%, transparent); color: var(--d-accent); }
  .sk-st.paused, .sk-st.pending { background: var(--d-amber-bg); color: var(--d-amber); }
  .sk-st.failed { background: color-mix(in oklab, var(--d-no) 16%, transparent); color: var(--d-no); }
  .sk-fit { height: 7px; border-radius: 7px; background: var(--d-hover); margin: 8px 0; overflow: hidden; }
  .sk-fit i { display: block; height: 100%; border-radius: 7px; background: var(--d-grad); position: relative; overflow: hidden; transform-origin: left; animation: sk-grow 1.1s var(--d-ease) both; }
  .sk-fit i::after { content: ""; position: absolute; inset: 0; background: linear-gradient(100deg, transparent 30%, rgba(255,255,255,.55) 50%, transparent 70%); transform: translateX(-100%); animation: sk-shimmer 2.2s 1s infinite; }
  .sk-cd .s { font-size: 14px; margin: 4px 0 6px; } .sk-cd .m { font-size: 13px; color: var(--d-muted); word-break: break-word; }
  .sk-cd .m a { color: var(--d-accent); text-decoration: none; } .sk-cd .m a:hover { text-decoration: underline; }
  .sk-cd .acts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; align-items: center; }
  .sk-cd h4 { margin: 0; font-size: 16px; font-weight: 650; display: flex; justify-content: space-between; gap: 8px; }
  .sk-ok { color: var(--d-ok); font-size: 13.5px; font-weight: 600; }
  .sk-modal { position: fixed; inset: 0; z-index: 70; background: rgba(8,10,18,.5); display: flex; align-items: center; justify-content: center; padding: 16px; }
  .sk-box { background: var(--d-card2); border: 1px solid var(--d-line); border-radius: var(--d-r-xl); padding: 22px 24px; max-width: 560px; width: 100%; box-sizing: border-box; max-height: 90vh; overflow-y: auto; box-shadow: var(--d-shadow-pop); }
  .sk-box h3 { margin: 0 0 12px; font-size: 19px; font-weight: 650; }
  .sk-kv { display: grid; grid-template-columns: 90px 1fr; gap: 6px 12px; font-size: 14px; margin: 10px 0; } .sk-kv b { color: var(--d-muted); font-weight: 500; } .sk-kv span { overflow-wrap: anywhere; }
  .sk-box .acts { display: flex; gap: 10px; justify-content: flex-end; margin-top: 16px; }
  .sk-form { display: grid; gap: 10px; } .sk-form input { width: 100%; }
  .sk-toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%); background: var(--d-card2); color: var(--d-text); border: 1px solid var(--d-line);
    padding: 10px 18px; border-radius: var(--d-r-pill); z-index: 80; box-shadow: var(--d-shadow-pop); max-width: 90vw; font-weight: 550; }
  /* themed scrollbars, the system's white one stays out of the dark theme */
  #skillsView, #skillsView * { scrollbar-width: thin; scrollbar-color: color-mix(in oklab, var(--d-muted) 55%, transparent) transparent; }
  :root[data-theme="dark"] #skillsView { color-scheme: dark; }
  /* motion: transform and opacity (60 fps); the list and cards enter when the user acts (.sk-anim), not on every poll. Durations and curves are the --d-* tokens */
  /* the panel itself is opaque from the first frame (the chat must never show through); only the cards move and fade in, over that solid ground, in under 400 ms */
  .sk-pill, .sk-chip, .sk-btn, .sk-row, .sk-ag, .sk-who .w { transition: background-color var(--d-t-fast), border-color var(--d-t-fast), color var(--d-t-fast), transform var(--d-t) var(--d-spring), box-shadow var(--d-t); }
  .sk-pill:hover:not(.on), .sk-chip:hover:not(.on) { border-color: var(--d-accent); transform: translateY(-2px); }
  .sk-pill:active, .sk-chip:active, .sk-btn:active:not(:disabled) { transform: scale(.95); }
  .sk-btn.pri:hover:not(:disabled) { transform: scale(1.06); }
  .sk-row:hover:not(.on) { transform: translateY(-3px); box-shadow: 0 18px 36px -16px rgba(0,0,0,.45); border-color: color-mix(in oklab, var(--o, var(--d-accent)) 50%, var(--d-line)); }
  .sk-hd:focus-visible { outline: 2px solid var(--d-accent); outline-offset: -3px; border-radius: var(--d-r-lg); }
  .sk-ag:hover { transform: translateY(-2px); border-color: color-mix(in oklab, var(--d-accent) 45%, var(--d-line)); }
  .sk-pill:focus-visible, .sk-chip:focus-visible, .sk-btn:focus-visible, .sk-logo:focus-visible { outline: 2px solid var(--d-accent); outline-offset: 2px; }
  .sk-ft { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; } .sk-ft .sk-bd { margin-top: 0; }
  .sk-bd { padding: 0; } .sk-bd span { transition: transform var(--d-t-fast) var(--d-spring); } .sk-row:hover .sk-bd span { transform: translateY(-1px); }
  .sk-anim .sk-main > .sk-card, .sk-anim > .sk-card, .sk-anim .sk-candwrap > .sk-card { animation: sk-enter var(--d-t) var(--d-ease) both; }
  .sk-anim .sk-main > .sk-card + .sk-card, .sk-anim .sk-candwrap > .sk-card + .sk-card { animation-delay: .06s; }
  .sk-anim .sk-row, .sk-anim .sk-grid > *, .sk-anim .sk-req { animation: sk-enter var(--d-t) var(--d-ease) both; animation-delay: calc(min(var(--i, 0), 8) * 12ms); }
  .sk-animd .sk-row.on .sk-more { animation: sk-unfold var(--d-t-enter) var(--d-ease) both; } .sk-animd .sk-row.on .sk-cols > * { animation: sk-enter var(--d-t-enter) var(--d-ease) both; } .sk-animd .sk-row.on .sk-cols > :nth-child(2) { animation-delay: .07s; }
  .sk-anim .sk-bd span { animation: sk-pop var(--d-t) var(--d-spring) both; }
  .sk-modal.in { animation: sk-fade var(--d-t-fast) ease both; backdrop-filter: blur(4px); }
  .sk-modal.in .sk-box { animation: sk-pop-in var(--d-t) var(--d-spring) both; }
  .sk-toast { animation: sk-toast 3.8s var(--d-ease) both; }
  @keyframes sk-drift { to { transform: translate3d(2%, -2%, 0) scale(1.06); } }
  @keyframes sk-enter { from { opacity: 0; transform: translateY(14px) scale(.97); } to { opacity: 1; transform: none; } }
  @keyframes sk-pop { from { opacity: 0; transform: scale(.7); } to { opacity: 1; transform: none; } }
  @keyframes sk-pop-in { from { opacity: 0; transform: translateY(14px) scale(.95); } to { opacity: 1; transform: none; } }
  @keyframes sk-unfold { from { grid-template-rows: 0fr; opacity: 0; } to { grid-template-rows: 1fr; opacity: 1; } }
  @keyframes sk-fade { from { opacity: 0; } to { opacity: 1; } }
  @keyframes sk-grow { from { transform: scaleX(0); } to { transform: none; } }
  @keyframes sk-shimmer { to { transform: translateX(100%); } }
  @keyframes sk-toast { 0% { opacity: 0; transform: translate(-50%, 14px); } 7%, 90% { opacity: 1; transform: translate(-50%, 0); } 100% { opacity: 0; transform: translate(-50%, 8px); } }
  /* D6: candidates per room with a score (cards like Explore), derive/suggest, improve with a diff */
  .sk-candwrap { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; padding: 2px 2px 8px; margin: -2px; }   /* the whole tab scrolls as one page, the form never crowds the list out */
  .sk-candwrap > .sk-card { flex: none; } .sk-candwrap .sk-rows { overflow: visible; flex: none; }
  .sk-derive { padding: 18px 22px; gap: 12px; display: flex; flex-direction: column; flex: none; }
  .sk-derive textarea, .sk-src select, .sk-src input { box-sizing: border-box; padding: 10px 16px; border: 1px solid var(--d-line); background: var(--d-card2); color: var(--d-text); font: inherit; outline: none; transition: border-color var(--d-t-fast), box-shadow var(--d-t); }
  .sk-chatbox textarea { box-sizing: border-box; border: 1px solid var(--d-line); background: var(--d-card2); color: var(--d-text); font: inherit; outline: none; transition: border-color var(--d-t-fast), box-shadow var(--d-t); width: 100%; min-height: 62px; resize: vertical; border-radius: var(--d-r-lg); padding: 12px 16px; }
  .sk-chatbox textarea:focus { border-color: color-mix(in oklab, var(--d-accent) 60%, transparent); box-shadow: 0 0 0 4px color-mix(in oklab, var(--d-accent) 16%, transparent); }
  .sk-chatbox .acts { justify-content: flex-start; } .sk-or { margin: 14px 0 8px; display: flex; align-items: center; gap: 10px; color: var(--d-muted); font-size: .82em; } .sk-or::before, .sk-or::after { content: ''; flex: 1; height: 1px; background: var(--d-line); }
  .sk-derive textarea { width: 100%; min-height: 62px; resize: vertical; border-radius: var(--d-r-lg); padding: 12px 16px; }
  .sk-src select, .sk-src input { border-radius: var(--d-r-pill); }
  .sk-derive textarea:focus, .sk-src select:focus, .sk-src input:focus { border-color: color-mix(in oklab, var(--d-accent) 60%, transparent); box-shadow: 0 0 0 4px color-mix(in oklab, var(--d-accent) 16%, transparent); }
  .sk-src { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; } .sk-src input { flex: 1; min-width: 200px; }
  .sk-derive .r { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .sk-job { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; font-size: 14px; } .sk-job .q { font-weight: 600; }
  .sk-score { --p: 50; --sc: var(--d-amber); width: 44px; height: 44px; border-radius: 50%; flex: none; display: grid; place-items: center; position: relative;
    background: conic-gradient(var(--sc) calc(var(--p) * 1%), var(--d-hover) 0); font-weight: 750; font-size: 16px; transition: transform var(--d-t) var(--d-spring); }
  .sk-score::before { content: ""; position: absolute; inset: 5px; border-radius: 50%; background: var(--d-card2); } .sk-score b { position: relative; }
  .sk-score.hi { --sc: var(--d-ok); } .sk-score.lo { --sc: var(--d-muted); }
  .sk-row.on .sk-score, .sk-hd:hover .sk-score { transform: scale(1.08); }
  .sk-ul { margin: 0; padding-left: 18px; font-size: 14px; } .sk-ul li { margin: 3px 0; }
  .sk-cr { display: grid; grid-template-columns: 112px 1fr 22px; gap: 10px; align-items: center; font-size: 13.5px; color: var(--d-muted); } .sk-cr .sk-fit { margin: 5px 0; } .sk-cr em { font-style: normal; text-align: right; color: var(--d-text); font-variant-numeric: tabular-nums; }
  .sk-diff { margin: 10px 0; padding: 10px 0; border-radius: var(--d-r-md); background: var(--d-card2); border: 1px solid var(--d-line); font: 12.5px/1.5 ui-monospace, Consolas, monospace; max-height: 300px; overflow: auto; }
  .sk-diff span { display: block; padding: 0 14px; white-space: pre-wrap; word-break: break-word; }
  .sk-diff .a { background: color-mix(in oklab, var(--d-ok) 17%, transparent); } .sk-diff .d { background: color-mix(in oklab, var(--d-no) 17%, transparent); } .sk-diff .h { color: var(--d-accent); }
  .sk-box.wide { max-width: 760px; } .sk-box.wide .sk-kv { grid-template-columns: 110px 1fr; }
  .sk-acts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; align-items: center; }
  .sk-ft .sk-warn { font-size: 11.5px; font-weight: 600; padding: 2px 10px; border-radius: var(--d-r-pill); background: var(--d-amber-bg); color: var(--d-amber); }
  .sk-ft .sk-ok { font-size: 12.5px; }
  .sk-ft .sk-dim { font-size: 11.5px; font-weight: 600; padding: 2px 10px; border-radius: var(--d-r-pill); background: var(--d-hover); color: var(--d-muted); }
  .sk-row.sk-child { border-left: 3px solid color-mix(in oklab, var(--o, var(--d-accent)) 55%, transparent); }
  .sk-ft .sk-lv { font-size: 11px; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; padding: 2px 9px; border-radius: var(--d-r-pill); border: 1px solid var(--d-line); color: var(--d-muted); }
  .sk-case { margin: 6px 0; } .sk-case .h { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 13.5px; } .sk-case .h b { font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: var(--d-muted); } .sk-case .h span:nth-child(2) { flex: 1; min-width: 120px; } .sk-case .sk-path { margin: 4px 0 2px; }
  .sk-case-t { margin: 10px 0; border: 1px solid var(--d-line); border-radius: var(--d-r-md); background: var(--d-card2); } .sk-case-t > div { display: flex; gap: 10px; padding: 8px 14px; font-size: 13.5px; align-items: center; } .sk-case-t > div + div { border-top: 1px solid var(--d-line); } .sk-case-t b { font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: var(--d-muted); } .sk-case-t span { flex: 1; } .sk-case-t em { font-style: normal; font-weight: 700; } .sk-case-t .bad { background: var(--d-amber-bg); color: var(--d-amber); }
  .sk-warn-t { color: var(--d-amber); font-size: 13.5px; font-weight: 600; }
  .sk-pre { margin: 8px 0; padding: 10px 14px; border-radius: var(--d-r-md); background: var(--d-card2); border: 1px solid var(--d-line); font: 12px/1.5 ui-monospace, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 160px; overflow: auto; }
  @media (prefers-reduced-motion: reduce) { #skillsView, #skillsView *, #skillsView::before { animation-duration: .01ms !important; animation-delay: 0s !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; } }
  @media (max-width: 820px) {
    #skillsView { padding: 12px; gap: 10px; }
    .sk-pill { padding: 6px 13px; font-size: 14px; }
    .sk-explore { padding: 12px 12px 4px; } .sk-bar input { width: 100%; }
    .sk-rows { grid-template-columns: minmax(0, 1fr); } .sk-row.sk-child { margin-left: calc(var(--dep, 0) * 16px); } .sk-cols { padding: 2px 14px 16px; }
    .sk-pad { padding: 16px; }
    .sk-grid { grid-template-columns: 1fr; }
  }`;
  document.head.appendChild(css);

  const main = document.createElement('main');
  main.id = 'skillsView';
  document.body.appendChild(main);

    const ago = ts => {
    if (!ts) return '';
    const s = Math.max(0, Date.now() / 1000 - ts);
    return s < 90 ? I18N.text('skillsv.agoNow') : s < 5400 ? I18N.text('skillsv.agoMin', {n: Math.round(s / 60)}) : s < 129600 ? I18N.text('skillsv.agoHour', {n: Math.round(s / 3600)}) : I18N.text('skillsv.agoDay', {n: Math.round(s / 86400)});
  };
  // the entry animations run only when the user acts (tab, filter chip, a pick), never on the 4 s poll
  let animT = 0;
  const animate = (c = 'sk-anim') => { main.classList.remove('sk-anim', 'sk-animd'); void main.offsetWidth; main.classList.add(c); clearTimeout(animT); animT = setTimeout(() => main.classList.remove('sk-anim', 'sk-animd'), 900); };
  function pick(id) {                                  // a card: it opens in place with its detail (a second click closes it), the others stay still
    SK.sel = SK.sel === id ? null : id; keep(); animate('sk-animd');
    fillRows();
    const on = main.querySelector('.sk-row.on'), hd = on ? on.querySelector('.sk-hd') : main.querySelector(`.sk-hd[data-sel="${CSS.escape(id)}"]`);
    if (hd) hd.focus({preventScroll: true});
    if (on && on.scrollIntoView) on.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }
  function toast(text) {
    if (!text) return;
    const el = document.createElement('div'); el.className = 'sk-toast'; el.textContent = text;
    main.appendChild(el); setTimeout(() => el.remove(), 3800);
  }

  // ---- data ----
  // D8 made-up fields (names of CORE's contract v4): checks, verified, usage, levels, cases, activation
  const V = (state, at, exit) => ({state, ok: state === 'verified', at, exit, hash: 'ab12cd34ef56', skill_hash: '0123456789ab'});
  function mockD8(d, now) {
    const S = n => d.skills.find(x => x.name === n), C = n => d.candidates.find(x => x.name === n);
    const ck = cmd => ({cmd, cwd: null, timeout: 110});
    d.skills.concat(d.candidates).forEach(x => Object.assign(x, {check: null, verified: V('unverified', null, null)}));
    const U = (count, rooms, ok, fail, last, log, unused) => ({count, rooms, last, ok, fail, unused_rooms: unused ? 4 : 0, scanned_rooms: 4, unused: !!unused, log: log || []});
    d.skills.forEach(x => { x.usage = U(0, 0, 0, 0, null, [], false); x.usage.scanned_rooms = 2; });
    S('caveman').usage = U(7, 3, 5, 2, now - 1800, [{room: 'stanza-skill', agent: 'UI', task: 'T23', ok: true, at: now - 1800}, {room: 'stanza-skill', agent: 'CORE', task: 'T22', ok: true, at: now - 7200}, {room: 'kernel-gtx1080', agent: 'VOXEL', task: 'T4', ok: false, at: now - 86400}, {room: 'kernel-gtx1080', agent: 'VOXEL', task: null, ok: null, at: now - 90000}]);
    d.skills.concat(d.candidates).forEach(x => { x.cases = []; });
    const cs = (id, task, cmd) => ({id, task, check: ck(cmd)});
    S('run').cases = [cs('c1', 'a plain launch shows the window', 'node t/launch.mjs'), cs('c2', 'a second launch reuses the server', 'node t/relaunch.mjs')];
    C('pdf-merge').cases = [cs('c1', 'merge two files in page order', 'python tests/merge_order.py'), cs('c2', 'keep the bookmarks', 'python tests/bookmarks.py'), cs('c3', 'an encrypted input stops and asks', 'python tests/encrypted.py')];
    d.skills.forEach(x => { x.measured = null; x.activation = null; });
    S('caveman').activation = {right: 5, wrong: 1, total: 6, at: now - 3600, suggestion: 'Use when the user asks for shorter replies. Do NOT use for code, commit messages or file contents.'};
    S('caveman').measured = {tokens_saved: 3100, steps_saved: -2, basis: 'Mean of 5 tasks with the skill against 8 without, in the same rooms. A comparison, not proof of cause.', with: {n: 5, tokens_mean: 8200, steps_mean: 14}, without: {n: 8, tokens_mean: 11300, steps_mean: 12}, min_n: 3, at: now - 3600};
    S('ponytail').measured = {tokens_saved: null, steps_saved: null, basis: 'Need 3 tasks with the skill and 3 without: 2 with, 6 without.', with: {n: 2}, without: {n: 6}, min_n: 3, at: now - 3600};
    Object.assign(S('godot-master'), {level: 'strategy', children: [S('run').id]}); Object.assign(S('run'), {level: 'function', parent: S('godot-master').id, children: [S('pdf-merge').id]}); Object.assign(S('pdf-merge'), {level: 'step', parent: S('run').id});
    d.skills.forEach(x => { x.level = x.level || null; x.parent = x.parent || null; x.children = x.children || []; });
    S('ponytail').usage = U(2, 1, 2, 0, now - 40000, [{room: 'stanza-skill', agent: 'CORE', task: 'T25', ok: true, at: now - 40000}]);
    S('godot-master').usage = U(3, 1, 1, 2, now - 200000, []);
    ['aws-cdk', 'run', 'artifact-design'].forEach(n => { S(n).usage = U(0, 0, 0, 0, null, [], true); });
    S('ponytail').check = ck('python scripts/tools/test_ponytail.py'); S('ponytail').verified = V('verified', now - 7200, 0);
    S('godot-master').check = ck('godot --headless --check-only -s res://tests/run.gd'); S('godot-master').verified = V('failed', now - 3000, 2);
    S('run').check = ck('node scripts/tools/smoke_run.mjs');
    C('cuda-graphs-pascal').check = ck('python bench/check_graphs.py --sm 61');
    C('pdf-merge').check = ck('python tests/merge_order.py'); C('pdf-merge').verified = V('verified', now - 600, 0);
  }
  const mockData = () => {
    const now = Math.floor(Date.now() / 1000);
    const sk = (origin, name, brief, plugin, agents, adv) => ({id: `${origin}:${plugin || '-'}:${name}`, name, brief, description: brief + ' ' + brief, origin,
      plugin: plugin ? plugin + '@' + plugin : null, version: plugin ? '1.2.0' : null, path: `C:/Users/me/.claude/skills/${name}/SKILL.md`,
      advised: adv ? [{to: adv, at: now - 600}] : [], agents, updatable: !!plugin});
    const d = {v: 1, at: now, origins: ['user', 'project', 'plugin', 'added'], skills: [
      sk('plugin', 'caveman', 'Ultra-terse reply style, keeps every fact.', 'caveman', ['CORE', 'UI', 'VOXEL'], 'UI'),
      sk('plugin', 'ponytail', 'Smallest change that fully solves the task.', 'ponytail', ['CORE']),
      sk('plugin', 'artifact-design', 'Design guidance for published pages.', 'artifacts', []),
      sk('user', 'aws-cdk', 'Author and deploy AWS CDK stacks.', null, []),
      sk('user', 'godot-master', 'Godot 4.7 expert library.', null, ['VOXEL']),
      sk('project', 'run', 'Launch the app and see a change working.', null, []),
      sk('added', 'pdf-merge', 'Merge several PDF files into one.', null, [])],
      agents: [{name: 'CORE', type: 'room-agent', skills: [{id: 'plugin:caveman:caveman', via: ['brief', 'used'], count: 3}, {id: 'plugin:ponytail:ponytail', via: ['type'], count: 0}]},
        {name: 'UI', type: 'room-agent', skills: [{id: 'plugin:caveman:caveman', via: ['brief'], count: 0}]},
        {name: 'VOXEL', type: 'room-agent', skills: [{id: 'plugin:caveman:caveman', via: ['brief'], count: 1}, {id: 'user:-:godot-master', via: ['used'], count: 2}]},
        {name: 'SEARCHER', type: 'room-agent', skills: []}],
      searcher: {present: true, name: 'SEARCHER', busy: false},
      rooms: [{id: 'a1b2c3d4', name: 'stanza-skill', current: true, n: 3}, {id: '9f8e7d6c', name: 'kernel-gtx1080', current: false, n: 2}],
      candidates: [
        {id: 'cand:9f8e7d6c:cuda-graphs-pascal', room: '9f8e7d6c', name: 'cuda-graphs-pascal', score: 9, kind: 'derive', tasks: ['T4', 'T9'], at: now - 3600, req: 'r4', status: 'new', improves: null, covered_by: null, tokens: 610, tokens_saved: 4200,
          why: 'The same 6 build and bench steps repeated in 11 runs; one wrong flag costs a full rebuild.', criteria: {recurrence: 9, error_cost: 8, specificity: 9, overlap: 2, weight: 6},
          repeated: ['configure with -DGGML_CUDA_GRAPHS=ON', 'run the bench at 3 batch sizes'], hard: ['sm_61 has no tensor cores: skip the fp16 path']},
        {id: 'cand:9f8e7d6c:kernel-bench-table', room: '9f8e7d6c', name: 'kernel-bench-table', score: 7, kind: 'suggest', tasks: ['T2'], at: now - 3500, req: 'r6', status: 'new', improves: null, covered_by: null, tokens: 260, tokens_saved: null,
          why: 'Every run ends with the same markdown table, built by hand.', criteria: {recurrence: 8, error_cost: 3, specificity: 7, overlap: 3, weight: 4}, repeated: ['paste the numbers in the table'], hard: []},
        {id: 'cand:a1b2c3d4:pdf-merge', room: 'a1b2c3d4', name: 'pdf-merge', score: 6, kind: 'improve', tasks: [], at: now - 900, req: 'r7', status: 'new', improves: 'added:-:pdf-merge', covered_by: null, tokens: 420, tokens_saved: 900,
          why: 'Rewrite of pdf-merge with the failure cases found today.', criteria: {recurrence: 6, error_cost: 6, specificity: 7, overlap: 5, weight: 5}, repeated: ['merge in page order'], hard: ['encrypted input']},
        {id: 'cand:a1b2c3d4:room-merge-order', room: 'a1b2c3d4', name: 'room-merge-order', score: 4, kind: 'suggest', tasks: ['T6'], at: now - 800, req: 'r6', status: 'new', improves: null, covered_by: 'user:-:aws-cdk', tokens: 180, tokens_saved: null,
          why: 'Useful once, specific to this room.', criteria: {recurrence: 3, error_cost: 5, specificity: 7, overlap: 4, weight: 3}, repeated: [], hard: ['merge core before ui']},
        {id: 'cand:a1b2c3d4:commit-style', room: 'a1b2c3d4', name: 'commit-style', score: 3, kind: 'derive', tasks: [], at: now - 700, req: 'r4', status: 'added', improves: null, covered_by: null, tokens: 120, tokens_saved: null,
          why: 'Short commit messages in the same shape.', criteria: {recurrence: 4, error_cost: 1, specificity: 3, overlap: 6, weight: 2}, repeated: [], hard: []}],
      requests: [{req: 'r1', q: 'pdf merge', by: 'USER', at: now - 300, state: 'done', file: 'research/skills-r1.json', cards: [
        {name: 'pdf-merge', what: 'Merge PDF files into one.', source: 'github.com/x/y', url: 'https://github.com/x/y', added: false, install_hint: 'copy folder into skills', trust: 'repo 1.2k stars', fit: 0.8},
        {name: 'pdf-tools', what: 'Split, merge, rotate PDFs.', source: 'github.com/a/b', url: 'https://github.com/a/b', added: true, install_hint: '', trust: '', fit: 0.6}]},
        {req: 'r2', q: 'video edit', by: 'USER', at: now - 60, state: 'paused', file: null, cards: []},
        {req: 'r8', kind: 'derive', q: 'kernel routes I tried', by: 'USER', at: now - 1200, state: 'failed', log: 'skills-temp/r8.log', file: null, cards: []},
        {req: 'r9', kind: 'suggest', q: 'suggestions from kernel-gtx1080', by: 'USER', at: now - 90, state: 'running', file: null, cards: []}]};
    mockD8(d, now);
    return d;
  };
  const MOCK_DIFF = '--- added:-:pdf-merge\n+++ candidate\n@@ -1,6 +1,8 @@\n # pdf-merge\n \n-Merge PDF files with pdftk.\n+Merge PDF files in page order with pypdf.\n+If an input is encrypted, stop and ask for the password.\n \n ## Steps\n-1. list the files\n-2. run pdftk\n+1. list the files and sort them by name\n+2. merge with PdfWriter, keep the bookmarks\n+3. check the page count of the result\n';
  // the made-up answers of ?mock=1: a preview first, then the same call with confirm; nothing leaves the page
  function mockAct(b) {
    const D = SK.mock || (SK.mock = mockData()), c = b.id && D.candidates.find(x => x.id === b.id);
    if (b.action === 'diff') return {ok: true, diff: MOCK_DIFF, added: 5, removed: 3, target: c && c.improves ? {id: c.improves, path: 'C:/Users/me/.claude/skills/pdf-merge/SKILL.md', origin: 'added', copy: false} : null};
    if (b.action === 'update_check') return {ok: true, update: b.skill.includes('caveman') ? {installed: '1.2.0', available: '1.3.0', newer: true, source: 'plugin caveman@caveman', changes: 'Adds the lite level and fixes the ultra trigger words.', checked_at: Date.now() / 1000}
      : {installed: '1.2.0', available: '1.2.0', newer: false, source: 'plugin', checked_at: Date.now() / 1000}};
    if (b.action === 'update_apply') { if (!b.confirm) return {ok: true, preview: {name: (byId(b.skill) || {}).name, from: 'marketplace caveman', to: 'C:/Users/me/.claude/plugins/cache/caveman/1.3.0', installed: '1.2.0', available: '1.3.0'}}; load(true); return {ok: true}; }
    if (b.action === 'measure') { const x = D.skills.find(y => y.id === b.id); if (x && !x.measured) x.measured = {tokens_saved: 2400, steps_saved: 3, basis: 'Mean of 5 tasks with the skill against 8 without, in the same rooms. A comparison, not proof of cause.', with: {n: 5, tokens_mean: 9000, steps_mean: 12}, without: {n: 8, tokens_mean: 11400, steps_mean: 15}, min_n: 3, at: Date.now() / 1000}; return {ok: true, measured: x && x.measured}; }
    if (b.action === 'level_set') { const x = D.skills.find(y => y.id === b.id); if (x) { x.level = b.level; x.parent = b.parent; D.skills.forEach(y => { y.children = D.skills.filter(z => z.parent === y.id).map(z => z.id); }); } load(true); return {ok: true}; }
    if (b.action === 'activation_check') return {ok: true, check: {positives: 2, negatives: 0, has_exclusion: false, closeness: 0.12, advice: 'The description says when to use it but never when not to. Add a "Do NOT use for" clause.', suggestion: 'Do NOT use for code, commit messages or file contents.', confused_with: [{id: 'plugin:ponytail:ponytail', name: 'ponytail', overlap: 0.31}]}};
    if (b.action === 'activation_test') {
      if (!b.confirm) return {ok: true, preview: {kind: 'activation', name: 'SKILLWORK', task: 'Write 3 requests that must activate ' + ((byId(b.id) || {}).name || '') + ' and 3 near misses, and say which skill each would pick', prompts: [], n: 6, reads: ['name + description of every skill'], writes: ['skills-jobs/r11.activation.json'], budget_usd: 1, est_tokens: 30000, est_usd: 1}};
      D.requests.push({req: 'r11', kind: 'activation', skill: b.id, q: '', by: 'USER', at: Math.floor(Date.now() / 1000), state: 'running', cards: []});
      setTimeout(() => { const x = D.skills.find(y => y.id === b.id); D.requests = D.requests.filter(q => q.req !== 'r11'); if (x) x.activation = {right: 4, wrong: 2, total: 6, at: Math.floor(Date.now() / 1000), suggestion: 'Use when ... Do NOT use for ...'}; load(true); }, 5000);
      load(true); return {ok: true, req: 'r11'};
    }
    if (b.action === 'cases_set') { const x = c || D.skills.find(y => y.id === b.id); if (x) x.cases = (b.cases || []).map((k, i) => ({id: 'c' + (i + 1), task: k.task, check: k.check})); load(true); return {ok: true}; }
    if (b.action === 'cases_run') {
      const x = c || D.skills.find(y => y.id === b.id), list = (x && x.cases) || [];
      if (!b.confirm) return {ok: true, preview: {name: x && x.name, cases: list.map(k => ({id: k.id, check: k.check})), cwd: 'C:/Users/me/.claude/skills/' + (x && x.name), timeout: 110}};
      return {ok: true, results: list.map((k, i) => ({id: k.id, passed: i !== 1, exit: i !== 1 ? 0 : 1})), at: Date.now() / 1000};
    }
    if (b.action === 'usage_scan') return {ok: true, scanned: {rooms: 4, transcripts: 12, new: 3}, complete: true};
    if (b.action === 'check_run') {
      const x = c || byId(b.skill || b.id) || D.skills.find(y => y.id === (b.skill || b.id));
      if (!x || !x.check) return {ok: false, error: 'no check'};
      if (!b.confirm) return {ok: true, preview: {name: x.name, what: c ? 'candidate' : 'skill', cmd: x.check.cmd, cwd: x.check.cwd || 'C:/Users/me/.claude/skills/' + x.name, timeout: x.check.timeout, note: 'runs on your computer'}};
      const pass = !/godot/.test(x.name); x.verified = V(pass ? 'verified' : 'failed', Math.floor(Date.now() / 1000), pass ? 0 : 2); load(true);
      return {ok: true, passed: pass, exit: pass ? 0 : 2, out: pass ? '12 passed in 0.8s' : 'FAILED tests/run.gd:41  expected 3, got 2', hash: 'ab12cd34ef56', at: Date.now() / 1000, verified: x.verified};
    }
    if (b.action === 'dismiss') { if (c) c.status = 'dismissed'; load(true); return {ok: true}; }
    const chat = b.source && b.source.chat;
    const pre = {derive: () => chat ? {kind: 'derive', name: 'LEAD', task: 'Derive skills from the current conversation' + (b.desc ? ': ' + b.desc : ''), reads: ['the current conversation'], writes: ['skills-candidates/**']}
      : {kind: 'derive', name: 'SKILLWORK', task: 'Derive a skill from: ' + (b.desc || ''), reads: ['skills-jobs/r10.input.md'], writes: ['skills-candidates/**'], budget_usd: 1},
      suggest: () => ({kind: 'suggest', name: 'SKILLWORK', task: 'Suggest 3 to 5 skills from the source', reads: ['skills-jobs/r10.input.md'], writes: ['skills-candidates/**'], budget_usd: 1}),
      improve: () => ({kind: 'improve', name: 'SKILLWORK', task: 'Rewrite ' + b.skill + ' with the source', reads: ['skills-jobs/r10.input.md'], writes: ['skills-candidates/**'], budget_usd: 2,
        target: {id: b.skill, path: 'C:/Users/me/.claude/skills/x/SKILL.md', origin: 'plugin', copy: (byId(b.skill) || {}).origin === 'plugin'}}),
      promote: () => ({gate: c && c.improves && c.cases.length ? c.cases.map(k => ({id: k.id, cmd: k.check.cmd, cwd: null, timeout: 110})).concat([{id: 'check', cmd: c.check.cmd, cwd: null, timeout: 110}]) : undefined, runs: c && c.cases ? 1 + 2 * c.cases.length : undefined, unverified: !!c && c.verified.state !== 'verified', name: c ? c.name : '?', from: 'ROOM/skills-candidates/' + (c ? c.name : ''), to: 'C:/Users/me/.claude/skills/' + (c ? c.name : ''), backup: c && c.improves ? 'C:/Users/me/.claude/skills-backup/' + c.name + '/20261114-191500' : null, replaces: !!(c && c.improves), diff: c && c.improves ? MOCK_DIFF : undefined})}[b.action];
    if (!pre) { toast(I18N.text('skillsv.mockDone')); return {ok: true, mock: true}; }
    if (!b.confirm) return {ok: true, preview: pre()};
    if (b.action === 'promote' && c && c.verified.state !== 'verified' && !b.unverified_ok) return {ok: false, needs: 'unverified_ok', error: 'unverified'};
    if (b.action === 'promote' && c && c.improves && c.cases.length && !c._tried) {
      c._tried = true;
      return {ok: false, reverted: true, error: 'case c2 got worse; the old folder is back', cases_result: [{id: 'c1', before: false, after: true}, {id: 'c2', before: true, after: false}, {id: 'c3', before: true, after: true}], better: 1, worse: 1};
    }
    if (b.action === 'promote' && c && c.improves && c.cases.length) { c.status = 'added'; load(true); return {ok: true, cases_result: [{id: 'c1', before: false, after: true}, {id: 'c2', before: true, after: true}, {id: 'c3', before: true, after: true}], better: 1, worse: 0}; }
    if (b.action === 'promote' && c) c.status = 'added';
    load(true); return {ok: true, mock: true};
  }
  async function load(force) {
    try {
      let d;
      if (MOCK) d = SK.mock || (SK.mock = mockData());
      else {
        const r = await fetch('skills.json');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        d = await r.json();
      }
      SK.err = '';
      const h = JSON.stringify([d.skills, d.agents, d.searcher, d.requests, d.rooms, d.candidates]);
      if (!force && h === SK.hash) return;
      SK.hash = h; SK.data = d;
    } catch (e) { SK.err = String(e); SK.data = SK.data || null; }
    refresh();
  }
  async function act(body) {
    if (MOCK) return mockAct(body);
    try {
      const r = await fetch('skills/do', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      const txt = await r.text();
      let j = {}; try { j = JSON.parse(txt); } catch (e) {}
      if (j.need) return j;
      if (j.reverted) { toast(I18N.text('skillsv.err', {why: j.error || ''})); return j; }   // an improvement the gate refused: the answer still carries the cases
      if (!r.ok || j.ok === false || j.error) { toast(I18N.text('skillsv.err', {why: j.error || txt || r.status})); return null; }
      return j;
    } catch (e) { toast(I18N.text('skillsv.err', {why: String(e)})); return null; }
  }

  // ---- helpers ----
  const skills = () => (SK.data && SK.data.skills) || [];
  const byId = id => skills().find(s => s.id === id);
  const agentsOf = () => (SK.data && SK.data.agents) || [];
  const OT = () => ({user: I18N.text('skillsv.o.user'), project: I18N.text('skillsv.o.project'), plugin: I18N.text('skillsv.o.plugin'), added: I18N.text('skillsv.o.added'), account: I18N.text('skillsv.o.account'), builtin: I18N.text('skillsv.o.builtin')});
  const originName = o => OT()[o] || o;
  const pname = s => String((s && s.plugin) || '').split('@')[0];
  const oTag = (o, s) => `<span class="sk-o" style="--o:var(--o-${esc(o)})">${esc(o === 'plugin' && pname(s) ? I18N.text('skillsv.o.pluginNamed', {name: pname(s)}) : originName(o))}</span>`;
  const OX = () => ({'': I18N.text('skillsv.ox.all'), user: I18N.text('skillsv.ox.user'), project: I18N.text('skillsv.ox.project'), plugin: I18N.text('skillsv.ox.plugin'), added: I18N.text('skillsv.ox.added'), account: I18N.text('skillsv.ox.account'), builtin: I18N.text('skillsv.ox.builtin')});
  function fromText(s) {                               // "where it comes from", in plain words, for the opened card
    const m = String(s.plugin || '').split('@'), so = s.source && typeof s.source === 'object' ? s.source : null;   // so: the server's own words (D7: kind, label, url, version)
    if (so && so.kind === 'repo') return I18N.text('skillsv.from.repo', {label: so.label || '?'});
    if (so && so.kind === 'local') return I18N.text('skillsv.from.local');
    if (so && so.kind === 'desktop') return I18N.text('skillsv.from.desktop');
    if (so && so.kind === 'marketplace') { const l = String(so.label || '').split('@'); return I18N.text('skillsv.from.plugin', {name: l[0] || m[0] || '?', market: l[1] || m[1] || '?', version: so.version || s.version || '?'}); }
    return s.origin === 'plugin' ? I18N.text('skillsv.from.plugin', {name: m[0] || '?', market: m[1] || '?', version: s.version || '?'})
      : s.origin === 'user' ? I18N.text('skillsv.from.user') : s.origin === 'project' ? I18N.text('skillsv.from.project') : s.origin === 'added' ? I18N.text('skillsv.from.added')
      : s.origin === 'account' ? I18N.text('skillsv.from.account') : s.origin === 'builtin' ? I18N.text('skillsv.from.builtin') : s.origin;
  }
  // D8 point 1: "verified" = its check passed (and when); "not verified" = no check, or never run. The check is a command on the user's computer: it runs only after a confirm.
  const isVer = x => !!(x && x.verified && x.verified.state === 'verified');
  const verState = x => (x && x.verified && x.verified.state) || 'unverified';
  function vTag(x, always) {                           // skills show it once they have a check, candidates always
    if (!x || (!always && !x.check && verState(x) === 'unverified')) return '';
    const st = verState(x), v = x.verified || {}, t = v.at ? ` title="${esc(I18N.text('skillsv.ver.at', {when: ago(v.at)}))}"` : '';
    return st === 'verified' ? `<span class="sk-ok"${t}>${IC.check} ${esc(I18N.text('skillsv.ver.ok'))}</span>`
      : st === 'failed' ? `<span class="sk-warn"${t}>${esc(I18N.text('skillsv.ver.failed'))}</span>` : `<span class="sk-dim">${esc(I18N.text('skillsv.ver.not'))}</span>`;
  }
  function chkHtml(x, cand) {                          // the section in an opened card: the command in full, the state, "run" (asks first), what the last run printed
    if (!x || (!x.check && verState(x) === 'unverified' && !cand)) return '';
    const k = x.check, v = x.verified || {}, st = verState(x), o = SK.chk[x.id];
    const state = st === 'verified' ? `<div class="sk-ok">${IC.check} ${esc(I18N.text('skillsv.ver.passedAt', {when: ago(v.at)}))}</div>`
      : st === 'failed' ? `<div class="sk-warn-t">${esc(I18N.text('skillsv.ver.failedAt', {when: ago(v.at), exit: v.exit == null ? I18N.text('skillsv.ver.timeout') : v.exit}))}</div>`
      : `<div class="sk-sub">${esc(k ? (v.at ? I18N.text('skillsv.ver.changed') : I18N.text('skillsv.ver.neverRun')) : I18N.text('skillsv.ver.noCheck'))}</div>`;
    return `<div class="sk-sec">${esc(I18N.text('skillsv.ver.head'))}</div>${state}`
      + (k ? `<div class="sk-path">${esc(k.cmd)}</div><div class="sk-sub">${esc(I18N.text('skillsv.ver.where', {cwd: k.cwd || I18N.text('skillsv.ver.here'), s: k.timeout || '?'}))}</div>`
        + `<div class="sk-acts"><button class="sk-btn small" data-act="chkrun" data-cid="${esc(x.id)}">${esc(I18N.text('skillsv.ver.run'))}</button></div>` : '')
      + (o && o.out ? `<div class="sk-pre">${esc(o.out)}</div>` : '');
  }
  // D8 point 3: where and how a skill was used, read from the transcripts (the server counts; "never used" is only a hint, nothing is removed on its own)
  function useHtml(s) {
    const u = s.usage; if (!u) return '';
    const O = o => o === true ? I18N.text('skillsv.use.ok') : o === false ? I18N.text('skillsv.use.bad') : I18N.text('skillsv.use.nt');
    const head = u.count ? `<div class="sk-desc" style="margin:0 0 6px">${esc(I18N.text('skillsv.use.count', {n: u.count, rooms: u.rooms}))} ${esc(I18N.text('skillsv.use.outcome', {ok: u.ok, fail: u.fail}))}</div><div class="sk-sub">${esc(I18N.text('skillsv.use.last', {when: ago(u.last)}))}</div>`
      : `<div class="sk-sub">${esc(u.scanned_rooms ? I18N.text('skillsv.use.never', {n: u.scanned_rooms}) : I18N.text('skillsv.use.none'))}</div>` + (u.unused ? `<div class="sk-note">${esc(I18N.text('skillsv.use.unusedNote'))}</div>` : '');
    const log = (u.log || []).slice(0, 8).map(l => `<li>${esc(l.room || '?')} · ${esc(l.task || I18N.text('skillsv.use.noTask'))} · ${esc(l.agent || '?')} · ${esc(O(l.ok))} · ${esc(ago(l.at))}</li>`).join('');
    return `<div class="sk-sec">${esc(I18N.text('skillsv.use.head'))}</div>${head}${log ? `<ul class="sk-ul">${log}</ul>` : ''}`
      + `<div class="sk-acts"><button class="sk-btn small" data-act="usescan"${SK.scan === '...' ? ' disabled' : ''}>${esc(I18N.text('skillsv.use.scan'))}</button></div>` + (SK.scan && SK.scan !== '...' ? `<div class="sk-sub">${esc(SK.scan)}</div>` : '');
  }
  // D8 point 2: a saving is shown only when it was measured (tasks with the skill against tasks without); never an estimate
  function measHtml(s) {
    const m = s.measured, n = v => Math.abs(Math.round(v)).toLocaleString();
    const body = !m ? `<div class="sk-sub">${esc(I18N.text('skillsv.meas.none'))}</div>`
      : (m.tokens_saved != null || m.steps_saved != null
        ? `<div class="sk-who">${m.tokens_saved != null ? `<span class="w">${esc(m.tokens_saved >= 0 ? I18N.text('skillsv.meas.saves', {n: n(m.tokens_saved)}) : I18N.text('skillsv.meas.costs', {n: n(m.tokens_saved)}))}</span>` : ''}`
          + `${m.steps_saved != null ? `<span class="w">${esc(m.steps_saved >= 0 ? I18N.text('skillsv.meas.fewer', {n: n(m.steps_saved)}) : I18N.text('skillsv.meas.more', {n: n(m.steps_saved)}))}</span>` : ''}</div>`
          + (m.with && m.without ? `<div class="sk-sub">${esc(I18N.text('skillsv.meas.on', {a: m.with.n, b: m.without.n}))}</div>` : '') : '')
      + (m && m.basis ? `<div class="sk-sub">${esc(m.basis)}</div>` : '');
    return `<div class="sk-sec">${esc(I18N.text('skillsv.meas.head'))}</div>${body}<div class="sk-acts"><button class="sk-btn small" data-act="measure">${esc(I18N.text('skillsv.meas.btn'))}</button></div><div class="sk-note">${esc(I18N.text('skillsv.meas.note'))}</div>`;
  }
  // D8 point 4: does the description make the skill fire when it should, and only then? Phase 1 reads the description (free, local); phase 2 asks the model (costs tokens, preview with the cost first)
  function actHtml(s) {
    const a = SK.act[s.id] || {}, d = a.data, r = s.activation, pend = ((SK.data && SK.data.requests) || []).find(q => q.kind === 'activation' && q.skill === s.id && (q.state === 'pending' || q.state === 'running')), bad = ((SK.data && SK.data.requests) || []).find(q => q.kind === 'activation' && q.skill === s.id && q.state === 'failed');
    const free = a.busy ? `<div class="sk-sub">${esc(I18N.text('skillsv.act.checking'))}</div>` : !d ? '' :
      `<div class="sk-who"><span class="w">${esc(I18N.text('skillsv.act.pos'))}<small>${esc(d.positives)}</small></span><span class="w">${esc(I18N.text('skillsv.act.neg'))}<small>${esc(d.negatives)}</small></span><span class="w">${esc(I18N.text('skillsv.act.close'))}<small>${Math.round((Number(d.closeness) || 0) * 100)}%</small></span></div>`
      + (d.has_exclusion ? '' : `<div class="sk-warn-t">${esc(I18N.text('skillsv.act.noExcl'))}</div>`) + (d.advice ? `<div class="sk-desc" style="margin:6px 0">${esc(d.advice)}</div>` : '')
      + (d.suggestion ? `<div class="sk-sub">${esc(I18N.text('skillsv.act.suggest'))}</div><div class="sk-path">${esc(d.suggestion)}</div>` : '')
      + ((d.confused_with || []).length ? `<div class="sk-sub">${esc(I18N.text('skillsv.act.confused'))}</div><div class="sk-who">${d.confused_with.map(c => `<button class="w sk-who-b" data-goto="${esc(c.id || '')}"${c.id ? '' : ' disabled'}>${esc(c.name)}<small>${Math.round((Number(c.overlap) || 0) * 100)}%</small></button>`).join('')}</div>` : '');
    const model = pend ? `<div class="sk-sub">${esc(I18N.text('skillsv.act.running'))}</div>` : bad ? `<div class="sk-warn-t">${esc(I18N.text('skillsv.act.failed'))}</div>` : '';
    const res = r && r.total ? `<div class="sk-sec" style="margin-top:14px">${esc(I18N.text('skillsv.act.result'))}</div><div class="sk-who"><span class="w ${r.wrong ? '' : 'ok'}">${esc(I18N.text('skillsv.act.right', {a: r.right, t: r.total}))}</span>${r.wrong ? `<span class="w">${esc(I18N.text('skillsv.act.wrong', {n: r.wrong}))}</span>` : ''}</div><div class="sk-sub">${esc(ago(r.at))}</div>`
      + (r.suggestion ? `<div class="sk-sub">${esc(I18N.text('skillsv.act.betterDesc'))}</div><div class="sk-path">${esc(r.suggestion)}</div>` : '') : '';
    return `<div class="sk-sec">${esc(I18N.text('skillsv.act.head'))}</div><div class="sk-src"><button class="sk-btn small" data-act="actcheck"${a.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.act.check'))}</button>`
      + `<button class="sk-btn small" data-act="acttest"${pend ? ' disabled' : ''}>${esc(I18N.text('skillsv.act.test'))}</button></div>${free}${model}${res}<div class="sk-note">${esc(I18N.text('skillsv.act.note'))}</div>`;
  }
  // D8 point 6: nearby tasks, each with its own check. An improvement is kept only if no case that passed before fails after (our rule, stricter than the paper's). A case is a command that proves it.
  const MAXCASES = 4;
  function casesHtml(x) {
    const cs = x.cases || [], res = (SK.cres[x.id] || {}).results || [], full = cs.length >= MAXCASES;
    const rows = cs.map((c, i) => { const r = res.find(y => y.id === c.id);
      return `<div class="sk-case"><div class="h"><b>${esc(c.id)}</b><span>${esc(c.task)}</span>${r ? (r.passed ? `<span class="sk-ok">${IC.check} ${esc(I18N.text('skillsv.cases.pass'))}</span>` : `<span class="sk-warn-t">${esc(I18N.text('skillsv.cases.fail'))}</span>`) : ''}`
        + `<button class="sk-btn small" data-act="casedel" data-cid="${esc(x.id)}" data-i="${i}" aria-label="${esc(I18N.text('skillsv.cases.del'))}">&times;</button></div><div class="sk-path">${esc(c.check && c.check.cmd)}</div></div>`; }).join('');
    return `<div class="sk-sec">${esc(I18N.text('skillsv.cases.head'))}</div>` + (rows || `<div class="sk-sub">${esc(I18N.text('skillsv.cases.none'))}</div>`)
      + (full ? '' : `<div class="sk-src"><input id="skCaseTask" type="text" maxlength="160" placeholder="${esc(I18N.text('skillsv.cases.task'))}"><input id="skCaseCmd" type="text" maxlength="400" placeholder="${esc(I18N.text('skillsv.cases.cmd'))}"><button class="sk-btn small" data-act="caseadd" data-cid="${esc(x.id)}">${esc(I18N.text('skillsv.cases.add'))}</button></div>`)
      + (cs.length ? `<div class="sk-acts"><button class="sk-btn small" data-act="casesrun" data-cid="${esc(x.id)}">${esc(I18N.text('skillsv.cases.run'))}</button></div>` : '')
      + `<div class="sk-note">${esc(I18N.text('skillsv.cases.note', {k: MAXCASES}))}</div>`;
  }
  // the paper's utility, as the server computes it: the mean of the per-case changes (here -1, 0 or +1). Informative: the rule that decides is "no case gets worse"
  const utility = rs => rs.length ? rs.reduce((a, r) => a + (r.after ? 1 : 0) - (r.before ? 1 : 0), 0) / rs.length : 0;
  function lvlHtml(s) {                                // where it sits in the tree, and a way to set it (the server checks: parent strictly higher, no cycle)
    const par = s.parent && byId(s.parent), kids = (s.children || []).map(byId).filter(Boolean);
    const opt = (v, t, cur) => `<option value="${esc(v)}"${v === cur ? ' selected' : ''}>${esc(t)}</option>`;
    return `<div class="sk-sec">${esc(I18N.text('skillsv.lv.head'))}</div>`
      + (par ? `<div class="sk-sub">${esc(I18N.text('skillsv.lv.under'))}</div><div class="sk-who"><button class="w sk-who-b" data-goto="${esc(par.id)}">${esc(par.name)}<small>${esc(LV()[par.level] || '')}</small></button></div>` : '')
      + (kids.length ? `<div class="sk-who">${kids.map(k => `<button class="w sk-who-b" data-goto="${esc(k.id)}">${esc(k.name)}<small>${esc(LV()[k.level] || '')}</small></button>`).join('')}</div>` : '')
      + `<div class="sk-src"><select id="skLv" aria-label="${esc(I18N.text('skillsv.lv.level'))}">${opt('', I18N.text('skillsv.lv.none'), s.level || '')}${Object.entries(LV()).map(([k, t]) => opt(k, t, s.level || '')).join('')}</select>`
      + `<select id="skPar" aria-label="${esc(I18N.text('skillsv.lv.parent'))}">${opt('', I18N.text('skillsv.lv.noParent'), s.parent || '')}${skills().filter(x => x.id !== s.id).map(x => opt(x.id, x.name, s.parent || '')).join('')}</select>`
      + `<button class="sk-btn small" data-act="lvset">${esc(I18N.text('skillsv.lv.save'))}</button></div><div class="sk-note">${esc(I18N.text('skillsv.lv.note'))}</div>`;
  }
  const VT = () => ({brief: I18N.text('skillsv.via.brief'), type: I18N.text('skillsv.via.type'), used: I18N.text('skillsv.via.used')});
  const viaText = v => (v || []).map(x => VT()[x] || x).join(' · ');
  const ST = () => ({pending: I18N.text('skillsv.st.pending'), paused: I18N.text('skillsv.st.paused'), running: I18N.text('skillsv.st.running'), done: I18N.text('skillsv.st.done'), failed: I18N.text('skillsv.st.failed')});
  function visible() {
    const q = SK.q.trim().toLowerCase();
    return skills().filter(s => (!SK.origin || s.origin === SK.origin) && (!SK.unused || (s.usage && s.usage.unused)) && (!q || (s.name + ' ' + s.brief + ' ' + s.description + ' ' + (s.plugin || '')).toLowerCase().includes(q)));
  }
  const agentOptions = () => `<option value="*">${esc(I18N.text('skillsv.allAgents'))}</option>` + agentsOf().map(a => `<option value="${esc(a.name)}">${esc(a.name)}</option>`).join('');

  // ---- shell ----
  function top() {
    const tn = {explore: I18N.text('skillsv.tab.explore'), agents: I18N.text('skillsv.tab.agents'), search: I18N.text('skillsv.tab.search'), cand: I18N.text('skillsv.tab.cand')};
    const tabs = ['explore', 'agents', 'search', 'cand'].map(t => `<button class="sk-pill${SK.tab === t ? ' on' : ''}" data-tab="${t}">${esc(tn[t])}</button>`).join('');
    const n = skills().length;
    const bar = `<span class="sk-sp"></span><span class="sk-upd">${esc(I18N.text('skillsv.count', {n}))}</span>`
      + `<button class="sk-btn small" data-act="addform">${IC.plus} ${esc(I18N.text('skillsv.add'))}</button>`;
    return `<div class="sk-top"><button class="sk-logo" data-close="1" title="${esc(I18N.text('skillsv.back'))}">${IC.spark}</button><span class="sk-title">${esc(I18N.text('skillsv.title'))}</span>${tabs}${bar}</div>`;
  }
  function shell() {
    let body = '';
    if (SK.err && !SK.data) body = `<div class="sk-card sk-pad"><div class="sk-empty">${esc(I18N.text('skillsv.loadErr', {why: SK.err}))}</div></div>`;
    else if (!SK.data) body = `<div class="sk-card sk-pad"><div class="sk-empty">${esc(I18N.text('skillsv.loading'))}</div></div>`;
    else if (SK.tab === 'explore') {
      body = `<div class="sk-card sk-explore" id="skMain"><div class="sk-bar">`
        + `<input id="skQ" type="text" autocomplete="off" placeholder="${esc(I18N.text('skillsv.filter'))}" value="${esc(SK.q)}"><div class="sk-chips" id="skChips"></div></div><div class="sk-note sk-help" id="skHelp"></div><div class="sk-rows" id="skRows"></div></div>`;
    } else if (SK.tab === 'agents') body = `<div class="sk-card sk-pad" id="skAgents"></div>`;
    else if (SK.tab === 'cand') {
      body = `<div class="sk-candwrap"><div class="sk-card sk-derive"><div class="sk-sec" style="margin:0">${esc(I18N.text('skillsv.cand.head'))}</div>`
        + `<textarea id="skDesc" maxlength="600" placeholder="${esc(I18N.text('skillsv.cand.descHint'))}">${esc(SK.cand.desc)}</textarea>`
        + `<div class="sk-src" data-srcbox="derive">${srcHtml('derive')}</div>`
        + `<div class="r"><button class="sk-btn pri" data-act="derive">${esc(I18N.text('skillsv.cand.derive'))}</button><button class="sk-btn" data-act="suggest">${esc(I18N.text('skillsv.cand.suggest'))}</button></div>`
        + `<div class="sk-note" style="margin:0">${esc(I18N.text('skillsv.cand.note'))}</div><div id="skJobs"></div></div>`
        + `<div class="sk-card sk-explore" id="skCands"><div class="sk-bar"><div class="sk-chips" id="skRoomChips"></div></div><div class="sk-rows" id="skCandRows"></div></div></div>`;
    } else body = `<div class="sk-card sk-find"><div class="sk-sec" style="margin:0">${esc(I18N.text('skillsv.findHead'))}</div><div class="r"><input id="skSq" type="text" autocomplete="off" maxlength="300" placeholder="${esc(I18N.text('skillsv.findHint'))}" value="${esc(SK.searchQ)}">`
      + `<button class="sk-btn pri" data-act="search">${esc(I18N.text('skillsv.search'))}</button></div><div class="sk-chips" id="skFor"></div><div id="skSt"></div></div><div class="sk-card sk-pad" id="skReqs"></div>`;
    main.innerHTML = top() + body + '<div id="skModal"></div>';
    fill();
  }
  // refresh: keep the typed text and the scroll, only fill what changed
  function refresh() {
    if (!SK.open) return;
    const need = !main.querySelector(SK.tab === 'explore' ? '#skMain' : SK.tab === 'agents' ? '#skAgents' : SK.tab === 'cand' ? '#skCands' : '#skReqs') || (SK.data && main.querySelector('.sk-pad .sk-empty') && SK.tab !== 'search');
    if (need) shell(); else fill();
  }
  function fill() {
    const n = main.querySelector('.sk-upd'); if (n) n.textContent = I18N.text('skillsv.count', {n: skills().length});
    if (!SK.data) return;
    if (SK.tab === 'explore') { fillChips(); fillRows(); }
    else if (SK.tab === 'agents') fillAgents();
    else if (SK.tab === 'cand') { fillJobs(); fillRoomChips(); fillCands(); }
    else { fillFor(); fillStatus(); fillReqs(); }
    fillModal();
  }
  function fillChips() {
    const c = skills().reduce((m, s) => (m[s.origin] = (m[s.origin] || 0) + 1, m), {});
    const el = $('skChips'); if (!el) return;
    const hp = $('skHelp'); if (hp) hp.textContent = SK.unused ? I18N.text('skillsv.use.help') : OX()[SK.origin] || OX()[''];
    const nu = skills().filter(s => s.usage && s.usage.unused).length;
    el.innerHTML = [''].concat((SK.data.origins || []).filter(o => c[o])).map(o => `<button class="sk-chip${SK.origin === o ? ' on' : ''}" data-origin="${esc(o)}">${esc(o ? originName(o) : I18N.text('skillsv.all'))}<span class="n">${o ? c[o] : skills().length}</span></button>`).join('')
      + (nu ? `<button class="sk-chip${SK.unused ? ' on' : ''}" data-act="unusedf">${esc(I18N.text('skillsv.use.filter'))}<span class="n">${nu}</span></button>` : '');
  }
  // D3: on which agents each skill is active, as badges (all of them in the tooltip, three shown)
  function badges(s) {
    const a = s.agents || [];
    if (!a.length) return '';
    return `<div class="sk-bd" title="${esc(I18N.text('skillsv.inAgents', {n: a.length}) + ': ' + a.join(', '))}">${a.slice(0, 3).map(n => `<span>${esc(n)}</span>`).join('')}${a.length > 3 ? `<span>+${a.length - 3}</span>` : ''}</div>`;
  }
  // D8 point 5: three levels (strategy > function > step) shown as a tree; a child whose parent is filtered out stands as a root
  const LV = () => ({strategy: I18N.text('skillsv.lv.strategy'), function: I18N.text('skillsv.lv.function'), step: I18N.text('skillsv.lv.step')});
  function treeOrder(v) {
    if (!v.some(s => s.level || s.parent)) return v.map(s => [s, 0]);
    const ids = new Set(v.map(s => s.id)), kids = {}, out = [];
    v.forEach(s => { if (s.parent && ids.has(s.parent) && s.parent !== s.id) (kids[s.parent] ||= []).push(s); });
    const seen = new Set(), walk = (s, d) => { if (seen.has(s.id)) return; seen.add(s.id); out.push([s, d]); (kids[s.id] || []).forEach(c => walk(c, d + 1)); };
    v.forEach(s => { if (!(s.parent && ids.has(s.parent) && s.parent !== s.id)) walk(s, 0); });
    v.forEach(s => walk(s, 0));                        // a cycle (the server refuses one) must not make a card vanish
    return out;
  }
  function fillRows() {
    const el = $('skRows'); if (!el) return;
    const v = visible(), top = el.scrollTop;
    el.innerHTML = v.length ? treeOrder(v).map(([s, dep], i) => `<div class="sk-row${s.id === SK.sel ? ' on' : ''}${s.enabled === false ? ' off' : ''}${dep ? ' sk-child' : ''}" style="--o:var(--o-${esc(s.origin)});--i:${Math.min(i, 14)};--dep:${Math.min(dep, 3)}">`
      + `<div class="sk-hd" data-sel="${esc(s.id)}" tabindex="0" role="button" aria-expanded="${s.id === SK.sel}"><div class="tl">${esc((s.name || '?').charAt(0).toUpperCase())}</div>`
      + `<div class="rb"><div class="n"><span>${esc(s.name)}</span></div><div class="s">${esc(s.brief)}</div><div class="sk-ft">${oTag(s.origin, s)}${s.level ? `<span class="sk-lv">${esc(LV()[s.level] || s.level)}</span>` : ''}${vTag(s)}${s.usage && s.usage.unused ? `<span class="sk-dim">${esc(I18N.text('skillsv.use.tag'))}</span>` : ''}${badges(s)}</div></div>${IC.down.replace('class="sk-i"', 'class="sk-i sk-chev"')}</div>`
      + (s.id === SK.sel ? detail(s) : '') + '</div>').join('')
      : `<div class="sk-empty">${esc(I18N.text('skillsv.none'))}</div>`;
    el.scrollTop = top;
    if (typeof requestAnimationFrame === 'function' && main.classList.contains('sk-animd')) countUp(el);
  }
  // D7: "Update" only on skills with an outside creator (the server says which: updatable). The check is read-only; the update itself asks first.
  function updHtml(s) {
    const u = SK.upd[s.id] || {}, d = u.data;
    const body = u.busy ? `<div class="sk-sub">${esc(I18N.text('skillsv.upd.checking'))}</div>`
      : !d ? '' : d.newer == null ? (d.installed && d.available && d.installed !== d.available   // a different version but the origin could not say if newer: the pull is fast-forward only, so it is safe to offer
        ? `<div class="sk-sub">${esc(I18N.text('skillsv.upd.differs', {a: d.installed, b: d.available}))}</div><div class="sk-acts"><button class="sk-btn pri small" data-act="updapply">${esc(I18N.text('skillsv.upd.apply'))}</button></div>`
        : `<div class="sk-sub">${esc(I18N.text('skillsv.upd.unknown', {v: d.installed || '?'}))}</div>`)
      : !d.newer ? `<div class="sk-ok">${IC.check} ${esc(I18N.text('skillsv.upd.latest', {v: d.installed || '?'}))}</div>`
      : `<div class="sk-who"><span class="w">${esc(I18N.text('skillsv.upd.installed'))}<small>${esc(d.installed || '?')}</small></span><span class="w">${esc(I18N.text('skillsv.upd.available'))}<small>${esc(d.available || '?')}</small></span></div>`
        + (d.changes ? `<div class="sk-desc" style="margin:8px 0">${esc(d.changes)}</div>` : '') + (d.source ? `<div class="sk-sub">${esc(I18N.text('skillsv.upd.source', {src: d.source}))}</div>` : '')
        + `<div class="sk-acts"><button class="sk-btn pri small" data-act="updapply">${esc(I18N.text('skillsv.upd.apply'))}</button></div>`;
    return `<div class="sk-sec">${esc(I18N.text('skillsv.upd.head'))}</div><div class="sk-src"><button class="sk-btn" data-act="updcheck"${u.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.upd.check'))}</button></div>${body}`
      + `<div class="sk-note">${esc(I18N.text('skillsv.upd.note'))}</div>`;
  }
  // the card at a glance: four tiles (check state, use, measured saving, activation). Numbers count up and bars and rings fill when the card is opened by a click (not on every poll)
  function tilesHtml(s) {
    const u = s.usage, m = s.measured, a = s.activation, st = verState(s), v = s.verified || {};
    const T = (cls, i, inner) => `<div class="sk-tile ${cls}" style="--i:${i}">${inner}</div>`;
    const state = T(st, 0, `<div class="b">${st === 'verified' ? IC.check + ' ' + esc(I18N.text('skillsv.ver.ok')) : st === 'failed' ? esc(I18N.text('skillsv.ver.failed')) : esc(I18N.text('skillsv.ver.not'))}</div>`
      + `<div class="l">${esc(v.at ? I18N.text('skillsv.ver.at', {when: ago(v.at)}) : s.check ? I18N.text('skillsv.ver.neverRun') : I18N.text('skillsv.tile.noCheck'))}</div>`);
    const tot = u ? (u.ok || 0) + (u.fail || 0) : 0, nt = u && u.count > tot ? u.count - tot : 0, pc = x => u && u.count ? (100 * x / u.count).toFixed(1) : 0;
    const use = T(u && u.count ? 'ok' : 'none', 1, u && u.count
      ? `<div class="b" data-count="${u.count}">${u.count}</div><div class="l">${esc(I18N.text('skillsv.tile.uses', {rooms: u.rooms}))}</div>`
        + `<div class="bar"><i class="ok" style="--w:${pc(u.ok || 0)}%"></i><i class="bad" style="--w:${pc(u.fail || 0)}%"></i><i class="nt" style="--w:${pc(nt)}%"></i></div>`
      : `<div class="b">0</div><div class="l">${esc(I18N.text('skillsv.tile.neverUsed'))}</div>`);
    const ts = m && m.tokens_saved != null ? m.tokens_saved : null;
    const sav = T(ts == null ? 'none' : ts >= 0 ? 'ok' : 'bad', 2, ts == null ? `<div class="b">&ndash;</div><div class="l">${esc(I18N.text('skillsv.tile.notMeasured'))}</div>`
      : `<div class="b"><span>${ts >= 0 ? '+' : '&minus;'}</span><span data-count="${Math.abs(Math.round(ts))}">${Math.abs(Math.round(ts)).toLocaleString()}</span></div><div class="l">${esc(I18N.text('skillsv.tile.tokens'))}</div>`);
    const pr = a && a.total ? Math.round(100 * a.right / a.total) : null;
    const act = T(pr == null ? 'none' : pr >= 80 ? 'ok' : pr >= 50 ? 'mid' : 'bad', 3, pr == null ? `<div class="b">&ndash;</div><div class="l">${esc(I18N.text('skillsv.tile.notTested'))}</div>`
      : `<div class="row"><div class="ring" data-ring="${pr}" style="--p:${pr}"><b>${a.right}/${a.total}</b></div><div class="l">${esc(I18N.text('skillsv.tile.fires'))}</div></div>`);
    return `<div class="sk-tiles">${state}${use}${sav}${act}</div>`;
  }
  function countUp(root) {
    const els = root.querySelectorAll('[data-count],[data-ring]');
    if (!els.length || typeof requestAnimationFrame !== 'function' || (typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
    const t0 = performance.now();
    const step = t => { const k = Math.min(1, (t - t0) / 850), e = 1 - Math.pow(1 - k, 3);
      els.forEach(x => { if (x.dataset.count != null) x.textContent = Math.round(Number(x.dataset.count) * e).toLocaleString(); else x.style.setProperty('--p', (Number(x.dataset.ring) * e).toFixed(1)); });
      if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  function detail(s) {                                 // the opened card: what it does and where it lives on the left, who has it and the recommendation on the right
    const ag = agentsOf();
    const who = (s.agents || []).map(n => { const a = ag.find(x => x.name === n); const e = a && a.skills.find(x => x.id === s.id);
      return `<span class="w">${esc(n)}<small>${e ? esc(viaText(e.via)) + (e.count ? ' · ' + esc(I18N.text('skillsv.used', {n: e.count})) : '') : ''}</small></span>`; }).join('');
    const adv = (s.advised || []).map(a => `<span class="w">${esc(a.to === '*' ? I18N.text('skillsv.allAgents') : a.to)}<small>${esc(ago(a.at))}</small></span>`).join('');
    const sub = [s.enabled === false ? I18N.text('skillsv.disabled') : '', fromText(s)].filter(Boolean).join(' · ');
    return `<div class="sk-more"><div class="sk-mi"><div class="sk-cols"><div>`
      + (sub ? `<div class="sk-h"><span class="sk-sub">${esc(sub)}</span></div>` : '')
      + `<div class="sk-desc">${esc(s.description || s.brief)}</div>${s.path ? `<div class="sk-path">${esc(s.path)}</div>` : ''}${tilesHtml(s)}`
      + `<div class="sk-sec">${esc(I18N.text('skillsv.hasIt'))}</div>` + (who ? `<div class="sk-who">${who}</div>` : `<div class="sk-sub">${esc(I18N.text('skillsv.nobody'))}</div>`)
      + `<div class="sk-sec">${esc(I18N.text('skillsv.recommend'))}</div><div class="sk-rec"><select id="skTo">${agentOptions()}</select><button class="sk-btn pri" data-act="recommend">${esc(I18N.text('skillsv.recommendBtn'))}</button></div>`
      + `<div class="sk-note">${esc(I18N.text('skillsv.recommendNote'))}</div>`
      + (adv ? `<div class="sk-sec">${esc(I18N.text('skillsv.advised'))}</div><div class="sk-who">${adv}</div>` : '')
      + `</div><div>` + (s.updatable ? updHtml(s) : '') + chkHtml(s) + useHtml(s) + measHtml(s) + lvlHtml(s) + actHtml(s) + casesHtml(s)
      + `<div class="sk-sec">${esc(I18N.text('skillsv.cand.improveHead'))}</div><div class="sk-src" data-srcbox="imp">${srcHtml('imp')}<button class="sk-btn" data-act="improve">${esc(I18N.text('skillsv.cand.improve'))}</button></div>`
      + `<div class="sk-note">${esc(['user', 'project', 'added'].includes(s.origin) ? I18N.text('skillsv.cand.improveInPlace') : I18N.text('skillsv.cand.improveCopy'))}</div></div></div></div></div>`;
  }
  function fillAgents() {
    const el = $('skAgents'); if (!el) return;
    const ag = agentsOf();
    el.innerHTML = ag.length ? `<div class="sk-grid">` + ag.map(a => {
      const chips = (a.skills || []).map(x => { const s = byId(x.id);
        return `<button class="w sk-who-b" data-goto="${esc(x.id)}">${esc(s ? s.name : x.id)}<small>${esc(viaText(x.via))}${x.count ? ' · ' + esc(I18N.text('skillsv.used', {n: x.count})) : ''}</small></button>`; }).join('');
      return `<div class="sk-ag" style="--i:${Math.min(ag.indexOf(a), 9)}"><h3>${esc(a.name)}</h3><div class="sk-sub">${esc(a.type || '')}</div>` + (chips ? `<div class="sk-who who">${chips}</div>` : `<div class="none">${esc(I18N.text('skillsv.noSkills'))}</div>`) + '</div>'; }).join('') + '</div>'
      : `<div class="sk-empty">${esc(I18N.text('skillsv.noAgents'))}</div>`;
  }
  function fillFor() {
    const el = $('skFor'); if (!el) return;
    el.innerHTML = `<span class="sk-sub" style="align-self:center">${esc(I18N.text('skillsv.forWho'))}</span>`
      + agentsOf().map(a => `<button class="sk-chip${SK.searchFor.includes(a.name) ? ' on' : ''}" data-for="${esc(a.name)}">${esc(a.name)}</button>`).join('')
      + (SK.searchFor.length ? '' : `<span class="sk-sub" style="align-self:center">${esc(I18N.text('skillsv.forAll'))}</span>`);
  }
  function fillStatus() {
    const el = $('skSt'); if (!el) return;
    const s = SK.data.searcher || {};
    el.innerHTML = s.present
      ? `<div class="sk-sub"><span class="sk-dot ${s.busy ? 'warn' : 'ok'}"></span> ${esc((s.busy ? I18N.text('skillsv.searcherBusy', {name: s.name}) : I18N.text('skillsv.searcherOk', {name: s.name})))}</div>`
      : `<div class="sk-banner"><span>${esc(I18N.text('skillsv.noSearcher'))}</span><button class="sk-btn small" data-act="tempsearcher">${esc(I18N.text('skillsv.tempSearcher'))}</button></div>`;
  }
  function cardHtml(c, req, i) {
    const fit = Math.max(0, Math.min(1, Number(c.fit) || 0));
    return `<div class="sk-ag sk-cd" style="--i:${Math.min(i, 9)}"><h4><span>${esc(c.name)}</span>${c.added ? `<span class="sk-ok">${IC.check} ${esc(I18N.text('skillsv.added'))}</span>` : ''}</h4>`
      + (c.fit != null ? `<div class="sk-fit" title="${esc(I18N.text('skillsv.fit', {n: Math.round(fit * 100)}))}"><i style="width:${Math.round(fit * 100)}%"></i></div>` : '')
      + `<div class="s">${esc(c.what)}</div><div class="m">${/^https?:\/\//i.test(c.url || '') ? `<a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.source || c.url)}</a>` : esc(c.source || '')}${c.trust ? ' · ' + esc(c.trust) : ''}</div>`
      + `<div class="acts"><button class="sk-btn small pri" data-act="cardadd" data-req="${esc(req)}" data-i="${i}"${c.added ? ' disabled' : ''}>${esc(I18N.text('skillsv.addCard'))}</button>`
      + `<button class="sk-btn small" data-act="cardrec" data-req="${esc(req)}" data-i="${i}">${esc(I18N.text('skillsv.recommendBtn'))}</button></div></div>`;
  }
  function fillReqs() {
    const el = $('skReqs'); if (!el) return;
    const rq = ((SK.data.requests) || []).filter(r => !r.kind || r.kind === 'search').reverse();   // the derive/suggest/improve jobs are listed in the Candidates tab
    el.innerHTML = rq.length ? rq.map(r => `<div class="sk-req"><div class="rh"><span class="rq">${esc(r.q)}</span><span class="sk-st ${esc(r.state)}">${esc(ST()[r.state] || r.state)}</span><span class="sk-sub">${esc(ago(r.at))}</span></div>`
      + ((r.cards || []).length ? `<div class="sk-grid">${r.cards.map((c, i) => cardHtml(c, r.req, i)).join('')}</div>` : `<div class="sk-sub">${esc((r.state === 'done' ? I18N.text('skillsv.noResults') : I18N.text('skillsv.waiting')))}</div>`) + '</div>').join('')
      : `<div class="sk-empty">${esc(I18N.text('skillsv.noRequests'))}</div>`;
  }

  // ---- D6: candidates the jobs wrote in the rooms, each with a score; derive, suggest and improve start a job after a confirmation ----
  const rooms = () => (SK.data && SK.data.rooms) || [];
  const roomName = id => (rooms().find(r => r.id === id) || {}).name || id;
  const KT = () => ({derive: I18N.text('skillsv.cand.kind.derive'), suggest: I18N.text('skillsv.cand.kind.suggest'), improve: I18N.text('skillsv.cand.kind.improve')});
  const KC = {derive: 'var(--d-k-skill)', suggest: 'var(--d-k-cmd)', improve: 'var(--d-k-plan)'};
  const CR = () => ({recurrence: I18N.text('skillsv.cand.c.recurrence'), error_cost: I18N.text('skillsv.cand.c.error_cost'), specificity: I18N.text('skillsv.cand.c.specificity'), overlap: I18N.text('skillsv.cand.c.overlap'), weight: I18N.text('skillsv.cand.c.weight')});
  const tag = (k, t) => `<span class="sk-o" style="--o:${KC[k] || 'var(--d-muted)'}">${esc(t)}</span>`;
  function srcHtml(p) {                                // where the job reads from: a room, a folder or a GitHub repo
    const s = SK.cand.src[p];
    const ks = [['room', I18N.text('skillsv.cand.src.room')], ['folder', I18N.text('skillsv.cand.src.folder')], ['repo', I18N.text('skillsv.cand.src.repo')], ['chat', I18N.text('skillsv.cand.src.chat')]];
    return `<select data-srck="${p}" aria-label="${esc(I18N.text('skillsv.cand.src.label'))}">${ks.map(k => `<option value="${k[0]}"${s.k === k[0] ? ' selected' : ''}>${esc(k[1])}</option>`).join('')}</select>`
      + (s.k === 'chat' ? ''
        : s.k === 'room'
        ? `<select data-srcv="${p}"><option value="current">${esc(I18N.text('skillsv.cand.src.current'))}</option>${rooms().filter(r => !r.current).map(r => `<option value="${esc(r.id)}"${s.v === r.id ? ' selected' : ''}>${esc(r.name)}</option>`).join('')}</select>`
        : `<input data-srcv="${p}" type="text" autocomplete="off" maxlength="300" placeholder="${esc(s.k === 'folder' ? I18N.text('skillsv.cand.src.folderHint') : I18N.text('skillsv.cand.src.repoHint'))}" value="${esc(s.v)}">`);
  }
  function srcBody(p) {
    const s = SK.cand.src[p], v = String(s.v || '').trim();
    if (s.k === 'chat') return {chat: true};          // the lead's own session, which already holds the conversation
    if (!v) { toast(I18N.text('skillsv.cand.srcEmpty')); return null; }
    return {[s.k]: v};
  }
  const diffHtml = t => `<div class="sk-diff">${String(t || '').replace(/\n$/, '').split('\n').map(l => `<span class="${/^(\+\+\+|---|@@)/.test(l) ? 'h' : l[0] === '+' ? 'a' : l[0] === '-' ? 'd' : ''}">${esc(l) || ' '}</span>`).join('')}</div>`;
  const cands = () => ((SK.data && SK.data.candidates) || []).filter(c => c.status !== 'dismissed');
  function fillJobs() {
    const el = $('skJobs'); if (!el) return;
    const j = ((SK.data.requests) || []).filter(r => ['derive', 'suggest', 'improve'].includes(r.kind)).slice(-4).reverse();
    el.innerHTML = j.length ? `<div class="sk-sec" style="margin:6px 0 2px">${esc(I18N.text('skillsv.cand.jobs'))}</div>` + j.map(r => `<div class="sk-job">${tag(r.kind, KT()[r.kind] || r.kind)}<span class="q">${esc(r.q)}</span>`
      + `<span class="sk-st ${esc(r.state)}">${esc(r.state === 'running' ? I18N.text('skillsv.cand.running') : ST()[r.state] || r.state)}</span><span class="sk-sub">${esc(ago(r.at))}${r.state === 'failed' && r.log ? ' · ' + esc(I18N.text('skillsv.cand.log', {log: r.log})) : ''}${r.note ? ' · ' + esc(r.note) : ''}</span></div>`).join('') : '';
  }
  function fillRoomChips() {
    const el = $('skRoomChips'); if (!el) return;
    const all = cands(), n = id => all.filter(c => c.room === id).length;
    el.innerHTML = `<button class="sk-chip${SK.cand.room ? '' : ' on'}" data-croom="">${esc(I18N.text('skillsv.cand.allRooms'))}<span class="n">${all.length}</span></button>`
      + rooms().map(r => `<button class="sk-chip${SK.cand.room === r.id ? ' on' : ''}" data-croom="${esc(r.id)}">${esc(r.name)}${r.current ? ' ' + esc(I18N.text('skillsv.cand.here')) : ''}<span class="n">${n(r.id)}</span></button>`).join('');
  }
  function fillCands() {
    const el = $('skCandRows'); if (!el) return;
    const v = cands().filter(c => !SK.cand.room || c.room === SK.cand.room).sort((a, b) => (b.score - a.score) || (b.at - a.at)), top = el.scrollTop;
    el.innerHTML = v.length ? v.map((c, i) => {
      const on = c.id === SK.cand.sel, sc = Math.max(1, Math.min(10, Math.round(Number(c.score) || 1))), cov = c.covered_by && (byId(c.covered_by) || {}).name;
      return `<div class="sk-row${on ? ' on' : ''}" style="--o:${KC[c.kind] || 'var(--d-accent)'};--i:${Math.min(i, 14)}"><div class="sk-hd" data-cand="${esc(c.id)}" tabindex="0" role="button" aria-expanded="${on}">`
        + `<div class="sk-score${sc >= 8 ? ' hi' : sc <= 4 ? ' lo' : ''}" style="--p:${sc * 10}" title="${esc(I18N.text('skillsv.cand.score', {n: sc}))}"><b>${sc}</b></div>`
        + `<div class="rb"><div class="n"><span>${esc(c.name)}</span></div><div class="s">${esc(c.why)}</div><div class="sk-ft">${tag(c.kind, KT()[c.kind] || c.kind)}${vTag(c, true)}`
        + (!SK.cand.room && rooms().length > 1 ? `<div class="sk-bd"><span>${esc(roomName(c.room))}</span></div>` : '')
        + (c.status === 'added' ? `<span class="sk-ok">${IC.check} ${esc(I18N.text('skillsv.cand.addedTag'))}</span>` : '')
        + (c.covered_by ? `<span class="sk-warn">${esc(I18N.text('skillsv.cand.covered', {name: cov || c.covered_by}))}</span>` : '') + `</div></div>${IC.down.replace('class="sk-i"', 'class="sk-i sk-chev"')}</div>`
        + (on ? candDetail(c) : '') + '</div>';
    }).join('') : `<div class="sk-empty">${esc(I18N.text('skillsv.cand.none'))}</div>`;
    el.scrollTop = top;
  }
  function candDetail(c) {
    const cr = c.criteria || {}, d = SK.cand.diffs[c.id], nm = (k, t) => (c[k] || []).length ? `<div class="sk-sec">${esc(t)}</div><ul class="sk-ul">${c[k].map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
    const mets = [c.tokens != null ? I18N.text('skillsv.cand.tokens', {n: c.tokens}) : ''].filter(Boolean).map(t => `<span class="w">${esc(t)}</span>`).join('');
    const bars = Object.keys(CR()).filter(k => cr[k] != null).map(k => { const n = Math.max(0, Math.min(10, Number(cr[k]) || 0));
      return `<div class="sk-cr"><span>${esc(CR()[k])}</span><div class="sk-fit"><i style="width:${n * 10}%"></i></div><em>${n}</em></div>`; }).join('');
    const diff = !d ? `<div class="sk-sub">${esc(I18N.text('skillsv.cand.diffLoading'))}</div>` : d.err ? '' : `<div class="sk-sub">+${Number(d.added) || 0} -${Number(d.removed) || 0}${d.target && d.target.copy ? ' · ' + esc(I18N.text('skillsv.cand.copyNote')) : ''}</div>${diffHtml(d.diff)}`;
    return `<div class="sk-more"><div class="sk-mi"><div class="sk-cols"><div><div class="sk-sec">${esc(I18N.text('skillsv.cand.why'))}</div><div class="sk-desc" style="margin-top:0">${esc(c.why)}</div>`
      + (mets ? `<div class="sk-who">${mets}</div>` : '') + (c.tasks && c.tasks.length ? `<div class="sk-sec">${esc(I18N.text('skillsv.cand.tasks'))}</div><div class="sk-who">${c.tasks.map(t => `<span class="w">${esc(t)}</span>`).join('')}</div>` : '')
      + nm('repeated', I18N.text('skillsv.cand.repeated')) + nm('hard', I18N.text('skillsv.cand.hard')) + `</div><div>`
      + (bars ? `<div class="sk-sec">${esc(I18N.text('skillsv.cand.criteria'))}</div>${bars}` : '')
      + chkHtml(c, true) + casesHtml(c)
      + `<div class="sk-sec">${esc(c.improves ? I18N.text('skillsv.cand.diffImp') : I18N.text('skillsv.cand.diffNew'))}</div>${diff}`
      + (c.status === 'added' ? `<div class="sk-ok">${IC.check} ${esc(I18N.text('skillsv.cand.addedTag'))}</div>`
        : `<div class="sk-acts"><button class="sk-btn pri small" data-act="cpromote" data-cid="${esc(c.id)}">${esc(c.improves ? I18N.text('skillsv.cand.apply') : I18N.text('skillsv.cand.add'))}</button>`
          + `<button class="sk-btn small" data-act="cdismiss" data-cid="${esc(c.id)}">${esc(I18N.text('skillsv.cand.dismiss'))}</button></div>`)
      + `</div></div></div></div>`;
  }
  function pickCand(id) {
    SK.cand.sel = SK.cand.sel === id ? null : id; animate('sk-animd'); fillCands();
    const hd = main.querySelector(`.sk-hd[data-cand="${CSS.escape(id)}"]`); if (hd) hd.focus({preventScroll: true});
    const on = main.querySelector('.sk-row.on'); if (on && on.scrollIntoView) on.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    if (SK.cand.sel && !SK.cand.diffs[id]) loadDiff(id);
  }
  async function loadDiff(id) {                        // the diff of a candidate against what it replaces (the whole file when it is new)
    const r = await act({action: 'diff', id});
    SK.cand.diffs[id] = good(r) ? r : {err: true};
    if (SK.open && SK.cand.sel === id) { main.classList.remove('sk-anim', 'sk-animd'); fillCands(); }
  }

  // ---- modal: every addition is confirmed here, with what and from where ----
  function fillModal() {
    const el = $('skModal'); if (!el) return;
    const m = SK.form, fresh = !el.innerHTML;          // the box animates in once, not at every busy/preview refill
    if (!m) { el.innerHTML = ''; return; }
    queueMicrotask(() => { const b = fresh && el.firstElementChild; if (b) b.classList.add('in'); });
    if (m.kind === 'path') {
      const p = m.preview;
      el.innerHTML = `<div class="sk-modal"><div class="sk-box"><h3>${esc(I18N.text('skillsv.addHead'))}</h3>`
        + (p ? '' : `<div class="sk-chatbox"><b>${esc(I18N.text('skillsv.chat.head'))}</b><div class="sk-note" style="margin:2px 0 8px">${esc(I18N.text('skillsv.chat.note'))}</div>`
          + `<textarea id="skChatDesc" maxlength="600" placeholder="${esc(I18N.text('skillsv.chat.hint'))}">${esc(SK.chatDesc || '')}</textarea>`
          + `<div class="acts" style="margin-top:8px"><button class="sk-btn pri small" data-act="chatderive">${esc(I18N.text('skillsv.chat.go'))}</button></div></div><div class="sk-or">${esc(I18N.text('skillsv.chat.or'))}</div>`)
        + `<div class="sk-form"><input id="skPath" type="text" autocomplete="off" placeholder="${esc(I18N.text('skillsv.addPath'))}" value="${esc(m.path || '')}">`
        + (p ? kv([[I18N.text('skillsv.k.name'), p.name], [I18N.text('skillsv.k.what'), p.brief], [I18N.text('skillsv.k.from'), p.from], [I18N.text('skillsv.k.to'), p.to || p.path]]) : '')
        + `</div><div class="sk-note">${esc(I18N.text('skillsv.addNote'))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + (p ? `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.confirmAdd'))}</button>` : `<button class="sk-btn pri" data-act="mpreview"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.preview'))}</button>`) + '</div></div></div>';
    } else if (m.kind === 'card' || m.kind === 'temp') {
      const c = m.card, p = m.preview || {};
      const rows = m.kind === 'card' ? [[I18N.text('skillsv.k.name'), p.name || c.name], [I18N.text('skillsv.k.what'), p.brief || c.what], [I18N.text('skillsv.k.from'), p.from || c.url || c.source], [I18N.text('skillsv.k.to'), p.to || p.path], [I18N.text('skillsv.k.trust'), c.trust]]
        : [[I18N.text('skillsv.k.name'), p.name], [I18N.text('skillsv.k.task'), p.task]];
      el.innerHTML = `<div class="sk-modal"><div class="sk-box"><h3>${esc((m.kind === 'temp' ? I18N.text('skillsv.tempHead') : I18N.text('skillsv.addHead')))}</h3>${kv(rows)}`
        + `<div class="sk-note">${esc((m.kind === 'temp' ? I18N.text('skillsv.tempNote') : I18N.text('skillsv.addNote')))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc((m.kind === 'temp' ? I18N.text('skillsv.tempConfirm') : I18N.text('skillsv.confirmAdd')))}</button></div></div></div>`;
    } else if (m.kind === 'rec') {
      el.innerHTML = `<div class="sk-modal"><div class="sk-box"><h3>${esc(I18N.text('skillsv.recommend'))}: ${esc(m.card.name)}</h3><div class="sk-rec"><select id="skTo">${agentOptions()}</select></div>`
        + `<div class="sk-note">${esc(I18N.text('skillsv.recommendNote'))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button><button class="sk-btn pri" data-act="mconfirm">${esc(I18N.text('skillsv.recommendBtn'))}</button></div></div></div>`;
    } else if (m.kind === 'job') {                     // derive / suggest / improve: what the background session reads, writes and costs at most
      const p = m.preview || {}, t = p.target, heads = {derive: I18N.text('skillsv.cand.jh.derive'), suggest: I18N.text('skillsv.cand.jh.suggest'), improve: I18N.text('skillsv.cand.jh.improve')};
      el.innerHTML = `<div class="sk-modal"><div class="sk-box wide"><h3>${esc(heads[m.job] || m.job)}</h3>`
        + kv([[I18N.text('skillsv.k.task'), p.task], [I18N.text('skillsv.cand.k.reads'), (p.reads || []).join(', ')], [I18N.text('skillsv.cand.k.writes'), (p.writes || []).join(', ')],
          [I18N.text('skillsv.cand.k.budget'), p.budget_usd != null ? I18N.text('skillsv.cand.usd', {n: p.budget_usd}) : ''],
          [I18N.text('skillsv.cand.k.target'), t ? t.path + (t.copy ? ' (' + I18N.text('skillsv.cand.copyNote') + ')' : '') : '']])
        + `<div class="sk-note">${esc(m.body && m.body.source && m.body.source.chat ? I18N.text('skillsv.chat.jobNote') : m.job === 'improve' ? I18N.text('skillsv.cand.improveNote') : I18N.text('skillsv.cand.jobNote'))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.cand.jobConfirm'))}</button></div></div></div>`;
    } else if (m.kind === 'update') {                  // update a skill from its creator: what changes and from where, then the user confirms
      const p = m.preview || {};
      el.innerHTML = `<div class="sk-modal"><div class="sk-box"><h3>${esc(I18N.text('skillsv.upd.head'))}: ${esc(p.name || '')}</h3>`
        + kv([[I18N.text('skillsv.upd.installed'), p.installed], [I18N.text('skillsv.upd.available'), p.available], [I18N.text('skillsv.k.from'), p.from], [I18N.text('skillsv.k.to'), p.to || p.writes], [I18N.text('skillsv.upd.how'), p.how]])
        + `<div class="sk-note">${esc(I18N.text('skillsv.upd.applyNote'))}${p.restart ? ' ' + esc(I18N.text('skillsv.upd.restart')) : ''}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.upd.apply'))}</button></div></div></div>`;
    } else if (m.kind === 'acttest') {                 // phase 2 of the activation test: a model writes the requests, so it costs tokens: what it reads, writes and costs at most, first
      const p = m.preview || {};
      el.innerHTML = `<div class="sk-modal"><div class="sk-box wide"><h3>${esc(I18N.text('skillsv.act.testHead'))}: ${esc(m.name || '')}</h3>`
        + kv([[I18N.text('skillsv.k.task'), p.task], [I18N.text('skillsv.act.k.n'), p.n], [I18N.text('skillsv.cand.k.reads'), (p.reads || []).join(', ')], [I18N.text('skillsv.cand.k.writes'), (p.writes || []).join(', ')],
          [I18N.text('skillsv.act.k.tokens'), p.est_tokens != null ? Number(p.est_tokens).toLocaleString() : ''], [I18N.text('skillsv.cand.k.budget'), p.budget_usd != null ? I18N.text('skillsv.cand.usd', {n: p.budget_usd}) : '']])
        + (p.note ? `<div class="sk-note">${esc(p.note)}</div>` : '') + `<div class="sk-note">${esc(I18N.text('skillsv.act.testNote'))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.act.testGo'))}</button></div></div></div>`;
    } else if (m.kind === 'cases') {                   // run the cases: every command whole, in order, before anything runs
      const p = m.preview || {}, list = p.cases || p.commands || p.cmds || [];
      el.innerHTML = `<div class="sk-modal"><div class="sk-box wide"><h3>${esc(I18N.text('skillsv.cases.runHead'))}: ${esc(p.name || '')}</h3>`
        + `<div class="sk-pre">${list.map(c => esc(typeof c === 'string' ? c : [c.id, (c.check && c.check.cmd) || c.cmd || ''].filter(Boolean).join('  '))).join('\n')}</div>`
        + kv([[I18N.text('skillsv.ver.k.cwd'), p.cwd], [I18N.text('skillsv.ver.k.timeout'), p.timeout ? I18N.text('skillsv.ver.sec', {n: p.timeout}) : '']])
        + `<div class="sk-note">${esc(I18N.text('skillsv.cases.runNote', {n: list.length}))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.cases.runGo'))}</button></div></div></div>`;
    } else if (m.kind === 'gate') {                    // what the gate found when an improvement was laid: the cases before and after, and whether the old version came back
      const r = m.res || {}, rs = r.cases_result || [], uv = typeof r.utility === 'number' ? r.utility : utility(rs), cs = (m.cand && m.cand.cases) || [], taskOf = id => ((cs.find(c => c.id === id) || {}).task) || '', mark = v => v ? '\u2713' : '\u2717';
      el.innerHTML = `<div class="sk-modal"><div class="sk-box wide"><h3>${esc(r.reverted ? I18N.text('skillsv.cases.refused') : I18N.text('skillsv.cases.kept'))}</h3>`
        + `<div class="sk-case-t">${rs.map(c => `<div class="${c.before && !c.after ? 'bad' : ''}"><b>${esc(c.id)}</b><span>${esc(taskOf(c.id))}</span><em>${mark(c.before)} &rarr; ${mark(c.after)}</em></div>`).join('')}</div>`
        + `<div class="sk-who"><span class="w">${esc(I18N.text('skillsv.cases.better', {n: r.better == null ? 0 : r.better}))}</span><span class="w">${esc(I18N.text('skillsv.cases.worse', {n: r.worse == null ? 0 : r.worse}))}</span>${rs.length ? `<span class="w">${esc(I18N.text('skillsv.cases.utility', {n: (uv >= 0 ? '+' : '') + uv.toFixed(2)}))}</span>` : ''}</div>`
        + (r.reverted ? `<div class="sk-note sk-warn-t">${esc(I18N.text('skillsv.cases.revertNote'))}</div>` : '') + (r.error ? `<div class="sk-sub">${esc(r.error)}</div>` : '')
        + `<div class="sk-note">${esc(I18N.text('skillsv.cases.utilityNote'))}</div><div class="acts"><button class="sk-btn pri" data-act="mclose">${esc(I18N.text('skillsv.cases.ok'))}</button></div></div></div>`;
    } else if (m.kind === 'check') {                   // run a check: the whole command first, nothing runs before the confirm
      const p = m.preview || {};
      el.innerHTML = `<div class="sk-modal"><div class="sk-box wide"><h3>${esc(I18N.text('skillsv.ver.runHead'))}: ${esc(p.name || '')}</h3>`
        + kv([[I18N.text('skillsv.ver.k.cmd'), p.cmd], [I18N.text('skillsv.ver.k.cwd'), p.cwd], [I18N.text('skillsv.ver.k.timeout'), p.timeout ? I18N.text('skillsv.ver.sec', {n: p.timeout}) : '']])
        + `<div class="sk-note">${esc(I18N.text('skillsv.ver.runNote'))}</div><div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button>`
        + `<button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(I18N.text('skillsv.ver.runGo'))}</button></div></div></div>`;
    } else if (m.kind === 'promote') {                 // add a candidate to the real skills, or apply an improvement: the old version goes to a dated backup first
      const p = m.preview || {}, gl = (p.gate || []).map(g => typeof g === 'string' ? {cmd: g} : g), gate = gl.filter((g, i) => gl.findIndex(h => h.cmd === g.cmd && h.id === g.id) === i), runs = p.runs != null ? p.runs : 2 * gate.length, c = m.cand, d = p.diff || (SK.cand.diffs[c.id] || {}).diff;
      el.innerHTML = `<div class="sk-modal"><div class="sk-box wide"><h3>${esc(c.improves ? I18N.text('skillsv.cand.applyHead') : I18N.text('skillsv.cand.addHead'))}</h3>`
        + kv([[I18N.text('skillsv.k.name'), p.name || c.name], [I18N.text('skillsv.k.from'), p.from], [I18N.text('skillsv.k.to'), p.to], [I18N.text('skillsv.cand.k.backup'), p.backup]])
        + (d ? diffHtml(d) : '') + `<div class="sk-note">${esc(p.replaces ? I18N.text('skillsv.cand.replaceNote') : I18N.text('skillsv.cand.newNote'))}</div>`
        + (gate.length ? `<div class="sk-sec">${esc(I18N.text('skillsv.cases.gate'))}</div><div class="sk-pre">${gate.map(g => esc([g.id, g.cmd].filter(Boolean).join('  '))).join('\n')}</div><div class="sk-note">${esc(I18N.text('skillsv.cases.gateNote', {n: runs}))}</div>` : '')
        + (m.unver ? `<div class="sk-note sk-warn-t">${esc(I18N.text('skillsv.ver.unverNote'))}</div>` : '')
        + `<div class="acts"><button class="sk-btn" data-act="mclose">${esc(I18N.text('skillsv.cancel'))}</button><button class="sk-btn pri" data-act="mconfirm"${SK.busy ? ' disabled' : ''}>${esc(m.unver ? I18N.text('skillsv.ver.addUnver') : c.improves ? I18N.text('skillsv.cand.apply') : I18N.text('skillsv.cand.add'))}</button></div></div></div>`;
    }
  }
  const kv = rows => `<div class="sk-kv">${rows.filter(r => r[1]).map(r => `<b>${esc(r[0])}</b><span>${esc(r[1])}</span>`).join('')}</div>`;
  const openForm = f => { SK.form = f; SK.busy = false; fillModal(); const i = $('skPath'); if (i) i.focus(); };

  // ---- actions ----
  const cardOf = b => { const r = ((SK.data.requests) || []).find(x => x.req === b.dataset.req); return r && r.cards[Number(b.dataset.i)]; };
  async function doRecommend(skill, to) {
    const r = await act({action: 'advise', skill, to: to === '*' ? 'all' : to});
    if (r && r.ok !== false) { toast(I18N.text('skillsv.recommended')); load(true); }
  }
  const good = r => r && r.ok !== false && !r.need;
  async function askTemp(q, forWho) {                 // no searcher in the room: show what a temporary one (-P) would do, the user confirms
    if (!q) { toast(I18N.text('skillsv.writeFirst')); return; }
    const r = await act({action: 'temp_searcher', q, for: forWho || [], confirm: false});
    if (good(r)) openForm({kind: 'temp', q, for: forWho || [], preview: r.preview || {name: 'SKILLFIND', task: q}});
  }
  async function startJob(job, body) {                // preview first (nothing started), the modal confirms
    const r = await act({...body, action: job, confirm: false});
    if (good(r)) openForm({kind: 'job', job, body, preview: r.preview || {task: job}});
  }
  async function onAct(b) {
    const a = b.dataset.act, m = SK.form;
    if (a === 'updcheck' && SK.sel) {                  // read only: installed and available version
      const id = SK.sel; SK.upd[id] = {busy: true}; fillRows();
      const r = await act({action: 'update_check', skill: id});
      SK.upd[id] = good(r) && r.update ? {data: r.update} : {}; fillRows();
    } else if (a === 'updapply' && SK.sel) {
      const id = SK.sel, r = await act({action: 'update_apply', skill: id, confirm: false});
      if (good(r)) openForm({kind: 'update', skill: id, preview: r.preview || {name: (byId(id) || {}).name}});
    } else if (a === 'chatderive') { const desc = (SK.chatDesc || '').trim(); openForm(null); startJob('derive', {desc, source: {chat: true}}); }
    else if (a === 'derive' || a === 'suggest') {
      const desc = (SK.cand.desc || '').trim(), source = srcBody('derive');
      if (a === 'derive' && !desc && !(source && source.chat)) { toast(I18N.text('skillsv.writeFirst')); return; }
      if (source) startJob(a, a === 'derive' ? {desc, source} : {source});
    } else if (a === 'improve') { const source = srcBody('imp'); if (source && SK.sel) startJob('improve', {skill: SK.sel, source}); }
    else if (a === 'cpromote') {
      const c = cands().find(x => x.id === b.dataset.cid); if (!c) return;
      const r = await act({action: 'promote', id: c.id, confirm: false});
      if (good(r)) { const p = r.preview || {name: c.name}; openForm({kind: 'promote', cand: c, preview: p, unver: p.unverified != null ? !!p.unverified : 'verified' in c && !isVer(c)}); }
    } else if (a === 'measure' && SK.sel) {            // reads the local cost data and the usage registry; writes the result next to the skill, spends nothing
      const r = await act({action: 'measure', id: SK.sel});
      if (good(r)) { toast(r.measured && r.measured.tokens_saved != null ? I18N.text('skillsv.meas.done') : I18N.text('skillsv.meas.notEnough')); load(true); }
    } else if (a === 'lvset' && SK.sel) {              // metadata only, nothing runs: strategy > function > step, the server refuses a cycle or a wrong order
      const r = await act({action: 'level_set', id: SK.sel, level: $('skLv').value || null, parent: $('skPar').value || null});
      if (good(r)) { toast(I18N.text('skillsv.lv.saved')); load(true); }
    } else if (a === 'unusedf') { SK.unused = !SK.unused; animate(); fillChips(); fillRows();
    } else if (a === 'usescan') {                      // reads only the new part of the transcripts (the server stops after 20 s: press again when it says not finished)
      SK.scan = '...'; fillRows();
      const r = await act({action: 'usage_scan'}), sc = good(r) && r.scanned;
      SK.scan = sc ? I18N.text('skillsv.use.scanned', {n: sc.new, rooms: sc.rooms}) + (r.complete === false ? ' ' + I18N.text('skillsv.use.scanMore') : '') : '';
      await load(true); fillRows();
    } else if (a === 'caseadd' || a === 'casedel') {   // metadata only (the commands run only from "Run", after a confirm)
      const id = b.dataset.cid, x = skills().find(y => y.id === id) || cands().find(y => y.id === id); if (!x) return;
      const list = (x.cases || []).map(c => ({task: c.task, check: c.check}));
      if (a === 'casedel') list.splice(Number(b.dataset.i), 1);
      else { const t = (($('skCaseTask') || {}).value || '').trim(), c = (($('skCaseCmd') || {}).value || '').trim(); if (!t || !c) { toast(I18N.text('skillsv.writeFirst')); return; } list.push({task: t, check: {cmd: c, cwd: null, timeout: 110}}); }
      const r = await act({action: 'cases_set', id, cases: list.length ? list : null});
      if (good(r)) { if (a === 'caseadd') { const t = $('skCaseTask'), c = $('skCaseCmd'); if (t) t.value = ''; if (c) c.value = ''; } load(true); }
    } else if (a === 'casesrun') {
      const id = b.dataset.cid, r = await act({action: 'cases_run', id, confirm: false});
      if (good(r)) openForm({kind: 'cases', id, body: {action: 'cases_run', id}, preview: r.preview || {}});
    } else if (a === 'actcheck' && SK.sel) {           // free and local: reads the description only
      const id = SK.sel; SK.act[id] = {busy: true}; fillRows();
      const r = await act({action: 'activation_check', id});
      SK.act[id] = good(r) && r.check ? {data: r.check} : {}; fillRows();
    } else if (a === 'acttest' && SK.sel) {
      const id = SK.sel, r = await act({action: 'activation_test', id, confirm: false});
      if (good(r)) openForm({kind: 'acttest', id, name: (byId(id) || {}).name, body: {action: 'activation_test', id}, preview: r.preview || {}});
    } else if (a === 'chkrun') {                       // a skill or a candidate: the preview shows the command in full
      const id = b.dataset.cid, isC = id.startsWith('cand:'), body = isC ? {action: 'check_run', cand: id} : {action: 'check_run', skill: id};
      const r = await act({...body, confirm: false});
      if (good(r)) openForm({kind: 'check', id, body, preview: r.preview || {}});
    } else if (a === 'cdismiss') {
      const r = await act({action: 'dismiss', id: b.dataset.cid});
      if (good(r)) { if (SK.cand.sel === b.dataset.cid) SK.cand.sel = null; toast(I18N.text('skillsv.cand.dismissedOk')); load(true); }
    } else if (a === 'recommend') doRecommend(SK.sel, $('skTo').value);
    else if (a === 'addform') openForm({kind: 'path', path: '', preview: null});
    else if (a === 'mclose') openForm(null);
    else if (a === 'mpreview') {
      const p = ($('skPath').value || '').trim(); if (!p) return;
      m.path = p; SK.busy = true; fillModal();
      const r = await act({action: 'add', path: p});
      SK.busy = false;
      if (good(r)) m.preview = r.preview || {name: p.split(/[\/]/).filter(Boolean).pop(), from: p};
      fillModal();
    } else if (a === 'mconfirm') {
      if (m.kind === 'rec') { const to = $('skTo').value; openForm(null); await doRecommend(m.skill, to); return; }
      SK.busy = true; fillModal();
      const body = m.kind === 'path' ? {action: 'add', path: m.path, confirm: true} : m.kind === 'card' ? {action: 'add', req: m.req, card: m.card.name, confirm: true}
        : m.kind === 'update' ? {action: 'update_apply', skill: m.skill, confirm: true}
        : m.kind === 'check' || m.kind === 'acttest' || m.kind === 'cases' ? {...m.body, confirm: true}
        : m.kind === 'job' ? {...m.body, action: m.job, confirm: true} : m.kind === 'promote' ? {action: 'promote', id: m.cand.id, confirm: true, ...(m.unver ? {unverified_ok: true} : {})}
        : {action: 'temp_searcher', q: m.q, for: m.for, confirm: true};
      if (m.preview && m.preview.token) body.token = m.preview.token;   // the server hands a token with the preview; without it nothing runs
      const r = await act(body);
      SK.busy = false;
      if (good(r) && m.kind === 'job') { toast(I18N.text('skillsv.cand.jobStarted')); if (m.job === 'derive') { SK.cand.desc = ''; SK.chatDesc = ''; const t = $('skDesc'); if (t) t.value = ''; } openForm(null); load(true); }
      else if (good(r) && m.kind === 'update') { delete SK.upd[m.skill]; toast(I18N.text('skillsv.upd.done', {name: (byId(m.skill) || {}).name || ''}) + (r.restart ? ' ' + I18N.text('skillsv.upd.restart') : '')); openForm(null); load(true); }
      else if (m.kind === 'promote' && r && r.cases_result) { openForm({kind: 'gate', cand: m.cand, res: r}); load(true); }
      else if (good(r) && m.kind === 'cases') { SK.cres[m.id] = {results: r.results || []}; const ok = (r.results || []).filter(y => y.passed).length; toast(I18N.text('skillsv.cases.done', {a: ok, t: (r.results || []).length})); openForm(null); load(true); }
      else if (good(r) && m.kind === 'acttest') { toast(I18N.text('skillsv.act.started')); openForm(null); load(true); }
      else if (m.kind === 'check' && r && (r.ok !== false || r.exit != null)) { SK.chk[m.id] = {out: String(r.out || '').slice(-1500)}; toast(r.passed ? I18N.text('skillsv.ver.toastOk') : I18N.text('skillsv.ver.toastFail', {exit: r.exit == null ? I18N.text('skillsv.ver.timeout') : r.exit})); openForm(null); load(true); }
      else if (good(r) && m.kind === 'promote') { toast(I18N.text('skillsv.cand.promoted', {name: m.cand.name})); openForm(null); load(true); }
      else if (good(r)) { toast((m.kind === 'temp' ? I18N.text('skillsv.tempAsked') : I18N.text('skillsv.addedOk'))); if (m.kind === 'temp') { SK.searchQ = ''; const i = $('skSq'); if (i) i.value = ''; } openForm(null); load(true); } else fillModal();
    } else if (a === 'search') {
      const q = ($('skSq').value || '').trim(); if (!q) return;
      const r = await act({action: 'search', q, for: SK.searchFor});
      if (r && r.need === 'temp_searcher') askTemp(q, SK.searchFor);
      else if (good(r)) { SK.searchQ = ''; $('skSq').value = ''; toast(I18N.text('skillsv.searchSent')); load(true); }
    } else if (a === 'tempsearcher') askTemp((($('skSq') || {}).value || '').trim(), SK.searchFor);
    else if (a === 'cardadd') {
      const c = cardOf(b); if (!c) return;
      const r = await act({action: 'add', req: b.dataset.req, card: c.name});
      if (good(r)) openForm({kind: 'card', card: c, req: b.dataset.req, preview: r.preview || {name: c.name, brief: c.what, from: c.url || c.source}});
    } else if (a === 'cardrec') {
      const c = cardOf(b); if (!c) return;
      const s = skills().find(x => x.name === c.name);
      if (!s) { toast(I18N.text('skillsv.recNotAdded')); return; }
      openForm({kind: 'rec', card: c, skill: s.id});
    }
  }
  main.addEventListener('click', e => {
    if (e.target.classList && e.target.classList.contains('sk-modal') && SK.form) { openForm(null); return; }
    const t = e.target.closest('[data-tab],[data-close],[data-for],[data-origin],[data-sel],[data-goto],[data-act],[data-cand],[data-croom]');
    if (!t) return;
    if (t.dataset.close) open(false);
    else if (t.dataset.cand) pickCand(t.dataset.cand);
    else if (t.dataset.croom !== undefined) { SK.cand.room = t.dataset.croom; animate(); fillRoomChips(); fillCands(); }
    else if (t.dataset.tab !== undefined) { SK.tab = t.dataset.tab; keep(); animate(); shell(); }
    else if (t.dataset.for) { const n = t.dataset.for, i = SK.searchFor.indexOf(n); if (i < 0) SK.searchFor.push(n); else SK.searchFor.splice(i, 1); fillFor(); }
    else if (t.dataset.origin !== undefined) { SK.origin = t.dataset.origin; animate(); fillChips(); fillRows(); }
    else if (t.dataset.sel) pick(t.dataset.sel);
    else if (t.dataset.goto) { SK.sel = t.dataset.goto; SK.tab = 'explore'; keep(); animate('sk-animd'); shell(); const on = main.querySelector('.sk-row.on'); if (on) on.scrollIntoView({block: 'center'}); }
    else if (t.dataset.act) onAct(t);
  });
  main.addEventListener('input', e => {
    const t = e.target;
    if (t.id === 'skQ') { SK.q = t.value; fillRows(); } else if (t.id === 'skSq') SK.searchQ = t.value; else if (t.id === 'skDesc') SK.cand.desc = t.value; else if (t.id === 'skChatDesc') SK.chatDesc = t.value;
    else if (t.dataset && t.dataset.srcv) SK.cand.src[t.dataset.srcv].v = t.value;
  });
  main.addEventListener('change', e => {               // the source of a job: the kind (room, folder, repo) changes what the second field is
    const t = e.target, d = t.dataset || {};
    if (d.srcv) SK.cand.src[d.srcv].v = t.value;
    else if (d.srck) { const s = SK.cand.src[d.srck]; s.k = t.value; s.v = s.k === 'room' ? 'current' : ''; const box = t.closest('[data-srcbox]'), bt = box.querySelector('button'); box.innerHTML = srcHtml(d.srck) + (bt ? bt.outerHTML : ''); const i = box.querySelector('[data-srcv]'); if (i) i.focus(); }
  });
  main.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    if (e.target.id === 'skSq') { e.preventDefault(); onAct({dataset: {act: 'search'}}); }
    else if (e.target.id === 'skPath') { e.preventDefault(); onAct({dataset: {act: 'mpreview'}}); }
  });
  addEventListener('keydown', e => {
    if (!SK.open || SK.form && e.key !== 'Escape') return;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || '');
    if (e.key === 'Escape') {
      if (SK.form) openForm(null); else if (SK.sel && SK.tab === 'explore') { SK.sel = null; keep(); animate('sk-animd'); fillRows(); }
      else if (SK.cand.sel && SK.tab === 'cand') { SK.cand.sel = null; animate('sk-animd'); fillCands(); } else if (!typing) open(false);
      return;
    }
    if (SK.tab !== 'explore' && SK.tab !== 'cand' || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === '/' && !typing) { const q = $('skQ'); if (q) { e.preventDefault(); q.focus(); } }
    else if (/^Arrow(Down|Up|Left|Right)$/.test(e.key) && (!typing || (document.activeElement || {}).id === 'skQ' && /Down|Up/.test(e.key))) {   // walk the cards with the keyboard
      const hds = [...main.querySelectorAll('.sk-hd')]; if (!hds.length) return;
      const cur = hds.indexOf(document.activeElement), step = /Down|Right/.test(e.key) ? 1 : -1;
      if (cur < 0 && step < 0) return;
      e.preventDefault(); hds[Math.max(0, Math.min(hds.length - 1, cur + step))].focus();
    } else if ((e.key === 'Enter' || e.key === ' ') && !typing && document.activeElement && document.activeElement.dataset && (document.activeElement.dataset.sel || document.activeElement.dataset.cand)) { e.preventDefault(); const d = document.activeElement.dataset; if (d.cand) pickCand(d.cand); else pick(d.sel); }
  });

  function open(on) {
    SK.open = !!on;
    document.body.classList.toggle('sk-open', SK.open);
    btn.classList.toggle('on', SK.open);
    const u = new URL(location.href);
    if (SK.open) u.searchParams.set('view', 'skills'); else if (u.searchParams.get('view') === 'skills') u.searchParams.delete('view');
    history.replaceState(null, '', u);
    if (SK.open) { animate(); shell(); load(true); }
  }
  const btn = document.createElement('button');
  btn.className = 'icon-btn'; btn.id = 'skillsBtn'; btn.innerHTML = IC.spark;
  btn.addEventListener('click', () => open(!SK.open));
  const ob = document.getElementById('officeBtn');
  if (ob) ob.insertAdjacentElement('beforebegin', btn);
  // open the panel on one skill (the 3D office calls this for the heavy actions: check, activation, cases, improve)
  function show(id) {
    SK.sel = id || null; SK.tab = 'explore'; SK.origin = ''; SK.q = ''; SK.unused = false; keep(); animate('sk-animd'); open(true);
    setTimeout(() => { const on = main.querySelector('.sk-row.on'); if (on) on.scrollIntoView({block: 'center'}); }, 350);
  }
  window.skillsView = {open, show, toggle: () => open(!SK.open)};
  (typeof I18N_READY !== 'undefined' ? I18N_READY : Promise.resolve()).then(() => {
    try { btn.title = I18N.text('skillsv.btn'); } catch (e) {}
    if (new URLSearchParams(location.search).get('view') === 'skills') open(true);
  });
  setInterval(() => { if (SK.open && !document.hidden && !SK.form) load(); }, 4000);
})();
