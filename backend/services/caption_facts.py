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

from services.caption_config import MAX_CP_LOSS_FOR_TACTIC_CELEBRATION


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
    chess.KING: 0,  # king has no exchange value (SEE caps before king capture)
}

# Phase boundary thresholds (mirrors detect_phase in game_decryption_v5_service)
_OPENING_MAX_MOVE_HIGH_PIECES = 10  # if piece_count >= 28
_OPENING_MAX_MOVE_MID_PIECES = 15   # if piece_count >= 24

# Eval thresholds — kept inside the extractor so renderers don't drift
# into their own "winning/losing" semantics. Numeric, deterministic,
# universally reusable. Renderers consume the booleans, not the threshold.
EVAL_WINNING_THRESHOLD_CP = 200    # user_is_winning when user_eval_after >= +200cp
EVAL_LOSING_THRESHOLD_CP = -200    # user_is_losing  when user_eval_after <= -200cp

# Exchange loss threshold — for is_exchange_losing flag (Phase 2).
# A move whose SEE loses more than this counts as a material-losing
# exchange. Set above small-fluctuation noise (a half-pawn).
EXCHANGE_LOSS_THRESHOLD_CP = 50


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


# ────────────────────────────────────────────────────────────────────
# Static Exchange Evaluation (SEE) — chess-textbook capture-sequence math.
#
# Walks the recapture sequence on a target square. At each ply, the side
# to move uses their CHEAPEST available attacker and the OPPOSING side
# (now to move) decides whether to continue or stop. The "stop or
# continue" choice is the standard backwards pass:
#     gain[d] = -max(-gain[d], gain[d+1])
#
# Returns SEE in centipawns from the INITIATING side's perspective:
#     SEE > 0  → exchange wins material for initiator
#     SEE == 0 → even trade (or exchange not played)
#     SEE < 0  → exchange loses material; initiator should NOT initiate
#
# Why we need SEE instead of raw attacker/defender counts:
#   - pinned defenders don't really defend
#   - x-ray defenders/attackers need lining up
#   - piece-value imbalance: P-defended Q is still lost to a R attack
#   - recapture order matters (cheapest-first or you waste material)
# Counts get all of these wrong. SEE gets them right by simulation.
#
# Implementation notes:
#   - We exclude pieces already used in earlier captures from being
#     reused (the `consumed` set).
#   - Pinned attackers that can't legally move to the target are skipped
#     (would otherwise hang the king).
#   - En-passant is supported: the captured pawn is identified before
#     the simulated move.
# ────────────────────────────────────────────────────────────────────

def _square_set(squares) -> chess.SquareSet:
    """Tolerant SquareSet builder accepting iterables of squares."""
    if isinstance(squares, chess.SquareSet):
        return squares
    out = chess.SquareSet()
    for sq in squares:
        out.add(sq)
    return out


def _is_pinned_against_target(board: chess.Board, attacker_sq: int, target_sq: int) -> bool:
    """True if the piece on `attacker_sq` is absolutely pinned in a way
    that prevents it from moving to `target_sq` (i.e. moving there
    would expose its own king).

    Uses python-chess `board.pin(color, square)` which returns the set
    of squares the pinned piece CAN move to along the pin line. This
    check is TURN-INDEPENDENT — works whether or not the piece's side
    is currently to move (important inside SEE simulation where we
    flip sides on each ply without actually pushing moves).
    """
    piece = board.piece_at(attacker_sq)
    if not piece:
        return True
    if not board.is_pinned(piece.color, attacker_sq):
        return False
    # Get the squares the pinned piece can still legally reach.
    pin_mask = board.pin(piece.color, attacker_sq)
    # pin_mask may be a SquareSet or an int bitboard depending on version
    if isinstance(pin_mask, chess.SquareSet):
        return target_sq not in pin_mask
    return not (chess.BB_SQUARES[target_sq] & pin_mask)


def static_exchange_eval(board: chess.Board, target_sq: int, initiating_side: chess.Color) -> int:
    """
    Compute SEE on `target_sq` assuming `initiating_side` makes the
    first capture using their cheapest legal attacker. Returns net
    material in centipawns from `initiating_side`'s POV.

    If `initiating_side` has no legal attacker on `target_sq`, returns 0.
    """
    # Find cheapest legal NON-KING attacker from initiating_side.
    # Kings are excluded from SEE recapture sequences by convention:
    # a king "recapture" is only legal when no other opponent attacker
    # remains AND the destination square isn't attacked. Modelling that
    # exactly is fragile; the conservative choice (skip the king) yields
    # SEE estimates that are correct in middlegame positions and slightly
    # too-cautious in some K+P endgames. Tracked as a Phase-1 limitation
    # in design doc §18.1.
    attackers = board.attackers(initiating_side, target_sq)
    if not attackers:
        return 0

    cheapest_sq = None
    cheapest_val = 10 ** 9
    for sq in attackers:
        piece = board.piece_at(sq)
        if not piece:
            continue
        if piece.piece_type == chess.KING:
            continue
        if _is_pinned_against_target(board, sq, target_sq):
            continue
        val = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if val < cheapest_val:
            cheapest_val = val
            cheapest_sq = sq

    if cheapest_sq is None:
        return 0

    captured = board.piece_at(target_sq)
    if not captured:
        return 0
    captured_val = PIECE_VALUE_CP.get(captured.piece_type, 0)

    # First capture
    gain = [captured_val]
    current_piece_val = cheapest_val  # piece that just moved onto target
    consumed = {cheapest_sq}
    side = not initiating_side

    while True:
        # Same king-skip rule applies on every recapture ply.
        candidates = board.attackers(side, target_sq) & ~_square_set(consumed)
        cheapest_sq = None
        cheapest_val_iter = 10 ** 9
        for sq in candidates:
            piece = board.piece_at(sq)
            if not piece:
                continue
            if piece.piece_type == chess.KING:
                continue
            if _is_pinned_against_target(board, sq, target_sq):
                continue
            val = PIECE_VALUE_CP.get(piece.piece_type, 0)
            if val < cheapest_val_iter:
                cheapest_val_iter = val
                cheapest_sq = sq

        if cheapest_sq is None:
            break

        gain.append(current_piece_val - gain[-1])
        consumed.add(cheapest_sq)
        current_piece_val = cheapest_val_iter
        side = not side

    # Backwards pass: at each level, the side can choose not to continue.
    for d in range(len(gain) - 2, -1, -1):
        gain[d] = -max(-gain[d], gain[d + 1])

    return gain[0]


def _see_for_played_move(board_before: chess.Board, played_move: chess.Move) -> Optional[int]:
    """Return SEE for a capture move (the played side's perspective),
    or None if the move is not a capture."""
    if not board_before.is_capture(played_move):
        return None
    # Compute SEE on the target square with the played side as initiator.
    initiator = board_before.turn
    return static_exchange_eval(board_before, played_move.to_square, initiator)


def _target_square_exchange_cp(board_after: chess.Board, target_sq: int) -> Optional[int]:
    """For NON-CAPTURE moves: after the played move, would the opponent
    capturing on `target_sq` win material? Returns SEE from the
    opponent's POV (positive = they win material by capturing).
    Returns None when there's nothing on target_sq.

    Named target_square_exchange_cp (was see_target_square_cp) to prevent
    semantic overload — there are now multiple SEE-flavoured fields and
    each one needs to say WHICH exchange it represents.
    """
    piece_on_target = board_after.piece_at(target_sq)
    if not piece_on_target:
        return None
    initiator = board_after.turn  # opponent is to move in board_after
    return static_exchange_eval(board_after, target_sq, initiator)


