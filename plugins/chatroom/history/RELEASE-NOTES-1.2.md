# chatroom 1.2

## Why this release

Two production rooms of my social media work, run in the desktop app, measured where the tokens go. Every agent started at 68k tokens of context before doing anything, the chat messages themselves weighed almost nothing, and what cost was the number of requests: each one reads the whole context again. Half of the lead's wakes came from checks that were wrong, and an agent that wrote "I wait for your ok" walked away four times.

## Fewer false alarms

- In the desktop app the type of an agent was never recorded, so the room took its agents for plain subagents and asked to rotate them at 150k tokens instead of 350k. A participant with no type recorded is now a room agent, and the roster hook records the type when Claude Code gives it.
- An agent that ends with nothing in hand has finished its job: it is no longer counted as a failure, and no false lesson is proposed at the closing.
- The cost table keeps the agents that already left the room.

## Agents that wait, and say it once

- "I wait for your ok" to the lead, with or without a question mark, keeps the agent until the lead answers.
- `post --wait-for LEAD` (or `wait_for` in the chat tool) posts a delivery and waits for the answer in one call: no extra status to quiet the timer, no agent resumed by hand.
- A post refused because another message crossed it goes again with `post --resend`, without writing it twice. An order of the lead is no longer held back by an agent's report that crossed it: the report is shown after.
- After a post, the confirmation is the last line, and the reminder about a stopped relay comes once in half an hour.

## Lighter on tokens

- `prompt NAME --out FILE --stub` prints three lines to give the agent ("read this file and follow it"), so an 18k-character prompt never passes through the lead's context.
- A message that tags the lead reaches it whole, up to 800 characters, so it does not have to read it again.
- A structured status keeps the agent's notebook state current by itself.
- `brief mode=deliveries` is for rooms where nobody discusses: each agent delivers a file, closes its task and ends, without plans, votes or the rules about them in its prompt.
- Two new agent types: `room-agent-lean`, with only files, shell, web and the chat, which compacts near 170k; `room-agent-short`, with a five-minute cache, for one run that waits for nobody.
- Long shell outputs are trimmed from 16k characters instead of 32k, keeping the errors and the tail.

## The rest

A viewer that stops writes why in `viewer.exit`. A lesson that is too long is refused with the text already cut to fit.

## What I did not do

- The two new agent types are there to be tried, not the default: their saving has to be measured on a real room first.
- I could not reproduce a process marked as still running after it ended; the check that reads it is unchanged.
