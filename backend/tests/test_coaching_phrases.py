"""
Coaching Phrases Library Viewer

Run on server:
    python tests/test_coaching_phrases.py

Shows all cached coaching phrases, grouped by type and intent.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    total = await db.coaching_phrases.count_documents({})
    print("=" * 70)
    print(f"COACHING PHRASES LIBRARY — {total} entries")
    print("=" * 70)

    if total == 0:
        print("\nEmpty — play some games with coach to populate.")
        print("Each coach move and student mistake generates a phrase via LLM.")
        print("Second time the same scenario appears, it serves from this cache.")
        return

    # Group by type
    coach_phrases = await db.coaching_phrases.find(
        {"type": "coach_move"}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    user_phrases = await db.coaching_phrases.find(
        {"type": "user_feedback"}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    # ─── Coach move phrases ───
    print(f"\n{'─' * 70}")
    print(f"COACH MOVE PHRASES ({len(coach_phrases)})")
    print(f"{'─' * 70}")

    # Group by intent
    by_intent = {}
    for p in coach_phrases:
        intent = p.get("intent", "unknown")
        by_intent.setdefault(intent, []).append(p)

    for intent, phrases in sorted(by_intent.items()):
        print(f"\n  [{intent.upper()}] — {len(phrases)} phrases")
        for p in phrases:
            key = p.get("scenario_key", "")
            resp = p.get("response", {})
            explanation = resp.get("explanation", "")[:80]
            question = resp.get("hint_for_user", "")[:60]
            hint = resp.get("opponent_opportunity", {})
            hint_msg = hint.get("message", "")[:60] if isinstance(hint, dict) else ""

            print(f"    Key: {key}")
            print(f"    Text: {explanation}")
            if question:
                print(f"    Question: {question}")
            if hint_msg:
                print(f"    Hint: {hint_msg}")
            print(f"    Facts: {p.get('facts', [])[:3]}")
            print()

    # ─── User feedback phrases ───
    print(f"\n{'─' * 70}")
    print(f"USER FEEDBACK PHRASES ({len(user_phrases)})")
    print(f"{'─' * 70}")

    by_fundamental = {}
    for p in user_phrases:
        fund = p.get("fundamental", "unknown")
        by_fundamental.setdefault(fund, []).append(p)

    for fund, phrases in sorted(by_fundamental.items()):
        print(f"\n  [{fund.upper()}] — {len(phrases)} phrases")
        for p in phrases:
            key = p.get("scenario_key", "")
            resp = p.get("response", {})
            question = resp.get("question", "")[:80]
            hint = resp.get("hint", "")[:80]

            print(f"    Key: {key}")
            print(f"    Question: {question}")
            if hint:
                print(f"    Hint: {hint}")
            print(f"    Severity: {p.get('severity')}, Phase: {p.get('phase')}")
            print()

    # ─── Coverage summary ───
    print(f"\n{'─' * 70}")
    print("COVERAGE SUMMARY")
    print(f"{'─' * 70}")

    all_intents = ["hanging_piece_punishment", "fork_opportunity", "threat_awareness"]
    all_phases = ["opening", "middlegame", "endgame"]
    all_move_types = ["capture", "quiet", "check", "castle"]
    all_fundamentals = ["check_opponents_move", "hanging_pieces", "king_safety",
                        "calculate", "development", "center_control", "have_a_plan"]

    print("\n  Coach move coverage:")
    for intent in all_intents:
        count = len(by_intent.get(intent, []))
        bar = "#" * min(count, 20)
        print(f"    {intent:30s} {count:3d} {bar}")

    print("\n  User feedback coverage:")
    for fund in all_fundamentals:
        count = len(by_fundamental.get(fund, []))
        bar = "#" * min(count, 20)
        print(f"    {fund:30s} {count:3d} {bar}")

    # Unique scenario keys
    all_keys = set()
    for p in coach_phrases + user_phrases:
        all_keys.add(p.get("scenario_key", ""))

    print(f"\n  Total unique scenarios cached: {len(all_keys)}")
    print(f"  Total phrases: {total}")
    print(f"\n  When a scenario repeats → instant response (no LLM call)")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
