// 0.19.9 B6: the mod's inbox does not hand the lead again what its relay or another of its names already took in
// node --experimental-strip-types test_0199_b_mod.mjs   (CHATROOM_SCRIPTS = the scripts folder, default: this file's parent)
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SCRIPTS = (process.env.CHATROOM_SCRIPTS || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')).replace(/\\/g, '/')
const { register } = await import(pathToFileURL(SCRIPTS.replace(/scripts\/?$/, 'hooks/register.ts')).href)
const hooks = {}
register((ev, a, b) => { hooks[ev] = b || a; return { catch: () => undefined } })

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'mod0199b_'))
const ROOM = path.join(tmp, 'room').replace(/\\/g, '/'); fs.mkdirSync(ROOM)
const REG = path.join(tmp, 'chatroom', 'rooms.json'); fs.mkdirSync(path.dirname(REG), { recursive: true })
const w = (f, t) => fs.writeFileSync(path.join(ROOM, f), t)
w('roster.json', JSON.stringify({ A: 'a1' }))
w('config.json', JSON.stringify({ user_name: 'USER', self_names: ['LEAD', 'COORDINATOR'], participants: ['A'] }))
w('sessions.json', JSON.stringify({ 'sid-lead': 'LEAD' }))
const msgs = []
const say = (from, text) => { msgs.push({ n: msgs.length + 1, from, text }); return msgs.length }
const stamp = () => fs.writeFileSync(REG, JSON.stringify({ [ROOM]: { url: 'http://x', ts: Date.now() / 1000, ids: ['a1'], sessions: ['sid-lead'], participants: ['A'], user: 'USER', title: 't' } }))
stamp()
const $ = {
  env: { get: async () => tmp },
  command: { register: async () => undefined },
  clock: { every: () => undefined },
  fs: { read: async p => fs.readFileSync(p, 'utf8'), write: async (p, t) => fs.writeFileSync(p, t) },
  http: { fetch: async (url, init) => init?.method === 'POST' ? { ok: true, text: '{}' } : ({ ok: true, text: JSON.stringify({ title: 't', user: 'USER', lang: 'it', participants: ['A'], heartbeat: 120, n: msgs.length, last: msgs.slice(-12), idle: [], pct: {}, state: {} }) }) },
  agent: { list: async () => [] },
  ui: { invalidate: () => undefined, toast: () => undefined, notify: async () => undefined },
}
await hooks['session.start']($, {}, async () => ({}))
const refresh = async () => { stamp(); await hooks['session.start']($, {}, async () => ({})); await new Promise(r => setTimeout(r, 30)) }
let fails = 0
const ok = (name, cond, info) => { console.log((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : '  [' + JSON.stringify(info) + ']')); if (!cond) fails++ }
const lead = async () => (await hooks['classic.PostToolUse']($, { session_id: 'sid-lead' }, async () => ({}))).additionalContext?.join('\n') || ''

// a lead whose relay took the message in (its own cursor) and whose delivered mark is empty or missing: nothing again
say('A', '@LEAD one')
w('cursor__alerts_LEAD.txt', '1')
w('delivered_LEAD.txt', '')
await refresh()
let got = await lead()
ok('the relay cursor holds when the delivered mark reads as 0', got === '', got)
// what the lead read under another of its names
say('A', '@LEAD two')
w('cursor_COORDINATOR.txt', '2')
await refresh()
got = await lead()
ok('a message read under another name of the lead is not handed', got === '', got)
// control: a newer one still arrives
say('A', '@LEAD three')
await refresh()
got = await lead()
ok('a newer message still arrives', /#3 da A: @LEAD three/.test(got), got)
console.log(fails ? 'FAIL ' + fails : 'mod 0199 b ok')
fs.rmSync(tmp, { recursive: true, force: true })
process.exit(fails ? 1 : 0)
