// The Skills view (0.19, D8): verification (check, verified), usage, measured, levels, activation, cases. Contract: scratch/CORE/skills.d8.contract.md
// node plugins/chatroom/scripts/tools/test_skills_d8.mjs
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const S = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let passed = 0, total = 0;
const test = (name, bad) => { total++; if (bad) console.log(`FAIL ${name}: ${bad}`); else { passed++; console.log(`PASS ${name}`); } };

const V = (state, at = null, exit = null) => ({state, ok: state === 'verified', at, exit, hash: 'ab12cd34ef56', skill_hash: '0123456789ab'});
const CK = cmd => ({cmd, cwd: null, timeout: 110});
const sk = (name, extra = {}) => ({id: `user:-:${name}`, name, brief: name + ' brief', description: name + ' d', origin: 'user', plugin: null, version: null, path: '/x/' + name, advised: [], agents: [], updatable: false,
  check: null, verified: V('unverified'), level: null, parent: null, children: [], cases: [], measured: null, activation: null, usage: {count: 0, rooms: 0, last: null, ok: 0, fail: 0, unused_rooms: 0, scanned_rooms: 0, unused: false, log: []}, ...extra});
const cand = (name, extra = {}) => ({id: `cand:r1:${name}`, room: 'r1', name, score: 7, kind: 'derive', tasks: [], at: 1, req: 'r1', status: 'new', improves: null, covered_by: null, tokens: 100, tokens_saved: null, why: 'why ' + name,
  criteria: {}, repeated: [], hard: [], check: null, verified: V('unverified'), level: null, parent: null, children: [], cases: [], measured: null, activation: null, usage: {count: 0}, ...extra});
const DATA = {v: 1, origins: ['user'], skills: [sk('good', {check: CK('pytest -q'), verified: V('verified', 1700000000, 0)}), sk('bad', {check: CK('make <test>'), verified: V('failed', 1700000000, 2)}), sk('b-func', {level: 'function', parent: 'user:-:a-strat'}), sk('a-strat', {level: 'strategy', children: ['user:-:b-func']}), sk('cyc1', {parent: 'user:-:cyc2'}), sk('cyc2', {parent: 'user:-:cyc1'}), sk('plain'), sk('idle', {usage: {count: 0, rooms: 0, last: null, ok: 0, fail: 0, unused_rooms: 4, scanned_rooms: 4, unused: true, log: []}}),
  sk('busy', {usage: {count: 5, rooms: 2, last: 1700000000, ok: 3, fail: 2, unused_rooms: 0, scanned_rooms: 4, unused: false, log: [{room: 'r<1>', agent: 'UI', task: 'T3', ok: true, at: 1700000000}, {room: 'r2', agent: 'CORE', task: null, ok: null, at: 1700000000}]},
    measured: {tokens_saved: 2400, steps_saved: -1, basis: 'tasks <with> against without', with: {n: 5}, without: {n: 8}, min_n: 3, at: 1}, activation: {right: 4, wrong: 2, total: 6, at: 1700000000, suggestion: 'Do <NOT> use'}, cases: [{id: 'c1', task: 'merge <two>', check: CK('t1.py')}, {id: 'c2', task: 'keep marks', check: CK('t2.py')}]})],
  agents: [], searcher: {present: true, name: 'S', busy: false}, requests: [], rooms: [{id: 'r1', name: 'room', current: true, n: 2}],
  candidates: [cand('c-imp', {improves: 'user:-:plain', check: CK('t.py'), verified: V('verified', 1, 0), cases: [{id: 'c1', task: 'first <b>', check: CK('a.py')}, {id: 'c2', task: 'second', check: CK('b.py')}]}), cand('c-checked', {check: CK('python t.py'), verified: V('verified', 1700000000, 0)}), cand('c-plain')]};
const els = {}, calls = [], handlers = {};
let TAB = 'explore', SEL = 'user:-:good', ANS = {};
const el = id => (els[id] ??= {id, innerHTML: '', textContent: '', value: '', style: {}, classList: {toggle() {}, add() {}, remove() {}}, querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, insertAdjacentElement() {}, focus() {}});
const mk = () => ({classList: {toggle() {}, add() {}, remove() {}}, style: {}, querySelector: () => null, querySelectorAll: () => [], appendChild() {}, offsetWidth: 0, insertAdjacentElement() {},
  addEventListener(t, f) { (handlers[t] ??= []).push(f); }, set innerHTML(v) {}, get innerHTML() { return ''; }});
