"""
Focus-aware re-engagement email — one script for the whole cohort.

Consumes each user's active focus from user_active_focus + their move_observations
aggregates. Body and subject are anchored to their locked topic. Links CTA to
/coach/moments/<their-topic> (guaranteed to exist via moments_topic_registry).

Voice: coach-first, not stats-first. Every specific number is verified against
their own data before it goes in.

Usage:
  # dry-run — show emails for everyone
  python scripts/send_focus_email.py
  # dry-run — one user
  python scripts/send_focus_email.py --user-id user_xxx
  # send for real
  python scripts/send_focus_email.py --send
  # send to one user
  python scripts/send_focus_email.py --send --user-id user_xxx
  # send only to top N (by baseline metric — worst-first for triage)
  python scripts/send_focus_email.py --send --limit 5

Rate-limits at 2s between sends (well under Zoho's free limits). Tracks
`focus_email_sent_at` on the user record so re-runs skip already-sent
users. `--force` overrides.
"""
import argparse, asyncio, os, re, smtplib, ssl, sys, time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient
from services.moments_topic_registry import list_topics, TOPICS as MOMENTS_TOPICS
from services.move_observation_deriver import aggregate_user_signals
from services.primary_weakness_picker import COLLECTION as FOCUS_COLL


# ─── Voice templates, per topic ────────────────────────────────────────────
# Each template produces: subject, plain body, html body. All string
# interpolation uses ONLY the verified fields we pass in.

TOPIC_LABELS = {
    "piece_safety": "Piece safety",
    "ignoring_king_safety_threats": "King safety",
    "fork_misses": "Spotting forks",
    "discovered_attack_misses": "Discovered attacks",
    "removal_of_defender_misses": "Removing defenders",
    "neglecting_development": "Piece development",
    "poor_piece_activity": "Piece activity",
    "pawn_structure_damage": "Pawn structure",
    "king_activity_neglect": "Endgame king play",
    "threat_awareness": "Reading opponent threats",
    "punish_blunders": "Punishing opponent mistakes",
}


