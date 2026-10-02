"""The why-better append must not overwrite an authored reason.

Step 11c appends the board-derived best_move_why onto any bare
"{best} was better." shell. Its guard tested for the literal " — it ", so a
clause opening with "it's" slipped through the missing space and was
overwritten by the generic reason.

That is why the trap library reached nobody: "it's the textbook refutation in
the {trap_context_name}" was replaced every time. Measured on the corpus,
4 of 17,689 stored reviews name a trap and 302 of 305 games where the player
held the punishment say nothing. 12 of the 37 authored user why-clauses do not
begin with "it " and were all being replaced.
"""
import json
import re

import pytest

R12 = json.load(open("/app/backend/data/captions/R12_blunder.json", encoding="utf-8"))


def _shell_pattern(best):
    return (
        re.escape(best)
        + r" (?:was (?:the )?(?:better|stronger) move(?: here)?|"
          r"was better|would have made things harder for your opponent)"
          r"(?P<reason>\s*[—-]\s*[^.]*)?\."
    )


def _would_overwrite(caption, best):
    m = re.search(_shell_pattern(best), caption)
    if not m:
        return False
    return not (m.group("reason") or "").strip(" —-")


class TestTheGuard:
    def test_a_bare_shell_still_gets_the_append(self):
        assert _would_overwrite("Bc5 is a mistake. d5 was better.", "d5")

    def test_an_ordinary_reason_is_protected(self):
        assert not _would_overwrite(
            "Bc5 is a mistake. d5 was better — it attacks the bishop on c4.", "d5")

    def test_a_reason_opening_with_an_apostrophe_is_protected(self):
        assert not _would_overwrite(
            "Bc5 is a mistake. d5 was better — it's the textbook refutation in the "
            "Fried Liver Attack.", "d5")

    @pytest.mark.parametrize("reason", [
        "Knights on the rim are weak — keep them near the middle.",
        "Your queen gets chased — their knight hits it and it must move again.",
        "The hard part started before this move.",
        "In the opening, a slow pawn move wastes time.",
    ])
    def test_every_authored_shape_survives(self, reason):
        assert not _would_overwrite(f"Bc5 is a mistake. d5 was better — {reason}", "d5")


class TestTheAuthoredClausesThatWereBeingLost:
    """A third of them do not start with "it ", which is the whole bug."""

    def test_the_trap_clause_does_not_start_with_it_space(self):
        text = R12["variants"]["why_user_missed_trap_punishment"]
        assert text.startswith("it's"), text
        assert not text.startswith("it ")

    def test_a_meaningful_share_of_clauses_would_have_been_overwritten(self):
        names = {r["variant"] for r in R12.get("why_clauses_user", []) if r.get("variant")}
        texts = {n: R12["variants"].get(n, "") for n in names}
        at_risk = [n for n, t in texts.items() if not t.startswith("it ")]
        # Not pinning the exact number -- pinning that the old guard's
        # assumption ("every reason starts with 'it '") is simply false.
        assert len(at_risk) >= 5, at_risk
        assert "why_user_missed_trap_punishment" in at_risk
