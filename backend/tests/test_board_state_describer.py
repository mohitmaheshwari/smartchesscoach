"""Unit tests for services/board_state_describer.py.

Covers each metric in isolation (using crafted FENs where one shape
clearly dominates) plus the top-N selector's diversity rule.
"""
from __future__ import annotations

import os
import sys

# Ensure backend/ is on sys.path so `import services...` works when
# this file is run directly with `python tests/test_board_state_describer.py`.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from services.board_state_describer import (  # noqa: E402
    BoardStateFact,
    describe_board_state,
    select_top_facts,
)


# ────────────────────────────────────────────────────────────────────
# describe_board_state — fact_id presence by FEN
# ────────────────────────────────────────────────────────────────────


def _fact_ids(facts):
    return {f.fact_id for f in facts}


def test_starting_position_emits_no_facts():
    # Both sides symmetric, no piece is undefended, no king pressure,
    # no gap. Move 1 also gates out development metrics by move count
    # (the metric only fires when a real GAP exists, not at game start).
    facts = describe_board_state(
        fen_after="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        user_color="white",
        move_number=1,
    )
    assert facts == []


def test_queen_alone_active_fires():
    # White queen on h5 (rank 5 — opp territory for white), all other
    # white pieces on home rank. Plus white is to move so we ensure
    # FEN is well-formed.
    fen = "rnbqkbnr/ppp1pppp/8/3p3Q/8/8/PPPP1PPP/RNB1KBNR b KQkq - 1 3"
    facts = describe_board_state(fen, "white", move_number=8)
    ids = _fact_ids(facts)
    assert "bs_queen_alone_active" in ids
    # Pull the fact, check the queen square placeholder
    q = next(f for f in facts if f.fact_id == "bs_queen_alone_active")
    assert q.placeholders["bs_queen_square"] == "h5"
    assert q.category == "activity"
    assert q.severity == 25


def test_development_gap_fires_when_opp_developed_more():
    # White: just pawn moves, knights/bishops on home squares.
    # Black: knights on f6/c6, bishop on f5 → 3 developed.
    fen = "r2qkb1r/pppp1ppp/2n2n2/4pb2/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 4"
    facts = describe_board_state(fen, "white", move_number=4)
    ids = _fact_ids(facts)
    assert "bs_development_gap" in ids
    f = next(x for x in facts if x.fact_id == "bs_development_gap")
    assert f.placeholders["bs_user_developed"] == 0
    assert f.placeholders["bs_opp_developed"] == 3
    assert f.severity == 20  # gap >= 3


def test_development_gap_silent_late_game():
    # Same FEN but move_number > 20 — opening metric should not fire.
    fen = "r2qkb1r/pppp1ppp/2n2n2/4pb2/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 4"
    facts = describe_board_state(fen, "white", move_number=25)
    assert "bs_development_gap" not in _fact_ids(facts)


def test_pieces_on_back_rank_fires_in_opening():
    # White all minors home (4); black has knight on c6 developed (3 home).
    # User=white is behind in development → fires.
    fen = "r1bqkbnr/pppppppp/2n5/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 1 2"
    facts = describe_board_state(fen, "white", move_number=3)
    ids = _fact_ids(facts)
    assert "bs_pieces_on_back_rank" in ids
    f = next(x for x in facts if x.fact_id == "bs_pieces_on_back_rank")
    assert f.placeholders["bs_back_rank_count"] == 4


def test_king_shield_broken_after_castling_with_pushed_pawns():
    # White king castled kingside (on g1), kingside pawns pushed —
    # f-pawn pushed to f4, g/h pawns advanced/missing → shield broken.
    # We need: king on g1 (not e1), front rank = rank 2, files f/g/h
    # mostly missing user pawns.
    fen = "rnbqkbnr/pppppppp/8/8/5P2/6P1/PPPPP2P/RNBQ1RK1 b kq - 0 1"
    facts = describe_board_state(fen, "white", move_number=12)
    ids = _fact_ids(facts)
    assert "bs_king_shield_broken" in ids


def test_king_shield_intact_after_castling():
    # White castled kingside, pawns still on f2/g2/h2 → shield intact.
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ1RK1 b kq - 0 1"
    facts = describe_board_state(fen, "white", move_number=12)
    assert "bs_king_shield_broken" not in _fact_ids(facts)


def test_central_control_gap_fires():
    # Black has knights on c6/f6 attacking the center; white has
    # only pawns and homed pieces.
    fen = "r1bqkb1r/pppppppp/2n2n2/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    facts = describe_board_state(fen, "white", move_number=4)
    ids = _fact_ids(facts)
    assert "bs_central_control_gap" in ids