def _exchange_participants(
    board: chess.Board,
    target_sq: int,
    initiating_side: chess.Color,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Return (effective_attackers, effective_defenders) — the pieces
    that would actually participate in the SEE sequence in cheapest-
    first order, with pinned-against-king pieces filtered out.

    Distinct from raw `attackers_on_target` / `defenders_on_target`
    which list ALL pieces with line-of-sight regardless of legality.
    """
    eff_attackers: List[Tuple[str, str]] = []
    eff_defenders: List[Tuple[str, str]] = []

    # Walk the exchange sequence. We don't actually need the SEE result
    # here — just the order of participants.
    consumed: set = set()
    side = initiating_side

    while True:
        attackers = board.attackers(side, target_sq) & ~_square_set(consumed)
        cheapest_sq = None
        cheapest_val = 10 ** 9
        for sq in attackers:
            piece = board.piece_at(sq)
            if not piece:
                continue
            if piece.piece_type == chess.KING:
                continue  # Kings don't participate in SEE per convention
            if _is_pinned_against_target(board, sq, target_sq):
                continue
            val = PIECE_VALUE_CP.get(piece.piece_type, 0)
            if val < cheapest_val:
                cheapest_val = val
                cheapest_sq = sq
        if cheapest_sq is None:
            break

        piece = board.piece_at(cheapest_sq)
        entry = (chess.square_name(cheapest_sq), PIECE_TYPE_NAMES.get(piece.piece_type, "piece"))
        if side == initiating_side:
            eff_attackers.append(entry)
        else:
            eff_defenders.append(entry)
        consumed.add(cheapest_sq)
        side = not side

    return eff_attackers, eff_defenders


# ────────────────────────────────────────────────────────────────────
# Threats and undefended pieces
# ────────────────────────────────────────────────────────────────────

def _threats_created(
    board_before: chess.Board,
    board_after: chess.Board,
    played_move: chess.Move,
) -> List[Dict[str, Any]]:
    """Return structured evidence of every threat the played move creates.

    A threat is: own piece NOW attacks an enemy piece such that SEE on
    capturing that enemy piece is favorable for us. Evidence (NOT labels)
    per LAW 3 — renderer can render but never re-derive.

    Each threat:
      {
        "attacker_square":          str,   # piece that's now threatening
        "target_square":            str,   # enemy piece being threatened
        "target_piece_type":        str,
        "target_value_cp":          int,
        "see_cp":                   int,   # net material if we capture
        "is_immediate":             bool,  # we'd play it next without prep
        "via_moving_piece":         bool,  # the moving piece is the attacker
        "via_discovered":           bool,  # a different own piece's line opened up
      }
    """
    threats: List[Dict[str, Any]] = []
    own_color = not board_after.turn  # we just moved; board_after.turn is opp
    opp_color = board_after.turn

    # Pre-compute which enemy pieces are attacked by which of OUR pieces
    # in board_before vs board_after. The diff = new threats.
    enemy_squares = [sq for pt in range(chess.PAWN, chess.KING + 1)
                       for sq in board_after.pieces(pt, opp_color)]

    for enemy_sq in enemy_squares:
        enemy_piece = board_after.piece_at(enemy_sq)
        if not enemy_piece or enemy_piece.piece_type == chess.KING:
            continue  # checks are handled by is_check, not threats

        attackers_after = board_after.attackers(own_color, enemy_sq)
        attackers_before = board_before.attackers(own_color, enemy_sq)
        # A NEW attacker is one that's in 'after' but not in 'before'.
        # Or: the from-square was an attacker and it moved away (capture case — handled elsewhere).
        new_attackers = attackers_after - attackers_before
        if not new_attackers:
            continue

        # Pick the cheapest new attacker as the "primary threat-maker"
        cheapest_attacker_sq = None
        cheapest_val = 10 ** 9
        for atk_sq in new_attackers:
            piece = board_after.piece_at(atk_sq)
            if not piece:
                continue
            val = PIECE_VALUE_CP.get(piece.piece_type, 0)
            if val < cheapest_val:
                cheapest_val = val
                cheapest_attacker_sq = atk_sq
        if cheapest_attacker_sq is None:
            continue

        # SEE: if we initiate a capture on enemy_sq, do we win material?
        see_cp = static_exchange_eval(board_after, enemy_sq, own_color)
        if see_cp <= 0:
            continue  # not a winning threat — opponent defends adequately

        # Mutual-line / attacker-survival gate. The above SEE assumes WE
        # initiate, but it's actually opp's move next. If opp can take
        # our threatening attacker at SEE ≥ 0, the threat doesn't
        # materialise — they capture before we get to. From d7ce40cf
        # corpus: #14 Kf1 was emitting "threatens Rxe8 winning the rook"
        # while ...Rxe1+ was the immediate reply on the same cleared line.
        opp_attackers_on_attacker = board_after.attackers(opp_color, cheapest_attacker_sq)
        if opp_attackers_on_attacker:
            opp_see_on_attacker = static_exchange_eval(
                board_after, cheapest_attacker_sq, opp_color
            )
            if opp_see_on_attacker >= 0:
                continue

        attacker_piece = board_after.piece_at(cheapest_attacker_sq)
        target_value_cp = PIECE_VALUE_CP.get(enemy_piece.piece_type, 0)
        # If see_cp < target_value, the winning sequence cost us some
        # material along the way → it required at least one recapture
        # exchange. Renderer uses this to phrase confidently for free
        # captures vs. cautiously for trade-required ones.
        winning_line_requires_recapture = see_cp < target_value_cp

        threats.append({
            "attacker_square": chess.square_name(cheapest_attacker_sq),
            "attacker_piece_type": (
                PIECE_TYPE_NAMES.get(attacker_piece.piece_type, "piece")
                if attacker_piece else "piece"
            ),
            "target_square": chess.square_name(enemy_sq),
            "target_piece_type": PIECE_TYPE_NAMES.get(enemy_piece.piece_type, "piece"),
            "target_value_cp": target_value_cp,
            "see_cp": see_cp,
            "is_immediate": True,  # for now all detected threats are immediate;
                                   # multi-ply threat chains arrive in commit #4.
            "via_moving_piece": cheapest_attacker_sq == played_move.to_square,
            "via_discovered": cheapest_attacker_sq != played_move.to_square,
            "winning_line_requires_recapture": winning_line_requires_recapture,
        })

    # Sort by target value descending — highest-value threat first.
    threats.sort(key=lambda t: -t["target_value_cp"])
    return threats


def _pieces_now_undefended(
    board_before: chess.Board,
    board_after: chess.Board,
    played_move: chess.Move,
) -> List[Dict[str, Any]]:
    """Return own pieces that LOST a defender as a result of the played move.

    Evidence (NOT a label per LAW 3):
      [
        {
          "square":                 str,    # the undefended piece
          "piece_type":             str,
          "piece_color":            "white|black",
          "lost_defender_square":   str | None,  # if a specific defender disappeared
          "lost_defender_piece":    str | None,
          "now_attacked":           bool,   # is this piece under attack from opp?
          "see_if_captured_cp":     int,    # SEE from opp's POV
        },
        ...
      ]

    Computed by diffing defender counts before vs after for each own
    piece. Renderer decides how to phrase it (or whether to mention).
    """
    out: List[Dict[str, Any]] = []
    own_color = not board_after.turn
    opp_color = board_after.turn
    from_sq = played_move.from_square

    # Own pieces that existed BEFORE the move and still exist after.
    # (The moved piece itself is on a different square afterwards — skip.)
    own_squares_before = [
        sq for pt in range(chess.PAWN, chess.KING + 1)
        for sq in board_before.pieces(pt, own_color)
        if sq != from_sq
    ]

    for sq in own_squares_before:
        piece = board_after.piece_at(sq)
        if not piece or piece.color != own_color:
            # Piece was captured during the move (e.g., en passant edge case)
            continue

        defenders_before = board_before.attackers(own_color, sq)
        defenders_after = board_after.attackers(own_color, sq)
        lost = defenders_before - defenders_after

        # Did this piece lose a defender? The from_square will normally
        # appear in `lost` if the moved piece was defending sq.
        if not lost:
            continue

        # Was the lost defender the moved piece?
        lost_defender_sq = None
        lost_defender_piece = None
        if from_sq in lost:
            moved_piece = board_before.piece_at(from_sq)
            if moved_piece:
                lost_defender_sq = chess.square_name(from_sq)
                lost_defender_piece = PIECE_TYPE_NAMES.get(moved_piece.piece_type, "piece")
        else:
            # A different defender disappeared (e.g. through-line broken).
            # Pick the most valuable lost defender.
            best_lost = None
            best_val = -1
            for ldsq in lost:
                piece_lost = board_before.piece_at(ldsq)
                if piece_lost and PIECE_VALUE_CP.get(piece_lost.piece_type, 0) > best_val:
                    best_val = PIECE_VALUE_CP[piece_lost.piece_type]
                    best_lost = (ldsq, piece_lost)
            if best_lost:
                lost_defender_sq = chess.square_name(best_lost[0])
                lost_defender_piece = PIECE_TYPE_NAMES.get(best_lost[1].piece_type, "piece")

        attackers_after = board_after.attackers(opp_color, sq)
        now_attacked = bool(attackers_after)
        # Defenders of `sq` are own-color pieces that ATTACK that square
        # (in chess parlance, defending = attacking your own piece's square).
        # The piece on sq doesn't defend itself.
        remaining_defenders = board_after.attackers(own_color, sq)
        remaining_defender_count = len(remaining_defenders)
        see_if_captured = 0
        if now_attacked:
            see_if_captured = static_exchange_eval(board_after, sq, opp_color)
        # "Hanging" is a strong renderer signal — distinct from "lost a
        # defender but still adequately defended." Defined as:
        # under attack AND the exchange loses material AND no other
        # defender remains. Renderer can branch on this without re-
        # checking geometry.
        is_now_hanging = (
            now_attacked
            and see_if_captured > 0
            and remaining_defender_count == 0
        )

        out.append({
            "square": chess.square_name(sq),
            "piece_type": PIECE_TYPE_NAMES.get(piece.piece_type, "piece"),
            "piece_value_cp": PIECE_VALUE_CP.get(piece.piece_type, 0),
            "piece_color": "white" if piece.color == chess.WHITE else "black",
            "lost_defender_square": lost_defender_sq,
            "lost_defender_piece": lost_defender_piece,
            "now_attacked": now_attacked,
            "see_if_captured_cp": see_if_captured,
            "remaining_defender_count": remaining_defender_count,
            "is_now_hanging": is_now_hanging,
        })

    # Sort: pieces that are now under losing exchange first (highest material at risk).
    out.sort(key=lambda x: -x["see_if_captured_cp"] if x["now_attacked"] else 0)
    return out


# ────────────────────────────────────────────────────────────────────
# Tactic-shape detectors
#
# Each detector emits STRUCTURED EVIDENCE — coordinates, piece types,
# values — never a label like "fork" or "pin". The renderer decides
# whether to call something a fork / double attack / pressure / battery
# based on the evidence + context.
#
# Per LAW 3 in the module docstring. Per user instruction (2026-05-11):
# "Same for pins. DO NOT emit `is_pinned: true`. Emit the geometric
# evidence of the line."
# ────────────────────────────────────────────────────────────────────

def _multi_target_attack_evidence(threats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group `threats_created` entries by attacker_square. Any attacker
    with ≥2 separately-winning threats forms a multi-target-attack shape.

    NAMED `multi_target_attack` rather than `fork`: the geometric primitive
    is "one piece, multiple targets." The renderer decides whether to
    call it "fork" / "double attack" / "pressure on two pieces" based on
    context (piece type, target values, position).
    """
    by_attacker: Dict[str, List[Dict[str, Any]]] = {}
    for t in threats:
        by_attacker.setdefault(t["attacker_square"], []).append(t)

    out: List[Dict[str, Any]] = []
    for attacker_sq, ts in by_attacker.items():
        if len(ts) < 2:
            continue
        # Sort targets by value descending so renderer sees the most valuable first
        targets_sorted = sorted(ts, key=lambda t: -t["target_value_cp"])
        out.append({
            "attacker_square": attacker_sq,
            "attacker_piece_type": ts[0]["attacker_piece_type"],
            "attacked_targets": [
                {
                    "square": t["target_square"],
                    "piece_type": t["target_piece_type"],
                    "value_cp": t["target_value_cp"],
                    "see_cp": t["see_cp"],
                }
                for t in targets_sorted
            ],
            "via_moving_piece": all(t.get("via_moving_piece", False) for t in ts),
        })
    # Sort fork shapes by the highest-value target descending
    out.sort(key=lambda f: -f["attacked_targets"][0]["value_cp"])
    return out


# Pin/skewer shapes share a common geometry: a sliding own piece lines
# up two enemy pieces. The difference is value ordering of front/rear.
# The renderer decides terminology; the extractor only emits evidence.

_SLIDING_PIECE_TYPES = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def _ray_squares(from_sq: int, direction: Tuple[int, int]) -> List[int]:
    """Walk a (dx, dy) direction from from_sq, yielding each on-board
    square in order until off-board."""
    df, dr = direction
    file_, rank_ = chess.square_file(from_sq), chess.square_rank(from_sq)
    out: List[int] = []
    while True:
        file_ += df
        rank_ += dr
        if not (0 <= file_ < 8 and 0 <= rank_ < 8):
            break
        out.append(chess.square(file_, rank_))
    return out


def _piece_can_move_along_line(
    board: chess.Board,
    piece_square: int,
    line_squares: List[int],
) -> bool:
    """Returns True if the piece on `piece_square` can move to ANY square
    in `line_squares` legally. Used to determine whether a pinned piece
    can still slide along the pin line (e.g. a rook pinned on a file can
    still move on the file)."""
    piece = board.piece_at(piece_square)
    if not piece:
        return False
    # We don't need legal_moves (turn-dependent). We check pin geometry:
    # piece can move along the line iff the line direction is the SAME
    # as the pin direction. python-chess `board.pin(color, sq)` returns
    # the SquareSet of legal destinations (along the pin line).
    pin_mask = board.pin(piece.color, piece_square)
    if isinstance(pin_mask, chess.SquareSet):
        return any(sq in pin_mask for sq in line_squares)
    return any(bool(chess.BB_SQUARES[sq] & pin_mask) for sq in line_squares)


def _aligned_pieces_evidence(
    board_after: chess.Board,
    own_color: chess.Color,
) -> List[Dict[str, Any]]:
    """Return ALL aligned-piece configurations seen in board_after — the
    geometric shape that the renderer can interpret as a pin / skewer /
    x-ray depending on value relations.

    For each own sliding piece (bishop, rook, queen), walk its rays.
    If a ray hits enemy piece A then enemy piece B (further along,
    same line), emit one evidence dict with a `front_value_vs_rear`
    flag — "lower" | "higher" | "equal" — that lets the renderer
    decide naming.

    NAMED `aligned_pieces` rather than `pin_shape`/`skewer_shape`:
    pin and skewer are RENDER-time names; the geometric primitive is
    "three pieces on a line." Merging them into one field with a value-
    comparison flag prevents the extractor from cementing renderer
    taxonomy (per user feedback 2026-05-11).
    """
    out: List[Dict[str, Any]] = []
    opp_color = not own_color

    # Directions per piece type
    DIAGONAL_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    ORTHO_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    sliding_pieces = []
    for piece_type in _SLIDING_PIECE_TYPES:
        for sq in board_after.pieces(piece_type, own_color):
            sliding_pieces.append((sq, piece_type))

    for slider_sq, slider_type in sliding_pieces:
        if slider_type == chess.BISHOP:
            dirs = DIAGONAL_DIRS
        elif slider_type == chess.ROOK:
            dirs = ORTHO_DIRS
        else:  # QUEEN
            dirs = DIAGONAL_DIRS + ORTHO_DIRS

        slider_piece = board_after.piece_at(slider_sq)

        for direction in dirs:
            ray = _ray_squares(slider_sq, direction)
            # Walk along the ray, collecting up to 2 enemy pieces.
            first_enemy = None
            second_enemy = None
            blocked_by_own = False
            for sq in ray:
                piece = board_after.piece_at(sq)
                if not piece:
                    continue
                if piece.color == own_color:
                    blocked_by_own = True
                    break
                if first_enemy is None:
                    first_enemy = (sq, piece)
                else:
                    second_enemy = (sq, piece)
                    break
            if blocked_by_own or first_enemy is None or second_enemy is None:
                continue

            front_sq, front_piece = first_enemy
            rear_sq, rear_piece = second_enemy
            front_val = PIECE_VALUE_CP.get(front_piece.piece_type, 0)
            rear_val = PIECE_VALUE_CP.get(rear_piece.piece_type, 0)

            # Front-vs-rear value comparison (renderer decides taxonomy):
            #   "lower"  → front cheaper than rear  (classic pin shape)
            #   "higher" → front more valuable      (classic skewer shape)
            #   "equal"  → renderer's call          (e.g. R+R battery, N+B)
            if front_val < rear_val:
                front_value_vs_rear = "lower"
            elif front_val > rear_val:
                front_value_vs_rear = "higher"
            else:
                front_value_vs_rear = "equal"

            line_kind = (
                "diagonal" if direction in DIAGONAL_DIRS else
                ("file" if direction[0] == 0 else "rank")
            )

            # Can the front piece move along this line (sliding piece
            # of same direction)? If not, even a non-king rear creates
            # an effective pin.
            front_can_move_along = False
            front_pt = front_piece.piece_type
            if front_pt == chess.QUEEN:
                front_can_move_along = True
            elif front_pt == chess.ROOK and line_kind in ("file", "rank"):
                front_can_move_along = True
            elif front_pt == chess.BISHOP and line_kind == "diagonal":
                front_can_move_along = True

            out.append({
                "attacker_square": chess.square_name(slider_sq),
                "attacker_piece_type": PIECE_TYPE_NAMES.get(slider_type, "piece"),
                "front_piece_square": chess.square_name(front_sq),
                "front_piece_type": PIECE_TYPE_NAMES.get(front_piece.piece_type, "piece"),
                "front_piece_value_cp": front_val,
                "rear_piece_square": chess.square_name(rear_sq),
                "rear_piece_type": PIECE_TYPE_NAMES.get(rear_piece.piece_type, "piece"),
                "rear_piece_value_cp": rear_val,
                "line_kind": line_kind,
                "front_value_vs_rear": front_value_vs_rear,
                "front_can_move_along_line": front_can_move_along,
                "rear_is_king": rear_piece.piece_type == chess.KING,
                "front_is_king": front_piece.piece_type == chess.KING,
            })

    return out


def _discovered_attack_evidence(
    board_before: chess.Board,
    board_after: chess.Board,
    played_move: chess.Move,
) -> List[Dict[str, Any]]:
    """If the played move's from_square was on a line between an own
    sliding piece and an enemy piece, the move uncovered the slider's
    attack. Emit evidence per such uncovered line.

    Pure geometry — slider on one side, played-move from_square in the
    middle, enemy piece on the other side. After the move, the line is
    open and the slider attacks the enemy.

    NAMED `discovered_attack` rather than `discovery_shape`: cleaner
    primitive; the "shape" suffix added no information.
    """
    out: List[Dict[str, Any]] = []
    own_color = not board_after.turn  # we just moved
    opp_color = board_after.turn
    from_sq = played_move.from_square

    # For each own sliding piece, walk rays. If a ray passes through
    # from_sq (the played move's origin) and lands on an enemy piece,
    # AND the slider doesn't attack that enemy in board_before but DOES
    # in board_after, → discovered attack.
    for piece_type in _SLIDING_PIECE_TYPES:
        for slider_sq in board_after.pieces(piece_type, own_color):
            if slider_sq == played_move.to_square:
                continue  # the moving piece itself isn't doing "discovery"
            # Walk all rays from slider_sq
            slider_piece = board_after.piece_at(slider_sq)
            if piece_type == chess.BISHOP:
                dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
            elif piece_type == chess.ROOK:
                dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            else:
                dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1),
                        (1, 0), (-1, 0), (0, 1), (0, -1)]
            for direction in dirs:
                ray = _ray_squares(slider_sq, direction)
                if from_sq not in ray:
                    continue
                # Find the first piece on this ray AFTER from_sq.
                from_idx = ray.index(from_sq)
                target_sq = None
                target_piece = None
                for sq in ray[from_idx + 1:]:
                    p = board_after.piece_at(sq)
                    if p:
                        target_sq = sq
                        target_piece = p
                        break
                if target_sq is None or target_piece is None:
                    continue
                if target_piece.color == own_color:
                    continue  # uncovered to an own piece — not a threat
                if target_piece.piece_type == chess.KING:
                    # Discovered CHECK — emit separately; renderer will pick
                    # check-with-bonus template (R06) but the discovery
                    # evidence is useful for explaining why.
                    pass
                # Verify it's actually a NEW attack — in board_before the
                # slider's attack on target_sq was blocked by the piece
                # on from_sq.
                if board_before.is_attacked_by(own_color, target_sq):
                    # The slider already attacked this square via another
                    # path; not a real discovery for this target.
                    # Heuristic: check if from_sq blocks the line in board_before
                    pre_attackers = board_before.attackers(own_color, target_sq)
                    if slider_sq in pre_attackers:
                        continue  # slider already attacked via clear line

                # Mutual-line gate. The line that opened works both ways
                # — opponent may now see our slider through the same gap.
                # Since it's opp's move next, if they can capture our
                # slider at SEE ≥ 0 the discovered attack is illusory:
                # the slider is taken before it can execute the discovery.
                # From d7ce40cf corpus: #14 Kf1 was emitting "uncovers
                # rook hitting e8" while black's Rxe1+ was right there.
                opp_attackers_on_slider = board_after.attackers(opp_color, slider_sq)
                if opp_attackers_on_slider:
                    opp_see_on_slider = static_exchange_eval(
                        board_after, slider_sq, opp_color
                    )
                    if opp_see_on_slider >= 0:
                        continue
                out.append({
                    "discovered_attacker_square": chess.square_name(slider_sq),
                    "discovered_attacker_piece_type": PIECE_TYPE_NAMES.get(piece_type, "piece"),
                    "moved_piece_from_square": chess.square_name(from_sq),
                    "target_square": chess.square_name(target_sq),
                    "target_piece_type": PIECE_TYPE_NAMES.get(target_piece.piece_type, "piece"),
                    "target_value_cp": PIECE_VALUE_CP.get(target_piece.piece_type, 0),
                    "is_check": target_piece.piece_type == chess.KING,
                    "line_direction": direction,
                })
    return out


