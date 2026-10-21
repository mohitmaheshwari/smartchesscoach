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
    q_left_it_loose,
    q_pushed_past_the_support,
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
    # Other good moves, best first, each with its own continuation:
    # [{move_san, eval_cp, line_san}] as stockfish_service.get_candidate_lines
    # returns them. Empty when nobody paid for an engine.
    #
    # The questions read `pv_best` -- the single best line -- and that is all
    # they could ever see. On Mohit's move-5 position the lesson sat in the
    # engine's THIRD choice: Nc6 (+30) against the best Nf6 (+58). A plan the
    # player gave up does not stop mattering because the engine marginally
    # preferred a different one.
    candidates: Sequence[Dict[str, Any]] = ()

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
    # Why this finding is not usable, or why its premise is weak. Empty when
    # it passed. Kept as text because it is read by a developer, never a
    # player -- the card gets slots, not sentences.
    size_problem: str = ""
    challenged: str = ""
    lines: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """May the caption layer speak this?

        Three conditions, which are steps 2, 6 and 7 of the hand procedure:
        it must be about the CHOICE and not the position, its size must match
        the engine's complaint, and its own premise must survive a look at the
        board.
        """
        return (self.differential in (DISTINGUISHES, INHERENT)
                and not self.size_problem
                and not self.challenged)


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

PIECE_CP = {"pawn": 100, "knight": 300, "bishop": 300,
            "rook": 500, "queen": 900, "king": 0}

# A positional or tempo lesson may not explain a catastrophe. Measured over
# 500 games, the cp_loss these findings sit on:
#
#   abandoned_own_defender  p75  400   max  1178    1.1% at 900cp or more
#   blocked_a_plan          p75  276   max 10315    4.5%
#   engine_undoes_it        p75  456   max 19950   16.7%
#   returns_home            p75  326   max 19950   13.3%
#
# The well-behaved body tops out around 1,200 and the rest is a separate
# population of mate scores at 8,500 and up. So the bar goes in that gap, and
# the same 900 falls out of the excess distribution measured independently in
# `contrastive_reasoner._beyond_this_man`. Twenty-four players were being
# mated while the card explained that their piece came back.
POSITIONAL_MAX_CP = 900

# How far below the best a candidate may be and still count as "a plan the
# player could have had". why_on_demand uses 50 for the same judgement and
# says why: it will not recommend a move materially worse than the engine's
# best just because it made a tidier story. Same number, same reason.
CANDIDATE_CLOSENESS_CP = 50

# How far a material claim may sit ABOVE the engine's own number before it is
# describing a different event.
#
# Unlike the positional bar there is no clean gap here, and that is worth
# saying rather than hiding. Measured over 500 games on 92 material findings,
# claim_cp minus cp_loss:
#
#   p25 -185   p50 -48   p75 +21   p90 +167   p95 +202   p99 +399
#   71.7% claim at or below the engine's number
#
# The tail is smooth, so this is a judgement at the 95th percentile, not a
# natural break. Some gap is legitimate: a claim measures material in the
# line while cp_loss prices the whole position, so a piece that falls with
# compensation reads high by design. 200 keeps 95% and cuts the six cards
# that claim a rook or a queen on a move the engine priced near a pawn.
CLAIM_SLACK_CP = 200


@dataclass(frozen=True)
class Question:
    concept: str
    tier: int
    ask: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]
    subject: Tuple[str, ...] = ()
    inherent: bool = False
    # How much material this answer accounts for, or None when the lesson is
    # positional. Step 7 of the hand-written procedure -- "does my answer match
    # the engine's number?" -- which until now lived inside ONE question, so
    # every new question had to remember it and would eventually not.
    claim_cp: Optional[Callable[[Dict[str, Any]], Optional[int]]] = None
    # Step 6 -- attack the story already on the card. Returns a reason the
    # claim's own premise is weak, or None when it holds.
    challenge: Optional[Callable[[Dict[str, Any], "MoveUnderStudy"],
                                 Optional[str]]] = None


# An EMPTY subject means "compare on existence": any answer at all after the
# better move counts as present-after-both. That is the right test for the
# retreat questions. Their claim is "the move loses time", and if the engine
# walks a piece home after the better move too, then shuffling is what this
# position does and not what this move cost. Marking them `inherent` was my
# first instinct and it was wrong: they assert a property, they just assert it
# about whichever piece moved.
def _lost_man_cp(answer: Dict[str, Any]) -> Optional[int]:
    return PIECE_CP.get(str(answer.get("lost") or ""))


def _retreat_was_voluntary(answer: Dict[str, Any],
                           move: "MoveUnderStudy") -> Optional[str]:
    """Step 6, on the one claim we actually make: "the move loses time".

    Mohit, on the Nc3 card: "why would nC3 comes back to b1, there is no
    attack on nc3 in coming future, it's safe there". He was right, and the
    board agrees -- nothing ever attacks c3, so the knight is regrouping via
    d2, not being chased. "Loses time" reads a deliberate manoeuvre backwards.

    So: walk the played line and ask whether the piece is ever attacked where
    it stands. If it never is, the retreat is a choice and the premise of the
    claim does not hold.
    """
    board = move.board_before()
    try:
        played = board.parse_san(str(move.played_san))
    except (ValueError, AssertionError, TypeError):
        return None
    walk = board.copy()
    walk.push(played)
    here = played.to_square
    us = board.turn
    for san in list(move.pv_played or ())[:8]:
        if walk.attackers(not us, here):
            return None                      # it really was chased
        try:
            mv = walk.parse_san(str(san))
        except (ValueError, AssertionError):
            return None
        if mv.from_square == here:
            here = mv.to_square
        walk.push(mv)
    if walk.attackers(not us, here):
        return None
    return "nothing ever attacks the piece, so the retreat is a choice"


