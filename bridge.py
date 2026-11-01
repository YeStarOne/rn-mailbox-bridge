#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rn-mailbox-bridge -- give a tool-less AI a mailbox in a Reason Network team.

Runs the official `reason-network` CLI on behalf of an agent that cannot run
anything itself (e.g. a desktop chat app that can only read/write files you
give it). Two threads, stdlib only:

  IN : `reason-network listen --as NAME` long-polls the team; every message is
       prepended to mailbox/inbox.md (newest first; older mail auto-archived
       to mailbox/inbox-archive.md). If the bridge is down, messages queue in
       the daemon and are picked up on the next listen (Pull semantics).
  OUT: anything saved to mailbox/outbox.md -- first line = recipient
       address(es) like `alice/dev`, rest = body -- is delivered via
       `reason-network send <to> --from NAME`, then archived under
       mailbox/sent/. Failures are archived as outbox-failed-*.md.

Also sets the session's `doing` status once via the hook command, so the team
list shows the bridge is standing by.

Usage:
    python bridge.py --session myagent
    python bridge.py --session myagent --mailbox D:/somewhere/mailbox

Single instance: binds a localhost port derived from the session name, so two
bridges for two different sessions can run side by side; a duplicate of the
same session exits silently. Designed to run 24/7 (pythonw on Windows,
launchd/whatever elsewhere). Autostart via your OS's usual mechanism.
"""
import argparse
import datetime
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import zlib

# Windows: pythonw has no console. Without CREATE_NO_WINDOW every console
# subprocess (the CLI) gets a NEW console window popped by Windows -- the
# listen loop then pops one every poll cycle. See README "Windows notes".
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

MAX_INBOX = 120_000          # bytes; older mail beyond this goes to the archive
LOG_LIMIT = 200_000          # bytes; log is trimmed to half when exceeded
HEADER_END = "<!-- HEADER-END -->"
STABLE_POLLS = 2             # outbox must look unchanged this many polls before sending

INBOX_HEADER = (
    "# %(title)s\n\n"
    "> You are team member **%(addr)s**. Messages from teammates are written "
    "here by the bridge, **newest first** (older mail: inbox-archive.md).\n"
    "> To reply: save a file `outbox.md` next to this one, first line = "
    "recipient address (e.g. `alice/dev`), everything below = the message.\n\n"
    + HEADER_END + "\n\n"
)

io_lock = threading.Lock()


def default_cli():
    """Locate the reason-network CLI: ~/.local/bin first, then PATH."""
    exe = "reason-network.exe" if os.name == "nt" else "reason-network"
    p = os.path.join(os.path.expanduser("~"), ".local", "bin", exe)
    if os.path.exists(p):
        return p
    found = shutil.which("reason-network")
    return found or p


class Bridge:
    def __init__(self, args):
        self.session = args.session
        self.base = os.path.abspath(args.mailbox)
        self.inbox = os.path.join(self.base, "inbox.md")
        self.inbox_archive = os.path.join(self.base, "inbox-archive.md")
        self.outbox = os.path.join(self.base, "outbox.md")
        self.log_path = os.path.join(self.base, "bridge.log")
        self.sent_dir = os.path.join(self.base, "sent")
        self.cli = args.cli or default_cli()
        self.cwd = self.base
        self.wait = args.wait
        self.port = args.port or (39200 + zlib.crc32(self.session.encode()) % 500)
        self.addr = args.addr  # only used in the inbox header text

    # ---------- small utils ----------

    def log(self, msg):
        line = "[%s] %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
        with io_lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
                if os.path.getsize(self.log_path) > LOG_LIMIT:
                    with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                        tail = f.read()[-LOG_LIMIT // 2:]
                    with open(self.log_path, "w", encoding="utf-8") as f:
                        f.write(tail)
            except OSError:
                pass

    def stamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def run(self, argv, timeout, stdin_text=None):
        """Run the CLI without ever popping a console window (see NO_WINDOW)."""
        return subprocess.run(
            argv, input=stdin_text, cwd=self.cwd, capture_output=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=NO_WINDOW)

    # ---------- inbox ----------

    def prepend_inbox(self, text):
        block = "## %s · Reason Network message\n\n%s\n\n---\n\n" % (self.stamp(), text.strip())
        with io_lock:
            try:
                with open(self.inbox, "r", encoding="utf-8") as f:
                    old = f.read()
            except OSError:
                old = None
            if old is None or HEADER_END not in old:
                new = self._fresh_inbox() + block
            else:
                head, rest = old.split(HEADER_END, 1)
                new = head + HEADER_END + "\n" + block + rest.lstrip("\n")
            if len(new.encode("utf-8")) > MAX_INBOX:
                head, rest = new.split(HEADER_END, 1)
                cut = rest.rfind("\n---\n", 0, MAX_INBOX)
                if cut > 0:
                    try:
                        with open(self.inbox_archive, "a", encoding="utf-8") as f:
                            f.write(rest[cut:])
                    except OSError:
                        pass
                    new = head + HEADER_END + rest[:cut] + "\n(older messages: see inbox-archive.md)\n"
            with open(self.inbox, "w", encoding="utf-8") as f:
                f.write(new)

    def _fresh_inbox(self):
        title = "# %s mailbox (Reason Network -> this agent)" % self.session
        return INBOX_HEADER % {"title": title, "addr": self.addr}

    def listen_loop(self):
        doing_set = False
        while True:
            try:
                p = self.run(
                    [self.cli, "listen", "--as", self.session, "--wait", str(self.wait)],
                    timeout=self.wait + 100)
                if p.returncode != 0:
                    self.log("listen exited %d: %s" % (
                        p.returncode, ((p.stderr or "") + (p.stdout or "")).strip()[:200]))
                    time.sleep(10)
                    continue
                out = (p.stdout or "").strip()
                if out.startswith("No messages"):
                    pass  # poll timeout, nothing to do
                elif out:
                    self.prepend_inbox(out)
                    self.log("inbox: received %d chars -> inbox.md" % len(out))
                if not doing_set:
                    self.set_doing()
                    doing_set = True
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                self.log("listen error: %r" % e)
                time.sleep(10)

    def set_doing(self):
        try:
            self.run([self.cli, "hook", "cli", "doing", "--session", self.session,
                      "--doing", "mailbox bridge: standing by (inbox.md in / outbox.md out)"],
                     timeout=30)
        except Exception as e:
            self.log("set_doing failed: %r" % e)

    # ---------- outbox ----------

    def move_outbox(self, tag):
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = ("sent-%s.md" % ts) if tag is None else ("%s-%s.md" % (tag, ts))
        dst = os.path.join(self.sent_dir if tag is None else self.base, name)
        if os.path.exists(dst):
            dst = dst.replace(".md", "-%d.md" % int(time.time()))
        try:
            os.rename(self.outbox, dst)
            return dst
        except OSError as e:
            self.log("outbox archive failed: %r" % e)
            return None

    def handle_outbox(self, raw):
        lines = raw.strip("\ufeff").splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            return True
        tos = [t for t in lines[0].strip().replace("，", " ").replace(",", " ").split() if t]
        body = "\n".join(lines[1:]).strip()
        if not tos or not all(("/" in t or t == "*") for t in tos):
            self.move_outbox("outbox-invalid")
            self.log("outbox skipped: first line is not recipient address(es) like `alice/dev`")
            return True
        if not body:
            self.move_outbox("outbox-invalid")
            self.log("outbox skipped: empty body")
            return True
        ok = True
        for to in tos:
            try:
                p = self.run([self.cli, "send", to, "--from", self.session, "-"],
                             timeout=60, stdin_text=body)
                if p.returncode == 0:
                    self.log("sent -> %s (%d chars)" % (to, len(body)))
                else:
                    ok = False
                    self.log("send failed -> %s: %s" % (
                        to, ((p.stderr or "") + (p.stdout or "")).strip()[:200]))
            except Exception as e:
                ok = False
                self.log("send error -> %s: %r" % (to, e))
        if ok:
            self.move_outbox(None)
        return ok

    def outbox_loop(self):
        attempts = {}
        last_seen = None
        while True:
            try:
                if os.path.exists(self.outbox):
                    st = os.stat(self.outbox)
                    if st.st_size > 0:
                        key = (st.st_size, int(st.st_mtime))
                        if key != last_seen:
                            last_seen = key  # wait until the file stops changing (half-written files)
                        else:
                            with open(self.outbox, "r", encoding="utf-8", errors="replace") as f:
                                raw = f.read()
                            last_seen = None
                            if not self.handle_outbox(raw):
                                n = attempts.get(key, 0) + 1
                                attempts[key] = n
                                self.log("outbox send attempt %d failed" % n)
                                if n >= 3:
                                    self.move_outbox("outbox-failed")
                                    self.log("outbox failed 3 times; archived for inspection")
            except Exception as e:
                self.log("outbox error: %r" % e)
            time.sleep(3)

    # ---------- lifecycle ----------

    def run_forever(self):
        os.makedirs(self.sent_dir, exist_ok=True)
        guard = socket.socket()
        try:
            guard.bind(("127.0.0.1", self.port))
            guard.listen(1)
        except OSError:
            print("bridge for %s already running (port %d busy)" % (self.session, self.port))
            return
        if not os.path.exists(self.inbox):
            with open(self.inbox, "w", encoding="utf-8") as f:
                f.write(self._fresh_inbox())
        self.log("bridge started pid=%d session=%s cli=%s port=%d" % (
            os.getpid(), self.session, self.cli, self.port))
        threading.Thread(target=self.listen_loop, daemon=True).start()
        threading.Thread(target=self.outbox_loop, daemon=True).start()
        while True:
            time.sleep(3600)


def main():
    ap = argparse.ArgumentParser(description="Mailbox bridge: Reason Network <-> a tool-less AI")
    ap.add_argument("--session", default=os.environ.get("RN_BRIDGE_SESSION", "myagent"),
                    help="team session name to register (default: $RN_BRIDGE_SESSION or 'myagent')")
    ap.add_argument("--addr", default=None,
                    help="your full team address shown in the inbox header (e.g. alice/myagent); guessed if omitted")
    ap.add_argument("--mailbox", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "mailbox"),
                    help="mailbox directory (default: ./mailbox next to this script)")
    ap.add_argument("--wait", type=int, default=600, help="listen long-poll seconds (default 600)")
    ap.add_argument("--port", type=int, default=0,
                    help="single-instance lock port (default: derived from session name)")
    ap.add_argument("--cli", default=None, help="path to the reason-network CLI (default: autodetect)")
    args = ap.parse_args()
    if not args.addr:
        team = os.environ.get("RN_TEAM")
        args.addr = ("%s/%s" % (team, args.session)) if team else args.session
    Bridge(args).run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
