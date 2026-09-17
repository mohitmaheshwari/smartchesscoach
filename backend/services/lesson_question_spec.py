"""What we print, and what we accept — held together in one place.

A training card used to ask "Which move keeps every piece safe?" and then
grade the engine's single best move. Both halves were defensible on their own;
together they made a lesson that could not be passed by answering the question
it asked. Measured on five positions served to one account, 9/8/5/19/12 of the
legal moves kept every piece safe and exactly one was accepted each time.

So the question text and the grading rule are not allowed to live apart any
more. They are one record here, and the surfaces read it rather than each
keeping a copy -- the adapter had one, the pattern-training page had another,
and they had already drifted apart.

Two families, because two different things were wrong:

  any_safe     The question was right and the grader was wrong. Piece safety
               is a habit, not a puzzle: plenty of moves satisfy it and the
               lesson is whether you avoided the ones that do not.
  single_best  The grader was right and the question was wrong. There really
               is one tactic; asking "which of your pieces has no defender?"
               poses something the board cannot be marked against.

`task_line` exists so the card never has to be coy about which family it is
in. It replaced a sentence that counted the unsafe moves ("13 of 38 leave a
piece where it can be taken"), which reads as an invitation to pick any of the
other 25 and was then followed by rejecting 24 of them.

The two reason options per category are both heuristics a 600-1500 player
actually holds. The pair they replaced was "It leaves my pieces protected" vs
"It looks active, even if a piece can be taken" -- nobody picks the second, so
the question measured nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

ANY_SAFE = "any_safe"
SINGLE_BEST = "single_best"

MORE_THAN_ONE = "More than one move works here."
EXACTLY_ONE = "One move is right here."


@dataclass(frozen=True)
class ReasonOption:
    """One answer to the reason question, with the coaching it earns.

    The correction lives here rather than in a lookup keyed by reason id
    somewhere else. It used to: `teaching_engine._belief_lead` held text for
    `keeps_piece_safe` and `looks_active`, and the moment the options changed
    the corrections would have been orphaned silently -- the follow-up would
    simply come back empty and nothing would have failed.
    """

    id: str
    label: str
    # Named back to the player when the move was wrong: what they believed.
    belief_lead: str = ""
    # Filed when the move was right but the stated reason was not. Empty on
    # the expected option, which by definition needs no correcting.
    misconception_id: str = ""
    correction: str = ""


@dataclass(frozen=True)
class QuestionSpec:
    category: str
    question: str
    accepts: str
    task_line: str
    reason_prompt: str
    # The first is the expected answer; the order shown to the player is
    # shuffled per position elsewhere, so this order never leaks.
    reason_options: Tuple[ReasonOption, ...]
    # Wording for a surface that accepts only one move. An any_safe category
    # needs it because the same concept is trained in two places on two
    # graders: the lesson workspace marks any safe move, while
    # /training/prescribed marks the stored best move. Printing "more than one
    # move works" on the second one would be the same lie in a new place.
    best_move_question: str = ""

    @property
    def expected_reason(self) -> str:
        return self.reason_options[0].id

    def reason(self, reason_id: object) -> Optional[ReasonOption]:
        key = str(reason_id or "")
        for option in self.reason_options:
            if option.id == key:
                return option
        return None

    def accepts_many(self) -> bool:
        return self.accepts == ANY_SAFE

    def question_for(self, accepts: str) -> str:
        """The wording honest for the grader that will mark the answer."""
        if accepts == SINGLE_BEST and self.best_move_question:
            return self.best_move_question
        return self.question

    def task_line_for(self, accepts: str) -> str:
        return EXACTLY_ONE if accepts == SINGLE_BEST else self.task_line


_SPECS: Tuple[QuestionSpec, ...] = (
    QuestionSpec(
        category="piece_safety",
        question="Play a move that leaves nothing of yours hanging.",
        accepts=ANY_SAFE,
        task_line=(
            MORE_THAN_ONE
            + " Any move that lands where it cannot simply be taken counts."
        ),
        reason_prompt="What did you check before choosing the move?",
        reason_options=(
            ReasonOption(
                id="checked_landing_square",
                label="I checked what could capture the piece once it landed.",
                belief_lead=(
                    "You checked the square it landed on, so the habit is "
                    "right and the count is what slipped."
                ),
            ),
            # A real and popular rule that quietly fails: the attacked piece
            # is often defended, and the one actually hanging is elsewhere.
            ReasonOption(
                id="moved_the_attacked_piece",
                label="I moved the piece that was already under attack.",
                belief_lead=(
                    "You went to the piece being attacked, which is the "
                    "instinct to adjust here."
                ),
                misconception_id="attacked_is_not_the_same_as_hanging",
                correction=(
                    "A piece under attack is often defended and perfectly "
                    "safe. Look for the one with nothing behind it."
                ),
            ),
        ),
        best_move_question=(
            "Something of yours can be taken here. Find the best move."
        ),
    ),
    QuestionSpec(
        category="calculation_depth",
        question=(
            "One line here runs further than it looks. Find the move that "
            "still holds up two moves deep."
        ),
        accepts=SINGLE_BEST,
        task_line=EXACTLY_ONE,
        reason_prompt="How did you pick it?",
        reason_options=(
            ReasonOption(
                id="followed_the_line",
                label="I followed the forcing line to the end before choosing.",
                belief_lead=(
                    "You did follow the line, so the question is where it "
                    "stopped."
                ),
            ),
            ReasonOption(
                id="best_right_now",
                label="I picked the move that looked strongest on this move.",
                belief_lead=(
                    "You judged it on this move alone, which is the habit "
                    "this position punishes."
                ),
                misconception_id="stops_calculating_too_early",
                correction=(
                    "Play the opponent's best reply in your head before you "
                    "decide. The move that looks strongest often is not once "
                    "they answer."
                ),
            ),
        ),
    ),
    QuestionSpec(
        category="missed_tactic",
        question="There is a tactic in this position. Find it.",
        accepts=SINGLE_BEST,
        task_line=EXACTLY_ONE,
        reason_prompt="How did you pick it?",
        reason_options=(
            ReasonOption(
                id="looked_for_forcing",
                label="I looked at every capture and check first.",
                belief_lead=(
                    "You did look at the forcing moves, so one of them was "
                    "passed over rather than missed."
                ),
            ),
            ReasonOption(
                id="improved_worst_piece",
                label="I improved the piece that was doing the least.",
                belief_lead=(
                    "Improving your worst piece is a good rule and the wrong "
                    "one for this position."
                ),
                misconception_id="quiet_move_when_a_tactic_exists",
                correction=(
                    "When something is loose or a king is exposed, check "
                    "every capture and check before you improve a piece."
                ),
            ),
        ),
    ),
    QuestionSpec(
        category="tactical_oversight",
        question=(
            "There is a tactic here that is easy to walk straight past. "
            "Find it."
        ),
        accepts=SINGLE_BEST,
        task_line=EXACTLY_ONE,
        reason_prompt="How did you pick it?",
        reason_options=(
            ReasonOption(
                id="checked_opponent_loose",
                label="I looked for what the opponent had left loose.",
                belief_lead=(
                    "You were looking in the right place, so it is what "
                    "counts as loose that needs widening."
                ),
            ),
            ReasonOption(
                id="finished_my_plan",
                label="I carried on with the plan I already had.",
                belief_lead=(
                    "You stayed with your plan, which is why the chance went "
                    "past unnoticed."
                ),
                misconception_id="plan_blocks_the_scan",
                correction=(
                    "A plan is worth keeping and worth interrupting. Before "
                    "each move, look once at what the opponent just left "
                    "undefended."
                ),
            ),
        ),
    ),
    QuestionSpec(
        category="king_safety",
        question=(
            "Your king is the problem in this position. Find the move that "
            "fixes it."
        ),
        accepts=SINGLE_BEST,
        task_line=EXACTLY_ONE,
        reason_prompt="What did you look at first?",
        reason_options=(
            ReasonOption(
                id="counted_attackers",
                label="I counted what is aimed at my king right now.",
                belief_lead=(
                    "You counted the attackers, so it is one of the lines "
                    "into the king that went unseen."
                ),
            ),
            ReasonOption(
                id="attack_first",
                label="I went for my own attack before they got to me.",
                belief_lead=(
                    "You backed your own attack to arrive first, and that is "
                    "the race this position loses."
                ),
                misconception_id="counter_attacks_instead_of_defending",
                correction=(
                    "Count both sides before racing. If more pieces point at "
                    "your king than at theirs, spend the move on your king."
                ),
            ),
        ),
    ),
    QuestionSpec(
        category="opening_knowledge",
        question="Find the move that keeps your opening on track.",
        accepts=SINGLE_BEST,
        task_line=EXACTLY_ONE,
        reason_prompt="How did you pick it?",
        reason_options=(
            ReasonOption(
                id="develop_and_centre",
                label="I brought a new piece out towards the centre.",
                belief_lead=(
                    "Developing towards the centre is the right aim, so it "
                    "is the piece or the square that needs changing."
                ),
            ),
            ReasonOption(
                id="took_the_pawn",
                label="I took the pawn that was on offer.",
                belief_lead=(
                    "You took what was offered, which is what the opening "
                    "was counting on."
                ),
                misconception_id="takes_the_opening_pawn",
                correction=(
                    "A pawn offered this early is usually bought with your "
                    "development. Count how many moves it costs before you "
                    "take it."
                ),
            ),
        ),
    ),
    QuestionSpec(
        category="endgame_technique",
        question="This endgame turns on one accurate move. Find it.",
        accepts=SINGLE_BEST,
        task_line=EXACTLY_ONE,
        reason_prompt="What did you work out first?",
        reason_options=(
            ReasonOption(
                id="king_race_first",
                label="I worked out where the kings end up first.",
                belief_lead=(
                    "Starting with the kings is right, so it is the count "
                    "that came out wrong."
                ),
            ),
            ReasonOption(
                id="push_the_runner",
                label="I pushed my most advanced pawn.",
                belief_lead=(
                    "You pushed the pawn nearest the end, which is the habit "
                    "this endgame punishes."
                ),
                misconception_id="pushes_before_placing_the_king",
                correction=(
                    "In an endgame the king moves first and the pawn "
                    "follows. Place it before you push."
                ),
            ),
        ),
    ),
)

BY_CATEGORY: Mapping[str, QuestionSpec] = {
    spec.category: spec for spec in _SPECS
}

# Other names the same idea travels under. `community_training_positions`
# stores `pattern_type` from a different vocabulary than `community_puzzles`
# stores `issue_type`, and the concept lesson addresses piece safety as
# `undefended_piece`. Resolving them here stops a caller silently falling
# through to a generic question because it held the other spelling.
_ALIASES: Mapping[str, str] = {
    "undefended_piece": "piece_safety",
    "piece_safety_simple_hang": "piece_safety",
    "hanging_piece": "piece_safety",
    "poor_piece_safety": "piece_safety",
    "missed_threat": "king_safety",
    "opponent_threats": "king_safety",
    "tactical": "missed_tactic",
    "tactical_miss": "missed_tactic",
    "pin": "missed_tactic",
}

# Used where a category is genuinely unknown. It promises nothing about how
# many moves are right, because at that point we do not know.
FALLBACK = QuestionSpec(
    category="",
    question="Find the move this position asks for.",
    accepts=SINGLE_BEST,
    task_line=EXACTLY_ONE,
    reason_prompt="How did you pick it?",
    reason_options=(
        ReasonOption(
            id="looked_for_forcing",
            label="I looked at every capture and check first.",
            belief_lead=(
                "You did look at the forcing moves, so one of them was "
                "passed over rather than missed."
            ),
        ),
        ReasonOption(
            id="best_right_now",
            label="I picked the move that looked strongest on this move.",
            belief_lead=(
                "You judged it on this move alone, which is the habit this "
                "position punishes."
            ),
            misconception_id="stops_calculating_too_early",
            correction=(
                "Play the opponent's best reply in your head before you "
                "decide."
            ),
        ),
    ),
)


def canonical_category(value: object) -> str:
    key = str(value or "").strip().lower()
    return _ALIASES.get(key, key)


def get_spec(category: object) -> Optional[QuestionSpec]:
    """The spec for a category, or None if we have never described it."""
    return BY_CATEGORY.get(canonical_category(category))


def spec_or_fallback(category: object) -> QuestionSpec:
    return get_spec(category) or FALLBACK


def accepts_many_moves(category: object) -> bool:
    """Whether the printed question promises that several moves are right.

    The grader asks this, so a card can never advertise one rule and then be
    marked by another.
    """
    spec = get_spec(category)
    return bool(spec and spec.accepts_many())


def reason_belief_lead(category: object, reason_id: object) -> str:
    """What the player believed, in their words, for a wrong move.

    Returns "" when we have nothing worth naming, so the board fact stands
    alone rather than being padded.
    """
    spec = get_spec(category)
    option = spec.reason(reason_id) if spec else None
    return option.belief_lead if option else ""


def reason_correction(
    category: object,
    reason_id: object,
) -> Tuple[Optional[str], Optional[str]]:
    """Filed when the move was right but the stated reason was not."""
    spec = get_spec(category)
    option = spec.reason(reason_id) if spec else None
    if option is None or not option.correction:
        return (None, None)
    return (option.misconception_id or None, option.correction)


def describe() -> Dict[str, Dict[str, object]]:
    """Flat view, for tests and the admin surfaces."""
    return {
        spec.category: {
            "question": spec.question,
            "accepts": spec.accepts,
            "task_line": spec.task_line,
            "reason_prompt": spec.reason_prompt,
            "expected_reason": spec.expected_reason,
            "reason_options": [
                {"id": option.id, "label": option.label}
                for option in spec.reason_options
            ],
        }
        for spec in _SPECS
    }