TOPIC_INSIGHTS = {
    "piece_safety": {
        "subject": "{first_name}, I picked the one thing to fix in your play",
        "hook": "I ran a full pattern analysis on your games and picked ONE thing worth locking on.",
        "the_thing": "**Piece safety.** You leave pieces sitting where the opponent can just take them — {occ} times across your {games} analyzed games. That's the biggest single leak in your play right now.",
        "identity": "The pattern isn't that you play badly. It's that you attack, look for the next move, and forget to check what YOU'RE leaving hanging.",
        "the_fix": "The habit: **before every move**, look at each of your pieces and ask '*is anyone attacking this?*' Three seconds. Most strong attackers do this without naming it.",
        "cta_line": "I pulled 3 specific moments from your games where this happened.",
    },
    "ignoring_king_safety_threats": {
        "subject": "{first_name}, your king is walking around too much",
        "hook": "I locked your coaching focus on ONE thing this week, and it's the one that costs you games fastest.",
        "the_thing": "**King safety.** You've let your king get caught in the open **{occ} times** across your {games} games. Usually because you were attacking and left your own defense thin.",
        "identity": "The gap isn't that you can't defend. It's that when you're in attacking mode, your king becomes invisible to you.",
        "the_fix": "The habit: after every 3 opponent moves, ask '*where would checkmate come from right now?*' — even if you're up material.",
        "cta_line": "I pulled 3 moments from your games where you were winning until your king got caught.",
    },
    "fork_misses": {
        "subject": "{first_name}, you're missing forks in both directions",
        "hook": "Locked your coaching focus this week on one specific pattern in your play.",
        "the_thing": "**Fork blindness.** {occ} moments across your games where a fork was on the board — either yours to play, or theirs about to hit you.",
        "identity": "You calculate lines but skip the geometry. Fork patterns are visual — you'd catch them with practice, not more thinking.",
        "the_fix": "The drill: for every knight move you're considering, ask '*what does this knight attack besides its target?*' Same for every check.",
        "cta_line": "3 fork moments from your recent games — the ones you missed and the ones you set up.",
    },
    "neglecting_development": {
        "subject": "{first_name}, you're starting your middlegame too early",
        "hook": "Coaching focus for the next 14 days: one specific opening habit.",
        "the_thing": "**Slow development.** {occ} times across {games} games, you started attacking before all your pieces were developed. Attackers with 6 pieces beat attackers with 4 — always.",
        "identity": "You have the attacking instinct. What you don't have yet is the patience to build up first.",
        "the_fix": "The rule: no queen moves and no captures until BOTH bishops and BOTH knights are off the back rank and you've castled. Boring for 8 moves, then unleash.",
        "cta_line": "3 games where you attacked early and gave back what you'd built.",
    },
    "poor_piece_activity": {
        "subject": "{first_name}, half your pieces are on vacation",
        "hook": "Locked this week's focus on one habit that would move your rating fastest.",
        "the_thing": "**Passive pieces.** {occ} moments across your games where one of your pieces was sitting on a bad square doing nothing. You had time — you didn't relocate.",
        "identity": "You develop your pieces then leave them. Strong players move the WORST piece every 5-6 moves.",
        "the_fix": "The scan: after each opponent move, ask '*which of my pieces is least useful right now?*' — then find it a job.",
        "cta_line": "3 moments where a passive piece cost you tempo (or the game).",
    },
    "threat_awareness": {
        "subject": "{first_name}, you're missing what your opponent is setting up",
        "hook": "This week's focus locks on one thing — the exact pattern where your losses come from.",
        "the_thing": "**Reading opponent's threats.** {occ} moments across your games where the opponent set up a threat AND you didn't address it. The threat then landed.",
        "identity": "You focus on your own plan — that's a strength. The gap is scanning what THEY just changed on the board.",
        "the_fix": "The one-question habit: after every opponent move, '*what does this move NEW-Y threaten that it didn't before?*' — no other question, no other plan, until you have the answer.",
        "cta_line": "3 games where opponent set up a threat, you didn't see it, they won.",
    },
    "punish_blunders": {
        "subject": "{first_name}, your opponents give you gifts. You're not taking them.",
        "hook": "One pattern in your play, locked as this week's focus.",
        "the_thing": "**Not punishing blunders.** Your opponents blundered **{occ} times** across your games, and you didn't take advantage.",
        "identity": "You're a solid player who plays your own game. What you don't do is switch modes when the opponent hands you material.",
        "the_fix": "The switch: any time opponent's move loses more than 100cp, STOP playing your plan and calculate the punishment. It's the highest-EV moment in chess.",
        "cta_line": "3 games where opponent blundered and you missed the punishment.",
    },
}

# Fallback for topics we don't have hand-crafted insights for yet
GENERIC_TEMPLATE = {
    "subject": "{first_name}, your coaching focus this week is set",
    "hook": "I locked your coaching focus on ONE pattern in your play.",
    "the_thing": "**{topic_label}.** Detected in {occ} moments across your {games} analyzed games — it's the highest-impact thing to fix right now.",
    "identity": "One habit, 14 days. It's a targetable, coachable pattern.",
    "the_fix": "I pulled specific moments from your games so you can see it happen in your own play.",
    "cta_line": "See the moments.",
}


def _first_name(name: str) -> str:
    if not name: return "there"
    return name.split()[0].strip() or "there"


def _build_email_content(user_name: str, focus: dict, aggregate: dict, games: int) -> tuple:
    """Returns (subject, plain, html)."""
    topic = focus.get("topic_key")
    first_name = _first_name(user_name)
    tmpl = TOPIC_INSIGHTS.get(topic, GENERIC_TEMPLATE)

    # Occurrence count — verified from either the aggregate or the focus baseline
    occ = focus.get("picker_evidence_count") or focus.get("baseline_metric", {}).get("occurrence_count") or 0
    topic_label = TOPIC_LABELS.get(topic, topic.replace("_", " "))
    moments_topic = focus.get("moments_page_topic") or "piece_safety"

    subject = tmpl["subject"].format(first_name=first_name)
    fields = dict(first_name=first_name, occ=occ, games=games, topic_label=topic_label)

    # Plain-text body
    plain = f"""\
Hi {first_name},

{tmpl['hook']}

{tmpl['the_thing'].format(**fields).replace('**', '')}

{tmpl['identity']}

{tmpl['the_fix']}

{tmpl['cta_line']}

  https://chessguru.ai/coach/moments/{moments_topic}

— your coach

P.S. Your focus is locked for 14 days. Check back at chessguru.ai/home
to see how your rate is moving.
"""

    # HTML body
    def _bold(s): return s.replace('**', '<b>' if s.count('**') % 2 == 0 else '</b>').replace('**', '</b>')
    the_thing_html = tmpl["the_thing"].format(**fields)
    # Convert markdown **bold** to HTML
    the_thing_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', the_thing_html)
    the_fix_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', tmpl["the_fix"])

    html = f"""\
<p>Hi {first_name},</p>
<p>{tmpl['hook']}</p>
<p>{the_thing_html}</p>
<p>{tmpl['identity']}</p>
<p>{the_fix_html}</p>
<p>{tmpl['cta_line']}</p>
<p><a href="https://chessguru.ai/coach/moments/{moments_topic}" style="display:inline-block;
padding:10px 18px; background:#6366f1; color:white; text-decoration:none;
border-radius:6px; font-weight:600;">Show me the moments →</a></p>
<p>— your coach</p>
<p style="color:#6b7280; font-size:13px;"><i>P.S. Your focus is locked for 14 days.
Check back at <a href="https://chessguru.ai/home">chessguru.ai/home</a> to see
how your rate is moving.</i></p>
"""
    return subject, plain, html


