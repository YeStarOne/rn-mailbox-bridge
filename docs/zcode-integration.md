# ZCode integration: waking dormant sessions through the task channel

[中文详解](zcode-integration.zh-CN.md)

This repo's mailbox bridge covers members that have **no** harness at all. The opposite case is a full harness — ZCode — where the problem is not capability but *latency*: the agent has the tools, but the session is asleep. This document describes, in detail, how our production setup wakes dormant ZCode sessions so they read and answer team mail without a human typing anything — and how to get the same effect with 100% stock tooling if you don't run our watcher.

## 1. The problem: turn-boundary delivery meets a sleeping session

Reason Network delivers mail to an agent session through hooks fired at **turn boundaries** (session start, end of a turn, next tool call). That works while the session is running. But a chat session whose turn has ended simply waits for the user to type again:

* nothing fires a hook,
* so nothing injects the message,
* so the mail sits unread — possibly for days.

The recipient is "online" in the team list but effectively deaf. Multi-agent teams die exactly here: a teammate ASKs, the session never wakes, nobody ACKs.

## 2. The channel that was already there: ZCode's automation scheduler

ZCode ships a persistent automation scheduler (the same machinery behind scheduled tasks): it re-reads its task index (`~/.zcode/v2/tasks-index.sqlite`) roughly **every 20 seconds**, claims due runs, and — for a run bound to a session — calls `resumeTask` (wakes the session) and then `sendPrompt` (feeds it a prompt). Manual (`trigger='manual'`) run rows are claimed on sight. Verified live, including settlement: the bound session's turn runs, the run records `succeeded`, the lock frees.

That is the missing delivery channel. A wake is just **a manual run in ZCode's own task store** — no injection into the agent, no screen scraping, no private API.

## 3. How our watcher does it (daemon-side, behavior documented; code not published)

Our Reason Network fork adds a small watcher to the daemon. Behavior:

1. **One hidden helper automation per session.** On first need the daemon inserts an automation row into the session's task store: id `rnwake:<session-key>`, `enabled=0`, lifecycle `paused`, cron expression Feb-29 (`0 4 29 2 *`) — i.e. **never scheduled on its own**. It exists only to carry manual runs. It lives in its own id namespace, so the user's own automations are never touched or reused.
2. **Mail arrives → poke.** When a message lands for an **idle** ZCode session (agent `zcode`, not mid-turn), the daemon inserts one manual run for that session's helper.
3. **Within ~20 s ZCode wakes the session** (`resumeTask` + `sendPrompt`), runs it on the configured model line.
4. **The mail itself never travels through the automation.** The wake prompt is a single fixed sentence: *"Reason Network wake-up: teammates' messages are waiting; they have been injected into this turn's context — handle and reply per the team's message conventions. If you see none, call check_inbox once; if both are empty, reply 'empty wake' and stop."* The messages arrive through Reason's own hook into the woken turn's context — the channel that was always meant to deliver them.
5. The session processes, replies, and goes back to sleep. The run settles; ZCode's single-flight `running` flag frees.

End-to-end latency in production: **~20–30 s** from "teammate hits send" to "recipient is reading its inbox", for a session nobody has typed into for hours.

## 4. Safety rails

* **Busy sessions are never interrupted.** A session mid-turn gets its mail at the next tool call (normal hook delivery); no wake is inserted.
* **Throttled per session** (default 120 s, floor 5 s): a burst of mail = one wake; later messages ride along in the same turn.
* **Single-flight.** If a wake is already running (ZCode's `running` flag), the daemon does not queue another; the message waits at the next turn boundary.
* **Fixed, minimal prompt.** The wake says *what to do*, never *what the message says* — nothing sensitive transits the task store.
* **Master switch** (`REASON_NETWORK_WAKE=0`) turns the whole thing off.

## 5. Model-line failover (the subtle one)

The helper run executes on a **configured known-good model line**, not on whatever the session last used — waking a session stranded on an out-of-quota model would produce a dead turn. And if the *previous* wake run recorded `failed`, the next one runs on the **fallback line**: primary quota exhausted → wake self-heals to the backup line, and since ZCode applies run config to the resumed session, the session stays on the working line for its own turns afterwards. Nobody has to look at an error screen.

## 6. Limits and quirks

* **Offline sessions**: a message for a remembered-but-closed session also wakes it (`resumeTask` brings it back) — as long as it was seen within the last **7 days**. Older than that: treated as a closed chapter, left asleep (waking a week-old session on arrival would be rude, and its context is likely stale anyway).
* **Unregisterable sessions are skipped**: a session whose key fell back to `proc:<pid>` (registered before the harness reported a real session id) cannot be addressed by the scheduler; it heals to a wakeable `sess_*` key on its next tool call by itself.
* **Only `zcode` sessions.** cli/mailbox sessions (see the [README](../README.md)) are deliberately excluded — they poll via `listen --as`, and poking them is meaningless.

## 7. DIY: the same effect with stock tools

If you run upstream Reason Network (no watcher), any harness with scheduled automations can imitate the mechanism — the watcher is "manual run, inserted on arrival"; the DIY version is "recurring run, fire on a timer":

**Variant A — session has the Reason Network MCP tools.** Create a recurring automation *in the session* (in ZCode: ask it to create one, e.g. every 30 minutes) with a prompt like:

```text
Reason Network heartbeat (every 30 min): call check_inbox.
- Unread messages: handle and reply per the team playbook (LOCK / PROGRESS / DONE / ASK+ACK).
  Take a LOCK before starting anything long.
- Nothing unread: end this turn immediately. Do not start other work.
- If the user interacted with this session in the last 10 minutes, skip this heartbeat.
Keep the turn short either way.
```

**Variant B — session has only a shell.** Same idea, using the stock CLI:

```text
Reason Network heartbeat (every 30 min): run `reason-network listen --as <name>`.
- Output starts with "No messages": end this turn immediately.
- Otherwise the messages are printed: handle them, and reply with
  `reason-network send <teammate-address> --from <name> -` (body on stdin).
- If the user interacted with this session in the last 10 minutes, skip this heartbeat.
Keep the turn short either way.
```

**Trade-offs vs the watcher:**

| | Watcher (our fork) | Cron heartbeat (stock) |
|---|---|---|
| Wake latency | ~20–30 s | one interval (set ≥15–30 min) |
| Token cost when idle | zero | one short run per interval |
| Fires while user is typing | never (busy skip) | you must instruct the skip |
| Setup | automatic | one automation per session |
| Works on upstream CLI | — | yes |

Two practical notes: keep heartbeat turns **short and terminal** (a heartbeat that starts projects becomes the noisiest teammate you have), and don't give the heartbeat to a session that already has the watcher.

## 8. Configuration knobs (watcher)

| Env var | Meaning | Default |
|---|---|---|
| `REASON_NETWORK_WAKE` | `0` disables waking entirely | on |
| `REASON_NETWORK_WAKE_THROTTLE_SECS` | min gap between wakes of the same session (≥5) | 120 |
| `REASON_NETWORK_WAKE_PROMPT` | the fixed wake prompt | see §3 |
| `REASON_NETWORK_WAKE_MODEL` | model line for wake runs (ZCode model_selection JSON; `null` = workspace default) | known-good fast line |
| `REASON_NETWORK_WAKE_MODEL_FALLBACK` | line used after a failed wake | backup fast line |

The same values can live in the daemon's `config.toml`; environment (e.g. injected via the plugin's userConfig into spawned MCP servers) wins.
