"""The milestone chain: what we worked on, and what the measurement found.

docs/progress_then_and_now_scope.md

Mohit, 2026-10-07: "not just first 10 vs last 10, but also a comparison of
milestones... a coach never just gets stuck on what you were before me, a coach
keeps on teaching and seeing are you improving."

A milestone here is a FOCUS CYCLE -- the stretch the coach spent on one thing --
not a fixed block of games. Blocks of 10 and 20 were measured and rejected:
trend/noise came out at 1.46 and 1.22, and pooling the raw counts instead of
averaging per-game scores made no difference at all (1.45), because the
denominator was never small. The habit series are simply flat. A focus cycle,
measured by its own proof detector, is the thing that actually moves.

THREE RULES, EACH FROM A MEASUREMENT RATHER THAN A PREFERENCE
-------------------------------------------------------------

1. NEVER CHAIN ACROSS METRIC NAMES. On 2026-09-21 every one of 32 observations
   was written with metric_name None, and they produced deltas of +97%, +236%,
   +382%, +473%. Those are not chess facts; that day of measurement had no
   metric identity at all. Separately, piece_safety_misses_per_decision is a
   per-DECISION rate while king_safety_per_game and time_management_per_game
   are per-GAME, so even two valid readings can sit on different scales. A
   cycle is only ever compared with itself, on one metric.

2. NEVER ASSERT A VERDICT FROM ONE OBSERVATION. Of the 30 focuses with a real
   verdict, 23 never flip between improved and regressed, and 17 of the 18
   outlier readings fall on that one bad day. Requiring agreement is what turns
   a stable signal into a statement and leaves the artefact out. A coach does
   not revise his assessment because of one session.

3. NO NUMBERS ON SCREEN. The deltas are real and sizeable -- median 39% -- but
   "you are 29% better at piece safety" is not something a 1200 player can use.
   The words carry it.

WHAT IT REFUSES TO CLAIM: that we caused any of it. The within-user
difference-in-differences that could support that lives in
scripts/measure_coaching_contribution.py and currently finds no detectable
effect, which is the expected answer while the product is not yet live. This
describes change; it never takes credit for it.
"""
from __future__ import annotations

import collections
from typing import Any, Dict, List, Mapping, Optional, Sequence

SHADOW = "focus_outcome_shadow"
FOCUSES = "user_active_focus"

# How many observations must agree, on one metric, before a verdict is spoken.
# Two excludes the single-day artefact and still lets the coach speak after two
# days; three would have bought a week of silence for nothing, since the stable
# series are stable from their first reading.
MIN_AGREEING = 2

REAL_VERDICTS = ("improved", "stuck", "regressed")

# In the second person, in words. "stuck" is deliberately not called "stuck" to
# the player: that is a label for us, not a thing to tell someone.
VERDICT_WORDS: Mapping[str, str] = {
    "improved": "this got better",
    "regressed": "this got worse while we worked on it",
    "stuck": "this did not move",
}

TOPIC_WORDS: Mapping[str, str] = {
    "piece_safety": "leaving pieces where they can be taken",
    "king_safety": "letting your king get exposed",
    "missed_tactic": "missing the tactic that was there",
    "tactical_oversight": "seeing one move and missing the next",
    "calculation_depth": "stopping the line too early",
    "time_management": "running your clock down",
    "opening_knowledge": "leaving what you know in the opening",
    "endgame_technique": "converting the endgame",
}


def topic_words(topic: Optional[str]) -> Optional[str]:
    """Plain words for a topic, or None.

    None rather than a prettified key. "Tactical oversight" is a label from our
    database, not something a coach says, and printing the raw key is how a
    reader finds out they are reading a dashboard.
    """
    if not topic:
        return None
    return TOPIC_WORDS.get(str(topic).strip())


