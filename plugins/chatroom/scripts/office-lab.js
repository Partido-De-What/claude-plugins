// The laboratory: the look of a research room (config.mode === 'research'). Same plan, same places, same functions as the office
// (arcade, TV, radio, rack, arena...): only the pictures change. A clean lab: white walls, steel, grey resin floors, cold light,
// cyan and amber for what is on and what needs care. office.js loads this file only for research rooms (import() on demand), so the
// normal office pays nothing for it. Pixel art drawn in a canvas like office-floor.js (same density, same filters), no images.
//
// What office.js uses: THEME (colours), FLOOR (for buildFloor), sky() (the light), install() (the wall bands), labTexture() (the
// same pictures for other modules: the research walls of office-research.js), PALETTE (the colours of the states, for every module);
// for the furniture MODELS (the lab's builder for a model name of office-voxel.js, same size as the office's), item() (a lab piece
// for a placed item, or null), withLab() (the items the lab adds to the plan) and SIGNS (the look of the signs).
import {PX, rnd, shade, dot, speckle, makeTexture} from './office-floor.js';
import {CATALOG} from './office-layout.js';
import {CLEAR} from './office-research.js';             // the wall spans the research panels use (office-research.js): the furniture stays out of them

/** the colours of the lab, and the states: the same everywhere in the plugin (3D and 2D) */
export const PALETTE = {
  white: '#eef3f6', steel: '#aeb8c2', resin: '#8c969f', ink: '#0e1a22',
  cyan: '#4dd0e1', amber: '#ffb74d',
  keep: '#43a047', discard: '#90a4ae', crash: '#e53935', run: '#4dd0e1', warn: '#ffb74d',
};

/** colours that office.js reads: the walls and ceiling, the cold light (hemisphere, sun by the hour, lamps) */
export const THEME = {
  wall: '#eef3f6', ceiling: '#f3f7f9',
  wallPal: {skirt: '#3b4a55', base: '#c9d3da', door: '#7e8c97', win: '#dfeaf0', blind: '#c4d6df', sill: '#e8eff3'},   // blindWall(): the parts that are not the wall colour
  hemi: ['#e6f3ff', '#46515c'], sun: {night: '#e4eeff', dusk: '#dbe8ff', day: '#eaf4ff'}, lamp: '#bfe9ff',
};

// ------------------------------------------------------------------ the pictures
/** the hexagon a pixel falls in, on a lattice that repeats every w x h pixels (6 columns x 5 rows, odd columns half a row down, the rows
 *  stretched to regular hexagons): {id 0..29, d: pixels to its centre, edge: pixels to the joint with the nearest neighbour, lit: upper left of its centre} */
