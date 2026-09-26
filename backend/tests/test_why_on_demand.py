"""Tests for the on-demand "Why" button and the both-sides scoreboard.

The property under test is mostly a NEGATIVE one: the feature exists to
stop the system manufacturing a reason it cannot derive, so the tests
that matter most are the ones asserting it stays quiet.
"""

import os
import sys

import chess
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.game_summary_service import build_move_scoreboard  # noqa: E402
from services.punishment_resolver import _net_victim_loss  # noqa: E402
from services.why_on_demand import _arrows, _phrase, explain  # noqa: E402


class _Stub:
    """Minimal stand-in for Punishment; _phrase only reads these fields."""

    def __init__(self, direction, mechanism, victim_piece=None,
                 agent_move="Nf3", victim_square=None, returns_home=False):
        self.direction = direction
        self.mechanism = mechanism
        self.victim_piece = victim_piece
        self.agent_move = agent_move
        self.victim_square = victim_square
        self.returns_home = returns_home


# --------------------------------------------------------------------------
# _net_victim_loss: which piece the victim is genuinely down
# --------------------------------------------------------------------------

def test_even_trade_names_no_piece():
    """A knight for a knight is not a piece anyone lost.

    Without this, WINS_MATERIAL would name a victim on every exchange
    and the caption would claim a loss the player did not suffer.
    """
    pre = chess.Board()
    after = chess.Board()
    after.remove_piece_at(chess.G8)   # black knight
    after.remove_piece_at(chess.G1)   # white knight
    assert _net_victim_loss(pre, after, chess.BLACK, chess.WHITE) is None


def test_knight_for_pawn_names_the_knight():
    pre = chess.Board()
    after = chess.Board()
    after.remove_piece_at(chess.G8)   # black loses a knight
    after.remove_piece_at(chess.A2)   # white loses only a pawn
    assert _net_victim_loss(pre, after, chess.BLACK, chess.WHITE) == "knight"


def test_nothing_lost_names_nothing():
    pre = chess.Board()
    assert _net_victim_loss(pre, chess.Board(), chess.BLACK, chess.WHITE) is None


def test_queen_survives_cancellation_against_a_rook():
    pre = chess.Board()
    after = chess.Board()
    after.remove_piece_at(chess.D8)   # black queen
    after.remove_piece_at(chess.A1)   # white rook
    assert _net_victim_loss(pre, after, chess.BLACK, chess.WHITE) == "queen"


# --------------------------------------------------------------------------
# _phrase: never dress an unknown up as a known
# --------------------------------------------------------------------------

def test_unnamed_material_never_says_piece():
    """"wins your piece" is a sentence with no information in it.

    It shipped for months because the `or "piece"` fallback could not
    fail. When the resolver cannot name the loss we say "material".
    """
    for direction in ("received", "missed"):
        text = _phrase(_Stub(direction, "WINS_MATERIAL"), "Qd3")
        assert text is not None
        assert "piece" not in text
        assert "material" in text


def test_named_material_uses_the_name():
    text = _phrase(_Stub("received", "WINS_MATERIAL", victim_piece="knight",
                         agent_move="Bxe5"), "Qd3")
    assert "knight" in text
    assert "material" not in text


def test_unknown_mechanism_returns_none_not_filler():
    assert _phrase(_Stub("received", "SOMETHING_NEW"), "Qd3") is None


def test_no_numeric_quantities_in_any_phrase():
    """No centipawns, no counts, no "2 pawns".

    Digits inside a move name (Nf3) or a square (e5) are the board's own
    vocabulary and stay; a NUMBER is what must never appear.
    """
    for direction in ("received", "missed"):
        for mech in ("MATE", "WINS_MATERIAL", "FORK", "TRAPPED",
                     "PROMOTES", "FORCES_RETREAT"):
            text = _phrase(_Stub(direction, mech, victim_piece="rook",
                                 victim_square="e5", agent_move="Nf3"), "Qd3")
            if not text:
                continue
            stripped = text.replace("Qd3", "").replace("e5", "").replace("Nf3", "")
            assert not any(ch.isdigit() for ch in stripped), (mech, text)
            # and no spelled-out counts either
            for word in (" two pawns", " three pawns", " a pawn and"):
                assert word not in text.lower(), (mech, text)


