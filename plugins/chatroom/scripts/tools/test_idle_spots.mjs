// Life in idle: the places list chat.py reads (idle_spots.json) matches the default office, and every place is sound.
// node plugins/chatroom/scripts/tools/test_idle_spots.mjs
import {readFileSync} from 'node:fs';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0;
const test = (name, fn) => {
  total++;
  try { const bad = fn(); if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } }
  catch (e) { console.log(`FAIL ${name}: ${e.stack || e}`); }
};
const {defaultIdleSpots} = await import(pathToFileURL(path.join(S, 'tools', 'idle_spots.mjs')).href);
const now = defaultIdleSpots(), saved = JSON.parse(readFileSync(path.join(S, 'idle_spots.json'), 'utf8'));

test('idle_spots.json is up to date with the default office (run tools/idle_spots.mjs after a layout change)',
  () => JSON.stringify(now) === JSON.stringify(saved) ? '' : `${saved.spots.length} saved, ${now.spots.length} now`);
test('ids run 1..N with no gap', () => now.spots.every((s, i) => s.id === i + 1) ? '' : 'ids out of order');
test('every place is in a known zone', () => now.spots.every(s => now.zones.some(z => z.key === s.zone)) ? '' : now.spots.filter(s => !now.zones.some(z => z.key === s.zone)).map(s => s.id).join(','));
test('no games and no work seats: only coffee and common', () => now.spots.every(s => s.tag === 'coffee' || s.tag === 'common') ? '' : 'other tags');
test('the map is 14 rows of 24', () => now.grid.length === 14 && now.grid.every(r => r.length === 24) ? '' : `${now.grid.length} rows`);
test('zone keys are single distinct letters', () => new Set(now.zones.map(z => z.key)).size === now.zones.length && now.zones.every(z => /^[A-Z]$/.test(z.key)) ? '' : 'bad keys');
test('enough places for a full room of idle agents (at least 20)', () => now.spots.length >= 20 ? '' : `${now.spots.length}`);
console.log(`\n${passed}/${total} passed`);