export function hexAt(x, y, w, h) {
  const cw = w / 6, ch = h / 5, k = 1.1547 * cw / ch, i0 = Math.floor(x / cw), j0 = Math.floor(y / ch);
  let a = null, b = null;                                           // the nearest two centres
  for (let i = i0 - 1; i <= i0 + 1; i++) for (let j = j0 - 1; j <= j0 + 1; j++) {
    const cx = (i + 0.5) * cw, cy = (j + 0.5 + (i & 1) * 0.5) * ch, d = Math.hypot(x - cx, (y - cy) * k), c = {i, j, cx, cy, d};
    if (!a || d < a.d) { b = a; a = c; } else if (!b || d < b.d) b = c;
  }
  const gap = Math.hypot(a.cx - b.cx, (a.cy - b.cy) * k);
  return {id: ((a.i % 6) + 6) % 6 + 6 * (((a.j % 5) + 5) % 5), d: a.d, edge: (b.d * b.d - a.d * a.d) / (2 * gap), lit: (x - a.cx) + (y - a.cy) * k < 0};
}
const hexTiles = (base, seed) => (g, w, h) => {                    // antistatic floor: hexagons with a conductive stud in the middle
  const r = rnd(seed), tones = Array.from({length: 30}, () => shade(base, 0.92 + r() * 0.16));
  const joint = shade(base, 0.5), hi = shade(base, 1.3), lo = shade(base, 0.82), stud = shade(base, 1.45);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const c = hexAt(x + 0.5, y + 0.5, w, h);
    dot(g, x, y, c.d < 1 ? stud : c.edge < 0.6 ? joint : c.edge < 1.6 ? (c.lit ? hi : lo) : tones[c.id]);
  }
};
const resin = (base, seed) => (g, w, h) => {                       // epoxy resin tiles, 50 cm: a lit edge on top and left, a dark joint, chips
  const r = rnd(seed), n = 4, s = w / n;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    g.fillStyle = shade(base, 0.97 + r() * 0.06); g.fillRect(i * s, j * s, s, s);
    for (let k = 0; k < s * s / 12; k++) dot(g, i * s + Math.floor(r() * s), j * s + Math.floor(r() * s), shade(base, r() < 0.5 ? 0.93 : 1.08));
    g.fillStyle = shade(base, 1.14); g.fillRect(i * s + 1, j * s + 1, s - 1, 1); g.fillRect(i * s + 1, j * s + 1, 1, s - 1);
  }
  g.fillStyle = shade(base, 0.74);
  for (let i = 0; i < n; i++) { g.fillRect(i * s, 0, 1, h); g.fillRect(0, i * s, w, 1); }
};
function clean(g, w, h) {                                           // clean-room raised floor: white panels 50 cm, perforated
  const r = rnd(111), n = 4, s = w / n, base = '#e6edf1';
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    g.fillStyle = shade(base, 0.97 + r() * 0.05); g.fillRect(i * s, j * s, s, s);
    for (let x = 3; x < s - 1; x += 3) for (let y = 3; y < s - 1; y += 3) dot(g, i * s + x, j * s + y, '#a9b9c3');
    g.fillStyle = '#ffffff'; g.fillRect(i * s + 1, j * s + 1, s - 1, 1); g.fillRect(i * s + 1, j * s + 1, 1, s - 1);
  }
  g.fillStyle = '#b3c0c9';
  for (let i = 0; i < n; i++) { g.fillRect(i * s, 0, 1, h); g.fillRect(0, i * s, w, 1); }
}
function steel(g, w, h) {                                           // brushed steel plates, 1 m, a rivet in each corner
  const r = rnd(61), base = '#a7b1bb', s = w / 2;
  for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) {
    g.fillStyle = shade(base, 0.95 + r() * 0.1); g.fillRect(i * s, j * s, s, s);
    for (let y = 0; y < s; y++) for (let k = 0; k < 3; k++) {       // brushing: short runs along x
      const x = Math.floor(r() * s), len = 6 + Math.floor(r() * 14), t = shade(base, r() < 0.5 ? 0.93 : 1.08);
      for (let q = 0; q < len; q++) dot(g, i * s + (x + q) % s, j * s + y, t);
    }
    g.fillStyle = '#6c7680'; g.fillRect(i * s, j * s, s, 1); g.fillRect(i * s, j * s, 1, s);
    g.fillStyle = '#d4dbe1'; g.fillRect(i * s + 1, j * s + 1, s - 1, 1); g.fillRect(i * s + 1, j * s + 1, 1, s - 1);
    for (const [x, y] of [[3, 3], [s - 4, 3], [3, s - 4], [s - 4, s - 4]]) { dot(g, i * s + x, j * s + y, '#e8edf1'); dot(g, i * s + x + 1, j * s + y + 1, '#5d6670'); }
  }
}
function esd(g, w, h) {                                             // ESD fabric of the benches: a fine weave, studs every 4 pixels
  g.fillStyle = '#34444c'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#3d4e57'; for (let y = 0; y < h; y += 2) for (let x = (y / 2) % 2 * 2; x < w; x += 4) g.fillRect(x, y, 2, 1);
  for (let x = 1; x < w; x += 4) for (let y = 1; y < h; y += 4) dot(g, x, y, '#566a75');
}
function circuit(g, w, h) {                                         // printed circuit board: traces with pads, chips with pins, vias
  const r = rnd(83), cells = w / 8;
  g.fillStyle = '#0b2a31'; g.fillRect(0, 0, w, h); speckle(g, w, h, r, w * h / 10, '#0b2a31', 0.25);
  for (let k = 0; k < cells * 2; k++) {                             // buses along x and along y, one lane each: a segment and a pad at each end
    const along = k % 2 === 0, line = (k >> 1) * 8 + (r() < 0.5 ? 2 : 5), start = 2 + Math.floor(r() * (w - 32)), len = 10 + Math.floor(r() * 18);
    g.fillStyle = '#1b8a98'; if (along) g.fillRect(start, line, len, 1); else g.fillRect(line, start, 1, len);
    g.fillStyle = PALETTE.cyan;
    for (const e of [start, start + len]) if (along) g.fillRect(e - 1, line - 1, 3, 3); else g.fillRect(line - 1, e - 1, 3, 3);
  }
  for (let k = 0; k < 3; k++) {                                     // chips
    const x = 4 + Math.floor(r() * (w - 22)), y = 4 + Math.floor(r() * (h - 18));
    g.fillStyle = '#06181c'; g.fillRect(x, y, 14, 10);
    g.fillStyle = '#7aa7b0'; for (let p = 1; p < 14; p += 3) { g.fillRect(x + p, y - 1, 1, 1); g.fillRect(x + p, y + 10, 1, 1); }
    dot(g, x + 2, y + 2, PALETTE.amber);
  }
  for (let k = 0; k < 14; k++) dot(g, Math.floor(r() * w), Math.floor(r() * h), r() < 0.2 ? PALETTE.amber : PALETTE.cyan);
}
function trace(g, w, h) {                                           // a strip of circuit, 0.34 m tall: the technical band along the walls
  const r = rnd(91);
  g.fillStyle = '#0b2a31'; g.fillRect(0, 0, w, h); speckle(g, w, h, r, w * h / 10, '#0b2a31', 0.25);
  for (const y of [2, h - 3]) for (let x = 1; ;) {
    const len = 6 + Math.floor(r() * 14); if (x + len + 3 > w) break;
    if (r() < 0.8) { g.fillStyle = '#1b8a98'; g.fillRect(x, y, len, 1); g.fillStyle = PALETTE.cyan; g.fillRect(x + len - 1, y - 1, 3, 3); }
    x += len + 3 + Math.floor(r() * 4);
  }
  for (let k = 0; k < 5; k++) { const x = 2 + Math.floor(r() * (w - 4)); g.fillStyle = '#1b8a98'; g.fillRect(x, 2, 1, h - 4); dot(g, x, Math.floor(h / 2), PALETTE.amber); }
  for (let k = 0; k < 2; k++) {
    const x = 6 + Math.floor(r() * (w - 20)); g.fillStyle = '#06181c'; g.fillRect(x, 3, 10, h - 6);
    g.fillStyle = '#7aa7b0'; for (let p = 1; p < 10; p += 3) { g.fillRect(x + p, 2, 1, 1); g.fillRect(x + p, h - 3, 1, 1); }
  }
}
function blueprint(g, w, h) {                                       // blueprint paper: a fine grid every 25 cm, a stronger one every metre, a dimension line
  g.fillStyle = '#123f66'; g.fillRect(0, 0, w, h);
  for (let k = 0; k < w; k += 8) { g.fillStyle = k % 32 ? '#1a5584' : '#3b8cc2'; g.fillRect(k, 0, 1, h); g.fillRect(0, k, w, 1); }
  g.fillStyle = '#cfe9f7'; g.fillRect(10, 20, 24, 1); g.fillRect(10, 17, 1, 7); g.fillRect(33, 17, 1, 7);
  g.fillRect(40, 42, 1, 14); g.fillRect(37, 42, 7, 1); g.fillRect(37, 55, 7, 1);
}
function pad(g, w, h) {                                             // the lounge rug of the lab: a lit floor pad, cyan border and amber corners
  const b = Math.max(2, Math.round(Math.min(w, h) * 0.05));
  g.fillStyle = '#10283c'; g.fillRect(0, 0, w, h);
  for (let x = 0; x < w; x += 8) { g.fillStyle = '#17405e'; g.fillRect(x, 0, 1, h); }
  for (let y = 0; y < h; y += 8) { g.fillStyle = '#17405e'; g.fillRect(0, y, w, 1); }
  g.fillStyle = '#2a8ea0'; g.fillRect(0, 0, w, b); g.fillRect(0, h - b, w, b); g.fillRect(0, 0, b, h); g.fillRect(w - b, 0, b, h);
  g.fillStyle = PALETTE.cyan; g.fillRect(b + 1, b + 1, w - 2 * b - 2, 1); g.fillRect(b + 1, h - b - 2, w - 2 * b - 2, 1); g.fillRect(b + 1, b + 1, 1, h - 2 * b - 2); g.fillRect(w - b - 2, b + 1, 1, h - 2 * b - 2);
  g.fillStyle = PALETTE.amber;
  for (const [x, y, dx, dy] of [[b + 1, b + 1, 1, 1], [w - b - 2, b + 1, -1, 1], [b + 1, h - b - 2, 1, -1], [w - b - 2, h - b - 2, -1, -1]]) for (let k = 0; k < 8; k++) { dot(g, x + dx * k, y, PALETTE.amber); dot(g, x, y + dy * k, PALETTE.amber); }
}

