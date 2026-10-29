// The chatroom mod. Runs inside Claude Code, in the session that opened a room (the lead), where every subagent's
// tool call passes. It does three things:
// - tells the room's viewer what each room agent is doing (tool start and end, a permission it waits for), so the
//   3D office animates it at once; agents of other sessions or of no room are left alone;
// - writes the roster by itself: an agent spawned with a description that starts with a participant's name
//   ("FETTE: checks the parser") is that participant;
// - adds /stanza: a pane with the room (who works, who waits for you, the last messages, a box to write to all),
//   and toasts when someone tags you, a plan or a closing arrives, or an agent starts waiting for you;
// - hands a room agent (and the lead) the messages that tag it in the middle of its work: after each tool and before it
//   stops, one short line per message (never the whole chat), marked delivered (ROOM/delivered_NAME.txt).
// Rooms are found in ~/.claude/chatroom/rooms.json, which `chat.py serve` stamps every few seconds.
import type { Register } from 'claude-code'

type Room = { url: string; ts: number; ids: string[]; sessions?: string[]; participants: string[]; user: string; title: string; rtk?: string | null }
type Agent = { tool?: string | null; target?: string; since?: number | null; waiting?: number | null }
type Message = { n: number; from: string; text: string; kind?: string; ts?: number }
type Summary = {
  title: string; user: string; lang?: string; participants: string[]; heartbeat: number; n: number
  last: Message[]; idle: string[]; pct: Record<string, number>; state: { agents?: Record<string, Agent> }
}

const PANE = 'stanza'
const FIELDS = ['file_path', 'notebook_path', 'command', 'pattern', 'url', 'query', 'description', 'to']
let registry = ''
let sessionId = ''
let rooms: Record<string, Room> = {}
let paneOpen = false
const summaries = new Map<string, Summary>()
const seen = new Map<string, number>()
const waitingSeen = new Map<string, Set<string>>()

const roomOf = (id?: string) => (id ? Object.values(rooms).find(r => r.ids.includes(id)) : undefined)
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const startsWithName = (d: string, name: string) => new RegExp('^\\s*' + escapeRe(name) + '(?![\\w-])', 'i').test(d)
const oneLine = (s: string, n: number) => {
  const t = s.replace(/\s+/g, ' ').trim()
  return t.length > n ? t.slice(0, n - 1) + '…' : t
}
function pick(e: Record<string, unknown>) {
  const out: Record<string, string> = {}
  for (const k of FIELDS) if (typeof e[k] === 'string') out[k] = (e[k] as string).slice(0, 300)
  return out
}

// RTK for a room agent's shell command: `rtk rewrite` prints the shorter-output form (exit 0 or 3), or nothing (1: run it
// as it is), or a refusal (2 with a message). The rewrite calls `rtk` by name, so its folder goes first in PATH.
async function rtk($: any, exe: string, command: string): Promise<string | { deny: string }> {
  if (/(^|[^|])\|(?!\|)/.test(command)) return command   // inside a pipe rtk changes the output the next stage counts (grep -c gave 0)
  try {
    const r = await $.process.run([exe, 'rewrite', command], { timeoutMs: 5000 })
    const out = (r.stdout || '').trim()
    if ((r.exitCode === 0 || r.exitCode === 3) && out && out !== command) {
      const dir = exe.replace(/[\\/][^\\/]*$/, '').replace(/\\/g, '/').replace(/^([A-Za-z]):/, (_: string, d: string) => '/' + d.toLowerCase())
      return `export PATH="${dir}:$PATH" RTK_SUPPRESS_HOOK_WARNING=1; ${out}`   // its "run rtk init -g" is not for agents
    }
    if (r.exitCode === 2 && out) return { deny: out }
  } catch {
    // rtk missing or slow: the command runs as it is
  }
  return command
}

// a picture a room agent is about to read: the viewer hands back a copy at most 1000 px wide (thumbs.py), or the same path
async function thumb($: any, room: Room, path: string): Promise<string> {
  try {
    const r = await $.http.fetch(room.url + '/thumb', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }),
    })
    const p = r.ok ? JSON.parse(r.text).path : null
    return typeof p === 'string' && p ? p : path
  } catch {
    return path                                        // no viewer: the agent reads the original
  }
}

function send($: any, room: Room, ev: object) {
  void $.http.fetch(room.url + '/hook', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ev),
  }).catch(() => undefined)
}

