#!/usr/bin/env python3
"""
Debug: What facts ARE detected for blocked moves?

Check if we're silencing captions that SHOULD be shown
(openings, fundamentals, positional, etc.)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from services.caption_facts import extract_facts
import json


def main():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client["chess_coach"]

    print("=" * 100)
    print("DEBUG: WHAT FACTS ARE DETECTED FOR BLOCKED MOVES?")
    print("=" * 100)
    print()

    analyzed_games = list(db.game_analyses.find({}).limit(50))

    blocked_moves = []

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

            if not fen_before or cp_loss < 50 or cp_loss >= 100:
                continue

            try:
                # Use REGULAR extract_facts, not verified
                facts = extract_facts(
                    fen_before=fen_before,
                    played_san=move_san,
                    best_move_san=None,
                    eval_before_cp=eval_before,
                    eval_after_cp=eval_after,
                    cp_loss=int(cp_loss),
                )

                # What facts exist?
                detected_facts = []

                # Check all possible fact types
                if facts.get("is_check"):
                    detected_facts.append("is_check")
                if facts.get("is_castling"):
                    detected_facts.append("is_castling")
                if facts.get("opening_name"):
                    detected_facts.append(f"opening:{facts.get('opening_name')}")
                if facts.get("phase"):
                    detected_facts.append(f"phase:{facts.get('phase')}")
                if facts.get("pieces_now_undefended"):
                    detected_facts.append(f"hangs:{len(facts.get('pieces_now_undefended'))}")
                if facts.get("threats_created"):
                    detected_facts.append(f"threats:{len(facts.get('threats_created'))}")
                if facts.get("multi_target_attack_evidence"):
                    detected_facts.append("multi_target_attack")
                if facts.get("aligned_pieces_evidence"):
                    detected_facts.append("aligned_pieces")
                if facts.get("discovered_attack_evidence"):
                    detected_facts.append("discovered_attack")
                if facts.get("mate_threat_evidence"):
                    detected_facts.append("mate_threat")
                if facts.get("missed_tactic_evidence"):
                    detected_facts.append("missed_tactic")

                if detected_facts:
                    blocked_moves.append({
                        "game": game_id[:8],
                        "move": f"m{move_num} {move_san}",
                        "cp_loss": cp_loss,
                        "facts": detected_facts,
                    })

            except Exception as e:
                pass

    # Sort by cp_loss
    blocked_moves.sort(key=lambda x: x["cp_loss"], reverse=True)

    print(f"Blocked moves WITH detected facts: {len(blocked_moves)}")
    print()

    if blocked_moves:
        print("TOP 25 BLOCKED MOVES THAT DO HAVE FACTS:")
        print("-" * 100)
        print()

        for idx, m in enumerate(blocked_moves[:25], 1):
            print(f"{idx:2d}. Game {m['game']} {m['move']} ({m['cp_loss']}cp)")
            print(f"    Facts detected: {', '.join(m['facts'])}")
            print()

    else:
        print("NO FACTS DETECTED on blocked moves")
        print()
        print("This means:")
        print("  - No hangs, no forks, no threats")
        print("  - No checks, no castling")
        print("  - No opening context")
        print("  - No discovered attacks, no mate threats")
        print()
        print("These are PURE POSITIONAL mistakes with no tactical reason")


if __name__ == "__main__":
    main()
