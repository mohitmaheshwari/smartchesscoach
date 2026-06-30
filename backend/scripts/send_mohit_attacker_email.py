"""
Second email to Mohit — the "attacker" angle.

The first email (send_mohit_reengagement.py) used the long-game conversion
data. This one uses the new move_observations layer to surface a different
identity: Mohit AS an attacker who hangs pieces. Uses real observed counts
across his 556 analyzed games.

Subject: data-forward + surprise.
Body: identity ("you're an attacker") → specific number proof → the
specific gap (piece safety on attacking moves) → tiny ask (3 moments page).
"""
import argparse, asyncio, os, smtplib, ssl, sys
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
CTA_TOPIC = "piece_safety"
SUBJECT = "Mohit, you give check 678 times. You hang pieces too. Two facts that don't usually go together."

BODY_TEXT = """\
Hi Mohit,

I ran a new analysis layer across your games today and surfaced
something I couldn't see before:

You're an attacker.

Across your 556 analyzed games you give check 678 times. You set up
double-attack-checks 224 times. You play winning-attack patterns and
deliver checkmate 76 times. Most players at any level don't have this
volume of forcing-move activity — it's how you generate your wins.

Your opening confirms it: you keep reaching for the same classical
1.e4 setup. Bishop to c4. Knight development to f3 and c3 (473 moves
combined). Castle kingside (156 times). Aggressive, principled chess.

Here's what doesn't fit. While you're creating threats, you're also
leaving 780 piece-safety holes — pieces sitting where the opponent
can just take them. The interesting part: in your last 3 piece-safety
disasters, you were already WINNING by +1.5 or more — and the bad
move was a check you gave (Be3+, Qd1+, Qh5+). You attack AND give
material back. That's not a 1400 vs 1500 gap. That's the gap between
players who attack and players who attack-and-don't-give-anything-back.

The fix isn't more attacking practice. You already attack. It's a
3-second piece-safety scan right BEFORE the attacking move —
especially before you give check. Most strong attackers do this
without naming it.

I pulled 3 specific moments from your games where this happened.
Take 8 minutes.

  https://chessguru.ai/coach/moments/piece_safety

— your coach

P.S. The "find the engine's best move" count for you across your
games is 2,720. When your gut fires, it's usually right. The leak
isn't your judgment — it's a missing safety scan.
"""

BODY_HTML = """\
<p>Hi Mohit,</p>
<p>I ran a new analysis layer across your games today and surfaced something
I couldn't see before:</p>
<p><b>You're an attacker.</b></p>
<p>Across your <b>556 analyzed games</b> you give check <b>678 times</b>. You
set up double-attack-checks <b>224 times</b>. You play winning-attack
patterns and deliver checkmate <b>76 times</b>. Most players at any level
don't have this volume of forcing-move activity — it's how you generate
your wins.</p>
<p>Your opening confirms it: you keep reaching for the same classical 1.e4
setup. Bishop to c4. Knight development to f3 and c3 (<b>473 moves combined</b>).
Castle kingside (<b>156 times</b>). Aggressive, principled chess.</p>
<p>Here's what doesn't fit. While you're creating threats, you're also
leaving <b>780 piece-safety holes</b> — pieces sitting where the opponent
can just take them. The interesting part: in your last 3 piece-safety
disasters, you were already <i>winning</i> by +1.5 or more — and the bad
move was a check you gave (<b>Be3+</b>, <b>Qd1+</b>, <b>Qh5+</b>). You attack
AND give material back. That's not a 1400 vs 1500 gap. That's the gap
between players who attack and players who attack-and-don't-give-anything-back.</p>
<p>The fix isn't more attacking practice. You already attack. It's a
<b>3-second piece-safety scan right BEFORE the attacking move</b> —
especially before you give check. Most strong attackers do this without
naming it.</p>
<p>I pulled <b>3 specific moments from your games</b> where this happened.
Take 8 minutes.</p>
<p><a href="https://chessguru.ai/coach/moments/piece_safety" style="display:inline-block;
padding:10px 18px; background:#6366f1; color:white; text-decoration:none;
border-radius:6px; font-weight:600;">Show me the 3 moments →</a></p>
<p>— your coach</p>
<p style="color:#6b7280; font-size:13px;"><i>P.S. The "find the engine's best
move" count for you across your games is <b>2,720</b>. When your gut fires,
it's usually right. The leak isn't your judgment — it's a missing
safety scan.</i></p>
"""

SENT_FIELD = "attacker_email_sent_at"


def build_message(smtp_user, from_name):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = formataddr((from_name, smtp_user))
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = smtp_user
    msg.attach(MIMEText(BODY_TEXT, "plain", "utf-8"))
    msg.attach(MIMEText(BODY_HTML, "html", "utf-8"))
    return msg


async def main_async(send, force):
    from services.moments_topic_registry import list_topics
    if CTA_TOPIC not in list_topics():
        sys.exit(f"ERROR: CTA_TOPIC '{CTA_TOPIC}' not in registry")
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
    print(BODY_TEXT)

    if not send: return
    if not smtp_user or not smtp_password:
        sys.exit("ERROR: SMTP_USER and SMTP_PASSWORD required")

    mongo_url = os.environ.get("MONGO_URL")
    if mongo_url:
        client = AsyncIOMotorClient(mongo_url)
        db = client[os.environ.get("DB_NAME", "chess_coach")]
        u = await db.users.find_one({"user_id": TO_USER_ID}, {SENT_FIELD: 1}) or {}
        if u.get(SENT_FIELD) and not force:
            sys.exit("Already sent the attacker email. Use --force to re-send.")

    print("\nSending...")
    msg = build_message(smtp_user, smtp_from_name)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=30) as s:
        s.login(smtp_user, smtp_password)
        s.sendmail(smtp_user, [TO_EMAIL], msg.as_string())
    print(f"✅ SENT to {TO_EMAIL}")
    if mongo_url:
        await db.users.update_one({"user_id": TO_USER_ID},
            {"$set": {SENT_FIELD: datetime.now(timezone.utc).isoformat()}})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--send", action="store_true")
    p.add_argument("--force", action="store_true")
    asyncio.run(main_async(*vars(p.parse_args()).values()))


if __name__ == "__main__":
    main()
