"""Which openings cost this player games.

docs/opening_report_scope.md, signed off 2026-09-26.

opening_knowledge is the one weakness topic that cannot be promoted, because
its single authorized detector -- left_book_for_a_worse_move -- fires twice in
the entire product. That detector is aimed at a hard problem: catching a
player leaving theory, which needs the book to match his move history.

Which openings cost him material needs no book. It is already in the games.

NOT A SECOND OPENING TABLE
--------------------------
Classification reuses `decryption_voice.opening_book._OPENINGS`, the curated
table the caption layer already matches against, and asks it a different
question. That table answers "which opening did this move complete", because
it was built for per-move captions. A game needs "which opening is this",
which is the longest line the game's own moves follow. Same rows, same names,
one source.

Its keys (`italian_giuoco_piano`, `ruy_lopez`) are the curriculum's keys, so a
classified game links straight to a lesson with no second mapping in between.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

# The measured distribution, not chosen numbers. Errors per 100 opening moves
# across 435 eligible user-and-opening pairs, 2026-09-26:
#     min 0.0   q1 8.8   median 12.5   q3 16.7   max 35.6
#
# Re-measured on the CANONICAL basis after the classifier changed. The first
# numbers (q1 9.6, q3 17.9) came from grouping by a prefix of the platform's
# opening name, which is a different question from "which line in our table
# did this game follow". Keeping them would have banded players against a
# population that no longer exists.
STRONG_BELOW = 8.8
WEAK_ABOVE = 16.7

# 30.3% of user-and-opening pairs have ONE game and 56.1% have three or fewer.
# A rate under this is noise with a decimal point on it.
#
# THE COST OF THIS GATE, measured rather than assumed: 27.1% of users have NO
# opening that passes it, and 47.5% have two or fewer. So this report is
# silent or nearly silent for about half the user base, and that is the right
# outcome -- those players get the phase-level grade on the areas card, which
# needs no per-opening sample. Lowering the gate to serve them would buy
# coverage with claims the games do not support.
MIN_GAMES = 5
MIN_OPENING_MOVES = 40


def classify_opening(history_san: Iterable[str]) -> Optional[str]:
    """The opening this game played, as a curriculum key.

    The longest line in the shared table that the game's own moves follow.
    `recognize_opening_from_history` cannot answer this: it requires the last
    move supplied to be the one that COMPLETES the name, because it exists to
    caption the move where an opening becomes recognisable. Feeding it a whole
    game returns nothing unless the game happened to end on that move.
    """
    from services.decryption_voice.opening_book import _OPENINGS

    history = [str(m) for m in (history_san or [])]
    if not history:
        return None
    best_key, best_len = None, 0
    for entry in _OPENINGS:
        moves = entry.get("moves") or []
        if len(moves) > len(history) or len(moves) <= best_len:
            continue
        if history[:len(moves)] == list(moves):
            best_key, best_len = entry.get("name"), len(moves)
    return best_key


def band_for(errors_per_100: float) -> str:
    """Where this rate sits against what every player does in the opening."""
    if errors_per_100 < STRONG_BELOW:
        return "strong"
    if errors_per_100 > WEAK_ABOVE:
        return "weak"
    return "middling"


def build_report(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Rank a player's openings.

    `rows` is one entry per game: {"opening": key, "opening_moves": int,
    "mistakes": int}. Openings below the gate are counted but never ranked --
    they are reported as "not enough games yet" rather than scored, because a
    rate over one game says nothing and a confident line built on it is a lie
    with a label.
    """
    tally: Dict[str, Dict[str, int]] = {}
    for row in rows or []:
        key = row.get("opening")
        if not key:
            continue
        slot = tally.setdefault(key, {"games": 0, "moves": 0, "mistakes": 0})
        slot["games"] += 1
        slot["moves"] += int(row.get("opening_moves") or 0)
        slot["mistakes"] += int(row.get("mistakes") or 0)

    ranked: List[Dict[str, Any]] = []
    thin = 0
    for key, slot in tally.items():
        if slot["games"] < MIN_GAMES or slot["moves"] < MIN_OPENING_MOVES:
            thin += 1
            continue
        rate = 100.0 * slot["mistakes"] / slot["moves"]
        ranked.append({
            "opening": key,
            "band": band_for(rate),
            # internal only -- never rendered, per the no-numbers rule
            "_errors_per_100": rate,
            "_games": slot["games"],
            "_moves": slot["moves"],
        })
    ranked.sort(key=lambda r: r["_errors_per_100"])

    return {
        "measured": bool(ranked),
        "openings": ranked,
        "not_enough_games": thin,
        "best": ranked[0]["opening"] if ranked else None,
        "worst": ranked[-1]["opening"] if ranked else None,
    }


def report_lines(report: Dict[str, Any], teachable: Optional[set] = None
                 ) -> Dict[str, Any]:
    """The words, and whether a "learn it" door exists behind them.

    No numbers reach the player: the ordering carries the information and the
    rate only chooses the sentence. The worst opening is named because that is
    the one sentence worth acting on; the best is named warmly because a
    report that is only bad news is a failure scoreboard.

    The copy deliberately says "you rarely slip here" and never "your best
    opening". After gating, the thinnest eligible sample is still around 130
    opening moves, so the ORDER of the top few is not stable enough to claim a
    winner, though the bands either side of it are.
    """
    worst = report.get("worst")
    best = report.get("best")
    if not worst:
        return {"available": False,
                "reason": "not enough games in any one opening yet"}

    pretty = lambda key: str(key or "").replace("_", " ").title()
    lines: Dict[str, Any] = {
        "available": True,
        "worst": worst,
        "worst_label": pretty(worst),
        "best": best,
        "best_label": pretty(best),
        "best_line": "You rarely slip here.",
        "worst_line": "This one costs you more mistakes than any other opening you play.",
        "can_learn_worst": bool(teachable and worst in teachable),
    }
    return lines
