"""Regression tests for move-caused pin/skewer attribution.

The aligned-piece primitive is allowed to describe only a shape created by the
played move. A shape that was already present cannot become evidence that the
player created, spotted, or walked into that motif.
"""

from services.caption_facts import extract_facts
from services.motif_profile_service import _classify_aligned


def _aligned(fen: str, played_san: str):
    return extract_facts(
        fen_before=fen,
        played_san=played_san,
        best_move_san=played_san,
        cp_loss=0,
    )["aligned_pieces_evidence"]


def test_unrelated_move_does_not_claim_preexisting_absolute_pin():
    aligned = _aligned(
        "4k3/8/2n5/1B6/8/8/P7/4K3 w - - 0 1",
        "a3",
    )

    assert aligned == []
    assert _classify_aligned(aligned) == set()


def test_new_absolute_pin_is_a_pin_not_a_skewer():
    aligned = _aligned(
        "4k3/8/2n5/8/8/8/4B3/4K3 w - - 0 1",
        "Bb5",
    )

    assert len(aligned) == 1
    assert aligned[0]["rear_is_king"] is True
    assert aligned[0]["front_value_vs_rear"] == "lower"
    assert _classify_aligned(aligned) == {"pin"}


def test_slider_move_along_existing_pin_line_is_not_new_attribution():
    aligned = _aligned(
        "4k3/8/2n5/8/B7/8/8/7K w - - 0 1",
        "Bb5",
    )

    assert aligned == []


def test_unrelated_move_does_not_claim_preexisting_skewer():
    aligned = _aligned(
        "4r1k1/8/2q5/1B6/8/8/P6K/8 w - - 0 1",
        "a3",
    )

    assert aligned == []
    assert _classify_aligned(aligned) == set()


def test_new_queen_rook_alignment_is_classified_as_skewer():
    aligned = _aligned(
        "4r1k1/8/2q5/8/8/8/4B2K/8 w - - 0 1",
        "Bb5",
    )

    assert len(aligned) == 1
    assert aligned[0]["front_piece_type"] == "queen"
    assert aligned[0]["rear_piece_type"] == "rook"
    assert aligned[0]["front_value_vs_rear"] == "higher"
    assert _classify_aligned(aligned) == {"skewer"}
