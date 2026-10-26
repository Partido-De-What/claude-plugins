// Cards in the chat (cards.py): a message of kind 'card' drawn as a box of generic blocks (text, rows, form, bars, actions),
// its live state from cards.json, and its buttons answered by POST card_action. A type may get its own renderer with
// CARDS.register(type, (card, data, ro) => html); everything else is drawn from data.blocks. Read-only (ro) in another room's
// chat. A value typed in a field goes in the request body to the local server and is cleared at once: never in the page's
// state, the URL or an attribute.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const url = u => /^https?:\/\/[^\s"'<>]+$/.test(String(u || '')) ? String(u) : '';
  const STATES = {ok: '✓', bad: '✗', warn: '!', wait: '◌'};        // a shape as well as a colour
  const css = `
.xcard { margin: 8px auto; width: min(620px, 94%); background: var(--in); color: var(--text); border-radius: 10px; padding: 10px 12px;
  box-shadow: 0 1px .5px var(--shadow); border-top: 3px solid var(--accent); font-size: 13.5px; overflow-wrap: anywhere; }
.xcard .xc-head { display: flex; gap: 8px; align-items: center; font-weight: 700; font-size: 14px; }
.xcard .xc-head .xc-x { margin-left: auto; border: 0; background: transparent; color: var(--muted); cursor: pointer; font-size: 15px; }
.xcard .xc-text { margin: 6px 0; } .xcard .xc-note { color: var(--muted); font-size: 12px; margin-top: 6px; }
.xcard .xc-err { color: #d64545; font-size: 12.5px; margin-top: 6px; }
.xcard .xc-row { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; padding: 6px 0; border-top: 1px solid var(--border); }
.xcard .xc-row:first-child { border-top: 0; }
.xcard .xc-dot { font-size: 12px; } .xcard .ok { color: #25a55f; } .xcard .bad { color: #d64545; } .xcard .warn { color: #e0a000; } .xcard .wait { color: var(--muted); }
.xcard .xc-label { font-weight: 600; min-width: 120px; } .xcard .xc-value { color: var(--muted); flex: 1; min-width: 120px; }
.xcard input, .xcard select { border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; background: var(--input); color: var(--text);
  font: inherit; font-size: 13px; min-width: 0; max-width: 100%; }
.xcard button.xc-act { border: 1px solid var(--accent); background: transparent; color: inherit; border-radius: 14px; padding: 4px 12px;
  cursor: pointer; font: inherit; font-size: 12.5px; } .xcard button.xc-act:hover:not(:disabled) { background: var(--accent); color: #fff; }
.xcard button.xc-act:disabled { opacity: .5; cursor: default; }
.xcard .xc-form { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; margin: 6px 0; }
.xcard .xc-form label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--muted); }
.xcard .xc-bar { display: grid; grid-template-columns: minmax(90px, 32%) 1fr auto; gap: 6px; align-items: center; margin: 3px 0; font-size: 12.5px; }
.xcard .xc-bar i { display: block; height: 10px; border-radius: 5px; background: var(--accent); min-width: 2px; }
.xcard .xc-bar span:nth-child(2) { background: var(--border); border-radius: 5px; }
.xcard .xc-acts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.xcard a { color: var(--link); }
.xcard.xc-off { opacity: .7; font-size: 12.5px; padding: 5px 12px; cursor: pointer; }
@media (prefers-reduced-motion: no-preference) { .xcard .wait { animation: xc-pulse 1.4s ease-in-out infinite; } }
@keyframes xc-pulse { 50% { opacity: .3; } }
@media (max-width: 480px) { .xcard button.xc-act, .xcard input, .xcard select { min-height: 36px; } .xcard .xc-head .xc-x { width: 32px; height: 32px; }
  .xcard a { display: inline-block; padding: 8px 0; } }`;
  const act = (a, key, ro) => `<button class="xc-act" data-act="${esc(a.id)}"${key ? ` data-key="${esc(key)}"` : ''}${a.confirm ? ` data-confirm="${esc(a.confirm)}"` : ''}${ro || a.disabled ? ' disabled' : ''}>${esc(a.label)}</button>`;
  const field = (f, ro) => {
    const name = esc(f.name), label = esc(f.label || '');
    const input = f.type === 'select'
      ? `<select data-name="${name}"${ro ? ' disabled' : ''}>${(f.options || []).map(o => `<option value="${esc(o.value ?? o)}"${(o.value ?? o) === f.value ? ' selected' : ''}>${esc(o.label ?? o)}</option>`).join('')}</select>`
      : `<input data-name="${name}" type="${f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text'}" autocomplete="off" spellcheck="false"`
        + `${f.type === 'password' ? '' : ` value="${esc(f.value ?? '')}"`} placeholder="${esc(f.placeholder || '')}" aria-label="${label}"${ro ? ' disabled' : ''}>`;
    return label ? `<label>${label}${input}</label>` : input;
  };
  const BLOCKS = {
    text: b => `<div class="xc-text">${esc(b.text)}</div>`,
    rows: (b, ro) => (b.rows || []).map(r => `<div class="xc-row" data-row="${esc(r.key || '')}">`
      + (r.state ? `<span class="xc-dot ${esc(r.state)}" title="${esc(r.state)}" aria-hidden="true">${STATES[r.state] || '●'}</span>` : '')
      + `<span class="xc-label">${esc(r.label)}</span><span class="xc-value">${esc(r.value || '')}`
      + (url(r.link) ? ` <a href="${esc(url(r.link))}" target="_blank" rel="noopener noreferrer">${esc(r.link_label || I18N.text('card.link'))}</a>` : '') + '</span>'
      + (r.fields || []).map(f => field(f, ro)).join('') + (r.actions || []).map(a => act(a, r.key, ro)).join('') + '</div>').join(''),
    form: (b, ro) => `<div class="xc-form" data-row="${esc(b.key || '')}">${(b.fields || []).map(f => field(f, ro)).join('')}${b.submit ? act(b.submit, b.key, ro) : ''}</div>`,
    bars: b => {
      const top = Math.max(...(b.items || []).map(x => +x.max || +x.value || 0), 1e-9);
      return (b.title ? `<div class="xc-note">${esc(b.title)}</div>` : '') + (b.items || []).map(x => `<div class="xc-bar"><span>${esc(x.label)}</span>`
        + `<span><i style="width:${Math.max(0, Math.min(100, (+x.value || 0) / top * 100)).toFixed(1)}%"></i></span>`
        + `<span>${esc(x.value ?? '—')}${b.unit ? ' ' + esc(b.unit) : ''}${x.note ? ' · ' + esc(x.note) : ''}</span></div>`).join('');
    },
    actions: (b, ro) => `<div class="xc-acts">${(b.items || []).map(a => act(a, b.key, ro)).join('')}</div>`,
  };
  const CARDS = {
    state: {}, types: {}, msgs: new Map(),
    register(type, fn) { this.types[type] = fn; },
    html(m, ro) {
      const card = m.card, s = ro ? {} : this.state[card.id] || {}, d = {...card.data, ...s};   // another room's card: never this room's state
      if (s.dismissed) return `${esc(d.icon || '🗂')} ${esc(d.title || m.text)}`;
      const body = this.types[card.type] ? this.types[card.type](card, d, ro)
        : (d.blocks || []).map(b => (BLOCKS[b.t] || (() => ''))(b, ro)).join('');
      return `<div class="xc-head">${esc(d.icon || '🗂')} <span>${esc(d.title || '')}</span>`
        + (ro ? '' : `<button class="xc-x" data-act="dismiss" title="${esc(I18N.text('card.dismiss'))}">✕</button>`) + '</div>' + body
        + (d.note ? `<div class="xc-note">${esc(d.note)}</div>` : '') + (d.error ? `<div class="xc-err">${esc(d.error)}</div>` : '')
        + `<div class="xc-note" style="text-align:right"><span class="num">#${+m.n} ${esc(m.time || '')}</span></div>`;
    },
    // the element of a card message, or null when it is not a card the page can draw (the viewer then shows its text)
    build(m, ro) {
      if (!m.card || typeof m.card !== 'object' || !m.card.id || !m.card.data) return null;
      if (!ro) this.msgs.set(m.card.id, m);
      if (!ro && !this.asked) { this.asked = true; setTimeout(() => this.load(), 0); }       // the state of the cards at once, not after the first 3 s
      const el = document.createElement('div');
      el.className = 'xcard' + (!ro && (this.state[m.card.id] || {}).dismissed ? ' xc-off' : '');
      el.dataset.card = m.card.id;
      if (ro) el.dataset.ro = '1';
      el.innerHTML = this.html(m, ro);
      return el;
    },
    redraw(id) {
      const m = this.msgs.get(id);
      if (!m) return;
      document.querySelectorAll(`.xcard[data-card="${id}"]:not([data-ro])`).forEach(el => {
        el.className = 'xcard' + ((this.state[id] || {}).dismissed ? ' xc-off' : '');
        el.innerHTML = this.html(m, false);
      });
    },
    async load() {                                    // state written by the producers (a ping that ended, a key verified)
      if (!this.msgs.size) return;
      try {
        const r = await fetch('cards.json?t=' + Date.now(), {cache: 'no-store'});
        if (!r.ok) return;
        const next = await r.json();
        for (const id of this.msgs.keys()) if (JSON.stringify(next[id]) !== JSON.stringify(this.state[id])) { this.state[id] = next[id]; this.redraw(id); }
      } catch (e) {}
    },
    async send(id, action, key, values) {
      try {
        const r = await fetch('card_action', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, action, key, values})});
        const text = await r.text();
        if (!r.ok) this.state[id] = {...(this.state[id] || {}), error: text.slice(0, 300) || I18N.text('card.failed')};
        else {
          this.state[id] = JSON.parse(text);
          const go = this.state[id].open;                  // a login page (OpenRouter PKCE): the answer names it, the user clicked for it
          if (/^https:\/\/[^\s"'<>]+$/.test(go || '')) window.open(go, '_blank', 'noopener');
        }
      } catch (e) { this.state[id] = {...(this.state[id] || {}), error: I18N.text('card.unreachable')}; }
      this.redraw(id);
    },
  };
  if (typeof document !== 'undefined' && document.head) {
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    document.addEventListener('click', e => {
      const box = e.target.closest && e.target.closest('.xcard');
      if (!box || box.dataset.ro) return;
      const id = box.dataset.card;
      if (box.classList.contains('xc-off') && !e.target.closest('[data-act]')) {      // a dismissed card opens again on a click
        return CARDS.send(id, 'reopen', '', {});                        // the server keeps it open: the next load does not close it again
      }
      const b = e.target.closest('[data-act]');
      if (!b || b.disabled) return;
      if (b.dataset.confirm && !confirm(b.dataset.confirm)) return;
      const scope = b.closest('[data-row]') || box, values = {};
      scope.querySelectorAll('[data-name]').forEach(i => { values[i.dataset.name] = i.value; if (i.type === 'password') i.value = ''; });
      box.querySelectorAll('button').forEach(x => { x.disabled = true; });
      CARDS.send(id, b.dataset.act, b.dataset.key || scope.dataset.row || '', values);
    });
    setInterval(() => CARDS.load(), 3000);
  }
  window.CARDS = CARDS;
})();