// each kind: m = metres one texture covers (w x h = m * PX; `h` in pixels when it differs), rough, metal, draw(g, w, h)
const KINDS = {
  labResin: {m: 2, rough: 0.3, draw: resin('#98a3ac', 101)}, labResinLight: {m: 2, rough: 0.3, draw: resin('#c4ced4', 102)}, labResinDark: {m: 2, rough: 0.3, draw: resin('#6c7781', 103)},
  labHex: {m: 2, rough: 0.5, draw: hexTiles('#5d7081', 104)}, labHexDark: {m: 2, rough: 0.5, draw: hexTiles('#3f505e', 105)},
  labClean: {m: 2, rough: 0.4, draw: clean}, labSteel: {m: 2, rough: 0.35, metal: 0.35, draw: steel}, labEsd: {m: 0.5, rough: 0.85, draw: esd},
  labCircuit: {m: 2, rough: 0.5, draw: circuit}, labBlueprint: {m: 2, rough: 0.9, draw: blueprint},
  labTrace: {m: 2, h: 11, rough: 0.5, draw: trace},
  labPad: {fit: true, rough: 0.6, draw: pad},
};
/** the office's floor kinds seen as lab kinds (office-floor.js buildFloor: the zones keep their names, only the picture changes) */
export const FLOOR = {
  alias: {carpet: 'labResin', booth: 'labHexDark', parquet: 'labResinDark', parquetLight: 'labClean', common: 'labHex', tiles: 'labResinLight',
          stone: 'labSteel', game: 'labHexDark', mat: 'labEsd', rug: 'labPad'},
  kinds: KINDS,
};

