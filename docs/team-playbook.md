# Multi-agent team playbook

A mailbox gets an agent *into* the team. These conventions are what make a mixed team — several agents, maybe a human or two — actually productive instead of chaotic. They emerged from running a small production team of ZCode sessions plus a tool-less desktop assistant; nothing here is specific to any one product.

## 1. Roster: who does what

Keep one document (a shared file, a memory store, anything the team can read) that answers three questions:

* which members exist,
* which domain each owns (backtests, indexing, research, ops, ...),
* where to find their outputs.

Rules that keep it alive:

* Every member registers its domain **before** starting work, and updates the roster when its role changes.
* `doing` status is the real-time truth; the roster only records the *domain*. Never resolve "what is X doing right now" from the roster.
* A member that sees itself missing from (or mislabeled in) the roster fixes it and tells the team.

## 2. Session naming

Name members after their job so the team list reads itself: `bt-*` backtest, `idx-*` indexing, `dat-*` data, `rsh-*` research, `ops-*` ops, `ui-*` visualization. An auto-assigned name (`agent-7`) is a smell — rename on first contact.

## 3. Five message types

Most team traffic is one of five kinds. Say which one you're sending:

| Type | Meaning |
|---|---|
| **LOCK** | I'm using shared resource X until T — don't touch it. Always with a scope and an expiry. |
| **PROGRESS** | Periodic heartbeat on long work, so nobody wonders if you died. |
| **DONE** | Work finished. Where the output lives, what changed, any follow-ups. |
| **HANDOFF** | I'm leaving; here's the state, the next step, and the traps. |
| **ASK / ACK** | Ask a teammate for something / acknowledge within a fixed window (say 15 min) even if the answer is "not yet". |

An ACK is not an answer — it's a promise to answer. Teams die of silent ASKs.

## 4. Shared resources

* One writer at a time for anything shared: a repository, an index, a database, a file another agent might read. Take a LOCK first; check for LOCKs before you push.
* Long runs (indexing, big builds, backtests) make the whole tree they touch read-only for everyone else — announce them.
* Numbers don't travel through files that others can't search. When a result matters, put the numbers *in the message body*.

## 5. Don't work alone

The failure mode of agent teams is two members independently burning hours on the same problem because each assumed it was alone. When your task overlaps someone's domain, or you need their output:

* **ASK first.** A sleeping teammate wakes in ~30 s (how: [zcode-integration.md](zcode-integration.md)); redoing their work costs hours.
* When you receive an ASK, ACK it even before you have the answer.

## 6. The human as last mile

Tool-less members (a desktop assistant reachable only through files) are full members with one constraint: someone must ferry bytes. Design for it:

* Their mailbox is the interface; keep the contract (README) simple enough that a human can operate it by hand.
* They are **not** for urgent work — their latency is "whenever a human next feeds them".
* Anything the team must never leak (credentials, invite links, private paths) stays out of the mailbox entirely. Mailbox files get read into third-party contexts you don't control.

## 7. Keep a memory

Conversations are lost; files persist. Put durable findings — decisions, gotchas, post-mortems, who-decided-what — into a shared, searchable store (a git repo of markdown files works fine), and commit + push after every change, not in batches. A finding that lives only in one session's context is a finding you will pay to rediscover.
