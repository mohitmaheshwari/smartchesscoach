"""
Live test for Teaching Move Selector v2.

Run on server where Stockfish is available:
    cd /app/backend
    python tests/test_v2_live.py

Outputs structured logs for every position:
    - intent selected
    - best raw score + spread
    - pattern detected (yes/weak)
    - engine rank of selected move
    - all candidate breakdowns
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import json
import logging

from coach_play.teaching.move_selector_v2 import TeachingMoveSelectorV2
from coach_play.teaching.types import TeachingIntent

# Enable info logging for our code, suppress Stockfish UCI noise
logging.basicConfig(level=logging.INFO, format="%(message)s")
# Suppress chess.engine debug output (the UCI protocol lines)
logging.getLogger("chess.engine").setLevel(logging.WARNING)

# ─── TEST POSITIONS ─────────────────────────────────────────────
# 15 real middlegame positions covering different scenarios

POSITIONS = [
    {
        "name": "Italian Game — early middlegame",
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "coach_color": "white",
        "note": "Standard opening — should the coach create threats or develop?",
    },
    {
        "name": "Black knight undefended on d5",
        "fen": "r1bqkb1r/ppp2ppp/2n5/3np3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 5",
        "coach_color": "white",
        "note": "Knight on d5 can be challenged — hanging piece opportunity",
    },
    {
        "name": "Open position with loose pieces",
        "fen": "r1b1kb1r/ppppqppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
        "coach_color": "white",
        "note": "Multiple pieces in play — tactical possibilities",
    },
    {
        "name": "Middlegame — black has weak f7",
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 0 4",
        "coach_color": "black",
        "note": "Coach is black — how does it create counter-threats?",
    },
    {
        "name": "Knight can fork king and rook",
        "fen": "r3k2r/ppp2ppp/2n1b3/3Np3/2B1P3/8/PPPP1PPP/R1BQK2R w KQkq - 0 8",
        "coach_color": "white",
        "note": "Nd5 might create fork opportunities",
    },
    {
        "name": "Rook on open file",
        "fen": "r1bq1rk1/ppp2ppp/2n1bn2/3pp3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 8",
        "coach_color": "white",
        "note": "Positional middlegame — can coach create threats?",
    },
    {
        "name": "Opponent king uncastled",
        "fen": "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
        "coach_color": "white",
        "note": "Black hasn't castled — threat opportunities",
    },
    {
        "name": "Complex middlegame — many pieces",
        "fen": "r2qkb1r/pppb1ppp/2n1pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R w KQkq - 0 6",
        "coach_color": "white",
        "note": "Queen's Gambit structure — positional play",
    },
    {
        "name": "Endgame-ish — fewer pieces",
        "fen": "4k3/ppp2ppp/4p3/3p4/3P1B2/4P3/PPP2PPP/4K3 w - - 0 15",
        "coach_color": "white",
        "note": "Simple endgame — what does the system do with limited material?",
    },
    {
        "name": "Tactical — pieces hanging everywhere",
        "fen": "r1b1k2r/ppp2ppp/2n1pn2/3p4/1bPP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 0 6",
        "coach_color": "white",
        "note": "Nimzo-Indian — Bb4 pins knight, tactical tension",
    },
    {
        "name": "Coach is winning — should it simplify?",
        "fen": "r1bq1rk1/ppp2ppp/2n2n2/3pp3/1bP1P3/2NP1N2/PP3PPP/R1BQKB1R w - - 0 7",
        "coach_color": "white",
        "note": "Small advantage — does it play for teaching or crushing?",
    },
    {
        "name": "Post-opening — pieces developed",
        "fen": "r2q1rk1/pppbbppp/2n1pn2/3p4/2PP4/2NBPN2/PP3PPP/R1BQ1RK1 w - - 0 9",
        "coach_color": "white",
        "note": "Fully developed — middlegame plans",
    },
    {
        "name": "Sharp Sicilian position",
        "fen": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
        "coach_color": "white",
        "note": "Najdorf — sharp, tactical possibilities",
    },
    {
        "name": "Closed center — positional",
        "fen": "r1bqkb1r/pp3ppp/2nppn2/2p5/2PPP3/2N2N2/PP3PPP/R1BQKB1R w KQkq - 0 6",
        "coach_color": "white",
        "note": "Closed position — limited tactics. Does system fall back gracefully?",
    },
    {
        "name": "Piece under attack — must respond",
        "fen": "r1bqk2r/pppp1ppp/2n2n2/4p3/1bB1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 4 4",
        "coach_color": "white",
        "note": "Bb4 attacks Nc3 — coach must deal with threat AND teach",
    },
]

# ─── FOCUS SCENARIOS ────────────────────────────────────────────
# Test with different student profiles

PROFILES = [
    {"name": "No focus (default)", "focus": None, "weaknesses": [], "violations": []},
    {"name": "Tactics focus", "focus": "tactics", "weaknesses": ["calculation"], "violations": []},
    {"name": "Threat awareness", "focus": "prophylaxis", "weaknesses": ["threat_awareness"], "violations": ["check_opponents_move"]},
]


def run_test():
    print("=" * 80)
    print("TEACHING MOVE SELECTOR V2 — LIVE TEST")
    print("=" * 80)

    selector = TeachingMoveSelectorV2()

    # Aggregated stats
    all_results = []
    intent_counts = {}
    pattern_yes = 0
    pattern_weak = 0
    total = 0
    spreads = []
    raw_scores = []
    ranks = []

    profile = PROFILES[0]  # Default profile first

    print(f"\n--- Profile: {profile['name']} ---\n")

    for pos in POSITIONS:
        board = chess.Board(pos["fen"])
        coach_color = chess.WHITE if pos["coach_color"] == "white" else chess.BLACK

        print(f"\n{'─' * 60}")
        print(f"Position: {pos['name']}")
        print(f"FEN: {pos['fen']}")
        print(f"Note: {pos['note']}")
        print(f"Coach plays: {'White' if coach_color == chess.WHITE else 'Black'}")

        try:
            result = selector.select_move(
                board=board,
                coach_color=coach_color,
                teaching_focus=profile["focus"],
                student_weaknesses=profile["weaknesses"],
                last_game_violations=profile["violations"],
            )

            # Compute metrics
            all_raw = [s.raw_score for s in result.all_candidates] if result.all_candidates else [0]
            spread = max(all_raw) - min(all_raw)
            best_raw = result.score_breakdown.raw_score
            is_pattern = best_raw >= 0.3

            spreads.append(spread)
            raw_scores.append(best_raw)
            ranks.append(result.eval_rank)
            total += 1

            intent_name = result.intent.value
            intent_counts[intent_name] = intent_counts.get(intent_name, 0) + 1

            if is_pattern:
                pattern_yes += 1
            else:
                pattern_weak += 1

            # Print results
            print(f"\n  SELECTED: {result.selected_san}")
            print(f"  Intent: {result.intent.value}")
            print(f"  Reason: {result.intent_reason}")
            print(f"  Raw score: {best_raw:.2f}")
            print(f"  Spread: {spread:.2f}")
            print(f"  Engine quality: {result.score_breakdown.engine_quality:.2f}")
            print(f"  Final score: {result.score_breakdown.final_score:.2f}")
            print(f"  Engine rank: {result.eval_rank}")
            print(f"  Fallbacks: {result.feasibility_fallbacks}")
            print(f"  Pattern: {'YES' if is_pattern else 'WEAK'}")
            print(f"  Sub-scores: {result.score_breakdown.sub_scores}")
            print(f"  Explanation: {result.score_breakdown.explanation}")

            # All candidates
            print(f"\n  All candidates ({len(result.all_candidates)}):")
            for i, s in enumerate(result.all_candidates):
                marker = " <<<" if s.final_score == result.score_breakdown.final_score else ""
                print(f"    [{i}] raw={s.raw_score:.2f} eng={s.engine_quality:.2f} "
                      f"final={s.final_score:.2f} — {s.explanation}{marker}")

            all_results.append({
                "position": pos["name"],
                "move": result.selected_san,
                "intent": intent_name,
                "raw": round(best_raw, 2),
                "spread": round(spread, 2),
                "rank": result.eval_rank,
                "pattern": "YES" if is_pattern else "WEAK",
                "fallbacks": result.feasibility_fallbacks,
            })

        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # ─── SUMMARY ────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\nPositions tested: {total}")
    print(f"Pattern YES: {pattern_yes}/{total} ({pattern_yes/total*100:.0f}%)")
    print(f"Pattern WEAK: {pattern_weak}/{total} ({pattern_weak/total*100:.0f}%)")

    print(f"\nScore spread: min={min(spreads):.2f} max={max(spreads):.2f} avg={sum(spreads)/len(spreads):.2f}")
    print(f"Raw scores: min={min(raw_scores):.2f} max={max(raw_scores):.2f} avg={sum(raw_scores)/len(raw_scores):.2f}")
    print(f"Engine ranks: min={min(ranks)} max={max(ranks)} avg={sum(ranks)/len(ranks):.1f}")

    print(f"\nIntent distribution:")
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        print(f"  {intent}: {count}/{total} ({count/total*100:.0f}%)")

    # ─── Now test with different profiles ───────────────────────
    print("\n" + "=" * 80)
    print("PROFILE COMPARISON (same 3 positions, different student profiles)")
    print("=" * 80)

    test_positions = POSITIONS[:3]  # First 3 positions only

    for profile in PROFILES:
        print(f"\n--- {profile['name']} ---")
        for pos in test_positions:
            board = chess.Board(pos["fen"])
            coach_color = chess.WHITE if pos["coach_color"] == "white" else chess.BLACK
            try:
                result = selector.select_move(
                    board=board,
                    coach_color=coach_color,
                    teaching_focus=profile["focus"],
                    student_weaknesses=profile["weaknesses"],
                    last_game_violations=profile["violations"],
                )
                print(f"  {pos['name'][:35]:35s} → {result.selected_san:6s} "
                      f"intent={result.intent.value:30s} raw={result.score_breakdown.raw_score:.2f} "
                      f"rank={result.eval_rank}")
            except Exception as e:
                print(f"  {pos['name'][:35]:35s} → ERROR: {e}")

    selector._close_engine()
    print("\nDone.")


if __name__ == "__main__":
    run_test()