# ────────────────────────────────────────────────────────────────────
# PV material walks + mate threat detection
#
# SEE tells us about IMMEDIATE exchange material. The PV walk tells us
# about MULTI-PLY tactical material — e.g. a 4-ply combination that
# wins a piece in the third move. SEE alone misses these; the PV walk
# resolves them.
#
# Mate threat detection: walks the PV for checkmate notation (#) or
# detects mate-distance via eval sentinel. Mate priority overrides
# material in primary_reason scoring.
# ────────────────────────────────────────────────────────────────────


def _side_material_cp(board: chess.Board, color: chess.Color) -> int:
    """Sum of piece values for `color` in board. Excludes king (no
    SEE value). Centipawns."""
    total = 0
    for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(pt, color)) * PIECE_VALUE_CP[pt]
    return total


def _normalize_pv_starting_with(
    leading_san: Optional[str], pv: List[str]
) -> List[str]:
    """Ensure the PV list starts with `leading_san`. Different engine
    record formats include or omit the leading move; this helper makes
    walks idempotent regardless.

    Returns a NEW list; doesn't mutate input.
    """
    if not leading_san:
        return list(pv)
    leading_clean = _normalize_san(leading_san)
    if pv and _normalize_san(pv[0]) == leading_clean:
        return list(pv)
    return [leading_san] + list(pv)


