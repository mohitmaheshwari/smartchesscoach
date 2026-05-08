"""
Mock-games audit — stress-test the Path B caption pipeline + the
punishment-puzzle service against a synthetic corpus.

Generates N games where two Stockfish instances at different skill
levels play each other (approximating two rated players). For every
ply, runs the same caption + puzzle detection used in production.
Outputs a report mirroring caption_coverage_audit.py so we can compare
the template fire rate before Parth re-tests.

Usage:
    python scripts/mock_games_audit.py
    python scripts/mock_games_audit.py --output /tmp/mock_audit.txt
    python scripts/mock_games_audit.py --depth 14 --time 0.3
    python scripts/mock_games_audit.py --max-plies 80

Caveats:
  - Stockfish skill-level approximations of low ratings aren't exact;
    the games look 1100-1500 ish but aren't a statistical claim about
    real player behaviour.
  - Skill Level adds randomness, so re-runs produce different games.
"""

import argparse
import os
import random
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import chess
import chess.engine
import chess.pgn

# Defaults
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
DEFAULT_DEPTH = 12
DEFAULT_TIME_PER_MOVE = 0.2  # seconds — generation only; analysis uses higher
DEFAULT_MAX_PLIES = 120
DEFAULT_MULTIPV = 3
ANALYSIS_DEPTH = 14

# Default pairs (matches the spread proposed in the planning message)
DEFAULT_PAIRS: List[Tuple[int, int]] = [
    (1200, 1100),
    (1200, 1200),
    (1200, 1300),
    (1200, 1400),
    (1100, 1200),
    (1300, 1200),
    (1400, 1200),
    (1100, 1100),
    (1400, 1400),
    (1100, 1400),
]


def rating_to_skill(rating: int) -> int:
    """Approximate Stockfish skill level (0-20) for a target rating.
    Mirrors coach_play.coach_opponent.rating_to_skill_level."""
    if rating < 800:
        return 0
    if rating < 1000:
        return 3
    if rating < 1200:
        return 5
    if rating < 1400:
        return 8
    if rating < 1600:
        return 10
    if rating < 1800:
        return 12
    if rating < 2000:
        return 15
    if rating < 2200:
        return 17
    return 20


# ── Game generation ─────────────────────────────────────────────────


@contextmanager
def _engine(skill_level: int, threads: int = 1):
    eng = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    try:
        eng.configure({"Skill Level": skill_level, "Threads": threads})
        yield eng
    finally:
        eng.quit()


def play_game(
    white_rating: int,
    black_rating: int,
    depth: int = DEFAULT_DEPTH,
    time_per_move: float = DEFAULT_TIME_PER_MOVE,
    max_plies: int = DEFAULT_MAX_PLIES,
) -> chess.pgn.Game:
    """Two engines play a full game. Returns a PGN game object."""
    skill_w = rating_to_skill(white_rating)
    skill_b = rating_to_skill(black_rating)

    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "MockAudit"
    game.headers["White"] = f"SF-skill-{skill_w} (~{white_rating})"
    game.headers["Black"] = f"SF-skill-{skill_b} (~{black_rating})"
    game.headers["WhiteElo"] = str(white_rating)
    game.headers["BlackElo"] = str(black_rating)
    node = game

    with _engine(skill_w) as eng_w, _engine(skill_b) as eng_b:
        ply = 0
        limit = chess.engine.Limit(depth=depth, time=time_per_move)
        while not board.is_game_over() and ply < max_plies:
            engine = eng_w if board.turn == chess.WHITE else eng_b
            try:
                result = engine.play(board, limit)
            except Exception as e:
                game.headers["Termination"] = f"engine_error: {e}"
                break
            if result.move is None:
                break
            board.push(result.move)
            node = node.add_variation(result.move)
            ply += 1

    if board.is_checkmate():
        game.headers["Result"] = "1-0" if board.turn == chess.BLACK else "0-1"
    elif board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        game.headers["Result"] = "1/2-1/2"
    else:
        game.headers["Result"] = "*"
    return game


