"""One face. A move goes in, the facts come out.

Mohit, 2026-10-23:

    "I want everything inside framework and framework takes care of
    everything, right now we have different faces... games or moves talk
    to framework and framework decide and generate and send to LLM...
    consolidate everything inside one face, so game talks to one face and
    then that face decides what to do."

This is the first half of that: the one place that decides WHICH facts a
move has. `decide` -- precedence between the framework, the distilled
layer and the rule cascade -- is the second half and still lives in the
renderer; see docs/one_face_framework_scope.md.

Three kinds of move, and the caller no longer has to know which:

    FAULT      cp_loss at or above 40. The facts are about the BETTER
               move: why the engine's choice was better than this one.
               Measured: facts on 75% of faults.

    GOOD       everything else. The facts are about the PLAYED move --
               what it achieved. This is new, and it is the same
               detectors aimed at a different move.

    PLAN       a named shape that sets something up, like the rook pawn
               advancing before the push that hits a bishop. Fires
               alongside GOOD.

The GOOD kind is the whole reason this file exists. The detectors were
only ever called with the better move, so every fact read as "what the
better move achieves" -- meaningless on a move that IS best -- and 58% of
a review page got nothing from them. I told Mohit that made the framework
structurally limited to mistakes. He asked why, and the answer was that I
had confused the wiring with the detectors: they take a board and a move
and say what that move DOES.

Measured over 5,879 non-faulted moves: the same detectors, aimed at the
played move, find facts on **62.4%**. Together with faults that takes the
framework from writing 22% of the page to roughly 68%, with no new
detector and no new engine call.

Pure: no database, no engine, no network. Everything it needs is already
on the stored move.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# The review page shows cards down to 40cp, so that is where a move stops
# being "fine" and starts being a fault. Not 100: Mohit opened a 42cp card
# reading only "Opponent's c3 is an inaccuracy. Play c6." and asked why the
# engine had not said why. It had never been asked.
FAULT_CP = 40

# move_purposes' tiers: MATE 4, MATERIAL 3, SAFETY 2, POSITIONAL 1.
MATERIAL_TIER = 3

FAULT = "fault"
GOOD = "good"
PLAN = "plan"


@dataclass(frozen=True)
class Facts:
    """What this move is, and what is true about it."""
    kind: str                                   # FAULT | GOOD | PLAN
    purposes: List[Dict[str, Any]] = field(default_factory=list)
    plan: List[Dict[str, Any]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.purposes or self.plan)

    @property
    def all(self) -> List[Dict[str, Any]]:
        return list(self.purposes) + list(self.plan)

    @property
    def top_tier(self) -> int:
        return max((int(p.get("tier") or 1) for p in self.purposes),
                   default=0)

    @property
    def notable(self) -> bool:
        """Is this worth a sentence at all?

        A fault always is -- the reader is asking why their move was worse.
        A plan is, because something is coming.

        A GOOD move usually is not, and that is the point. A coach says
        nothing about most good moves; he speaks when something real
        happened. Praising a developing move on move three is the same
        filler Mohit has been chasing all week, in a cheerful register.

        Measured over 7,996 good moves, by the highest tier among their
        facts:

            MATE          0.7%  ->  0.1 captions a game
            MATERIAL     23.2%  ->  4.8   <- this one
            SAFETY       20.5%  ->  8.9
            POSITIONAL   18.5%  -> 12.6

        MATERIAL is the cut: about five a game, and the kinds that fire
        there are won material, a trapped piece and a running passer --
        exactly what a coach would mention. One tier lower doubles the
        volume to say "you developed a piece".
        """
        if self.kind == FAULT:
            return bool(self.purposes)
        if self.plan:
            return True
        return self.top_tier >= MATERIAL_TIER


def facts_for(
    fen_before: str,
    played_san: str,
    *,
    best_san: Optional[str] = None,
    cp_loss: int = 0,
    pv_after_played: Optional[Sequence[str]] = None,
    pv_after_best: Optional[Sequence[str]] = None,
    eval_line: Optional[Sequence[str]] = None,
    threat: Optional[Any] = None,
    mate_info: Optional[Dict[str, Any]] = None,
) -> Facts:
    """Everything the engine can say about this move, and nothing else.

    The caller passes a move and gets facts. It does not choose a detector
    set, does not know which purposes exist, and does not decide whether
    this is a mistake -- that was the scattering this replaces.
    """
    from services.move_purposes import plan_purposes_for, purposes_for

    if not fen_before or not played_san:
        return Facts(kind=GOOD)

    is_fault = int(cp_loss or 0) >= FAULT_CP

    if is_fault:
        try:
            ps = purposes_for(
                fen_before, played_san, best_san,
                list(pv_after_played or []), list(pv_after_best or []),
                threat, mate_info, eval_line=eval_line)
        except Exception as exc:
            logger.debug("[framework] fault facts failed: %r", exc)
            ps = []
        return Facts(kind=FAULT, purposes=ps)

    # A GOOD move. The played move is the subject, so it is passed as its
    # own "better move" -- the detectors then describe what IT achieves.
    try:
        ps = purposes_for(
            fen_before, played_san, played_san,
            list(pv_after_played or []), list(eval_line or []),
            None, mate_info, eval_line=eval_line)
    except Exception as exc:
        logger.debug("[framework] good-move facts failed: %r", exc)
        ps = []

    # Drop the purposes that only mean something against an alternative.
    # "the move played brought nothing out" is nonsense about a move that
    # WAS the best one, and shipping it would be the same class of error
    # as telling a player the better move when they played it.
    ps = [p for p in ps if not str(p.get("kind", "")).startswith("played_")]

    # And drop the mate transitions, which are WRONG here rather than
    # merely unhelpful. 51 of 7,996 non-faulted moves came back with
    # `allowed_forced_mate`: a move that allows forced mate is not a good
    # move, and the explanation is the mate sentinel -- once a player is
    # lost, every move they make "allows mate" while cp_loss stays at 0
    # because the position was already decided. Saying so on a quiet move
    # would read as a blunder that never happened.
    ps = [p for p in ps
          if str(p.get("kind", "")) not in
          ("allowed_forced_mate", "missed_forced_mate")]

    try:
        pl = plan_purposes_for(fen_before, played_san, eval_line=eval_line)
    except Exception as exc:
        logger.debug("[framework] plan facts failed: %r", exc)
        pl = []

    return Facts(kind=PLAN if (pl and not ps) else GOOD,
                 purposes=ps, plan=pl)


def decide(
    inputs,
    state,
    *,
    eval_lookup: Optional[Dict[str, Any]] = None,
    **cascade_kwargs,
):
    """The finished card. The caller renders what comes back.

    Mohit, when I reported that six writers still produced one page after
    `facts_for` shipped: "six writers, no man, no, clearly mentioned."

    He was right. `facts_for` consolidated what a move's FACTS are, and
    left the precedence -- which writer's words actually reach the card --
    in the renderer, where it had been arbitrating between three faces.
    This is that half.

    What it owns, in order:

      1. the rule cascade and the distilled layer, by calling
         `build_move_teaching_decision` itself
      2. the framework's own text, which REPLACES the cascade's words when
         the analysis wrote one from proven facts
      3. nothing else. Arrows, highlights and best-move arrows come back
         exactly as the decision produced them -- Mohit asked for the
         arrows to be left alone, and the corpus fingerprint checks both
         arrow columns per card to prove it.

    The returned object is the decision, with `.text.caption` and
    `.text.rule_name` already settled, so a caller cannot pick a different
    winner by accident. That was the whole failure mode: three writers and
    a renderer deciding between them.
    """
    from services.caption_pipeline import build_move_teaching_decision

    decision = build_move_teaching_decision(
        inputs, state, eval_lookup=eval_lookup, **cascade_kwargs)

    # The framework's sentence, written once at analysis time from the
    # engine's own facts and stored on the move. Nothing calls a model
    # here.
    #
    # eval_lookup is keyed by the first FOUR fen fields, not the whole
    # string. Looking it up with the full FEN finds nothing and fails
    # silently, which was the shape of three wiring bugs in this path.
    llm = None
    try:
        key = " ".join((inputs.fen_before or "").split()[:4])
        row = (eval_lookup or {}).get(key) or {}
        llm = (row.get("llm_caption") or "").strip() or None
    except Exception:
        llm = None

    if llm:
        decision.text.caption = llm
        decision.text.rule_name = (
            (decision.text.rule_name or "") + "→LLM_CAPTION")
    return decision


def facts_for_move(move: Dict[str, Any]) -> Facts:
    """`facts_for` straight from a stored move_evaluation.

    The shape the analysis worker and the renderer both already hold, so
    neither has to remember which field feeds which argument -- the last
    place that knowledge lived in three copies.
    """
    return facts_for(
        move.get("fen_before") or "",
        str(move.get("move") or ""),
        best_san=(str(move.get("best_move")) if move.get("best_move")
                  else None),
        cp_loss=int(move.get("cp_loss") or 0),
        pv_after_played=move.get("pv_after_played"),
        pv_after_best=move.get("pv_after_best"),
        eval_line=move.get("eval_line_played"),
        threat=move.get("threat"),
        mate_info=move.get("mate_info"),
    )
