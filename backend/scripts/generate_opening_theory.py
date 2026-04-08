"""
Generate Opening Theory Critical Positions
=============================================

Uses Lichess Opening Explorer API + Stockfish to auto-generate
critical positions for each opening in our theory tree.

For each opening:
1. Walk the main line move by move
2. At each position, query Lichess for move popularity + win rates
3. Find "mistake" moves (popular but low win rate)
4. Run Stockfish to confirm + get best move
5. Generate coaching content (why_bad, consequence, learning)

Usage:
  cd backend
  python scripts/generate_opening_theory.py

  # Or from Docker:
  docker cp scripts/generate_opening_theory.py chess-coach-backend:/app/backend/scripts/
  docker exec -it chess-coach-backend python3 scripts/generate_opening_theory.py

Requirements:
  - Internet access (Lichess API)
  - Stockfish installed
  - python-chess
"""

import json
import os
import sys
import time
import chess
import chess.engine
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
THEORY_FILE = os.path.join(SCRIPT_DIR, "..", "data", "coaching", "opening_theory_tree.json")
import shutil
# Auto-detect: Docker path or local
STOCKFISH_PATH = shutil.which("stockfish") or "/usr/games/stockfish"

# Config
LICHESS_API = "https://explorer.lichess.ovh/lichess"

# Get a free token at https://lichess.org/account/oauth/token
LICHESS_TOKEN = os.environ.get("LICHESS_TOKEN", "")
MIN_GAMES = 100          # Minimum games for a move to be considered
WIN_RATE_THRESHOLD = 0.42  # Below this = likely a mistake
MAX_POSITIONS_PER_OPENING = 8
MAX_DEPTH_MOVES = 12     # Don't go deeper than move 12
STOCKFISH_DEPTH = 16
API_DELAY = 1.5          # Seconds between Lichess API calls (rate limit)

# Rating range for Lichess explorer
RATINGS = "1200,1400,1600"  # Target audience


