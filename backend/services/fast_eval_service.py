"""
Fast Eval Service
==================

Bounded Stockfish evaluation for pending move assessment.
Latency must be measured on the deployment host, not inferred from node counts.

Strategy:
  - Keep Stockfish warm (long-lived process)
  - Two searches from the same root, one restricted to the proposed move
  - Serialized access to the warm engine; no unbound scalar cache
  - Inherited 800ms budget includes queue and startup; startup may overrun it
  - No LLM, no deep search, no opening lookups
"""

import chess
import chess.engine
import logging
import time
import threading
from typing import Optional, Dict, Tuple
from config import STOCKFISH_PATH

logger = logging.getLogger(__name__)

# ─── WARM ENGINE POOL ─────────────────────────────────────────────

_engine_lock = threading.RLock()
_warm_engine: Optional[chess.engine.SimpleEngine] = None


def _get_engine() -> chess.engine.SimpleEngine:
    """Get or create warm Stockfish instance."""
    global _warm_engine
    with _engine_lock:
        if _warm_engine is None:
            try:
                _warm_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
                _warm_engine.configure({"Threads": 1, "Hash": 64})
                logger.info("Fast eval: Stockfish engine warmed up")
            except Exception as e:
                logger.error(f"Fast eval: Failed to start Stockfish: {e}")
                raise
        return _warm_engine


def _restart_engine():
    """Restart engine if it crashes."""
    global _warm_engine
    with _engine_lock:
        if _warm_engine:
            try:
                _warm_engine.quit()
            except Exception:
                pass
        _warm_engine = None
    return _get_engine()


# ─── FAST EVAL ────────────────────────────────────────────────────

PASS_A_NODES = 80000   # Inherited per-search node ceiling, not a latency claim
HARD_TIMEOUT_MS = 800  # Allow more time since we use 1200ms frontend window
# What we report when the search did not happen. Deliberately NOT "good" --
# see _timeout_result.
UNKNOWN_QUALITY = "unknown"


def fast_eval(
    fen_before: str,
    uci_move: str,
    cached_eval_before: Optional[float] = None,
) -> Dict:
    """Compare unrestricted and forced-move searches on the SAME root.

    The legacy scalar cache has no FEN, POV, units or search provenance. Keep
    the argument for existing callers, but never use it as evaluation evidence.
    One transaction owns the shared UCI engine: simultaneous analyse calls can
    cancel one another even though SimpleEngine itself is thread-safe.
    """
    start = time.monotonic()
    deadline = start + HARD_TIMEOUT_MS / 1000
    if not _engine_lock.acquire(timeout=HARD_TIMEOUT_MS / 1000):
        return {**_timeout_result(), "failure_reason": "engine_busy"}
    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(uci_move)
        if not board.is_valid() or move not in board.legal_moves:
            return {**_timeout_result(), "failure_reason": "invalid_position_or_move"}
        engine = _get_engine()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {**_timeout_result(), "failure_reason": "search_budget_exhausted"}
        # Reserve half the remaining budget for each root search. The inherited
        # node ceiling remains; time is an additional limit, not measured depth.
        best = _search(engine,
            board, chess.engine.Limit(nodes=PASS_A_NODES, time=remaining / 2)
        )
        _validate_search(board, best)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {**_timeout_result(), "failure_reason": "search_budget_exhausted"}
        same_move = best["pv"][0] == move
        played = best if same_move else _search(
            engine, board, chess.engine.Limit(nodes=PASS_A_NODES, time=remaining),
            root_moves=[move],
        )
        _validate_search(board, played, move)
        result = _build_result(
            best["score"].white().score(mate_score=10000) / 100,
            played["score"].white().score(mate_score=10000) / 100,
            board.san(best["pv"][0]), board.turn,
            min(best["depth"], played["depth"]),
            best.get("nodes", 0) + (0 if same_move else played.get("nodes", 0)),
            (time.monotonic() - start) * 1000,
        )
        result["search_evidence"] = {
            "schema_version": "pwc_root_comparison.v1",
            "fen_before": board.fen(), "played_uci": uci_move,
            "score_pov": "white", "score_unit": "pawns",
            "best_depth": best["depth"], "played_depth": played["depth"],
            "best_pv": [m.uci() for m in best["pv"]],
            "played_pv": [m.uci() for m in played["pv"]],
        }
        return result
    except chess.engine.EngineTerminatedError:
        # Do not synchronously restart inside a failed request. Next request
        # can warm a replacement; preserve this request's failed status.
        global _warm_engine
        _warm_engine = None
        return {**_timeout_result(), "failure_reason": "engine_terminated"}
    except Exception as exc:
        logger.warning("Fast eval unavailable: %s", type(exc).__name__)
        return {**_timeout_result(), "failure_reason": "search_unavailable"}
    finally:
        _engine_lock.release()


