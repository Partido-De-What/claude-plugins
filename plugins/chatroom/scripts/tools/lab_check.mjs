// Self-check of office-lab.js without a browser: every picture draws inside its canvas, the hexagon lattice repeats every w x h pixels,
// and the wall band covers the walls but not the doors. Run: node tools/lab_check.mjs (exit 0 = ok)
import assert from 'node:assert/strict';
import {FLOOR, THEME, PALETTE, hexAt, install} from '../office-lab.js';
import {PX} from '../office-floor.js';

for (const [name, K] of Object.entries(FLOOR.kinds)) {
  const [w, h] = K.fit ? [200, 120] : [K.m * PX, K.h || K.m * PX], rects = [];
  K.draw({set fillStyle(v) {}, fillRect: (x, y, rw, rh) => rects.push([x, y, rw, rh])}, w, h);
  assert(rects.length > 10, `${name}: draws something`);
  for (const [x, y, rw, rh] of rects) assert(x >= 0 && y >= 0 && x + rw <= w && y + rh <= h, `${name}: ${[x, y, rw, rh]} outside ${w}x${h}`);
}
const ids = new Set();
for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) {
  const a = hexAt(x + 0.5, y + 0.5, 64, 64), b = hexAt(x + 64.5, y + 128.5, 64, 64);
  assert.equal(a.id, b.id, `hex repeat at ${x},${y}`); assert(a.edge >= -1e-9, 'edge >= 0'); ids.add(a.id);
}
assert.equal(ids.size, 30, 'all 30 hexagons of the period are seen');
for (const t of Object.values(FLOOR.alias)) assert(FLOOR.kinds[t], `alias target ${t}`);
// the band: a fake THREE that keeps the geometry; north wall of the default plan (a (-15,-10) b (15,-10), rot 0, a door at 8..9)
let pos = [];
const THREE = {BufferGeometry: class { setAttribute(n, a) { if (n === 'position') pos = a.arr; } setIndex() {} },
               Float32BufferAttribute: class { constructor(arr) { this.arr = arr; } }, Mesh: class { constructor(g, m) { this.g = g; } }, MeshStandardMaterial: class {}};
globalThis.document = {createElement: () => ({getContext: () => ({set fillStyle(v) {}, fillRect() {}})})};
THREE.CanvasTexture = class { constructor() {} }; THREE.RepeatWrapping = 1; THREE.NearestFilter = 1; THREE.SRGBColorSpace = 1;
install({THREE, renderer: {capabilities: {getMaxAnisotropy: () => 1}}, scene: {add() {}}, PLACED: {walls: [{a: [-15, -10], b: [15, -10], len: 30, rot: 0, doors: [[8, 9]]}]}});
const xs = []; for (let i = 0; i < pos.length; i += 3) xs.push(pos[i]);
assert.equal(pos.length / 3, 8, 'two segments around one door');
assert(!xs.some(x => x > -15 + 8 - 0.3 + 1e-9 && x < -15 + 9 + 0.3 - 1e-9), 'no band across the door');
assert(pos.every((v, i) => i % 3 !== 2 || Math.abs(v - (-10 + 0.13)) < 1e-9), 'band stands 13 cm inside the wall');
console.log('lab_check: ok', Object.keys(FLOOR.kinds).length, 'kinds', THEME.wall, PALETTE.cyan);
