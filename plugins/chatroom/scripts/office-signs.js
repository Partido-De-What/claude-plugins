// The signs of the office: neon boards that name the places (the control room, the arcade, the cinema, the open space), hanging from the ceiling or on a wall, and a
// small guide on an easel at the entrance for whoever comes in the first time. They are data (LAYOUT.signs, in office-layout.js: text in both languages, where,
// how big, which colour), so a sign can be moved or renamed without touching this file. Drawn once per language.
// In a research room (`lab`, office-lab.js) the boards are clean laboratory plates, white with a steel frame, a coloured badge and a hazard strip,
// the places have lab names and the guide is on white paper.

// the guide's lines are in locales/<lang>.json (signs.guide.N)
const COLORS = {cyan: ['#e0ffff', '#00e5ff'], magenta: ['#ffe0fa', '#ff2bd6'], amber: ['#fff4d6', '#ffab00'], green: ['#eaffea', '#39e75f'], white: ['#ffffff', '#9fb3ff']};

function neon(text, w, h, tone) {
  const c = document.createElement('canvas'); c.width = Math.round(w * 400); c.height = Math.round(h * 400); const g = c.getContext('2d');
  const [core, glow] = COLORS[tone] || COLORS.cyan;
  g.fillStyle = '#0a0c18'; g.fillRect(0, 0, c.width, c.height);
  g.strokeStyle = glow; g.lineWidth = 6; g.shadowColor = glow; g.shadowBlur = 14; g.strokeRect(10, 10, c.width - 20, c.height - 20); g.shadowBlur = 0;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  let size = c.height * 0.52; g.font = `900 ${size}px "Segoe UI", sans-serif`;
  while (g.measureText(text).width > c.width - 70 && size > 14) { size -= 3; g.font = `900 ${size}px "Segoe UI", sans-serif`; }
  g.shadowColor = glow; g.shadowBlur = 26; g.fillStyle = glow; g.fillText(text, c.width / 2, c.height / 2 + 3); g.shadowBlur = 10; g.fillStyle = core; g.fillText(text, c.width / 2, c.height / 2 + 3);
  return c;
}
const LAB_TONES = {cyan: '#4dd0e1', magenta: '#ba68c8', amber: '#ffb74d', green: '#43a047', white: '#90a4ae'};
function plate(text, w, h, tone) {                     // a laboratory plate: the badge in the tone's colour, the place in dark ink, a hazard strip
  const c = document.createElement('canvas'); c.width = Math.round(w * 400); c.height = Math.round(h * 400); const g = c.getContext('2d');
  g.fillStyle = '#eef3f6'; g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = '#aeb8c2'; g.fillRect(0, 0, c.width, 8); g.fillRect(0, c.height - 8, c.width, 8); g.fillRect(0, 0, 8, c.height); g.fillRect(c.width - 8, 0, 8, c.height);
  const badge = Math.round(c.height * 0.3); g.fillStyle = LAB_TONES[tone] || LAB_TONES.cyan; g.fillRect(8, 8, badge, c.height - 16);
  g.strokeStyle = '#0e1a22'; g.lineWidth = 5; g.beginPath();                    // a hexagon on the badge
  for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3 + Math.PI / 6, x = 8 + badge / 2 + Math.cos(a) * badge * 0.28, y = c.height / 2 + Math.sin(a) * badge * 0.28; if (k) g.lineTo(x, y); else g.moveTo(x, y); }
  g.closePath(); g.stroke();
  for (let x = 8 + badge; x < c.width - 8; x += 24) { g.fillStyle = '#ffb74d'; g.fillRect(x, c.height - 22, 12, 14); g.fillStyle = '#0e1a22'; g.fillRect(x + 12, c.height - 22, 12, 14); }
  g.textAlign = 'left'; g.textBaseline = 'middle'; g.fillStyle = '#0e1a22';
  const x0 = 8 + badge + 20, room = c.width - x0 - 24;
  let size = (c.height - 30) * 0.5; g.font = `900 ${size}px "Segoe UI", sans-serif`;
  while (g.measureText(text).width > room && size > 14) { size -= 3; g.font = `900 ${size}px "Segoe UI", sans-serif`; }
  g.fillText(text, x0, (c.height - 22) / 2 + 2);
  return c;
}
function guide(lines, lab) {
  const c = document.createElement('canvas'); c.width = 640; c.height = 480; const g = c.getContext('2d');
  g.fillStyle = lab ? '#eef3f6' : '#f4ecd8'; g.fillRect(0, 0, c.width, c.height); g.strokeStyle = lab ? '#6c7781' : '#5d3a1a'; g.lineWidth = 10; g.strokeRect(5, 5, c.width - 10, c.height - 10);
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillStyle = lab ? '#00838f' : '#c0392b'; g.font = '900 54px "Segoe UI", sans-serif'; g.fillText(lines[0], c.width / 2, 62);
  g.fillStyle = lab ? '#0e1a22' : '#2b2118'; g.font = '600 31px "Segoe UI", sans-serif';
  lines.slice(1).forEach((l, i) => g.fillText(l, c.width / 2, 140 + i * 62));
  return c;
}