# ── Per-move analysis ────────────────────────────────────────────────


def analyse_game(
    game: chess.pgn.Game,
    depth: int = ANALYSIS_DEPTH,
    multipv: int = DEFAULT_MULTIPV,
) -> List[Dict]:
    """Walk the game move by move; return per-move records suitable for
    the caption pipeline. Each record has:
      move_number, move_san, fen_before, fen_after, is_white_move,
      best_move_san, cp_loss, severity, pv_after_best (top-3 moves
      from user POV), pv_after_played (3-ply continuation).
    """
    records: List[Dict] = []
    board = game.board()

    with _engine(20) as eng:  # full-strength for analysis
        eng.configure({"MultiPV": multipv})
        prev_eval_white_pov: Optional[int] = None
        for move in game.mainline_moves():
            fen_before = board.fen()
            move_san = board.san(move)
            move_number = (board.ply() // 2) + 1
            is_white_move = board.turn == chess.WHITE

            # Multi-PV analysis from current position (pre-move)
            try:
                infos = eng.analyse(
                    board,
                    chess.engine.Limit(depth=depth),
                    multipv=multipv,
                )
            except Exception:
                infos = []

            # Top-N moves from white's POV
            top_moves: List[Tuple[str, int]] = []
            best_move_san = None
            best_eval_white = None
            for info in infos[:multipv]:
                pv = info.get("pv") or []
                if not pv:
                    continue
                first = pv[0]
                try:
                    san = board.san(first)
                except Exception:
                    continue
                score = info.get("score")
                if score is None:
                    continue
                pov_w = score.white()
                if pov_w.is_mate():
                    cp = 30000 if pov_w.mate() and pov_w.mate() > 0 else -30000
                else:
                    cp = pov_w.score(mate_score=30000) or 0
                top_moves.append((san, cp))
                if best_move_san is None:
                    best_move_san = san
                    best_eval_white = cp

            # Compute cp_loss for the move just played
            played_eval_white: Optional[int] = None
            played_pv_san: List[str] = []
            try:
                board.push(move)
                played_info = eng.analyse(board, chess.engine.Limit(depth=depth))
                ps = played_info.get("score")
                if ps is not None:
                    pov_w = ps.white()
                    played_eval_white = (
                        30000 if pov_w.is_mate() and (pov_w.mate() or 0) > 0
                        else -30000 if pov_w.is_mate()
                        else (pov_w.score(mate_score=30000) or 0)
                    )
                played_pv = played_info.get("pv") or []
                # Build SAN for first 3 plies
                tmp = board.copy()
                for m in played_pv[:3]:
                    try:
                        played_pv_san.append(tmp.san(m))
                        tmp.push(m)
                    except Exception:
                        break
                board.pop()
            except Exception:
                pass

            # cp_loss is from the moving side's POV
            if best_eval_white is not None and played_eval_white is not None:
                if is_white_move:
                    cp_loss = max(0, best_eval_white - played_eval_white)
                else:
                    # for black, lower white-eval = better for black
                    cp_loss = max(0, played_eval_white - best_eval_white)
            else:
                cp_loss = 0

            severity = (
                "blunder" if cp_loss >= 300
                else "mistake" if cp_loss >= 100
                else "inaccuracy" if cp_loss >= 30
                else "good"
            )

            # PV after best (3 plies)
            pv_after_best_san: List[str] = []
            if best_move_san:
                try:
                    tmp = board.copy()
                    best_move_obj = tmp.parse_san(best_move_san)
                    tmp.push(best_move_obj)
                    pv_best_info = eng.analyse(tmp, chess.engine.Limit(depth=depth))
                    pv_best = pv_best_info.get("pv") or []
                    pv_after_best_san = [best_move_san]
                    walk = tmp.copy()
                    for m in pv_best[:2]:
                        try:
                            pv_after_best_san.append(walk.san(m))
                            walk.push(m)
                        except Exception:
                            break
                except Exception:
                    pass

            board.push(move)
            records.append({
                "move_number": move_number,
                "move_san": move_san,
                "is_white_move": is_white_move,
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "best_move_san": best_move_san,
                "cp_loss": cp_loss,
                "severity": severity,
                "top_moves": top_moves,
                "pv_after_best": pv_after_best_san,
                "pv_after_played": played_pv_san,
            })

    return records


# ── Caption + puzzle eval per move ───────────────────────────────────


def caption_for_record(rec: Dict, user_color: str, history_san: List[str]) -> Dict:
    """Run the caption pipeline as production does."""
    from services.decryption_voice.per_move_caption import caption_for_move
    is_user_move = (
        (user_color == "white" and rec["is_white_move"])
        or (user_color == "black" and not rec["is_white_move"])
    )
    try:
        result = caption_for_move(
            fen_before=rec["fen_before"],
            move_san=rec["move_san"],
            move_number=rec["move_number"],
            severity=rec["severity"],
            best_move_san=rec["best_move_san"],
            pv_after_best=rec["pv_after_best"],
            pv_after_played=rec["pv_after_played"],
            user_color=user_color,
            is_user_move=is_user_move,
            move_history_san=list(history_san),
        )
    except Exception:
        result = None
    return {
        "is_user_move": is_user_move,
        "source": result.source if result else "silent",
        "text": result.text if result else "",
    }


def puzzle_for_record(rec: Dict, user_color: str, session_puzzle_count: int) -> Optional[Dict]:
    """Test if the punishment-puzzle service would arm a puzzle on the
    user's TURN — i.e., after the COACH (opp) just played this move."""
    # Puzzle is armed when opp (non-user) just played and user is to move next
    is_opp_move = not (
        (user_color == "white" and rec["is_white_move"])
        or (user_color == "black" and not rec["is_white_move"])
    )
    if not is_opp_move:
        return None
    from coach_play.punishment_puzzle import evaluate_for_puzzle
    user_chess_color = chess.WHITE if user_color == "white" else chess.BLACK

    # Convert top_moves from white-POV to user-POV
    pv_top_moves: List[Tuple[str, int]] = []
    for san, cp_white in rec["top_moves"]:
        cp = cp_white if user_chess_color == chess.WHITE else -cp_white
        pv_top_moves.append((san, cp))

    try:
        b_before = chess.Board(rec["fen_before"])
        b_after = chess.Board(rec["fen_after"])
        # Reconstruct coach_move from SAN
        coach_move = b_before.parse_san(rec["move_san"])
    except Exception:
        return None

    spec = evaluate_for_puzzle(
        board_before_coach=b_before,
        coach_move=coach_move,
        board_after_coach=b_after,
        user_color=user_chess_color,
        pv_top_moves=pv_top_moves,
        session_puzzle_count=session_puzzle_count,
        frequency_cap=3,
    )
    if spec is None:
        return None
    return {
        "pattern_type": spec.pattern_type,
        "observation": spec.observation,
        "challenge": spec.challenge,
        "reveal": spec.reveal,
    }


# ── Main runner ──────────────────────────────────────────────────────


def run(args) -> str:
    pairs = DEFAULT_PAIRS
    if args.pairs:
        # Format: 1200v1100,1200v1200,...
        pairs = []
        for token in args.pairs.split(","):
            t = token.strip().lower().replace("vs", "v")
            if "v" not in t:
                continue
            w, b = t.split("v", 1)
            pairs.append((int(w), int(b)))

    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("MOCK GAMES AUDIT")
    lines.append("=" * 78)
    lines.append(f"  pairs:           {pairs}")
    lines.append(f"  generation depth/time: {args.depth}/{args.time}s/move, max_plies={args.max_plies}")
    lines.append(f"  analysis depth:  {ANALYSIS_DEPTH}, multipv={DEFAULT_MULTIPV}")
    lines.append(f"  stockfish:       {STOCKFISH_PATH}")
    lines.append("")

    # Aggregates
    overall_source_counts: Counter = Counter()
    per_pair_source_counts: Dict[Tuple[int, int], Counter] = defaultdict(Counter)
    overall_user_moves = 0
    sample_by_source: Dict[str, List[Dict]] = defaultdict(list)
    puzzle_hits: Counter = Counter()  # pattern_type -> count
    puzzle_examples: List[Dict] = []
    severity_with_engine_review: Counter = Counter()
    games_played = 0

    started = time.time()
    for pair in pairs:
        w_rating, b_rating = pair
        # Default user is white. Could iterate both colors but keeping
        # 1 user-color per game is enough signal for MVP.
        user_color = "white"

        print(f"  Generating {w_rating}v{b_rating}...", flush=True)
        game = play_game(
            w_rating, b_rating,
            depth=args.depth,
            time_per_move=args.time,
            max_plies=args.max_plies,
        )
        result = game.headers.get("Result", "*")
        plies = sum(1 for _ in game.mainline_moves())
        print(f"    {plies} plies, result {result}; analysing...", flush=True)
        records = analyse_game(game, depth=ANALYSIS_DEPTH, multipv=DEFAULT_MULTIPV)
        games_played += 1

        history_san: List[str] = []
        session_puzzle_count = 0
        for rec in records:
            cap = caption_for_record(rec, user_color, history_san)
            history_san.append(rec["move_san"])

            if cap["is_user_move"]:
                overall_source_counts[cap["source"]] += 1
                per_pair_source_counts[pair][cap["source"]] += 1
                overall_user_moves += 1
                if len(sample_by_source[cap["source"]]) < 3:
                    sample_by_source[cap["source"]].append({
                        "pair": pair,
                        "move": f"M{rec['move_number']} {rec['move_san']}",
                        "text": (cap["text"] or "")[:120],
                    })
                if cap["source"] == "engine_review_needed":
                    severity_with_engine_review[rec["severity"]] += 1
            else:
                # Test puzzle arming for this opp move
                puzzle = puzzle_for_record(rec, user_color, session_puzzle_count)
                if puzzle:
                    puzzle_hits[puzzle["pattern_type"]] += 1
                    session_puzzle_count += 1
                    if len(puzzle_examples) < 12:
                        puzzle_examples.append({
                            "pair": pair,
                            "after_coach": rec["move_san"],
                            "pattern": puzzle["pattern_type"],
                            "observation": puzzle["observation"],
                            "challenge": puzzle["challenge"],
                            "reveal": puzzle["reveal"],
                        })

    elapsed = time.time() - started
    lines.append(f"  games played:    {games_played}")
    lines.append(f"  user moves:      {overall_user_moves}")
    lines.append(f"  elapsed:         {elapsed:.1f}s")
    lines.append("")

    # Overall coverage table
    lines.append("OVERALL COVERAGE BY SOURCE (user moves only):")
    lines.append("-" * 78)
    total = sum(overall_source_counts.values()) or 1
    deterministic = 0
    review = 0
    EXCLUDED = {"engine_fallback", "silent", "good_generic", "engine_review_needed"}
    for src, n in overall_source_counts.most_common():
        pct = 100.0 * n / total
        marker = ""
        if src in ("engine_fallback", "silent", "good_generic"):
            marker = " ← needs work"
        elif src == "engine_review_needed":
            marker = " ← review tab"
        lines.append(f"  {n:6d}  {pct:5.1f}%  {src}{marker}")
        if src not in EXCLUDED:
            deterministic += n
        if src == "engine_review_needed":
            review = n
    lines.append("")
    lines.append(f"  SUBSTANTIVE COVERAGE:    {deterministic}/{total}  ({100.0*deterministic/total:.1f}%)")
    lines.append(f"  FOR HUMAN COACH REVIEW:  {review}/{total}  ({100.0*review/total:.1f}%)")
    lines.append("")

    # Per-pair breakdown
    lines.append("PER-PAIR COVERAGE (user = white):")
    lines.append("-" * 78)
    for pair, counts in per_pair_source_counts.items():
        ptotal = sum(counts.values()) or 1
        pdet = sum(n for s, n in counts.items() if s not in EXCLUDED)
        pgen = counts.get("good_generic", 0)
        prev = counts.get("engine_review_needed", 0)
        lines.append(
            f"  {pair[0]}v{pair[1]}: {ptotal} moves | "
            f"substantive {100.0*pdet/ptotal:5.1f}% | "
            f"good_generic {100.0*pgen/ptotal:5.1f}% | "
            f"review_needed {100.0*prev/ptotal:5.1f}%"
        )
    lines.append("")

    # Engine review by severity
    if severity_with_engine_review:
        lines.append("ENGINE_REVIEW_NEEDED BY SEVERITY:")
        for sev, n in severity_with_engine_review.most_common():
            lines.append(f"  {sev:12s}  {n}")
        lines.append("")

    # Sample captions per source
    lines.append("SAMPLE CAPTIONS (3 per source):")
    lines.append("-" * 78)
    for src, _ in overall_source_counts.most_common():
        examples = sample_by_source.get(src, [])
        if not examples:
            continue
        lines.append(f"  {src}:")
        for ex in examples:
            lines.append(f"    {ex['pair'][0]}v{ex['pair'][1]}  {ex['move']}: {ex['text']}")
        lines.append("")

    # Punishment-puzzle hits
    lines.append("PUNISHMENT-PUZZLE HITS:")
    lines.append("-" * 78)
    if not puzzle_hits:
        lines.append("  (no puzzles armed — no opp moves met the gating criteria)")
    else:
        for pattern, n in puzzle_hits.most_common():
            lines.append(f"  {n:4d}  {pattern}")
    lines.append("")
    if puzzle_examples:
        lines.append("PUZZLE EXAMPLES (up to 12):")
        lines.append("-" * 78)
        for ex in puzzle_examples:
            lines.append(f"  {ex['pair'][0]}v{ex['pair'][1]} — after coach {ex['after_coach']} ({ex['pattern']})")
            lines.append(f"    obs: {ex['observation']}")
            lines.append(f"    cha: {ex['challenge']}")
            lines.append(f"    rev: {ex['reveal']}")
            lines.append("")

    # Quality flags — scan for forbidden filler words
    lines.append("QUALITY FLAGS (caption text containing concept-without-consequence words):")
    lines.append("-" * 78)
    forbidden = ["repositions", "activates", "controls the column", "small move", "to a better spot"]
    flagged = 0
    flagged_examples: List[str] = []
    for src, examples in sample_by_source.items():
        for ex in examples:
            txt = (ex.get("text") or "").lower()
            for word in forbidden:
                if word in txt:
                    flagged += 1
                    if len(flagged_examples) < 8:
                        flagged_examples.append(f"  [{src}] {ex['move']}: {ex.get('text')}")
                    break
    if flagged == 0:
        lines.append("  none in sampled captions ✓")
    else:
        lines.append(f"  {flagged} flagged caption(s) in samples:")
        for f in flagged_examples:
            lines.append(f)
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pairs", default=None, help="comma-list e.g. '1200v1100,1200v1200,...'")
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="generation engine depth")
    p.add_argument("--time", type=float, default=DEFAULT_TIME_PER_MOVE, help="seconds per move during generation")
    p.add_argument("--max-plies", type=int, default=DEFAULT_MAX_PLIES, help="cap game length")
    p.add_argument("--output", default=None, help="write report to file (default: stdout)")
    args = p.parse_args()

    report = run(args)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print()
        print(report)