def settled_verdict(observations: Sequence[Mapping[str, Any]]
                    ) -> Optional[Dict[str, Any]]:
    """The verdict a cycle has actually settled on, or None.

    Keeps only observations on the cycle's dominant metric, then requires the
    most recent MIN_AGREEING of them to agree. Anything else returns None,
    which the surface shows as "still watching" -- the honest answer, and far
    better than a verdict that reverses tomorrow.
    """
    usable = [o for o in observations
              if o.get("metric_name")
              and o.get("resolution") in REAL_VERDICTS
              and o.get("delta_pct") is not None]
    if len(usable) < MIN_AGREEING:
        return None

    names = collections.Counter(str(o["metric_name"]) for o in usable)
    metric = names.most_common(1)[0][0]
    on_metric = [o for o in usable if str(o["metric_name"]) == metric]
    if len(on_metric) < MIN_AGREEING:
        return None

    on_metric.sort(key=lambda o: str(o.get("observed_on") or ""))
    recent = on_metric[-MIN_AGREEING:]
    if len({o["resolution"] for o in recent}) != 1:
        return None

    verdict = recent[-1]["resolution"]
    return {
        "verdict": verdict,
        "words": VERDICT_WORDS.get(verdict, ""),
        "metric_name": metric,
        # Kept for us and never rendered, per rule 3.
        "delta_pct": recent[-1]["delta_pct"],
        "observations": len(on_metric),
        "first_seen": on_metric[0].get("observed_on"),
        "last_seen": on_metric[-1].get("observed_on"),
    }


async def build_chain(db, user_id: str) -> Dict[str, Any]:
    """Every stretch the coach has worked on, oldest first.

    The focus history gives the cycles, focus_outcome_shadow gives what each
    one measured. A cycle with no settled verdict is still listed: "we are on
    this now" is part of the story, and dropping it would turn the chain into a
    trophy cabinet.
    """
    cycles = await db[FOCUSES].find(
        {"user_id": user_id, "type": {"$ne": "strength"}},
        {"_id": 1, "topic_key": 1, "status": 1, "started_at": 1,
         "created_at": 1, "closed_at": 1, "resolution": 1}).to_list(None)

    seen: Dict[str, List[Mapping[str, Any]]] = collections.defaultdict(list)
    cursor = db[SHADOW].find(
        {"user_id": user_id},
        {"_id": 0, "focus_id": 1, "observed_on": 1, "resolution": 1,
         "delta_pct": 1, "metric_name": 1})
    async for doc in cursor:
        seen[str(doc.get("focus_id"))].append(doc)

    out = []
    for cycle in cycles:
        words = topic_words(cycle.get("topic_key"))
        if not words:
            continue
        # A CYCLE APPEARS ONLY IF SOMETHING WAS EVER MEASURED AGAINST IT.
        #
        # Without this the chain showed one player NINE rows, seven of them
        # dated 2026-07-01/02 and all repeating the same sentence. Those are
        # `superseded_v6` through `v9` -- our own migrations rewriting a single
        # focus -- and a coach's notebook does not carry the same entry five
        # times on one day.
        #
        # The test is evidence, not a status whitelist, because the statuses do
        # not split cleanly and a hardcoded list would rot at the next
        # migration. Measured 2026-10-08: the four `superseded_v*` statuses
        # hold 163 rows with ZERO observations between them, while `active`
        # (53/53), `superseded_by_recency_ranking` (30/30),
        # `superseded_by_detector_promotion` (12/12), `completed` (2/2) and
        # `escalated` (1/1) are fully observed. A focus the measurement loop
        # never saw is not a stretch the player lived through; it is a row.
        observations = seen.get(str(cycle["_id"]), [])
        if not observations:
            continue
        out.append({
            "topic": cycle.get("topic_key"),
            "words": words,
            "started_at": cycle.get("started_at") or cycle.get("created_at"),
            "closed_at": cycle.get("closed_at"),
            "is_current": cycle.get("status") == "active",
            "settled": settled_verdict(observations),
            # Provenance only. The stored resolution was written by whatever
            # the detector looked like at the time; differencing against stored
            # values turned 13 improved / 0 regressed into 4 / 3 / 6 when the
            # before half was re-derived with current code.
            "stored_resolution": cycle.get("resolution"),
        })

    out.sort(key=lambda c: str(c.get("started_at") or ""))
    return {
        "schema_version": "progress_chain.v1",
        "cycles": out,
        "measured": any(c["settled"] for c in out),
    }
