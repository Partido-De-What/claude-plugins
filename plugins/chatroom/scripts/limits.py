"""The limits of the harness the room lives in, in one place, checked at import. Each number the room picks (how long a
wait blocks, how long the SubagentStop hook holds an agent) must stay under a limit of Claude Code or of the prompt
cache; on 30/10 a hold of 50 minutes passed the 600 s stall watchdog and killed the agents it held. A change here that
breaks one of these rules fails at the first import, in every test."""

WATCHDOG = 600                 # Claude Code declares a subagent stalled after 600 s without progress, and kills it
SHELL_MAX = 600                # the longest timeout of one shell call (Bash tool)
MONITOR_MAX = 1800             # the Monitor tool ends after 30 minutes at most
CACHE_5M, CACHE_1H = 300, 3600 # prompt cache lifetimes: subagents 5 minutes, chatroom:room-agent 1 hour

WAIT_MAX = 110                 # a wait while working
IDLE_WAIT = 270                # a wait while idle, 5-minute cache: a wake reads the cache instead of writing it again
IDLE_WAIT_LONG = 540           # the same with the 1-hour cache: half the wakes
HOLD_WAIT = 540                # the SubagentStop hook holds a stopped agent this long, then lets one short turn through
HOLD_TIMEOUT = 590             # its timeout in hooks.json: the hook ends before the watchdog in every case

assert IDLE_WAIT + 10 < CACHE_5M
assert IDLE_WAIT_LONG + 30 < SHELL_MAX and IDLE_WAIT_LONG < CACHE_1H
assert HOLD_WAIT + 30 <= HOLD_TIMEOUT < WATCHDOG
assert WAIT_MAX < IDLE_WAIT
