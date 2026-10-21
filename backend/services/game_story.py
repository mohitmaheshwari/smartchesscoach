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

# v2, 2026-10-21: every shown line carries the English it renders as, and a
# line that cannot be named is no longer shown. Rows written as v1 hold raw
# ids, pre-dedupe moments and span labels that counted positions out loud, so
# the read path recomputes them rather than serving them.
#
# v3, 2026-10-21: the story knows the result and the move played. A lost game
# no longer leads with a compliment, a hidden deciding mistake is located by
# its move instead of vanishing, and `home_lines` is the cut the home card
# shows. Scope: docs/game_story_on_screen_scope.md.
#
# v4, 2026-10-22: unnamed catch-all labels are no longer merged into one
# moment, and 395 stored "missed pin" labels were relabelled after the pin
# prover stopped accepting pins the front piece can take. Stories stored as
# v3 can hold either, so they are rebuilt on read.
#
# v5, 2026-10-22: every story carries the ledger and the plan (title,
# chapters, lesson, coach notes), from services.game_ledger and
# services.game_story_plan.
#
# v6, 2026-10-22: the ledger records opponent knights, rooks and queens the
# player shut in, credited only when the player caused it and it mattered.
SCHEMA_VERSION = "game_story.v6"

MAX_MOMENTS = 3          # the headline plus two
MAX_SPANS = 2
MAX_HOME_LINES = 3       # two moments and one stretch, as signed off

# Measured over the last three games of the 60 most active players (168
# games): "Answered a threat" headlined 12 of them, once on the second move
# of the game. Answering a threat is real, and it is not what a game was
# about, so it may appear lower in the review and never leads or reaches home.
_NEVER_LEADS = frozenset({"responded_to_threat"})

# When the move that decided the game cannot be NAMED -- its detector is not
# approved -- it is still located. Of 79 lost games in that sample, 41 had
# their deciding mistake hidden, and 15 led with a compliment instead. These
# sentences claim only what the engine alone already decides: that this move
# changed the game. They say nothing about why, which is exactly the part
# that needs an approved detector.
_LOCATED_IN_A_LOSS = "This is where the game got away."
_LOCATED_OTHERWISE = "This move gave a lot away."
LOCATED_ID = "located_turn"

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


# ─── Naming ──────────────────────────────────────────────────────────────
#
# Mohit, 2026-10-20, looking at a real story: "the story connects tags not the
# pieces and doesn't use english much, can't really show like that on app for
# users". He was right, and measuring it showed how right:
#
#     negative subtypes   74.0% of volume had an English name
#     executed motifs      2.8% of volume had one
#
# The story GUARANTEES a positive and ranks executed motifs above the three
# flags, so the positive line of nearly every story rendered as a raw id --
# `double_attack_line`, `pawn_hole_fianchetto`. The guarantee made it worst
# exactly where he noticed it.
#
# Each namespace already has an owner and this module adds no words of its
# own. A sixth concept vocabulary is the last thing this product needs:
#
#     negative subtype / positive flag  pattern_catalog.json
#     executed motif                    services.shape_patterns
#
# `shape_patterns` carries language signed off 2026-05-12 (class 6-8 English,
# keep the terms Indian coaches teach) and covers all 21 motifs the corpus
# produces, so naming them took no authoring at all -- only this lookup.
#
# An id with no entry is NOT shown. That is a narrow gate, not a silencing
# one: `test_every_story_id_has_an_english_name` walks every id the corpus
# can produce and fails if one is unnamed, so the gate is what makes the
# authoring obligation enforceable rather than what hides a gap.


def _display_name(label_id: str, polarity: str) -> Optional[str]:
    """The English this moment is shown as, or None when it may not be shown."""
    if polarity == "positive":
        try:
            from services.shape_patterns import PATTERNS_BY_ID
            shape = PATTERNS_BY_ID.get(label_id)
        except Exception:
            shape = None
        if shape and shape.get("name"):
            return str(shape["name"])
    try:
        from services.pattern_catalog import get_pattern
        entry = get_pattern(label_id) or {}
    except Exception:
        entry = {}
    name = entry.get("human_name")
    return str(name) if name else None


