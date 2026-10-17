// The laboratory: the look of a research room (config.mode === 'research'). Same plan, same places, same functions as the office
// (arcade, TV, radio, rack, arena...): only the pictures change. A clean lab: white walls, steel, grey resin floors, cold light,
// cyan and amber for what is on and what needs care. office.js loads this file only for research rooms (import() on demand), so the
// normal office pays nothing for it. Pixel art drawn in a canvas like office-floor.js (same density, same filters), no images.
//
// What office.js uses: THEME (colours), FLOOR (for buildFloor), sky() (the light), install() (the wall bands), labTexture() (the
// same pictures for other modules: the research walls of office-research.js), PALETTE (the colours of the states, for every module).
import {PX, rnd, shade, dot, speckle, makeTexture} from './office-floor.js';

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
    dot(g, x, y, c.d < 1.2 ? stud : c.edge < 0.6 ? joint : c.edge < 1.6 ? (c.lit ? hi : lo) : tones[c.id]);
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
  for (let k = 0; k < cells * 2; k++) {                             // buses along x and along y: a segment and a pad at each end
    const along = k % 2 === 0, line = Math.floor(r() * cells) * 8 + (r() < 0.5 ? 2 : 5), start = 2 + Math.floor(r() * (w - 32)), len = 10 + Math.floor(r() * 18);
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
export function install({THREE, renderer, scene, PLACED}) {
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