def _pv_material_delta(
    board_before: chess.Board,
    pv_san: List[str],
    initiator_color: chess.Color,
    max_plies: int = 8,
) -> int:
    """Walk the PV (SAN list) up to `max_plies` plies; return net
    material change for `initiator_color` in centipawns.

    Positive = initiator gained material.
    Returns 0 if the PV can't be replayed cleanly.
    """
    if not pv_san:
        return 0

    sim = board_before.copy()
    init_own = _side_material_cp(sim, initiator_color)
    init_opp = _side_material_cp(sim, not initiator_color)

    plies_pushed = 0
    for san in pv_san[:max_plies]:
        try:
            move = sim.parse_san(san)
            sim.push(move)
            plies_pushed += 1
        except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
            break

    if plies_pushed == 0:
        return 0

    final_own = _side_material_cp(sim, initiator_color)
    final_opp = _side_material_cp(sim, not initiator_color)

    own_delta = final_own - init_own         # ≤ 0 (can only lose pieces)
    opp_delta = final_opp - init_opp         # ≤ 0
    # Net gain for initiator = pieces they took (= -opp_delta) minus
    # pieces they lost (= -own_delta). Equivalent: own_delta - opp_delta.
    return own_delta - opp_delta


def _pv_resolves_to_mate(pv_san: List[str], max_plies: int = 8) -> Optional[int]:
    """If the PV ends in checkmate (SAN ending with '#'), return the
    1-indexed ply at which mate is delivered. Otherwise None.
    """
    for i, san in enumerate(pv_san[:max_plies]):
        if san.endswith("#"):
            return i + 1
    return None


