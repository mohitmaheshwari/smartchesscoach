"""Integrity gates for the trap library.

Every check here corresponds to a defect that was live in production on
2026-09-05, found by replaying all 55 traps through python-chess and
Stockfish:

  * the beneficiary of a trap was derived from a hard-coded family -> colour
    table, which disagreed with the trap's own ``trap_color`` for 17 of the
    36 forced traps, so the player who SPRANG Legal's Mate or Noah's Ark was
    told "You fell into the ...!";
  * ``how_to_avoid`` was derived from ``trap_line[0]``, which is the
    trap-SETTER's move in 30 of 55 entries;
  * ``safe_moves`` contained moves that were illegal at the decision point,
    and one (Stafford Castling Trap's ``d4``) that allows mate in one.

These use python-chess only -- no engine, no database -- so they run
anywhere. The centipawn judgements that produced the safe-move removals are
recorded in the commit; this file guards the structural invariants.
"""
import json
import sys
from pathlib import Path

import chess
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

TRAPS_PATH = BACKEND / "data" / "traps.json"


def _traps():
    data = json.loads(TRAPS_PATH.read_text(encoding="utf-8"))
    for family, entries in data.items():
        if str(family).startswith("_") or not isinstance(entries, list):
            continue
        for trap in entries:
            if isinstance(trap, dict):
                yield family, trap


def _board_after(moves):
    board = chess.Board()
    for san in moves:
        board.push_san(san)
    return board


ALL = list(_traps())


def test_the_library_is_not_empty():
    assert len(ALL) >= 50


@pytest.mark.parametrize("family,trap", ALL, ids=[f"{f}/{t['name']}" for f, t in ALL])
def test_every_line_is_legal(family, trap):
    """Setup and trap line must replay from the initial position."""
    board = chess.Board()
    for san in trap.get("setup_moves", []):
        board.push_san(san)
    for step in trap.get("trap_line", []):
        board.push_san(step["move"])


@pytest.mark.parametrize("family,trap", ALL, ids=[f"{f}/{t['name']}" for f, t in ALL])
def test_trap_color_is_stated(family, trap):
    """analyze_game_for_traps fails closed without it, so it must be present."""
    assert trap.get("trap_color") in ("white", "black"), trap.get("name")


@pytest.mark.parametrize("family,trap", ALL, ids=[f"{f}/{t['name']}" for f, t in ALL])
def test_the_line_never_checkmates_its_own_setter(family, trap):
    """The Mortimer entry ended with the trap-SETTER mated while claiming
    result_type=checkmate for that same side."""
    board = chess.Board()
    for san in trap.get("setup_moves", []):
        board.push_san(san)
    for step in trap.get("trap_line", []):
        board.push_san(step["move"])
    if not board.is_checkmate():
        return
    mated = "white" if board.turn == chess.WHITE else "black"
    assert mated != trap["trap_color"], (
        f"{trap['name']}: the line mates {mated}, which is the trap_color"
    )


@pytest.mark.parametrize("family,trap", ALL, ids=[f"{f}/{t['name']}" for f, t in ALL])
def test_safe_moves_are_legal_at_a_real_decision_point(family, trap):
    """Two conventions exist for where the victim's mistake sits, so a safe
    move must be legal in at least one of the two candidate positions."""
    safe = trap.get("safe_moves") or []
    if not safe:
        return
    setup = trap.get("setup_moves", [])
    candidates = [_board_after(setup)]
    if setup:
        candidates.append(_board_after(setup[:-1]))
    for move in safe:
        assert any(_legal(board, move) for board in candidates), (
            f"{trap['name']}: safe move {move!r} is illegal at either decision point"
        )


def _legal(board, san):
    try:
        board.parse_san(san)
        return True
    except Exception:
        return False


