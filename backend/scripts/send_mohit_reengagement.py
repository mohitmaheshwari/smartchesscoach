"""
One-off re-engagement email to Mohit (user_8b599930d7ef → bhutramohit@gmail.com).

This is also serving as a deliverability test of the campaign infrastructure
— you'll see the email in your own inbox so you can vet the experience
before scaling to 45 users.

USAGE:
    python scripts/send_mohit_reengagement.py            # dry-run
    python scripts/send_mohit_reengagement.py --send     # send
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

TO_USER_ID = "user_8b599930d7ef"
TO_EMAIL = "bhutramohit@gmail.com"
TO_NAME = "Mohit"

# Email-promise = page-delivery guard. Must exist in moments_topic_registry.
CTA_TOPIC = "long_game_conversion"

SUBJECT = "Mohit, you win short games but lose the long ones — here's why"

BODY_TEXT = """\
Hi Mohit,

I went through your last 545 games and found something specific.

Most coaches assume a strong player closes out winning games. You don't —
and the data is precise about it.

When you win in under 40 moves, your win rate is 41%. Solid.

When the game reaches move 40, you drop to 34%.

That's a 7-point gap. It means in the games that last long enough for
the endgame to matter, you're actively giving back the advantage you
build by move 10. (Your average position evaluation by move 10 is +0.26
— you're slightly winning the opening on average.)

Here's what's happening: holding a small advantage is a completely
different skill from getting one. Most players never separate the two
in their mind. They treat the endgame like the opening — keep looking
for the next attack instead of squeezing the position.

I picked 3 of your long-game losses where your opponent never improved
their position — you simply gave away an evaluation by playing actively
when you should have been simplifying.

10 minutes. You'll feel the difference in your next long game.

  https://chessguru.ai/coach/moments/long_game_conversion

— your coach

P.S. The fix isn't more attacking patterns. It's a 3-question checklist
for once you have an advantage. Simple, repeatable, and most strong
players use it without naming it.
"""

BODY_HTML = """\
<p>Hi Mohit,</p>

<p>I went through your last <b>545 games</b> and found something specific.</p>

<p>Most coaches assume a strong player closes out winning games. You
don't — and the data is precise about it.</p>

<p>When you win in <b>under 40 moves</b>, your win rate is <b>41%</b>. Solid.</p>

<p>When the game reaches <b>move 40</b>, you drop to <b>34%</b>.</p>

<p>That's a 7-point gap. It means in the games that last long enough
for the endgame to matter, you're actively giving back the advantage
you build by move 10. (Your average position evaluation by move 10 is
<b>+0.26</b> — you're slightly winning the opening on average.)</p>

<p>Here's what's happening: <b>holding a small advantage is a
completely different skill from getting one.</b> Most players never
separate the two in their mind. They treat the endgame like the
opening — keep looking for the next attack instead of squeezing the
position.</p>

<p>I picked <b>3 of your long-game losses</b> where your opponent never
improved their position — you simply gave away an evaluation by playing
actively when you should have been simplifying.</p>

<p>10 minutes. You'll feel the difference in your next long game.</p>

<p><a href="https://chessguru.ai/coach/moments/long_game_conversion" style="display:inline-block;
padding:10px 18px; background:#6366f1; color:white; text-decoration:none;
border-radius:6px; font-weight:600;">Show me the 3 long-game losses →</a></p>

<p>— your coach</p>

<p style="color:#6b7280; font-size:13px;"><i>P.S. The fix isn't more
attacking patterns. It's a 3-question checklist for once you have an
advantage. Simple, repeatable, and most strong players use it without
naming it.</i></p>
"""


def build_message(smtp_user, from_name):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = formataddr((from_name, smtp_user))
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = smtp_user
    msg.attach(MIMEText(BODY_TEXT, "plain", "utf-8"))
    msg.attach(MIMEText(BODY_HTML, "html", "utf-8"))
    return msg


async def already_sent(db):
    u = await db.users.find_one({"user_id": TO_USER_ID}, {"reengagement_email_sent_at": 1})
    return bool(u and u.get("reengagement_email_sent_at"))


async def mark_sent(db):
    await db.users.update_one(
        {"user_id": TO_USER_ID},
        {"$set": {"reengagement_email_sent_at": datetime.now(timezone.utc).isoformat()}},
    )


async def main_async(send, force):
    from services.moments_topic_registry import list_topics
    if CTA_TOPIC not in list_topics():
        sys.exit(
            f"ERROR: CTA_TOPIC '{CTA_TOPIC}' not in moments_topic_registry. "
            f"Add it, or pick an existing topic. Refusing to send."
        )

    smtp_host = os.environ.get("SMTP_HOST", "smtp.zoho.in")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "Mohit from ChessGuru")

    print("=" * 60)
    print(f"From:    {smtp_from_name} <{smtp_user}>")
    print(f"To:      {TO_NAME} <{TO_EMAIL}>")
    print(f"Subject: {SUBJECT}")
    print(f"Mode:    {'SEND' if send else 'DRY-RUN'}")
    print("=" * 60)
    print()
    print(BODY_TEXT)
    print("=" * 60)

    if not smtp_user or not smtp_password:
        sys.exit("ERROR: SMTP_USER and SMTP_PASSWORD required")

    mongo_url = os.environ.get("MONGO_URL")
    if mongo_url:
        client = AsyncIOMotorClient(mongo_url)
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        if await already_sent(db) and not force:
            print("\n⚠️  Already sent. Use --force to override.")
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
        sys.exit(f"❌ FAILED: {e}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--send", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    asyncio.run(main_async(args.send, args.force))


if __name__ == "__main__":
    main()
