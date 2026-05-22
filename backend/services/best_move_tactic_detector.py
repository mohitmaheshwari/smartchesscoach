"""Detects the tactical idea behind the engine's best move by walking
`pv_after_best` with python-chess.

Closes Mohit-flagged gap (2026-05-20): captions said
"{best_move} was better" without explaining WHY. The user is left
guessing what tactic the engine saw. The detector walks the PV from
the position after best_move and identifies the climax:

  - mate_in_N — PV contains a `#` mate move by the user side
  - piece_capture — PV contains a user-side capture of a piece worth
    >= knight value (the actionable "you'd win the queen/rook/etc.")
  - material — PV contains user-side pawn captures only (no piece)
  - None — nothing significant, PV is positional / quiet

The result feeds R12_blunder.json `why_clauses_user` predicates so the
phrasing lives in JSON. Python only extracts chess data here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    import chess
except Exception:  # pragma: no cover — defensive
    chess = None  # type: ignore

logger = logging.getLogger(__name__)


_PIECE_NAME = {
    1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king",
}
_PIECE_VALUE = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 100}


def detect_missed_tactic(
    fen_before: Optional[str],
    best_move_san: Optional[str],
    pv_after_best: List[str],
    user_color: str,
    eval_before_cp: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Walk the principal variation after engine's recommended move,
    return a structured payload describing the tactical climax.

    Args:
      fen_before: FEN of the position BEFORE the user's actual move
        (the position where best_move was the engine's choice).
      best_move_san: Engine's recommended move (SAN).
      pv_after_best: List of SAN moves played AFTER best_move was made,
        alternating opp, user, opp, user, ...
      user_color: "white" or "black"
      eval_before_cp: Stockfish's eval before any move was played (cp,
        from white's POV). Used to GUARD piece_capture claims — a PV
        capture only counts as "winning a piece" if the engine's eval
        truly reflects piece-up territory for the user. Without this
        check the detector over-claims (e.g. user "wins the queen"
        when the engine just sees +250cp because of an implicit
        recapture past the PV horizon).

    Returns one of (highest-priority match wins):
      {"kind": "mate", "ply": N, "mating_move": "Qxf7#"}
      {"kind": "piece_capture", "piece_type": "queen",
       "square": "d8", "capturing_move": "Nxd8", "ply": N}
      {"kind": "material", "captures": N}
      None — no actionable tactic in the PV

    Decision logic:
      - mate found in PV → "mate" (unambiguous, always claim)
      - user-side piece capture (knight+) in PV AND user_eval_at_best
        is in piece-up territory (>= +500cp from user POV) AND net
        captures within PV favor user → "piece_capture"
      - net captures within PV favor user (any value, including pawns) →
        "material" (honest about magnitude without overclaiming)
      - otherwise → None
    """
    if not chess or not fen_before or not best_move_san or not pv_after_best:
        return None

    try:
        board = chess.Board(fen_before)
        best_move_obj = board.parse_san(best_move_san)
        board.push(best_move_obj)
    except Exception as exc:
        logger.warning(f"[tactic_detector] bad fen or best_move: {exc}")
        return None

    user_piece_captures: List[Dict[str, Any]] = []
    user_pawn_captures = 0
    opp_captures_value = 0  # net opp gain within PV (recaptures inside the window)
    mate_payload: Optional[Dict[str, Any]] = None

    # pv[0] is played by OPP, pv[1] by user, alternating.
    for ply_index, san in enumerate(pv_after_best):
        is_user_move = (ply_index % 2 == 1)
        try:
            move = board.parse_san(san)
        except Exception:
            break

        is_capture = board.is_capture(move)
        captured_piece_type = None
        captured_square = None
        if is_capture:
            captured_square = chess.square_name(move.to_square)
            if board.is_en_passant(move):
                captured_piece_type = 1
            else:
                cap_piece = board.piece_at(move.to_square)
                captured_piece_type = cap_piece.piece_type if cap_piece else None

        board.push(move)
        if board.is_checkmate() and is_user_move:
            mate_payload = {
                "kind": "mate",
                "ply": ply_index + 1,
                "mating_move": san,
            }
            break

        if is_capture and captured_piece_type:
            if is_user_move:
                if captured_piece_type >= 2:
                    user_piece_captures.append({
                        "kind": "piece_capture",
                        "piece_type": _PIECE_NAME.get(captured_piece_type, "piece"),
                        "piece_value": _PIECE_VALUE.get(captured_piece_type, 0),
                        "square": captured_square,
                        "capturing_move": san,
                        "ply": ply_index + 1,
                    })
                else:
                    user_pawn_captures += 1
            else:
                # Opponent recapture inside the PV window — eats into
                # the user's gain.
                opp_captures_value += _PIECE_VALUE.get(captured_piece_type, 0)

    if mate_payload:
        return mate_payload

    # Net the user gain against any opp recapture seen within the PV.
    user_gain = sum(c["piece_value"] for c in user_piece_captures) + user_pawn_captures
    net_user_gain = user_gain - opp_captures_value

    # Threshold guard for piece_capture: the engine's stored eval must
    # actually support a piece-up advantage from the user's POV. For a
    # white user, eval_before_cp >= +400 means white has minor-piece-up
    # territory; for black, eval_before_cp <= -400. Without this guard
    # the detector over-claims when the PV contains a capture whose
    # recapture lives past the PV horizon (engine knows about it via
    # eval; the PV doesn't show it).
    #
    # Threshold lowered 500 → 400 (Mohit 2026-05-21) so that real
    # sacrifice tactics — where the user gives up a minor piece to
    # win a queen, netting +4cp on the board but +400-450cp by engine
    # eval — still credit as piece_capture instead of degrading to
    # the engine-speak "material" fallback. Found via Bb5+ on
    # rnbqkb1r/pp3ppp/1n1p4/4p3/2B5/5N2/PPP2PPP/RNBQR1K1: Nxe5 dxe5
    # Bxf7+ Kxf7 Qxd8 wins the queen but engine eval is only +431cp
    # because of the bishop+knight investment.
    #
    # Threshold lowered again 400 → 250 (Mohit 2026-05-22). The 400cp
    # threshold was still rejecting clean piece-win captions when the
    # engine's eval was held back by black's compensation (e.g. open
    # files, active piece). Examples from pending_review:
    #   - row #003 (Bxa6): eval +379 — rejected at 400
    #   - row #009 (Nxe5): eval +295 — rejected at 400
    #   - row #014 (Nxe5): eval +57 — rejected at 400 (but PV win is real)
    #   - row #025 (Nxe5): eval +140 — rejected at 400
    # In all these cases the PV shows a real piece/pawn win; the lower
    # threshold catches them. 250cp = engine sees ~ +2.5 pawn advantage
    # which is enough to back the claim without over-reaching.
    user_color_white = (user_color or "").lower() == "white"
    user_eval_at_best = None
    if eval_before_cp is not None:
        user_eval_at_best = eval_before_cp if user_color_white else -eval_before_cp

    if user_piece_captures and net_user_gain >= 3:
        if user_eval_at_best is None or user_eval_at_best >= 250:
            best_capture = max(user_piece_captures, key=lambda c: c["piece_value"])
            return {
                "kind": "piece_capture",
                "piece_type": best_capture["piece_type"],
                "square": best_capture["square"],
                "capturing_move": best_capture["capturing_move"],
                "ply": best_capture["ply"],
            }
        # Piece appears in PV but engine eval doesn't back a piece-up
        # claim — there's an implicit recapture past the PV horizon.
        # Downgrade to honest "material" claim.

    if net_user_gain >= 1:
        return {"kind": "material", "captures": user_pawn_captures + len(user_piece_captures)}

    return None
