"""
Generate per-user re-engagement email payloads from the freshly backfilled
player_profiles + player_identities.

Output is a JSON array — one entry per user with:
  - to_email, to_name, user_id
  - subject (personalized)
  - body_text (plain-text, ~150-200 words)
  - body_html (same content with light formatting)
  - observations  (the raw data points we used — for audit / A-B testing)

Drop the JSON into your mailer (Sendgrid/Mailchimp/etc.) as a campaign.

The tone:
  - Undramatic. We're not selling, we're noticing.
  - Patterns, not moves ("you got forked" not "you played Nxe4").
  - No chess jargon (target 600-1500 audience).
  - One concrete suggestion, not a wall of advice.
  - Always end with a low-friction CTA.

USAGE:
  python generate_reengagement_emails.py                     # all users >= 20 games
  python generate_reengagement_emails.py --min-games 50      # higher bar
  python generate_reengagement_emails.py --uid user_xxx      # one user (preview)
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


# ---- Coach-friendly translations of the 9 cognitive_gap subcategories ----
WEAKNESS_PHRASES = {
    "one_move_blunders": "leaving pieces undefended",
    "ignoring_king_safety_threats": "letting your king get caught in the open",
    "poor_piece_activity": "pieces sitting passive, not joining the fight",
    "fork_misses": "missing forks — both yours to play and theirs to threaten",
    "neglecting_development": "starting the middlegame before all your pieces are out",
    "discovered_attack_misses": "missing discovered attacks",
    "removal_of_defender_misses": "missing chances to knock out a defender first",
    "pawn_structure_damage": "creating weak pawns you can't take back",
    "king_activity_neglect": "leaving your king in the corner during endgames",
    "complex_tactical_miss": "missing multi-move combinations",
}

# Top opening → coach observation
def opening_note(top_openings: list) -> str:
    if not top_openings:
        return ""
    top = top_openings[0][0]
    # Strip ECO suffixes, keep the family name
    simple = top.split(" Defense")[0].split(" Game")[0].split(" Opening")[0]
    return simple


def style_note(style: dict) -> str:
    if not style:
        return ""
    agg = style.get("aggressive_tendency") or 0.5
    pos = style.get("positional_tendency") or 0.5
    if agg >= 0.7 and pos >= 0.6:
        return "You play with energy — you take risks and create chances. The thing holding you back is small slips, not strategy."
    if agg >= 0.7:
        return "You're an attacking player by nature."
    if pos >= 0.7:
        return "You play patient, solid chess."
    return ""


def trend_hook(trend: str, recent_games: int) -> str:
    if trend == "improving":
        return "I went through your last games and you're actually getting better — fewer mistakes, more good moves. The next step is small."
    if trend == "regressing":
        return "Your last few games haven't gone your way. That's frustrating — and usually fixable in 2-3 sessions."
    if trend == "stuck":
        return f"You've played {recent_games} games and your numbers haven't moved much. That's not effort — that's missing focus."
    return ""


def build_subject(name: str, trend: str, top_opening: str, total: int) -> str:
    first_name = (name or "there").split()[0]
    if trend == "improving":
        return f"{first_name}, you're getting better. Here's what's next."
    if trend == "regressing":
        return f"{first_name}, your last 10 games tell a different story"
    if total >= 200:
        return f"{first_name}, I looked at all {total} of your games"
    return f"{first_name}, your coach has some thoughts"


def build_body(user: dict, profile: dict, identity: dict, top_openings: list, last30: dict) -> tuple:
    """Returns (plain_text, html)."""
    name = user.get("name") or "there"
    first_name = name.split()[0]
    trend = profile.get("improvement_trend", "stuck")
    total = profile.get("games_analyzed_count", 0)
    avg_acc = profile.get("average_accuracy")
    top_ws = profile.get("top_weaknesses") or []
    style = (identity.get("style_profile") or {}) if identity else {}

    # Pick top 3 weaknesses (excluding the generic one if we have other signal)
    real_weaknesses = [w for w in top_ws if w.get("subcategory") != "one_move_blunders"]
    if len(real_weaknesses) >= 3:
        focus = real_weaknesses[:3]
    else:
        focus = top_ws[:3]

    # Observations to surface
    observations = []
    if avg_acc:
        observations.append(f"Your average accuracy is {avg_acc}% — that's {'in the top tier' if avg_acc>=70 else 'right in the middle of the pack' if avg_acc>=60 else 'where most players this stage are'}.")
    if focus:
        top_w = focus[0]
        phrase = WEAKNESS_PHRASES.get(top_w["subcategory"], top_w["subcategory"])
        observations.append(f"Your biggest pattern: {phrase}. I saw it {top_w['occurrence_count']} times across your games.")
    if len(focus) >= 2:
        phrase = WEAKNESS_PHRASES.get(focus[1]["subcategory"], focus[1]["subcategory"])
        observations.append(f"After that: {phrase}.")
    op_name = opening_note(top_openings)
    if op_name:
        observations.append(f"Your most-played opening is the {op_name}. You've played it many times — and we could go deeper.")
    sn = style_note(style)
    if sn:
        observations.append(sn)

    # Recent record
    wld = last30 or {}
    w, l, d = wld.get("win", 0), wld.get("loss", 0), wld.get("draw", 0)
    if w + l + d > 0:
        wr = round(100 * w / max(w + l + d, 1))
        if wr >= 60:
            observations.append(f"Recent record: {w}W / {l}L / {d}D — {wr}% wins. Whatever you're doing, keep doing.")
        elif wr <= 40:
            observations.append(f"Recent record: {w}W / {l}L / {d}D — only {wr}% wins. That's not a slump signal yet, but it's a signal.")

    # One concrete suggestion based on top weakness
    suggestion = "Come back for one game and let me show you the pattern in your last loss."
    if focus:
        sub = focus[0]["subcategory"]
        if sub == "ignoring_king_safety_threats":
            suggestion = "Come back for 15 minutes — I'll show you the 3 specific moments your king got caught last week."
        elif sub == "fork_misses":
            suggestion = "Come back for one focused session — I'll walk you through the 5 forks you missed and the 2 you set up."
        elif sub == "poor_piece_activity":
            suggestion = "Come back for one game with the activity-check prompt. You'll feel the difference in 10 moves."
        elif sub == "neglecting_development":
            suggestion = "Come back for one rapid game with the opening-checklist on. Just 15 minutes."

    # ---- Compose plain text ----
    para1 = f"Hi {first_name},\n\n"
    para1 += trend_hook(trend, total) + "\n\n"

    para2 = "Here's what I notice about how you play:\n\n"
    for obs in observations[:4]:
        para2 += f"• {obs}\n"
    para2 += "\n"

    para3 = f"My recommendation: {suggestion}\n\n"
    para4 = ("Open one game on ChessGuru this week — even just 10 minutes — and the next time we look at "
             "your games together, the numbers should move.\n\n")
    para5 = "— Your coach\n"

    plain = para1 + para2 + para3 + para4 + para5

    # ---- Compose HTML ----
    obs_html = "".join(f"<li>{o}</li>" for o in observations[:4])
    html = f"""<p>Hi {first_name},</p>
