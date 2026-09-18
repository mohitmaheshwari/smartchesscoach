"""A mate swing is about the king or the tactic, never "oversight".

`docs/move_classification_from_gold_scope.md` §1, amendment 2, signed off
2026-09-18. One line in `analysis_interpreter` assigned TACTICAL_OVERSIGHT to
every missed mate, and it is the single largest source of mislabelling in the
product.

Measured on production, 1,339 stored `tactical_oversight` moves:

    49.4%  had mate and lost it      -> belongs to missed_tactic
     4.0%  allowed a NEW mate        -> belongs to king_safety
    46.4%  no mate involved          -> genuinely not a mate swing
     0.3%  already lost before the move

It is also why that bucket's average cp_loss reads 7,524 — those are mate
scores, not oversights — and why 81% of its `generic_oversight` subtype is a
mate swing when sampled independently.

The allowed-mate half never had a rule at all: the missed-mate trigger only
fires when a mate existed BEFORE the move, so a player walking into one fell
through to whatever the generic gap analysis guessed.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import analysis_interpreter as ai  # noqa: E402

SOURCE = (BACKEND / "analysis_interpreter.py").read_text(encoding="utf-8")


def test_a_missed_mate_is_a_missed_tactic_not_an_oversight():
    trigger = SOURCE[SOURCE.index("# TRIGGER 2: the mate gate."):]
    trigger = trigger[: trigger.index("# TRIGGER 3")]
    assert "cognitive_gap = GAP_MISSED_TACTIC" in trigger
    assert "TACTICAL_OVERSIGHT" not in trigger.replace(
        "This line used to assign TACTICAL_OVERSIGHT", ""), (
        "the missed-mate branch must no longer assign tactical_oversight"
    )


def test_allowing_a_mate_is_king_safety():
    """The half that had no rule at all.

    Asserted on behaviour rather than on source text since the rule moved into
    `mate_gate_label` -- shared so the backfill of 7,797 stored labels cannot
    drift from the live path.
    """
    trigger = SOURCE[SOURCE.index("# TRIGGER 2: the mate gate."):]
    trigger = trigger[: trigger.index("# TRIGGER 3")]
    assert "cognitive_gap = GAP_KING_SAFETY" in trigger

    # An allowed mate has NO mate before the move, so the missed-mate half can
    # never see it. This is the case that used to fall through to a guess.
    assert ai.mate_gate_label({"before": None, "after": -3}) == "king_safety"
    # Already being mated before the move is not something this move caused.
    assert ai.mate_gate_label({"before": -2, "after": -3}) is None


def test_the_missed_mate_half_tolerates_a_slower_mate():
    """Mate in 3 becoming mate in 4 is still winning; it is not the error."""
    assert ai.mate_gate_label({"before": 3, "after": 4}) is None
    assert ai.mate_gate_label({"before": 3, "after": 8}) == "missed_tactic"
    assert ai.mate_gate_label({"before": 3, "after": None}) == "missed_tactic"


def test_the_backfill_and_the_live_path_share_one_predicate():
    """The whole reason the rule is a module-level function.

    A second copy inside the backfill script would be correct the day it was
    written and wrong the first time this rule changed.
    """
    script = (BACKEND / "scripts" / "backfill_mate_gate_labels.py").read_text(
        encoding="utf-8")
    assert "from analysis_interpreter import mate_gate_label" in script
    assert "GAP_MISSED_TACTIC" not in script.replace(
        "# no local copy of GAP_MISSED_TACTIC", ""), (
        "the script must not restate the gate's own constants"
    )


def test_it_uses_the_string_constants_not_the_enum():
    """`CognitiveGap` has no MISSED_TACTIC and no KING_SAFETY.

    Its members are HANGING_PIECE_BLINDNESS, KING_SAFETY_NEGLECT and so on --
    a different vocabulary, noted at the top of analysis_interpreter. Writing
    `CognitiveGap.MISSED_TACTIC.value` raises AttributeError at runtime, which
    a source-only test would never catch, so this asserts on the enum itself.
    """
    from cognitive_gap_service import CognitiveGap

    assert not hasattr(CognitiveGap, "MISSED_TACTIC")
    assert not hasattr(CognitiveGap, "KING_SAFETY")
    assert ai.GAP_MISSED_TACTIC == "missed_tactic"
    assert ai.GAP_KING_SAFETY == "king_safety"


def test_the_gate_runs_before_the_turning_point_trigger():
    """Trigger 3 re-runs the generic gap analysis and would overwrite us."""
    gate = SOURCE.index("# TRIGGER 2: the mate gate.")
    turning = SOURCE.index("# TRIGGER 3: Turning Point")
    assert gate < turning


def test_a_position_with_no_mate_is_left_alone():
    """46.4% of the bucket. The gate must not widen into ordinary mistakes."""
    for mate_info in (None, {}, {"before": None, "after": None}):
        assert ai.mate_gate_label(mate_info) is None, mate_info


def test_a_malformed_mate_info_does_not_take_down_an_analysis_run():
    assert ai.mate_gate_label({"before": "3", "after": None}) is None


def test_the_scope_records_this_decision():
    scope = (BACKEND.parent / "docs" /
             "move_classification_from_gold_scope.md").read_text(encoding="utf-8")
    assert "SIGNED OFF 2026-09-18" in scope
    assert "Mate gate" in scope


def test_the_gate_reads_mate_scores_in_the_players_frame_not_whites():
    """The defect that nearly wrote 7,806 labels, 738 of them wrong.

    `mate_info` comes from `stockfish_service.evaluate_position`, which
    returns `score.white()` -- "positive = white mates, negative = black
    mates". The first version of this gate ignored that and was colour-blind.
    Measured on production over 8,863 fires before the fix:

        613  a BLACK player with after=-17 is mating in 17, and was told
             "you walked into mate"
        109  a WHITE player with before=-22 was being mated and ESCAPED,
             and was told "you had a forced win and let it go"
         16  had mate in 2, now faces mate in 3 -- losing a won game, which
             is a missed tactic before it is a king-safety lapse

    Every assertion below is one of those three, in both colours.
    """
    g = ai.mate_gate_label

    # Losing your own forced mate, from either side of the board.
    assert g({"before": 3, "after": None}, "white") == "missed_tactic"
    assert g({"before": -3, "after": None}, "black") == "missed_tactic"

    # Escaping a mate against you is a GOOD move. It is not a missed tactic.
    assert g({"before": -3, "after": None}, "white") is None
    assert g({"before": 3, "after": None}, "black") is None

    # Walking into a mate, from either side.
    assert g({"before": None, "after": -17}, "white") == "king_safety"
    assert g({"before": None, "after": 17}, "black") == "king_safety"

    # ...and the same number when it means the player is WINNING.
    assert g({"before": None, "after": -17}, "black") is None
    assert g({"before": None, "after": 17}, "white") is None

    # Mate in 2 becoming mate in 3 against you is losing a won game.
    assert g({"before": 2, "after": -3}, "white") == "missed_tactic"

    # Already being mated before the move is not this move's doing.
    assert g({"before": -2, "after": -3}, "white") is None


def test_the_interpreter_passes_the_colour_down_to_the_gate():
    """The predicate being correct is worth nothing if the caller drops it."""
    assert "mate_gate_label(mate_info, user_color)" in SOURCE
    # _interpret_single_move must both accept the colour and be handed it.
    signature = SOURCE[SOURCE.index("def _interpret_single_move"):]
    assert "user_color" in signature[: signature.index(") -> InterpretedMove")]
    call = SOURCE[SOURCE.index("interpreted_move = self._interpret_single_move"):]
    assert "user_color=user_color" in call[:160]


def test_the_backfill_resolves_each_games_colour():
    """A backfill that assumed white would reintroduce the same 738 errors."""
    script = (BACKEND / "scripts" / "backfill_mate_gate_labels.py").read_text(
        encoding="utf-8")
    assert "user_color" in script
    assert "mate_gate_label(" in script


def test_playing_the_checkmate_is_not_a_missed_tactic():
    """Mate in ZERO is checkmate on the board, i.e. the player just won.

    Zero has no sign, so it cannot be flipped into a player's frame -- but on
    a move the player made, checkmate afterwards can only mean they delivered
    it, since you cannot move yourself into being mated.

    Board-verified on production: 400 of 400 sampled `after == 0` moves are
    the player playing mate (Qh1#, Rxf6#, Qxf7#). Without this the gate calls
    2,751 checkmates "missed_tactic" -- you had mate in 1, you played it, and
    the product tells you that you missed a tactic. It is the winning move of
    the game recorded as the mistake of the game.
    """
    g = ai.mate_gate_label
    assert g({"before": 1, "after": 0}, "white") is None     # white played M1
    assert g({"before": -1, "after": 0}, "black") is None    # black played M1
    assert g({"before": 3, "after": 0}, "white") is None     # mated early
    # Checkmate before the move cannot happen; there would be no move to judge.
    assert g({"before": 0, "after": None}, "white") is None

    # And the neighbouring cases must still fire, so this is not a blanket mute.
    assert g({"before": 1, "after": None}, "white") == "missed_tactic"
    assert g({"before": None, "after": -1}, "white") == "king_safety"