def _mate_threat_evidence(
    eval_after_cp: Optional[int],
    pv_after_played: List[str],
    pv_after_best: List[str],
    own_color: chess.Color,
    is_checkmate: bool = False,
) -> Optional[Dict[str, Any]]:
    """Detect forced mate from PV + eval sentinels. Returns an evidence
    dict or None.

    Four signal sources, in order:
      0. board_after.is_checkmate() — the PLAYED move just delivered
         mate. This is the strongest possible signal; the PV is empty
         because the game is over, so PV-scanning won't find it.
         From d7ce40cf corpus: #24 OPP Rd1# was being classed as plain
         check because the other three signals all missed.
      1. The PV contains a SAN ending in '#' → mate forced; ply distance
         known directly.
      2. eval_after_cp is in the mate-sentinel range (|eval| >= 9000) →
         engine reports forced mate; we know it exists but not the side
         delivering it without checking sign.
      3. Both — most reliable.

    Evidence emitted:
      {
        "side_delivering_mate": "white" | "black",
        "ply_to_mate": int | None,         # known if PV has '#' or is_checkmate
        "via_played_move": bool,           # detected in pv_after_played OR move is mate
        "via_best_move": bool,             # detected in pv_after_best
        "engine_eval_indicates_mate": bool,
        "delivered_on_this_move": bool,    # is_checkmate after the played move
      }
    """
    # 0. The played move IS mate (board_after.is_checkmate() == True).
    if is_checkmate:
        return {
            "side_delivering_mate": "white" if own_color == chess.WHITE else "black",
            "ply_to_mate": 1,
            "via_played_move": True,
            "via_best_move": False,
            "engine_eval_indicates_mate": True,
            "delivered_on_this_move": True,
        }

    # PV-based mate detection
    played_mate_ply = _pv_resolves_to_mate(pv_after_played)
    best_mate_ply = _pv_resolves_to_mate(pv_after_best)

    # Eval-sentinel detection. Note eval_after_cp is from white's POV
    # by standard convention; user_color flips it for the user's POV.
    engine_eval_indicates_mate = (
        eval_after_cp is not None and abs(eval_after_cp) >= 9000
    )

    if played_mate_ply is None and best_mate_ply is None and not engine_eval_indicates_mate:
        return None

    # Determine who's delivering the mate. eval_after is from white's POV;
    # positive = white winning. So if eval is +9000, white delivers mate.
    side_delivering_mate = None
    if eval_after_cp is not None and abs(eval_after_cp) >= 1000:
        side_delivering_mate = "white" if eval_after_cp > 0 else "black"

    return {
        "side_delivering_mate": side_delivering_mate,
        "ply_to_mate": played_mate_ply or best_mate_ply,
        "via_played_move": played_mate_ply is not None,
        "via_best_move": best_mate_ply is not None,
        "engine_eval_indicates_mate": engine_eval_indicates_mate,
        "delivered_on_this_move": False,
    }


# ────────────────────────────────────────────────────────────────────
# Missed-tactic detection (commit #4b)
#
# Run the same tactic-shape detectors that we use on the played position
# but apply them to the position AFTER the engine's best move. If a
# tactic shape exists in pv_after_best that didn't exist in
# pv_after_played, the user missed a tactic.
#
# Visibility scoring (per user feedback 2026-05-11):
#   The shape must be HUMAN-VISIBLE — Stockfish ghost tactics that
#   require 6-ply only-move precision should NOT trigger missed-tactic
#   coaching. Score 1 = trivial (immediate, ≥minor piece), score 5 =
#   engine-only depth.
#
# Renderer thresholds the score via DEFAULT_VISIBLE_TACTIC_THRESHOLD in
# caption renderer config (default 2). Different surfaces (1200 coach,
# 1800 coach, puzzle mode) can set different thresholds.
# ────────────────────────────────────────────────────────────────────


