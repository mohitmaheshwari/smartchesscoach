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
    _material_swing,
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


# How much material the line may cost us BEYOND the man we name, before the
# man is no longer the story. One pawn, and for once the threshold is a break
# in the data rather than a percentile -- measured on the whole corpus, in
# pawns, for both questions that name a man:
#
#   left_it_loose  n=5447   <=-3 9.9%  -1 8.9%  +0 62.0%  +1 7.5%  +3 2.9%
#   abandoned      n=2543   <=-3 1.3%  -1 3.7%  +0 82.9%  +1 6.6%  +2 4.2%
#
# A spike at exactly zero against a tenth of it at +1 -- 8.3x and 12.6x --
# in two questions derived independently. The claim either accounts for
# precisely the material that falls or it does not, and the cliff sitting in
# the same place twice is why this is a property of the claim rather than of
# the question it came from.
#
# The median loss/claim ratio also climbs monotonically with extra (1.4x at
# 0, 1.6x at +1, 2.0x at +2, 3.0x at +5), which is why the RATIO looked like
# the problem at first. It is a noisy proxy for this, and a dangerous one: it
# scored abandoned_own_defender at 0% while 275 of its findings were wrong.
NAMED_MAN_EXTRA_MAX_PAWNS = 1


def _a_detector_already_owns_this(move: "MoveUnderStudy") -> Optional[str]:
    """Decline the card when a hard, verified material fact explains it.

    Mohit, 2026-10-22, after opening one card on the admin page:

        "framework should only be called when detectors don't work... if user
         asked even for this move which is shown on caption, why explain
         button the framework which is our backbone here might just tell
         something fucking stupid and complete product goes down in eyes of
         the user"

    The card was white playing Qg3 with Qxg7 taking a free pawn. The shipped
    caption said exactly that. The framework said `returns_home` -- a symptom
    about a piece going back -- because nothing better survived and nothing
    told it to stay out of the way.

    Measured over 177,198 flagged cards: on 11,633 the better move takes an
    UNDEFENDED enemy man we did not take. The framework is rightly silent on
    10,358 of them, and on 1,275 it answers anyway:

        left_it_loose 433 · blocked_a_plan 380 · returns_home 218
        abandoned_own_defender 157 · engine_undoes_it 71

    What was left on the board in that bucket: 7,177 pawns, 1,518 bishops,
    1,469 knights, 970 rooks and 499 queens. left_it_loose is the worst of
    them, because it says OUR man was loose when the story is THEIR man was
    free -- mirror images, and confusing them is worse than silence.

    So this is a precedence rule, and the repo already has the order: engine-
    hard facts outrank positional ones. The framework's questions are
    positional and behavioural almost without exception, so where a hard
    material fact answers the card, the framework declines rather than ranks.
    Declines, not "scores lower": it cannot see what the detector said, so it
    is in no position to compare.

    Returns the reason to stand down, or None to proceed.
    """
    best = str(move.best_san or "")
    if not best:
        return None
    board = move.board_before()
    try:
        mv = board.parse_san(best)
    except (ValueError, AssertionError, TypeError, KeyError):
        return None
    if not board.is_capture(mv) or board.is_en_passant(mv):
        return None
    victim = board.piece_at(mv.to_square)
    if victim is None or victim.color == board.turn:
        return None
    if board.attackers(not board.turn, mv.to_square):
        return None               # defended: a trade or a tactic, not "free"
    try:
        played = board.parse_san(str(move.played_san))
    except (ValueError, AssertionError, TypeError, KeyError):
        return None
    if played.to_square == mv.to_square:
        return None               # we did take it, just differently
    return (f"{best} takes an undefended {chess.piece_name(victim.piece_type)}"
            f" on {chess.square_name(mv.to_square)}. A free capture is a hard"
            f" material fact and the detectors own it.")


