"""The why button's engine path: services/reasoning/differential.py behind a flag.

Mohit, 2026-10-31: "do all these changes, and then wire it to UI so I can run
it on a review game, connect with luna gpt 6". This module is the wiring. It
builds the engine budget for a button press, runs the differential, and shapes
the result into the contract routes/coach.py already returns, so the card in
GameDecryptionV5.jsx needs no new fields to show the answer.

Default OFF. `WHY_DIFFERENTIAL_ENABLED=1` turns it on; when it finds nothing the
route falls through to services/why_on_demand.py unchanged, so coverage can
only go up. The words come from services/why_words.py (gpt-6-luna) when
WHY_WORDS_ENABLED=1, and the deterministic sentence ships otherwise.

Budget. Node and depth caps together: the search stops at the depth when the
position is simple and at the node cap when it is not, so the wait is bounded
either way. Six searches at most: root MultiPV, played move if not in it, and
two per branch for the reply locator.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

WHY_DIFFERENTIAL_ENABLED = os.environ.get("WHY_DIFFERENTIAL_ENABLED", "0") == "1"
WHY_DIFFERENTIAL_NODES = int(os.environ.get("WHY_DIFFERENTIAL_NODES", "2000000"))
WHY_DIFFERENTIAL_DEPTH = int(os.environ.get("WHY_DIFFERENTIAL_DEPTH", "16"))
WHY_DIFFERENTIAL_MEASURE_ALTERNATIVE = os.environ.get("WHY_DIFFERENTIAL_MEASURE_ALTERNATIVE", "1") == "1"
WHY_DIFFERENTIAL_HASH_MB = int(os.environ.get("WHY_DIFFERENTIAL_HASH_MB", "64"))


def button_config(engine_path: Optional[str] = None, *, nodes: Optional[int] = None):
    from services.reasoning.contracts import ReasoningConfig
    if engine_path is None:
        from config import STOCKFISH_PATH
        engine_path = STOCKFISH_PATH
    n = int(nodes or WHY_DIFFERENTIAL_NODES)
    return ReasoningConfig(engine_path=engine_path, nodes=n, stability_nodes=n, max_queries=8,
                           max_total_nodes=8 * n, rank_width=3, root_cap=3, reply_width=2, max_plies=12,
                           max_hypotheses=1, max_expanded_nodes=1, hash_mb=WHY_DIFFERENTIAL_HASH_MB,
                           equivalence_cp=30)


def explain(fen_before: str, played_san: str, *, mover_is_user: bool = True,
            rating: Optional[int] = None, depth: Optional[int] = None,
            engine_path: Optional[str] = None, alternative_san: Optional[str] = None) -> Dict[str, Any]:
    """Run the differential for one move. Sync; callers put it on a thread.

    `alternative_san` is the card's stored best move when it has one, so the
    sentence and the card agree on the better move. Never raises for engine
    trouble: the route needs a dict either way.
    """
    from services.reasoning.differential import explain_move
    try:
        return explain_move(fen_before, played_san, config=button_config(engine_path),
                            depth=int(depth or WHY_DIFFERENTIAL_DEPTH), mover_is_user=mover_is_user,
                            rating=rating, measure_alternative=WHY_DIFFERENTIAL_MEASURE_ALTERNATIVE,
                            alternative_san=alternative_san or None)
    except ValueError as exc:
        return {"found": False, "reason": "bad_input", "error": str(exc)}
    except Exception as exc:                      # noqa: BLE001
        logger.exception("why differential failed")
        return {"found": False, "reason": "engine_error", "error": type(exc).__name__}


# Differential verdicts after which the old path must NOT run: it would say
# something the differential has just shown to be untrue or not the difference.
#   engine_choice / no_gap      the move is the engine's own choice; the old path
#                               fired on 6 of the 8 good moves in the regression
#                               set (2026-10-31), every one a recapture called a win
#   shared_consequence_only     the better move allows the same thing
NO_FALLBACK_REASONS = ("engine_choice", "no_gap", "shared_consequence_only")


def old_answer_is_an_exchange(fen_before: str, played_san: str, old: Optional[Dict[str, Any]]) -> bool:
    """True when the old path's "X wins your piece" is a recapture of a piece
    that itself just captured, and the trade was even or better for the mover.

    services/punishment_resolver measures material from the position AFTER the
    played move, so after Nxf5 exf5 it reports "exf5 wins your knight" although
    a knight was taken first. Measured on the 37-position set: 9 of its 21
    sentences on bad moves and 6 false fires on good moves had this shape.
    """
    if not old or not old.get("found") or old.get("direction") != "received" or old.get("mechanism") != "WINS_MATERIAL":
        return False
    try:
        import chess
        from services.reasoning.differential import _VALUE
        board = chess.Board(fen_before)
        played = board.parse_san(played_san)
        captured = board.piece_at(played.to_square)
        if captured is None:
            return False
        mover_piece = board.piece_at(played.from_square)
        board.push(played)
        reply = board.parse_san(str(old.get("move_san") or ""))
        if reply.to_square != played.to_square:
            return False
        return _VALUE[captured.piece_type] >= _VALUE[mover_piece.piece_type]
    except Exception:                                 # noqa: BLE001
        return False


def old_answer_contradicts_eval(differential: Optional[Dict[str, Any]], old: Optional[Dict[str, Any]]) -> bool:
    """A material claim on a move the differential graded an inaccuracy or
    good contradicts the engine: a pawn is worth more than the whole gap.
    ho20 in the regression set: the old path said "gxh3 wins your pawn" on a
    move the judge prefers."""
    if not differential or not old or not old.get("found"):
        return False
    return (differential.get("class") in ("inaccuracy", "good")
            and old.get("mechanism") in ("WINS_MATERIAL", "FORK", "TRAPPED", "MATE", "PROMOTES"))


def summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a differential result worth returning when it found nothing."""
    return {"engine": "differential", "found": bool(result.get("found")), "reason": result.get("reason"),
            "family": result.get("family"), "class": result.get("class"), "gap_cp": result.get("gap_cp"),
            "better_move": result.get("better_move"),
            "reply_san": (result.get("played_branch") or {}).get("reply_san"),
            "shared_consequence": result.get("shared_consequence"),
            "runtime_ms": (result.get("runtime") or {}).get("wall_ms")}


def to_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a found result into the why endpoint's existing contract."""
    consequence = result.get("consequence") or {}
    return {
        "found": True,
        "direction": result["direction"],
        "mechanism": result["mechanism"],
        "text": result["text"],
        "move_san": (result.get("played_branch") or {}).get("reply_san") if result["direction"] == "received"
                    else result.get("better_move"),
        "line_san": list(result.get("line_san") or []),
        "arrows": list(result.get("arrows") or []),
        "candidate_rank": None,
        "eval_gap_cp": result.get("gap_cp"),
        "payoff_cp": consequence.get("payoff_cp"),
        "punishment": consequence or None,
        "engine": "differential",
        "family": result.get("family"),
        "class": result.get("class"),
        "better_move": result.get("better_move"),
        "causes": [c["text"] for c in (result.get("causes") or [])],
        "facts": result.get("facts"),
        "differential": summary(result),
    }
