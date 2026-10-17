"""What a concept detector is allowed to say, and when.

Forty-eight detectors computed an opinion about a move and threw it away.
They were silent for three separate reasons -- no permission, no words, and
nowhere to appear -- and this module is the second of those: the words.

Mohit, 2026-10-17: "about reaching nobody, i can't have that done", and then
"everything a coach is never shy to give negative too". So each detector has
two sentences here, the compliment and the correction, and both end on a
principle that outlives the game they were said in.

THREE RULES THIS FILE ENFORCES

1. Permission comes from `detector_quality`, never from a list in here.
   `_AUTHORIZATIONS` is the single place a detector is promoted, so a
   detector that has not earned caption grade says nothing no matter what is
   written below.

2. Some detectors need a CONDITION as well as permission.
   `endgame_king_centralization` steps towards the middle on 100% of its
   fires -- and 42 of 122 of them do it with 13 to 21 pieces still on the
   board, where walking the king to the centre is not endgame technique but a
   way to get mated. No wording fixes that, so it is gated on the piece
   count. `concept_central_pawn_break` is gated on enemy pawns actually being
   in contact, because "break" overclaims for the other 63%.

3. A correction must be VERIFIED, not assumed.
   Measured over 400 games, "a move of this kind was better" held only 84-88%
   of the time against a fresh depth-18 look -- the detector reads the best
   move stored at analysis time, and deeper that is often a different move.
   One case in eight would have told a player to develop a piece when the
   strongest move was a queen move developing nothing. So a correction is
   shown only when the caller supplies a verifier AND it confirms the claim.
   No verifier means no correction. It fails closed, on purpose.

Evidence: docs/detectors_speak_scope.md.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import chess

from services.detector_quality import (
    QualitySurface,
    concept_quality_id,
    is_authorized,
)

APPLIED = "applied"
WRONG = "wrong"

# At or below this many pieces, walking the king towards the middle is
# endgame technique. Above it, it is how a player gets mated.
ENDGAME_PIECE_LIMIT = 12


Sentence = Tuple[str, str]  # (what happened, the principle it teaches)


CONCEPT_SENTENCES: Dict[str, Dict[str, Sentence]] = {
    "coached_development": {
        APPLIED: (
            "You brought a new piece into the game.",
            "A piece left at home is a piece not helping you.",
        ),
        WRONG: (
            "A piece was still sitting at home, and bringing it out was "
            "better here.",
            "A piece left at home is a piece not helping you.",
        ),
    },
    "opening_center": {
        APPLIED: (
            "Your pawn took a square in the middle.",
            "The middle is the ground both sides want first.",
        ),
        WRONG: (
            "A pawn into the middle was stronger here.",
            "The middle is the ground both sides want first.",
        ),
    },
    "opening_castling": {
        APPLIED: (
            "You castled, so your king is tucked away.",
            "Get the king safe before the position opens up.",
        ),
        WRONG: (
            "Castling was the better move here.",
            "Get the king safe before the position opens up.",
        ),
    },
    "concept_rook_open_file": {
        APPLIED: (
            "Your rook moved to a file with none of your pawns in the way.",
            "Rooks want lines with nothing blocking them.",
        ),
        WRONG: (
            "Your rook belonged on the clear file here.",
            "Rooks want lines with nothing blocking them.",
        ),
    },
    "endgame_king_centralization": {
        APPLIED: (
            "Your king stepped towards the middle.",
            "When few pieces are left, the king turns into a fighter.",
        ),
        WRONG: (
            "Walking your king towards the middle was better here.",
            "When few pieces are left, the king turns into a fighter.",
        ),
    },
    "concept_central_pawn_break": {
        APPLIED: (
            "You pushed a pawn to challenge theirs in the middle.",
            "When the middle is stuck, a pawn push is how you open it.",
        ),
        WRONG: (
            "Striking in the middle with a pawn was better here.",
            "When the middle is stuck, a pawn push is how you open it.",
        ),
    },
    "opening_development_with_tempo": {
        APPLIED: (
            "You brought a piece out and attacked something at the same time.",
            "A new piece that arrives with a threat gains you a free move.",
        ),
        WRONG: (
            "You could have brought a piece out and made a threat with it.",
            "A new piece that arrives with a threat gains you a free move.",
        ),
    },
}


# Most specific first. Seven detectors over forty moves collide on about one
# firing move in nine, and the pairs that collide are near-synonyms -- "came
# out and hit something" contains "came out", and the reverse is not true --
# so two sentences would read as repetition rather than as two ideas.
PRIORITY: Tuple[str, ...] = (
    "opening_development_with_tempo",
    "concept_central_pawn_break",
    "concept_rook_open_file",
    "endgame_king_centralization",
    "opening_castling",
    "coached_development",
    "opening_center",
)


def _enemy_pawn_in_contact(
    board: chess.Board, move: chess.Move, colour: chess.Color
) -> bool:
    """Are enemy pawns actually meeting this pawn where it landed?"""
    them = not colour
    after = board.copy()
    after.push(move)
    for square in after.attackers(them, move.to_square):
        piece = after.piece_at(square)
        if piece is not None and piece.piece_type == chess.PAWN:
            return True
    for square in after.attacks(move.to_square):
        piece = after.piece_at(square)
        if piece is not None and piece.color == them and piece.piece_type == chess.PAWN:
            return True
    return False


def _gate_king_centralization(
    board: chess.Board, move: chess.Move, colour: chess.Color
) -> bool:
    return len(board.piece_map()) <= ENDGAME_PIECE_LIMIT


def _gate_central_pawn_break(
    board: chess.Board, move: chess.Move, colour: chess.Color
) -> bool:
    return _enemy_pawn_in_contact(board, move, colour)


# A detector here must satisfy its gate as well as hold caption grade.
GATES: Dict[str, Callable[[chess.Board, chess.Move, chess.Color], bool]] = {
    "endgame_king_centralization": _gate_king_centralization,
    "concept_central_pawn_break": _gate_central_pawn_break,
}


def may_speak(skill_id: str) -> bool:
    """Has this detector earned caption grade? Asked of detector_quality."""
    return is_authorized(concept_quality_id(skill_id), QualitySurface.CAPTION)


def concept_sentence_for_move(
    *,
    skill_id: str,
    outcome: str,
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    verify_correction: Optional[Callable[[chess.Board, chess.Move, chess.Color], bool]] = None,
) -> Optional[Dict[str, Any]]:
    """The one sentence this detector may say about this move, or None.

    `verify_correction` is required for a correction and is handed the
    position so it can check, at the depth the claim is made at, that a move
    of this kind really was better. Without it corrections stay silent.
    """
    if outcome not in (APPLIED, WRONG):
        return None
    bank = CONCEPT_SENTENCES.get(skill_id)
    if not bank or outcome not in bank:
        return None
    if not may_speak(skill_id):
        return None

    gate = GATES.get(skill_id)
    if gate is not None:
        try:
            if not gate(board_before, move, user_color):
                return None
        except Exception:
            return None

    if outcome == WRONG:
        if verify_correction is None:
            return None
        try:
            if not verify_correction(board_before, move, user_color):
                return None
        except Exception:
            return None

    said, principle = bank[outcome]
    return {
        "skill_id": skill_id,
        "outcome": outcome,
        "sentence": said,
        "principle": principle,
        "text": f"{said} {principle}",
    }


def pick_concept_sentence(
    *,
    outcomes: List[Tuple[str, str]],
    board_before: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
    verify_correction: Optional[Callable[[chess.Board, chess.Move, chess.Color], bool]] = None,
) -> Optional[Dict[str, Any]]:
    """One sentence for this move, from everything that fired on it.

    A correction outranks a compliment: being told what to fix is worth more
    than being told what went right, and a move that earned both is a move
    where the correction is the thing to say.
    """
    by_id = {skill_id: outcome for skill_id, outcome in outcomes}
    for wanted in (WRONG, APPLIED):
        for skill_id in PRIORITY:
            if by_id.get(skill_id) != wanted:
                continue
            found = concept_sentence_for_move(
                skill_id=skill_id,
                outcome=wanted,
                board_before=board_before,
                move=move,
                user_color=user_color,
                verify_correction=verify_correction,
            )
            if found is not None:
                return found
    return None