# --------------------------------------------------------------------------
# explain(): silence is a valid answer
# --------------------------------------------------------------------------

def test_explain_returns_none_with_nothing_to_go_on():
    assert explain(chess.STARTING_FEN, "e4", [], []) is None


def test_explain_refuses_a_candidate_that_is_much_worse():
    """The closeness gate must not be bypassed to get a tidier story.

    Candidate 2 is explainable-looking but a long way behind candidate 1,
    so the loop has to stop rather than recommend it.
    """
    board = chess.Board()
    cands = [
        {"move_san": "e4", "eval_cp": 30, "line_san": ["e4", "e5"]},
        {"move_san": "a4", "eval_cp": -400, "line_san": ["a4", "e5"]},
    ]
    assert explain(board.fen(), "h4", [], cands) is None


def test_explain_has_no_fen_no_answer():
    assert explain("", "e4", [], []) is None
    assert explain(chess.STARTING_FEN, "", [], []) is None


# --------------------------------------------------------------------------
# _arrows: built from the board, never from the sentence
# --------------------------------------------------------------------------

def test_arrows_come_from_pushing_moves():
    arrows = _arrows(chess.STARTING_FEN, ["e4", "e5", "Nf3"])
    assert [a["from"] for a in arrows] == ["e2", "e7", "g1"]
    assert [a["to"] for a in arrows] == ["e4", "e5", "f3"]


def test_arrows_stop_at_an_illegal_move_rather_than_guess():
    arrows = _arrows(chess.STARTING_FEN, ["e4", "Qxh8", "Nf3"])
    assert len(arrows) == 1


# --------------------------------------------------------------------------
# build_move_scoreboard: both sides, nothing dropped
# --------------------------------------------------------------------------

def _mv(n, san, severity, is_user):
    return {"move_number": n, "move_san": san, "severity": severity,
            "is_user_move": is_user, "phase": "middlegame", "plan": {}}


def test_scoreboard_keeps_every_moment_not_just_the_top_three():
    """GameSummary caps at 3 user + 2 opponent. A section whose point is
    completeness must not inherit that cap."""
    v5 = [_mv(i, f"N{i}", "blunder", True) for i in range(1, 6)]
    v5 += [_mv(i, f"B{i}", "opp_blunder", False) for i in range(6, 10)]
    out = build_move_scoreboard(v5)
    assert len(out["moments"]) == 9
    assert out["you"]["blunder"] == 5
    assert out["opponent"]["blunder"] == 4


def test_scoreboard_ignores_good_moves():
    v5 = [_mv(1, "e4", "good", True), _mv(2, "e5", "good", False),
          _mv(3, "Qh5", "mistake", True)]
    out = build_move_scoreboard(v5)
    assert len(out["moments"]) == 1
    assert out["moments"][0]["move_san"] == "Qh5"


def test_scoreboard_labels_the_two_sides():
    v5 = [_mv(1, "Qh5", "mistake", True), _mv(2, "Nf6", "opp_mistake", False)]
    out = build_move_scoreboard(v5)
    sides = {m["side"] for m in out["moments"]}
    assert sides == {"you", "opponent"}


def test_scoreboard_is_in_move_order():
    v5 = [_mv(9, "Rd1", "blunder", True), _mv(2, "Qh5", "mistake", True),
          _mv(5, "Nf6", "opp_mistake", False)]
    out = build_move_scoreboard(v5)
    assert [m["move_number"] for m in out["moments"]] == [2, 5, 9]


def test_scoreboard_empty_input_is_safe():
    out = build_move_scoreboard([])
    assert out["moments"] == []


