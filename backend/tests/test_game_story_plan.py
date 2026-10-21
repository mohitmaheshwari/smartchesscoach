"""The story plan says only what the ledger holds, in plain words, no numbers.

docs/game_story_by_phase_scope.md v2, steps 3 and 4.
"""
import re

import pytest

from services.game_story_plan import (
    choose_events,
    event_text,
    finish_lines,
    lesson,
    opening_lines,
    plan_story,
    story_type,
)


def mistake(san="Ng5", move_number=16, **kw):
    base = {"kind": "your_mistake", "side": "you", "san": san, "move_number": move_number,
            "tier": "blunder", "decisive": True, "punished": False,
            "danger": {"kind": "queen_trapped", "reply": "Rh1"},
            "evidence": {"best": "Bxc3", "their_reply": "f4"},
            "eval_before": 633, "eval_after": -307, "fen_before": "x", "uci": "h3g5"}
    base.update(kw)
    return base


def theirs(san="f4", move_number=17, **kw):
    base = {"kind": "their_mistake", "side": "them", "san": san, "move_number": move_number,
            "tier": "blunder", "decisive": True, "taken": True, "your_answer": "Bxc3",
            "evidence": {"their_best": "Rh1", "your_best": "Bxc3"},
            "eval_before": -307, "eval_after": 581, "fen_before": "y", "uci": "f2f4"}
    base.update(kw)
    return base


def ledger(events, outcome="win", curve=None, opening=None, finish=None):
    return {
        "events": events,
        "outcome": outcome,
        "curve": curve if curve is not None else [20, 260, 60, 590, 630, -300, 580, 600],
        "opening": opening or {"name": "Queen's Pawn Opening", "last_move": 12, "eval_at_end": 140,
                               "costliest": {"san": "e5", "cp_loss": 100, "best": "a6"},
                               "every_move_engine_best": False},
        "finish": finish or {"outcome": outcome, "termination": "resignation",
                             "final_eval": 590, "kept_winning": True,
                             "was_winning_and_did_not_win": False},
    }


class TestStoryType:
    def test_a_win_with_an_unpunished_decisive_mistake_is_an_escape(self):
        assert story_type(ledger([mistake()]))["id"] == "narrow_escape"
        assert story_type(ledger([mistake(), mistake("Nxg5", 13)]))["id"] == "narrow_escapes"

    def test_a_win_never_in_trouble_is_clean(self):
        assert story_type(ledger([], curve=[0, 50, 200, 400, 600]))["id"] == "clean_win"

    def test_a_loss_after_being_winning_slipped_away(self):
        assert story_type(ledger([], outcome="loss", curve=[0, 400, 100, -500]))["id"] == "slipped_away"

    def test_a_quiet_game_is_not_called_dramatic(self):
        t = story_type(ledger([], outcome="loss", curve=[0, -50, -120, -400]))
        assert t["id"] == "hard_game"


class TestWords:
    def test_the_trapped_queen_escape(self):
        assert event_text(mistake(), {}) == (
            "Ng5 nearly cost you your queen. After Rh1, she would have had no safe square. "
            "They played f4 instead.")

    def test_a_quiet_best_reply_is_not_called_a_punishment(self):
        e = mistake(san="Kg2", danger={"kind": "chance", "reply": "Kg7"}, punished=True,
                    evidence={"best": "h4", "their_reply": "Kg7"}, decisive=False)
        assert event_text(e, {}) == "Kg2 was a mistake, and they found the best reply, Kg7."

    def test_only_a_decisive_mistake_says_the_win_was_gone(self):
        e = mistake(danger={"kind": "chance", "reply": "Qxd5"}, punished=True,
                    evidence={"best": "Bxc3", "their_reply": "e4"})
        assert "winning position was gone" in event_text(e, {})
        assert event_text({**e, "decisive": False}, {}) == "Ng5 was a mistake."

    def test_an_allowed_name_is_used(self):
        e = mistake(danger={"kind": "chance", "reply": "Qxd5"})
        assert event_text(e, {(16, "Ng5"): "Left a piece undefended"}) == (
            "Ng5: Left a piece undefended. They did not punish it.")

    def test_a_taken_chance_says_good_answer_not_punished(self):
        assert event_text(theirs(), {}) == "They went wrong with f4, and you found a good answer: Bxc3."


