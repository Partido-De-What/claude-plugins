// The Hangar of the Gates: the look of a spawn room (config.mode === 'spawn'), the room where agents on external models work.
// A night hangar where the agents come from other worlds through gates, one per provider. Same plan, same places, same
// functions as the office (arcade, TV, radio, arena...): the pictures change, and a few live pieces are added:
// - the gates of the providers (a lit arch each, its colour from the provider's id, red when it has no quota left), with
//   a tank of the day's free quota on the pillar; a role that comes in flashes at its gate, a role that changes host
//   sends a streak from one gate to the other; the mysterious gate openrouter/free lets out a shadow now and then;
// - the departures board (split-flap): role, model, host, state; "no tokens" blinks;
// - the holographic table: the AA index and the strong points of the models the roles run on;
// - the Headroom press and the RTK funnel, working while they compress, with the tokens saved;
// - a role with no tokens left: its figure stops, a pager pulses over its head; a click asks for its replacement
//   (event chatroom:replace, the card Sostituisci of the viewer);
// - six easter eggs, all mute: the Konami code on the board (credits), seven clicks on a gate (a llama), the cave
//   painting (the tokens caveman saved), a trophy on the desk of a role whose model is first in a benchmark, the board
//   asleep between midnight and one, the shadow of openrouter/free.
// Pixel art drawn in canvases like office-floor.js and office-lab.js, no images, no sounds. office.js loads this file only
// for spawn rooms (import() on demand); it uses the lab's interface (THEME, FLOOR, sky, install, item, MODELS, withLab)
// and start() for the live pieces. The data come from GET /spawn.json (chat.py, REGIA): a 404 leaves the hangar empty
// but for the mysterious gate; ?hangar=demo feeds made-up data that change by themselves (previews, tests).
import {PX, rnd, shade, dot, speckle, makeTexture} from './office-floor.js';
import {CATALOG} from './office-layout.js';

export const HANGAR = true;
export const PALETTE = {
  night: '#070b18', steel: '#7d8794', steelD: '#3d4654', steelL: '#aab4c0', ink: '#15171c',
  yellow: '#ffd400', cyan: '#38e8ff', red: '#ff1744', gold: '#ffc83d', holo: '#5ef0ff', violet: '#b388ff',
};
/** colours that office.js reads: walls, ceiling, the parts of blindWall(), the ceiling panels, the cold night light */
export const THEME = {
  wall: '#3d4654', ceiling: '#1a1f29',
  wallPal: {skirt: '#1d222b', base: '#2a313c', door: '#56606e', win: '#7c8a9c', blind: '#2f3846', sill: '#606b7a', cap: PALETTE.yellow, cap2: '#1d222b'},
  light: '#cfe3ff', hemi: ['#9bb7ff', '#141a28'], sun: '#9fb4ff', lamp: '#8fb8ff',
};

// ------------------------------------------------------------------ the pictures
const tread = (base, seed) => (g, w, h) => {                       // diamond tread plate: raised diagonal studs, alternating
  const r = rnd(seed), hi = shade(base, 1.35), lo = shade(base, 0.68);
  g.fillStyle = base; g.fillRect(0, 0, w, h); speckle(g, w, h, r, w * h / 8, base, 0.06);
  for (let y = 0; y < h; y += 8) for (let x = (y / 8) % 2 * 4; x < w; x += 8) {
    const up = ((x + y) / 4) % 2;
    for (let k = 0; k < 4; k++) { const px = (x + (up ? k : 3 - k)) % w, py = (y + k) % h; dot(g, px, py, hi); dot(g, (px + 1) % w, (py + 1) % h, lo); }
  }
};
function carbon(g, w, h) {                                          // carbon fibre: a 2x2 twill, lit threads
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const t = ((x >> 1) + (y >> 1)) % 4 < 2, s = (x + y) % 2;
    dot(g, x, y, t ? (s ? '#2c3139' : '#23272e') : (s ? '#1b1e24' : '#202329'));
  }
}
function grid(g, w, h) {                                            // neon grid: cyan lines every 50 cm, brighter every 2 m
  g.fillStyle = '#0b1020'; g.fillRect(0, 0, w, h); speckle(g, w, h, rnd(301), w * h / 10, '#0b1020', 0.3);
  for (let i = 0; i < w; i += 16) { g.fillStyle = i ? '#1a5f7a' : PALETTE.cyan; g.fillRect(i, 0, 1, h); g.fillRect(0, i, w, 1); }
}
function hazard(g, w, h) {                                          // safety stripes, yellow and black at 45 degrees
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) dot(g, x, y, Math.floor((x + y) / 8) % 2 ? PALETTE.ink : PALETTE.yellow);
}
function rivets(g, w, h) {                                          // riveted wall panels, 1 m: seams, a row of rivets top and bottom
  const r = rnd(311), base = '#4a5462';
  g.fillStyle = base; g.fillRect(0, 0, w, h); speckle(g, w, h, r, w * h / 6, base, 0.07);
  g.fillStyle = '#2b323c'; g.fillRect(0, 0, 1, h); g.fillRect(0, 0, w, 1); g.fillRect(0, h - 1, w, 1);
  g.fillStyle = '#6a7584'; g.fillRect(1, 1, w - 1, 1);
  for (let x = 3; x < w - 1; x += 4) for (const y of [3, h - 4]) { dot(g, x, y, '#9aa6b5'); dot(g, x + 1, y + 1, '#262c35'); }
}
function pad(g, w, h) {                                             // a landing pad: dark, a yellow ring and an H, blue lights round it
  g.fillStyle = '#10161f'; g.fillRect(0, 0, w, h);
  const cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.36;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy); if (Math.abs(d - R) < 1.6) dot(g, x, y, PALETTE.yellow); }
  const s = R * 0.55; g.fillStyle = PALETTE.yellow;
  g.fillRect(cx - s * 0.6, cy - s, 3, 2 * s); g.fillRect(cx + s * 0.6 - 3, cy - s, 3, 2 * s); g.fillRect(cx - s * 0.6, cy - 1, s * 1.2, 3);
  for (let x = 3; x < w - 2; x += 6) { dot(g, x, 2, '#4fc3ff'); dot(g, x, h - 3, '#4fc3ff'); }
  for (let y = 3; y < h - 2; y += 6) { dot(g, 2, y, '#4fc3ff'); dot(g, w - 3, y, '#4fc3ff'); }
}
// each kind: m = metres one texture covers (w x h = m * PX; `h` in pixels when it differs), rough, metal, draw(g, w, h)
const KINDS = {
  hgPlate: {m: 1, rough: 0.55, metal: 0.35, draw: tread('#5b6470', 201)}, hgPlateDark: {m: 1, rough: 0.55, metal: 0.35, draw: tread('#3b424c', 202)},
  hgPlateLight: {m: 1, rough: 0.5, metal: 0.35, draw: tread('#7a838e', 203)}, hgCarbon: {m: 0.5, rough: 0.35, metal: 0.2, draw: carbon},
  hgGrid: {m: 2, rough: 0.4, draw: grid}, hgHazard: {m: 1, rough: 0.7, draw: hazard}, hgPad: {fit: true, rough: 0.6, draw: pad},
  hgHazardBand: {m: 1, h: 10, rough: 0.7, draw: hazard}, hgRivet: {m: 1, h: 14, rough: 0.5, metal: 0.35, draw: rivets},
};
/** the office's floor kinds seen as hangar kinds (office-floor.js buildFloor: the zones keep their names, the pictures change) */
export const FLOOR = {
  alias: {carpet: 'hgPlate', booth: 'hgPlateDark', parquet: 'hgCarbon', parquetLight: 'hgPlateDark', common: 'hgGrid', tiles: 'hgPlateLight',
          stone: 'hgPlateDark', game: 'hgGrid', mat: 'hgHazard', rug: 'hgPad'},
  kinds: KINDS,
};