def _display_detail(label_id: str) -> Optional[str]:
    """One plain sentence under the name, or nothing.

    Only `pattern_catalog` is read here, and an executed motif therefore
    shows its name alone. That is a register decision, measured rather than
    assumed: of the 21 motifs the corpus produces, 8 descriptions are
    instructions for a live position ("Just take it", "do not trade
    lightly", "Attack it once more") and 3 are authored silence, so 11 of 21
    would read as advice about a game that is already over, or as a blank.

    The motif NAME survives the change of register in all 21 cases, which is
    why it is used and the sentence is not. Writing a second, past-tense
    description for the same id is the obvious alternative and the wrong one
    while it would live in a different file from the first -- if these want
    report-register sentences, they belong in `shape_patterns` beside the
    language they would join.
    """
    try:
        from services.pattern_catalog import get_pattern
        text = (get_pattern(label_id) or {}).get("short_description")
    except Exception:
        return None
    return str(text).strip() if text and str(text).strip() else None


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
        # The id stays -- it is stable, and an audit has to be able to tie a
        # shown line back to the detector that claimed it. The English rides
        # alongside rather than replacing it.
        "display_name": _display_name(label_id, polarity),
        "display_detail": _display_detail(label_id),
        "move_number": observation.get("move_number"),
        "ply": observation.get("ply"),
        # The move itself is how a line is located on screen. A player reads
        # no move numbers (the no-numbers rule), so "Kg3" is the address.
        "move_san": observation.get("move_san"),
        "move_uci": observation.get("move_uci"),
        "fen_before": observation.get("fen_before"),
        "color": observation.get("color"),
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
    outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble one game's story. Pure: no DB, no LLM, no engine.

    `recurring_ids` are the things this player keeps doing -- their focus
    topics or recent subtypes. Absent, recurrence simply does not rank, which
    is why it is a parameter and not a lookup.

    `is_showable` decides which moments may be NAMED to a player; the default
    allows all. Passing the detector-quality gate keeps a shadow detector's
    claim stored and auditable while never shown, exactly as captions do.

    `outcome` is `game_outcome.user_outcome`'s answer: "win", "loss", "draw"
    or "unknown". It only changes what LEADS and how a located line is
    worded; nothing is ranked or hidden by it.
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
    #
    # Only a NAMED kind is merged. A label the player cannot be shown is a
    # catch-all, not a kind: on 2026-10-22, after the false-pin relabel, game
    # 56b6c294 had 13...Nxg5 and 16...Ng5 both stored as
    # missed_generic_tactic, the merge kept Nxg5, and Ng5 -- the move that let
    # Rh1 trap the queen -- vanished from the story.
    _seen_ids = set()
    deduped = []
    for moment in moments:
        named = showable(moment.get("detector_quality_id")) and bool(
            moment.get("display_name"))
        key = (moment.get("polarity"), str(moment.get("id"))) if named \
            else (moment.get("polarity"), str(moment.get("id")), moment.get("ply"))
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
            # Spans were already written in English -- the span half of the
            # complaint was fixed by rewriting these templates. Carrying the
            # same key as a moment means a caller renders one list, not two.
            "display_name": trend.get("label"),
            "display_detail": None,
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
    showable_ranked = [
        m for m in moments
        if showable(m.get("detector_quality_id")) and m.get("display_name")
    ]

    lost = str(outcome or "").lower() == "loss"
    located = _located_line(moments, showable_ranked, lost=lost)
    if located is not None:
        showable_ranked = [located] + showable_ranked

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

    # What leads. Ranking already puts a deciding move first; these two rules
    # only stop the wrong thing from leading when ranking would let it.
    lead = next((m for m in chosen if _may_lead(m, lost=lost)), None)
    if lead is not None:
        chosen = [lead] + [m for m in chosen if m is not lead]
    spans_shown = spans[:MAX_SPANS]
    headline = lead or (spans_shown[0] if spans_shown else None)

    return {
        "schema_version": SCHEMA_VERSION,
        "outcome": outcome,
        "user_move_count": summary.get("user_move_count", 0),
        "headline": headline,
        # Everything ranked, for the record and any later audit.
        "moments": moments[:MAX_MOMENTS * 2],
        # What may be said out loud, in the order it is said.
        "moments_showable": chosen,
        "spans": spans_shown,
        "home_lines": _home_lines(chosen, spans_shown, headline),
        # An empty story is a fact about the game, not missing coverage, and
        # saying so stops a caller inventing filler to fill the space.
        "is_empty": not chosen and not spans,
    }


def _may_lead(moment: Mapping[str, Any], *, lost: bool) -> bool:
    """A lost game never leads with a compliment; some lines never lead."""
    if moment.get("id") in _NEVER_LEADS:
        return False
    if lost and moment.get("polarity") == "positive":
        return False
    return True


def _located_line(
    moments: Sequence[Mapping[str, Any]],
    showable_ranked: Sequence[Mapping[str, Any]],
    *,
    lost: bool,
) -> Optional[Dict[str, Any]]:
    """The deciding mistake, located by its move, when it cannot be named.

    Only when NO deciding mistake can be named: if one can, it leads on its
    own and a second, vaguer line about a different move would compete with
    it. The hidden moment stays in `moments` under its real id, so an audit
    can still see what the detector claimed.
    """
    if any(m.get("polarity") == "negative" and m.get("decisive")
           for m in showable_ranked):
        return None
    hidden = next(
        (m for m in moments
         if m.get("polarity") == "negative" and m.get("decisive")
         and m.get("move_san")),
        None,
    )
    if hidden is None:
        return None
    return {
        **hidden,
        "id": LOCATED_ID,
        "display_name": _LOCATED_IN_A_LOSS if lost else _LOCATED_OTHERWISE,
        "display_detail": None,
        # Nothing is named, so no detector is being quoted. The claim the
        # line does make -- this move changed the game -- is the engine's.
        "detector_quality_id": None,
        "located_from": hidden.get("detector_quality_id"),
    }