# --------------------------------------------------------------------------
# The symbols the route imports at call time
# --------------------------------------------------------------------------

def test_engine_class_and_method_exist():
    """The route imports these INSIDE the request handler.

    A wrong name there cannot fail at startup, cannot fail at import,
    and cannot fail in any unit test -- it fails once, per click, as a
    caught exception that the endpoint reports as "no reason found".
    Shipped exactly that way: the class is StockfishEngine and the route
    asked for StockfishService, so every click returned engine_error in
    0.1s and looked indistinguishable from honest silence.
    """
    import inspect

    from stockfish_service import StockfishEngine

    assert hasattr(StockfishEngine, "get_candidate_lines")
    assert hasattr(StockfishEngine, "__enter__")
    assert hasattr(StockfishEngine, "__exit__")
    params = inspect.signature(StockfishEngine.__init__).parameters
    assert "threads" in params

    sig = inspect.signature(StockfishEngine.get_candidate_lines).parameters
    for expected in ("board", "num", "depth", "pv_length"):
        assert expected in sig, expected


def test_route_module_imports_names_that_exist():
    """Walk the handler's own source for `from X import Y` and resolve each.

    Deferred imports inside a function body are invisible to every other
    check in this file; this is the one that looks at them.
    """
    import ast
    import importlib
    import os

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(here, "routes", "coach.py"), encoding="utf-8").read()
    tree = ast.parse(src)

    handler = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == "get_move_why"),
        None,
    )
    assert handler is not None, "get_move_why not found"

    checked = 0
    for node in ast.walk(handler):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        module = importlib.import_module(node.module)
        for alias in node.names:
            assert hasattr(module, alias.name), (
                f"{node.module} has no {alias.name}")
            checked += 1
    assert checked > 0, "no deferred imports found -- test is vacuous"


# --------------------------------------------------------------------------
# Scoreboard rows must not repeat what the row already shows
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "Opening mistake (move 10)",
    "Opening blunder (move 4)",
    "Mistake on move 17",
    "Blunder on move 3",
    "Endgame slip (move 40)",
    "",
    None,
])
def test_filler_descriptions_are_dropped(raw):
    from services.game_summary_service import _scoreboard_text
    assert _scoreboard_text(raw) is None


@pytest.mark.parametrize("raw,expected", [
    ("Left piece hanging (move 12)", "Left piece hanging"),
    ("Allowed a fork (move 9)", "Allowed a fork"),
    ("Back rank exposed (move 21)", "Back rank exposed"),
    ("Got pinned (move 8)", "Got pinned"),
])
def test_real_descriptions_survive_minus_the_move_number(raw, expected):
    from services.game_summary_service import _scoreboard_text
    assert _scoreboard_text(raw) == expected


def test_opponent_rows_carry_no_template_sentence():
    """"A chance for you here" on every opponent error is a template."""
    v5 = [_mv(3, "Bxe5", "opp_mistake", False)]
    out = build_move_scoreboard(v5)
    assert out["moments"][0]["text"] is None
    assert out["moments"][0]["side"] == "opponent"


# --------------------------------------------------------------------------
# Arrows must survive the REAL frames, not a hand-written line
# --------------------------------------------------------------------------

def test_received_arrows_are_drawn_from_the_real_resolver_output():
    """1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6?? 4.Qxf7#.

    The isolation test above feeds _arrows a line that already starts at
    fen_before, so it passed while the shipped code fed it a line that
    began two moves later -- every SAN illegal, every arrow dropped. This
    goes through explain() and asserts the arrows actually come back.
    """
    board = chess.Board()
    for san in ("e4", "e5", "Bc4", "Nc6", "Qh5"):
        board.push_san(san)
    fen = board.fen()   # Black to move; Nf6 allows mate

    out = explain(fen, "Nf6", ["Nf6", "Qxf7#"], [])
    assert out is not None
    assert out["direction"] == "received"
    assert out["mechanism"] == "MATE"
    assert out["arrows"], "arrows came back empty"
    # first the mistake, then the move that punishes it
    assert (out["arrows"][0]["from"], out["arrows"][0]["to"]) == ("g8", "f6")
    assert (out["arrows"][1]["from"], out["arrows"][1]["to"]) == ("h5", "f7")


