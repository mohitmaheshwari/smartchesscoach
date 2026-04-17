"""
Coach's Plan for a User — Diagnostic Script

Run this to see exactly what the coach has planned for a specific user:
- Current focus (what the coach is teaching right now)
- Why this was picked (prescription reason)
- Progress (clean streak for the current focus)
- Weaknesses tracked with pattern decay states
- Things the user has learned
- Queue of next skills
- Recent game-by-game prescription history

Usage:
    cd backend
    python scripts/coach_plan_for_user.py <user_id>

If no user_id given, shows for dev_user_local (DEV_MODE default).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path so we can import services
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _fmt_date(ts):
    """Format a timestamp for display."""
    if not ts:
        return "never"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return ts
    if isinstance(ts, datetime):
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = now - ts
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                return f"{delta.seconds // 60}m ago"
            return f"{hours}h ago"
        if delta.days == 1:
            return "yesterday"
        if delta.days < 7:
            return f"{delta.days}d ago"
        return ts.strftime("%Y-%m-%d")
    return str(ts)


def _banner(title, char="="):
    line = char * 72
    print()
    print(line)
    print(f"  {title}")
    print(line)


async def show_coach_plan(user_id: str):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print()
    print(f"Coach's Plan for: {user_id}")
    print(f"Database: {DB_NAME}")

    # ========== 1. COACH MEMORY — the persistent plan ==========
    _banner("THE PLAN (coach_memory.learning)")
    memory = await db.coach_memory.find_one({"user_id": user_id})
    if not memory:
        print("  No coach memory yet — user hasn't played enough analyzed games.")
        print("  The coach starts forming a plan after the first game is analyzed.")
    else:
        learning = memory.get("learning", {})
        current = learning.get("current_focus")
        if current:
            print(f"  Current focus:  {current}")
        else:
            print("  Current focus:  (none yet — no actionable weakness identified)")

        suggested = learning.get("suggested_next", [])
        if suggested:
            print(f"  Up next:        {', '.join(suggested)}")

        print(f"  Games played:   {memory.get('performance', {}).get('games_played', 0)}")
        print(f"  Avg accuracy:   {memory.get('performance', {}).get('avg_accuracy', 0):.1f}%")
        print(f"  Last updated:   {_fmt_date(memory.get('updated_at'))}")

    # ========== 2. LATEST PRESCRIPTION — what the coach said after last game ==========
    _banner("LATEST PRESCRIPTION (from most recent postgame_analysis)")
    latest = await db.postgame_analyses.find_one(
        {"user_id": user_id, "coach_prescription": {"$exists": True, "$ne": None}},
        sort=[("created_at", -1)]
    )
    if not latest:
        print("  No prescription yet — either no games played, or all games were clean.")
    else:
        print(f"  Prescription:       {latest.get('coach_prescription')}")
        print(f"  Type:               {latest.get('prescription_type')}")
        print(f"  Reason:             {latest.get('prescription_reason')}")
        print(f"  From game ending:   {_fmt_date(latest.get('created_at'))}")
        if latest.get("endgame_type"):
            print(f"  Endgame detected:   {latest.get('endgame_type')}")
        if latest.get("endgame_lesson_needed"):
            print(f"  Endgame lesson:     {latest.get('endgame_lesson_needed')}")

    # ========== 3. WEAKNESSES — tracked patterns ==========
    _banner("WEAKNESSES THE COACH IS WATCHING")
    if memory:
        weaknesses = memory.get("weaknesses", [])
        if not weaknesses:
            print("  No weaknesses tracked yet.")
        else:
            # Sort by detection count and recency
            weaknesses.sort(key=lambda w: (w.get("detection_count", 0)), reverse=True)
            for w in weaknesses[:10]:
                name = w.get("name") or w.get("habit_id", "?")
                count = w.get("detection_count", 0)
                improving = "↗ improving" if w.get("improving") else "  active"
                last = _fmt_date(w.get("last_detected"))
                print(f"  {name:40s}  {count:>3} times  {improving}   last: {last}")

    # ========== 4. PATTERN DECAY STATES — which patterns are ACTIVE/DECLINING/FADING ==========
    _banner("PATTERN DECAY STATES (from cognitive gap aggregates)")
    try:
        from services.pattern_decay_service import compute_pattern_scores

        # Fetch recent games for decay computation
        games = await db.games.find(
            {"user_id": user_id, "is_analyzed": True},
            {"game_id": 1, "imported_at": 1, "cognitive_gaps": 1}
        ).sort("imported_at", -1).limit(20).to_list(20)

        if not games:
            print("  No analyzed games yet.")
        else:
            # Build enriched games for decay
            enriched = []
            for g in games:
                gaps = g.get("cognitive_gaps") or []
                for gap in gaps:
                    enriched.append({
                        "pattern": gap if isinstance(gap, str) else gap.get("pattern", "unknown"),
                        "game_id": g.get("game_id"),
                    })

            if enriched:
                scores = compute_pattern_scores(enriched)
                if scores:
                    for name, data in sorted(scores.items(), key=lambda x: -x[1].get("weighted_score", 0))[:10]:
                        state = data.get("state", "?").upper()
                        score = data.get("weighted_score", 0)
                        recent = data.get("recent_raw", 0)
                        streak = data.get("clean_streak", 0)
                        state_color = {"ACTIVE": "🔴", "DECLINING": "🟡", "FADING": "🟢"}.get(state, "⚪")
                        print(f"  {state_color} {name:35s}  score: {score:5.2f}  recent: {recent}  clean streak: {streak}  [{state}]")
                else:
                    print("  No pattern scores computed.")
            else:
                print("  No cognitive gap data in recent games.")
    except Exception as e:
        print(f"  Could not compute decay: {e}")

    # ========== 5. WHAT THE STUDENT HAS LEARNED (by rule: 5/3/no-recent-fail) ==========
    _banner("THINGS LEARNED (seen ≥ 5, correct ≥ 3, no recent failure)")
    if memory:
        learning = memory.get("learning", {})
        openings = learning.get("openings_learned", [])
        traps = learning.get("traps_learned", [])
        endgames = learning.get("endgames_learned", [])
        concepts = learning.get("concepts_mastered", [])

        if openings:
            print(f"  Openings:  {', '.join(openings)}")
        if traps:
            print(f"  Traps:     {', '.join(traps)}")
        if endgames:
            print(f"  Endgames:  {', '.join(endgames)}")
        if concepts:
            print(f"  Concepts:  {', '.join(concepts)}")
        if not (openings or traps or endgames or concepts):
            print("  Nothing learned yet (rule: 5 seen, 3 correct, no recent failure).")

    # ========== 5b. SKILL PROGRESS — in-flight, not yet learned ==========
    _banner("SKILLS IN PROGRESS (not yet learned)")
    if memory:
        skills = memory.get("learning", {}).get("skills", [])
        if not skills:
            print("  No skill tracking yet. New games will start populating this.")
        else:
            # Show skills that have been seen but not yet learned
            in_progress = [s for s in skills if not s.get("learned_at")]
            in_progress.sort(key=lambda s: s.get("seen", 0), reverse=True)
            if not in_progress:
                print("  All tracked skills are fully learned!")
            else:
                print(f"  {'Skill':<35} {'Type':<8} {'Seen':>5} {'Correct':>8} {'Wrong':>6}  {'Recent':<20}")
                print(f"  {'-'*35} {'-'*8} {'-'*5} {'-'*8} {'-'*6}  {'-'*20}")
                for s in in_progress[:15]:
                    sid = (s.get("skill_id") or "?")[:35]
                    st = (s.get("skill_type") or "?")[:8]
                    seen = s.get("seen", 0)
                    correct = s.get("correct", 0)
                    wrong = s.get("wrong", 0)
                    outcomes = s.get("outcomes", [])[-5:]
                    recent = " ".join("✓" if o == "correct" else "✗" if o == "wrong" else "·" for o in outcomes)
                    print(f"  {sid:<35} {st:<8} {seen:>5} {correct:>8} {wrong:>6}  {recent:<20}")

    # ========== 6. PRESCRIPTION HISTORY — last 10 games ==========
    _banner("RECENT GAME PRESCRIPTIONS (last 10)")
    history = await db.postgame_analyses.find(
        {"user_id": user_id, "coach_prescription": {"$exists": True}},
        {"coach_prescription": 1, "prescription_type": 1, "prescription_reason": 1,
         "game_result": 1, "created_at": 1, "accuracy": 1, "blunders": 1}
    ).sort("created_at", -1).limit(10).to_list(10)

    if not history:
        print("  No history yet.")
    else:
        print(f"  {'When':<12} {'Result':<7} {'Acc':<6} {'Bl':<4} {'Prescription':<25} {'Reason':<40}")
        print(f"  {'-'*12} {'-'*7} {'-'*6} {'-'*4} {'-'*25} {'-'*40}")
        for g in history:
            when = _fmt_date(g.get("created_at"))
            result = g.get("game_result", "?")[:7]
            acc = f"{g.get('accuracy', 0):.0f}%" if g.get("accuracy") else "?"
            bl = str(g.get("blunders", "?"))
            presc = str(g.get("coach_prescription", ""))[:25]
            reason = str(g.get("prescription_reason", ""))[:40]
            print(f"  {when:<12} {result:<7} {acc:<6} {bl:<4} {presc:<25} {reason:<40}")

    # ========== 7. SUGGESTED ACTIONS — what should the coach do next session ==========
    _banner("COACH'S PLAN FOR NEXT SESSION")
    if memory:
        current = memory.get("learning", {}).get("current_focus")
        if current:
            print(f"  1. During Play with Coach: create {current} opportunities")
            print(f"  2. On home page: show 'Work on {current}' button")
            print(f"  3. Track if user avoids this pattern in next 3 games")
            print(f"  4. If clean for 3 games → graduate to next skill")
            if memory.get("learning", {}).get("suggested_next"):
                print(f"     Next in queue: {memory['learning']['suggested_next'][0]}")
        else:
            print("  Coach is in 'observe' mode — needs more games to identify a focus.")
    else:
        print("  No plan yet. User needs to play + analyze some games first.")

    print()
    client.close()


def main():
    user_id = sys.argv[1] if len(sys.argv) > 1 else "dev_user_local"
    asyncio.run(show_coach_plan(user_id))


if __name__ == "__main__":
    main()