class TestLesson:
    def test_one_event_is_not_a_lesson(self):
        assert lesson(ledger([mistake()])) is None

    def test_two_events_sharing_a_theme_are(self):
        result = lesson(ledger([mistake(), mistake("Qd2", 20)]))
        assert result["id"] == "queen_danger"


class TestOpening:
    @pytest.mark.parametrize("opening, expected", [
        ({"name": "Scandinavian Defense", "every_move_engine_best": True, "eval_at_end": 30,
          "costliest": {"cp_loss": 0}}, "You played the Scandinavian Defense perfectly."),
        ({"name": "Scandinavian Defense", "every_move_engine_best": False, "eval_at_end": 10,
          "costliest": {"cp_loss": 30}}, "You played the Scandinavian Defense well."),
        ({"name": "London System", "every_move_engine_best": False, "eval_at_end": -250,
          "costliest": {"cp_loss": 180, "san": "h3", "best": "c3"}}, "You came out of the London System worse."),
        ({"name": None, "every_move_engine_best": False, "eval_at_end": 20,
          "costliest": {"cp_loss": 70}}, "The opening gave a level position."),
    ])
    def test_the_verdict(self, opening, expected):
        assert opening_lines(opening)[0]["text"].startswith(expected)

    def test_the_costly_move_is_named_with_the_better_one(self):
        lines = opening_lines({"name": "London System", "eval_at_end": -250,
                               "costliest": {"cp_loss": 180, "san": "h3", "best": "c3"}})
        assert lines[1]["text"] == "h3 was the costly move. c3 was better."


class TestFinish:
    @pytest.mark.parametrize("finish, expected", [
        ({"outcome": "win", "termination": "resignation", "kept_winning": True},
         "From there you stayed well ahead, and they resigned."),
        ({"outcome": "win", "termination": "checkmate", "kept_winning": False},
         "In the end you finished with checkmate."),
        ({"outcome": "loss", "termination": "timeout", "was_winning_and_did_not_win": True},
         "You were winning at one point, but could not hold it. You ran out of time."),
        ({"outcome": "draw", "termination": "repetition"}, "The game was drawn by repetition."),
    ])
    def test_how_it_ended(self, finish, expected):
        assert finish_lines(finish)[0]["text"] == expected


class TestSelection:
    def test_a_missed_chance_answered_by_a_told_mistake_is_folded(self):
        missed = theirs("h4", 13, taken=False, your_answer="Nxg5", decisive=True)
        answer = mistake("Nxg5", 13, danger={"kind": "chance", "reply": "Qxd5"})
        chosen = choose_events(ledger([missed, answer]))
        assert [e["san"] for e in chosen] == ["Nxg5"]
        # The coach notes keep it.
        notes = plan_story(ledger([missed, answer]))["coach_notes"]
        assert [n["san"] for n in notes] == ["h4", "Nxg5"]

    def test_at_most_six_events(self):
        events = [mistake(f"a{i}", 13 + i) for i in range(10)]
        assert len(choose_events(ledger(events))) <= 6


# A move or a square such as "Ng5", "a6", "Rxf3+" or "O-O" is how a line is
# located, and the only place a digit may appear.
_MOVE = re.compile(r"\b(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)")


class TestNoNumbers:
    def test_no_digit_outside_a_move(self):
        events = [mistake(), theirs(), mistake("Nxg5", 13, danger={"kind": "mate_allowed", "reply": "Qh7"}),
                  {"kind": "missed_mate", "side": "you", "san": "Rxa3", "move_number": 30,
                   "evidence": {"best": "g5+"}, "tier": "blunder", "decisive": True}]
        plan = plan_story(ledger(events + [mistake("Qd2", 20)]))
        texts = [line["text"] for ch in plan["chapters"] for line in ch["lines"]]
        texts += [n["text"] for n in plan["coach_notes"]]
        texts += [plan["type"]["title"], (plan["lesson"] or {}).get("text", "")]
        for text in texts:
            assert not re.search(r"\d", _MOVE.sub("", text)), text