def _missed_tactic_evidence(
    board_before: chess.Board,
    pv_after_best: List[str],
    best_move_san: Optional[str],
    played_tactics_exist: bool,
) -> List[Dict[str, Any]]:
    """If the user did NOT play the best move, run the shape detectors
    on the position after best_move and the next opponent reply.

    Returns a list of missed-tactic entries — each with:
      - tactic_kind: "multi_target_attack" | "aligned_pieces" | "discovered_attack"
      - tactic_data: the evidence dict from the corresponding detector
      - tactic_resolves_at_ply: 1 = after best move; 2 = after best
        move + forced response; etc.
      - minimum_material_gain_cp: SEE value of best capturing move
        in the detected shape
      - human_visibility_score: 1 = trivial, 5 = engine-only depth.
        Computed from tactic_resolves_at_ply + material gain +
        complexity of intervening moves.
    """
    if not pv_after_best or not best_move_san:
        return []
    if played_tactics_exist:
        # User already created a tactic with the played move; don't
        # bother surfacing alternative tactics from pv_after_best.
        return []

    # Walk pv_after_best up to a few plies, run shape detectors on each
    # board_after-best-line position, return any new shapes found.
    sim = board_before.copy()
    normalized_pv = _normalize_pv_starting_with(best_move_san, pv_after_best)

    plies_walked = 0
    own_color = sim.turn  # whoever was to move at board_before
    out: List[Dict[str, Any]] = []

    for ply_idx, san in enumerate(normalized_pv[:4]):
        try:
            move = sim.parse_san(san)
            sim.push(move)
            plies_walked += 1
        except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
            break

        # Only check tactics AFTER own-color moves resolve (i.e. after
        # plies 1 (best), 3 (best + opponent reply + own next), etc.).
        # Tactic in board AFTER own move means we're looking at what
        # WE could have created.
        is_own_move = (ply_idx % 2 == 0)
        if not is_own_move:
            continue

        # Synthesize a played_move stub for discovery detection (using
        # the actual played move at this ply). We need the move object,
        # not just SAN.
        # _discovered_attack_evidence needs the pre-move and post-move
        # boards. Since we already pushed `move`, we'd need to track the
        # pre-move state. Simplest: skip discovered_attack here; it's
        # heavily move-context dependent. Focus on aligned_pieces and
        # multi-target patterns which depend only on the post-move
        # position.

        # Run aligned-pieces and multi-target detectors on the current
        # sim board (which is the post-ply position from own POV).
        aligned = _aligned_pieces_evidence(sim, own_color)
        # Multi-target requires threats_created which requires a
        # before+after diff. We approximate: any aligned-pieces shape
        # with rear_value > 300 counts as a potential winning tactic.
        for shape in aligned:
            # Only flag shapes that win material — front_value_vs_rear
            # = "lower" (classic pin/winning skewer scenario) and rear
            # is high-value (rook or queen).
            if shape["rear_piece_value_cp"] < 500:
                continue
            # Resolves at the ply where the shape was detected.
            tactic_resolves_at_ply = plies_walked
            minimum_material_gain_cp = shape["rear_piece_value_cp"] - shape["front_piece_value_cp"]
            if minimum_material_gain_cp <= 0:
                # Not actually a winning gain at this geometry.
                continue
            # Visibility: 1 if resolves on ply 1, +1 per extra ply.
            # If gain is < 200cp (less than a minor piece), bump score
            # by 1 (smaller targets are harder for humans to value).
            visibility = tactic_resolves_at_ply
            if minimum_material_gain_cp < 200:
                visibility += 1
            out.append({
                "tactic_kind": "aligned_pieces",
                "tactic_data": shape,
                "tactic_resolves_at_ply": tactic_resolves_at_ply,
                "minimum_material_gain_cp": minimum_material_gain_cp,
                "human_visibility_score": visibility,
            })

    # Sort by visibility ascending (most visible first), then by gain desc
    out.sort(key=lambda x: (x["human_visibility_score"], -x["minimum_material_gain_cp"]))
    return out


# ────────────────────────────────────────────────────────────────────
# Primary-reason scoring layer (commit #4b)
#
# Pick ONE category of reason from the facts dict using a HARD priority
# order. Returns a structured dict identifying the category and the
# reference to the supporting evidence — NOT a coaching string. The
# renderer turns the category into prose.
#
# Priority (highest first):
#   1.  mate            — mate_threat_evidence is present
#   2.  tactic_played   — own tactic shape on the played move
#   3.  check_extra     — is_check AND threats_created non-empty
#   4.  forced_recapture — single-best forced response
#   5.  material        — gated: material delta accounts for ≥70% of
#                         eval swing AND is positive (own gain)
#   6.  king_safety     — is_castling
#   7.  defense         — defends a higher-value attacked piece
#   8.  threat          — threats_created non-empty (no tactic above)
#   9.  pawn_structure  — recapture toward centre (Phase 1 minimal)
#  10.  development     — opening + develops_minor + concrete next-step
#  11.  None            — no extractable reason; renderer stays silent
# ────────────────────────────────────────────────────────────────────


def _eval_swing_cp(facts: Dict[str, Any]) -> int:
    """Eval delta from side-to-move's POV. Positive = the move made the
    position better for the side that just moved."""
    eb = facts.get("eval_before_cp")
    ea = facts.get("eval_after_cp")
    if eb is None or ea is None:
        return 0
    side_white = facts.get("moving_piece_color") == "white"
    # Eval-after is white-POV; for black, we flip both then take diff.
    if side_white:
        return ea - eb
    return -(ea - eb)


def _material_explains_eval(facts: Dict[str, Any]) -> bool:
    """Material gain accounts for at least 70% of the eval swing.
    Prevents 'wins a pawn' from drowning out 'creates a mating attack'
    when the eval swing is much larger than the material gain."""
    delta_played = facts.get("material_delta_played_cp") or 0
    if delta_played <= 0:
        return False
    swing = _eval_swing_cp(facts)
    if swing <= 50:
        return False
    return abs(delta_played) >= 0.7 * abs(swing) - 50


