"""The card's two grades must not contradict each other.

Every card ships `severity` and `severity_canonical`. They answer different
questions, and the UI uses both: `frontend/src/lib/moveSeverity.js` gradeOf
reads `severity`, and when that says good it reaches into
`severity_canonical`, because practical softening legitimately files a real
inaccuracy under good (600 of 2,389 good cards over 120 games).

Until v238 the card filled `severity_canonical` from
`_practical.canonical_tier`, which `classify_severity_practical` recomputes
from raw cp_loss. That object knows nothing about the sanity gates, so the UI
reached past every one of them. Traced live on game_74fdbd74c468 by
intercepting compute_severity_for_move:

    m44  Qh1#  helper returned good / good, played_is_mate=True
               card carried severity=good, severity_canonical="blunder"
    m28  Nc4   helper returned context / good, best==played=True
               card carried severity=context, severity_canonical="inaccuracy"

So a player was told they blundered on the move that delivered checkmate, and
that the engine's own top choice was an inaccuracy.

The distinction these tests lock is the reason the fix is not "gate harder":

  a SANITY gate says the engine did not fault this move at all -- best move
    equals played, mate delivered, mate still forced, forced recapture, book
    move. The grade itself was wrong, so canonical must follow.
  a PRESENTATION gate says we choose not to lead with it -- practical
    softening, and the rating-band suppression in the ADAPTIVE PRIORITY block.
    The grade stands; reaching past it is that field's whole purpose, so
    canonical must NOT follow.

The negative control is the third class below. A fix that pushed canonical to
"good" whenever severity reads good would pass every positive test here and
silence the 600 real inaccuracies the field exists to carry -- which is the
same failure as grading a non-mistake, pointing the other way.

Layer 1 reads the card dict out of the AST, because the bug was never in the
helper -- the helper returned the right answer and the card dict read a
different object. No DB and no engine.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import chess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption_pipeline import compute_severity_for_move  # noqa: E402

_V5 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "services", "game_decryption_v5_service.py")


def _card_dict_value_for(key: str) -> ast.AST:
    """The expression the card dict assigns to `key`.

    Found by looking for the dict that also carries "severity" and
    "move_san", so a same-named key in some other dict cannot answer for it.
    """
    tree = ast.parse(open(_V5, encoding="utf-8").read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if not {"severity", "severity_canonical", "move_san"} <= keys:
            continue
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == key:
                return v
    raise AssertionError("no card dict carrying severity + move_san found")


class TestTheCardReadsTheGatedTier:
    def test_severity_canonical_is_not_taken_from_practical(self):
        """_practical.canonical_tier is the raw cp_loss tier and goes through
        no gate. Reading it here is the v238 bug."""
        value = _card_dict_value_for("severity_canonical")
        source = ast.unparse(value)
        assert "_practical" not in source, (
            "the card's severity_canonical reads %r -- _practical recomputes "
            "the tier from raw cp_loss, so the UI resurrects every sanity "
            "gate the pipeline applied" % source
        )

    def test_severity_canonical_is_the_name_the_gates_write(self):
        value = _card_dict_value_for("severity_canonical")
        assert isinstance(value, ast.Name), (
            "expected the local the gates mutate, got %r" % ast.unparse(value))
        assert value.id == "severity_canonical"

    def test_both_grades_come_from_the_same_gated_locals(self):
        """`severity` and `severity_canonical` must track together through the
        overrides; a dict that reads one local and one object is how they
        drifted apart in the first place."""
        sev = _card_dict_value_for("severity")
        canon = _card_dict_value_for("severity_canonical")
        assert isinstance(sev, ast.Name) and isinstance(canon, ast.Name)


class TestEverySanityOverrideMovesBothGrades:
    """An override that writes severity="good" and leaves canonical alone is
    an override the UI undoes. Checked structurally: inside the render loop,
    every statement that assigns the literal "good" to `severity` must have a
    sibling assigning "good" to `severity_canonical` -- EXCEPT the adaptive
    suppression, which is a presentation gate and is named here on purpose."""

    # The rating-band gate: "below this player's threshold -- treat as fine".
    # It decides what to SAY, not what the engine found, so it must not move
    # canonical. Identified by the local it also writes.
    _PRESENTATION_MARKER = "move_priority"

    def _sibling_bodies(self):
        tree = ast.parse(open(_V5, encoding="utf-8").read())
        out = []
        for node in ast.walk(tree):
            for field in ("body", "orelse", "finalbody"):
                body = getattr(node, field, None)
                if isinstance(body, list) and body:
                    out.append(body)
        return out

    @staticmethod
    def _assigns_good(stmt, name):
        return (
            isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name
                    for t in stmt.targets)
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value == "good"
        )

    @staticmethod
    def _writes(stmt, name):
        return isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in stmt.targets)

    def test_no_sanity_override_sets_severity_alone(self):
        offenders = []
        for body in self._sibling_bodies():
            for stmt in body:
                if not self._assigns_good(stmt, "severity"):
                    continue
                if any(self._writes(s, self._PRESENTATION_MARKER)
                       for s in body):
                    continue  # the adaptive gate, deliberately one-sided
                if not any(self._assigns_good(s, "severity_canonical")
                           for s in body):
                    offenders.append(getattr(stmt, "lineno", "?"))
        assert not offenders, (
            "severity is forced to 'good' without severity_canonical at "
            "line(s) %s -- the UI reads canonical when severity is good, so "
            "that override never reaches the screen" % offenders
        )

    def test_the_presentation_gate_is_still_one_sided(self):
        """The negative control for the test above: if someone 'fixes' the
        adaptive suppression to move canonical too, the 600 real inaccuracies
        it files under good stop being recoverable and this fails."""
        found = False
        for body in self._sibling_bodies():
            if not any(self._writes(s, self._PRESENTATION_MARKER)
                       for s in body):
                continue
            if any(self._assigns_good(s, "severity") for s in body):
                found = True
                assert not any(
                    self._assigns_good(s, "severity_canonical")
                    for s in body), (
                    "the rating-band suppression now clears canonical too; "
                    "it decides what to say, not what the engine found")
        assert found, "the adaptive suppression block was not found at all"


def _severity(**over):
    """compute_severity_for_move with a plain, quiet default position."""
    board = chess.Board()
    kwargs = dict(
        cp_loss=0, opp_cp_loss=0, is_user=True, is_white=True,
        user_color="white",
        mate_sentinel_eval_cp=None, mate_sentinel_eval_before_cp=None,
        user_eval_before_white_pov=None, user_eval_after_white_pov=None,
        opp_eval_before=None, opp_eval_after=None,
        board_before=board, played_move=None, prev_move=None,
        full_move_number=1, best_move_san=None, played_san=None,
    )
    kwargs.update(over)
    return compute_severity_for_move(**kwargs)


class TestTheGatesThemselves:
    """The helper's own answers, so a future refactor cannot move the bug
    upstream of the card dict."""

    def test_the_engines_own_move_is_not_a_fault_at_any_cp_loss(self):
        """cp_loss is a difference between two searches; when the played move
        IS the best move the number is noise, whatever its size."""
        for cpl in (30, 99, 100, 249, 250, 399, 400, 19990):
            out = _severity(cp_loss=cpl, best_move_san="Nf3", played_san="Nf3")
            assert out.is_best_equals_played is True
            assert out.severity_canonical == "good", cpl
            assert out.severity_user_facing == "good", cpl

    def test_a_delivered_mate_is_not_a_blunder(self):
        """The shape of Mohit's Qh1# card: a back-rank mate, Black to move.
        cp_loss is the mate sentinel, which is exactly why the raw tier said
        blunder on the move that won the game."""
        board = chess.Board("r5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        move = board.parse_san("Ra1#")
        after = board.copy(stack=False)
        after.push(move)
        assert after.is_checkmate(), "fixture is not mate; the test proves nothing"
        out = _severity(
            cp_loss=19990, is_white=False, board_before=board,
            played_move=move, played_san="Ra1#",
        )
        assert out.played_is_mate is True
        assert out.severity_canonical == "good"

    def test_a_real_inaccuracy_keeps_its_grade(self):
        """The negative control. No gate fires, so the engine's finding
        stands and the UI can still recover it from canonical."""
        out = _severity(cp_loss=89, best_move_san="Kg7", played_san="Kf7")
        assert out.is_best_equals_played is False
        assert out.played_is_mate is False
        assert out.severity_canonical == "inaccuracy"

    def test_a_real_blunder_keeps_its_grade(self):
        out = _severity(cp_loss=425, best_move_san="Qd3", played_san="g5")
        assert out.severity_canonical == "blunder"

    def test_the_gate_stays_silent_when_the_best_move_is_unknown(self):
        """Right-or-silent: with no engine truth we never guess the move was
        best, so a 425cp loss is still a blunder."""
        out = _severity(cp_loss=425, best_move_san=None, played_san="g5")
        assert out.is_best_equals_played is False
        assert out.severity_canonical == "blunder"

    def test_the_opponent_side_gets_the_same_gate(self):
        """The gate was is_user-only before v159, which is how "Opponent's
        Nxh4 is an inaccuracy" shipped on a move the engine itself plays."""
        out = _severity(
            cp_loss=0, opp_cp_loss=44, is_user=False,
            best_move_san="Nxh4", played_san="Nxh4",
        )
        assert out.is_best_equals_played is True
        assert out.severity_canonical == "good"
        assert out.severity_user_facing == "context"