def test_open_file_owned_by_opp_fires():
    # d-file is fully open of pawns AND white has no major on it.
    # Black rook on d8 owns the file. White rook on a1, bishop on c1,
    # king on g1; black has bishop on f8, king on g8.
    fen = "3r1bk1/ppp1pppp/8/8/8/8/PPP1PPPP/R1B3K1 w - - 0 13"
    facts = describe_board_state(fen, "white", move_number=14)
    ids = _fact_ids(facts)
    assert "bs_open_file_owned_by_opp" in ids
    f = next(x for x in facts if x.fact_id == "bs_open_file_owned_by_opp")
    assert f.placeholders["bs_file_letter"] == "d"
    assert f.placeholders["bs_opp_major_piece"] == "rook"


def test_isolated_attacker_fires():
    # White knight on e5 (rank 5 = opp territory for white), no white
    # defender, attacked by black pieces (pawns on d6 and f6).
    fen = "rnbqkb1r/pp1p1ppp/3p1p2/4N3/8/8/PPPP1PPP/RNBQKB1R b KQkq - 0 1"
    facts = describe_board_state(fen, "white", move_number=8)
    ids = _fact_ids(facts)
    assert "bs_isolated_attacker" in ids


def test_user_color_black_flips_perspective():
    # Black queen on a4 (rank 4 = opp territory for black), all other
    # black pieces home. From BLACK's perspective this is queen alone.
    fen = "rnb1kbnr/ppppp1pp/5p2/8/q7/8/PPPPPPPP/RNBQKBNR w KQkq - 1 3"
    facts = describe_board_state(fen, "black", move_number=8)
    ids = _fact_ids(facts)
    assert "bs_queen_alone_active" in ids
    f = next(x for x in facts if x.fact_id == "bs_queen_alone_active")
    assert f.placeholders["bs_queen_square"] == "a4"


# ────────────────────────────────────────────────────────────────────
# select_top_facts — diversity + ranking
# ────────────────────────────────────────────────────────────────────


def test_select_top_facts_preserves_severity_order():
    facts = [
        BoardStateFact("a", "activity", 10),
        BoardStateFact("b", "coordination", 25),
        BoardStateFact("c", "development", 15),
    ]
    facts.sort(key=lambda x: x.severity, reverse=True)
    picked = select_top_facts(facts, n=2)
    assert [f.fact_id for f in picked] == ["b", "c"]


def test_select_top_facts_diversity_caps_per_category():
    # Three from "activity", two from "development". With max=2 per
    # category, we must drop one activity.
    facts = [
        BoardStateFact("act1", "activity", 25),
        BoardStateFact("act2", "activity", 20),
        BoardStateFact("act3", "activity", 18),
        BoardStateFact("dev1", "development", 17),
        BoardStateFact("dev2", "development", 12),
    ]
    facts.sort(key=lambda x: x.severity, reverse=True)
    picked = select_top_facts(facts, n=3, max_per_category=2)
    ids = [f.fact_id for f in picked]
    # Top severity from activity (act1, act2) kept; third slot goes
    # to highest-severity NON-activity → dev1.
    assert ids == ["act1", "act2", "dev1"]


def test_select_top_facts_returns_empty_for_empty_input():
    assert select_top_facts([], n=3) == []


def test_select_top_facts_returns_fewer_when_input_short():
    facts = [BoardStateFact("only", "activity", 10)]
    picked = select_top_facts(facts, n=3)
    assert len(picked) == 1
    assert picked[0].fact_id == "only"


# ────────────────────────────────────────────────────────────────────
# Robustness
# ────────────────────────────────────────────────────────────────────


def test_invalid_fen_returns_empty_list():
    assert describe_board_state("not-a-real-fen", "white", 10) == []


def test_unknown_color_treated_as_black():
    # The describer falls back to black for any non-"white" input.
    facts = describe_board_state(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "purple",
        1,
    )
    # Just ensure it doesn't crash. Empty result expected at move 1.
    assert isinstance(facts, list)


if __name__ == "__main__":  # pragma: no cover
    # Tiny self-runner so `python test_board_state_describer.py`
    # gives a quick pass/fail without pytest.
    import traceback

    funcs = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = []
    for fn in funcs:
        try:
            fn()
            passed += 1
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed.append((fn.__name__, traceback.format_exc()))
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{passed}/{len(funcs)} passed.")
    if failed:
        print("\nFailures:")
        for name, tb in failed:
            print(f"\n--- {name} ---\n{tb}")
        sys.exit(1)