let V = null, CTX = null;                                           // office-voxel.js and the context, from install(): the models are built after it
const made = new Map();
/** a lab picture as a shared texture (one per name; do not dispose): `labTexture({THREE, renderer}, 'labCircuit')`. Names: the keys of KINDS except labPad */
export function labTexture(ctx, name) {
  const K = KINDS[name];
  if (!K || K.fit) throw new Error(`labTexture: ${name}`);
  if (!made.has(name)) made.set(name, makeTexture(ctx, K.draw, K.m * PX, K.h || K.m * PX));
  return made.get(name);
}

// ------------------------------------------------------------------ the light
/** cold light, after every change of the sky (office.js drawSky sets the warm one first) */
export function sky({sun, hemi, lamps, night, dusk}) {
  sun.color.set(night ? THEME.sun.night : dusk ? THEME.sun.dusk : THEME.sun.day);
  hemi.color.set(THEME.hemi[0]); hemi.groundColor.set(THEME.hemi[1]);
  for (const l of lamps) l.color.set(THEME.lamp);
}

// ------------------------------------------------------------------ the walls
/** a band of printed circuit along the foot of every outer wall (one mesh, one draw call), but not across the doors: PLACED.walls from office-layout.js resolve() */
export function install(ctx) {
  const {THREE, renderer, scene, PLACED} = ctx; V = ctx.V ?? V; CTX = ctx;
  const map = labTexture({THREE, renderer}, 'labTrace'), H = KINDS.labTrace.h / PX, Y0 = 0.26, OUT = 0.13;   // 13 cm: the face of the wall (12.5) and 5 mm
  const pos = [], nor = [], uv = [], idx = [];
  for (const w of PLACED.walls) {
    const c = Math.cos(w.rot), s = Math.sin(w.rot), ax = w.a[0], az = w.a[1];       // along the wall (c, -s), inward (s, c)
    const gaps = [...w.doors].sort((p, q) => p[0] - q[0]).map(([u, v]) => [u - 0.3, v + 0.3]);   // the door frames stand out 25 cm
    let from = 0;
    for (const [u0, u1] of [...gaps, [w.len, w.len]]) {
      if (u0 - from > 0.2) {
        const n = pos.length / 3, at = (u, y) => [ax + c * u + s * OUT, y, az - s * u + c * OUT];
        for (const [u, y, v] of [[from, Y0, 0], [u0, Y0, 0], [u0, Y0 + H, 1], [from, Y0 + H, 1]]) { pos.push(...at(u, y)); nor.push(s, 0, c); uv.push(u / KINDS.labTrace.m, v); }
        idx.push(n, n + 1, n + 2, n, n + 2, n + 3);
      }
      from = u1;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(idx);
  const band = new THREE.Mesh(g, new THREE.MeshStandardMaterial({map, roughness: 0.5, emissive: '#ffffff', emissiveMap: map, emissiveIntensity: 0.3,
                                                              polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -4}));
  band.name = 'lab-band'; scene.add(band);
  return {band};
}

// ------------------------------------------------------------------ the furniture
// The lab's builders carry the names of office-voxel.js and the same size and pivot: the plan (collision boxes, seats, desks) does not change.
// Voxel meshes with vertex colours, like the office's: they bake together with the rest (no draw call more).
const STEEL = '#aeb8c2', STEEL_L = '#c9d3da', STEEL_D = '#6c7781', ESD = '#34444c';
const vmesh = (v, opts) => V.mesh(v, {scale: 0.05, jitter: 0.03, ...opts});

function workDesk() {                    // 1.6 x 0.8 m, top at 0.7 m: ESD bench top on a steel frame, a perforated panel with a cyan line, a steel pedestal
  const v = new V.Vox();
  v.box(0, 13, 0, 31, 13, 15, ESD).box(0, 13, 15, 31, 13, 15, STEEL_L).box(0, 12, 15, 31, 12, 15, STEEL_L).box(0, 13, 0, 0, 13, 15, STEEL_L).box(31, 13, 0, 31, 13, 15, STEEL_L);
  for (const x of [1, 29]) v.box(x, 1, 7, x + 1, 12, 8, STEEL).box(x, 0, 1, x + 1, 0, 14, STEEL_L);
  v.box(1, 3, 7, 30, 3, 8, STEEL);                                            // the stretcher between the legs
  v.box(3, 6, 1, 28, 11, 1, STEEL_L).box(3, 11, 1, 28, 11, 1, PALETTE.cyan);   // panel with a cyan line
  v.box(5, 11, 3, 18, 11, 5, '#2b3a42');                                      // cable tray
  v.box(21, 1, 3, 27, 11, 14, '#e3e9ed');
  for (const y of [4, 8]) v.box(21, y, 14, 27, y, 14, STEEL_D);
  for (const y of [2, 6, 10]) v.box(23, y, 15, 25, y, 15, PALETTE.cyan);      // handles, standing out
  return vmesh(v, {pivot: [16, 0, 8], jitter: 0.06});
}
function cubicle() {                     // the screens of one cubicle: frosted glass in a steel edge, a cyan line under the frosted strip
  const v = new V.Vox(), glass = '#b9d3dc';
  const screen = (x0, x1, z0, z1, h) => {
    v.box(x0, 0, z0, x1, 1, z1, STEEL_D).box(x0, 2, z0, x1, h - 1, z1, (x, y) => (x + y) % 9 === 0 ? '#cfe3ea' : glass).box(x0, h, z0, x1, h, z1, STEEL);
  };
  screen(-20, 20, -20, -19, 22);
  v.box(-20, 17, -20, 20, 21, -19, '#e6f2f6').box(-20, 16, -20, 20, 16, -19, PALETTE.cyan);
  screen(-20, -19, -18, 3, 19); screen(18, 19, -18, 3, 19);
  for (const x of [-20, 20]) v.box(x, 0, -20, x, 22, -19, STEEL);
  return vmesh(v, {pivot: [0.5, 0, 0.5]});
}
function smallDesk() {                   // 1.2 x 0.7 m: white resin top, steel legs, a tablet and a rack of sample tubes
  const v = new V.Vox();
  v.box(0, 6, 0, 11, 6, 6, '#e8eef1').box(0, 6, 6, 11, 6, 6, STEEL_L);
  for (const [x, z] of [[0, 0], [11, 0], [0, 6], [11, 6]]) v.box(x, 0, z, x, 5, z, STEEL);
  v.box(3, 7, 2, 6, 7, 4, '#202228').box(8, 7, 1, 10, 7, 3, STEEL_D);
  v.box(8, 8, 1, 8, 8, 2, PALETTE.cyan).box(9, 8, 1, 9, 8, 2, PALETTE.amber).box(10, 8, 1, 10, 8, 2, PALETTE.cyan);
  return V.mesh(v, {pivot: [6, 0, 3.5]});
}
function bossDesk() {                    // the director's desk: white resin, cyan trim, the name plate and a plant kept
  const v = new V.Vox(), top = '#dfe6eb', side = '#c3ccd3', trim = PALETTE.cyan;
  v.box(0, 6, 0, 23, 7, 9, top).box(0, 0, 0, 23, 5, 1, side).box(0, 0, 0, 1, 5, 9, side).box(22, 0, 0, 23, 5, 9, side);
  v.box(0, 7, 0, 23, 7, 0, trim).box(4, 2, -1, 19, 2, -1, trim);
  v.box(9, 8, 1, 14, 8, 1, '#2b2b2b').box(9, 9, 1, 14, 9, 1, trim);
  v.box(19, 8, 6, 20, 9, 7, PALETTE.amber).box(19, 10, 6, 20, 10, 7, '#ffffff');
  v.box(2, 8, 6, 3, 8, 7, '#2e7d32').box(2, 9, 6, 3, 11, 7, '#43a047').set(2, 12, 6, '#66bb6a');
  return V.mesh(v, {pivot: [12, 0, 5]});
}
function confTable() {                   // a white resin table on steel legs
  const v = new V.Vox(), top = '#dde5ea';
  v.box(0, 7, 0, 27, 7, 11, top).box(1, 7, 0, 26, 7, 0, STEEL_L);
  v.box(6, 0, 4, 7, 6, 7, STEEL).box(20, 0, 4, 21, 6, 7, STEEL).box(4, 0, 5, 9, 0, 6, STEEL).box(18, 0, 5, 23, 0, 6, STEEL);
  v.box(12, 8, 5, 15, 8, 6, '#2b2f38');
  return V.mesh(v, {pivot: [14, 0, 6]});
}
function fumeHood() {                    // 1.2 x 0.7 m: steel base cabinet, ESD work surface, an enclosure with glass sides and an open sash, a duct to the ceiling
  const v = new V.Vox(), W = 24, D = 14;
  v.box(0, 0, 0, W - 1, 17, D - 1, STEEL_L).box(0, 0, 0, W - 1, 1, D - 1, STEEL_D);
  for (const x of [0, 8, 15, 23]) v.box(x, 2, D - 1, x, 16, D - 1, STEEL_D);
  for (const x of [6, 9, 14, 17]) v.box(x, 11, D, x, 14, D, PALETTE.cyan);
  v.box(0, 18, 0, W - 1, 18, D - 1, ESD).box(0, 18, D - 1, W - 1, 18, D - 1, STEEL);
  v.box(0, 19, 0, W - 1, 43, 0, '#bcd6df').box(0, 19, 0, 0, 43, D - 1, '#bcd6df').box(W - 1, 19, 0, W - 1, 43, D - 1, '#bcd6df');
  v.box(0, 44, 0, W - 1, 45, D - 1, STEEL).box(0, 40, D - 1, W - 1, 43, D - 1, STEEL_L);
  v.box(2, 41, D - 1, 5, 42, D - 1, '#0f2c36').set(3, 41, D - 1, '#43a047').set(4, 41, D - 1, '#43a047');
  v.box(0, 19, D - 1, 0, 39, D - 1, STEEL).box(W - 1, 19, D - 1, W - 1, 39, D - 1, STEEL);
  v.box(9, 46, 4, 14, 59, 9, STEEL_L).box(9, 59, 4, 14, 59, 9, STEEL_D);
  return vmesh(v, {pivot: [W / 2, 0, D / 2], jitter: 0.02});
}
/** the lab's builder for a model name of office-voxel.js (undefined: office.js uses the office's own) */
// the pieces whose office model takes the colour of its wood as an argument: the same model in steel and white resin
const binderShelf = seed => V.binderShelf(seed, STEEL), barCounter = len => V.barCounter(len, STEEL_L), cafeTable = top => V.cafeTable(top ? top : '#e3e9ed');
export const MODELS = {workDesk, cubicle, smallDesk, bossDesk, confTable, fumeHood, binderShelf, barCounter, cafeTable};
CATALOG.fumeHood = {model: 'fumeHood', foot: [1.2, 0.7]};              // a new piece of the catalog: office-layout.js resolve() gives it its box

function labCabinet(it) {                // a tall cabinet of the pack becomes a server rack or a sample fridge, as big as the pack's one
  const [w, h, d] = V.packSize(it.pack, it.scale ?? 0.065) || [0.8, 1.8, 0.5], seed = V.hashName(it.x + ',' + it.z), r = V.rnd(seed), v = new V.Vox();
  const W = Math.max(8, Math.round(w / 0.05)), H = Math.max(20, Math.round(h / 0.05)), D = Math.max(6, Math.round(d / 0.05));
  if (seed % 2) {                        // sample fridge: steel body, dark glass door with cyan shelves, a handle, a status strip
    v.box(0, 0, 0, W - 1, H - 1, D - 1, STEEL_L).box(0, 0, 0, W - 1, 1, D - 1, STEEL_D);
    v.box(1, 4, D - 1, W - 2, H - 5, D - 1, '#0f2c36');
    for (let y = 8; y < H - 5; y += 6) v.box(2, y, D - 1, W - 3, y, D - 1, PALETTE.cyan);
    v.box(W - 3, 6, D, W - 3, H - 8, D, STEEL).box(2, H - 3, D - 1, W - 3, H - 3, D - 1, '#1f8a98');
  } else {                               // server rack: dark case, units with vents and status lights
    v.box(0, 0, 0, W - 1, H - 1, D - 1, '#161b22').box(0, H - 1, 0, W - 1, H - 1, D - 1, STEEL_D);
    for (let y = 2; y < H - 3; y += 3) {
      v.box(1, y, D - 1, W - 2, y + 1, D - 1, '#252d38').set(2, y, D - 1, [PALETTE.cyan, '#43a047', PALETTE.amber][Math.floor(r() * 3)]).set(3, y, D - 1, '#43a047');
      for (let x = 5; x < W - 2; x += 2) v.set(x, y + 1, D - 1, '#161b22');
    }
  }
  return vmesh(v, {pivot: [W / 2, 0, D / 2], jitter: 0.02});
}
function labBoard(it) {                  // a blueprint panel in a steel frame instead of the pack's corkboard and wall graph (same size, same place)
  const {THREE} = CTX, [w, h, d] = V.packSize(it.pack, it.scale ?? 0.065) || [1, 0.8, 0.1], g = new THREE.Group();
  const W = Math.max(6, Math.round(w / 0.05)), H = Math.max(6, Math.round(h / 0.05)), iw = (W - 2) * 0.05, ih = (H - 2) * 0.05;
  const frame = vmesh(new V.Vox().box(0, 0, 0, W - 1, 0, 0, STEEL).box(0, H - 1, 0, W - 1, H - 1, 0, STEEL).box(0, 0, 0, 0, H - 1, 0, STEEL).box(W - 1, 0, 0, W - 1, H - 1, 0, STEEL), {pivot: [W / 2, 0, 0]});
  frame.position.z = -d / 2;
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(iw, ih), new THREE.MeshStandardMaterial({map: labTexture(CTX, 'labBlueprint'), roughness: 0.8}));
  const uv = plane.geometry.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * iw / KINDS.labBlueprint.m, uv.getY(i) * ih / KINDS.labBlueprint.m);
  plane.position.set(0, h / 2, -d / 2 + 0.052); g.add(frame, plane);
  return g;
}
const TINT = {couch: {hue: 0.55, sat: 0.5, light: 1.1}};              // the brown couches go blue-grey
/** a lab piece for a placed item (office-layout.js resolve() item), or null: the office builds it as usual */
export function item(it, Vm) {
  V ??= Vm;
  if (!V) return null;                   // no voxel helpers yet: the office draws the piece
  if (!it.pack && MODELS[it.model]) return MODELS[it.model](...(it.args || []));
  if (it.type === 'cabinet') return labCabinet(it);
  if (it.type === 'corkboard' || it.type === 'wallGraph') return labBoard(it);
  if (TINT[it.type] && it.pack) return V.packModel(it.pack, {...it, tint: TINT[it.type]});
  return null;
}
/** the items of the plan for the lab: without the pieces standing where the research panels hang (no mesh, no collision box either), plus a fume hood against
 *  the south wall of the meeting room (once: a saved plan keeps its own) */
export function withLab(items) {
  const kept = items.filter(it => !CLEAR.some(c => it.x >= c.x0 && it.x <= c.x1 && it.z >= c.z0 && it.z <= c.z1));
  return kept.some(it => it.type === 'fumeHood') ? kept : [...kept, {type: 'fumeHood', x: 12, z: 9.5, rot: Math.PI}];
}
