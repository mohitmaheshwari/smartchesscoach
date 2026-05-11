"""
Caption Facts — the canonical chess-semantics layer for ChessGuru.

Per design doc `docs/caption_pipeline_design.md` and memory rule
`feedback_renderer_never_computes_chess_meaning.md`:

    THIS MODULE COMPUTES CHESS MEANING. The renderer does not.

Every fact returned by `extract_facts()` is:
    - atomic (a single deterministic value, never interpreted prose)
    - geometric (derivable from FEN + engine data; no opinions)
    - machine-composable (renderers select and format; never re-derive)

──────────────────────────────────────────────────────────────────────
Four implementation laws (locked 2026-05-11):
──────────────────────────────────────────────────────────────────────

LAW 1 — NO SMART STRINGS AS FACTS.
    Bad:   {"best_reason": "wins a pawn"}
    Good:  {"best_move_wins_material": True,
            "best_move_material_delta_cp": 100,
            "best_move_targets": [(sq, piece_type), ...]}
    Phrasing belongs to the renderer. Facts stay atomic.

LAW 2 — NO FUTURE CONVENIENCE FACTS.
    Forbidden: is_nice_move, is_aggressive, is_positional, is_sharp,
    is_natural, and anything that smuggles in human emotional judgment
    as a fact. This module answers: what changed, what attacks what,
    what is defended, what the PV proves, what geometry exists.
    It does NOT answer: whether a human emotionally approves.

LAW 3 — TACTIC DETECTORS EMIT EVIDENCE, NOT LABELS.
    Bad:   {"tactic": "fork"}
    Good:  {"tactic": "fork", "forker_square": "f3",
            "targets": [(sq, piece_type), ...]}
    The renderer must be able to write the caption from the evidence
    alone, without re-running any chess logic of its own.

LAW 4 — THIS MODULE IS REPLAYABLE IN ISOLATION.
    A CLI entry point and a pure-function API let any extracted fact
    be reproduced from a (FEN, move, engine_data) triple. Every Parth
    disagreement and every hallucination claim traces back here.
    Treat this file like a chess-science layer, not an app helper.

──────────────────────────────────────────────────────────────────────
First commit covers:
    - Engine truth (pass-through from stored move_evaluations)
    - Basic position facts (check, capture, castling, forced recapture)
    - Attack/defense lists (raw — NOT SEE yet; that's commit #2)
    - Phase, opening name (uses existing detect_opening_from_moves)
    - Target square, captured piece, moving piece type

Not yet implemented (subsequent commits):
    - SEE (Static Exchange Evaluation) — commit #2
    - Threats created / pieces now undefended — commit #2
    - Tactic detection with evidence — commit #3
    - PV material walk — commit #3
    - Primary-reason extractor — commit #4
    - Concept-library facts (passed pawn, doubled, etc) — Phase 3

Usage (Python):
    from services.caption_facts import extract_facts
    facts = extract_facts(
        fen_before="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 3",
        played_san="Nc3",
        best_move_san="O-O",
        eval_before_cp=20, eval_after_cp=15,
        cp_loss=5,
        pv_after_played=["Nc3", "Bc5", "O-O"],
        pv_after_best=["O-O", "Bc5", "c3"],
        move_history_san=["e4", "e5", "Nf3", "Nc6", "Bc4"],
        full_move_number=3,
    )

Usage (CLI):
    python -m backend.services.caption_facts \\
        --fen "..." --move Nc3 --best O-O \\
        --eval-before 20 --eval-after 15 --cp-loss 5
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

import chess


# ────────────────────────────────────────────────────────────────────
# Public constants
# ────────────────────────────────────────────────────────────────────

PIECE_TYPE_NAMES: Dict[int, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

PIECE_VALUE_CP: Dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,  # king has no exchange value
}

# Phase boundary thresholds (mirrors detect_phase in game_decryption_v5_service)
_OPENING_MAX_MOVE_HIGH_PIECES = 10  # if piece_count >= 28
_OPENING_MAX_MOVE_MID_PIECES = 15   # if piece_count >= 24


# ────────────────────────────────────────────────────────────────────
# Helpers (private — no chess judgment, just data)
# ────────────────────────────────────────────────────────────────────

def _normalize_san(san: str) -> str:
    """Strip annotation suffixes (!, ?, +, #) so equality comparisons work."""
    return (san or "").rstrip("!?+#")


def _piece_type_at(board: chess.Board, square: int) -> Optional[int]:
    p = board.piece_at(square)
    return p.piece_type if p else None


def _piece_name_at(board: chess.Board, square: int) -> Optional[str]:
    pt = _piece_type_at(board, square)
    return PIECE_TYPE_NAMES.get(pt) if pt is not None else None


def _attackers_of(board: chess.Board, color: chess.Color, square: int) -> List[Tuple[str, str]]:
    """Return [(square_name, piece_name), ...] for every piece of `color`
    that attacks `square` in the given board position."""
    out: List[Tuple[str, str]] = []
    for sq in board.attackers(color, square):
        p = board.piece_at(sq)
        if p:
            out.append((chess.square_name(sq), PIECE_TYPE_NAMES.get(p.piece_type, "piece")))
    return out


def _detect_phase(board: chess.Board, full_move_number: int) -> str:
    """Game-phase determination mirrored from V5's detect_phase.
    Returns one of: opening | middlegame | endgame."""
    piece_count = len(board.piece_map())
    queens = (
        len(board.pieces(chess.QUEEN, chess.WHITE))
        + len(board.pieces(chess.QUEEN, chess.BLACK))
    )
    if full_move_number <= _OPENING_MAX_MOVE_HIGH_PIECES and piece_count >= 28:
        return "opening"
    if full_move_number <= _OPENING_MAX_MOVE_MID_PIECES and piece_count >= 24:
        return "opening"
    if queens == 0 or piece_count <= 12:
        return "endgame"
    if piece_count <= 18:
        return "endgame"
    return "middlegame"


def _is_forced_recapture(board_before: chess.Board, played_move: chess.Move) -> bool:
    """A move is a 'forced recapture' if:
      - The previous move was a capture
      - The played move recaptures on the same square
      - There is no other reasonable move (this is a soft criterion;
        we approximate as 'played move is the only legal capture on
        that square AND there's at least one other own piece attacking
        it that would have lost more material if it had been ignored')

    For commit #1, we use the simpler criterion:
      - previous_move was a capture (board_before.peek() returns it)
      - played_move captures on the SAME square as previous_move went to
      - that square contains an opponent piece that just moved there
    """
    if not played_move or not board_before.move_stack:
        return False
    prev = board_before.peek()
    if not prev or prev.to_square is None:
        return False
    # The previous move must have been a capture into prev.to_square.
    # board_before is the position AFTER prev was played. So the piece
    # at prev.to_square in board_before is the opponent's piece that
    # just landed there.
    landing_piece = board_before.piece_at(prev.to_square)
    if not landing_piece:
        return False
    if landing_piece.color == board_before.turn:
        # The piece on the to-square belongs to side-to-move, which
        # means our previous move wasn't a capture by them — bail.
        return False
    # The played move must be capturing on prev.to_square.
    return played_move.to_square == prev.to_square and board_before.is_capture(played_move)


# ────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────

def extract_facts(
    *,
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str] = None,
    eval_before_cp: Optional[int] = None,
    eval_after_cp: Optional[int] = None,
    cp_loss: int = 0,
    pv_after_played: Optional[List[str]] = None,
    pv_after_best: Optional[List[str]] = None,
    move_history_san: Optional[List[str]] = None,
    full_move_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Extract the deterministic facts dict for one move.

    Inputs are pure data: a FEN string, the played move (SAN), the
    engine's best move (SAN), eval/cp_loss, and the engine's PV after
    each. No database access, no global state.

    Returns a flat dict whose keys match the contract described in
    `docs/caption_pipeline_design.md` §4. Every key is atomic — no
    interpreted prose, no judgment, no convenience labels.

    Raises:
        chess.InvalidMoveError if played_san cannot be parsed from fen_before.
        ValueError if fen_before is invalid.
    """
    pv_after_played = pv_after_played or []
    pv_after_best = pv_after_best or []
    move_history_san = move_history_san or []
    cp_loss = max(0, cp_loss or 0)

    # Build board_before. If the caller provided move_history, replay it
    # so board_before.move_stack has the previous moves (needed for the
    # forced-recapture check). Otherwise rely on the FEN alone.
    if move_history_san:
        board_before = chess.Board()
        for san in move_history_san:
            try:
                board_before.push_san(san)
            except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
                # History invalid — fall back to FEN-only board (no stack)
                board_before = chess.Board(fen_before)
                break
        # Sanity check: replayed position should match the FEN we got
        # (board_before.fen() may differ in halfmove/fullmove counters
        # but the position part should match).
        if " ".join(board_before.fen().split()[:4]) != " ".join(fen_before.split()[:4]):
            # History didn't reach the same position. Trust the FEN.
            board_before = chess.Board(fen_before)
    else:
        board_before = chess.Board(fen_before)

    # Parse the played move.
    played_move = board_before.parse_san(played_san)

    # Build board_after.
    board_after = board_before.copy()
    board_after.push(played_move)

    # ── Engine truth (pass-through) ────────────────────────────────────
    played_is_best = (
        best_move_san is not None
        and _normalize_san(played_san) == _normalize_san(best_move_san)
    )

    # ── Position facts ─────────────────────────────────────────────────
    moving_piece = board_before.piece_at(played_move.from_square)
    moving_piece_type = moving_piece.piece_type if moving_piece else None
    moving_piece_color = moving_piece.color if moving_piece else None

    is_capture = board_before.is_capture(played_move)
    captured_piece = None
    if is_capture:
        # Detect en-passant: in EP, the captured pawn is NOT on
        # played_move.to_square — it's one rank behind/ahead.
        if board_before.is_en_passant(played_move):
            captured_piece = chess.Piece(chess.PAWN, not board_before.turn)
        else:
            captured_piece = board_before.piece_at(played_move.to_square)
    captured_piece_type_name = (
        PIECE_TYPE_NAMES.get(captured_piece.piece_type)
        if captured_piece else None
    )

    is_check = board_after.is_check()
    is_checkmate = board_after.is_checkmate()
    is_castling = board_before.is_castling(played_move)
    is_promotion = played_move.promotion is not None
    forced_recapture = _is_forced_recapture(board_before, played_move)

    target_square = chess.square_name(played_move.to_square)
    from_square = chess.square_name(played_move.from_square)

    # ── Attack/defense math (raw lists; SEE comes in commit #2) ────────
    # All measured on board_after (the position after the move).
    own_color = moving_piece_color if moving_piece_color is not None else board_before.turn
    opp_color = not own_color

    attackers_on_target = _attackers_of(board_after, opp_color, played_move.to_square)
    defenders_on_target = _attackers_of(board_after, own_color, played_move.to_square)

    # ── Phase ──────────────────────────────────────────────────────────
    full_move = full_move_number or board_before.fullmove_number
    phase = _detect_phase(board_before, full_move)

    # ── Opening (uses existing detector) ───────────────────────────────
    opening_name = None
    opening_variation = None
    opening_key = None
    try:
        from services.opening_mastery import detect_opening_from_moves
        # Include the played move so the detector sees the current position
        history_inc_played = list(move_history_san) + [played_san]
        info = detect_opening_from_moves(history_inc_played)
        if info:
            opening_name = info.get("opening_name")
            opening_variation = info.get("variation")
            opening_key = info.get("opening_key")
    except Exception:
        # Detector unavailable — opening facts stay None
        pass

    # ── Game-state flags (purely from eval — no chess judgment) ────────
    # "user_is_winning" is from the PERSPECTIVE OF THE SIDE WHO JUST MOVED.
    # eval_after_cp is from white's POV per standard engine convention,
    # so we flip for black.
    user_eval_after = eval_after_cp
    if user_eval_after is not None and own_color == chess.BLACK:
        user_eval_after = -user_eval_after
    user_is_winning = (user_eval_after is not None) and (user_eval_after >= 200)
    user_is_losing = (user_eval_after is not None) and (user_eval_after <= -200)

    # ── Move-history facts ─────────────────────────────────────────────
    move_index = len(move_history_san)  # 0-based ply index of the played move

    # ── Build the facts dict ───────────────────────────────────────────
    facts: Dict[str, Any] = {
        # ENGINE TRUTH (pass-through)
        "cp_loss": cp_loss,
        "eval_before_cp": eval_before_cp,
        "eval_after_cp": eval_after_cp,
        "best_move_san": best_move_san,
        "played_san": played_san,
        "played_is_best": played_is_best,
        "pv_after_played": list(pv_after_played),
        "pv_after_best": list(pv_after_best),

        # POSITION FACTS
        "fen_before": fen_before,
        "fen_after": board_after.fen(),
        "from_square": from_square,
        "target_square": target_square,
        "moving_piece_type": PIECE_TYPE_NAMES.get(moving_piece_type) if moving_piece_type else None,
        "moving_piece_color": "white" if own_color == chess.WHITE else "black",
        "is_capture": is_capture,
        "captured_piece_type": captured_piece_type_name,
        "is_check": is_check,
        "is_checkmate": is_checkmate,
        "is_castling": is_castling,
        "is_promotion": is_promotion,
        "is_forced_recapture": forced_recapture,
        "is_pawn_move": moving_piece_type == chess.PAWN,

        # ATTACK / DEFENSE — RAW LISTS (SEE arrives commit #2)
        "attackers_on_target": attackers_on_target,
        "defenders_on_target": defenders_on_target,
        "attacker_count": len(attackers_on_target),
        "defender_count": len(defenders_on_target),

        # PHASE / MOVE INDEX
        "phase": phase,
        "move_index": move_index,
        "full_move_number": full_move,

        # OPENING (best-effort; None when no match)
        "opening_name": opening_name,
        "opening_variation": opening_variation,
        "opening_key": opening_key,
        "is_book_move": opening_name is not None and move_index <= 12,

        # GAME-STATE FLAGS (purely eval-derived)
        "user_is_winning": user_is_winning,
        "user_is_losing": user_is_losing,

        # PLACEHOLDERS for fields arriving in subsequent commits.
        # Renderer rules MUST check is None before reading these.
        "see_played_capture_cp": None,         # commit #2
        "see_target_square_cp": None,          # commit #2
        "is_exchange_losing": None,            # commit #2
        "exchange_loss_cp": None,              # commit #2
        "threats_created": None,               # commit #2
        "pieces_now_undefended": None,         # commit #2
        "tactics_detected": None,              # commit #3 — list of evidence dicts
        "material_delta_played_cp": None,      # commit #3
        "material_delta_best_cp": None,        # commit #3
        "free_capture": None,                  # commit #3
        "missed_tactic": None,                 # commit #3
        "queen_out_early": None,               # commit #3
        "opponent_queen_out_early": None,      # commit #3
        "primary_reason": None,                # commit #4
    }

    return facts


# ────────────────────────────────────────────────────────────────────
# CLI — pure replayability per LAW 4
# ────────────────────────────────────────────────────────────────────

def _main() -> int:
    p = argparse.ArgumentParser(
        description="Extract caption facts for a single move. Pure function, "
                    "no DB access. Output is JSON. Used to inspect what the "
                    "extractor sees for any (FEN, move) pair without booting "
                    "the rest of the app."
    )
    p.add_argument("--fen", required=True,
                   help="FEN of the position BEFORE the move.")
    p.add_argument("--move", required=True,
                   help="The played move in SAN (e.g. Nf3).")
    p.add_argument("--best", default=None,
                   help="The engine's best move in SAN.")
    p.add_argument("--eval-before", type=int, default=None,
                   help="Eval in centipawns from white's POV before the move.")
    p.add_argument("--eval-after", type=int, default=None,
                   help="Eval in centipawns from white's POV after the move.")
    p.add_argument("--cp-loss", type=int, default=0,
                   help="cp_loss from the side-to-move's POV.")
    p.add_argument("--pv-played", default="",
                   help="Space-separated SAN list of pv_after_played.")
    p.add_argument("--pv-best", default="",
                   help="Space-separated SAN list of pv_after_best.")
    p.add_argument("--history", default="",
                   help="Space-separated SAN list of moves played BEFORE the position.")
    p.add_argument("--full-move", type=int, default=None,
                   help="Full move number.")
    args = p.parse_args()

    facts = extract_facts(
        fen_before=args.fen,
        played_san=args.move,
        best_move_san=args.best,
        eval_before_cp=args.eval_before,
        eval_after_cp=args.eval_after,
        cp_loss=args.cp_loss,
        pv_after_played=args.pv_played.split() if args.pv_played else [],
        pv_after_best=args.pv_best.split() if args.pv_best else [],
        move_history_san=args.history.split() if args.history else [],
        full_move_number=args.full_move,
    )
    json.dump(facts, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    # Allow `python -m services.caption_facts ...` from backend/ root
    sys.exit(_main())
