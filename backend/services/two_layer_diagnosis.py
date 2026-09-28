"""Knowledge or behaviour: which of the two a player's misses point at.

docs/two_layer_coaching_scope.md, signed off 2026-09-28.

Mohit's model: a coach says either *you do not know this pattern yet* or *you
know it and you are not looking*. Forks, pins and hangs are the DRILL, not the
diagnosis -- a player is never "bad at threat awareness".

WHERE THE BEHAVIOUR SIGNAL COMES FROM, AND WHERE IT DOES NOT
------------------------------------------------------------
The scope said the behaviour reading would come from the CONTEXT OF THE MISSES
-- were they rushed. Measured 2026-09-28, it does not:

    fast-miss share across 49 players:
        min 0.00   q1 0.13   median 0.15   q3 0.18   max 0.28

Even the most rushed player rushes barely a quarter of his misses. There is
nobody we could honestly tell "you are moving before you look" about tactical
misses. So the behaviour layer comes from the player's general tempo instead,
which IS strong -- thinks-too-long is stable at 0.88 across halves of a player's
games.

WHY THINKS-LONG AND NOT THE CLOCK SHAPE
---------------------------------------
Both were tested against the knowledge axis. Only one is independent of it:

    knowledge x thinks-long          10 / 14 / 15 / 10   balanced
    knowledge x front-loaded clock   16 /  8 /  9 / 16   heavy diagonal

The front-loaded clock moves WITH the knowledge rate, so it carries much of the
same information. `thinks_long` splits the population evenly against knowledge,
which is what an independent second axis looks like.

THE CUT IS RELATIVE, AND THE WORDING MUST NOT BE
------------------------------------------------
The knowledge rate runs q1 0.58, median 0.66, q3 0.70. Missing a third of the
tactics that were there is ordinary for a 600-1500 player, so an absolute cut
would diagnose everybody. The cut therefore selects WHOM to coach, and the
wording must never imply a comparison -- "let us make this automatic", never
"you are below average". Nothing in this module returns a number.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# WHICH GATE THESE NUMBERS WERE MEASURED AGAINST.
#
# A knowledge cut only means something relative to the pattern set that produced
# the rates. When the gate gained pin, skewer and hidden_attack, the overall take
# rate fell from 67% to 53% -- and the old 0.66 cut, untouched, went from
# splitting the population in half to sitting above almost all of it, diagnosing
# every single player. A test asserts this matches the gate's own version, so
# the next pattern added cannot quietly do the same thing.
CALIBRATED_FOR_GATE = "opportunity_gate.v2_seven_patterns"

# Measured on the seven-pattern gate, 55 judgeable players, 2026-09-28:
#
#     min 0.361   p10 0.434   q1 0.462   median 0.524   q3 0.554   max 0.657
#
# The cut is the LOWER QUARTILE, not the median, and that is a deliberate
# choice rather than a rounding. The three candidates:
#
#     q1     0.462 -> 13 of 55 diagnosed, 42 told nothing
#     median 0.524 -> 27 of 55
#     0.550        -> 38 of 55
#
# A strong claim about a few people beats a weak claim about half of them. We
# have never shown that the drill changes anything, so the first version should
# be quiet and confident; widening is easy once the drill proves itself, while
# retracting a diagnosis nobody needed is not.
#
# The previous value was 0.66, measured on a two-pattern gate. On this gate that
# sits at the HUNDREDTH percentile -- above every player, max 0.657 -- so it
# diagnosed all 55. Hence CALIBRATED_FOR_GATE above.
KNOWLEDGE_LOW_CUT = 0.46

# Kept as an alias so the name change does not silently break a caller. The cut
# is no longer a median and calling it one would invite the next person to
# "correct" it back.
KNOWLEDGE_MEDIAN = KNOWLEDGE_LOW_CUT

# Share of a player's moves taken at more than three times his own pace for that
# game. Measured across the same players: q1 0.12, median 0.14, q3 0.17. This
# one splits which KIND of gap, not whether there is one, so the median is right
# here -- both sides of it get coached, just differently.
THINKS_LONG_MEDIAN = 0.14

KNOWLEDGE_GAP = "knowledge"
ATTENTION_GAP = "attention"
NO_TACTICAL_GAP = "no_tactical_gap"
NOT_ENOUGH_EVIDENCE = "not_enough_evidence"

# What each verdict means for the DRILL. The whole point of separating the two
# layers is that the same missed forks lead to different exercises.
PRESCRIPTION = {
    KNOWLEDGE_GAP: "teach the shape -- puzzles on the pattern he misses most",
    ATTENTION_GAP: "a looking habit, NOT more puzzles on the pattern",
    NO_TACTICAL_GAP: "nothing here; his misses are not about seeing shapes",
    NOT_ENOUGH_EVIDENCE: "say nothing until he has played more",
}


def diagnose(pooled: Dict[str, Any],
             thinks_long_share: Optional[float]) -> Dict[str, Any]:
    """Which layer this player's tactical misses point at.

    `pooled` is a `services.opportunity_gate.pooled_knowledge` result.
    `thinks_long_share` is the share of his moves taken at more than three times
    his own pace for that game.

    The two gaps are distinguished by a single question: when he misses, had he
    given himself time to see it?

      misses, and takes his time   -> he does not know the shape
      misses, and does not         -> he never looked long enough to know

    A player who finds most of them gets no diagnosis on this axis rather than a
    softened one, because a diagnosis nobody needs is noise in the coaching.
    """
    if not pooled or not pooled.get("judgeable"):
        return _verdict(NOT_ENOUGH_EVIDENCE, None)

    rate = pooled.get("_rate")
    if rate is None:
        return _verdict(NOT_ENOUGH_EVIDENCE, None)
    if rate >= KNOWLEDGE_MEDIAN:
        return _verdict(NO_TACTICAL_GAP, None)

    if thinks_long_share is None:
        # We know he misses them and nothing about how he spends his time.
        # Teaching the shape is the safe half of the answer: it helps either
        # way, where a looking-habit drill helps only one of them.
        return _verdict(KNOWLEDGE_GAP, None)

    if thinks_long_share >= THINKS_LONG_MEDIAN:
        return _verdict(KNOWLEDGE_GAP, "takes time and still does not see it")
    return _verdict(ATTENTION_GAP, "does not give himself time to see it")


def _verdict(layer: str, because: Optional[str]) -> Dict[str, Any]:
    return {
        "schema_version": "two_layer_diagnosis.v1",
        "layer": layer,
        "because": because,
        "prescription": PRESCRIPTION[layer],
    }


def card(diagnosis: Dict[str, Any], pattern: Optional[str]) -> Optional[Dict[str, str]]:
    """What the player reads. No counts, no percentages, no comparison.

    The pattern names the drill, never the diagnosis -- a per-pattern rate is
    too thin to describe a person, which is why `pooled_knowledge` pools.
    """
    layer = diagnosis.get("layer")
    shape = {"fork": "forks", "free_piece": "free material",
             "pin": "pins", "skewer": "skewers"}.get(str(pattern), "tactics")

    if layer == KNOWLEDGE_GAP:
        return {
            "headline": "Your eye has not learned this shape yet.",
            "body": ("Chances come up in your games more often than you take "
                     "them, and you are giving yourself time. So this is not "
                     "rushing. You are not seeing the shape."),
            "next": "Next: positions where %s are waiting. Find it before you move."
                    % shape,
        }
    if layer == ATTENTION_GAP:
        # DELIBERATELY A HYPOTHESIS, NOT A DIAGNOSIS.
        #
        # This verdict comes from the player's GENERAL tempo -- he is a quick
        # mover -- not from the speed of these particular misses. And the miss
        # speed does not support a causal claim: the fast-miss share runs 0.00
        # to 0.28 with a median of 0.15, and across 42 players mistakes are LESS
        # rushed than ordinary moves (13.2% against 23.5%).
        #
        # So the card offers slowing down as something to TRY and report back
        # on, and does not tell him his speed caused these misses. An earlier
        # version said "The idea is not the problem. Stopping to check is.",
        # which asserts exactly the causation the measurement refuses.
        return {
            "headline": "You play quickly. Let us find out if that is costing you.",
            "body": ("Chances come up in your games more often than you take "
                     "them, and you are a fast mover in general. Whether the "
                     "two are connected, we do not know yet."),
            "next": "Next: the same positions, but take your time on each one. "
                    "If you find more that way, we have our answer.",
        }
    return None
