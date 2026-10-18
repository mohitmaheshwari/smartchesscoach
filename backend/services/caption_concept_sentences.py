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
            "A piece left at home does not help you.",
        ),
        WRONG: (
            "You still had a piece at home. Bringing it out was better.",
            "A piece left at home does not help you.",
        ),
    },
    "opening_center": {
        APPLIED: (
            "Your pawn took a square in the middle.",
            "Both sides want the middle first.",
        ),
        WRONG: (
            "A pawn into the middle was stronger here.",
            "Both sides want the middle first.",
        ),
    },
    "opening_castling": {
        APPLIED: (
            "You castled. Your king is safer there.",
            "Get your king safe early.",
        ),
        WRONG: (
            "Castling was the better move here.",
            "Get your king safe early.",
        ),
    },
    "concept_rook_open_file": {
        APPLIED: (
            "Your rook moved to a line your own pawns do not block.",
            "Rooks need clear lines.",
        ),
        WRONG: (
            "Your rook should have gone to the clear line.",
            "Rooks need clear lines.",
        ),
    },
    "endgame_king_centralization": {
        APPLIED: (
            "Your king stepped towards the middle.",
            "With few pieces left, your king is a strong piece.",
        ),
        WRONG: (
            "Moving your king towards the middle was better here.",
            "With few pieces left, your king is a strong piece.",
        ),
    },
    "concept_central_pawn_break": {
        APPLIED: (
            "You pushed a pawn at theirs in the middle.",
            "A pawn push opens up a stuck middle.",
        ),
        WRONG: (
            "A pawn push in the middle was better here.",
            "A pawn push opens up a stuck middle.",
        ),
    },
    "opening_development_with_tempo": {
        APPLIED: (
            "You brought a piece out and attacked something at the same time.",
            "A new piece that makes a threat wins you a free move.",
        ),
        WRONG: (
            "You could have brought a piece out and made a threat.",
            "A new piece that makes a threat wins you a free move.",
        ),
    },
    # --- drafted 2026-10-18, awaiting evidence and Mohit's read ---------
    "concept_rook_seventh": {
        APPLIED: (
            "Your rook reached the row where their pawns start.",
            "Pawns on that row cannot run away.",
        ),
        WRONG: (
            "Your rook should have gone to that row.",
            "Pawns on that row cannot run away.",
        ),
    },
    "endgame_create_passed_pawn": {
        APPLIED: (
            "You made a pawn with no pawn left to stop it.",
            "A pawn with a clear road wins endings.",
        ),
        WRONG: (
            "Making a pawn with a clear road was better here.",
            "A pawn with a clear road wins endings.",
        ),
    },
    "concept_knight_outpost": {
        APPLIED: (
            "Your knight landed where no pawn can chase it away.",
            "A knight nobody can push back is worth more.",
        ),
        WRONG: (
            "Your knight should have gone where no pawn can chase it.",
            "A knight nobody can push back is worth more.",
        ),
    },
    "endgame_opposition": {
        APPLIED: (
            "Your king stepped up to face theirs, one square apart.",
            "When kings face each other, whoever moves first gives way.",
        ),
        WRONG: (
            "Moving up to face their king was better here.",
            "When kings face each other, whoever moves first gives way.",
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


def _mover(board: chess.Board, move: chess.Move, colour: chess.Color, kinds=None):
    piece = board.piece_at(move.from_square)
    if piece is None or piece.color != colour:
        return None
    if kinds and piece.piece_type not in kinds:
        return None
    return piece


def _home_squares(colour: chess.Color):
    return (
        {chess.B1, chess.G1, chess.C1, chess.F1}
        if colour == chess.WHITE
        else {chess.B8, chess.G8, chess.C8, chess.F8}
    )


def _centre_distance(square: int) -> float:
    return max(abs(chess.square_file(square) - 3.5), abs(chess.square_rank(square) - 3.5))


def p_development(board, move, colour) -> bool:
    """A knight or bishop of yours left its own home square."""
    if not _mover(board, move, colour, (chess.KNIGHT, chess.BISHOP)):
        return False
    home = _home_squares(colour)
    return move.from_square in home and move.to_square not in home


def p_centre(board, move, colour) -> bool:
    """A pawn of yours landed on one of the four centre squares."""
    if not _mover(board, move, colour, (chess.PAWN,)):
        return False
    return move.to_square in {chess.D4, chess.E4, chess.D5, chess.E5}


def p_castle(board, move, colour) -> bool:
    """You castled."""
    return board.turn == colour and board.is_castling(move)


def p_rook_open_file(board, move, colour) -> bool:
    """A rook of yours reached a file carrying none of YOUR pawns.

    Not "no pawns at all": of 121 fires, 64% were fully open files and 36%
    half-open, and not one had a friendly pawn on the file. Writing the
    stricter sentence is what made this detector look 57% accurate.
    """
    if not _mover(board, move, colour, (chess.ROOK,)):
        return False
    file_index = chess.square_file(move.to_square)
    after = board.copy()
    after.push(move)
    for rank in range(8):
        piece = after.piece_at(chess.square(file_index, rank))
        if piece is not None and piece.piece_type == chess.PAWN and piece.color == colour:
            return False
    return True


def p_king_centralization(board, move, colour) -> bool:
    """With the board emptied, your king stepped towards the middle.

    The piece limit is the whole point: 42 of 122 fires happen with 13 to 21
    pieces on, where this is not endgame technique but a way to get mated.
    """
    if not _mover(board, move, colour, (chess.KING,)):
        return False
    if board.is_castling(move):
        return False
    if len(board.piece_map()) > ENDGAME_PIECE_LIMIT:
        return False
    return _centre_distance(move.to_square) < _centre_distance(move.from_square)


def p_central_pawn_break(board, move, colour) -> bool:
    """A pawn of yours moved in the middle files where pawns actually meet."""
    if not _mover(board, move, colour, (chess.PAWN,)):
        return False
    if chess.square_file(move.to_square) not in (2, 3, 4, 5):
        return False
    return _enemy_pawn_in_contact(board, move, colour)


# The concept, as a decidable statement about the board. One source, used two
# ways: as the condition a compliment must satisfy before it is said, and as
# the test a correction's alternative move must pass. Precision was 100% on
# every promoted detector, so using it as a condition rejects nothing that was
# measured -- it just makes the sentence and the evidence the same thing.
def p_rook_seventh(board, move, colour) -> bool:
    """A rook of yours reached the rank their pawns start on."""
    if not _mover(board, move, colour, (chess.ROOK,)):
        return False
    target = 6 if colour == chess.WHITE else 1
    return chess.square_rank(move.to_square) == target


def _is_passed(board: chess.Board, square: int, colour: chess.Color) -> bool:
    """No enemy pawn on this file or either neighbour, ahead of this square."""
    piece = board.piece_at(square)
    if piece is None or piece.piece_type != chess.PAWN or piece.color != colour:
        return False
    f = chess.square_file(square)
    r = chess.square_rank(square)
    ahead = range(r + 1, 8) if colour == chess.WHITE else range(0, r)
    for file_index in (f - 1, f, f + 1):
        if not 0 <= file_index <= 7:
            continue
        for rank_index in ahead:
            other = board.piece_at(chess.square(file_index, rank_index))
            if other is not None and other.piece_type == chess.PAWN and other.color != colour:
                return False
    return True


def p_create_passed_pawn(board, move, colour) -> bool:
    """A pawn of yours ended the move with no enemy pawn left in its path,
    and did not already have one before it."""
    if not _mover(board, move, colour, (chess.PAWN,)):
        return False
    if _is_passed(board, move.from_square, colour):
        return False
    after = board.copy()
    after.push(move)
    return _is_passed(after, move.to_square, colour)


def p_knight_outpost(board, move, colour) -> bool:
    """A knight of yours landed where no enemy pawn can ever attack it, and
    one of your own pawns defends it."""
    if not _mover(board, move, colour, (chess.KNIGHT,)):
        return False
    after = board.copy()
    after.push(move)
    square = move.to_square
    f = chess.square_file(square)
    r = chess.square_rank(square)
    # Could an enemy pawn ever come down an adjacent file to hit it?
    ahead = range(r + 1, 8) if colour == chess.WHITE else range(0, r)
    for file_index in (f - 1, f + 1):
        if not 0 <= file_index <= 7:
            continue
        for rank_index in ahead:
            other = after.piece_at(chess.square(file_index, rank_index))
            if other is not None and other.piece_type == chess.PAWN and other.color != colour:
                return False
    # And is it held by one of ours?
    for square_from in after.attackers(colour, square):
        piece = after.piece_at(square_from)
        if piece is not None and piece.piece_type == chess.PAWN:
            return True
    return False


def p_opposition(board, move, colour) -> bool:
    """Your king stepped up to face theirs with exactly one square between,
    on the same file, rank or diagonal."""
    if not _mover(board, move, colour, (chess.KING,)):
        return False
    theirs = board.king(not colour)
    if theirs is None:
        return False
    after = board.copy()
    after.push(move)
    mine = after.king(colour)
    if mine is None:
        return False
    df = abs(chess.square_file(mine) - chess.square_file(theirs))
    dr = abs(chess.square_rank(mine) - chess.square_rank(theirs))
    aligned = (df == 0 and dr == 2) or (dr == 0 and df == 2) or (df == 2 and dr == 2)
    return aligned and after.turn != colour


CONCEPT_PREDICATES: Dict[str, Callable[[chess.Board, chess.Move, chess.Color], bool]] = {
    "coached_development": p_development,
    "opening_center": p_centre,
    "opening_castling": p_castle,
    "concept_rook_open_file": p_rook_open_file,
    "endgame_king_centralization": p_king_centralization,
    "concept_central_pawn_break": p_central_pawn_break,
    # Drafted, not yet promoted: these speak only once _AUTHORIZATIONS says so.
    "concept_rook_seventh": p_rook_seventh,
    "endgame_create_passed_pawn": p_create_passed_pawn,
    "concept_knight_outpost": p_knight_outpost,
    "endgame_opposition": p_opposition,
}

GATES = CONCEPT_PREDICATES


# When the caption above has already made the point, the sentence is not a
# second idea -- it is the same idea twice. Measured over 12 rendered reviews:
# 6 of 35 sentences landed under a caption saying the same thing, and every
# one was `opening_center` under the opening-intro rule on move one, where the
# caption already reads "White takes a share of the center".
#
# Keyed on the rule that wrote the caption. Only entries with a measured clash
# are listed; guessing at the rest would silence sentences for no reason.
# Measured over 25,757 stored cards: the distilled layer has its own authored
# caption for several of these ideas, and each fires on 0.4-1.0% of cards --
# good_develop 169, good_rook_activity 129, good_castle 121, good_centralize
# 118, good_rook_open_file 109, good_luft 30. Where one of those wrote the
# caption, the sentence below it is the same idea in a second voice.
SUPPRESS_WHEN_CAPTION_RULE_CONTAINS: Dict[str, Tuple[str, ...]] = {
    "opening_center": ("center", "centre", "centrali"),
    "concept_rook_open_file": ("rook_open_file", "rook_activity"),
    "endgame_king_centralization": ("king_activity", "centrali"),
    "concept_central_pawn_break": ("pawn_break",),
    "coached_development": ("develop",),
    "opening_castling": ("castl",),
}


def already_said(caption_rule: Optional[str], skill_id: str) -> bool:
    """True when the caption above the sentence has already made this point."""
    if not caption_rule:
        return False
    needles = SUPPRESS_WHEN_CAPTION_RULE_CONTAINS.get(skill_id)
    if not needles:
        return False
    rule = str(caption_rule).lower()
    return any(needle in rule for needle in needles)


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

    # The condition applies to a COMPLIMENT, where the predicate describes the
    # move he played. On a correction the predicate describes the move he did
    # NOT play, so gating the played move here would silence every correction
    # -- the alternative is what gets checked, by the verifier below.
    if outcome == APPLIED:
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
