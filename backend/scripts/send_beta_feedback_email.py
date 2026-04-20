"""
Beta feedback email sender — sends a personal ask to every user in the DB
who hasn't already received it.

Safety features:
  - Dry-run by default. Prints the preview and exits. Pass --send to actually send.
  - Tracks who got the email in `users.feedback_email_sent_at` so re-runs skip them.
  - Rate-limits at 2s between sends (well under Zoho's free limit).
  - Only sends to users with a valid-looking email.
  - Logs every attempt; failures don't stop the batch.

Usage:
    # preview first
    python scripts/send_beta_feedback_email.py

    # send for real (after preview looks right)
    python scripts/send_beta_feedback_email.py --send

    # send to just one address for final sanity check
    python scripts/send_beta_feedback_email.py --send --only your@email.com

    # resend to everyone (clears the sent-flag first) — NUCLEAR, use with care
    python scripts/send_beta_feedback_email.py --send --force
"""

import argparse
import asyncio
import os
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.zoho.in")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Mohit from ChessGuru")

SUBJECT = "I need 2 minutes of your time — Mohit from ChessGuru"

EMAIL_BODY = """\
Hi {first_name},

Thanks for joining ChessGuru early.

I'm Mohit — I'm the one building this. Being honest with you: ChessGuru is
still in active development. Some parts work well. Others are rough. I'm
pushing changes nearly every day.

That's why you're getting this email — I need real players to tell me
what's working and what isn't.

If you have 2 minutes, I'd genuinely like to hear:

  1. What was the first thing you tried — and what did you think?

  2. Where did it feel confusing, wrong, or disappointing?

  3. Is there one thing you wished the coach would say, show, or do?

Just hit reply. One line or ten — whatever you have time for. I read every
response myself.

Everyone who sends feedback during this stage gets their name on the
ChessGuru Contributors list — a permanent credit in the app for people
who shaped it in the earliest days.

The product only gets better if we build it with the people using it.
You saw the rough edges first. Tell me where they hurt.

Thanks for being here.

— Mohit
Founder, ChessGuru
chessguru.ai

P.S. Not ready yet? Play a couple of games, break something, then hit
reply when you're ready. No deadline on my end.
"""

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def extract_first_name(user: dict) -> str:
    """Pull something reasonable to greet by. 'there' if nothing fits."""
    for key in ("display_name", "name"):
        v = user.get(key)
        if v and isinstance(v, str):
            first = v.split()[0].strip()
            if first and len(first) <= 30:
                return first[0].upper() + first[1:].lower()
    email = user.get("email") or ""
    if "@" in email:
        handle = email.split("@")[0]
        tokens = [t for t in re.split(r"[._-]", handle) if t]
        if tokens:
            first = tokens[0]
            if 2 <= len(first) <= 12 and first.isalpha():
                return first[0].upper() + first[1:].lower()
    return "there"


def build_message(to_email: str, first_name: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_USER))
    msg["To"] = to_email
    msg["Reply-To"] = SMTP_USER
    msg.attach(MIMEText(EMAIL_BODY.format(first_name=first_name), "plain", "utf-8"))
    return msg


def send_one(to_email: str, first_name: str) -> None:
    msg = build_message(to_email, first_name)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=30) as s:
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, [to_email], msg.as_string())


async def fetch_users(db, only: str | None, force: bool):
    q: dict = {"email": {"$exists": True, "$ne": None, "$ne": ""}}
    if only:
        q["email"] = only
    elif not force:
        q["feedback_email_sent_at"] = {"$in": [None, ""]}
    return await db.users.find(
        q, {"_id": 0, "user_id": 1, "email": 1, "display_name": 1, "name": 1,
            "feedback_email_sent_at": 1}
    ).to_list(5000)


async def mark_sent(db, user_id: str):
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"feedback_email_sent_at": datetime.now(timezone.utc).isoformat()}},
    )


async def clear_sent_flag(db):
    res = await db.users.update_many({}, {"$unset": {"feedback_email_sent_at": ""}})
    return res.modified_count


async def main_async(send: bool, only: str | None, force: bool, delay: float):
    # Sanity-check env
    missing = [k for k in ("SMTP_USER", "SMTP_PASSWORD") if not os.environ.get(k)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)} — add them to backend/.env")
        sys.exit(1)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # --force clears the sent-flag so everyone gets the email again
    if force and send:
        n = await clear_sent_flag(db)
        print(f"[--force] cleared feedback_email_sent_at on {n} users")

    users = await fetch_users(db, only=only, force=force)

    # Filter out anything that doesn't look like a real email
    valid = []
    skipped_bad = 0
    for u in users:
        email = (u.get("email") or "").strip().lower()
        if not email or not EMAIL_RE.match(email):
            skipped_bad += 1
            continue
        u["email"] = email  # normalized
        valid.append(u)

    print()
    print(f"DB:                  {DB_NAME}")
    print(f"SMTP:                {SMTP_USER}  via  {SMTP_HOST}:{SMTP_PORT}")
    print(f"Subject:             {SUBJECT}")
    print(f"Mode:                {'SEND' if send else 'DRY-RUN'}")
    if only:
        print(f"Filter --only:       {only}")
    if force:
        print(f"Flag --force:        (cleared sent-flag)")
    print(f"Candidates matched:  {len(valid)}")
    print(f"Skipped bad emails:  {skipped_bad}")
    print(f"Delay per send:      {delay}s")
    print()

    if not valid:
        print("  Nothing to do.")
        client.close()
        return

    # Preview first 3 composed messages regardless of mode
    print("──────── Preview (first 3) ────────")
    for u in valid[:3]:
        first = extract_first_name(u)
        preview = EMAIL_BODY.format(first_name=first)
        print(f"\nTo: {u['email']}  (greeting: '{first}')")
        print("---")
        print("\n".join(preview.splitlines()[:6]))
        print("... [truncated]")
    print()

    if not send:
        print("[DRY-RUN] no emails sent. Re-run with --send to actually send.")
        client.close()
        return

    # Final confirmation before real send
    if not only:  # skip the confirm if you're only testing one address
        print(f"About to send {len(valid)} live emails via {SMTP_HOST}.")
        confirm = input("Type 'SEND' to proceed: ").strip()
        if confirm != "SEND":
            print("Aborted.")
            client.close()
            return

    # Do it
    sent = 0
    failed = []
    start = time.time()
    for i, u in enumerate(valid, 1):
        first = extract_first_name(u)
        try:
            send_one(u["email"], first)
            await mark_sent(db, u["user_id"])
            sent += 1
            print(f"  [{i}/{len(valid)}] ✓ {u['email']:<40}  ({first})")
        except Exception as e:
            failed.append((u["email"], str(e)))
            print(f"  [{i}/{len(valid)}] ✗ {u['email']:<40}  FAILED: {e}")
        if i < len(valid):
            time.sleep(delay)

    elapsed = time.time() - start
    print()
    print(f"Done in {elapsed:.0f}s. Sent: {sent}, Failed: {len(failed)}")
    if failed:
        print("\nFailures:")
        for email, err in failed:
            print(f"  - {email}: {err}")

    client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true",
                        help="Actually send (default is dry-run)")
    parser.add_argument("--only", type=str, default=None,
                        help="Only send to this exact email (final sanity check)")
    parser.add_argument("--force", action="store_true",
                        help="Clear feedback_email_sent_at first, so everyone re-receives")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds between sends (default 2)")
    args = parser.parse_args()
    asyncio.run(main_async(args.send, args.only, args.force, args.delay))


if __name__ == "__main__":
    main()