def _search(engine, board, limit, **kwargs):
    """Keep the last exact iteration, not a merged/aborted aspiration bound.

    SimpleEngine.analyse merges UCI info dictionaries. A lower/upperbound key
    from an earlier update can survive into its returned final score. Consume
    individual updates so the score, depth, PV and bound belong together.
    """
    exact = None
    with engine.analysis(board, limit, **kwargs) as analysis:
        for info in analysis:
            if info.get("score") is None:
                continue
            try:
                _validate_search(board, info, (kwargs.get("root_moves") or [None])[0])
            except ValueError:
                continue
            exact = dict(info)
    if exact is None:
        raise ValueError("No completed exact iteration")
    return exact


def _validate_search(board, info, forced_move=None):
    """Only complete, legal, non-bound scores may drive a move verdict."""
    if (
        not info.get("score") or int(info.get("depth") or 0) <= 0
        or info.get("lowerbound") or info.get("upperbound") or not info.get("pv")
    ):
        raise ValueError("Incomplete search evidence")
    if info["score"].white().score(mate_score=10000) is None:
        raise ValueError("Missing score")
    if forced_move is not None and info["pv"][0] != forced_move:
        raise ValueError("Search is not for the proposed move")
    replay = board.copy()
    for move in info["pv"]:
        if move not in replay.legal_moves:
            raise ValueError("Illegal principal variation")
        replay.push(move)


def _quick_eval(engine: chess.engine.SimpleEngine, board: chess.Board, nodes: int) -> float:
    """Compatibility helper. Failure propagates; it is never an equal score."""
    info = _search(engine, board, chess.engine.Limit(nodes=nodes))
    _validate_search(board, info)
    return info["score"].white().score(mate_score=10000) / 100


def _compute_cp_loss(eval_before: float, eval_after: float, side_to_move: chess.Color) -> int:
    """Compute centipawn loss from side-to-move's perspective. Always positive."""
    if side_to_move == chess.WHITE:
        return max(0, int((eval_before - eval_after) * 100))
    else:
        return max(0, int((eval_after - eval_before) * 100))


def _classify_quality(cp_loss: int) -> str:
    if cp_loss >= 300:
        return "blunder"
    if cp_loss >= 120:
        return "mistake"
    if cp_loss >= 60:
        return "inaccuracy"
    return "good"


def _build_result(
    eval_before: float, eval_after: float, best_move: str,
    side_to_move: chess.Color, depth: int, nodes: int, elapsed_ms: float
) -> Dict:
    cp_loss = _compute_cp_loss(eval_before, eval_after, side_to_move)
    return {
        "eval_before": round(eval_before, 2),
        "eval_after": round(eval_after, 2),
        "cp_loss": cp_loss,
        "best_move": best_move,
        # depth 0 means the search did not happen. A cp_loss of 0 then means
        # "we compared a position with itself", not "the move was fine".
        "move_quality": (_classify_quality(cp_loss) if depth > 0
                         else UNKNOWN_QUALITY),
        "depth": depth,
        "nodes": nodes,
        "elapsed_ms": round(elapsed_ms, 1),
    }


def _timeout_result(cached_eval: Optional[float] = None) -> Dict:
    """We did not evaluate the move. Say so; do not say it was fine.

    This used to report move_quality "good". A failed or timed-out search
    therefore asserted the move was a good one -- and CoachPlay paints that
    straight onto the board as an instant label. On a loaded box, the player
    who hung a queen got a green tick, because the one thing we knew was that
    we knew nothing.

    depth stays 0, which is what callers already test (`eval_is_valid`), so
    every existing guard behaves exactly as before. The difference is that the
    label is now honest for anything that reads the quality directly.
    """
    return {
        "eval_before": cached_eval or 0.0,
        "eval_after": cached_eval or 0.0,
        "cp_loss": 0,
        "best_move": "",
        "move_quality": UNKNOWN_QUALITY,
        "depth": 0,
        "nodes": 0,
        "elapsed_ms": 999,
    }


# ─── SIGNAL DETECTION (fast, no chess engine needed) ──────────────

