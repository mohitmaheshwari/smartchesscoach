"""
One-off re-engagement email to Shobhit (user_e9acb79dfc26).

Modeled on send_beta_feedback_email.py — same Zoho SMTP path
(mohit@chessguru.ai via smtp.zoho.in:465).

USAGE:
    # Dry-run (prints email, no send)
    python scripts/send_shobhit_reengagement.py

    # Real send (after you've reviewed dry-run)
    python scripts/send_shobhit_reengagement.py --send

Marks `users.reengagement_email_sent_at` on success so a re-run won't
double-send. Pass --force to override.
"""
import argparse
import asyncio
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient

# Recipient — Shobhit Maheshwari
TO_USER_ID = "user_e9acb79dfc26"
TO_EMAIL = "shobhit.bhutra1993@gmail.com"
TO_NAME = "Shobhit"

# CTA topic — must exist in services.moments_topic_registry.TOPICS or this
# script will refuse to run. Guarantees email-promise = page-delivery.
CTA_TOPIC = "piece_safety"

SUBJECT = "Shobhit, there's a moment in your games when you stop thinking"

BODY_TEXT = """\
Hi Shobhit,

Most coaches won't tell you this out loud:

Getting an advantage is the easy part. Keeping it is a completely
different skill — and most players never learn it.

Watch what happens around move 10 in your games. You usually have a
real edge by then — your pieces are out, your king is safe, your
position is just better than your opponent's. Your brain registers
"I'm winning" and quietly switches gears. You start executing
instead of thinking.

That tiny mental switch is what your opponents have been waiting for.

Strong players do something different. After they get an advantage,
they don't relax — they get MORE careful. Before every single move,
they look at each of their own pieces and ask one question:
"Is anyone touching this?" It takes 3 seconds. It saves the game.

I picked 3 specific moments from your games this week where you had
a winning position and one quick scan would have caught exactly what
your opponent was setting up.

10 minutes. You'll see your own play differently after.

  https://chessguru.ai/coach/moments/piece_safety

— your coach

P.S. Most students who build this habit see the difference inside
5–10 games. The change isn't subtle.
"""

BODY_HTML = """\
<p>Hi Shobhit,</p>

<p>Most coaches won't tell you this out loud:</p>

<p><b>Getting an advantage is the easy part. Keeping it is a
completely different skill — and most players never learn it.</b></p>

<p>Watch what happens around move 10 in your games. You usually have
a real edge by then — your pieces are out, your king is safe, your
position is just better than your opponent's. Your brain registers
"I'm winning" and quietly switches gears. You start
<i>executing</i> instead of <i>thinking</i>.</p>

<p>That tiny mental switch is what your opponents have been waiting for.</p>

<p>Strong players do something different. After they get an advantage,
they don't relax — they get <b>more careful</b>. Before every single
move, they look at each of their own pieces and ask one question:
<i>"Is anyone touching this?"</i> It takes 3 seconds. It saves the game.</p>

<p>I picked <b>3 specific moments from your games this week</b> where
you had a winning position and one quick scan would have caught exactly
what your opponent was setting up.</p>

<p>10 minutes. You'll see your own play differently after.</p>

<p><a href="https://chessguru.ai/coach/moments/piece_safety" style="display:inline-block;
padding:10px 18px; background:#6366f1; color:white; text-decoration:none;
border-radius:6px; font-weight:600;">Show me the 3 moments →</a></p>

<p>— your coach</p>

<p style="color:#6b7280; font-size:13px;"><i>P.S. Most students who
build this habit see the difference inside 5–10 games. The change
isn't subtle.</i></p>
"""


def build_message(smtp_user: str, from_name: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = formataddr((from_name, smtp_user))
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = smtp_user
    msg.attach(MIMEText(BODY_TEXT, "plain", "utf-8"))
    msg.attach(MIMEText(BODY_HTML, "html", "utf-8"))
    return msg


async def already_sent(db) -> bool:
    u = await db.users.find_one({"user_id": TO_USER_ID}, {"reengagement_email_sent_at": 1})
    return bool(u and u.get("reengagement_email_sent_at"))


async def mark_sent(db) -> None:
    await db.users.update_one(
        {"user_id": TO_USER_ID},
        {"$set": {"reengagement_email_sent_at": datetime.now(timezone.utc).isoformat()}},
    )


async def main_async(send: bool, force: bool):
    # Guarantee email-promise = page-delivery (see moments_topic_registry).
    from services.moments_topic_registry import list_topics
    if CTA_TOPIC not in list_topics():
        sys.exit(
            f"ERROR: CTA_TOPIC '{CTA_TOPIC}' is not in moments_topic_registry.TOPICS. "
            f"Either add it to the registry first, or change CTA_TOPIC. Refusing to send "
            f"an email with a CTA that doesn't have a backing page."
        )

    smtp_host = os.environ.get("SMTP_HOST", "smtp.zoho.in")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "Mohit from ChessGuru")

    print("=" * 60)
    print(f"From:           {smtp_from_name} <{smtp_user}>")
    print(f"To:             {TO_NAME} <{TO_EMAIL}>")
    print(f"Subject:        {SUBJECT}")
    print(f"SMTP:           {smtp_user} via {smtp_host}:{smtp_port}")
    print(f"Mode:           {'SEND' if send else 'DRY-RUN (no send)'}")
    print("=" * 60)
    print()
    print(BODY_TEXT)
    print("=" * 60)

    # Sanity checks
    if not smtp_user or not smtp_password:
        print("\nERROR: SMTP_USER and SMTP_PASSWORD must be set.")
        sys.exit(1)

    # Check dup-send
    mongo_url = os.environ.get("MONGO_URL")
    if mongo_url:
        client = AsyncIOMotorClient(mongo_url)
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        if await already_sent(db) and not force:
            print("\n⚠️  This user already has reengagement_email_sent_at set. "
                  "Skipping. Use --force to override.")
            return

    if not send:
        print("\nDry-run only. Re-run with --send to actually send.")
        return

    print("\nSending...")
    try:
        msg = build_message(smtp_user, smtp_from_name)
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=30) as s:
            s.login(smtp_user, smtp_password)
            s.sendmail(smtp_user, [TO_EMAIL], msg.as_string())
        print(f"✅ SENT to {TO_EMAIL}")
        if mongo_url:
            await mark_sent(db)
            print("✅ Marked users.reengagement_email_sent_at")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--send", action="store_true", help="Actually send. Default = dry-run.")
    p.add_argument("--force", action="store_true", help="Send even if already sent before.")
    args = p.parse_args()
    asyncio.run(main_async(args.send, args.force))


if __name__ == "__main__":
    main()
