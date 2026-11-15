// The chat redesign (0.19, D5): nothing of the 0.18 viewer is lost. Every id the script reaches still exists in the page or is made by it,
// the controls keep their ids, the chrome has no emoji button, the tokens are there, and en/it carry the new texts. Static checks on viewer.html.
// node plugins/chatroom/scripts/tools/test_viewer_redesign.mjs
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(S, 'viewer.html'), 'utf8');
const loc = l => JSON.parse(fs.readFileSync(path.join(S, '..', 'locales', `${l}.json`), 'utf8'));
let passed = 0, total = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };

// ids the page declares, ids a script creates (views inject their own buttons), ids the script reads with $('x') / getElementById
const declared = new Set([...html.matchAll(/\bid="([\w-]+)"/g)].map(m => m[1]));
const injected = new Set(['spawnBtn', 'skillsBtn', 'previewBtn', 'headroom', 'rs']);   // made by spawn-view / skills-view / preview-view / the research tab
const read = [...new Set([...html.matchAll(/(?:\$|getElementById)\('([\w-]+)'\)/g)].map(m => m[1]))];
const missing = read.filter(id => !declared.has(id) && !injected.has(id) && !new RegExp(`id=\\\\?["']${id}["']|id="${id}"|\\bid=\\$\\{`).test(html));
test('every id the script reads exists in the page', missing.length ? missing.join(', ') : '');

const keep = ['feed', 'box', 'send', 'attach', 'cmdBtn', 'suggest', 'pending', 'hint', 'search', 'searchBtn', 'soundBtn', 'gear', 'researchBtn', 'officeBtn', 'gicon', 'newer', 'empty',
  'fTitle', 'pTitle', 'pClose', 'pSave', 'preview', 'pvB', 'pvTo', 'd-tokens'];
const gone = keep.filter(id => !declared.has(id));
test('the controls of 0.18 keep their ids, the new ones are there', gone.join(', '));

test('the public API of the viewer is untouched', ['jumpTo', 'snapshot', 'tag', 'chatroom:data', 'chatroom:scope', 'chatroom:common'].filter(k => !html.includes(k)).join(', '));
test('the poll keeps ETag and Range', ['If-None-Match', 'Range'].filter(k => !html.includes(k)).join(', '));

const emojiBtn = [...html.matchAll(/<button[^>]*id="(?:researchBtn|officeBtn|searchBtn|soundBtn|gear|cmdBtn|attach|send)"[^>]*>([^<]*)</g)].filter(m => /[^\x00-\x7f]/.test(m[1])).map(m => m[0].slice(0, 40));
test('no emoji button left in the header and the composer', emojiBtn.join(' | '));
test('line icons come from one helper', /const ic = /.test(html) ? '' : 'ic() missing');

test('tokens: one style block with the --d-* set, dark overrides', ['--d-accent', '--d-grad', '--d-card', '--d-line', '--d-r-pill'].filter(k => !html.includes(k)).join(', ') || (html.includes('prefers-color-scheme: dark') ? '' : 'no dark'));
test('reduced motion is honored', html.includes('prefers-reduced-motion') ? '' : 'missing');

const want = ['viewer.preview', 'viewer.previewTo', 'viewer.navMove', 'viewer.navPick', 'viewer.navClose'];
for (const l of ['en', 'it']) {
  const L = loc(l);
  test(`${l}: the new texts exist`, want.filter(k => !L[k]).join(', '));
  test(`${l}: the hint no longer carries the emoji`, /⚡/.test(L['viewer.hint']) ? L['viewer.hint'] : '');
}
test('previewTo is declared with its {who}', /previewTo: \['who'\]/.test(html) ? '' : 'VIEW_ARGS');

// the palette: every quick command key of the server has an icon entry, or falls back to the server's emoji
const chat = fs.readFileSync(path.join(S, 'chat.py'), 'utf8');
const keys = [...(/^COMMANDS = \{([^}]*)\}/m.exec(chat)?.[1] ?? '').matchAll(/'(\w+)':/g)].map(m => m[1]);
test('palette knows the quick command keys', keys.length < 8 ? `found ${keys.length}` : keys.filter(k => !new RegExp(`\\b${k}: \\[`).test(html)).join(', '));

// E3: a quick command picked in the palette goes out at once, as before the redesign; the preview is only for typed text
const pickFn = /function pick\(i\) \{[\s\S]*?\n\}/.exec(html)?.[0] ?? '';
test('palette: a picked quick command is sent at once, no chip waiting for a second Enter', pickFn.includes("x.kind === 'cmd') return runCommand(x)") && !/cmdSel|cmdChip/.test(html) ? '' : 'the command waits');

