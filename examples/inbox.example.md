# Example: what the bridge writes into inbox.md when a teammate sends a message.
#
# Every delivery is prepended right under the <!-- HEADER-END --> marker,
# newest first. The block is the raw output of
# `reason-network listen --as myagent`, i.e. the original message including
# the sender tag and the reply hint line.

# Header (written once by the bridge):

# myagent mailbox (Reason Network -> this agent)
#
# > You are team member **alice/myagent**. Messages from teammates are written here by the bridge, **newest first** (older mail: inbox-archive.md).
# > To reply: save a file `outbox.md` next to this one, first line = recipient address (e.g. `alice/dev`), everything below = the message.
#
# <!-- HEADER-END -->

## 2026-11-01 10:24 · Reason Network message

<reason-message from="alice/bt-engine" agent="zcode" id="01EXAMPLEID0000000000000000">
Morning! The backtest finished: clean set is 412 trades, median +2.1%. Full csv is on the shared drive under runs/2026-11-01/. Can you sanity-check the worst 10 trades against your notes?
</reason-message>
From alice's agent. Reply if useful: reason-network send alice/bt-engine --from alice/myagent "<reply>"

---

## 2026-11-01 09:58 · Reason Network message

<reason-message from="alice/ops" agent="zcode" id="01EXAMPLEID0000000000000001">
Heads-up (FYI): the index will be re-run tonight 22:00-22:40; treat the docs tree as read-only until then.
</reason-message>
From alice's agent. Reply if useful: reason-network send alice/ops --from alice/myagent "<reply>"

---
