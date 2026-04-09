"""
Fast Eval Service
==================

Ultra-fast Stockfish evaluation for pending move assessment.
Target: P95 < 400ms, P99 < 500ms.

Strategy:
  - Keep Stockfish warm (long-lived process)
  - 2-pass eval: Pass A (depth 8, ~100ms), Pass B only if risky (~150ms)
  - Cache eval_before from session
  - Hard timeout at 400ms
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

_engine_lock = threading.Lock()
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

PASS_A_NODES = 30000  # ~100ms
PASS_B_NODES = 60000  # ~150ms (only if risky)
HARD_TIMEOUT_MS = 400


def fast_eval(
    fen_before: str,
    uci_move: str,
    cached_eval_before: Optional[float] = None,
) -> Dict:
    """
    2-pass fast evaluation.

    Pass A: Quick eval of position after move (depth ~8-10, ~100ms)
    Pass B: Only if Pass A shows risk, slightly deeper (~150ms)

    Returns:
        {
            "eval_before": float,  # centipawns / 100
            "eval_after": float,
            "cp_loss": int,  # always positive, from side-to-move perspective
            "best_move": str,  # SAN
            "move_quality": str,  # good/inaccuracy/mistake/blunder
            "depth": int,
            "nodes": int,
            "elapsed_ms": float,
        }
    """
    start = time.monotonic()

    try:
        board_before = chess.Board(fen_before)
        move = chess.Move.from_uci(uci_move)

        if move not in board_before.legal_moves:
            return _timeout_result(cached_eval_before)

        side_to_move = board_before.turn  # WHITE or BLACK
        engine = _get_engine()

        # ─── EVAL BEFORE (use cache or quick compute) ─────
        if cached_eval_before is not None:
            eval_before = cached_eval_before
        else:
            eval_before = _quick_eval(engine, board_before, PASS_A_NODES)

        elapsed = (time.monotonic() - start) * 1000
        if elapsed > HARD_TIMEOUT_MS:
            return _build_result(eval_before, eval_before, "", side_to_move, 0, 0, elapsed)

        # ─── EVAL AFTER (position after user's move) ─────
        board_after = board_before.copy()
        board_after.push(move)

        eval_after = _quick_eval(engine, board_after, PASS_A_NODES)

        # ─── BEST MOVE ─────
        best_move_san = ""
        try:
            info_best = engine.analyse(board_before, chess.engine.Limit(nodes=PASS_A_NODES))
            if info_best.get("pv"):
                best_move_san = board_before.san(info_best["pv"][0])
        except Exception:
            pass

        elapsed = (time.monotonic() - start) * 1000
        if elapsed > HARD_TIMEOUT_MS:
            return _build_result(eval_before, eval_after, best_move_san, side_to_move, 8, PASS_A_NODES, elapsed)

        # ─── PASS B: Only if risky ─────
        cp_loss_raw = _compute_cp_loss(eval_before, eval_after, side_to_move)

        if cp_loss_raw >= 80:  # Looks like a mistake — verify deeper
            eval_after_deep = _quick_eval(engine, board_after, PASS_B_NODES)
            eval_after = eval_after_deep

            # Re-eval best move deeper too
            try:
                info_deep = engine.analyse(board_before, chess.engine.Limit(nodes=PASS_B_NODES))
                if info_deep.get("pv"):
                    best_move_san = board_before.san(info_deep["pv"][0])
            except Exception:
                pass

        elapsed = (time.monotonic() - start) * 1000
        return _build_result(eval_before, eval_after, best_move_san, side_to_move, 10, PASS_B_NODES, elapsed)

    except chess.engine.EngineTerminatedError:
        logger.warning("Fast eval: engine crashed, restarting")
        _restart_engine()
        return _timeout_result(cached_eval_before)
    except Exception as e:
        logger.error(f"Fast eval failed: {e}")
        return _timeout_result(cached_eval_before)


def _quick_eval(engine: chess.engine.SimpleEngine, board: chess.Board, nodes: int) -> float:
    """Get eval in centipawns/100 (from White's perspective)."""
    try:
        info = engine.analyse(board, chess.engine.Limit(nodes=nodes))
        score = info["score"].white()
        if score.is_mate():
            return 100.0 if score.mate() > 0 else -100.0
        cp = score.score()
        return cp / 100.0 if cp is not None else 0.0
    except Exception:
        return 0.0


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
        "move_quality": _classify_quality(cp_loss),
        "depth": depth,
        "nodes": nodes,
        "elapsed_ms": round(elapsed_ms, 1),
    }


def _timeout_result(cached_eval: Optional[float] = None) -> Dict:
    return {
        "eval_before": cached_eval or 0.0,
        "eval_after": cached_eval or 0.0,
        "cp_loss": 0,
        "best_move": "",
        "move_quality": "good",
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
        "hung_piece": None,
        "missed_threat": None,
        "ignored_capture": None,
        "is_first_major_swing": False,
        "lost_winning_position": False,
        "is_strong_move": False,
        "is_non_obvious": False,
    }

    cp_loss = eval_result.get("cp_loss", 0)
    move_quality = eval_result.get("move_quality", "good")

    # Hung piece: user's piece attacked and undefended after the move
    # BUT: skip if all attackers are pinned (can't actually capture)
    opponent = not user_color
    for sq in chess.SQUARES:
        piece = board_after.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type != chess.KING:
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

                val = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}.get(piece.piece_type, 0)
                if val >= 3:  # Only major/minor pieces
                    signals["hung_piece"] = {
                        "piece": {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen"}.get(piece.piece_type, "piece"),
                        "square": chess.square_name(sq),
                        "value": val,
                    }
                    break  # One is enough

    # Missed threat: opponent was attacking user piece before move, still is after
    # Skip if all attackers are pinned
    if not signals["hung_piece"]:
        for sq in chess.SQUARES:
            piece = board_before.piece_at(sq)
            if piece and piece.color == user_color and piece.piece_type != chess.KING:
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
        # Check if user played the best move
        played_move = board_after.peek() if board_after.move_stack else None
        if played_move:
            try:
                best_san = eval_result["best_move"]
                played_san = board_before.san(played_move)
                if played_san == best_san:
                    signals["is_strong_move"] = True
                    # Non-obvious: not a recapture, not a check
                    is_recapture = (board_before.is_capture(played_move) and
                                    board_before.move_stack and
                                    board_before.peek().to_square == played_move.to_square)
                    board_check = board_before.copy()
                    board_check.push(played_move)
                    is_check = board_check.is_check()
                    signals["is_non_obvious"] = not is_recapture and not is_check
            except Exception:
                pass

    return signals
