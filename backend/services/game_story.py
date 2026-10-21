"""What one game left the player: the sharp moments and the slow ones.

Mohit, 2026-10-20: "each game leaves something, like trapped your queen, or
miss mate in 1 ... but also some other stories, like inactive pieces for long
time ... so good and bad parts of a game".

Two shapes, and the product already produces both:

    MOMENT  one move. Lives in `move_observations`, written at analysis time.
            Measured over 400 games: median 4 per game, and genuinely
            two-sided -- 1,063 negative against 548 positive.
    SPAN    many moves. `board_state_game_summary` already aggregates eleven
            board-state trends per game ("your pieces stayed on your side of
            the board across 12 moves"). Median 3 per game, ten of the eleven
            firing on a fifth to a half of games.

So this module ASSEMBLES. It owns no chess rules, no new metric and no second
vocabulary: moments come from the observation layer, spans from
`compute_game_summary`, decisiveness from `classify_severity_practical`. If a
detector is wrong it stays wrong in exactly one place.

RANKING, which is a coaching judgement and not a fact:

    decisive   first -- the move that changed the result is what a player
               remembers, and it is already computed
    recurring  second -- the habit they keep repeating ties this game to
               their actual learning need rather than to one afternoon
    severity   only as a tiebreak. Alone it almost always picks the largest
               eval swing, which is often neither of the above.

ONE GUARANTEE THE MEASUREMENT FORCES: if a positive moment exists, the story
contains one. Negatives outnumber positives 1,063 to 548 AND carry higher
severity, so any plain top-N by severity yields an all-bad story. "Good and
bad parts" does not happen by accident.

An empty story is a real answer. 73 of 400 games have no sharp moment and 51
of 250 no span; saying so beats inventing something.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import chess

from services.board_state_game_summary import compute_game_summary
from services.severity import classify_severity_practical

SCHEMA_VERSION = "game_story.v1"

MAX_MOMENTS = 3          # the headline plus two
MAX_SPANS = 2

_SEVERITY_RANK = {"critical": 3, "serious": 3, "moderate": 2,
                  "blunder": 3, "mistake": 2, "inaccuracy": 1,
                  "minor": 1, "good": 0}

# Fields on an observation that mark something the player got RIGHT. Each is a
# positive observation in its own right, never the absence of a failure --
# counting quiet moves would make every game read as a triumph.
_POSITIVE_FLAGS = (
    "punished_opponent_blunder",
    "found_best_in_critical",
    "responded_to_threat",
)
_POSITIVE_VALUE_FIELD = "tactical_pattern_executed"

# How much a success SIGNIFIES. Negatives arrive with a severity; positives do
# not, so without this every success tied at zero and the order fell to
# whichever observation happened to come first.
#
# The first real story built on one of Mohit's own won games headlined
# "responded_to_threat" at move 6 -- answering a threat on move six is not the
# story of a game -- while "found_best_in_critical" at move 32, the best move
# at a critical moment, sat below it on nothing but list order.
#
# Finding the only move that holds a critical position says more about a player
# than answering a threat any opponent hands you, so they are ranked by that
# and not by convenience.
_POSITIVE_STRENGTH = {
    "found_best_in_critical": 3,
    "punished_opponent_blunder": 2,
    "responded_to_threat": 1,
}
_EXECUTED_MOTIF_STRENGTH = 2


def _user_moves_for_summary(
    move_evaluations: Sequence[Mapping[str, Any]],
    user_color: str,
) -> List[Dict[str, Any]]:
    """Shape `move_evaluations` into what `compute_game_summary` reads.

    It needs only `is_user_move`, `fen_after` and `move_number`, all of which
    exist at analysis time -- which is why the story can be built then rather
    than waiting for `decryption_v5_data`, generated lazily on first review.

    User-ness is read from the FEN's side to move, NOT from
    `is_opponent_move`. Coach games do not set that field, so `not
    is_opponent_move` counted both players and doubled every trend's
    denominator. Verified over 120 games: the FEN basis reproduces the
    v5-sourced trends and counts exactly, 120 of 120, coach games included.
    """
    wanted = chess.WHITE if str(user_color or "white").lower() == "white" \
        else chess.BLACK
    shaped: List[Dict[str, Any]] = []
    for row in move_evaluations or []:
        fen_before = row.get("fen_before")
        if not fen_before:
            continue
        try:
            turn = chess.Board(fen_before).turn
        except (ValueError, AssertionError):
            continue
        shaped.append({
            "is_user_move": turn == wanted,
            "fen_after": row.get("fen_after"),
            "move_number": row.get("move_number"),
        })
    return shaped


def _decisive(observation: Mapping[str, Any]) -> bool:
    """Did this move hand away a won or level position?

    Delegates to `classify_severity_practical`, which already owns the
    win-probability states and the `decisiveness_changed` flag. Re-deriving it
    here would be a second answer to the same question.
    """
    eval_before = observation.get("eval_before")
    eval_after = observation.get("eval_after")
    if eval_before is None or eval_after is None:
        return False
    try:
        practical = classify_severity_practical(
            int(observation.get("cp_loss") or 0),
            mover_is_user=True,
            mover_is_white=str(observation.get("color") or "white").lower()
            == "white",
            eval_before_cp=int(eval_before),
            eval_after_cp=int(eval_after),
        )
    except (TypeError, ValueError):
        return False
    return bool(practical.decisiveness_changed)


def _moment_from(observation: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """One story moment, or None when the observation says nothing sharp."""
    subtype = observation.get("subtype")
    pattern = observation.get("missed_pattern")
    executed = observation.get(_POSITIVE_VALUE_FIELD)
    flags = [name for name in _POSITIVE_FLAGS if observation.get(name) is True]

    family = str(pattern) if pattern else None
    if subtype and pattern:
        label_id, polarity = str(subtype), "negative"
        quality_id = f"gap:{pattern}:{subtype}"
        strength = _SEVERITY_RANK.get(
            str(observation.get("severity") or "").lower(), 0)
    elif executed:
        label_id, polarity, quality_id = str(executed), "positive", None
        strength = _EXECUTED_MOTIF_STRENGTH
    elif flags:
        # Strongest signal the move carried, not the first one listed.
        best_flag = max(flags, key=lambda f: _POSITIVE_STRENGTH.get(f, 0))
        label_id, polarity, quality_id = best_flag, "positive", None
        strength = _POSITIVE_STRENGTH.get(best_flag, 0)
    else:
        return None

    return {
        "kind": "moment",
        "polarity": polarity,
        "id": label_id,
        "move_number": observation.get("move_number"),
        "ply": observation.get("ply"),
        "detector_quality_id": quality_id,
        # The family, because recurrence arrives as a TOPIC and a moment is a
        # SUBTYPE. `user_active_focus.topic_key` holds "missed_tactic" while
        # the moment is "missed_generic_tactic", so comparing ids alone meant
        # recurrence never once matched -- the same vocabulary mismatch that
        # separates lessons from observations elsewhere in this product,
        # reproduced inside one function.
        "family": family,
        "decisive": _decisive(observation) if polarity == "negative" else False,
        "severity": observation.get("severity"),
        "severity_rank": strength,
    }


def _rank_key(item: Mapping[str, Any], recurring: Iterable[str]):
    recurring = set(recurring or ())
    names = {str(item.get("id"))}
    if item.get("family"):
        names.add(str(item.get("family")))
    return (
        1 if item.get("decisive") else 0,
        1 if names & recurring else 0,
        item.get("severity_rank", 0),
        item.get("occurrence_count", 0),
    )


def build_game_story(
    *,
    observations: Sequence[Mapping[str, Any]],
    move_evaluations: Sequence[Mapping[str, Any]],
    user_color: str,
    recurring_ids: Iterable[str] = (),
    is_showable: Optional[Callable[[Optional[str]], bool]] = None,
) -> Dict[str, Any]:
    """Assemble one game's story. Pure: no DB, no LLM, no engine.

    `recurring_ids` are the things this player keeps doing -- their focus
    topics or recent subtypes. Absent, recurrence simply does not rank, which
    is why it is a parameter and not a lookup.

    `is_showable` decides which moments may be NAMED to a player; the default
    allows all. Passing the detector-quality gate keeps a shadow detector's
    claim stored and auditable while never shown, exactly as captions do.
    """
    recurring = set(recurring_ids or ())
    showable = is_showable or (lambda _quality_id: True)

    moments = [m for m in (_moment_from(o) for o in observations or []) if m]
    moments.sort(key=lambda m: _rank_key(m, recurring), reverse=True)
    # One slot per kind of mistake. The first real story this produced spent
    # two of its three slots on ignored_king_attack at moves 21 and 22 -- true
    # both times, and a waste of the story. A player takes away "you keep
    # ignoring attacks on your king", not two instances of it, so the
    # highest-ranked example of each id survives and the rest are dropped.
    # Repetition is the SPAN layer's job: it already says how many moves a
    # pattern lasted.
    _seen_ids = set()
    deduped = []
    for moment in moments:
        key = (moment.get("polarity"), str(moment.get("id")))
        if key in _seen_ids:
            continue
        _seen_ids.add(key)
        deduped.append(moment)
    moments = deduped

    summary = compute_game_summary(
        decryption_v5_data=_user_moves_for_summary(move_evaluations, user_color),
        user_color=user_color,
    )
    spans = [
        {
            "kind": "span",
            "polarity": "negative",
            "id": trend.get("fact_id"),
            "occurrence_count": trend.get("occurrence_count"),
            "move_numbers": trend.get("move_numbers"),
            "label": trend.get("label"),
            "severity_rank": 0,
            "decisive": False,
        }
        for trend in (summary.get("trends") or [])
    ]
    spans.sort(key=lambda s: _rank_key(s, recurring), reverse=True)

    # Select from what may actually be SHOWN, not from everything ranked.
    # The slice used to run before the showable filter, so an unnameable
    # moment ate a display slot: one of Mohit's games spent slot 1 on
    # missed_generic_tactic (Shadow, cannot be named) and showed two moments
    # where three were available. The full ranked list is still stored, so
    # nothing is lost from the record -- only the display picks from the
    # subset it is allowed to speak about.
    showable_ranked = [m for m in moments if showable(m.get("detector_quality_id"))]
    chosen = showable_ranked[:MAX_MOMENTS]
    # The guarantee. A plain top-N is all-negative in most games because
    # negatives are both more numerous and more severe, so if the player did
    # something right this story says so -- swapping the weakest chosen
    # negative rather than growing the list.
    if not any(m["polarity"] == "positive" for m in chosen):
        positive = next(
            (m for m in showable_ranked if m["polarity"] == "positive"), None)
        if positive is not None:
            chosen = (chosen[:MAX_MOMENTS - 1] + [positive]) if chosen \
                else [positive]

    shown = chosen
    headline = shown[0] if shown else (spans[0] if spans else None)

    return {
        "schema_version": SCHEMA_VERSION,
        "user_move_count": summary.get("user_move_count", 0),
        "headline": headline,
        # Everything ranked, for the record and any later audit.
        "moments": moments[:MAX_MOMENTS * 2],
        # What may be said out loud.
        "moments_showable": shown,
        "spans": spans[:MAX_SPANS],
        # An empty story is a fact about the game, not missing coverage, and
        # saying so stops a caller inventing filler to fill the space.
        "is_empty": not chosen and not spans,
    }