<p>{trend_hook(trend, total)}</p>
<p><strong>Here's what I notice about how you play:</strong></p>
<ul>{obs_html}</ul>
<p><strong>My recommendation:</strong> {suggestion}</p>
<p>Open one game on ChessGuru this week — even just 10 minutes — and the next time we look at your games together, the numbers should move.</p>
<p>— Your coach<br/><a href="https://chessguru.ai/home">chessguru.ai</a></p>"""

    return plain, html, observations


async def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-games", type=int, default=20)
    p.add_argument("--uid", default=None, help="Only one user (preview)")
    p.add_argument("--out", default="/tmp/reengagement_emails.json")
    args = p.parse_args()

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    if args.uid:
        uids = [args.uid]
    else:
        # >= min-games + has been analyzed at all
        pipeline = [
            {"$match": {"is_analyzed": True}},
            {"$group": {"_id": "$user_id", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": args.min_games}}},
            {"$sort": {"n": -1}},
        ]
        uids = [r["_id"] async for r in db.games.aggregate(pipeline)]

    out = []
    for uid in uids:
        user = await db.users.find_one({"user_id": uid}, {"_id": 0}) or {}
        if not user.get("email"):
            continue  # can't reach them
        profile = await db.player_profiles.find_one({"user_id": uid}, {"_id": 0}) or {}
        identity = await db.player_identities.find_one({"user_id": uid}, {"_id": 0}) or {}

        # Top openings from games
        from collections import Counter
        op_counts = Counter()
        async for g in db.games.find({"user_id": uid}, {"opening": 1}).limit(200):
            op = g.get("opening")
            if isinstance(op, dict): op = op.get("name")
            if op: op_counts[op] += 1
        top_openings = op_counts.most_common(5)

        # Last 30 W/L/D
        from collections import defaultdict
        wld = defaultdict(int)
        async for g in db.games.find({"user_id": uid}, {"result": 1, "user_color": 1, "date_played": 1}).sort("date_played", -1).limit(30):
            res = (g.get("result") or "").strip()
            col = g.get("user_color")
            if res == "1-0":
                wld["win" if col == "white" else "loss"] += 1
            elif res == "0-1":
                wld["win" if col == "black" else "loss"] += 1
            elif res in ("1/2-1/2", "½-½"):
                wld["draw"] += 1

        subject = build_subject(user.get("name", ""), profile.get("improvement_trend", "stuck"), opening_note(top_openings), profile.get("games_analyzed_count", 0))
        plain, html, observations = build_body(user, profile, identity, top_openings, dict(wld))

        out.append({
            "user_id": uid,
            "to_name": user.get("name"),
            "to_email": user.get("email"),
            "subject": subject,
            "body_text": plain,
            "body_html": html,
            "observations": observations,
            "trend": profile.get("improvement_trend"),
            "total_games": profile.get("games_analyzed_count"),
            "avg_accuracy": profile.get("average_accuracy"),
            "top_3_weaknesses": [(w["subcategory"], w["occurrence_count"]) for w in (profile.get("top_weaknesses") or [])[:3]],
            "top_opening": top_openings[0][0] if top_openings else None,
            "last_30_wld": dict(wld),
        })

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, default=str, indent=2, ensure_ascii=False)
    print(f"Wrote {len(out)} email payloads to {args.out}")
    print(f"Sample subjects:")
    for r in out[:6]:
        print(f"  → {r['to_email']}: \"{r['subject']}\"")


if __name__ == "__main__":
    asyncio.run(main())
