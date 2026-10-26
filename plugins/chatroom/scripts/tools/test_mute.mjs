// Audio off by default (0.13, Adrian's decision): a page that never saved its levels is silent, every source; saved levels stay.
// node plugins/chatroom/scripts/tools/test_mute.mjs
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0, n = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };
const SOURCES = ['tv', 'arcade', 'radio', 'lofi'];
globalThis.addEventListener ??= () => {};          // what the module touches of the page when it loads
async function page(saved) {                       // a fresh module per case, with this page's localStorage
  globalThis.localStorage = {getItem: k => (k === 'chatroom.mix.v2' ? saved : null), setItem() {}};
  return import(pathToFileURL(path.join(S, 'office-tv.js')).href + `?case=${n++}`);
}
let tv = await page(null);
test('a new page: every source at 0', SOURCES.filter(k => tv.mixLevel(k) !== 0).join(','));
test('a new page: soundOn() is false (chime and games stay quiet)', tv.soundOn() ? 'true' : '');
tv = await page('{broken');
test('a broken saved mix: still silent', SOURCES.some(k => tv.mixLevel(k) !== 0) || tv.soundOn() ? 'sound' : '');
tv = await page(JSON.stringify({master: 0.3, tv: 0.5, arcade: 0.5, radio: 1, lofi: 1, mute: {}}));
test('levels saved with sound on keep their sound', tv.soundOn() && Math.abs(tv.mixLevel('tv') - 0.15) < 1e-9 ? '' : `${tv.mixLevel('tv')}`);
tv = await page(JSON.stringify({master: 0, mute: {master: true, tv: true, arcade: true, radio: true, lofi: true}}));
test('the mute set by hand in the rooms stays silent', SOURCES.some(k => tv.mixLevel(k) !== 0) || tv.soundOn() ? 'sound' : '');
tv = await page(JSON.stringify({master: 0.8, mute: {master: false, tv: true}}));
test('unmuted from the mixer: the general level comes back, a muted source stays muted', tv.soundOn() && tv.mixLevel('tv') === 0 && tv.mixLevel('radio') === 0.8 ? '' : `${tv.mixLevel('tv')} ${tv.mixLevel('radio')}`);
console.log(`\n${passed}/${total} passed`);