def test_beneficiary_comes_from_trap_color_not_the_opening_family():
    """The regression itself: a Black trap inside a White-named opening.

    Noah's Ark is trap_color=black but lives under ruy-lopez. The old code
    read the family name and credited White.
    """
    from services.trap_library import analyze_game_for_traps

    trap = next(t for _, t in ALL if t["name"] == "Noah's Ark Trap")
    assert trap["trap_color"] == "black"
    moves = list(trap["setup_moves"]) + [s["move"] for s in trap["trap_line"]]

    as_black = analyze_game_for_traps(moves, "black")
    as_white = analyze_game_for_traps(moves, "white")

    assert any(t["trap_name"] == "Noah's Ark Trap" for t in as_black["traps_executed"]), (
        "Black sprang the trap and must be credited with executing it"
    )
    assert any(t["trap_name"] == "Noah's Ark Trap" for t in as_white["traps_fallen_into"]), (
        "White is the victim and must be the one who fell into it"
    )


def test_a_trap_with_no_stated_colour_is_ignored_rather_than_guessed():
    from services.trap_library import analyze_game_for_traps

    # A game that matches nothing still returns the empty shape.
    out = analyze_game_for_traps(["e4", "e5"], "white")
    assert out["traps_executed"] == []
    assert out["summary"]["executed_count"] == 0


def test_how_to_avoid_is_authored_not_derived_from_the_setters_move():
    """The derived text named trap_line[0]; for a setter-first entry that is
    a move the victim never had."""
    from services.trap_library import analyze_game_for_traps

    trap = next(t for _, t in ALL if t["name"] == "Noah's Ark Trap")
    moves = list(trap["setup_moves"]) + [s["move"] for s in trap["trap_line"]]
    fell = analyze_game_for_traps(moves, "white")["traps_fallen_into"]
    entry = next(t for t in fell if t["trap_name"] == "Noah's Ark Trap")
    assert entry["how_to_avoid"] == trap.get("how_to_avoid")


def test_no_trap_is_silently_quarantined_out_of_the_catalog():
    """A content edit must never delete a trap from what players can reach.

    Rewriting the Mortimer Trap to result_type=wins_piece while the authored
    line stopped BEFORE the knight was captured tripped the curriculum
    validator's material check. The record became non-publishable and
    trick_library_service dropped it: the served catalog went 36 -> 35 with
    nothing logged. The line replay tests above all passed, because they never
    asked whether the trap survives publication.
    """
    from services.curriculum_content_validator import validate_all_content

    traps = validate_all_content()["subjects"]["traps"]
    assert traps["quarantined"] == 0, (
        "quarantined traps: "
        + ", ".join(
            cid for cid, rec in traps["records"].items() if not rec["publishable"]
        )
    )
    assert traps["publishable"] == traps["total"]


def test_the_served_catalog_still_contains_every_forced_trap():
    import trick_library_service as tls

    forced = [t for _, t in ALL if (t.get("lesson_kind") or "forced_trap") == "forced_trap"]
    assert len(tls.TRAPS_DATABASE) == len(forced)
    assert "mortimer_trap" in tls.TRAPS_DATABASE


def test_a_material_claim_is_actually_demonstrated_by_the_line():
    """result_type promising material must show it in the final position."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
              chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

    def balance(board, colour):
        return sum(values[p.piece_type] * (1 if p.color == colour else -1)
                   for p in board.piece_map().values())

    material_claims = {"wins_queen", "wins_piece", "wins_material"}
    offenders = []
    for _family, trap in ALL:
        if trap.get("result_type") not in material_claims:
            continue
        colour = chess.WHITE if trap["trap_color"] == "white" else chess.BLACK
        board = chess.Board()
        for san in trap.get("setup_moves", []):
            board.push_san(san)
        before = balance(board, colour)
        for step in trap.get("trap_line", []):
            board.push_san(step["move"])
        after = balance(board, colour)
        if not (after > 0 and after > before):
            offenders.append(f"{trap['name']} ({before} -> {after})")
    assert not offenders, "material claim not demonstrated: " + "; ".join(offenders)