// T17 (0.19.9): every icon-only button of the toolbar and the composer has a visible word, en and it, and it survives the sound icon being redrawn
const lbl = Object.fromEntries([.../BTN_LABELS = \{([\s\S]*?)\};/.exec(html)?.[1].matchAll(/(\w+): \(\) => I18N\.text\('viewer\.lbl\.(\w+)'\)/g) ?? []].map(m => [m[1], m[2]]));
const iconBtns = ['researchBtn', 'skillsBtn', 'previewBtn', 'spawnBtn', 'officeBtn', 'searchBtn', 'soundBtn', 'gear', 'cmdBtn', 'attach'];
test('toolbar: each icon-only button has a label key, and the key exists in en and it', iconBtns.filter(id => !lbl[id]).join(', ') ||
  ['en', 'it'].flatMap(l => iconBtns.filter(id => !loc(l)[`viewer.lbl.${lbl[id]}`]).map(id => `${l}:${id}`)).join(', '));
test('toolbar: the label is drawn on config, at load (injected buttons) and after the sound icon is redrawn; a hidden button stays hidden',
  /labelBtns\(\);\s*\}/.test(html) && /I18N_READY \|\| Promise\.resolve\(\)\)\.then\(labelBtns\)/.test(html) && /ic\(on \? 'bell' : 'bellOff'\)[^}]*labelBtns\(\)/.test(html) && html.includes('.icon-btn[hidden] { display: none; }') ? '' : 'missing');

// the Skills panel, Explore tab (T16): cards that open in place, one select for the recommendation, themed scrollbars, Esc closes the card first
const sk = fs.readFileSync(path.join(S, 'skills-view.js'), 'utf8');
test('skills: grid of cards, the header toggles, the detail sits inside the card', ['class="sk-hd" data-sel', "grid-column: 1 / -1", 'function detail(', 'sk-unfold'].filter(k => !sk.includes(k)).join(', '));
test('skills: no list+detail leftovers', ['skDetail', 'phoneDetail', 'sk-back'].filter(k => sk.includes(k)).join(', '));
test('skills: scrollbars follow the theme', ['scrollbar-color', 'color-scheme: dark'].filter(k => !sk.includes(k)).join(', '));
test('skills: Esc closes the open card before the panel', /SK\.sel && SK\.tab === 'explore'\) \{ SK\.sel = null/.test(sk) ? '' : 'missing');

// T28: a phone must not scroll sideways: the parked settings panel is not rendered, the page clips, the Skills panel survives the office-only mode
const ou = fs.readFileSync(path.join(S, 'office-ui.js'), 'utf8');
test('phone: closed settings panel is hidden, open one visible, page clips x', ['#panel { position: fixed', 'visibility: hidden', '#panel.open { transform: none; visibility: visible', 'overflow-x: clip'].filter(k => !html.replace(/\s+/g, ' ').includes(k)).join(', '));
test('office-only mode keeps the Skills panel', /body\.mode-office > :not\(#office\)[^{]*:not\(#skillsView\)/.test(ou) ? '' : 'missing');

test('phone: the room chips stay on one swipeable row, the message preview is capped', ['.scope { flex-wrap: nowrap; overflow-x: auto', '#preview.show { max-height: min(280px, 34vh)'].filter(k => !html.includes(k)).join(', '));

test('phone: the seven header buttons stay on one row (375 px, Italian too) and the message count stays in sight', ['padding: 4px 3px; min-width: 0', '.strip .count { position: sticky'].filter(k => !html.includes(k)).join(', '));

// T37: the eighth button (a research room) must not wrap "Settings" onto a second row on a phone: all the buttons sit in one #tools box that does not wrap and swipes
const flat = html.replace(/\s+/g, ' ');
const toolsBox = /<div class="tools" id="tools">([\s\S]*?)<\/div>/.exec(html)?.[1] ?? '';
test('phone: every header button sits in one #tools row that never wraps and swipes sideways',
  ['researchBtn', 'officeBtn', 'searchBtn', 'soundBtn', 'gear'].filter(id => !toolsBox.includes(`id="${id}"`)).join(', ') ||
  (/\.tools \{ display: contents; \}/.test(flat) && /\.tools \{ display: flex; flex: 1 1 100%; min-width: 0; flex-wrap: nowrap;[^}]*overflow-x: auto/.test(flat) ? '' : 'css missing'));

console.log(`${passed}/${total}`);
process.exit(passed === total ? 0 : 1);
