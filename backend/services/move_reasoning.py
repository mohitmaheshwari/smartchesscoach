"""The reasoning framework: ask every question, then make each answer prove it
is about the CHOICE and not about the position.

Mohit 2026-10-21, having read the existing cards:

    "I need users to undresatnd why something is an inaccuracy"

and, on a card that was true and useless:

    "the other caption is more to just to dhwatever wihtout any learning,
     that's more of cramming part... we are teaching them the concepts"

What this adds that nothing here had
------------------------------------
Every explanation surface in this repo answers "what is true of this move".
None of them answers "what is true of this move AND NOT of the move the engine
wanted". Those are different questions, and only the second one is a reason.

    "Your opponent missed castling"      true, and true after every move
    "Nc3 blocks your own c-pawn"         true, and FALSE after O-O

That difference is the whole feature. A finding that survives after the better
move describes the position; the player would have met it either way, so it
cannot be why their move was worse. This module runs the differential test on
every answer and marks the ones that fail, so the caption layer can refuse
them instead of shipping another true irrelevance.

What this is NOT
----------------
It is not a new caption generator. It emits structured findings with slots;
prose stays in the caption layer, which is verified and voice-tested, and the
repo has a CI guard against teaching text appearing anywhere else.

It is not a new question bank either. The questions live in
`contrastive_reasoner` and are imported, because a concept whose answer is
computed in two places eventually gives two answers.

Budget
------
Board questions are free and always run. The engine is only asked for things
the board cannot answer, and only within a budget, because this runs behind a
button that already waits on Stockfish for seconds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import chess

from services.contrastive_reasoner import (
    CAUSE,
    EVIDENCE,
    SYMPTOM,
    q_abandoned_own_defender,
    q_blocked_a_plan,
    q_engine_undoes_it,
    q_returns_home,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"

# Differential outcomes. The names are the contract with the caption layer.
DISTINGUISHES = "distinguishes"        # true after the played move, not after the best
PRESENT_AFTER_BOTH = "present_after_both"   # true either way: a fact, not a reason
INHERENT = "inherent"                  # the question already compares the two moves
NOT_TESTED = "not_tested"              # no best move to compare against

# Ordinal, deliberately. A heuristic number presented as a probability is a
# number nobody can defend; Mohit's spec says the same in Part 7.
HIGH, MEDIUM, LOW = "high", "medium", "low"


@dataclass(frozen=True)
class MoveUnderStudy:
    """Everything a question may look at. Pure data, no engine, no database."""
    fen_before: str
    played_san: str
    best_san: Optional[str] = None
    pv_played: Sequence[str] = ()
    pv_best: Sequence[str] = ()
    cp_loss: Optional[int] = None
    mover_is_user: bool = True

    def board_before(self) -> chess.Board:
        return chess.Board(self.fen_before)

    def board_after(self, san: str) -> Optional[chess.Board]:
        board = self.board_before()
        try:
            board.push(board.parse_san(str(san)))
        except (ValueError, AssertionError, TypeError):
            return None
        return board


@dataclass(frozen=True)
class Finding:
    """One answer, with its proof status. Slots only -- never a sentence."""
    concept: str
    tier: int
    facts: Dict[str, Any]
    differential: str = NOT_TESTED
    confidence: str = LOW
    lines: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """May the caption layer speak this? Only if it is about the choice."""
        return self.differential in (DISTINGUISHES, INHERENT)


@dataclass
class Budget:
    """What the engine is allowed to spend. Counted, not hoped for."""
    max_probes: int = 2
    depth: int = 20
    spent: int = 0

    def take(self) -> bool:
        if self.spent >= self.max_probes:
            return False
        self.spent += 1
        return True


class Probe:
    """Engine access, budgeted. `engine` may be None -- then every probe is
    simply unavailable and the report says so rather than guessing."""

    def __init__(self, engine=None, budget: Optional[Budget] = None):
        self.engine = engine
        self.budget = budget or Budget()

    def evaluate(self, board: chess.Board, depth: Optional[int] = None
                 ) -> Optional[int]:
        """Centipawns from the side-to-move's view, or None if unaffordable."""
        if self.engine is None or not self.budget.take():
            return None
        try:
            score, _mate = self.engine.evaluate_position(
                board, depth=depth or self.budget.depth)
            return int(score)
        except Exception:
            logger.exception("probe: evaluate failed")
            return None

    def best_move(self, board: chess.Board, depth: Optional[int] = None
                  ) -> Optional[str]:
        if self.engine is None or not self.budget.take():
            return None
        try:
            move, _s, _m = self.engine.get_best_move(
                board, depth=depth or self.budget.depth)
            return board.san(move)
        except Exception:
            logger.exception("probe: best_move failed")
            return None


# ── the register ──────────────────────────────────────────────────────────
#
# `subject` names the fields that identify WHAT a finding is about, so the
# differential can ask "is the same thing true after the better move?" rather
# than comparing whole dicts, which differ on bookkeeping every time.
#
# `inherent` marks questions that already compare the played move with the
# better line. `blocked_a_plan` is the clearest: its entire claim is "the
# better line plays this and your move made it illegal", which cannot be true
# of the better move itself.

@dataclass(frozen=True)
class Question:
    concept: str
    tier: int
    ask: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]
    subject: Tuple[str, ...] = ()
    inherent: bool = False


