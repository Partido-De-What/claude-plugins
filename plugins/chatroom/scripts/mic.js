/* The composer's microphone (1.3.5): dictation into the message box. Speech goes through the browser's own recognition (the Web
   Speech API: in Edge it is Microsoft's speech service, the one behind Windows dictation; in Chrome it is Google's). Where the
   page has none (the desktop app's pane, Firefox) the button puts the cursor in the box and says to use Windows dictation,
   Win+H, which types into any focused box. Nothing is recorded or kept by the chat room: the browser streams the audio to its
   speech service only while the button is lit. Sending the message stops it. */
(() => {
  const box = document.getElementById('box'), hintEl = document.getElementById('hint');
  if (!box) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = document.createElement('button');
  btn.id = 'micBtn'; btn.type = 'button';
  btn.innerHTML = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4M8 22h8"/></svg>';
  box.insertAdjacentElement('beforebegin', btn);
  let rec = null, base = '', said = '', hintTimer = 0, hintWas = null;

  const lang = () => {
    const l = (typeof config !== 'undefined' && config.lang) || (navigator.language || 'it').slice(0, 2);
    return l === 'it' ? 'it-IT' : l === 'en' ? 'en-US' : navigator.language || 'it-IT';
  };
  function hint(text) {                      // a few seconds in the line under the box, then its own text again
    if (!hintEl) return alert(text);
    if (hintWas === null) hintWas = hintEl.innerHTML;
    hintEl.textContent = text;
    clearTimeout(hintTimer);
    hintTimer = setTimeout(() => { hintEl.innerHTML = hintWas; hintWas = null; }, 6000);
  }
  function put(text) {
    if (!rec) return;                        // a late result after the stop (the message may be sent already)
    box.value = base + text;
    box.dispatchEvent(new Event('input', {bubbles: true}));
  }
  function stopRec() {
    const r = rec;
    rec = null;
    btn.classList.remove('rec');
    btn.title = I18N.text('viewer.mic');
    if (r) { r.onend = null; try { r.stop(); } catch (e) {} }
  }
  btn.addEventListener('click', () => {
    if (rec) return stopRec();
    if (!SR) { box.focus(); hint(I18N.text('viewer.micWin')); return; }
    const r = new SR();
    r.lang = lang(); r.continuous = true; r.interimResults = true;
    base = box.value ? box.value.replace(/\s*$/, ' ') : ''; said = '';
    r.onresult = e => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) said += e.results[i][0].transcript; else interim += e.results[i][0].transcript;
      }
      put(said + interim);
    };
    r.onerror = e => {
      if (e.error === 'no-speech' || e.error === 'aborted') return;     // a pause, or our own stop: onend restarts or ends it
      // network / service-not-allowed: the page has the API but no speech service behind it (an embedded browser): Windows dictation instead
      if (e.error === 'network' || e.error === 'service-not-allowed' || e.error === 'language-not-supported') { box.focus(); hint(I18N.text('viewer.micWin')); }
      else hint((e.error === 'not-allowed' ? I18N.text('viewer.micDenied') : I18N.text('viewer.micErr')) + ` (${e.error})`);
      stopRec();
    };
    r.onend = () => { if (rec === r) { try { r.start(); } catch (e) { stopRec(); } } };   // Chrome ends after a silence: listen on until the user stops
    try { r.start(); rec = r; btn.classList.add('rec'); btn.title = I18N.text('viewer.micStop'); box.focus(); }
    catch (e) { hint(I18N.text('viewer.micErr')); }
  });
  document.getElementById('send')?.addEventListener('click', stopRec);
  box.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) stopRec(); });
  (typeof I18N_READY !== 'undefined' ? I18N_READY : Promise.resolve()).then(() => { try { btn.title = I18N.text('viewer.mic'); } catch (e) {} });
})();