globalThis.window = globalThis;
globalThis.CSS = {escape: s => s};
globalThis.document = {createElement: mk, getElementById: id => (id === 'officeBtn' ? null : el(id)), head: {appendChild() {}}, body: {appendChild() {}, classList: {toggle() {}}}, hidden: false, activeElement: null};
globalThis.location = {search: '', href: 'http://x/'};
globalThis.history = {replaceState() {}};
globalThis.localStorage = {getItem: () => JSON.stringify({tab: TAB, sel: SEL}), setItem() {}};
globalThis.addEventListener = () => {};
globalThis.setInterval = () => 0;
globalThis.I18N = {text: (k, f) => k + (f ? JSON.stringify(f) : '')};
globalThis.fetch = async (url, o) => {
  if (url === 'skills.json') return {ok: true, json: async () => DATA};
  const b = JSON.parse(o.body); calls.push(b);
  const j = ANS[b.action] ? ANS[b.action](b) : {ok: true};
  return {ok: true, text: async () => JSON.stringify(j)};
};
await import(pathToFileURL(path.join(S, 'skills-view.js')).href);
globalThis.skillsView.open(true);
await new Promise(r => setTimeout(r, 50));
const rows = () => els.skRows.innerHTML, crows = () => els.skCandRows.innerHTML, modal = () => els.skModal.innerHTML;
const click = t => handlers.click.forEach(f => f({target: {classList: {contains: () => false}, closest: () => t}}));
const wait = () => new Promise(r => setTimeout(r, 20));
const last = a => calls.filter(c => c.action === a).at(-1);

// ---- 1 check, verified
test('a skill with a passing check says Verified', rows().includes('skillsv.ver.ok') ? '' : rows().slice(0, 600));
test('a failed check shows as such, a skill without a check shows nothing', rows().includes('skillsv.ver.failed') && !/data-sel="user:-:plain"[\s\S]{0,400}skillsv\.ver\./.test(rows()) ? '' : rows().slice(0, 1500));
test('the opened card shows the command whole (escaped) and the Run button', rows().includes('pytest -q') && rows().includes('data-act="chkrun"') ? '' : rows().slice(-800));
click({dataset: {sel: 'user:-:good'}}); click({dataset: {sel: 'user:-:bad'}});
test('the command is escaped', rows().includes('make &lt;test&gt;') ? '' : rows().slice(-800));
ANS.check_run = b => b.confirm ? {ok: true, passed: false, exit: 2, out: 'boom <x>', hash: 'h', at: 1700000100, verified: V('failed', 1700000100, 2)} : {ok: true, preview: {name: 'bad', what: 'skill', cmd: 'make <test>', cwd: '/x/bad', timeout: 110, note: 'runs on your computer'}};
click({dataset: {act: 'chkrun', cid: 'user:-:bad'}});
await wait();
test('Run check asks for a preview first (confirm false, the id only: the command is never sent)', last('check_run') && last('check_run').confirm === false && last('check_run').skill === 'user:-:bad' && !('cmd' in last('check_run')) ? '' : JSON.stringify(calls));
test('the modal shows the whole command and the folder', modal().includes('make &lt;test&gt;') && modal().includes('/x/bad') && modal().includes('data-act="mconfirm"') ? '' : modal());
click({dataset: {act: 'mconfirm'}});
await wait();
test('confirm runs it (confirm true) and shows what it printed', last('check_run').confirm === true && rows().includes('boom &lt;x&gt;') ? '' : rows().slice(-600));

click({dataset: {tab: 'cand'}});
await wait();
test('candidates: Verified / Not verified always shown', crows().includes('skillsv.ver.ok') && crows().includes('skillsv.ver.not') ? '' : crows().slice(0, 900));
ANS.promote = b => b.confirm ? (b.unverified_ok ? {ok: true} : {ok: false, needs: 'unverified_ok'}) : {ok: true, preview: {unverified: true, name: 'c-plain', from: 'a', to: 'b'}};
click({dataset: {act: 'cpromote', cid: 'cand:r1:c-plain'}});
await wait();
test('an unverified candidate: the modal says so and the button says "not verified"', modal().includes('skillsv.ver.unverNote') && modal().includes('skillsv.ver.addUnver') ? '' : modal());
click({dataset: {act: 'mconfirm'}});
await wait();
test('confirm sends unverified_ok', last('promote').confirm === true && last('promote').unverified_ok === true ? '' : JSON.stringify(last('promote')));
ANS.promote = b => b.confirm ? {ok: true} : {ok: true, preview: {unverified: false, name: 'c-checked', from: 'a', to: 'b'}};
click({dataset: {act: 'cpromote', cid: 'cand:r1:c-checked'}});
await wait();
click({dataset: {act: 'mconfirm'}});
await wait();
test('a verified candidate is added without unverified_ok', last('promote').confirm === true && !('unverified_ok' in last('promote')) && !modal().includes('unverNote') ? '' : JSON.stringify(last('promote')));

