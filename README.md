# rn-mailbox-bridge

English | [中文说明](README.zh-CN.md)

Give **any** AI a mailbox in a [Reason Network](https://github.com/reason-machines/reason-network) team — even one that can't run tools, call APIs, or install plugins.

A single-file Python bridge (stdlib only) that speaks Reason Network on behalf of an agent that can only read and write files — for example a desktop chat app like ChatGPT Work. The agent becomes a **first-class team member**: teammates message it, it replies, it shows up in the team list.

```
              Reason Network team
  ┌──────────────────────────────────────────────┐
  │  teammate agents ── message ──> you/myagent  │
  └───────────────────────────────┬──────────────┘
                                  │  daemon queues mail (Pull semantics)
                                  ▼
        reason-network listen --as myagent   (long poll — the bridge runs this)
                                  │
                                  ▼
                      mailbox/inbox.md          (newest first, auto-archived)
                                  │   you hand the file to the AI
                                  ▼
                          the tool-less AI reads it
                                  ▲
                          the AI writes a reply
                                  │   (or you paste it for it)
                                  ▼
                      mailbox/outbox.md         (line 1 = recipient address)
                                  │
                                  ▼
        reason-network send <to> --from myagent (the bridge runs this)
```

## Why a file bridge

Reason Network already supports agents that have no native integration: `reason-network listen --as <name>` registers a **cli session** — a real team identity (`<person>/<name>`, agent=cli) that long-polls for messages and marks them read. `reason-network send <to> --from <name>` sends as that identity. Both are stock features of the official CLI; no fork, no patch, no server-side changes.

The bridge just keeps those two commands running forever and moves text between them and two markdown files. That's the whole trick — and it means **anything that can read a file can join your team**: desktop assistants, an AI in a chat window, a model behind a restricted sandbox, or a human teammate who prefers mail.

## The mailbox contract

| Direction | File | Format |
|---|---|---|
| team → agent | `mailbox/inbox.md` | Bridge-managed. Newest message block on top under `<!-- HEADER-END -->`; older mail rolls into `inbox-archive.md`. Each block is the raw message including the sender tag. |
| agent → team | `mailbox/outbox.md` | You/agent create it. **First line**: recipient address(es) — one per recipient, separated by spaces or commas (`alice/dev bob/ops`); `*` broadcasts. **Everything below**: the body. |

The bridge watches `outbox.md` and only sends after its size+mtime stay unchanged for two consecutive polls (~3–6 s), so a half-written file is never sent. After delivery the file is archived to `mailbox/sent/`; undeliverable mail is kept as `outbox-invalid-*.md` / `outbox-failed-*.md` for inspection. See [examples/](examples/).

## Quick start

Prerequisites: the [reason-network CLI](https://github.com/reason-machines/reason-network) installed and your machine joined to a team, plus Python 3.8+.

```bash
# 1. start the bridge for a session named "myagent"
python bridge.py --session myagent

# 2. from any teammate (or any agent with the RN tools)
reason-network send you/myagent "hello from the team"
#   → appears in mailbox/inbox.md within seconds

# 3. reply: save mailbox/outbox.md as
#      line 1: you/teammate-agent
#      line 2+: the reply
#   → delivered within seconds, archived to mailbox/sent/
```

Give the AI its mailbox by pointing it at the folder (attach `inbox.md`, or mount the folder into its workspace — whatever the product allows). If the AI cannot write files at all, copy its reply into `outbox.md` yourself; the human-as-last-mile is part of the design, not a hack.

## Running it for real

* **24/7**: run it under `pythonw bridge.py ...` on Windows (no console), or a launchd/systemd unit elsewhere. Register an autostart entry (e.g. an `HKCU\...\Run` key on Windows) so it comes back after reboot.
* **Single instance**: the bridge binds a localhost port derived from the session name. Starting it twice is harmless; running two bridges for two *different* sessions side by side works out of the box.
* **Offline-safe**: if the bridge (or the machine) is down, messages queue in the Reason Network daemon and are picked up by the next `listen` — nothing is lost.
* **Team presence**: on first successful poll the bridge sets the session's status via `reason-network hook cli doing ...`, so teammates see "mailbox bridge: standing by" in the team list.
* **Logs**: `mailbox/bridge.log` (self-trimming). Manual peek: `reason-network who <session>`; manual receive: `reason-network listen --as <session>`.

Options: `--session NAME`, `--mailbox DIR`, `--wait SECS` (long-poll, default 600), `--port N`, `--cli PATH`, `--addr PERSON/NAME` (header display only). `RN_BRIDGE_SESSION` / `RN_TEAM` env vars work too.

## Windows notes (hard-won)

* **`pythonw` has no console, and its console subprocesses grow one.** A naive loop that shells out to the CLI under `pythonw.exe` pops a **new black console window on every poll** — closing it kills the CLI with exit code `0xC000013A`, and the loop immediately pops the next one. The bridge passes `subprocess.CREATE_NO_WINDOW` to every subprocess; if you write your own tooling, do the same.
* If you don't use `pythonw`, a normal `python` in a terminal is fine — the flag is a no-op elsewhere.

## Running a multi-agent team (playbook)

A mailbox is only half of it — [docs/team-playbook.md](docs/team-playbook.md) collects the conventions that make a mixed team of agents (and humans) actually work: a roster of who-does-what, session naming, five message types (LOCK / PROGRESS / DONE / HANDOFF / ASK+ACK), shared-resource discipline, and the rule that beats them all: *when your task overlaps someone's, ASK before you start*.

## Limitations

* **Not real-time on the agent side**: the tool-less AI "reads its mail" whenever you feed it the file. Don't route urgent things through it.
* **No wake-up**: cli sessions are never proactively poked; they poll. That's by design (and upstream filters them out of the wake bridge).
* **Files only**: attachments >64 MB go through Reason Network's approval flow, not the mailbox; point teammates at a shared drive instead.

## Related

* [reason-machines/reason-network](https://github.com/reason-machines/reason-network) — the engine this bridges into (MIT OR Apache-2.0). `listen --as`, `send --from` and `hook` are stock upstream features.
* DeepSeek Harness team, *Super-agent design exploration* (Oct 2026) — independently validates the same building blocks (event-driven mailbox, persistent local daemon, offline catch-up) for their own multi-agent stack. Good reading on where the pattern is heading.

## License

MIT — see [LICENSE](LICENSE).
