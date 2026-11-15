// The Skills view (0.19, D7): the origin names and their explanation line, "where it comes from" on the card, the Update button only on
// skills with an outside creator (check = read only, apply = preview first), "derive from the current conversation" = source {chat:true}.
// node plugins/chatroom/scripts/tools/test_skills_d7.mjs
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };

const sk = (name, origin, extra = {}) => ({id: `${origin}:-:${name}`, name, brief: name + ' brief', description: name + ' d', origin, plugin: null, version: null, path: '/x/' + name, advised: [], agents: [], updatable: false, ...extra});
const SKILLS = [sk('cav', 'plugin', {plugin: 'cav@market', version: '1.2.0', updatable: true, source: {kind: 'marketplace', label: 'cav@market', version: '1.2.0'}}),
  sk('acct', 'account', {source: {kind: 'claude'}}), sk('mine', 'user'), sk('cloned', 'added', {updatable: true, source: {kind: 'repo', label: 'owner/name'}})];
const DATA = {v: 1, origins: ['user', 'plugin', 'added', 'account'], skills: SKILLS, agents: [], searcher: {present: true, name: 'S', busy: false}, requests: [], rooms: [], candidates: []};
const els = {}, calls = [], handlers = {};
let SEL = 'plugin:-:cav';
const el = id => (els[id] ??= {id, innerHTML: '', textContent: '', value: '', style: {}, classList: {toggle() {}, add() {}, remove() {}}, querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, insertAdjacentElement() {}, focus() {}});
const mk = () => ({classList: {toggle() {}, add() {}, remove() {}}, style: {}, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, offsetWidth: 0, insertAdjacentElement() {},
  addEventListener(t, f) { (handlers[t] ??= []).push(f); }, set innerHTML(v) {}, get innerHTML() { return ''; }});
globalThis.window = globalThis;
globalThis.CSS = {escape: s => s};
globalThis.document = {createElement: mk, getElementById: id => (id === 'officeBtn' ? null : el(id)), head: {appendChild() {}}, body: {appendChild() {}, classList: {toggle() {}}}, hidden: false, activeElement: null};
globalThis.location = {search: '', href: 'http://x/'};
globalThis.history = {replaceState() {}};
globalThis.localStorage = {getItem: () => JSON.stringify({tab: 'explore', sel: SEL}), setItem() {}};
globalThis.addEventListener = () => {};
globalThis.setInterval = () => 0;
globalThis.I18N = {text: (k, f) => k + (f ? JSON.stringify(f) : '')};
let UPD = {installed: '1.2.0', available: '1.3.0', newer: true, changes: 'new <b>things</b>', source: 'plugin cav@market'};
globalThis.fetch = async (url, o) => {
  if (url === 'skills.json') return {ok: true, json: async () => DATA};
  const b = JSON.parse(o.body); calls.push(b);
  const j = b.action === 'update_check' ? {ok: true, update: UPD}
    : b.action === 'update_apply' ? {ok: true, preview: {name: 'cav', installed: '1.2.0', available: '1.3.0', how: 'claude plugin update'}} : b.action === 'derive' ? {ok: true, preview: {kind: 'derive', name: 'LEAD', task: 't'}} : {ok: true};
  return {ok: true, text: async () => JSON.stringify(j)};
};
await import(pathToFileURL(path.join(S, 'skills-view.js')).href);
globalThis.skillsView.open(true);
await new Promise(r => setTimeout(r, 50));
const rows = () => els.skRows.innerHTML;
const click = t => handlers.click.forEach(f => f({target: {classList: {contains: () => false}, closest: () => t}}));
const wait = () => new Promise(r => setTimeout(r, 20));

test('the explanation line is there (all groups)', els.skHelp.textContent === 'skillsv.ox.all' ? '' : els.skHelp.textContent);
click({dataset: {origin: 'account'}});
test('picking a group changes the explanation line', els.skHelp.textContent === 'skillsv.ox.account' ? '' : els.skHelp.textContent);
click({dataset: {origin: ''}});
test('a plugin skill says which plugin on its card', rows().includes('skillsv.o.pluginNamed{&quot;name&quot;:&quot;cav&quot;}') ? '' : rows().slice(0, 500));
test('the opened card says where it comes from (marketplace, plugin, version)', rows().includes('skillsv.from.plugin{&quot;name&quot;:&quot;cav&quot;,&quot;market&quot;:&quot;market&quot;,&quot;version&quot;:&quot;1.2.0&quot;}') ? '' : rows().slice(-900));
test('updatable: the Check button is there', rows().includes('data-act="updcheck"') ? '' : rows().slice(-900));

click({dataset: {act: 'updcheck'}});
await wait();
test('check = update_check, read only, no confirm', calls.filter(c => c.action === 'update_check').length === 1 && !calls.some(c => c.confirm) ? '' : JSON.stringify(calls));
test('a newer version shows both versions, the changes (escaped) and the Update button', /1\.3\.0/.test(rows()) && rows().includes('new &lt;b&gt;things') && rows().includes('data-act="updapply"') ? '' : rows().slice(-900));
click({dataset: {act: 'updapply'}});
await wait();
const ap = calls.filter(c => c.action === 'update_apply');
test('Update asks for a preview first (confirm false)', ap.length === 1 && ap[0].confirm === false ? '' : JSON.stringify(ap));

UPD = {installed: 'ec57758', available: '12fa3cc', newer: null};
click({dataset: {act: 'updcheck'}});
await wait();
test('a different version with newer unknown: says both, offers Update (the pull is fast-forward only)', rows().includes('skillsv.upd.differs{&quot;a&quot;:&quot;ec57758&quot;,&quot;b&quot;:&quot;12fa3cc&quot;}') && rows().includes('data-act="updapply"') ? '' : rows().slice(-900));
UPD = {installed: '1.2.0', available: null, newer: null};
click({dataset: {act: 'updcheck'}});
await wait();
test('no available version and newer unknown: no Update button', rows().includes('skillsv.upd.unknown') && !rows().includes('data-act="updapply"') ? '' : rows().slice(-900));

// the other cards: no Update button for account skills and for your own
for (const [id, name] of [['account:-:acct', 'account'], ['user:-:mine', 'yours']]) {
  click({dataset: {sel: 'plugin:-:cav'}}); click({dataset: {sel: id}});
  test(`${name} skill: no Update button`, rows().includes('data-sel="' + id + '"') && !rows().includes('data-act="updcheck"') ? '' : rows().slice(-600));
}
click({dataset: {sel: 'account:-:acct'}}); click({dataset: {sel: 'added:-:cloned'}});
test('a repo skill says the repo', rows().includes('skillsv.from.repo{&quot;label&quot;:&quot;owner/name&quot;}') && rows().includes('data-act="updcheck"') ? '' : rows().slice(-600));

// derive from the conversation: source {chat:true}, a preview first
handlers.input.forEach(f => f({target: {id: 'skChatDesc', value: 'the build steps', dataset: {}}}));
click({dataset: {act: 'chatderive'}});
await wait();
const dv = calls.filter(c => c.action === 'derive');
test('derive from the conversation: source chat, the text, confirm false', dv.length === 1 && dv[0].source.chat === true && dv[0].desc === 'the build steps' && dv[0].confirm === false ? '' : JSON.stringify(dv));
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
