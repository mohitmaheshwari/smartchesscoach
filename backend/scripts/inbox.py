"""
Read-side Zoho mailbox helper for ongoing inbox checking.

Uses the same Zoho App Password as send_shobhit_reengagement.py (SMTP)
but talks IMAP instead. Stdlib only — imaplib + email parsing.

Commands:
    python scripts/inbox.py probe
        Connect, list folders, show counts. No content read.

    python scripts/inbox.py unread [--limit 20]
        List unread messages in INBOX (from, subject, date). Headers only.

    python scripts/inbox.py search --from EMAIL [--since DAYS] [--limit 20]
        Search by sender, return headers.

    python scripts/inbox.py read --uid MSG_UID
        Read full body of one specific message by IMAP UID.

    python scripts/inbox.py recent [--hours 24] [--limit 20]
        Recently received messages (any sender), headers only.

Env vars expected (same as the send script):
    SMTP_USER       — your zoho address (also IMAP user)
    SMTP_PASSWORD   — your zoho app password
    IMAP_HOST       — defaults to imap.zoho.in
    IMAP_PORT       — defaults to 993
"""
import argparse
import email
import imaplib
import os
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime


def _connect():
    host = os.environ.get("IMAP_HOST", "imap.zoho.in")
    port = int(os.environ.get("IMAP_PORT", "993"))
    user = os.environ.get("SMTP_USER")  # same address for both
    pw = os.environ.get("SMTP_PASSWORD")
    if not user or not pw:
        sys.exit("ERROR: set SMTP_USER and SMTP_PASSWORD env vars")
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, pw)
    return conn, user, host, port


def _decode(raw):
    if not raw:
        return ""
    parts = decode_header(raw)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            try:
                out.append(txt.decode(enc or "utf-8", errors="replace"))
            except Exception:
                out.append(txt.decode("utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)


def _short(s, n=80):
    s = (s or "").replace("\n", " ").replace("\r", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def cmd_probe():
    conn, user, host, port = _connect()
    print(f"✅ Connected to {host}:{port} as {user}\n")
    typ, folders = conn.list()
    print("Folders:")
    for f in folders:
        if not isinstance(f, bytes):
            continue
        # b'(\\HasNoChildren) "/" "INBOX"'
        line = f.decode("utf-8", errors="replace")
        # naive but works for Zoho's flat layout
        parts = line.rsplit('"', 2)
        name = parts[1] if len(parts) > 1 else line
        # count messages in each
        typ, _ = conn.select(name, readonly=True)
        if typ == "OK":
            typ, data = conn.search(None, "ALL")
            total = len(data[0].split()) if data and data[0] else 0
            typ, data = conn.search(None, "UNSEEN")
            unread = len(data[0].split()) if data and data[0] else 0
            print(f"  {name:<40}  total={total:>5}  unread={unread:>3}")
    conn.logout()


def _headers_for(conn, uids, limit):
    """Fetch BODY.PEEK[HEADER] for a list of UIDs. Return list of dicts."""
    out = []
    for uid in uids[-limit:][::-1]:  # most recent first within the slice
        typ, data = conn.uid("fetch", uid, "(BODY.PEEK[HEADER])")
        if typ != "OK" or not data or not data[0]:
            continue
        raw = data[0][1] if isinstance(data[0], tuple) else b""
        msg = email.message_from_bytes(raw)
        out.append({
            "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            "from": _decode(msg.get("From")),
            "subject": _decode(msg.get("Subject")),
            "date": msg.get("Date"),
            "to": _decode(msg.get("To")),
        })
    return out


def cmd_unread(limit):
    conn, *_ = _connect()
    conn.select("INBOX", readonly=True)
    typ, data = conn.uid("search", None, "UNSEEN")
    uids = data[0].split() if data and data[0] else []
    print(f"INBOX unread: {len(uids)}\n")
    for h in _headers_for(conn, uids, limit):
        print(f"  [{h['uid']:>6}]  {h['date'] or '?':<35}")
        print(f"           from: {_short(h['from'], 70)}")
        print(f"           subj: {_short(h['subject'], 90)}")
        print()
    conn.logout()


def cmd_search(from_addr, since_days, limit):
    conn, *_ = _connect()
    conn.select("INBOX", readonly=True)
    crit = []
    if from_addr:
        crit += ["FROM", f'"{from_addr}"']
    if since_days:
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
        crit += ["SINCE", since]
    if not crit:
        crit = ["ALL"]
    typ, data = conn.uid("search", None, *crit)
    uids = data[0].split() if data and data[0] else []
    print(f"Matched {len(uids)} messages (search: {' '.join(crit)})\n")
    for h in _headers_for(conn, uids, limit):
        print(f"  [{h['uid']:>6}]  {h['date'] or '?'}")
        print(f"           from: {_short(h['from'], 70)}")
        print(f"           subj: {_short(h['subject'], 90)}")
        print()
    conn.logout()


def cmd_read(uid):
    conn, *_ = _connect()
    conn.select("INBOX", readonly=True)
    typ, data = conn.uid("fetch", uid, "(BODY.PEEK[])")
    if typ != "OK" or not data or not data[0]:
        sys.exit(f"Could not fetch UID {uid}")
    raw = data[0][1] if isinstance(data[0], tuple) else b""
    msg = email.message_from_bytes(raw)
    print(f"From:    {_decode(msg.get('From'))}")
    print(f"To:      {_decode(msg.get('To'))}")
    print(f"Date:    {msg.get('Date')}")
    print(f"Subject: {_decode(msg.get('Subject'))}")
    print("-" * 60)
    # Extract plain text body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset, errors="replace")
                break
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    body = f"[HTML body — raw]\n{body[:5000]}"
                    break
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    print(body[:8000])
    conn.logout()


def cmd_recent(hours, limit):
    conn, *_ = _connect()
    conn.select("INBOX", readonly=True)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%d-%b-%Y")
    typ, data = conn.uid("search", None, "SINCE", since)
    uids = data[0].split() if data and data[0] else []
    print(f"Received in last {hours}h: {len(uids)}\n")
    for h in _headers_for(conn, uids, limit):
        print(f"  [{h['uid']:>6}]  {h['date'] or '?'}")
        print(f"           from: {_short(h['from'], 70)}")
        print(f"           subj: {_short(h['subject'], 90)}")
        print()
    conn.logout()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("probe")
    p_unread = sub.add_parser("unread"); p_unread.add_argument("--limit", type=int, default=20)
    p_search = sub.add_parser("search")
    p_search.add_argument("--from", dest="from_addr")
    p_search.add_argument("--since", type=int, default=7, help="days back")
    p_search.add_argument("--limit", type=int, default=20)
    p_read = sub.add_parser("read"); p_read.add_argument("--uid", required=True)
    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--hours", type=int, default=24); p_recent.add_argument("--limit", type=int, default=20)
    args = p.parse_args()

    if args.cmd == "probe": cmd_probe()
    elif args.cmd == "unread": cmd_unread(args.limit)
    elif args.cmd == "search": cmd_search(args.from_addr, args.since, args.limit)
    elif args.cmd == "read": cmd_read(args.uid)
    elif args.cmd == "recent": cmd_recent(args.hours, args.limit)
    else: p.print_help()


if __name__ == "__main__":
    main()