let V = null, CTX = null;                                           // office-voxel.js and the context, from install()
const made = new Map();
const texture = name => { const K = KINDS[name]; if (!made.has(name)) made.set(name, makeTexture(CTX, K.draw, K.m * PX, K.h || K.m * PX)); return made.get(name); };

// ------------------------------------------------------------------ the light
/** the night of the hangar, after every change of the sky (office.js drawSky sets the office's light first) */
export function sky({sun, hemi, lamps}) {
  sun.color.set(THEME.sun); sun.intensity = 1.05;
  hemi.color.set(THEME.hemi[0]); hemi.groundColor.set(THEME.hemi[1]); hemi.intensity = 0.7;
  for (const l of lamps) if (l.position.y < 3.5) l.color.set(THEME.lamp);        // the arena above keeps the colours of its teams
  CTX?.scene?.background?.set(PALETTE.night);
}

// ------------------------------------------------------------------ the furniture
// The bodies of the live pieces are pieces of the plan (CATALOG types, built by item()): office-merge.js bakes them with the rest.
// What moves or changes colour is added by install() on InstancedMesh and one texture atlas.
const vm = (v, pivot, opts = {}) => V.mesh(v, {pivot, scale: 0.05, jitter: 0.04, ...opts});
function workDesk() {                    // 1.6 x 0.8 m, top at 0.7 m (the office's size): a carbon top with a cyan edge, steel legs, a hazard line
  const v = new V.Vox(), P = PALETTE;
  v.box(0, 13, 0, 31, 13, 15, (x, y, z) => ((x >> 1) + (z >> 1)) % 2 ? '#262a31' : '#1d2026').box(0, 13, 15, 31, 13, 15, P.cyan).box(0, 12, 15, 31, 12, 15, P.steelD);
  for (const x of [1, 29]) v.box(x, 1, 7, x + 1, 12, 8, P.steel).box(x, 0, 1, x + 1, 0, 14, P.steelD);
  v.box(1, 3, 7, 30, 3, 8, P.steel);
  v.box(3, 6, 1, 28, 10, 1, P.steelD).box(3, 11, 1, 28, 11, 1, (x) => Math.floor(x / 2) % 2 ? P.ink : P.yellow);
  v.box(21, 1, 3, 27, 11, 14, '#2b313a');
  for (const y of [4, 8]) v.box(21, y, 14, 27, y, 14, P.ink);
  for (const y of [2, 6, 10]) v.box(23, y, 15, 25, y, 15, P.steelL);
  return vm(v, [16, 0, 8]);
}
function portal(mystery = false) {       // a gate 1.0 x 0.3 m, 2.3 m high, facing +z: steel pillars with rivets and hazard feet, a lintel, the tank's glass on the right pillar
  const v = new V.Vox(), S = mystery ? '#4a3a5c' : PALETTE.steel, D = PALETTE.steelD, haz = (x, y) => Math.floor((x + y) / 2) % 2 ? PALETTE.ink : PALETTE.yellow;
  v.box(0, 0, 0, 19, 0, 5, D);
  v.box(0, 1, 0, 2, 45, 5, S).box(17, 1, 0, 19, 45, 5, S).box(0, 42, 0, 19, 45, 5, S);
  v.box(0, 1, 5, 2, 7, 5, haz).box(17, 1, 5, 19, 7, 5, haz);
  for (let y = 10; y < 42; y += 5) v.set(1, y, 5, PALETTE.steelL).set(18, y, 5, PALETTE.steelL);
  if (!mystery) v.box(18, 8, 6, 18, 34, 6, '#0c1822').box(17, 7, 6, 19, 7, 6, D).box(17, 35, 6, 19, 35, 6, D);
  return vm(v, [10, 0, 3]);
}
function holoTable() {                   // 2.6 x 0.9 m, 0.75 m high: a dark steel body, a glass top lit from inside, the projector in the middle
  const v = new V.Vox();
  v.box(2, 0, 2, 49, 1, 15, PALETTE.steelD).box(4, 2, 4, 47, 12, 13, '#252b34').box(0, 13, 0, 51, 13, 17, PALETTE.steel);
  v.box(1, 14, 1, 50, 14, 16, '#0e3a48').box(0, 14, 0, 51, 14, 0, PALETTE.cyan).box(0, 14, 17, 51, 14, 17, PALETTE.cyan);
  v.box(23, 15, 7, 28, 15, 10, PALETTE.steelL).box(25, 16, 8, 26, 16, 9, PALETTE.holo);
  return vm(v, [26, 0, 9]);
}
function press() {                       // the Headroom press, 0.9 x 0.9 m: four columns, a top beam, a bed with a hazard edge (the ram moves: install())
  const v = new V.Vox(), S = PALETTE.steel;
  v.box(0, 0, 0, 17, 4, 17, PALETTE.steelD).box(1, 5, 1, 16, 5, 16, '#2a313c').box(0, 5, 0, 17, 5, 0, (x) => Math.floor(x / 2) % 2 ? PALETTE.ink : PALETTE.yellow);
  for (const [x, z] of [[0, 0], [16, 0], [0, 16], [16, 16]]) v.box(x, 6, z, x + 1, 33, z + 1, S);
  v.box(0, 30, 0, 17, 33, 17, PALETTE.steelD).box(7, 34, 7, 10, 36, 10, S);
  return vm(v, [9, 0, 9]);
}
function funnel() {                      // the RTK funnel, 0.9 x 0.9 m: a stand and a cone of steel open at the top (the ring turns: install())
  const v = new V.Vox();
  for (const [x, z] of [[1, 1], [16, 1], [1, 16], [16, 16]]) v.box(x, 0, z, x, 17, z, PALETTE.steelD);
  for (let y = 12; y <= 32; y++) {
    const R = y < 17 ? 1.6 : 1.6 + (y - 17) * 0.47;
    for (let x = -9; x <= 9; x++) for (let z = -9; z <= 9; z++) { const d = Math.hypot(x, z); if (d <= R + 0.5 && d > R - 0.9) v.set(9 + x, y, 9 + z, y === 32 ? PALETTE.steelL : y % 4 ? PALETTE.steel : '#6c7581'); }
  }
  return vm(v, [9.5, 0, 9.5]);
}
const BUILD = {portal: () => portal(false), mysteryPortal: () => portal(true), holoTable, press, funnel};
export const MODELS = {workDesk};
Object.assign(CATALOG, {                                             // new pieces of the catalog: office-layout.js resolve() gives them their boxes
  portal: {model: 'portal', foot: [1.0, 0.3]}, mysteryPortal: {model: 'mysteryPortal', foot: [1.0, 0.3]},
  holoTable: {model: 'holoTable', foot: [2.6, 0.9]}, press: {model: 'press', foot: [0.9, 0.9]}, funnel: {model: 'funnel', foot: [0.9, 0.9]},
});
/** a hangar piece for a placed item (office-layout.js resolve() item), or null: the office builds it as usual */
export function item(it, Vm) {
  V ??= Vm;
  return V && BUILD[it.type] ? BUILD[it.type]() : null;
}
// where the hangar puts its pieces in the default plan: two spans of the north wall become gates (the furniture there goes), the plaza's
// team table becomes the holographic table, its two tall plants the press and the funnel. A saved plan that already has gates keeps them.
const GATE_X = [5.15, 6.2, 7.25, 8.3, -8.2, -7.1, -6.0], MYSTERY_X = -4.85, GATE_Z = -9.62;
const CLEAR = [{x0: 4.4, x1: 9.0, z0: -10, z1: -8.9}, {x0: -8.8, x1: -4.3, z0: -10, z1: -8.9},
               {x0: 3.5, x1: 4.9, z0: 2.6, z1: 3.5, type: 'table'}, {x0: -5.2, x1: -4.4, z0: 4.0, z1: 4.8}, {x0: 8.1, x1: 8.9, z0: 4.0, z1: 4.8}];
