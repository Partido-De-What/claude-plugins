// Writes scripts/idle_spots.json: the places an idle agent may take in the default office, with their ids, zones and the
// 24x14 map of the zones (office-layout.js idleSpots). chat.py reads it when the user's own office has not published its
// list yet. Run it again when the default layout changes: node plugins/chatroom/scripts/tools/idle_spots.mjs
import {writeFileSync} from 'node:fs';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const url = f => pathToFileURL(path.join(S, f)).href;
globalThis.I18N ??= {tables: () => ({}), table: () => ({}), text: k => k, t: k => k};   // office-arcade.js reads its texts when used, not when loaded
const {DEFAULT_LAYOUT, resolve, floorPlan, idleSpots} = await import(url('office-layout.js'));
const {ARCADE_AT} = await import(url('office-arcade.js'));

export function defaultIdleSpots() {
  const placed = resolve(DEFAULT_LAYOUT);
  placed.boxes.push({x: ARCADE_AT.x, z: ARCADE_AT.z, hw: ARCADE_AT.hw, hd: ARCADE_AT.hd, rot: ARCADE_AT.rot});   // as the office adds it
  return idleSpots(DEFAULT_LAYOUT, placed, floorPlan(DEFAULT_LAYOUT, placed));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const out = defaultIdleSpots();
  writeFileSync(path.join(S, 'idle_spots.json'), JSON.stringify(out, null, 1) + '\n');
  console.log(`idle_spots.json: ${out.spots.length} places, ${out.zones.length} zones`);
}