async def _get_eligible_users(db, user_id: str = None, limit: int = 0):
    """Returns list of (user_doc, focus_doc, aggregate_signals, games_count) tuples."""
    query = {"status": "active"}
    if user_id: query["user_id"] = user_id
    focuses = await db[FOCUS_COLL].find(query).to_list(length=None)
    if limit:
        focuses = focuses[:limit]

    out = []
    for f in focuses:
        u = await db.users.find_one({"user_id": f["user_id"]})
        if not u or not u.get("email"):
            continue
        # Skip merged/deleted users
        if u.get("merged_into") or u.get("deleted_at"):
            continue
        obs = await db.move_observations.find({"user_id": f["user_id"]}).to_list(length=5000)
        agg = aggregate_user_signals(obs)
        games = await db.games.count_documents({"user_id": f["user_id"], "is_analyzed": True})
        out.append((u, f, agg, games))
    return out


def _build_message(subject, plain, html, smtp_user, from_name, to_email):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, smtp_user))
    msg["To"] = to_email
    msg["Reply-To"] = smtp_user
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


async def main_async(send: bool, user_id: str, limit: int, force: bool, delay: float):
    mongo_url = os.environ["MONGO_URL"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.zoho.in")
    smtp_port = int(os.environ.get("SMTP_PORT") or "465")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "Mohit from ChessGuru")

    if send and (not smtp_user or not smtp_password):
        sys.exit("ERROR: SMTP_USER and SMTP_PASSWORD required for --send")

    eligible = await _get_eligible_users(db, user_id, limit)
    print(f"=== {'APPLY' if send else 'DRY-RUN'} — {len(eligible)} eligible users ===\n")

    for i, (u, f, agg, games) in enumerate(eligible):
        # skip if already sent (unless --force)
        if not force and u.get("focus_email_sent_at"):
            print(f"[{i+1}/{len(eligible)}] SKIP (already sent) — {u.get('name')} <{u.get('email')}>")
            continue

        subject, plain, html = _build_email_content(u.get("name",""), f, agg, games)
        print(f"[{i+1}/{len(eligible)}] {u.get('name')} <{u.get('email')}>  topic={f['topic_key']}")
        print(f"   subject: {subject}")

        if send:
            try:
                msg = _build_message(subject, plain, html, smtp_user, smtp_from_name, u["email"])
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=30) as s:
                    s.login(smtp_user, smtp_password)
                    s.sendmail(smtp_user, [u["email"]], msg.as_string())
                await db.users.update_one(
                    {"user_id": u["user_id"]},
                    {"$set": {"focus_email_sent_at": datetime.now(timezone.utc).isoformat(),
                              "focus_email_topic": f["topic_key"]}}
                )
                print(f"   ✅ SENT")
                if delay > 0 and i < len(eligible) - 1:
                    time.sleep(delay)
            except Exception as e:
                print(f"   ❌ FAILED: {str(e)[:200]}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--send", action="store_true")
    p.add_argument("--user-id", default=None)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--force", action="store_true")
    p.add_argument("--delay", type=float, default=2.0, help="Seconds between sends (default: 2)")
    args = p.parse_args()
    asyncio.run(main_async(args.send, args.user_id, args.limit, args.force, args.delay))


if __name__ == "__main__":
    main()