export function withLab(items) {
  if (items.some(it => it.type === 'portal')) return items;
  const kept = items.filter(it => !CLEAR.some(c => it.x >= c.x0 && it.x <= c.x1 && it.z >= c.z0 && it.z <= c.z1 && (!c.type || it.type === c.type)));
  return [...kept, ...GATE_X.map(x => ({type: 'portal', x, z: GATE_Z})), {type: 'mysteryPortal', x: MYSTERY_X, z: GATE_Z},
          {type: 'holoTable', x: 4.2, z: 3.05}, {type: 'press', x: -4.8, z: 4.4}, {type: 'funnel', x: 8.5, z: 4.4}];
}

// ------------------------------------------------------------------ the rules (plain functions: tools/test_hangar.mjs runs them)
const TXT = (k, f = {}, lg) => (globalThis.I18N ? I18N.text('office.hangar.' + k, f, lg) : k);
/** a provider's colour: a hue from its id, so every viewer agrees; red when it has no quota left or is down */
export function gateColor(p) {
  if (!p) return PALETTE.violet;
  if (p.down || p.quota === 0) return PALETTE.red;
  let h = 2166136261; for (const c of String(p.id)) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
  const hue = (h % 360) / 360, s = 0.85, l = 0.55, q = l + s - l * s, pp = 2 * l - q;
  const ch = t => { t = (t + 1) % 1; const v = t < 1 / 6 ? pp + (q - pp) * 6 * t : t < 0.5 ? q : t < 2 / 3 ? pp + (q - pp) * (2 / 3 - t) * 6 : pp; return Math.round(v * 255).toString(16).padStart(2, '0'); };
  return '#' + ch(hue + 1 / 3) + ch(hue) + ch(hue - 1 / 3);
}
/** which provider stands at which gate: the ones the roles use first (most roles), then those with quota, then by name; at most `n` */
export function assignGates(providers, roles, n = GATE_X.length) {
  const use = new Map();
  for (const r of roles) use.set(r.provider, (use.get(r.provider) || 0) + 1);
  return [...providers].sort((a, b) => (use.get(b.id) || 0) - (use.get(a.id) || 0) || (b.quota > 0) - (a.quota > 0) || String(a.name || a.id).localeCompare(String(b.name || b.id))).slice(0, n);
}
/** what changed between two lists of roles: [{kind: 'in'|'move', name, from, to}] (from/to: provider ids) */
export function roleEvents(before, after) {
  const out = [], old = new Map(before.map(r => [r.name, r]));
  for (const r of after) {
    const o = old.get(r.name);
    if (!o) out.push({kind: 'in', name: r.name, to: r.provider});
    else if (o.host !== r.host || o.provider !== r.provider) out.push({kind: 'move', name: r.name, from: o.provider, to: r.provider});
  }
  return out;
}
/** the rows of the departures board: [role, model, host, state key] in fixed widths, upper case; `rows` at most, the last says how many more */
export const COLS = [9, 17, 12, 14];                                // NEMOTRON-3-ULTRA, OPEN_ROUTER and CHANGING GATE fit whole
const fit = (s, w) => String(s ?? '').toUpperCase().slice(0, w - 1).padEnd(w);            // one space between columns
export function boardRows(roles, rows, lg) {
  const all = roles.map(r => fit(r.name, COLS[0]) + fit(r.model, COLS[1]) + fit(r.host || r.provider, COLS[2]) + fit(TXT(r.state, {}, lg), COLS[3]));
  if (all.length <= rows) return all;
  return [...all.slice(0, rows - 1), fit('', COLS[0]) + fit(TXT('more', {n: all.length - rows + 1}, lg), COLS[1] + COLS[2] + COLS[3])];
}
/** the board asleep: between midnight and one, the first 8 seconds of every tenth minute */
export const asleep = d => d.getHours() === 0 && d.getMinutes() % 10 === 0 && d.getSeconds() < 8;
const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
/** one key into the Konami code: the new position (KONAMI.length = done) */
export const konamiStep = (pos, key) => key === KONAMI[pos] ? pos + 1 : key === KONAMI[0] ? 1 : 0;
export const CREDITS = 'ADRIAN CIPRIAN IANCU · ArtyomITA';
/** /spawn.json made safe to draw: lists of plain records, numbers bounded */
export function clean(d) {
  const s = (v, n = 40) => String(v ?? '').slice(0, n), num = v => Number.isFinite(+v) ? +v : 0;
  d = d && typeof d === 'object' ? d : {};
  return {
    providers: (Array.isArray(d.providers) ? d.providers : []).slice(0, 40).filter(p => p && p.id).map(p => ({id: s(p.id), name: s(p.name || p.id), quota: p.quota == null ? null : Math.max(0, Math.min(1, num(p.quota))), down: !!p.down})),
    roles: (Array.isArray(d.roles) ? d.roles : []).slice(0, 40).filter(r => r && r.name).map(r => ({name: s(r.name), provider: s(r.provider), model: s(String(r.model ?? '').split('/').pop(), 60), host: s(r.host), state: ['service', 'switch', 'notokens', 'stopped'].includes(r.state) ? r.state : 'service',
      trophy: r.trophy ? s(r.trophy) : null, aa: r.aa == null ? null : num(r.aa), strong: (Array.isArray(r.strong) ? r.strong : []).slice(0, 3).map(x => s(x, 24))})),
    saved: {headroom: num(d.saved?.headroom), rtk: num(d.saved?.rtk), caveman: num(d.saved?.caveman)},
    press: num(d.press), funnel: num(d.funnel), router: s(d.router, 60),
  };
}
/** made-up data that change by themselves (?hangar=demo): every gate, every state, the machines at work, a trophy */
export function demo(t, names) {
  const P = [['openrouter', 'OpenRouter'], ['nvidia', 'NVIDIA NIM'], ['groq', 'Groq'], ['gemini', 'Google AI Studio'], ['mistral', 'Mistral'], ['cerebras', 'Cerebras'], ['kilo', 'Kilo'], ['zen', 'OpenCode Zen']];
  const M = ['kimi-k3', 'nemotron-3-ultra', 'gpt-oss-120b', 'gemini-3-flash', 'devstral-2', 'qwen3.8-coder'], k = Math.floor(t / 15);
  const who = names.length ? names.slice(0, 8) : ['ALFA', 'BETA', 'GAMMA', 'DELTA'];
  return clean({
    providers: P.map(([id, name], i) => ({id, name, quota: i === 5 ? 0 : (Math.sin(t / 20 + i) + 1) / 2, down: i === 7})),
    roles: who.map((name, i) => ({name, provider: P[(i + k) % 5][0], host: P[(i + k) % 5][0], model: M[i % M.length], state: i === 1 ? 'notokens' : (k + i) % 4 === 0 ? 'switch' : 'service',
                                  trophy: i === 0 ? 'SWE-bench Verified' : null, aa: 38 + (i * 7) % 30, strong: [['SWE-bench', 'LiveCodeBench', 'GPQA'], ['AIME', 'MMLU-Pro'], ['IFEval']][i % 3]})),
    saved: {headroom: 12345 + k * 1700, rtk: 4567 + k * 900, caveman: 8901 + k * 300}, press: k % 2, funnel: (k + 1) % 2, router: M[k % M.length],
  });
}