def detect_signals_fast(
    board_before: chess.Board,
    board_after: chess.Board,
    user_color: chess.Color,
    eval_result: Dict,
    session_evals: list = None,
) -> Dict:
    """
    Fast signal detection using only python-chess (no Stockfish).
    Must be < 5ms.
    """
    signals = {
        # Critical signals
        "hung_piece": None,
        "missed_threat": None,
        "ignored_capture": None,
        "is_first_major_swing": False,
        "lost_winning_position": False,
        # Reinforcement signals
        "is_strong_move": False,
        "is_non_obvious": False,
        # Advisory/ambient signals (NEW)
        "is_opening_phase": False,
        "is_early_middlegame": False,
        "development_incomplete": False,
        "king_unsafe": False,
        "center_under_pressure": False,
        "premature_attack": False,
        "loose_pieces_present": False,
        "opponent_created_threat": None,
        "opponent_improved_activity": False,
    }

    cp_loss = eval_result.get("cp_loss", 0)
    move_quality = eval_result.get("move_quality", "good")

    # Hung piece: user's piece attacked and undefended after the move
    # Skip pawns (too noisy). Skip pinned attackers (can't actually capture).
    opponent = not user_color
    for sq in chess.SQUARES:
        piece = board_after.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type not in (chess.KING, chess.PAWN):
            attackers = board_after.attackers(opponent, sq)
            defenders = board_after.attackers(user_color, sq)
            if attackers and not defenders:
                # Check if ANY attacker can actually capture (not pinned)
                real_attackers = [
                    atk_sq for atk_sq in attackers
                    if not board_after.is_pinned(opponent, atk_sq)
                ]
                if not real_attackers:
                    continue  # All attackers are pinned — piece is safe

                val = {2: 3, 3: 3, 4: 5, 5: 9}.get(piece.piece_type, 0)
                if val >= 3:  # Only major/minor pieces (pawns already excluded)
                    signals["hung_piece"] = {
                        "piece": {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen"}.get(piece.piece_type, "piece"),
                        "square": chess.square_name(sq),
                        "value": val,
                    }
                    break  # One is enough

    # Missed threat: opponent was attacking user piece before move, still is after
    # Skip pawns and pinned attackers
    if not signals["hung_piece"]:
        for sq in chess.SQUARES:
            piece = board_before.piece_at(sq)
            if piece and piece.color == user_color and piece.piece_type not in (chess.KING, chess.PAWN):
                att_before = board_before.attackers(opponent, sq)
                def_before = board_before.attackers(user_color, sq)
                if att_before and not def_before:
                    # Check if attackers are pinned
                    real_att = [a for a in att_before if not board_before.is_pinned(opponent, a)]
                    if not real_att:
                        continue
                    # Was hanging before. Is it still hanging after?
                    piece_after = board_after.piece_at(sq)
                    if piece_after and piece_after.color == user_color:
                        att_after = board_after.attackers(opponent, sq)
                        def_after = board_after.attackers(user_color, sq)
                        if att_after and not def_after:
                            real_att_after = [a for a in att_after if not board_after.is_pinned(opponent, a)]
                            if not real_att_after:
                                continue
                            val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}.get(piece.piece_type, 0)
                            if val >= 3:
                                signals["missed_threat"] = {
                                    "piece": {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen"}.get(piece.piece_type, "piece"),
                                    "square": chess.square_name(sq),
                                }
                                break

    # Ignored capture: opponent piece hanging before move, user didn't take
    # Skip if user's attackers are all pinned
    for sq in chess.SQUARES:
        piece = board_before.piece_at(sq)
        if piece and piece.color == opponent and piece.piece_type != chess.KING:
            att = board_before.attackers(user_color, sq)
            defn = board_before.attackers(opponent, sq)
            if att and not defn:
                # Check if user's attackers are pinned
                real_att = [a for a in att if not board_before.is_pinned(user_color, a)]
                if not real_att:
                    continue
                val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}.get(piece.piece_type, 0)
                if val >= 3:
                    signals["ignored_capture"] = {
                        "piece": {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen"}.get(piece.piece_type, "piece"),
                        "square": chess.square_name(sq),
                        "value": val,
                    }
                    break

    # Game flow
    eval_before = eval_result.get("eval_before", 0)
    eval_after = eval_result.get("eval_after", 0)
    user_is_white = user_color == chess.WHITE

    # Lost winning position
    if user_is_white:
        was_winning = eval_before >= 1.5
        now_not = eval_after < 0.5
    else:
        was_winning = eval_before <= -1.5
        now_not = eval_after > -0.5
    signals["lost_winning_position"] = was_winning and now_not

    # First major swing
    if session_evals:
        if user_is_white:
            swing = eval_before - eval_after
        else:
            swing = eval_after - eval_before
        if swing >= 1.5:
            had_prior_swing = any(
                abs(e.get("eval_before", 0) - e.get("eval_after", 0)) >= 1.5
                for e in session_evals
            )
            signals["is_first_major_swing"] = not had_prior_swing

    # Strong non-obvious move
    if move_quality == "good" and eval_result.get("best_move"):
        played_move = board_after.peek() if board_after.move_stack else None
        if played_move:
            try:
                best_san = eval_result["best_move"]
                played_san = board_before.san(played_move)
                if played_san == best_san:
                    signals["is_strong_move"] = True
                    is_recapture = (board_before.is_capture(played_move) and
                                    board_before.move_stack and
                                    board_before.peek().to_square == played_move.to_square)
                    board_check = board_before.copy()
                    board_check.push(played_move)
                    is_check = board_check.is_check()
                    signals["is_non_obvious"] = not is_recapture and not is_check
            except Exception:
                pass

    # ─── AMBIENT / ADVISORY SIGNALS ──────────────────────────────

    move_number = board_after.fullmove_number
    signals["is_opening_phase"] = move_number <= 12
    signals["is_early_middlegame"] = 10 <= move_number <= 20

    # Development incomplete: minor pieces still on back rank
    back_rank = 0 if user_color == chess.WHITE else 7
    undeveloped = 0
    for f in range(8):
        sq = chess.square(f, back_rank)
        p = board_after.piece_at(sq)
        if p and p.color == user_color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
            undeveloped += 1
    signals["development_incomplete"] = undeveloped >= 2 and move_number >= 5

    # King unsafe: only if never castled AND still in opening/early middlegame
    # After move 25, king safety through castling is no longer relevant
    signals["king_unsafe"] = False
    if 8 <= move_number <= 25:
        king_sq = board_after.king(user_color)
        if king_sq is not None:
            castled_squares = (chess.G1, chess.C1) if user_color == chess.WHITE else (chess.G8, chess.C8)
            signals["king_unsafe"] = king_sq not in castled_squares

    # Center under pressure: opponent controls more center squares
    center_sqs = [chess.E4, chess.D4, chess.E5, chess.D5]
    our_center = sum(1 for sq in center_sqs if board_after.attackers(user_color, sq))
    opp_center = sum(1 for sq in center_sqs if board_after.attackers(opponent, sq))
    signals["center_under_pressure"] = opp_center > our_center + 2

    # Premature attack: user moved piece past rank 5 while development incomplete
    if signals["development_incomplete"] and move_quality in ("good", "inaccuracy"):
        played_move = board_after.peek() if board_after.move_stack else None
        if played_move:
            to_rank = chess.square_rank(played_move.to_square)
            attack_rank = 4 if user_color == chess.WHITE else 3  # rank 5 (0-indexed=4 for white)
            piece = board_after.piece_at(played_move.to_square)
            if piece and piece.color == user_color and piece.piece_type != chess.PAWN:
                if (user_color == chess.WHITE and to_rank >= attack_rank) or \
                   (user_color == chess.BLACK and to_rank <= attack_rank):
                    signals["premature_attack"] = True

    # Loose pieces: user has pieces attacked where attacker value < defender value
    loose_count = 0
    for sq in chess.SQUARES:
        p = board_after.piece_at(sq)
        if p and p.color == user_color and p.piece_type not in (chess.KING, chess.PAWN):
            atts = board_after.attackers(opponent, sq)
            defs = board_after.attackers(user_color, sq)
            if atts and len(list(defs)) <= 1:
                loose_count += 1
    signals["loose_pieces_present"] = loose_count >= 2

    # Opponent created threat: did opponent's last move attack something new?
    if board_before.move_stack:
        opp_last = board_before.peek()
        opp_to = opp_last.to_square
        # What does the opponent's piece now attack?
        opp_attacks = board_after.attacks(opp_to) if board_after.piece_at(opp_to) else chess.SquareSet()
        for sq in opp_attacks:
            target = board_after.piece_at(sq)
            if target and target.color == user_color and target.piece_type != chess.KING:
                val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}.get(target.piece_type, 0)
                if val >= 3:
                    opp_piece = board_after.piece_at(opp_to)
                    signals["opponent_created_threat"] = {
                        "attacker": _piece_name_str(opp_piece.piece_type) if opp_piece else "piece",
                        "target": _piece_name_str(target.piece_type),
                        "target_square": chess.square_name(sq),
                    }
                    break

    # Opponent improved activity: moved a piece to a more central square
    if board_before.move_stack:
        opp_last = board_before.peek()
        from_central = _centrality(opp_last.from_square)
        to_central = _centrality(opp_last.to_square)
        if to_central > from_central + 2:
            signals["opponent_improved_activity"] = True

    return signals


def _piece_name_str(piece_type: int) -> str:
    return {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}.get(piece_type, "piece")


def _centrality(sq: int) -> int:
    """How central is a square? 0-4 scale."""
    f, r = chess.square_file(sq), chess.square_rank(sq)
    return min(f, 7-f) + min(r, 7-r)