REGISTRY: Tuple[Question, ...] = (
    Question("blocked_a_plan", CAUSE, q_blocked_a_plan,
             subject=("san",), inherent=True),
    Question("abandoned_own_defender", CAUSE, q_abandoned_own_defender,
             subject=("square",), claim_cp=_lost_man_cp),
    # Its claim is about a square that can never be reached again, which is a
    # fact about THIS move: after the better move the pawn is still on its
    # start square and the support is still available. So it is inherent in
    # the same sense blocked_a_plan is.
    Question("pushed_past_the_support", CAUSE, q_pushed_past_the_support,
             subject=("weak_pawn",)),
    # Inherent: its third clause IS the comparison -- it only answers when the
    # better move cures what the played move leaves. It cannot be true of the
    # better move by construction.
    Question("left_it_loose", CAUSE, q_left_it_loose,
             subject=("square",), inherent=True,
             claim_cp=lambda a: PIECE_CP.get(str(a.get("loose") or ""))),
    Question("engine_undoes_it", EVIDENCE, q_engine_undoes_it, subject=(),
             challenge=_retreat_was_voluntary),
    Question("returns_home", SYMPTOM, q_returns_home, subject=(),
             challenge=_retreat_was_voluntary),
)


def _size_is_consistent(question: Question, answer: Dict[str, Any],
                        cp_loss: Optional[int]) -> Optional[str]:
    """Steps 1 and 7, as a framework rule rather than a habit.

    The size of the explanation has to match the size of the engine's
    complaint. Returns the reason it does not, or None when it does.

    This is the check that caught "dxe5 wins your knight" on a move the engine
    priced at one pawn. It lived inside a single question, so it protected one
    concept and nothing else.
    """
    if cp_loss is None:
        return None
    cp = abs(int(cp_loss))
    claim = question.claim_cp(answer) if question.claim_cp else None
    if claim is None:
        # A positional or tempo lesson. It may be right about the board and
        # still be the wrong thing to say to someone losing a queen.
        if cp >= POSITIONAL_MAX_CP:
            return (f"a positional lesson cannot explain {cp}cp; "
                    "something categorical happened")
        return None
    if claim > cp + CLAIM_SLACK_CP:
        return f"claims {claim}cp where the engine priced it at {cp}cp"
    if cp > claim + POSITIONAL_MAX_CP:
        return f"explains {claim}cp of a {cp}cp loss; the rest is unaccounted"
    return None


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


def _ask_against_candidates(question: Question, move: MoveUnderStudy
                            ) -> Optional[Dict[str, Any]]:
    """Re-ask using each strong alternative as the better move.

    The engine's top choice is one opinion about a position that may have
    several good plans. On Mohit's move-5 card the lesson was in the engine's
    THIRD line and the question, reading only the best one, said nothing.

    Only moves close to the best are used, so this widens the search for a
    lesson without inventing a better move the engine does not endorse. The
    answer is still checked by the differential and the size rule exactly as
    the primary one is -- this changes which lines are READ, never what counts
    as proof.
    """
    if not move.candidates:
        return None
    best_cp = None
    for cand in move.candidates:
        cp = cand.get("eval_cp")
        if cp is None:
            continue
        if best_cp is None:
            best_cp = int(cp)
        if int(cp) < best_cp - CANDIDATE_CLOSENESS_CP:
            break
        san = str(cand.get("move_san") or "")
        if not san or san == move.played_san or san == move.best_san:
            continue
        line = [str(x) for x in (cand.get("line_san") or [])]
        # get_candidate_lines leads with the candidate itself; the questions
        # expect the continuation AFTER it, the way pv_after_best is stored.
        if line and line[0] == san:
            line = line[1:]
        ctx = _ctx(move, move.played_san, move.pv_played, san, line)
        if ctx is None:
            continue
        try:
            answer = question.ask(ctx)
        except Exception:
            logger.exception("candidate ask: %s raised", question.concept)
            continue
        if answer:
            answer["from_candidate"] = san
            return answer
    return None


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
            answer = _ask_against_candidates(question, move)
        if not answer:
            continue
        differential = _run_differential(question, answer, move)
        size_problem = _size_is_consistent(question, answer, move.cp_loss) or ""
        challenged = ""
        if question.challenge is not None:
            try:
                challenged = question.challenge(answer, move) or ""
            except Exception:
                logger.exception("challenge: %s raised", question.concept)
        finding = Finding(
            concept=question.concept,
            tier=question.tier,
            facts={k: v for k, v in answer.items()
                   if k not in ("tier", "id")},
            differential=differential,
            confidence=_confidence(question.tier, differential, stability),
            size_problem=size_problem,
            challenged=challenged,
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