// ------------------------------------------------------------------ the walls
function band(THREE, PLACED, map, y0, H, m, extra = {}) {             // a band of a picture along every outer wall, not across the doors (one mesh)
  const OUT = 0.13, pos = [], nor = [], uv = [], idx = [];
  for (const w of PLACED.walls) {
    const c = Math.cos(w.rot), s = Math.sin(w.rot), ax = w.a[0], az = w.a[1];
    let from = 0;
    for (const [u0, u1] of [...[...w.doors].sort((p, q) => p[0] - q[0]).map(([u, v]) => [u - 0.3, v + 0.3]), [w.len, w.len]]) {
      if (u0 - from > 0.2) {
        const n = pos.length / 3, at = (u, y) => [ax + c * u + s * OUT, y, az - s * u + c * OUT];
        for (const [u, y, v] of [[from, y0, 0], [u0, y0, 0], [u0, y0 + H, 1], [from, y0 + H, 1]]) { pos.push(...at(u, y)); nor.push(s, 0, c); uv.push(u / m, v); }
        idx.push(n, n + 1, n + 2, n, n + 2, n + 3);
      }
      from = u1;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(idx);
  return new THREE.Mesh(g, new THREE.MeshStandardMaterial({map, roughness: 0.6, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -4, ...extra}));
}

// ------------------------------------------------------------------ the live pieces
const H = {};                                                       // everything install() makes and update() moves
const canvas = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
/** office.js calls it once the plan is resolved: the wall bands, the runway, and the live parts of the gates, the board, the table and the machines */
export function install(ctx) {
  const {THREE, scene, PLACED} = ctx; V = ctx.V ?? V; CTX = ctx;
  const tex = c => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; };
  const basic = (o = {}) => new THREE.MeshBasicMaterial({toneMapped: false, ...o});
  const group = new THREE.Group(); group.name = 'hangar'; scene.add(group); H.group = group; H.THREE = THREE; H.clicks = [];
  const hz = band(THREE, PLACED, texture('hgHazardBand'), 0.04, KINDS.hgHazardBand.h / PX, 1);
  const rv = band(THREE, PLACED, texture('hgRivet'), 2.5, KINDS.hgRivet.h / PX, 1, {metalness: 0.35});
  group.add(hz, rv);
  // the runway: a strip of chase lights along the plaza (one plane, its picture slides)
  const rc = canvas(64, 4), rg = rc.getContext('2d'); rg.fillStyle = '#05080f'; rg.fillRect(0, 0, 64, 4);
  for (let x = 0; x < 64; x += 8) { rg.fillStyle = x === 0 ? '#ffffff' : x < 24 ? PALETTE.cyan : '#0d3a52'; rg.fillRect(x + 2, 1, 4, 2); }
  H.runTex = tex(rc); H.runTex.wrapS = THREE.RepeatWrapping; H.runTex.repeat.set(30, 1); H.runTex.magFilter = THREE.NearestFilter;
  const run = new THREE.Mesh(new THREE.PlaneGeometry(15, 0.12), basic({map: H.runTex}));
  run.rotation.x = -Math.PI / 2; run.position.set(1.5, 0.012, 1.6); run.userData.noShot = true; group.add(run);
  // the gates, from the plan
  const gates = PLACED.items.filter(it => it.type === 'portal').sort((a, b) => b.x - a.x), myst = PLACED.items.find(it => it.type === 'mysteryPortal');
  const all = [...gates, ...(myst ? [myst] : [])]; H.gates = all; H.myst = myst ? all.length - 1 : -1;
  const place = (m, it, lx, y, lz) => { const c = Math.cos(it.rot || 0), s = Math.sin(it.rot || 0); m.position.set(it.x + lx * c + lz * s, y, it.z - lx * s + lz * c); m.rotation.y = it.rot || 0; return m; };
  const neonV = new V.Vox().box(3, 1, 3, 3, 41, 3, '#ffffff').box(16, 1, 3, 16, 41, 3, '#ffffff').box(3, 41, 3, 16, 41, 3, '#ffffff');
  const n = Math.max(1, all.length), M4 = new THREE.Matrix4(), col = new THREE.Color();
  H.neon = new THREE.InstancedMesh(neonV.geometry({pivot: [10, 0, 3], scale: 0.05, ao: false, jitter: 0}), basic({vertexColors: true}), n);
  const gc = canvas(128, 128), gg = gc.getContext('2d'), grad = gg.createRadialGradient(64, 64, 4, 64, 64, 64);
  grad.addColorStop(0, '#ffffff'); grad.addColorStop(0.45, '#7f7f7f'); grad.addColorStop(1, '#000000'); gg.fillStyle = grad; gg.fillRect(0, 0, 128, 128);
  H.glow = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.62, 2.0), basic({map: tex(gc), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}), n);
  H.tank = new THREE.InstancedMesh(new THREE.BoxGeometry(0.04, 1, 0.02), basic(), n);
  all.forEach((it, i) => {
    const o = new THREE.Object3D(); place(o, it, 0, 0, 0); o.updateMatrix(); H.neon.setMatrixAt(i, o.matrix);
    place(o, it, 0, 1.05, -0.02); o.updateMatrix(); H.glow.setMatrixAt(i, o.matrix);
    H.neon.setColorAt(i, col.set(i === H.myst ? PALETTE.violet : '#333a44')); H.glow.setColorAt(i, col.set(i === H.myst ? PALETTE.violet : '#000000'));
    H.tank.setColorAt(i, col.set(PALETTE.cyan)); H.tank.setMatrixAt(i, M4.makeScale(0, 0, 0));
  });
  H.glow.userData.hangar = {kind: 'gate'}; H.level = new Float32Array(n);
  for (const m of [H.neon, H.glow, H.tank]) { m.frustumCulled = false; m.userData.noShot = true; group.add(m); }
  H.place = place;
  // one atlas for every label: a row of 512 x 64 per gate, then the press, the funnel (one mesh, one draw call)
  const rows = all.length + 2;
  H.atlas = canvas(512, 64 * rows); H.atlasTex = tex(H.atlas); H.labelKey = [];
  const pos = [], uv = [], idx = [], quad = (k, it, lx, y, lz, w) => {
    const c = Math.cos(it.rot || 0), s = Math.sin(it.rot || 0), h = w / 8, b = pos.length / 3, v0 = 1 - (k + 1) / rows, v1 = 1 - k / rows;
    for (const [dx, dy, u, v] of [[-w / 2, -h / 2, 0, v0], [w / 2, -h / 2, 1, v0], [w / 2, h / 2, 1, v1], [-w / 2, h / 2, 0, v1]]) {
      const x = lx + dx; pos.push(it.x + x * c + lz * s, y + dy, it.z - x * s + lz * c); uv.push(u, v);
    }
    idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
  };
  all.forEach((it, i) => quad(i, it, 0, 2.2, 0.16, 0.9));
  const pr = PLACED.items.find(it => it.type === 'press'), fu = PLACED.items.find(it => it.type === 'funnel');
  if (pr) quad(rows - 2, pr, 0, 1.98, 0.47, 1.0);
  if (fu) quad(rows - 1, fu, 0, 2.0, 0.0, 1.0);
  const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); lg.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); lg.setIndex(idx);
  H.labels = new THREE.Mesh(lg, basic({map: H.atlasTex, transparent: true, side: THREE.DoubleSide, depthWrite: false})); H.labels.userData.noShot = true; group.add(H.labels);
  H.rows = rows;
  // the press: the ram (with its rod) goes down on a block of tokens that squashes
  if (pr) {
    H.ram = place(V.mesh(new V.Vox().box(0, 0, 0, 13, 2, 13, PALETTE.steelL).box(6, 3, 6, 7, 22, 7, '#9aa6b5').box(0, 0, 0, 13, 0, 13, PALETTE.yellow), {pivot: [7, 0, 7], scale: 0.05, jitter: 0.02}), pr, 0, 1.3, 0); group.add(H.ram);
    H.block = place(new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), basic({color: PALETTE.cyan, transparent: true, opacity: 0.75})), pr, 0, 0.3, 0); H.block.geometry.translate(0, 0.25, 0); group.add(H.block);
    H.pressAt = pr;
  }
  // the funnel: a lit ring turning on its rim
  if (fu) {
    H.ring = place(new THREE.Mesh(new THREE.TorusGeometry(0.43, 0.025, 6, 32), basic({color: PALETTE.yellow})), fu, 0, 1.64, 0); H.ring.rotation.x = Math.PI / 2; group.add(H.ring);
    H.funnelAt = fu;
  }
  // the holographic table: a picture that floats over it and turns to whoever looks
  const ht = PLACED.items.find(it => it.type === 'holoTable');
  if (ht) {
    H.holoC = canvas(512, 320); H.holoTex = tex(H.holoC);
    H.holo = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.0), basic({map: H.holoTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide}));
    H.holo.position.set(ht.x, 1.55, ht.z); H.holo.userData.noShot = true; group.add(H.holo);
  }
  // the departures board, hanging over the plaza
  H.boardC = canvas(1024, 288); H.boardTex = tex(H.boardC);
  const board = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 0.9), basic({map: H.boardTex}));
  board.position.set(5.0, 2.3, 1.32); H.board = board; group.add(board);
  const body = V.mesh(new V.Vox().box(0, 0, 0, 65, 19, 1, '#12151c').box(4, 20, 0, 4, 33, 0, '#8a929e').box(61, 20, 0, 61, 33, 0, '#8a929e'), {pivot: [33, 10, 2], scale: 0.05, jitter: 0.02});
  body.position.set(5.0, 2.3, 1.3); group.add(body);
  // the cave painting, on the west wall between the lounge and the games corner (the north wall is the gates' and the CHECK panel's)
  const pc = canvas(256, 180), p = pc.getContext('2d'), r = rnd(7);
  p.fillStyle = '#6b5440'; p.fillRect(0, 0, 256, 180);
  for (let i = 0; i < 900; i++) { p.fillStyle = r() < 0.5 ? '#5c4836' : '#7a624b'; p.fillRect(r() * 256, r() * 180, 3, 2); }
  p.fillStyle = '#b3472f'; p.strokeStyle = '#b3472f'; p.lineWidth = 5; p.lineCap = 'round';
  const fig = (x, y, club) => { p.beginPath(); p.arc(x, y - 30, 8, 0, 7); p.fill(); p.beginPath(); p.moveTo(x, y - 22); p.lineTo(x, y); p.lineTo(x - 10, y + 22); p.moveTo(x, y); p.lineTo(x + 10, y + 22); p.moveTo(x - 14, y - 14); p.lineTo(x + 14, y - 14); if (club) { p.moveTo(x + 14, y - 14); p.lineTo(x + 24, y - 40); } p.stroke(); };
  fig(60, 110, true); fig(110, 115, false);
  p.fillStyle = '#e2c27a'; p.font = '900 34px serif'; p.fillText('∑ 🔥', 150, 80);
  for (const [x, y] of [[200, 140], [225, 120], [180, 160]]) { p.beginPath(); p.arc(x, y, 7, 0, 7); p.fill(); }
  p.fillStyle = '#2b2118'; p.font = '700 18px serif'; p.fillText('UGH. FEW WORD.', 20, 165);
  const paint = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 0.7), basic({map: tex(pc)}));
  paint.position.set(-14.86, 1.6, -4.88); paint.rotation.y = Math.PI / 2; paint.userData.hangar = {kind: 'cave'}; group.add(paint); H.cave = paint;
  // the pager over a role with no tokens, and its ring on the floor (made on demand, at most a few)
  const qc = canvas(128, 128), q = qc.getContext('2d');
  q.fillStyle = '#ff1744'; q.beginPath(); q.arc(64, 64, 60, 0, 7); q.fill(); q.font = '72px sans-serif'; q.textAlign = 'center'; q.textBaseline = 'middle'; q.fillText('📟', 64, 70);
  H.pagerMat = new THREE.SpriteMaterial({map: tex(qc), toneMapped: false, depthTest: false}); H.ringGeo = new THREE.RingGeometry(0.34, 0.44, 28); H.pagers = new Map();
  H.flaps = null; H.tex = tex; H.basic = basic;
  return {group};
}