// ---- 3 usage
click({dataset: {tab: 'explore'}});
await wait();
test('a never-used skill carries the tag, and the filter chip counts them', rows().includes('skillsv.use.tag') && els.skChips.innerHTML.includes('data-act="unusedf"') && els.skChips.innerHTML.includes('skillsv.use.filter') ? '' : els.skChips.innerHTML);
click({dataset: {act: 'unusedf'}});
test('the filter keeps only the never-used skills and the help line says it is a hint', rows().includes('data-sel="user:-:idle"') && !rows().includes('data-sel="user:-:busy"') && els.skHelp.textContent === 'skillsv.use.help' ? '' : rows().slice(0, 300));
click({dataset: {act: 'unusedf'}});
click({dataset: {sel: 'user:-:busy'}});
test('an opened card shows the count, the outcomes and the log (escaped)', rows().includes('skillsv.use.count{&quot;n&quot;:5,&quot;rooms&quot;:2}') && rows().includes('r&lt;1&gt; · T3 · UI') && rows().includes('skillsv.use.noTask') ? '' : rows().slice(-900));
ANS.usage_scan = () => ({ok: true, scanned: {rooms: 3, transcripts: 9, new: 2}, complete: false});
click({dataset: {act: 'usescan'}});
await wait();
test('Count the use = usage_scan (reads only: no confirm), and says when it is not finished', last('usage_scan') && !last('usage_scan').confirm && rows().includes('skillsv.use.scanMore') ? '' : JSON.stringify(last('usage_scan')) + rows().slice(-300));
click({dataset: {sel: 'user:-:busy'}}); click({dataset: {sel: 'user:-:idle'}});
test('an unused skill says so and that nothing is removed on its own', rows().includes('skillsv.use.never{&quot;n&quot;:4}') && rows().includes('skillsv.use.unusedNote') && !/data-act="[a-z]*remove/.test(rows()) ? '' : rows().slice(-600));
// ---- 2 measured
click({dataset: {sel: 'user:-:idle'}}); click({dataset: {sel: 'user:-:busy'}});
test('a measured saving shows tokens and steps (a negative one says it costs), the task counts, the basis escaped', /skillsv\.meas\.saves\{&quot;n&quot;:&quot;2.?400&quot;\}/.test(rows()) && rows().includes('skillsv.meas.more{&quot;n&quot;:&quot;1&quot;}') && rows().includes('skillsv.meas.on{&quot;a&quot;:5,&quot;b&quot;:8}') && rows().includes('tasks &lt;with&gt; against without') ? '' : rows().slice(-900));
click({dataset: {sel: 'user:-:busy'}}); click({dataset: {sel: 'user:-:plain'}});
test('no measure = "not measured yet", never a number', rows().includes('skillsv.meas.none') && !rows().includes('skillsv.meas.saves') ? '' : rows().slice(-500));
ANS.measure = () => ({ok: true, measured: null});
click({dataset: {act: 'measure'}});
await wait();
test('Measure = {action measure, id}, reads only (no confirm)', last('measure') && last('measure').id === 'user:-:plain' && !last('measure').confirm ? '' : JSON.stringify(last('measure')));
// ---- 5 levels
click({dataset: {sel: 'user:-:busy'}});
const R = rows(), ia = R.indexOf('data-sel="user:-:a-strat"'), ib = R.indexOf('data-sel="user:-:b-func"');
test('a tree: the parent first, the child right under it, indented, with the level named', ia > 0 && ib > ia && /sk-child[^>]*--dep:1[^>]*>\s*<div class="sk-hd" data-sel="user:-:b-func"/.test(R) && R.includes('skillsv.lv.strategy') && R.includes('skillsv.lv.function') ? '' : R.slice(0, 900));
test('a cycle never hides a card', R.includes('data-sel="user:-:cyc1"') && R.includes('data-sel="user:-:cyc2"') ? '' : 'cycle cards missing');
click({dataset: {sel: 'user:-:a-strat'}});
test('the opened card lists its children and has the level controls', rows().includes('data-goto="user:-:b-func"') && rows().includes('id="skLv"') && rows().includes('data-act="lvset"') ? '' : rows().slice(-700));
els.skLv = {value: 'step'}; els.skPar = {value: 'user:-:b-func'};
click({dataset: {act: 'lvset'}});
await wait();
test('Save = level_set {id, level, parent}, metadata only (no confirm)', last('level_set') && last('level_set').id === 'user:-:a-strat' && last('level_set').level === 'step' && last('level_set').parent === 'user:-:b-func' && !last('level_set').confirm ? '' : JSON.stringify(last('level_set')));
// ---- 4 activation
click({dataset: {sel: 'user:-:a-strat'}}); click({dataset: {sel: 'user:-:busy'}});
test('the model test result: right of total, wrong, the better description (escaped)', rows().includes('skillsv.act.right{&quot;a&quot;:4,&quot;t&quot;:6}') && rows().includes('skillsv.act.wrong{&quot;n&quot;:2}') && rows().includes('Do &lt;NOT&gt; use') ? '' : rows().slice(-900));
ANS.activation_check = () => ({ok: true, check: {positives: 2, negatives: 0, has_exclusion: false, closeness: 0.31, advice: 'add <b>a clause</b>', suggestion: 'Do NOT use for x', confused_with: [{id: 'user:-:plain', name: 'plain', overlap: 0.4}]}});
click({dataset: {act: 'actcheck'}});
await wait();
test('free check = activation_check {id}, no confirm; shows counts, the missing exclusion, the advice escaped, who it is confused with', last('activation_check') && last('activation_check').id === 'user:-:busy' && !last('activation_check').confirm
  && rows().includes('skillsv.act.noExcl') && rows().includes('add &lt;b&gt;a clause&lt;/b&gt;') && rows().includes('data-goto="user:-:plain"') && rows().includes('31%') ? '' : rows().slice(-1200));
ANS.activation_test = b => b.confirm ? {ok: true, req: 'r9'} : {ok: true, preview: {kind: 'activation', name: 'SKILLWORK', task: 'write 6 requests', prompts: [], n: 6, reads: ['every description'], writes: ['skills-jobs/r9.json'], budget_usd: 1, note: 'a <b>simulation</b> from the descriptions'}};
click({dataset: {act: 'acttest'}});
await wait();
test('model test asks first: the modal shows the cost cap (budget) and the note of the server (a simulation, escaped) and nothing was started', last('activation_test').confirm === false && modal().includes('skillsv.cand.usd{&quot;n&quot;:1}') && modal().includes('a &lt;b&gt;simulation&lt;/b&gt; from the descriptions') && modal().includes('skillsv.act.testNote') ? '' : modal());
click({dataset: {act: 'mconfirm'}});
await wait();
test('confirm starts it (confirm true) and closes the modal', last('activation_test').confirm === true && modal() === '' ? '' : JSON.stringify(last('activation_test')) + modal().slice(0, 100));
// ---- 6 cases
globalThis.skillsView.open(true);
click({dataset: {tab: 'explore'}}); click({dataset: {sel: 'user:-:a-strat'}}); click({dataset: {sel: 'user:-:busy'}});
await wait();
test('cases are listed with id, task (escaped) and the command whole, and there is a form to add one', rows().includes('merge &lt;two&gt;') && rows().includes('t2.py') && rows().includes('id="skCaseTask"') && rows().includes('data-act="casesrun"') ? '' : rows().slice(-1200));
els.skCaseTask = {value: ''}; els.skCaseCmd = {value: ''};
const nSet = calls.filter(c => c.action === 'cases_set').length;
click({dataset: {act: 'caseadd', cid: 'user:-:busy'}});
await wait();
test('the cases section appears once in a skill', rows().split('id="skCaseTask"').length === 2 ? '' : 'twice');
test('the opened card has four tiles (check, use, saving, activation)', rows().split('class="sk-tile ').length === 5 ? '' : 'tiles');
test('an empty case is not sent', calls.filter(c => c.action === 'cases_set').length === nSet ? '' : 'sent');
els.skCaseTask = {value: ' third task '}; els.skCaseCmd = {value: 'pytest t3'};
click({dataset: {act: 'caseadd', cid: 'user:-:busy'}});
await wait();
const cs3 = last('cases_set');
test('Add = cases_set with the old cases and the new one (the command stored, nothing runs, no confirm)', cs3 && cs3.id === 'user:-:busy' && cs3.cases.length === 3 && cs3.cases[2].task === 'third task' && cs3.cases[2].check.cmd === 'pytest t3' && !cs3.confirm ? '' : JSON.stringify(cs3));
click({dataset: {act: 'casedel', cid: 'user:-:busy', i: '0'}});
await wait();
test('Remove = cases_set without that case', last('cases_set').cases.length === 1 && last('cases_set').cases[0].task === 'keep marks' ? '' : JSON.stringify(last('cases_set')));
ANS.cases_run = b => b.confirm ? {ok: true, results: [{id: 'c1', passed: true, exit: 0}, {id: 'c2', passed: false, exit: 1}], at: 1} : {ok: true, preview: {name: 'busy', cases: [{id: 'c1', check: CK('t1.py')}, {id: 'c2', check: CK('t2.py')}], cwd: '/x', timeout: 110, token: 'tk9'}};
click({dataset: {act: 'casesrun', cid: 'user:-:busy'}});
await wait();
test('Run the cases asks first and lists every command', last('cases_run').confirm === false && modal().includes('t1.py') && modal().includes('t2.py') && modal().includes('skillsv.cases.runNote{&quot;n&quot;:2}') ? '' : modal());
click({dataset: {act: 'mconfirm'}});
await wait();
await wait(); await wait();
test('the confirm sends back the preview token', last('cases_run').token === 'tk9' ? '' : JSON.stringify(last('cases_run')));
test('confirm runs them and shows passed / failed per case', last('cases_run').confirm === true && rows().includes('skillsv.cases.pass') && rows().includes('skillsv.cases.fail') ? '' : rows().slice(-1500));

click({dataset: {tab: 'cand'}});
await wait();
ANS.promote = b => b.confirm ? {ok: false, reverted: true, error: 'case c2 got worse', cases_result: [{id: 'c1', before: false, after: true}, {id: 'c2', before: true, after: false}], better: 1, worse: 1}
  : {ok: true, preview: {unverified: false, name: 'c-imp', from: 'a', to: 'b', replaces: true, gate: [{id: 'c1', cmd: 'a.py'}, {id: 'c2', cmd: 'b.py'}, {id: 'check', cmd: 't.py'}], runs: 5}};
click({dataset: {act: 'cpromote', cid: 'cand:r1:c-imp'}});
await wait();
test('an improvement with cases: the modal lists the gate commands (cmd, not [object Object]) and the runs the server counts', !modal().includes('[object') && modal().includes('a.py') && modal().includes('t.py') && modal().includes('skillsv.cases.gateNote{&quot;n&quot;:5}') ? '' : modal());
click({dataset: {act: 'mconfirm'}});
await wait();
test('a refused improvement (reverted): says the old version is back, marks the worse case, shows the counts and the informative utility', modal().includes('skillsv.cases.refused') && modal().includes('class="bad"') && modal().includes('skillsv.cases.worse{&quot;n&quot;:1}') && modal().includes('skillsv.cases.utility{&quot;n&quot;:&quot;+0.00&quot;}') && modal().includes('skillsv.cases.revertNote') && modal().includes('first &lt;b&gt;') ? '' : modal());
click({dataset: {act: 'mclose'}});
ANS.promote = b => b.confirm ? {ok: true, cases_result: [{id: 'c1', before: false, after: true}, {id: 'c2', before: true, after: true}], better: 1, worse: 0} : {ok: true, preview: {unverified: false, name: 'c-imp', gate: ['a.py']}};
click({dataset: {act: 'cpromote', cid: 'cand:r1:c-imp'}});
await wait();
click({dataset: {act: 'mconfirm'}});
await wait();
test('a kept improvement: says applied, no bad row, utility +0.50 (mean of the deltas)', modal().includes('skillsv.cases.kept') && !modal().includes('class="bad"') && modal().includes('+0.50') ? '' : modal());
globalThis.skillsView.show('user:-:a-strat');
await wait(); await wait();
test('skillsView.show(id) opens the panel on that skill', rows().includes('aria-expanded="true"') && /data-sel="user:-:a-strat"[^>]*aria-expanded="true"/.test(rows()) ? '' : rows().slice(0, 400));
const SRC = fs.readFileSync(path.join(S, 'skills-view.js'), 'utf8');
test('the panel root is not faded in (opaque from the first frame; the chat must not show through)', !/#skillsView\s*\{\s*animation:/.test(SRC) && !SRC.includes('@keyframes sk-open') ? '' : 'root animation');
console.log(`${passed}/${total} passed`);
process.exit(passed === total ? 0 : 1);