def _the_named_man_is_the_story(question: "Question", answer: Dict[str, Any],
                               move: "MoveUnderStudy") -> Optional[str]:
    """A question that says WHICH man you lost must name the man who falls.

    A framework rule, not a question's own clause, and the second time this
    file has had to learn the difference. _size_is_consistent below says it
    plainly: that check "lived inside a single question, so it protected one
    concept and nothing else". This one shipped the same way -- as
    left_it_loose's `challenge` -- and the measurement said why that was
    wrong within the hour.

    The ratio metric that FOUND the defect scored every other question at
    0%, so they looked clean. They were not: the same metric saw only 385 of
    left_it_loose's own 1,550 defects. Re-measured by walking the line, with
    `extra` = material falling beyond the man named, in pawns:

        left_it_loose           n=5447   +0 62.0%   +1  7.5%   extra>=1 16.7%
        abandoned_own_defender  n=2543   +0 82.9%   +1  6.6%   extra>=1 10.8%

    275 defects in abandoned_own_defender, from a question the ratio called
    spotless. The cliff also lands in the SAME place in both -- 8.3x and
    12.6x at +1 -- so one pawn is a property of the claim, not of the one
    question it was derived from.

    Keyed on claim_cp rather than a fact name: claim_cp already means "this
    answer accounts for this much material", and it returns the value, so
    the rule never needs to know which key holds the man. Any future
    material question inherits it with nothing to remember.
    pushed_past_the_support is the control for that choice -- it names a WEAK
    pawn, not a lost one, its mode sits at -1 rather than 0, and having no
    claim_cp it is correctly left alone.
    """
    if question.claim_cp is None:
        return None
    try:
        named = question.claim_cp(answer)
    except Exception:
        return None
    if not named:
        return None
    board = move.board_before()
    try:
        after = board.copy()
        after.push(board.parse_san(str(move.played_san)))
    except (ValueError, AssertionError, TypeError):
        return None
    swing = _material_swing(after, list(move.pv_played or ()), board.turn)
    if swing is None:
        return None                      # line will not replay; say nothing
    extra = -swing - (named // 100)
    if extra >= NAMED_MAN_EXTRA_MAX_PAWNS:
        return (f"{extra} more pawns of material fall in this line, so this "
                f"man is not the story")
    return None


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


# The eight steps, in the order they are taken, with the name of the thing
# that performs each one. The admin page reads THIS rather than holding its
# own copy, so a step cannot appear on a screen without something running it.
# Where a step has no mechanism of its own yet, `by` is empty and the trace
# says so instead of implying work that does not happen.
THE_EIGHT_STEPS: Tuple[Tuple[int, str, str], ...] = (
    (1, "expect a size", "_size_is_consistent"),
    (2, "two futures, and the reason is the difference", "_run_differential"),
    (3, "what we get to do in the better line", "q_blocked_a_plan"),
    (4, "legal before, illegal after", "q_blocked_a_plan"),
    (5, "is my own move in the way", "in_the_way"),
    (6, "attack the story before shipping it", "challenge"),
    (7, "does the answer match the engine's number", "_size_is_consistent"),
    (8, "one sentence a 1200 would use", ""),
)


@dataclass(frozen=True)
class AskedQuestion:
    """What became of one question, for the admin trace.

    Every question the engine asks, including the ones with nothing to say and
    the ones whose answers were thrown out. A card shows the sentence that
    won; this shows the six that did not and why, which is the part no surface
    in this repo has ever displayed.
    """
    concept: str
    tier: int
    answered: bool
    verdict: str                      # kept | dropped | no answer
    subject: str = ""                 # the square or man it spoke about
    reason: str = ""                  # why it was dropped, in the rule's words
    facts: Dict[str, Any] = field(default_factory=dict)


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
    # The engine's own account of its work. Carried on the report rather than
    # recomputed by a reader, because a second implementation of "what did it
    # do" is a second answer waiting to disagree with the first.
    asked: List[AskedQuestion] = field(default_factory=list)
    # Why the framework stood down, when it did. Empty means it ran. This is
    # NOT the same as having nothing to say: "a detector owns this" and "I
    # looked and found nothing" are different facts and a reader needs both.
    declined: str = ""

    @property
    def primary(self) -> Optional[Finding]:
        return self.findings[0] if self.findings else None

    @property
    def resolved(self) -> bool:
        return bool(self.findings)

    def steps(self) -> List[Dict[str, Any]]:
        """The eight steps with what actually happened at each, derived from
        this report alone -- never from a list the page keeps."""
        prim = self.primary
        all_f = self.findings + self.rejected
        if self.declined:
            return [{"step": num, "name": name, "by": by, "ran": False,
                     "note": "stood down: " + self.declined}
                    for num, name, by in THE_EIGHT_STEPS]
        size = [f for f in all_f if f.size_problem]
        chal = [f for f in all_f if f.challenged]
        plan = [f for f in all_f if f.concept == "blocked_a_plan"]
        out: List[Dict[str, Any]] = []
        for num, name, by in THE_EIGHT_STEPS:
            note, ran = "", False
            if num == 1:
                ran = True
                note = (f"refused {len(size)} answer(s) as the wrong size"
                        if size else "no answer was the wrong size")
            elif num == 2:
                ran = bool(all_f)
                note = (f"compared {len(all_f)} answer(s) after {self.played_san}"
                        f" against after {self.best_san or '(no better move)'}")
            elif num in (3, 4):
                ran = bool(plan)
                note = ("a plan question answered" if plan
                        else "no plan question answered")
            elif num == 5:
                ran = any(f.facts.get("in_the_way") for f in all_f)
                note = "our own move blocked the square" if ran else "not reached"
            elif num == 6:
                ran = True
                note = (f"broke {len(chal)} answer(s) on their own premise"
                        if chal else "every premise held")
            elif num == 7:
                ran = any(f.facts for f in all_f)
                note = (f"{len(size)} claim(s) did not match the number"
                        if size else "claims matched the engine's number")
            elif num == 8:
                ran = bool(prim)
                note = ("handed to the caption layer" if prim
                        else "nothing survived to say")
            out.append({"step": num, "name": name, "by": by,
                        "ran": ran, "note": note})
        return out


def reason_about(move: MoveUnderStudy, probe: Optional[Probe] = None
                 ) -> Report:
    """Ask everything, keep what is about the choice, rank what survives.

    Ranking is tier first and confidence second, which is the order the cards
    already needed: `blocked_a_plan` (CAUSE) and `returns_home` (SYMPTOM) both
    answer Mohit's Nc3 position, and the shipped caption spoke the symptom
    because nothing told it that causes outrank consequences.
    """
    probe = probe or Probe()

    # Precedence before anything else: where a hard material fact explains the
    # card, the detectors own it and this framework keeps out of the way.
    stand_down = _a_detector_already_owns_this(move)
    if stand_down:
        return Report(
            schema_version=SCHEMA_VERSION, played_san=move.played_san,
            best_san=move.best_san, findings=[], rejected=[], stability=None,
            probes_spent=probe.budget.spent, asked=[], declined=stand_down)

    stability = check_stability(move, probe)

    kept: List[Finding] = []
    rejected: List[Finding] = []
    asked: List[AskedQuestion] = []

    def _note_silence(q: Question) -> None:
        asked.append(AskedQuestion(concept=q.concept, tier=q.tier,
                                   answered=False, verdict="no answer"))

    for question in REGISTRY:
        ctx = _ctx(move, move.played_san, move.pv_played,
                   move.best_san, move.pv_best)
        if ctx is None:
            _note_silence(question)
            continue
        try:
            answer = question.ask(ctx)
        except Exception:
            logger.exception("question %s raised", question.concept)
            asked.append(AskedQuestion(
                concept=question.concept, tier=question.tier, answered=False,
                verdict="dropped", reason="the question raised an error"))
            continue
        if not answer:
            answer = _ask_against_candidates(question, move)
        if not answer:
            _note_silence(question)
            continue
        differential = _run_differential(question, answer, move)
        size_problem = _size_is_consistent(question, answer, move.cp_loss) or ""
        # The framework's own challenge first -- it applies to every question
        # that names material, so no author has to remember it -- then the
        # question's, which knows things only it can know.
        challenged = _the_named_man_is_the_story(question, answer, move) or ""
        if not challenged and question.challenge is not None:
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
        # The reason a reader most wants is the reason it was THROWN OUT, in
        # the rule's own words rather than a category name.
        asked.append(AskedQuestion(
            concept=question.concept, tier=question.tier, answered=True,
            verdict="kept" if finding.usable else "dropped",
            subject=str(next((finding.facts.get(k) for k in question.subject
                              if finding.facts.get(k)), "") or ""),
            reason=(finding.challenged or finding.size_problem
                    or ("" if finding.usable
                        else f"true after {move.best_san or 'the better move'}"
                             f" as well, so it is a fact about the position")),
            facts=dict(finding.facts),
        ))

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
        asked=asked,
    )