/** the lab's name of a place, by the office's English text (undefined: the sign keeps its own) */
const labName = (en, lg) => ({'CONTROL ROOM': I18N.text('office.lab.sign.control', {}, lg), CINEMA: I18N.text('office.lab.sign.screening', {}, lg), 'OPEN SPACE': I18N.text('office.lab.sign.lab', {}, lg)})[en];

/** signs: LAYOUT.signs; V: office-voxel.js; lang(): 'it' or 'en'; lab: the look of a research room. Returns {redraw()} (call when the language may have changed) */
export function buildSigns({THREE, scene, V, signs = [], lang = () => 'en', lab = false}) {
  const items = [];
  const group = new THREE.Group(); group.name = 'signs'; scene.add(group);            // one holder, so the office can bake the boards' bodies and rods with the furniture
  const plane = (tex, w, h) => new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({map: tex, toneMapped: false}));
  for (const s of signs) {
    const root = new THREE.Group(); root.position.set(s.x, s.y, s.z); root.rotation.y = s.rot || 0; group.add(root);
    const w = s.w || 1.4, h = s.h || 0.4;
    const tex = new THREE.CanvasTexture(document.createElement('canvas')); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;     // both faces of a hanging sign show the same picture: one texture
    const front = plane(tex, w, h); front.position.z = 0.028; root.add(front);
    if (s.hang || s.both) {                                                     // a hanging sign reads from both sides
      const back = plane(tex, w, h); back.position.z = -0.028; back.rotation.y = Math.PI; root.add(back);
    }
    // the board's body: a dark slab with a thin frame, and rods to the ceiling when it hangs
    const body = V.mesh(new V.Vox().box(0, 0, 0, Math.round(w * 20) - 1, Math.round(h * 20) - 1, 0, lab ? '#8c969f' : '#14161f'), {pivot: [w * 10, h * 10, 0.5], scale: 0.05, jitter: 0.02});
    root.add(body);
    if (s.hang) for (const dx of [-w / 2 + 0.12, w / 2 - 0.12]) {
      const rod = V.mesh(new V.Vox().box(0, 0, 0, 0, Math.max(2, Math.round((3.0 - s.y - h / 2) * 20)), 0, '#8a929e'), {pivot: [0, 0, 0], scale: 0.05, jitter: 0}); rod.position.set(dx, h / 2, 0); root.add(rod);
    }
    if (s.easel) for (const dx of [-w / 2 + 0.1, w / 2 - 0.1]) {                  // an easel: two legs to the floor
      const leg = V.mesh(new V.Vox().box(0, 0, 0, 1, Math.max(2, Math.round((s.y - h / 2) * 20)) - 1, 1, lab ? '#8c969f' : '#5d3a1a'), {pivot: [1, 0, 1], scale: 0.05, jitter: 0.02}); leg.position.set(dx, -s.y, -0.04); root.add(leg);
    }
    items.push({s, tex});
  }
  let drawn = '';
  function redraw() {
    const lg = lang() === 'it' ? 'it' : 'en';
    if (lg === drawn) return; drawn = lg;
    for (const {s, tex} of items) {
      const text = typeof s.text === 'string' ? s.text : (s.text[lg] || s.text.en);
      tex.image = s.kind === 'guide' ? guide(I18N.table('signs', {}, null, lg).guide, lab)
        : lab ? plate(labName(typeof s.text === 'string' ? s.text : s.text.en, lg) || text, s.w || 1.4, s.h || 0.4, s.tone) : neon(text, s.w || 1.4, s.h || 0.4, s.tone);
      tex.needsUpdate = true;
    }
  }
  return {redraw, count: items.length, group};                       // drawn by the office's first drawBoards(), when the language is known
}