def _home_lines(
    chosen: Sequence[Mapping[str, Any]],
    spans: Sequence[Mapping[str, Any]],
    headline: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """The cut the home card shows: two moments and one stretch, at most.

    The headline comes first whatever it is. "Answered a threat" is left out
    entirely -- on home there is room for three lines, and it is never one of
    the three that matter.
    """
    moments = [m for m in chosen if m.get("id") not in _NEVER_LEADS]
    if headline is not None and headline.get("kind") == "span":
        ordered = [headline] + moments[:1] + [s for s in spans if s is not headline]
    else:
        ordered = moments[:2] + list(spans[:1]) + moments[2:] + list(spans[1:])
    return [dict(item) for item in ordered[:MAX_HOME_LINES]]


def attach_plan(
    story: Dict[str, Any],
    *,
    move_evaluations: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    game: Mapping[str, Any],
    opening_deviation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Add the timeline-and-ledger story to a moment story, in place.

    docs/game_story_by_phase_scope.md v2. The moment layer above still owns
    which detector names may be SHOWN; the plan borrows exactly those names,
    so a gated name cannot reach the player through the new path either. A
    failure here costs the plan, never the story it is attached to.
    """
    try:
        from services.game_ledger import build_ledger, opening_phase_exit_move
        from services.game_outcome import user_outcome
        from services.game_story_plan import plan_story
        from services.opening_normalizer import normalize_opening

        names = {
            (m.get("move_number"), m.get("move_san")): m.get("display_name")
            for m in story.get("moments_showable") or []
            if m.get("display_name") and m.get("id") != LOCATED_ID
        }
        raw_name = game.get("opening") or game.get("opening_name")
        family = normalize_opening(raw_name) if raw_name else None
        ledger = build_ledger(
            move_evaluations=move_evaluations,
            observations=observations,
            user_color=game.get("user_color") or "white",
            outcome=user_outcome(game),
            termination=game.get("termination"),
            opening_name=family if family and family != "Other" else None,
            opening_deviation=opening_deviation,
            phase_exit_move=opening_phase_exit_move(game.get("pgn")),
        )
        story["ledger"] = ledger
        story["plan"] = plan_story(ledger, names=names)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("game story plan failed", exc_info=True)
        story["plan"] = None
    return story


async def story_for_game(db, game: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The story for one game, read from storage or rebuilt. The one loader.

    `game` needs `game_id`, `user_id`, `user_color` and `result`. Returns None
    when the game has not been analysed. The story endpoint and the home card
    both come through here, so a story cannot read one way on the review page
    and another way on home.

    A story stored under an older schema is rebuilt, not served: v1 rows hold
    raw detector ids, v2 rows do not know who won.
    """
    from services.detector_quality import QualitySurface, is_authorized
    from services.game_outcome import user_outcome

    game_id = game.get("game_id")
    if not game_id:
        return None
    stored_doc = await db.game_analyses.find_one(
        {"game_id": game_id}, {"_id": 0, "game_story": 1})
    # `is None`, not falsiness: an analysis with no stored story projects to
    # {}, which is falsy, and that read every game analysed before the worker
    # wrote stories as "not analysed" -- found on game 8f40005b.
    if stored_doc is None:
        return None
    stored = stored_doc.get("game_story")
    if stored and stored.get("schema_version") == SCHEMA_VERSION:
        return {**stored, "source": "stored"}

    analysis = await db.game_analyses.find_one(
        {"game_id": game_id},
        {"_id": 0, "stockfish_analysis.move_evaluations": 1, "opening_deviation": 1})
    # The plan needs the PGN, the opening name and how the game ended, which
    # callers do not always pass.
    needed = ("pgn", "opening", "opening_name", "termination", "result", "user_color", "user_id")
    if any(key not in game for key in needed):
        extra = await db.games.find_one(
            {"game_id": game_id}, {"_id": 0, **{key: 1 for key in needed}}) or {}
        game = {**extra, **{k: v for k, v in game.items() if v is not None}}
    observations = await db.move_observations.find(
        {"game_id": game_id}, {"_id": 0}).to_list(length=None)
    recurring = [
        str(row.get("topic_key"))
        async for row in db.user_active_focus.find(
            {"user_id": game.get("user_id"), "status": "active"},
            {"_id": 0, "topic_key": 1},
        )
        if row.get("topic_key")
    ]

    def _showable(quality_id):
        if not quality_id:
            return True
        try:
            return is_authorized(quality_id, QualitySurface.CAPTION)
        except Exception:
            return False

    move_evaluations = (
        ((analysis or {}).get("stockfish_analysis") or {}).get("move_evaluations") or []
    )
    story = build_game_story(
        observations=observations,
        move_evaluations=move_evaluations,
        user_color=game.get("user_color") or "white",
        recurring_ids=recurring,
        is_showable=_showable,
        outcome=user_outcome(game),
    )
    attach_plan(story, move_evaluations=move_evaluations, observations=observations,
                game=game, opening_deviation=(analysis or {}).get("opening_deviation"))
    return {**story, "source": "recomputed"}