// who spawned whom, as the engine knows it now (subagents and teammates, their status, their parent): the viewer draws the team from it
async function sendTeam($: any) {
  let agents: any[]
  try { agents = await $.agent.list() } catch { return }
  const team = agents.map(a => ({ id: a.id, name: String(a.teammateId || '').split('@')[0], type: a.type, status: a.status, parentId: a.parentId, description: a.description }))
  const ids = new Set(team.map(a => a.id))
  for (const room of Object.values(rooms)) {
    if (room.ids.some(i => ids.has(i)) || (sessionId && room.sessions?.includes(sessionId))) send($, room, { kind: 'team', agents: team })
  }
}

async function refresh($: any) {
  try {
    const now = Date.now() / 1000
    const all = JSON.parse(await $.fs.read(registry)) as Record<string, Room>
    rooms = Object.fromEntries(Object.entries(all).filter(([, r]) => now - r.ts < 60))
  } catch {
    rooms = {}
  }
  for (const [key, room] of Object.entries(rooms)) {
    try {
      const r = await $.http.fetch(room.url + '/summary.json')
      if (!r.ok) continue
      const s = JSON.parse(r.text) as Summary
      summaries.set(key, s)
      alerts($, key, s)
    } catch {
      // the room's server is gone: the registry drops it within a minute
    }
  }
  for (const key of [...summaries.keys()]) if (!rooms[key]) summaries.delete(key)
  await sendTeam($)
  if (paneOpen) $.ui.invalidate('ui.render')
}

function alerts($: any, key: string, s: Summary) {
  const it = s.lang !== 'en'
  const before = seen.get(key)
  seen.set(key, s.n)
  if (before !== undefined) {
    for (const m of s.last) {
      if (m.n <= before || m.kind || m.from === s.user) continue
      const tagged = new RegExp('@' + escapeRe(s.user) + '(?![\\w-])', 'i').test(m.text)
      if (tagged || /^\s*(PLAN|PIANO|CLOSED|CHIUSO)\b/i.test(m.text)) $.ui.toast(`💬 ${m.from}: ${oneLine(m.text, 90)}`)
    }
  }
  const agents = s.state.agents || {}
  const waiting = new Set(Object.keys(agents).filter(n => agents[n].waiting))
  const was = waitingSeen.get(key) || new Set<string>()
  waitingSeen.set(key, waiting)
  for (const n of waiting) {
    if (was.has(n)) continue
    const text = `🙋 ${n} ${it ? 'ti aspetta' : 'needs you'} (${s.title})`
    $.ui.toast(text)
    void $.ui.notify(text).catch(() => undefined)
  }
}

// Messages for an agent in the middle of its work. Who is who: a room agent by its agent id (the roster maps name to id),
// the lead's own session by its session id (sessions.json, written by chat.py). A message counts when it tags the agent
// (the lead also answers to the user's names), tags everyone, or comes from the user, and the agent neither read it
// (cursor_NAME.txt) nor was handed it (delivered_NAME.txt, which the monitor inbox.py writes too).
const names = new Map<string, { name: string; at: number }>()
const handed = new Map<string, number>()
const readText = async ($: any, path: string) => { try { return String(await $.fs.read(path)) } catch { return '' } }
const readInt = async ($: any, path: string) => parseInt(await readText($, path), 10) || 0
const tagsName = (text: string, who: string) => new RegExp('(?<![\\w@])@' + escapeRe(who) + '(?![\\w-])', 'i').test(text)

async function whoIs($: any, key: string, e: { agent_id?: string; session_id?: string }) {
  const id = e.agent_id || e.session_id || ''
  const hit = names.get(key + '|' + id)
  if (hit && (e.agent_id || Date.now() - hit.at < 30000)) return hit.name
  let name = ''
  try {
    if (e.agent_id) {
      const roster = JSON.parse(await readText($, key + '/roster.json') || '{}') as Record<string, string>
      name = Object.keys(roster).find(n => roster[n] === e.agent_id) || ''
    } else if (e.session_id) {
      name = (JSON.parse(await readText($, key + '/sessions.json') || '{}') as Record<string, string>)[e.session_id] || ''
    }
  } catch { /* an unreadable file: nobody */ }
  if (name) names.set(key + '|' + id, { name, at: Date.now() })
  return name
}

// every room of this agent or session: one session may lead several rooms, each with its own marks
async function inbox($: any, e: { agent_id?: string; session_id?: string }): Promise<string> {
  const keys = Object.entries(rooms).filter(([, r]) => (e.agent_id ? r.ids.includes(e.agent_id) : !!e.session_id && (r as any).sessions?.includes(e.session_id))).map(([k]) => k)
  const parts: string[] = []
  for (const key of keys) {
    const text = await inboxOf($, key, e)
    if (text) parts.push(keys.length > 1 ? text.replace(/^📨 /gm, `📨 [${summaries.get(key)?.title || key}] `) : text)
  }
  return parts.join('\n')
}

