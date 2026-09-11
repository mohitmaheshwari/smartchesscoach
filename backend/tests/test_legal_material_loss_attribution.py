"""A loose-piece card must not blame a move for a pre-existing weakness.

build_legal_material_loss_cause only ever looked at what was hanging AFTER the
played move. It never asked whether the same piece was already hanging before
it, so any move at all -- including a king step on the far side of the board --
could be blamed for a piece that was doomed regardless.

Flagged live 2026-09-09. The card read:

    "Qa4 left your rook on h1 available. Their queen on g2 could win it with
     Qxh1. Qxf7 was the safer move."

Engine truth for that position (depth 22):
  * the rook on h1 was ALREADY hanging before Qa4 (nothing defended it)
  * it is STILL hanging after Qxf7, the engine's own best move
  * Qa4 is engine #2 at -864cp, only 19cp behind Qxf7 at -845cp
  * Qxh1 is not even Black's best reply; after it White plays Qxe8+ and the
    evaluation goes from -864cp (100% loss) to -43cp (90% draw), so the
    "punishment" the card warned about would have thrown away Black's win

The gate is clause 2 of the attribution contract already written down in
services/concept_attribution.py -- "it was avoidable: at least one legal
alternative did not flip it" -- which had never been applied to this path.
If no legal move keeps the piece, losing it is not this move's fault.

Corpus measurement (400 games, 7,491 user moves): of 583 cards, 119 (20%) are
unattributable; 464 are genuine and still fire. An earlier one-move proxy
("does the engine's #1 move also lose it?") caught 99 of the 119 -- searching
every legal move catches the rest, including one card that announced a lost
rook when the real punishment was Qxd1#, i.e. mate reported as material.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.caption_facts import build_legal_material_loss_cause

FLOOR = 150

# The flagged position: White queen on b3, rook stranded on h1, black queen
# already on g2. Both Qa4 (played) and Qxf7 (engine best) leave h1 hanging.
FLAGGED_FEN = "4r2k/5pp1/p4b1p/8/7P/1QP5/1P3Pq1/2KN3R w - - 0 33"


def test_does_not_blame_a_move_for_a_piece_the_best_move_also_loses():
    cause = build_legal_material_loss_cause(
        fen_before=FLAGGED_FEN,
        played_san="Qa4",
        best_move_san="Qxf7",
        minimum_gain_cp=FLOOR,
    )
    assert cause is None, (
        "Qa4 was blamed for the h1 rook, but the rook was already hanging "
        "before the move and is still hanging after Qxf7 -- so neither the "
        "blame nor the 'safer move' recommendation is true. "
        f"Got: {cause}"
    )


def test_a_king_move_is_never_blamed_for_a_doomed_piece_elsewhere():
    # Real corpus shape (game_dbb7db5a44d1): a 10cp king step was blamed for a
    # bishop on the other side of the board that a knight wins either way.
    # Same structural defect, so it is pinned with the flagged case.
    cause = build_legal_material_loss_cause(
        fen_before=FLAGGED_FEN,
        played_san="Kd2",
        best_move_san="Qxf7",
        minimum_gain_cp=FLOOR,
    )
    assert cause is None


def test_still_fires_when_the_best_move_moves_the_piece_to_safety():
    # Positive control from the real corpus -- the gate must not silence
    # attributable cards. After Qxc2 the rook on g3 hangs to Bxg3; Rh3 steps
    # it out of reach, so blaming the move and recommending the rescue are
    # both true here.
    rescued = build_legal_material_loss_cause(
        fen_before="3r1r2/2p3pk/3b3p/3P1q2/4p2P/P2P2R1/1Pn1QPP1/2B2K2 w - - 0 25",
        played_san="Qxc2",
        best_move_san="Rh3",
        minimum_gain_cp=FLOOR,
    )
    assert rescued is not None, "attributable card must still be produced"
    assert rescued.affected.square == "g3"
    assert rescued.punishment_san == "Bxg3"
    assert rescued.best_move_purpose == "moves_affected_piece"


def test_a_genuine_card_carries_a_verified_saving_move():
    # The remedy clause must name a move proven to keep the piece rather than
    # asserting an unchecked "X was the safer move". Every card that survives
    # the gate has one by construction.
    cause = build_legal_material_loss_cause(
        fen_before="3r1r2/2p3pk/3b3p/3P1q2/4p2P/P2P2R1/1Pn1QPP1/2B2K2 w - - 0 25",
        played_san="Qxc2",
        best_move_san="Rh3",
        minimum_gain_cp=FLOOR,
    )
    assert cause is not None
    assert cause.avoidable_with_san, (
        "a card that passed clause 2 must carry the move that keeps the piece"
    )


def test_still_fires_when_the_best_move_adds_a_defender():
    # Second positive control, different remedy shape: after O-O-O the bishop
    # on d4 hangs to Qxd4, and Ne2 defends it.
    defended = build_legal_material_loss_cause(
        fen_before="2r1k2N/p2qb1p1/1p3n1p/1P6/3B4/P1NP1Q2/2P2P1P/R3K3 w Q - 3 19",
        played_san="O-O-O",
        best_move_san="Ne2",
        minimum_gain_cp=FLOOR,
    )
    assert defended is not None, "attributable card must still be produced"
    assert defended.affected.square == "d4"
    assert defended.best_move_purpose == "adds_defender"


# --- mate reported as material -----------------------------------------------
# Measured over 500 games (641 loose-piece cards rendered): 5 cards, 0.8%, had
# a CHECKMATE as the punishment they were warning about. Rare, but the card is
# wrong in the worst possible way -- it discusses a rook while the player is
# being mated. Live examples: Ne2 answered by Qxe2# (cp_loss 8742), Rg7
# answered by Qxg7# (cp_loss 8807), Rxe5 answered by Nxe5#.
#
# White to move. The rook on d1 is defended by the knight on e3. Nc4 abandons
# that defence and Black answers Qxd1#: the king on g1 is boxed in by its own
# f2/g2/h2 pawns and nothing can take or block. Ra1 is a real saving
# alternative, so clause 2 passes and the old code produced a full card:
#   "Nc4 left your rook on d1 available. Their queen on d8 could win it with
#    Qxd1#. Nd5 would have kept the rook on d1."
MATE_AS_MATERIAL_FEN = "3q3k/5ppp/8/8/8/4N3/5PPP/3R2K1 w - - 0 1"


def test_abstains_when_the_punishment_is_checkmate():
    cause = build_legal_material_loss_cause(
        fen_before=MATE_AS_MATERIAL_FEN,
        played_san="Nc4",
        best_move_san="Ra1",
        minimum_gain_cp=FLOOR,
    )
    assert cause is None, (
        "Qxd1 is checkmate, so the lesson is the mate, not the rook. A "
        "material card here talks about 500 centipawns while the player is "
        f"being mated. Got: {cause}"
    )


def test_the_same_shape_still_fires_when_the_capture_is_not_mate():
    # Control for the gate above: identical geometry, but White's h-pawn is on
    # h3, so after Qxd1+ the king walks to h2. Qxd1 then simply wins the rook,
    # the material card is the correct lesson, and it must still be produced.
    cause = build_legal_material_loss_cause(
        fen_before="3q3k/5ppp/8/8/8/4N2P/5PP1/3R2K1 w - - 0 1",
        played_san="Nc4",
        best_move_san="Ra1",
        minimum_gain_cp=FLOOR,
    )
    assert cause is not None, "a genuine loose-rook card must survive the gate"
    assert cause.affected.square == "d1"
    assert cause.punishment_san == "Qxd1+"
