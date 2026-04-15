"""
Coach Strength Test — What level is the coach actually playing?

Run on server:
    python tests/test_coach_strength.py

Plays 5 quick games (coach vs itself) at different user ratings
and measures the actual Elo by analyzing move quality with Stockfish
at full strength.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
import time

STOCKFISH_PATH = "/usr/games/stockfish"

def measure_coach_strength(user_rating: int, num_moves: int = 30):
    """
    Play the coach against itself for num_moves and measure quality.
    Uses full-strength Stockfish to judge each move.
    """
    from coach_play.teaching.move_selector_v2 import TeachingMoveSelectorV2

    selector = TeachingMoveSelectorV2(user_rating=user_rating)
    judge = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    judge.configure({"Skill Level": 20})

    board = chess.Board()
    total_cp_loss = 0
    move_count = 0
    intents = []

    print(f"\n{'='*50}")
    print(f"User Rating: {user_rating} → Coach Skill Level: {selector.skill_level}")
    print(f"{'='*50}")

    for i in range(num_moves):
        if board.is_game_over():
            break

        # Coach picks a move
        coach_color = board.turn
        try:
            result = selector.select_move(
                board=board,
                coach_color=coach_color,
            )
            coach_move = result.selected_move
            coach_san = result.selected_san
            intent = result.intent.value
            rank = result.eval_rank
        except Exception as e:
            print(f"  Move {i+1}: Selector error: {e}")
            break

        # Judge evaluates: what was the best move?
        judge_result = judge.analyse(board, chess.engine.Limit(depth=18))
        best_score = judge_result["score"].white()
        if best_score.is_mate():
            best_cp = 10000 if best_score.mate() > 0 else -10000
        else:
            best_cp = best_score.score()

        # Evaluate the coach's actual move
        board.push(coach_move)
        after_result = judge.analyse(board, chess.engine.Limit(depth=18))
        after_score = after_result["score"].white()
        if after_score.is_mate():
            after_cp = 10000 if after_score.mate() > 0 else -10000
        else:
            after_cp = after_score.score()
        board.pop()

        # CP loss from the moving side's perspective
        if coach_color == chess.WHITE:
            cp_loss = max(0, best_cp - after_cp)
        else:
            cp_loss = max(0, after_cp - best_cp)

        total_cp_loss += cp_loss
        move_count += 1
        intents.append(intent)

        marker = ""
        if cp_loss >= 100:
            marker = " *** BLUNDER"
        elif cp_loss >= 50:
            marker = " ** MISTAKE"
        elif cp_loss >= 20:
            marker = " * INACCURACY"

        if i < 10 or cp_loss >= 20:
            print(f"  {i+1:2d}. {coach_san:8s} rank={rank} intent={intent:30s} cp_loss={cp_loss:4d}{marker}")

        # Actually make the move
        board.push(coach_move)

    selector._close_engine()
    judge.quit()

    avg_cp_loss = total_cp_loss / max(move_count, 1)

    # Estimate Elo from average centipawn loss
    # Rough mapping: ACPL 10 ≈ 2500, ACPL 30 ≈ 2000, ACPL 60 ≈ 1500, ACPL 100 ≈ 1200, ACPL 200 ≈ 800
    if avg_cp_loss <= 10:
        est_elo = 2500
    elif avg_cp_loss <= 20:
        est_elo = int(2500 - (avg_cp_loss - 10) * 50)  # 2500 → 2000
    elif avg_cp_loss <= 50:
        est_elo = int(2000 - (avg_cp_loss - 20) * 17)  # 2000 → 1500
    elif avg_cp_loss <= 100:
        est_elo = int(1500 - (avg_cp_loss - 50) * 6)   # 1500 → 1200
    elif avg_cp_loss <= 200:
        est_elo = int(1200 - (avg_cp_loss - 100) * 4)  # 1200 → 800
    else:
        est_elo = max(400, int(800 - (avg_cp_loss - 200) * 2))

    from collections import Counter
    intent_dist = Counter(intents)

    print(f"\n  RESULTS:")
    print(f"  Moves played: {move_count}")
    print(f"  Avg CP loss:  {avg_cp_loss:.1f}")
    print(f"  Est. Elo:     ~{est_elo}")
    print(f"  Intents:      {dict(intent_dist)}")

    return {
        "user_rating": user_rating,
        "skill_level": selector.skill_level,
        "moves": move_count,
        "avg_cp_loss": round(avg_cp_loss, 1),
        "est_elo": est_elo,
        "intents": dict(intent_dist),
    }


def main():
    print("COACH STRENGTH TEST")
    print("=" * 60)
    print("Playing coach at different user ratings and measuring actual Elo.")
    print("Each test plays 30 moves and judges with full-strength Stockfish.\n")

    ratings = [800, 1200, 1400, 1600, 1800]
    results = []

    for rating in ratings:
        r = measure_coach_strength(rating, num_moves=30)
        results.append(r)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'User Rating':>12} {'Skill Lvl':>10} {'Avg CPL':>8} {'Est Elo':>8} {'Target':>8} {'Delta':>8}")
    print("-" * 60)
    for r in results:
        target = r["user_rating"] + 200  # Coach should play ~200 above student
        delta = r["est_elo"] - target
        status = "OK" if abs(delta) < 200 else ("TOO STRONG" if delta > 0 else "TOO WEAK")
        print(f"{r['user_rating']:>12} {r['skill_level']:>10} {r['avg_cp_loss']:>8.1f} {r['est_elo']:>8} {target:>8} {delta:>+8d} {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