def extract_primary_reason(facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a structured dict identifying THE primary-reason category
    for this move, plus a reference to the supporting evidence in the
    facts dict. Returns None when no extractable reason exists (renderer
    should render silently per R-FALLBACK).

    Output shape:
      {
        "category": "mate" | "tactic_played" | "check_extra" | ...,
        "ref_field": str,             # which facts key holds the evidence
        "priority_level": int,        # for debugging / regression
      }

    Does NOT produce coaching prose — LAW 1 (no smart strings).
    """
    # Priority 1: mate (essence overrides everything)
    if facts.get("mate_threat_evidence"):
        return {
            "category": "mate",
            "ref_field": "mate_threat_evidence",
            "priority_level": 1,
        }

    # ── Tactic-celebration safety gate ──────────────────────────────
    # If the engine calls this move a mistake/blunder, the geometric
    # tactic shape is incidental — celebrating "you forked X and Y"
    # on a 286-cp blunder is teaching the wrong thing. Fall through
    # to the blunder/mistake rules (added in a later commit) instead.
    # Bug from d7ce40cf corpus: #19 Re7, #17 a3, #9 Bg5.
    _move_cpl = facts.get("cp_loss") or 0
    _tactic_ok = _move_cpl < MAX_CP_LOSS_FOR_TACTIC_CELEBRATION

    # Priority 2: own tactic shape on the played move (gated)
    if _tactic_ok and facts.get("multi_target_attack_evidence"):
        return {
            "category": "tactic_played",
            "ref_field": "multi_target_attack_evidence",
            "priority_level": 2,
        }
    if _tactic_ok and facts.get("aligned_pieces_evidence"):
        # Only fire if rear piece has real value (≥ rook) — pawn pins
        # are too trivial to be the primary reason.
        for shape in facts["aligned_pieces_evidence"]:
            if shape.get("rear_piece_value_cp", 0) >= 500:
                return {
                    "category": "tactic_played",
                    "ref_field": "aligned_pieces_evidence",
                    "priority_level": 2,
                }
    if _tactic_ok and facts.get("discovered_attack_evidence"):
        for ev in facts["discovered_attack_evidence"]:
            if ev.get("target_value_cp", 0) >= 300:
                return {
                    "category": "tactic_played",
                    "ref_field": "discovered_attack_evidence",
                    "priority_level": 2,
                }

    # Priority 3: check + extra attack (concrete tactical pressure)
    if facts.get("is_check") and facts.get("threats_created"):
        return {
            "category": "check_extra",
            "ref_field": "threats_created",
            "priority_level": 3,
        }

    # Priority 4: plain check — is_check without an extra attack still
    # represents a forcing teaching moment ("king has to respond").
    # Lower than check_extra so a check + fork goes to category=tactic_played.
    if facts.get("is_check"):
        return {
            "category": "check_plain",
            "ref_field": "is_check",
            "priority_level": 4,
        }

    # Priority 5: forced recapture (factual, no praise).
    # Same cp_loss gate as tactic/threat — "only move, takes back the
    # piece" is celebratory framing that misleads on a losing recapture
    # (e.g. d7ce40cf #7 Nxd5 330 cp blunder where declining was better).
    if _tactic_ok and facts.get("is_forced_recapture"):
        return {
            "category": "forced_recapture",
            "ref_field": "captured_piece_type",
            "priority_level": 5,
        }

    # Priority 6: material — gated by eval-swing accounting
    if _material_explains_eval(facts):
        return {
            "category": "material",
            "ref_field": "material_delta_played_cp",
            "priority_level": 6,
        }

    # Priority 7: king safety
    if facts.get("is_castling"):
        return {
            "category": "king_safety",
            "ref_field": "is_castling",
            "priority_level": 7,
        }

    # Priority 7: defense — defends a higher-value attacked piece.
    # Phase 1 implementation: any piece in pieces_now_undefended which
    # is NOT now-hanging counts as "successfully defended elsewhere."
    # Stronger detection arrives when we add an explicit
    # `pieces_now_defended` field in a later phase.

    # Priority 8: threat creation (non-tactic threats; same gate as
    # tactics — threats are only worth celebrating on non-mistake moves).
    if _tactic_ok and facts.get("threats_created"):
        return {
            "category": "threat",
            "ref_field": "threats_created",
            "priority_level": 8,
        }

    # Priority 9: pawn structure (Phase 1 minimal — explicit fact)
    # Reserved for when concept facts arrive.

    # Priority 10: development — opening + develops minor + has next-step.
    # Gated on cp_loss like other celebratory categories — a 200 cp
    # mistake in the opening shouldn't be celebrated as development.
    if (
        _tactic_ok
        and facts.get("phase") == "opening"
        and facts.get("moving_piece_type") in ("knight", "bishop")
    ):
        # Phase 1: very permissive — any minor-piece move in opening
        # counts as a development reason. Concept refinements (named
        # next-step like "supports d4 break") arrive later.
        return {
            "category": "development",
            "ref_field": "moving_piece_type",
            "priority_level": 10,
        }

    # Priority 11: blunder — last-resort category that fills the silence
    # for any move whose engine evaluation calls it a mistake or worse.
    # All celebratory categories above are gated on cp_loss < the
    # MAX_CP_LOSS_FOR_TACTIC_CELEBRATION threshold, so anything that
    # reaches this point with cp_loss above that threshold is a real
    # blunder/mistake with no redeeming tactical or developmental story.
    # From d7ce40cf corpus this fills silences on:
    #   user side : #6 d3, #7 Nxd5, #9 Bg5, #17 a3, #19 Re7
    #   opp side  : #19 Rd8, #21 Rd8
    if _move_cpl >= MAX_CP_LOSS_FOR_TACTIC_CELEBRATION:
        return {
            "category": "blunder",
            "ref_field": "cp_loss",
            "priority_level": 11,
        }

    return None


def _queen_sortie_evidence(
    board_before: chess.Board,
    played_move: chess.Move,
    move_history_san: List[str],
    full_move_number: int,
) -> Optional[Dict[str, Any]]:
    """Evidence dict for early queen sorties — when a queen moves out
    in the opening before sufficient minor-piece development.

    Returns None when the move isn't a queen move, or when the position
    is past the opening phase (move_number > 10), or when adequate
    minor pieces are already developed.

    Per user feedback (2026-05-11): emit EVIDENCE, not a boolean
    judgment. Numbers the renderer can use to decide phrasing.
    """
    moving_piece = board_before.piece_at(played_move.from_square)
    if not moving_piece or moving_piece.piece_type != chess.QUEEN:
        return None
    if full_move_number > 10:
        return None

    queen_color = moving_piece.color
    # Count minor pieces (knight + bishop) of this color OFF their starting squares.
    # python-chess starting bitboards:
    if queen_color == chess.WHITE:
        starting_knights = {chess.B1, chess.G1}
        starting_bishops = {chess.C1, chess.F1}
    else:
        starting_knights = {chess.B8, chess.G8}
        starting_bishops = {chess.C8, chess.F8}

    developed_minor = 0
    for sq in board_before.pieces(chess.KNIGHT, queen_color):
        if sq not in starting_knights:
            developed_minor += 1
    for sq in board_before.pieces(chess.BISHOP, queen_color):
        if sq not in starting_bishops:
            developed_minor += 1

    # Count how many queen moves of this color have happened in history.
    queen_moves_so_far = 0
    for idx, san in enumerate(move_history_san):
        # White moves are even-indexed (0, 2, 4...), black are odd-indexed.
        is_white_move = (idx % 2 == 0)
        if is_white_move != (queen_color == chess.WHITE):
            continue
        if san.startswith("Q"):
            queen_moves_so_far += 1
    # The current move counts as the next queen move (about to be played).
    queen_move_index = queen_moves_so_far + 1

    return {
        "piece_color": "white" if queen_color == chess.WHITE else "black",
        "from_square": chess.square_name(played_move.from_square),
        "to_square": chess.square_name(played_move.to_square),
        "full_move_number": full_move_number,
        "minor_pieces_developed": developed_minor,
        "queen_move_index_in_opening": queen_move_index,
    }


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
    mover_is_user: Optional[bool] = None,
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

    # ── SEE-driven exchange truth (commit #2) ──────────────────────────
    # Raw attacker/defender counts above are kept for renderer reference
    # but DO NOT drive trigger logic. SEE handles pinned/x-ray/value-
    # imbalance correctly by simulating the actual cheapest-first
    # recapture sequence.
    see_played_capture_cp = _see_for_played_move(board_before, played_move)
    # For non-capture moves: would opponent win material capturing on
    # target_square next? SEE from their POV in board_after.
    target_square_exchange_cp = None
    if not is_capture:
        target_square_exchange_cp = _target_square_exchange_cp(board_after, played_move.to_square)

    # `is_exchange_losing` consolidates the two SEE signals:
    #   - if it's a capture: SEE for the played capture is negative
    #   - if not a capture: opponent's SEE on the target square is positive
    #     (meaning OUR piece is in danger of being won)
    if is_capture and see_played_capture_cp is not None:
        is_exchange_losing = see_played_capture_cp < -EXCHANGE_LOSS_THRESHOLD_CP
        exchange_loss_cp = abs(see_played_capture_cp) if see_played_capture_cp < 0 else 0
    elif target_square_exchange_cp is not None:
        is_exchange_losing = target_square_exchange_cp > EXCHANGE_LOSS_THRESHOLD_CP
        exchange_loss_cp = target_square_exchange_cp if target_square_exchange_cp > 0 else 0
    else:
        is_exchange_losing = False
        exchange_loss_cp = 0

    # ── Effective attackers/defenders (SEE-participating, pin-filtered) ─
    # Distinct from the RAW lists above. Effective = the pieces that
    # actually take part in the exchange sequence. Renderers should
    # prefer these for trigger logic; raw lists stay for reference.
    initiating_for_target = opp_color  # who'd start a capture sequence on the target?
    if is_capture:
        # The piece sitting on target was captured — exchange continues from
        # opponent's POV (they'd recapture).
        initiating_for_target = opp_color
    effective_attackers, effective_defenders = _exchange_participants(
        board_after, played_move.to_square, initiating_for_target
    )

    # ── Phase / full move number (needed by detectors below) ────────────
    full_move = full_move_number or board_before.fullmove_number
    phase = _detect_phase(board_before, full_move)

    # ── Threats created by the played move (structured evidence) ────────
    threats_created = _threats_created(board_before, board_after, played_move)

    # ── Pieces that lost a defender (structured evidence) ──────────────
    pieces_now_undefended = _pieces_now_undefended(board_before, board_after, played_move)

    # ── Tactic-shape evidence (commit #3 + renamed in #4a) ──────────────
    # All detectors emit structured evidence per LAW 3. Names changed
    # from {fork/pin/skewer/discovery}_shape to more primitive forms:
    #   multi_target_attack — "one attacker, multiple targets"
    #   aligned_pieces     — "three pieces on a line" (renderer picks
    #                        pin/skewer/x-ray via front_value_vs_rear)
    #   discovered_attack  — "uncovered attacker via played move"
    multi_target_attack_evidence = _multi_target_attack_evidence(threats_created)
    aligned_pieces_evidence = _aligned_pieces_evidence(board_after, own_color)
    discovered_attack_evidence = _discovered_attack_evidence(
        board_before, board_after, played_move
    )

    # ── Queen sortie evidence (NOT a boolean — evidence per LAW 3) ─────
    queen_sortie_evidence = _queen_sortie_evidence(
        board_before, played_move, move_history_san, full_move
    )

    # ── PV material walks (commit #4a) ──────────────────────────────────
    # SEE handles immediate exchange material. The PV walk handles multi-
    # ply tactical sequences (e.g. a 4-ply combo that wins a piece on
    # the third move). The two layers stack: SEE for one-shot exchanges,
    # PV-walk for sequences.
    #
    # Convention: both pv_after_played and pv_after_best may or may not
    # include the leading move (depends on engine record format).
    # _normalize_pv_starting_with_move handles both — the played move
    # is prepended only if missing.
    played_pv_normalized = _normalize_pv_starting_with(played_san, pv_after_played)
    best_pv_normalized = (
        _normalize_pv_starting_with(best_move_san, pv_after_best)
        if best_move_san else []
    )
    material_delta_played_cp = _pv_material_delta(
        board_before, played_pv_normalized, own_color
    )
    material_delta_best_cp = _pv_material_delta(
        board_before, best_pv_normalized, own_color
    ) if best_pv_normalized else 0

    # `free_capture` means PURELY "no recapture exists" — there is no
    # opponent piece (of the owner's color) attacking the target square
    # in board_before. This is geometric, not PV-derived: a 4-ply
    # exchange that nets positive material (e.g. bishop-for-knight
    # trade in commit's case A) is NOT a free capture even though
    # net material is positive. The renderer needs to distinguish
    # "took a piece nothing defends" from "won material via favourable
    # trade sequence."
    free_capture = False
    if is_capture and captured_piece is not None:
        owner_color = captured_piece.color
        # Recapturers = pieces of the OWNER's color (the one being
        # captured) that still attack the target after the capture
        # (excluding the moving piece itself; it's now on target_square).
        recapturers = board_after.attackers(owner_color, played_move.to_square)
        free_capture = len(recapturers) == 0

    # ── Mate threat evidence (commit #4a) ───────────────────────────────
    mate_threat_evidence = _mate_threat_evidence(
        eval_after_cp, pv_after_played, pv_after_best, own_color,
        is_checkmate=is_checkmate,
    )

    # ── Missed tactic evidence (commit #4b) ─────────────────────────────
    # Run shape detectors on pv_after_best to see if the user missed a
    # tactic. Visibility-scored — renderer thresholds via config.
    played_tactics_exist = bool(
        multi_target_attack_evidence
        or [s for s in aligned_pieces_evidence if s.get("rear_piece_value_cp", 0) >= 500]
        or discovered_attack_evidence
    )
    played_is_best_check = (
        best_move_san is not None
        and _normalize_san(played_san) == _normalize_san(best_move_san)
    )
    missed_tactic_evidence = (
        []
        if played_is_best_check
        else _missed_tactic_evidence(
            board_before, pv_after_best, best_move_san, played_tactics_exist
        )
    )

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
    user_is_winning = (user_eval_after is not None) and (user_eval_after >= EVAL_WINNING_THRESHOLD_CP)
    user_is_losing = (user_eval_after is not None) and (user_eval_after <= EVAL_LOSING_THRESHOLD_CP)

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

        # ATTACK / DEFENSE — RAW LISTS (pure geometry, no judgment)
        "attackers_on_target": attackers_on_target,
        "defenders_on_target": defenders_on_target,
        "attacker_count": len(attackers_on_target),
        "defender_count": len(defenders_on_target),

        # EFFECTIVE PARTICIPANTS (SEE-filtered, pin-aware)
        # These are the pieces that ACTUALLY take part in the exchange
        # sequence — renderer rules should prefer these over raw lists
        # for trigger logic. Raw lists remain available for reference.
        "effective_attackers_on_target": effective_attackers,
        "effective_defenders_on_target": effective_defenders,

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

        # SESSION CONTEXT (not chess truth — caller-supplied). Optional;
        # rules with perspective-specific voicing read this to flip "you"
        # vs "they" framing. Bend #5 — without it the renderer can't
        # tell a user's castling from an opponent's castling.
        "mover_is_user": mover_is_user,

        # EXCHANGE TRUTH (SEE — commit #2)
        "see_played_capture_cp": see_played_capture_cp,
        "target_square_exchange_cp": target_square_exchange_cp,
        "is_exchange_losing": is_exchange_losing,
        "exchange_loss_cp": exchange_loss_cp,
        "threats_created": threats_created,
        "pieces_now_undefended": pieces_now_undefended,

        # TACTIC-SHAPE EVIDENCE — STRUCTURED, NO LABELS.
        # Names use the GEOMETRIC primitive, not renderer taxonomy.
        # Renderer rules read these and decide whether to say "fork" /
        # "pin" / "skewer" / "x-ray" / "double attack" / "pressure" —
        # the extractor never commits to a coaching word.
        "multi_target_attack_evidence": multi_target_attack_evidence,
        "aligned_pieces_evidence": aligned_pieces_evidence,
        "discovered_attack_evidence": discovered_attack_evidence,

        # QUEEN SORTIE EVIDENCE (commit #3) — DICT or None, not bool.
        # Renderer reads numbers (move_number, minor_pieces_developed)
        # and decides whether/how to mention.
        "queen_sortie_evidence": queen_sortie_evidence,

        # PV MATERIAL WALKS (commit #4a) — multi-ply tactical material
        # truth that SEE alone can't see. Renderer rules use these to
        # detect long tactical sequences and gate the material primary
        # reason (only fire when the eval swing is explained by
        # material delta — prevents "wins a pawn" from drowning out
        # "creates a mating attack").
        "material_delta_played_cp": material_delta_played_cp,
        "material_delta_best_cp": material_delta_best_cp,
        "free_capture": free_capture,

        # MATE THREAT EVIDENCE (commit #4a) — highest priority reason.
        # When present, any primary_reason picker MUST prefer this
        # over tactic/material reasons. Mate is essence; everything
        # else is consequence.
        "mate_threat_evidence": mate_threat_evidence,

        # MISSED TACTIC EVIDENCE (commit #4b) — list of structured
        # evidence dicts with human_visibility_score. Renderer applies
        # its own visibility threshold via caption-renderer config.
        "missed_tactic_evidence": missed_tactic_evidence,

        # PRIMARY REASON (commit #4b) — see extract_primary_reason for
        # priority order. Computed AFTER all other facts are built so
        # the scorer has the full dict to read from.
        "primary_reason": None,  # populated below after the dict is built
    }

    # Compute primary_reason using the now-complete facts dict.
    facts["primary_reason"] = extract_primary_reason(facts)

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