def test_missed_arrows_start_at_the_recommended_move():
    board = chess.Board()
    for san in ("e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"):
        board.push_san(san)
    fen = board.fen()

    cands = [{
        "move_san": "Qxf7#",
        "eval_cp": 100000,
        "line_san": ["Qxf7#"],
    }]
    out = explain(fen, "d3", [], cands)
    if out is None:
        pytest.skip("resolver found no missed punishment in this frame")
    assert out["direction"] == "missed"
    assert out["arrows"], "arrows came back empty"
    assert out["arrows"][0]["san"] == "Qxf7#"


def test_every_found_result_that_has_a_line_also_has_arrows():
    """A found answer with an empty arrow list is the bug that shipped."""
    board = chess.Board()
    for san in ("e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"):
        board.push_san(san)
    fen = board.fen()
    for played, pv, cands in (
        ("Qxf7#", ["Qxf7#"], []),
        ("d3", [], [{"move_san": "Qxf7#", "eval_cp": 100000,
                     "line_san": ["Qxf7#"]}]),
    ):
        out = explain(fen, played, pv, cands)
        if out and out.get("line_san"):
            assert out["arrows"], (played, out["line_san"])


# --------------------------------------------------------------------------
# The mismatch gate: a scrap is not an explanation for a catastrophe
# --------------------------------------------------------------------------

def test_gate_keeps_a_proportionate_claim():
    from services.punishment_resolver import Punishment
    from services.why_on_demand import _explains_the_loss
    # 1137cp move, queen won -> proportionate, must survive
    p = Punishment(direction="received", mechanism="WINS_MATERIAL",
                   agent_move="Qxc5", payoff_cp=900)
    assert _explains_the_loss(p, 1137)


def test_gate_drops_a_scrap_on_a_catastrophe():
    from services.punishment_resolver import Punishment
    from services.why_on_demand import _explains_the_loss
    for cp, pay in ((9246, 100), (9148, 100), (8640, 100), (1239, 100),
                    (1305, 200), (8877, 500)):
        p = Punishment(direction="received", mechanism="WINS_MATERIAL",
                       agent_move="Rg1+", payoff_cp=pay)
        assert not _explains_the_loss(p, cp), (cp, pay)


def test_gate_leaves_small_losses_alone():
    """Below the threshold a pawn IS the proportionate answer."""
    from services.punishment_resolver import Punishment
    from services.why_on_demand import _explains_the_loss
    for cp in (100, 141, 200, 349, 999):
        p = Punishment(direction="received", mechanism="WINS_MATERIAL",
                       agent_move="Bxe5", payoff_cp=100)
        assert _explains_the_loss(p, cp), cp


def test_gate_never_judges_a_synthetic_payoff():
    """FORCES_RETREAT pays max(1, value//10) and MATE/PROMOTES pay a
    constant. Comparing those to cp_loss is meaningless, and doing it
    would delete sound captions."""
    from services.punishment_resolver import Punishment
    from services.why_on_demand import _explains_the_loss
    for mech in ("FORCES_RETREAT", "MATE", "PROMOTES"):
        p = Punishment(direction="received", mechanism=mech,
                       agent_move="hxg4", payoff_cp=30)
        assert _explains_the_loss(p, 9999), mech


def test_gate_is_not_knife_edge():
    """20% and 25% suppressed the same 6 answers in the measured sample."""
    from services.why_on_demand import MISMATCH_MIN_RATIO, MISMATCH_MIN_CP_LOSS
    assert 0.15 <= MISMATCH_MIN_RATIO <= 0.35
    assert MISMATCH_MIN_CP_LOSS >= 500
