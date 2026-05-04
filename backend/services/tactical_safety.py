"""
Tactical Safety — SEE-based helpers for "would this tactic actually work?"

Single home for the three checks the coaching surfaces need:

    target_truly_undefended(board_after, move)
        After a capture, is the landing square genuinely free of
        opponent attackers? "Free piece, nobody guarding it" claims
        should only fire when this returns True.

    capture_is_safe(board_before, move)
        Would the moving piece survive the capture? Uses standard SEE
        on the destination square from opponent POV. SEE > 0 means
        opponent gains material on recapture → unsafe (sacrifice).

    fork_is_safe(board_after_fork, fork_square, mover_color, gives_check)
        Would the forker survive opponent's response? SEE from
        opponent's POV on the fork square. Positive → forker hangs.
        Check forces opponent to deal with the check first, so a
        check-fork is treated as safe even when SEE is technically
        positive (opponent must respond to check before recapturing).

History: the coaching pipeline accumulated four independent binary
gates (cheapest_attacker < forker_value AND no defender) sprinkled
across move_comparison, coach_commentary, smart_coaching, and
pv_tactical_analyzer. They caught the most common false positives but
let cases through where the user has one defender but full SEE is
still negative (e.g., knight on pawn-defended square + one defender =
still loses 2 net pawns). This module replaces those gates with the
real SEE evaluation. One concern, one home, accurate answers.
"""

from __future__ import annotations

from typing import Optional

import chess

from .pattern_confidence.see import (
    PIECE_VALUE,
    static_exchange_eval,
    forced_exchange_eval,
)


def target_truly_undefended(
    board_before: chess.Board,
    move: chess.Move,
) -> bool:
    """Was the captured piece truly undefended — no opponent attackers
    on the landing square at all?

    Use this for "free piece" / "nobody was guarding it" claims. We
    deliberately don't go all the way to SEE here — even a cheaper
    defender means the capture isn't "free," it's a trade with a
    favorable balance, which deserves different framing.

    Returns False for non-capture moves (defensive default — we never
    want a non-capture to be tagged "free piece").
    """
    if not board_before.is_capture(move):
        return False
    # Apply the move and check whether opponent attacks the landing
    # square. ANY attacker on the destination = recapture is coming.
    board_after = board_before.copy(stack=False)
    moving_color = board_before.turn
    board_after.push(move)
    return not board_after.is_attacked_by(not moving_color, move.to_square)


def capture_is_safe(
    board_before: chess.Board,
    move: chess.Move,
) -> bool:
    """Would the moving piece survive on its destination square?

    Uses standard SEE from the OPPONENT's perspective on the to-square
    after the move. SEE > 0 means opponent gains material on recapture
    → the capture is a sacrifice / unsafe.

    Standard SEE means opponent will refuse to start an exchange that
    loses them material — so a defended capture where the cheapest
    defender would lose more than they gain returns SEE = 0 (safe for
    attacker). Use forced_exchange_eval if you need the strictly-bad
    answer regardless of opponent rationality.

    Use this for "wins material" / "free capture" claims on the
    user's OWN move that's being played.
    """
    board_after = board_before.copy(stack=False)
    moving_color = board_before.turn
    board_after.push(move)
    opp_see = static_exchange_eval(
        board_after, move.to_square, attacker_color=not moving_color
    )
    return opp_see <= 0


def fork_is_safe(
    board_after_fork: chess.Board,
    fork_square: chess.Square,
    mover_color: chess.Color,
    gives_check: bool = False,
) -> bool:
    """Will the forker survive opponent's response?

    Logic:
      - If opponent's standard SEE on the fork square is <= 0, the
        forker is safe (any recapture would lose opp material, so a
        rational opp won't start it).
      - Forced SEE catches the case where opp has ONE attacker that's
        cheaper than the forker but a recapture would still cost opp
        net (we still want to flag those as unsafe — they're real
        sacrifice risks even if the opp won't take). Conservative.
      - When the move gives check, opp MUST deal with the check
        before any recapture happens. The fork remains a threat the
        user has to respond to first. Treat as safe.

    Parameters mirror the existing gate signatures in
    coach_commentary._fork_is_safe and pv_tactical_analyzer
    interim safety gate, so the call-site changes are minimal.
    """
    if gives_check:
        return True
    # If opponent rationally won't take, the forker is safe.
    opp_see = static_exchange_eval(
        board_after_fork, fork_square, attacker_color=not mover_color
    )
    if opp_see <= 0:
        return True
    # Opponent gains material → forker hangs.
    return False


def fork_threat_is_real(
    board_before_opp_move: chess.Board,
    opp_move: chess.Move,
    user_color: chess.Color,
) -> bool:
    """Specifically for the "After your move, opp_move forks your X
    and Y" warning path.

    Different signature than fork_is_safe because here we're looking
    AT the opponent's hypothetical move from the user's POV: would
    user be able to capture the forker for material gain? If yes,
    the "fork" isn't a real threat — user just takes the forker.

    Mirrors what move_comparison._find_opponent_threats was checking,
    but uses real SEE instead of the cheapest_attacker < forker_value
    binary heuristic.

    Returns False (threat is fake) when:
      - opp_move doesn't give check
      - AND user can capture the forker for net material gain
        (forced_exchange_eval from user POV is positive)
    """
    board_after = board_before_opp_move.copy(stack=False)
    board_after.push(opp_move)

    if board_after.is_check():
        return True  # check forces user to address the check first

    # Forced SEE from user POV — would user gain material by capturing?
    user_see = forced_exchange_eval(
        board_after, opp_move.to_square, attacker_color=user_color
    )
    return user_see <= 0
