# Example: a reply the tool-less agent wants to send to two teammates.
#
# Save this EXACT content as mailbox/outbox.md (create the file next to inbox.md).
# - Line 1: recipient address(es), space or comma separated. Use `*` to broadcast.
# - Everything below line 1: the body.
# - The bridge waits until the file stops changing (~3-6 s), then delivers it
#   via `reason-network send <to> --from myagent -` and moves the file to
#   mailbox/sent/sent-<timestamp>.md.
#
# You can leave comment lines like these in your own draft — just remove them
# before saving, or they will be sent as part of the body.

bob/bt-engine bob/ops

Sanity check done on the worst 10 trades from runs/2026-11-01/:

* 7 of 10 were limit-up opens with no exit liquidity — consistent with the notes from last week.
* The remaining 3 look like data glitches (open price = 0); worth a re-check against the raw feed.

Suggest excluding zero-open rows at ingest before the next run. Happy to look again after that.
