"""rate_your_move.py — self-mirror of predict_coach_move (PWC premium).

The student grades their OWN move's quality (Good / Inaccuracy / Mistake-or-Blunder) before the coach
reveals the verdict. The actual quality is ALREADY computed by the V5 feedback (user_move_quality), so
this module only (a) buckets the 5-way engine quality into the 3 buttons the student sees, and (b) tells
whether the student's grade was right. Pure + unit-tested. See docs/rate_your_move_scope.md.

Firing (whether to SHOW the panel) lives in the frontend, since the frontend already has the quality —
fire only on instructive moves (a real mistake/blunder, or a clearly-best move), capped per game.
"""
from typing import Optional

# The student picks one of 3 buckets; the engine quality is one of best/good/inaccuracy/mistake/blunder.
_BUCKET = {
    "best": "good",
    "good": "good",
    "inaccuracy": "inaccuracy",
    "mistake": "mistake_blunder",
    "blunder": "mistake_blunder",
}

# The 3 buttons shown to the student (label -> bucket key).
RATING_OPTIONS = [
    {"key": "good", "label": "Good"},
    {"key": "inaccuracy", "label": "Inaccuracy"},
    {"key": "mistake_blunder", "label": "Mistake / Blunder"},
]


def quality_bucket(quality: Optional[str]) -> str:
    """Map an engine quality (best/good/inaccuracy/mistake/blunder) to one of the 3 student buckets."""
    return _BUCKET.get((quality or "").lower(), "good")


def rating_correct(guessed_bucket: Optional[str], actual_quality: Optional[str]) -> bool:
    """True if the student's 3-bucket grade matches the actual quality's bucket."""
    return (guessed_bucket or "").lower() == quality_bucket(actual_quality)


def is_instructive(quality: Optional[str]) -> bool:
    """A move worth asking the student to self-grade: a real mistake/blunder, or a clearly-best move.
    (The frontend pairs this with a per-game cap; routine 'good'/'inaccuracy' moves are skipped.)"""
    return (quality or "").lower() in ("best", "mistake", "blunder")