# An EMPTY subject means "compare on existence": any answer at all after the
# better move counts as present-after-both. That is the right test for the
# retreat questions. Their claim is "the move loses time", and if the engine
# walks a piece home after the better move too, then shuffling is what this
# position does and not what this move cost. Marking them `inherent` was my
# first instinct and it was wrong: they assert a property, they just assert it
# about whichever piece moved.
REGISTRY: Tuple[Question, ...] = (
    Question("blocked_a_plan", CAUSE, q_blocked_a_plan,
             subject=("san",), inherent=True),
    Question("abandoned_own_defender", CAUSE, q_abandoned_own_defender,
             subject=("square",)),
    Question("engine_undoes_it", EVIDENCE, q_engine_undoes_it, subject=()),
    Question("returns_home", SYMPTOM, q_returns_home, subject=()),
)


def _ctx(move: MoveUnderStudy, played_san: str, pv_played: Sequence[str],
         best_san: Optional[str], pv_best: Sequence[str]
         ) -> Optional[Dict[str, Any]]:
    before = move.board_before()
    after = move.board_after(played_san)
    if after is None:
        return None
    return {
        "before": before,
        "after": after,
        "played_san": str(played_san),
        "best_san": str(best_san or ""),
        "pv_best": list(pv_best or ()),
        "pv_played": list(pv_played or ()),
        "cp_loss": move.cp_loss,
    }


def _subject_of(answer: Dict[str, Any], fields: Tuple[str, ...]):
    return tuple(answer.get(f) for f in fields)


def _run_differential(question: Question, answer: Dict[str, Any],
                      move: MoveUnderStudy) -> str:
    """Would this still be true if the player had found the better move?

    The counterfactual is the better move itself: re-ask the same question of
    the position after it, reading its own continuation. An answer about the
    same subject means the finding is a property of the position, which the
    player would have faced either way.
    """
    if question.inherent:
        return INHERENT
    if not move.best_san or move.best_san == move.played_san:
        return NOT_TESTED
    alt = _ctx(move, move.best_san, move.pv_best, move.played_san,
               move.pv_played)
    if alt is None:
        return NOT_TESTED
    try:
        other = question.ask(alt)
    except Exception:
        logger.exception("differential: %s raised", question.concept)
        return NOT_TESTED
    if not other:
        return DISTINGUISHES
    if _subject_of(other, question.subject) == _subject_of(
            answer, question.subject):
        return PRESENT_AFTER_BOTH
    return DISTINGUISHES


def _confidence(finding_tier: int, differential: str,
                stability: Optional[str]) -> str:
    """Ordinal, and it only ever goes down.

    A claim that does not distinguish the two moves is not a weak reason, it
    is not a reason, so it never rates above LOW however stable the engine is.
    """
    if differential == PRESENT_AFTER_BOTH:
        return LOW
    if stability == "unstable":
        return LOW
    if differential == NOT_TESTED:
        return LOW if finding_tier < CAUSE else MEDIUM
    if finding_tier >= CAUSE:
        return HIGH if stability == "stable" else MEDIUM
    return MEDIUM if stability == "stable" else LOW


def check_stability(move: MoveUnderStudy, probe: Probe) -> Optional[str]:
    """Does the engine still prefer the same move when asked harder?

    Part 4 of Mohit's spec asks for this and nothing here had it. An unstable
    preference is not a thing to teach a 1200 a lesson about, so it lowers
    confidence rather than being hidden.
    """
    if probe.engine is None or not move.best_san:
        return None
    deeper = probe.best_move(move.board_before())
    if deeper is None:
        return None
    return "stable" if deeper == move.best_san else "unstable"


@dataclass(frozen=True)
class Report:
    """What the caption layer consumes. Evidence, never prose."""
    schema_version: str
    played_san: str
    best_san: Optional[str]
    findings: List[Finding]
    rejected: List[Finding]
    stability: Optional[str]
    probes_spent: int

    @property
    def primary(self) -> Optional[Finding]:
        return self.findings[0] if self.findings else None

    @property
    def resolved(self) -> bool:
        return bool(self.findings)


def reason_about(move: MoveUnderStudy, probe: Optional[Probe] = None
                 ) -> Report:
    """Ask everything, keep what is about the choice, rank what survives.

    Ranking is tier first and confidence second, which is the order the cards
    already needed: `blocked_a_plan` (CAUSE) and `returns_home` (SYMPTOM) both
    answer Mohit's Nc3 position, and the shipped caption spoke the symptom
    because nothing told it that causes outrank consequences.
    """
    probe = probe or Probe()
    stability = check_stability(move, probe)

    kept: List[Finding] = []
    rejected: List[Finding] = []
    for question in REGISTRY:
        ctx = _ctx(move, move.played_san, move.pv_played,
                   move.best_san, move.pv_best)
        if ctx is None:
            continue
        try:
            answer = question.ask(ctx)
        except Exception:
            logger.exception("question %s raised", question.concept)
            continue
        if not answer:
            continue
        differential = _run_differential(question, answer, move)
        finding = Finding(
            concept=question.concept,
            tier=question.tier,
            facts={k: v for k, v in answer.items()
                   if k not in ("tier", "id")},
            differential=differential,
            confidence=_confidence(question.tier, differential, stability),
        )
        (kept if finding.usable else rejected).append(finding)

    order = {HIGH: 2, MEDIUM: 1, LOW: 0}
    kept.sort(key=lambda f: (-f.tier, -order[f.confidence]))
    return Report(
        schema_version=SCHEMA_VERSION,
        played_san=move.played_san,
        best_san=move.best_san,
        findings=kept,
        rejected=rejected,
        stability=stability,
        probes_spent=probe.budget.spent,
    )
