#!/usr/bin/env python3
"""
Analyze captions blocked by Gate 1 (cp_loss < 100).

Shows what captions WOULD have been generated,
why they were blocked, and if Gate 1 is too strict.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from services.caption_facts_verified import extract_facts_verified
import chess


def main():
    client = MongoClient("mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27018")
    db = client["chess_coach"]

    print("=" * 100)
    print("GATE 1 BLOCKED CAPTIONS - DETAILED ANALYSIS")
    print("=" * 100)
    print()

    analyzed_games = list(db.game_analyses.find({}).limit(50))

    blocked_by_gate1 = []

    for analysis in analyzed_games:
        game_id = analysis.get("game_id")
        moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

        for move_data in moves:
            move_san = move_data.get("move")
            fen_before = move_data.get("fen_before")
            eval_before = move_data.get("eval_before", 0)
            eval_after = move_data.get("eval_after", 0)
            cp_loss = move_data.get("cp_loss", 0)
            move_num = move_data.get("move_number")

            if not fen_before or cp_loss >= 100:  # Skip if already verified or trivial
                continue

            if cp_loss < 50:  # Skip truly trivial moves
                continue

            # This was blocked by Gate 1
            try:
                facts = extract_facts_verified(
                    fen_before=fen_before,
                    played_san=move_san,
                    best_move_san=None,
                    eval_before_cp=eval_before,
                    eval_after_cp=eval_after,
                )

                verified = facts.get("verified", False)
                reason = facts.get("verification_reason", "")
                details = facts.get("verification_details", {})

                if not verified and reason == "cp_loss < 100 (not a real mistake)":
                    blocked_by_gate1.append({
                        "game": game_id[:8],
                        "move": f"m{move_num} {move_san}",
                        "cp_loss": cp_loss,
                        "eval_before": eval_before,
                        "eval_after": eval_after,
                        "details": details,
                    })

            except Exception:
                pass

    # Sort by cp_loss descending
    blocked_by_gate1.sort(key=lambda x: x["cp_loss"], reverse=True)

    print(f"Total moves blocked by Gate 1: {len(blocked_by_gate1)}")
    print()

    print("TOP 20 BLOCKED CAPTIONS (what WOULD have been shown):")
    print("-" * 100)
    print()

    for idx, b in enumerate(blocked_by_gate1[:20], 1):
        detections = [k for k, v in b["details"].items() if v]
        detection_str = ", ".join(detections) if detections else "no detection"

        print(f"{idx:2d}. Game {b['game']} {b['move']} ({b['cp_loss']:3d}cp)")
        print(f"    Detections: {detection_str}")
        print(f"    Reason: Gate 1 blocked (cp_loss < 100)")
        print()

    # Analyze distribution
    print("=" * 100)
    print("GATE 1 THRESHOLD ANALYSIS")
    print("=" * 100)
    print()

    ranges = {
        "50-74cp": [b for b in blocked_by_gate1 if 50 <= b["cp_loss"] < 75],
        "75-99cp": [b for b in blocked_by_gate1 if 75 <= b["cp_loss"] < 100],
    }

    for range_name, moves in ranges.items():
        print(f"{range_name}: {len(moves)} moves blocked")
        if moves:
            avg_cp_loss = sum(m["cp_loss"] for m in moves) // len(moves)
            print(f"  Average cp_loss: {avg_cp_loss}cp")
            has_detection = sum(1 for m in moves if any(m["details"].values()))
            print(f"  With detections: {has_detection}/{len(moves)}")
        print()

    print("=" * 100)
    print("SHOULD GATE 1 BE ADJUSTED?")
    print("=" * 100)
    print()

    over_75cp = len([b for b in blocked_by_gate1 if b["cp_loss"] >= 75])
    over_90cp = len([b for b in blocked_by_gate1 if b["cp_loss"] >= 90])

    print(f"Moves 75-99cp: {over_75cp}")
    print(f"Moves 90-99cp: {over_90cp}")
    print()

    if over_90cp > len(blocked_by_gate1) * 0.3:
        print("RECOMMENDATION: Consider lowering Gate 1 threshold to 75cp")
        print("  Reason: >30% of blocked moves are 90-99cp (close to threshold)")
        print("  Impact: Would show ~{} more captions".format(over_90cp))
    else:
        print("RECOMMENDATION: Gate 1 threshold of 100cp is GOOD")
        print("  Reason: Most blocked moves are <90cp (true inaccuracies)")
        print("  Impact: Current threshold correctly filters noise")
    print()


if __name__ == "__main__":
    main()