// ------------------------------------------------------------------ data and life
let S = null, data = clean({}), gateOf = new Map(), busy = false, miss = 0, konami = 0;
const DEMO = typeof location !== 'undefined' && /[?&]hangar=demo\b/.test(location.search);
/** office.js calls it at the end, when the people exist: ctx {camera, raycastables, emit(n, at, opts), say(text), figure(name) -> Person,
 *  desk(name) -> Group, names() -> [names], lang() -> 'it'|'en', active() -> the office is on screen} */
export function start(ctx) {
  S = ctx;
  if (H.glow) S.raycastables.push(H.glow);
  if (H.cave) S.raycastables.push(H.cave);
  if (typeof document !== 'undefined') document.addEventListener('keydown', e => {
    if (e.target.closest?.('input, textarea, select, [contenteditable]')) return;
    konami = konamiStep(konami, e.key.length === 1 ? e.key.toLowerCase() : e.key);
    if (konami > 4 && /^Arrow(Left|Right)$/.test(e.key)) e.stopImmediatePropagation();     // after ↑↑↓↓ the ← → are the code's, not "the next agent" of office-ui.js
    if (konami === KONAMI.length) { konami = 0; H.creditsUntil = performance.now() / 1000 + 9; }
  }, true);
  setBoard(); drawLabels(); poll(); setInterval(poll, 3000);
  if (/[?&]force\b/.test(location.search)) window.__officeHangar = {H, data: () => data, shadow: () => { H.nextShadow = 0; }, llama: i => startLlama(i), click};   // tests: see and call the live pieces
  return {update, click, clickPerson};
}
async function poll() {
  if (busy || !S.active() || (miss > 0 && miss++ % 10)) return;     // a 404 (no spawn yet): ask every 30 s
  busy = true;
  try {
    if (DEMO) return setData(demo(performance.now() / 1000, S.names()));
    const r = await fetch('spawn.json', {cache: 'no-store'});
    if (r.ok) { miss = 0; setData(clean(await r.json())); } else miss = Math.max(miss, 1);
  } catch (e) { miss = Math.max(miss, 1); } finally { busy = false; }
}
function gatePos(i, y = 1.05, out = 0.3) { const it = H.gates[i]; return it && new H.THREE.Vector3(it.x + Math.sin(it.rot || 0) * out, y, it.z + Math.cos(it.rot || 0) * out); }
function setData(d) {
  const before = data.roles, first = !H.seen;
  data = d; H.seen = true;
  const shown = assignGates(d.providers, d.roles, H.myst >= 0 ? H.gates.length - 1 : H.gates.length);
  gateOf = new Map(shown.map((p, i) => [p.id, i]));
  H.shown = shown;
  // events: a role that comes in flashes at its gate, one that moves sends a streak to the new gate
  if (!first) for (const ev of roleEvents(before, d.roles)) {
    const to = gateOf.get(ev.to), at = to !== undefined && gatePos(to);
    if (at) S.emit(50, at, {color: [gateColor(d.providers.find(p => p.id === ev.to)), '#ffffff'], speed: 2.5, up: 2, life: 0.9, size: 0.07});
    const from = ev.kind === 'move' ? gateOf.get(ev.from) : undefined;
    if (from !== undefined && to !== undefined && from !== to) (H.streaks ||= []).push({a: gatePos(from, 1.6), b: gatePos(to, 1.6), t: 0, color: gateColor(d.providers.find(p => p.id === ev.to))});
  }
  drawLabels(); drawHolo(); setBoard(); trophies();
}
function drawLabels() {
  const lg = S.lang(), key = JSON.stringify([lg, H.shown?.map(p => [p.id, p.name, gateColor(p)]), Math.round(data.saved.headroom), Math.round(data.saved.rtk)]);
  if (key === H.labelKey) return;
  H.labelKey = key;
  const g = H.atlas.getContext('2d'), row = (k, text, color) => {
    g.clearRect(0, k * 64, 512, 64); g.fillStyle = '#0a0d14e6'; g.fillRect(0, k * 64 + 6, 512, 52);
    g.font = '800 34px "Segoe UI", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.shadowColor = color; g.shadowBlur = 12; g.fillStyle = color;
    g.fillText(text, 256, k * 64 + 33, 490); g.shadowBlur = 0;
  };
  H.gates.forEach((_, i) => { const p = H.shown?.[i]; row(i, i === H.myst ? 'openrouter/free' : p ? p.name : '—', i === H.myst ? PALETTE.violet : p ? gateColor(p) : '#4a5160'); });
  const k = n => n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(Math.round(n));
  row(H.rows - 2, TXT('press', {n: k(data.saved.headroom)}, lg), PALETTE.cyan); row(H.rows - 1, TXT('funnel', {n: k(data.saved.rtk)}, lg), PALETTE.yellow);
  H.atlasTex.needsUpdate = true;
  const col = new H.THREE.Color();
  H.gates.forEach((_, i) => { if (i === H.myst) return; const p = H.shown?.[i]; H.neon.setColorAt(i, col.set(p ? gateColor(p) : '#333a44')); H.glow.setColorAt(i, col.set(p ? gateColor(p) : '#000000').multiplyScalar(0.8)); });
  H.neon.instanceColor.needsUpdate = true; H.glow.instanceColor.needsUpdate = true;
}
function drawHolo() {
  if (!H.holo) return;
  const lg = S.lang(), models = [...new Map(data.roles.filter(r => r.model).map(r => [r.model, r])).values()], key = JSON.stringify([lg, models.map(r => [r.model, r.aa, r.strong])]);
  if (key === H.holoKey) return;
  H.holoKey = key;
  const g = H.holoC.getContext('2d'), W = 512, Hh = 320, c = PALETTE.holo;
  g.clearRect(0, 0, W, Hh);
  g.strokeStyle = c; g.lineWidth = 2; g.strokeRect(4, 4, W - 8, Hh - 8);
  g.fillStyle = c; g.font = '800 26px "Segoe UI", sans-serif'; g.textBaseline = 'middle'; g.fillText(TXT('aa', {}, lg), 18, 28);
  const list = models.filter(r => r.aa != null).sort((a, b) => b.aa - a.aa).slice(0, 6), top = Math.max(1, ...list.map(r => r.aa));
  list.forEach((r, i) => {
    const y = 64 + i * 30, w = (W - 220) * r.aa / top;
    g.globalAlpha = 0.35; g.fillRect(170, y - 10, W - 220, 20); g.globalAlpha = 1; g.fillRect(170, y - 10, w, 20);
    g.font = '600 17px "Segoe UI", sans-serif'; g.fillText(r.model.slice(0, 16), 16, y); g.fillText(String(Math.round(r.aa)), 176 + w, y);
  });
  const best = list[0];
  if (best?.strong.length) { g.font = '700 18px "Segoe UI", sans-serif'; g.fillText(`${TXT('strong', {}, lg)}: ${best.strong.join(' · ')}`, 16, Hh - 30, W - 32); }
  if (!list.length) { g.font = '600 20px "Segoe UI", sans-serif'; g.fillText('—', 16, 70); }
  g.globalAlpha = 0.18; g.fillStyle = '#000000'; for (let y = 0; y < Hh; y += 4) g.fillRect(0, y, W, 2); g.globalAlpha = 1;
  H.holoTex.needsUpdate = true;
}
// the split-flap board: one cell per character; a cell that changes turns through random letters for a moment, then shows its letter
const FLAP = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-·', ROWS = 6, WIDTH = COLS.reduce((a, b) => a + b, 0);
function want() {
  const lg = S.lang(), now = performance.now() / 1000, pad = s => ' '.repeat(Math.max(0, Math.floor((WIDTH - s.length) / 2))) + s;
  if (now < (H.creditsUntil || 0)) return ['', '', pad(CREDITS), '', '', ''];
  if (asleep(new Date())) return ['', '', pad(TXT('sleep', {}, lg)), '', '', ''];
  const rows = boardRows(data.roles, ROWS, lg);
  return rows.length ? rows : [pad(TXT('empty', {}, lg))];
}
function setBoard() {
  const now = performance.now() / 1000, rows = want();
  H.flaps ||= Array.from({length: ROWS * WIDTH}, () => ({cur: ' ', to: ' ', until: 0}));
  for (let r = 0; r < ROWS; r++) for (let i = 0; i < WIDTH; i++) {
    const f = H.flaps[r * WIDTH + i], ch = (rows[r] || '').padEnd(WIDTH)[i];
    if (ch !== f.to) { f.to = ch; f.until = now + 0.15 + i * 0.012 + Math.random() * 0.25; }
  }
  H.boardDirty = true;
}
function drawBoard(now) {
  const g = H.boardC.getContext('2d'), lg = S.lang(), cw = (1024 - 24) / WIDTH, rh = 38;
  g.fillStyle = '#0b0d12'; g.fillRect(0, 0, 1024, 288);
  g.fillStyle = PALETTE.yellow; g.font = '900 30px "Segoe UI", sans-serif'; g.textBaseline = 'middle'; g.textAlign = 'left';
  g.fillText(now < (H.creditsUntil || 0) ? '★ CREDITS' : '✈ ' + TXT('title', {}, lg), 14, 22);
  let x0 = 12; g.font = '700 15px "Segoe UI", sans-serif'; g.fillStyle = '#8a93a3';
  for (const [k, w] of [['role', COLS[0]], ['model', COLS[1]], ['host', COLS[2]], ['state', COLS[3]]]) { g.fillText(TXT(k, {}, lg), x0 + 2, 52); x0 += w * cw; }
  let moving = false, blink = false;
  g.font = '700 26px Consolas, "Courier New", monospace'; g.textAlign = 'center';
  for (let r = 0; r < ROWS; r++) {
    const real = r < ROWS - (data.roles.length > ROWS ? 1 : 0) && !(now < (H.creditsUntil || 0)) && !asleep(new Date()), st = real ? data.roles[r]?.state : '';
    const y = 66 + r * rh, out = st === 'notokens', stopped = st === 'stopped';
    for (let i = 0; i < WIDTH; i++) {
      const f = H.flaps[r * WIDTH + i], x = 12 + i * cw;
      if (now < f.until) { f.cur = FLAP[Math.floor(Math.random() * FLAP.length)]; moving = true; } else f.cur = f.to;
      g.fillStyle = '#1a1e27'; g.fillRect(x + 1, y, cw - 2, rh - 6); g.fillStyle = '#0b0d12'; g.fillRect(x + 1, y + (rh - 6) / 2, cw - 2, 1);
      const stateCol = i >= WIDTH - COLS[3] && (out || stopped);
      if (stateCol && out) blink = true;
      g.fillStyle = stateCol ? (stopped || Math.floor(now * 2) % 2 ? PALETTE.red : '#5a1a22') : f.cur === f.to ? '#f2f2ea' : '#c9cbd4';   // no tokens blinks, stopped (401/402/403) stays red
      g.fillText(f.cur, x + cw / 2, y + (rh - 6) / 2 + 1);
    }
  }
  H.boardTex.needsUpdate = true;
  return moving || blink;
}
const _M = {};
function update(dt, t) {
  if (!S || !H.group) return;
  const T = H.THREE, now = performance.now() / 1000;
  // the board: flaps while they turn, the blink of "no tokens", credits and sleep when their time comes
  const wantKey = (now < (H.creditsUntil || 0)) + '|' + asleep(new Date());
  if (wantKey !== H.wantKey) { H.wantKey = wantKey; setBoard(); }
  if (H.flaps && (H.boardDirty || (H.boardMoving && now - (H.boardAt || 0) > 1 / 15))) { H.boardDirty = false; H.boardAt = now; H.boardMoving = drawBoard(now); }
  // the gates: the tank goes to its quota, a red gate flickers, the glow breathes
  const m = _M.m ||= new T.Matrix4(), o = _M.o ||= new T.Object3D(), c = _M.c ||= new T.Color();
  let glowChanged = false;
  H.gates.forEach((it, i) => {
    if (i === H.myst) { c.setHSL((t * 0.1) % 1, 0.8, 0.6); H.neon.setColorAt(i, c); H.glow.setColorAt(i, c.multiplyScalar(0.6 + 0.3 * Math.sin(t * 3))); glowChanged = true; return; }
    const p = H.shown?.[i], q = p?.quota ?? 0;
    H.level[i] += (q - H.level[i]) * Math.min(1, dt * 2);
    const h = 1.35 * H.level[i];
    H.place(o, it, 0.425, 0.4 + h / 2, 0.2); o.scale.set(1, Math.max(0.001, h), 1); o.updateMatrix(); H.tank.setMatrixAt(i, o.matrix);
    if (p && gateColor(p) === PALETTE.red) { H.neon.setColorAt(i, c.set(PALETTE.red).multiplyScalar(Math.sin(t * 23 + i) > -0.6 ? 1 : 0.2)); glowChanged = true; }
    else if (p) { H.glow.setColorAt(i, c.set(gateColor(p)).multiplyScalar(0.55 + 0.25 * Math.sin(t * 1.7 + i))); glowChanged = true; }
  });
  H.tank.instanceMatrix.needsUpdate = true;
  if (glowChanged) { H.neon.instanceColor.needsUpdate = true; H.glow.instanceColor.needsUpdate = true; }
  // streaks between gates
  if (H.streaks?.length) {
    H.streakMesh ||= Object.assign(new T.Mesh(new T.SphereGeometry(0.09, 10, 8), H.basic({color: '#ffffff'})), {frustumCulled: false});
    if (!H.streakMesh.parent) H.group.add(H.streakMesh);
    const s = H.streaks[0]; s.t += dt / 1.2;
    H.streakMesh.position.lerpVectors(s.a, s.b, Math.min(1, s.t)); H.streakMesh.position.y += Math.sin(Math.PI * Math.min(1, s.t)) * 1.2; H.streakMesh.material.color.set(s.color);
    if (Math.random() < dt * 30) S.emit(2, H.streakMesh.position, {color: s.color, speed: 0.3, up: 0.2, life: 0.4, size: 0.05, gravity: 0});
    if (s.t >= 1) { S.emit(40, s.b, {color: [s.color, '#ffffff'], speed: 2, up: 2, life: 0.8, size: 0.07}); H.streaks.shift(); if (!H.streaks.length) H.group.remove(H.streakMesh); }
  }
  // the machines: the press goes down on its block while Headroom compresses, the funnel's ring turns and drops tokens while RTK does
  if (H.ram) {
    const on = data.press > 0, k = on ? 0.5 + 0.5 * Math.cos(t * 2.4) : 1, y = 0.85 + 0.45 * k;
    H.ram.position.y = y; H.block.scale.y = Math.max(0.15, Math.min(1, (y - 0.32) / 0.55));
  }
  if (H.ring) {
    const on = data.funnel > 0; H.ring.rotation.z += dt * (on ? 4 : 0.3);
    if (on && Math.random() < dt * 6) S.emit(1, new T.Vector3(H.funnelAt.x + (Math.random() - 0.5) * 0.5, 1.9, H.funnelAt.z + (Math.random() - 0.5) * 0.5), {color: [PALETTE.yellow, PALETTE.cyan], speed: 0.05, up: -0.2, life: 0.9, size: 0.06, gravity: -2});
  }
  H.runTex.offset.x = (H.runTex.offset.x - dt * 0.6) % 1;
  // the hologram turns to the camera and floats
  if (H.holo) { const cp = S.camera.position; H.holo.rotation.y = Math.atan2(cp.x - H.holo.position.x, cp.z - H.holo.position.z); H.holo.position.y = 1.55 + Math.sin(t * 1.3) * 0.03; }
  // roles with no tokens: the figure stops, a pager pulses over its head, a red ring on the floor
  const out = new Set(data.roles.filter(r => r.state === 'notokens').map(r => r.name));
  for (const [name, pg] of H.pagers) if (!out.has(name) || !S.figure(name)) { H.group.remove(pg.sprite, pg.ring); H.pagers.delete(name); }
  for (const name of out) {
    const fig = S.figure(name); if (!fig) continue;
    let pg = H.pagers.get(name);
    if (!pg) {
      const sprite = new T.Sprite(H.pagerMat); sprite.userData.hangar = {kind: 'pager', name}; sprite.renderOrder = 5;
      const ring = new T.Mesh(H.ringGeo, H.basic({color: PALETTE.red, transparent: true, side: T.DoubleSide, depthWrite: false})); ring.rotation.x = -Math.PI / 2;
      H.group.add(sprite, ring); pg = {sprite, ring}; H.pagers.set(name, pg); S.raycastables.push(sprite);
    }
    fig.act = 'idle';
    const pulse = Math.max(0, Math.sin(t * 6)) ** 2, head = fig.head();
    pg.sprite.position.set(head.x, head.y + 0.55, head.z); pg.sprite.scale.setScalar(0.32 + 0.1 * pulse); pg.sprite.material.opacity = 0.55 + 0.45 * pulse;
    pg.ring.position.set(fig.pos.x, fig.pos.y + 0.02, fig.pos.z); pg.ring.material.opacity = 0.25 + 0.6 * pulse;
  }
  mystery(dt, t); llama(dt, t);
}
function trophies() {                    // a gold cup on the desk of a role whose model is first in a benchmark, with the benchmark's name
  H.cups ||= new Map();
  for (const r of data.roles) {
    const was = H.cups.get(r.name), desk = S.desk(r.name);
    if (was && (was.trophy !== r.trophy || was.desk !== desk)) { was.desk?.remove(was.g); H.cups.delete(r.name); }
    if (!r.trophy || !desk || H.cups.has(r.name)) continue;
    const T = H.THREE, g = new T.Group(), v = new V.Vox(), G = PALETTE.gold;
    v.box(2, 0, 2, 7, 0, 7, '#5d4037').box(4, 1, 4, 5, 3, 5, G).box(2, 4, 2, 7, 8, 7, G).box(3, 5, 3, 6, 8, 6, null).box(0, 6, 4, 1, 7, 5, G).box(8, 6, 4, 9, 7, 5, G);
    for (let x = 3; x <= 6; x++) for (let z = 3; z <= 6; z++) v.del(x, 8, z);
    g.add(V.mesh(v, {pivot: [5, 0, 5], scale: 0.025, jitter: 0.02}));
    const lc = canvas(256, 48), lg = lc.getContext('2d'); lg.fillStyle = '#000000b0'; lg.fillRect(0, 0, 256, 48); lg.fillStyle = G; lg.font = '800 24px "Segoe UI", sans-serif'; lg.textAlign = 'center'; lg.textBaseline = 'middle'; lg.fillText('🏆 ' + r.trophy, 128, 25, 250);
    const label = new T.Sprite(new T.SpriteMaterial({map: H.tex(lc), toneMapped: false})); label.scale.set(0.5, 0.094, 1); label.position.set(0, 0.36, 0); g.add(label);
    g.position.set(-0.32, 0.71, 0.12); desk.add(g);
    H.cups.set(r.name, {g, trophy: r.trophy, desk});
  }
  for (const [name, cup] of H.cups) if (!data.roles.some(r => r.name === name)) { cup.desk?.remove(cup.g); H.cups.delete(name); }
}
// the mysterious gate: now and then a shadow with a question mark steps out, the name of the model the router chose over its head
function mystery(dt, t) {
  if (H.myst < 0) return;
  const T = H.THREE, now = performance.now() / 1000;
  H.nextShadow ??= now + 20;
  if (!H.shadow && now > H.nextShadow && S.active()) {
    const it = H.gates[H.myst], dark = '#120c1c';
    const f = V.person({name: 'openrouter/free', shirt: dark, look: {skin: dark, hair: dark, top: dark, pants: dark, style: 'bald', outfit: 'polo', glasses: false, headphones: false}});
    const lc = canvas(256, 96), lg = lc.getContext('2d'); lg.textAlign = 'center'; lg.textBaseline = 'middle'; lg.fillStyle = PALETTE.violet;
    lg.font = '900 54px "Segoe UI", sans-serif'; lg.fillText('?', 128, 30); lg.font = '700 22px "Segoe UI", sans-serif'; lg.fillText(data.router || '???', 128, 76, 250);
    const tag = new T.Sprite(new T.SpriteMaterial({map: H.tex(lc), toneMapped: false, transparent: true})); tag.scale.set(0.8, 0.3, 1); tag.position.y = 2.25; f.root.add(tag);
    f.root.position.set(it.x, 0, it.z + 0.2); H.group.add(f.root);
    H.shadow = {f, tag, t: 0, x: it.x, z: it.z + 0.2};
    S.emit(40, new T.Vector3(it.x, 1.1, it.z + 0.3), {color: [PALETTE.violet, '#ffffff'], speed: 2, up: 1.5, life: 0.8, size: 0.06});
  }
  const s = H.shadow;
  if (!s) return;
  s.t += dt;
  const walk = Math.min(1, s.t / 3), P_ = s.f.parts;
  s.f.root.position.z = s.z + 2.2 * walk;
  const w = s.t < 3 ? Math.sin(s.t * 10) : 0; P_.legL.rotation.x = w * 0.6; P_.legR.rotation.x = -w * 0.6; P_.armL.rotation.x = -w * 0.5; P_.armR.rotation.x = w * 0.5;
  if (s.t > 5) s.f.body.scale.setScalar(Math.max(0.01, 1 - (s.t - 5)));
  if (s.t > 6) { H.group.remove(s.f.root); s.tag.material.map.dispose(); s.tag.material.dispose(); s.f.release(); H.shadow = null; H.nextShadow = performance.now() / 1000 + 45 + Math.random() * 45; }
}
// seven clicks on a gate: a llama walks out and across the hangar (for llama.cpp)
function llama(dt) {
  const L = H.llamaRun; if (!L) return;
  L.t += dt;
  let d = L.t * 1.2, i = 0;
  while (i < L.path.length - 1 && d > L.len[i]) { d -= L.len[i]; i++; }
  if (i >= L.path.length - 1) { H.group.remove(L.m); H.llamaRun = null; return; }
  const a = L.path[i], b = L.path[i + 1], k = d / L.len[i];
  L.m.position.set(a.x + (b.x - a.x) * k, Math.abs(Math.sin(L.t * 8)) * 0.04, a.z + (b.z - a.z) * k); L.m.rotation.y = Math.atan2(b.x - a.x, b.z - a.z);
}
function startLlama(i) {
  if (H.llamaRun) return;
  const it = H.gates[i], T = H.THREE, v = new V.Vox(), W = '#f3ead8', B = '#d9c7a6';
  v.box(0, 10, 0, 5, 15, 13, W).box(1, 0, 1, 1, 9, 1, B).box(4, 0, 1, 4, 9, 1, B).box(1, 0, 12, 1, 9, 12, B).box(4, 0, 12, 4, 9, 12, B);
  v.box(1, 16, 11, 4, 26, 14, W).box(1, 23, 15, 4, 26, 18, W).box(2, 23, 19, 3, 24, 19, '#3b2a20').set(1, 25, 15, '#1b1b2a').set(4, 25, 15, '#1b1b2a');
  v.box(1, 27, 12, 1, 29, 12, W).box(4, 27, 12, 4, 29, 12, W).box(0, 12, 6, 5, 13, 8, '#c0392b').box(2, 14, -1, 3, 15, 0, W);
  const m = V.mesh(v, {pivot: [2.5, 0, 7], scale: 0.05, jitter: 0.05}); H.group.add(m);
  const a = {x: it.x, z: it.z + 0.4}, mid = {x: it.x, z: 1.85}, end = {x: it.x > 0 ? -6 : 9, z: 1.85}, way = (f, t) => S.route?.(f, t)?.map(v => ({x: v.x, z: v.z})) || [t];
  const p = [a, ...way(a, mid), ...way(mid, end)].filter((q, k, l) => !k || Math.hypot(q.x - l[k - 1].x, q.z - l[k - 1].z) > 0.01);   // round the desks, the office's own A*
  const len = p.slice(1).map((q, k) => Math.hypot(q.x - p[k].x, q.z - p[k].z));
  H.llamaRun = {m, t: 0, path: p, len};
  S.emit(40, new T.Vector3(it.x, 1.1, it.z + 0.3), {color: ['#ffffff', PALETTE.gold], speed: 2, up: 2, life: 0.9, size: 0.07});
}
/** a click on a piece of the hangar (userData.hangar): seven on a gate in 5 s bring the llama, the painting tells caveman's savings, the pager asks for a replacement */
function click(ud, hit) {
  const now = performance.now() / 1000, lg = S.lang();
  if (ud.kind === 'gate') {
    const i = hit?.instanceId ?? 0;
    H.clicks = H.clicks.filter(c => c.i === i && now - c.t < 5); H.clicks.push({i, t: now});
    if (H.clicks.length >= 7) { H.clicks = []; startLlama(i); }
    else if (i === H.myst) S.say('openrouter/free · ' + (data.router || '???'));
    else { const p = H.shown?.[i]; if (p) S.say(`${p.name}${p.quota != null ? ' · ' + Math.round(p.quota * 100) + '%' : ''}`); }
    return;
  }
  if (ud.kind === 'cave') return S.say(data.saved.caveman > 0 ? TXT('cave', {n: Math.round(data.saved.caveman).toLocaleString(lg)}, lg) : TXT('caveNone', {}, lg));
  if (ud.kind === 'pager') clickPerson(ud.name);
}
/** a click on a figure: a role with no tokens asks for its replacement (the viewer opens the card Sostituisci); false lets the office select it as usual */
function clickPerson(name) {
  const r = data.roles.find(x => x.name === name && x.state === 'notokens');
  if (!r) return false;
  window.dispatchEvent(new CustomEvent('chatroom:replace', {detail: {name: r.name, model: r.model, provider: r.provider}}));
  S.say(TXT('replace', {name: r.name}, S.lang()));
  return false;
}
