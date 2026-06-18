#!/usr/bin/env python3
"""
DETECTOR AUDIT: Run existing detectors on feedback positions
and see what facts ARE being set vs what SHOULD be set.

Purpose: Fix broken detectors, don't build redundant ones.
"""

import sys
import asyncio
import json
from pymongo import MongoClient

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "chess_coach"

# Sample feedback items from Pattern #1 (WANTS_WHY_EXPLANATION)
AUDIT_ITEMS = [
    {
        "feedback_id": "fb_957fb320d332",
        "game_id": "game_692ab776c5b1",
        "move_number": 7,
        "move_san": "a3",
        "severity": "opp_mistake",
        "cp_loss": 174,
        "user_complaint": "why?? No teaching?",
        "coaching_text": "Opponent's a3 is an inaccuracy. Play Bxc5 winning the pawn.",
        "expected_facts": [
            "opp_failure_missed_capture",  # Should detect that a3 misses Bxc5
            "opp_reply_san",               # Should have: Bxc5
            "user_best_reply_san",         # User's best reply after opp blunder
        ]
    },
    {
        "feedback_id": "fb_3c15abde86a2",
        "game_id": "game_692ab776c5b1",
        "move_number": 7,
        "move_san": "a3",
        "severity": "opp_inaccuracy",
        "cp_loss": 76,
        "user_complaint": "like here, if it's a mistake, why??",
        "coaching_text": "Opponent's a3 is a mistake. Your strongest reply is e5.",
        "expected_facts": [
            "opp_failure_missed_move",     # Should detect a3 misses something
            "user_best_reply_san",         # e5
        ]
    }
]

async def audit_position(feedback_item):
    """Audit what detectors are firing for a single position."""

    print(f"\n{'='*80}")
    print(f"AUDITING: {feedback_item['feedback_id']}")
    print(f"{'='*80}")
    print(f"Move: {feedback_item['move_san']} (severity: {feedback_item['severity']}, {feedback_item['cp_loss']}cp)")
    print(f"User complaint: {feedback_item['user_complaint']}")
    print(f"Coaching text: {feedback_item['coaching_text']}")
    print()

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    # Fetch game analysis
    game = await db.games.find_one(
        {"game_id": feedback_item["game_id"]},
        {"_id": 0, "pgn": 1}
    ) if hasattr(db, 'find_one') else db.games.find_one(
        {"game_id": feedback_item["game_id"]},
        {"_id": 0, "pgn": 1}
    )

    analysis = await db.game_analyses.find_one(
        {"game_id": feedback_item["game_id"]},
        {"_id": 0, "stockfish_analysis": 1}
    ) if hasattr(db, 'find_one') else db.game_analyses.find_one(
        {"game_id": feedback_item["game_id"]},
        {"_id": 0, "stockfish_analysis": 1}
    )

    if not analysis:
        print("❌ No game analysis found")
        return

    move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

    # Find the move in the analysis
    target_move = next(
        (m for m in move_evals if m.get("move_number") == feedback_item["move_number"] and m.get("move") == feedback_item["move_san"]),
        None
    )

    if not target_move:
        print(f"❌ Move {feedback_item['move_san']} at move {feedback_item['move_number']} not found in analysis")
        return

    print("✓ Move found in analysis")
    print()
    print("FACTS CURRENTLY SET BY EXISTING DETECTORS:")
    print("-" * 80)

    # Show what facts ARE set
    set_facts = {}
    for key, value in target_move.items():
        if key not in ["move", "move_number", "fen_before", "fen_after"]:
            if value is not None and value != [] and value != "":
                set_facts[key] = value

    if set_facts:
        for key, value in sorted(set_facts.items()):
            print(f"  ✓ {key}: {value}")
    else:
        print("  (no facts set)")

    print()
    print("EXPECTED FACTS (from feedback):")
    print("-" * 80)
    for fact in feedback_item["expected_facts"]:
        if fact in set_facts:
            print(f"  ✓ {fact}: {set_facts[fact]}")
        else:
            print(f"  ❌ {fact}: MISSING (detector not firing?)")

    print()
    print("VERDICT:")
    print("-" * 80)
    missing = [f for f in feedback_item["expected_facts"] if f not in set_facts]
    if missing:
        print(f"⚠️  {len(missing)} expected facts MISSING:")
        for fact in missing:
            print(f"    - {fact}")
        print()
        print("Action: Debug why these detectors aren't firing on this position")
    else:
        print("✅ All expected facts present")
        print("Action: Check why caption isn't using them (template/gate issue)")

async def main():
    print("\n" + "="*80)
    print("DETECTOR AUDIT — Finding broken detectors vs missing templates")
    print("="*80)

    for item in AUDIT_ITEMS:
        try:
            await audit_position(item)
        except Exception as e:
            print(f"Error auditing {item['feedback_id']}: {e}")

if __name__ == "__main__":
    # Use sync version since db operations are sync
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    print("\n" + "="*80)
    print("DETECTOR AUDIT — Finding broken detectors vs missing templates")
    print("="*80)

    for item in AUDIT_ITEMS:
        print(f"\n{'='*80}")
        print(f"AUDITING: {item['feedback_id']}")
        print(f"{'='*80}")
        print(f"Move: {item['move_san']} (severity: {item['severity']}, {item['cp_loss']}cp)")
        print(f"User complaint: {item['user_complaint']}")
        print(f"Coaching text: {item['coaching_text']}")
        print()

        # Fetch game analysis
        analysis = db.game_analyses.find_one(
            {"game_id": item["game_id"]},
            {"_id": 0, "stockfish_analysis": 1}
        )

        if not analysis:
            print("❌ No game analysis found")
            continue

        move_evals = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

        # Find the move
        target_move = next(
            (m for m in move_evals if m.get("move_number") == item["move_number"] and m.get("move") == item["move_san"]),
            None
        )

        if not target_move:
            print(f"❌ Move not found in analysis")
            continue

        print("✓ Move found in analysis")
        print()
        print("FACTS CURRENTLY SET:")
        print("-" * 80)

        # Show what facts ARE set
        set_facts = {}
        for key, value in target_move.items():
            if key not in ["move", "move_number", "fen_before", "fen_after", "cp_loss", "best_move", "classification"]:
                if value is not None and value != [] and value != "":
                    set_facts[key] = value

        if set_facts:
            for key, value in sorted(set_facts.items()):
                if not key.startswith("_"):
                    print(f"  ✓ {key}: {str(value)[:60]}")
        else:
            print("  (minimal facts set)")

        print()
        print("EXPECTED FACTS FROM FEEDBACK:")
        print("-" * 80)
        for fact in item["expected_facts"]:
            if fact in set_facts:
                print(f"  ✓ {fact}: {set_facts[fact]}")
            else:
                print(f"  ❌ {fact}: MISSING")

        print()
        missing = [f for f in item["expected_facts"] if f not in set_facts]
        if missing:
            print(f"⚠️  ACTION: Debug why {missing[0]} detector isn't firing")
        else:
            print(f"✅ All facts present — issue is in rendering/template")

print("\nRun this script to see what detectors ARE firing on feedback positions.")