def query_lichess(fen: str, retries: int = 3) -> dict:
    """Query Lichess Opening Explorer for a position."""
    headers = {}
    if LICHESS_TOKEN:
        headers["Authorization"] = f"Bearer {LICHESS_TOKEN}"
    for attempt in range(retries):
        try:
            params = {
                "fen": fen,
                "ratings": RATINGS,
                "speeds": "rapid,classical",
                "topGames": 0,
                "recentGames": 0,
            }
            resp = httpx.get(LICHESS_API, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                logger.warning("Rate limited, waiting 10s...")
                time.sleep(10)
                continue
            if resp.status_code in (401, 403):
                logger.error("Auth failed. Set LICHESS_TOKEN env var. Get one at https://lichess.org/account/oauth/token")
                return {}
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Lichess API returned {resp.status_code}")
            return {}
        except Exception as e:
            logger.warning(f"Lichess API error (attempt {attempt+1}): {e}")
            time.sleep(3)
    return {}


def analyze_with_stockfish(fen: str, depth: int = STOCKFISH_DEPTH) -> dict:
    """Get Stockfish eval + best move for a position."""
    try:
        board = chess.Board(fen)
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        try:
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            score = info["score"].white()
            cp = score.score(mate_score=10000) if not score.is_mate() else (10000 if score.mate() > 0 else -10000)
            best_move = board.san(info["pv"][0])
            return {"best_move": best_move, "eval_cp": cp, "fen": fen}
        finally:
            engine.quit()
    except Exception as e:
        logger.error(f"Stockfish failed: {e}")
        return {"best_move": None, "eval_cp": 0, "fen": fen}


def eval_after_move(fen: str, move_san: str, depth: int = STOCKFISH_DEPTH) -> int:
    """Get Stockfish eval after playing a specific move. Returns eval in cp from White's perspective."""
    try:
        board = chess.Board(fen)
        move = board.parse_san(move_san)
        board.push(move)
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        try:
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            score = info["score"].white()
            return score.score(mate_score=10000) if not score.is_mate() else (10000 if score.mate() > 0 else -10000)
        finally:
            engine.quit()
    except Exception as e:
        logger.error(f"Stockfish eval_after_move failed: {e}")
        return 0


def compute_win_rate(move_data: dict, is_white: bool) -> float:
    """Compute win rate from Lichess move data."""
    w = move_data.get("white", 0)
    d = move_data.get("draws", 0)
    b = move_data.get("black", 0)
    total = w + d + b
    if total == 0:
        return 0.5
    if is_white:
        return (w + d * 0.5) / total
    else:
        return (b + d * 0.5) / total


def generate_learning(move_san: str, best_move: str, opening_name: str, why_bad: str) -> str:
    """Generate a learning sentence for the position."""
    if "develop" in why_bad.lower() or "piece" in why_bad.lower():
        return f"In the {opening_name}, develop your pieces toward the center before starting any attacks."
    if "castle" in why_bad.lower() or "king" in why_bad.lower():
        return f"In the {opening_name}, prioritize king safety. Castle early."
    if "pawn" in why_bad.lower() or "center" in why_bad.lower():
        return f"In the {opening_name}, fight for the center with pawns before moving minor pieces to the side."
    if "tempo" in why_bad.lower() or "time" in why_bad.lower():
        return f"In the {opening_name}, don't waste moves. Every move should develop or improve your position."
    return f"In the {opening_name}, follow the main idea: {best_move} keeps you on track."


def generate_why_bad(move_san: str, best_move: str, eval_diff: int, win_rate: float, opening_name: str, is_white: bool) -> str:
    """Generate a why_bad explanation."""
    side = "White" if is_white else "Black"

    if eval_diff >= 100:
        return f"{move_san} loses significant advantage. {best_move} was much stronger for {side}."
    elif eval_diff >= 50:
        return f"{move_san} is inaccurate here. {best_move} keeps {side}'s advantage."
    elif win_rate < 0.35:
        return f"{move_san} leads to positions where {side} struggles. Players who play {best_move} win significantly more."
    elif win_rate < 0.42:
        return f"{move_san} is a common mistake. {best_move} is the main line for good reason."
    else:
        return f"{move_san} is not the best choice. {best_move} is more accurate."


def process_opening(key: str, opening: dict) -> list:
    """Process one opening and generate critical positions."""
    name = opening.get("name", key)
    main_line = opening.get("main_line", [])

    if not main_line:
        logger.info(f"  Skipping {name} — no main line")
        return []

    logger.info(f"\n{'='*50}")
    logger.info(f"Processing: {name}")
    logger.info(f"Main line: {' '.join(main_line)}")

    board = chess.Board()
    critical_positions = []

    for move_idx, move_san in enumerate(main_line[:MAX_DEPTH_MOVES]):
        try:
            move = board.parse_san(move_san)
        except Exception:
            logger.warning(f"  Cannot parse move: {move_san}")
            break

        fen_before = board.fen()
        is_white = board.turn == chess.WHITE
        move_number = board.fullmove_number

        # Query Lichess for this position
        time.sleep(API_DELAY)
        lichess_data = query_lichess(fen_before)

        if not lichess_data or not lichess_data.get("moves"):
            board.push(move)
            continue

        moves = lichess_data["moves"]

        # Find the best move (highest win rate with enough games)
        best_lichess = None
        best_win_rate = 0
        for m in moves:
            total = m.get("white", 0) + m.get("draws", 0) + m.get("black", 0)
            if total < MIN_GAMES:
                continue
            wr = compute_win_rate(m, is_white)
            if wr > best_win_rate:
                best_win_rate = wr
                best_lichess = m

        if not best_lichess:
            board.push(move)
            continue

        best_move_san = best_lichess.get("san", "")

        # Find mistake moves (popular but low win rate)
        for m in moves:
            total = m.get("white", 0) + m.get("draws", 0) + m.get("black", 0)
            if total < MIN_GAMES:
                continue

            m_san = m.get("san", "")
            if m_san == best_move_san:
                continue  # Skip the best move

            wr = compute_win_rate(m, is_white)

            if wr < WIN_RATE_THRESHOLD and total >= MIN_GAMES * 2:
                # This is a popular mistake — verify with Stockfish
                logger.info(f"  Potential mistake at move {move_number}: {m_san} (win rate: {wr:.1%}, games: {total})")

                # Get best move eval
                sf_result = analyze_with_stockfish(fen_before)
                if not sf_result.get("best_move"):
                    continue

                best_eval = sf_result["eval_cp"]
                sf_best_move = sf_result["best_move"]

                # Eval the mistake move directly
                mistake_eval = eval_after_move(fen_before, m_san)

                # Compute eval difference from the side-to-move's perspective
                if is_white:
                    eval_diff = best_eval - mistake_eval
                else:
                    eval_diff = mistake_eval - best_eval  # Flip: lower is better for black

                logger.info(f"    Stockfish: best={sf_best_move} ({best_eval}cp), {m_san} ({mistake_eval}cp), diff={eval_diff}")

                if eval_diff >= 20:  # Stockfish confirms it's worse
                    why_bad = generate_why_bad(m_san, sf_best_move, eval_diff, wr, name, is_white)
                    learning = generate_learning(m_san, sf_best_move, name, why_bad)

                    position_key = f"move{move_number}_{m_san.lower().replace('+', '').replace('#', '').replace('x', 'x')}"

                    critical_positions.append({
                        "key": position_key,
                        "fen_pattern": fen_before,
                        "move_number": move_number,
                        "key_decision": f"Move {move_number}: choosing between {sf_best_move} and {m_san}",
                        "best_moves": {
                            sf_best_move: {
                                "quality": "best",
                                "info": {
                                    "why_good": f"The main line move. Players who play {sf_best_move} win {best_win_rate:.0%} of the time.",
                                    "win_rate": round(best_win_rate, 2),
                                }
                            }
                        },
                        "mistake_moves": {
                            m_san: {
                                "quality": "mistake",
                                "info": {
                                    "why_bad": why_bad,
                                    "consequence": f"Your position becomes harder to play. Win rate drops to {wr:.0%}.",
                                    "better_move": sf_best_move,
                                    "learning": learning,
                                    "eval_diff": eval_diff,
                                    "win_rate": round(wr, 2),
                                    "games_seen": total,
                                }
                            }
                        },
                    })

                    logger.info(f"    ✅ Confirmed: {m_san} is a mistake (eval diff: {eval_diff}, win rate: {wr:.1%})")
                else:
                    logger.info(f"    ❌ Stockfish says it's fine (diff={eval_diff}cp)")

                if len(critical_positions) >= MAX_POSITIONS_PER_OPENING:
                    break

        board.push(move)

        if len(critical_positions) >= MAX_POSITIONS_PER_OPENING:
            break

    logger.info(f"  → Generated {len(critical_positions)} critical positions for {name}")
    return critical_positions


def main():
    # Load existing theory tree
    logger.info(f"Loading theory tree from: {THEORY_FILE}")
    with open(THEORY_FILE, "r") as f:
        tree = json.load(f)

    meta = tree.pop("_meta", {})
    total_new = 0

    for key, opening in tree.items():
        positions = process_opening(key, opening)

        if positions:
            # Merge into existing critical_positions
            existing = opening.get("critical_positions", {})
            for pos in positions:
                pos_key = pos.pop("key")
                existing[pos_key] = pos
            opening["critical_positions"] = existing
            total_new += len(positions)

    # Restore meta
    tree["_meta"] = {
        **meta,
        "auto_generated": True,
        "positions_added": total_new,
        "generator": "generate_opening_theory.py",
    }

    # Save
    output_file = THEORY_FILE
    with open(output_file, "w") as f:
        json.dump(tree, f, indent=2)

    logger.info(f"\n{'='*50}")
    logger.info(f"Done! Added {total_new} critical positions.")
    logger.info(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
