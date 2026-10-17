// Self-check of office-lab.js without a browser: every picture draws inside its canvas, the hexagon lattice repeats every w x h pixels,
// and the wall band covers the walls but not the doors. Run: node tools/lab_check.mjs (exit 0 = ok)
import assert from 'node:assert/strict';
import {FLOOR, THEME, PALETTE, MODELS, hexAt, install, item, withLab} from '../office-lab.js';
import {CATALOG} from '../office-layout.js';
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
// a fake office-voxel.js: a Vox that only keeps its bounds, and the builders return it
class Vox { constructor() { this.b = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]; this.position = {z: 0}; }
  set(x, y, z, c) { const b = this.b; b[0] = Math.min(b[0], x); b[1] = Math.min(b[1], y); b[2] = Math.min(b[2], z); b[3] = Math.max(b[3], x); b[4] = Math.max(b[4], y); b[5] = Math.max(b[5], z); return this; }
  box(x0, y0, z0, x1, y1, z1, c) { if (c === null || c === undefined) return this; return this.set(x0, y0, z0).set(x1, y1, z1); } }
const V = {Vox, mesh: v => v, hashName: s => 7, rnd: () => () => 0.5, packSize: () => [0.8, 1.8, 0.5], packModel: () => 'pack'};
THREE.Group = class { constructor() { this.position = {z: 0}; } add() {} }; THREE.PlaneGeometry = class { constructor() { this.attributes = {uv: {count: 4, getX: () => 1, getY: () => 1, setXY() {}}}; } };
THREE.Mesh = class { constructor(g) { this.geometry = g; this.position = {set() {}}; } };
install({THREE, V, renderer: {capabilities: {getMaxAnisotropy: () => 1}}, scene: {add() {}}, PLACED: {walls: [{a: [-15, -10], b: [15, -10], len: 30, rot: 0, doors: [[8, 9]]}]}});
const xs = []; for (let i = 0; i < pos.length; i += 3) xs.push(pos[i]);
assert.equal(pos.length / 3, 8, 'two segments around one door');
assert(!xs.some(x => x > -15 + 8 - 0.3 + 1e-9 && x < -15 + 9 + 0.3 - 1e-9), 'no band across the door');
assert(pos.every((v, i) => i % 3 !== 2 || Math.abs(v - (-10 + 0.13)) < 1e-9), 'band stands 13 cm inside the wall');
// the furniture: same x/z extent (voxels) as the office's model it replaces, so the plan's collision boxes still fit (height may differ by a voxel)
const SAME = {workDesk: [0, 0, 0, 31, 13, 15], cubicle: [-20, 0, -20, 20, 22, 3], smallDesk: [0, 0, 0, 11, 7, 6], bossDesk: [0, 0, -1, 23, 12, 9], confTable: [0, 0, 0, 27, 8, 11]};
for (const [name, e] of Object.entries(SAME)) { const b = MODELS[name]().b; assert([0, 2, 3, 5].every(i => b[i] === e[i]), `${name} footprint ${b} vs ${e}`); assert(b[4] - e[4] <= 1 && b[1] === 0, `${name} height ${b[4]}`); }
const hood = MODELS.fumeHood().b; assert(hood[0] === 0 && hood[3] === 23 && hood[2] === 0 && hood[5] <= 14 && hood[4] <= 59, `hood ${hood}`);
assert.deepEqual(CATALOG.fumeHood.foot, [1.2, 0.7], 'catalog fumeHood');
assert(item({type: 'cabinet', pack: 'x', x: 1, z: 2}, V).b[3] === 15, 'cabinet as wide as the pack one (0.8 m = 16 voxels)');
assert(item({type: 'cubicle', model: 'cubicle', args: []}, V).b[0] === -20, 'item() builds a lab model by name');
assert.equal(item({type: 'plantTall', model: 'plantTall', args: []}, V), null, 'item() leaves the rest to the office');
assert.equal(item({type: 'couch', pack: 'p'}, V), 'pack', 'couch tinted through packModel');
const plan = withLab([{type: 'plantTall'}]); assert.equal(plan.length, 2); assert.equal(withLab(plan).length, 2, 'the hood is added once');
console.log('lab_check: ok', Object.keys(FLOOR.kinds).length, 'kinds', THEME.wall, PALETTE.cyan);