async function inboxOf($: any, key: string, e: { agent_id?: string; session_id?: string }): Promise<string> {
  const s = summaries.get(key)
  if (!s) return ''
  const name = await whoIs($, key, e)
  if (!name) return ''
  const mine = [name]
  if (!e.agent_id) {                                   // the lead answers to the user's names too
    try {
      const c = JSON.parse(await readText($, key + '/config.json') || '{}')
      mine.push(c.user_name, ...(c.user_aliases || []), ...(c.self_names || []))
    } catch { mine.push(s.user) }
  }
  const mark = handed.get(key + '|' + name) || 0
  const maybe = s.last.filter(m => m.n > mark && !m.kind && m.from !== name &&
    (m.from === s.user || /(?<![\w@])@(all|tutti|everyone)(?![\w-])/i.test(m.text) || mine.some(w => w && tagsName(m.text, w))))
  if (!maybe.length) return ''
  const seen = Math.max(mark, await readInt($, `${key}/cursor_${name}.txt`), await readInt($, `${key}/delivered_${name}.txt`))
  const fresh = maybe.filter(m => m.n > seen)
  const top = Math.max(...maybe.map(m => m.n))
  handed.set(key + '|' + name, top)
  if (!fresh.length) return ''
  const now = Math.max(top, await readInt($, `${key}/delivered_${name}.txt`))       // monotone, as chat.py delivered
  await $.fs.write(`${key}/delivered_${name}.txt`, String(now)).catch(() => undefined)
  const it = s.lang !== 'en'
  const shown = fresh.slice(-3).map(m => `📨 #${m.n} ${it ? 'da' : 'from'} ${m.from}: ${oneLine(m.text, 160)}`)
  if (fresh.length > 3) shown.unshift(`📨 (+${fresh.length - 3} ${it ? 'più vecchi: chat_read' : 'older: chat_read'})`)
  return shown.join('\n')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const dir = (await $.env.get('CLAUDE_CONFIG_DIR'))
      || `${(await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || ''}/.claude`
    registry = `${dir}/chatroom/rooms.json`
    sessionId = (await $.env.get('CLAUDE_CODE_SESSION_ID')) || ''
    await $.command.register({
      name: 'stanza', immediate: true,
      description: 'Show the open chatroom: who works, who waits for you, the last messages, a box to write to all',
    })
    $.clock.every(3000, () => refresh($))
    void refresh($)
    return next(e)
  })

  on('command.run', { command: 'stanza' }, async $ => {
    paneOpen = true
    await refresh($)
    await $.ui.open({ id: PANE, title: 'Stanza', focus: true, closeOnEscape: true })
    return {}
  })

  on('ui.close', async ($, e, next) => {
    if (e.id === PANE) paneOpen = false
    return next(e)
  }).catch(($, e, next) => next(e))          // fail open: a fault here never blocks the session

  // what each room agent does, at once: tool start and end
  on('tool.call', async ($, e, next) => {
    const room = roomOf(e.agentId)
    if (!room) return next(e)
    const file = (e as any).file_path
    if (e.tool === 'Read' && typeof file === 'string' && /\.(png|jpe?g|gif|webp)$/i.test(file)) {
      const small = await thumb($, room, file)           // each picture stays in the context, read again at every turn
      if (small !== file) e = { ...e, file_path: small } as typeof e
    }
    if (e.tool === 'Bash' && room.rtk && typeof (e as any).command === 'string') {
      const rewritten = await rtk($, room.rtk, (e as any).command)
      if (typeof rewritten !== 'string') return rewritten
      if (rewritten !== (e as any).command) e = { ...e, command: rewritten } as typeof e
    }
    const id = e.tool_use_id || `${e.agentId}-${Date.now()}`
    send($, room, { kind: 'tool', agentId: e.agentId, id, tool: e.tool, input: pick(e as Record<string, unknown>) })
    let ok = false
    try {
      const ran = await next(e)
      ok = ran.deny === undefined && !ran.isError
      return ran
    } finally {
      send($, room, { kind: 'done', agentId: e.agentId, id, ok })
    }
  }).catch(($, e, next) => next(e))          // fail open: a fault here never blocks the session

  // a permission prompt: only one the person is really shown. In auto mode most calls pass through an 'ask' that the
  // mode then approves by itself, and a long call (a chat wait, a test run) must not look like a wait for the user.
  on('classic.PermissionRequest', async ($, e, next) => {
    const room = roomOf(e.agent_id)
    if (room && e.agent_id) send($, room, { kind: 'ask', agentId: e.agent_id })
    return next(e)
  }).catch(($, e, next) => next(e))          // fail open: a fault here never blocks the session

  // a message in the middle of the work: after each tool, and before the agent (or the lead) stops
  on('classic.PostToolUse', async ($, e, next) => {
    const out = await next(e)
    const text = await inbox($, e as any)
    return text ? { ...out, additionalContext: [...(out.additionalContext || []), text] } : out
  }).catch(($, e, next) => next(e))          // fail open: a fault here never blocks the session
  // the engine wants each event name written out at its on() call: no loop over names
  on('classic.Stop', async ($, e, next) => {
    const out = await next(e)
    const text = await inbox($, e as any)
    return text && !out.block ? { ...out, block: text } : out
  }).catch(($, e, next) => next(e))          // fail open: a fault here never blocks the session
  on('classic.SubagentStop', async ($, e, next) => {
    const out = await next(e)
    const text = await inbox($, e as any)
    return text && !out.block ? { ...out, block: text } : out
  }).catch(($, e, next) => next(e))

  // the roster writes itself
  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    if (started.deny === undefined && started.agentId) {
      // who spawned whom: the parent's id (absent: the lead's own session), a named teammate, the kind of agent
      const ev = { agentId: started.agentId, description: e.description, parentAgentId: e.parentAgentId, isTeammate: !!e.isTeammate,
                   name: e.name, subagentType: e.subagentType, toolUseId: e.tool_use_id }
      for (const room of Object.values(rooms)) {
        if (room.participants.some(n => startsWithName(e.description, n))) {
          room.ids.push(started.agentId)
          send($, room, { kind: 'spawn', ...ev })
        } else if (e.parentAgentId && room.ids.includes(e.parentAgentId)) {      // a subagent of a room agent: drawn around its parent
          send($, room, { kind: 'child', ...ev })
        }
      }
    }
    return started
  }).catch(($, e, next) => next(e))          // fail open: a fault here never blocks the session

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Input } = $.ui.resolve(e)
    const width = Math.max(40, (e.props.bodyColumns ?? 80) - 2)
    const list = [...summaries.entries()]
    if (!list.length) {
      return Text({ dimColor: true, children: ['No open chatroom: start one with /chatroom:start, or run chat.py serve.'] })
    }
    const children: unknown[] = []
    for (const [key, s] of list) {
      const it = s.lang !== 'en', agents = s.state.agents || {}, room = rooms[key]
      const waiting = s.participants.filter(n => agents[n]?.waiting)
      children.push(Box({
        flexDirection: 'row', columnGap: 2, children: [
          Text({ bold: true, children: [`🏢 ${s.title}`] }),
          Text({ dimColor: true, children: [room ? room.url : ''] }),
          waiting.length ? Text({ color: 'red', bold: true, children: [`🙋 ${waiting.length} ${it ? 'ti aspettano' : 'need you'}`] }) : Text({ children: [''] }),
        ],
      }))
      for (const n of s.participants) {
        const a = agents[n] || {}, idle = s.idle.includes(n), pct = s.pct[n]
        const icon = a.waiting ? '🙋' : idle ? '💤' : a.tool ? '⚙️' : '·'
        const doing = a.waiting ? (it ? 'TI ASPETTA: ' : 'NEEDS YOU: ') + `${a.tool || ''} ${a.target || ''}`
          : idle ? 'idle' : a.tool ? `${a.tool} ${a.target || ''}` : ''
        children.push(Text({
          color: a.waiting ? 'red' : undefined, dimColor: idle,
          children: [oneLine(`${icon} ${n.padEnd(10)} ${pct === undefined ? '  —' : String(pct).padStart(3) + '%'}  ${doing}`, width)],
        }))
      }
      children.push(Text({ dimColor: true, children: [it ? '— ultimi messaggi' : '— last messages'] }))
      for (const m of s.last.filter(x => !x.kind).slice(-6)) {
        children.push(Text({ color: m.from === s.user ? 'magenta' : undefined, children: [oneLine(`#${m.n} ${m.from}: ${m.text}`, width)] }))
      }
      if (room) {
        children.push(Input({
          key: 'say-' + key, label: it ? `Scrivi a tutti come ${s.user}` : `Write to all as ${s.user}`, value: '',
          placeholder: it ? '@NOME per taggare' : '@NAME to tag', submitLabel: it ? 'invia' : 'send',
          onSubmit: async (value: string) => {
            if (!value.trim()) return
            await $.http.fetch(room.url + '/post', {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: value.trim() }),
            })
            await refresh($)
          },
        }))
      }
    }
    return Box({ flexDirection: 'column', children })
  })
}
