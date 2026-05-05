"""
Per-commentary confidence score.

Each moment in the post-game stack has a one-line caption explaining
what went wrong on that move. This module assigns a 0–1 confidence to
that caption — how likely is THIS specific string to be correct and
useful for the player. Below 0.8 the caption goes to a human review
queue; above 0.8 it ships as-is.

Composition:
    score = 0.50 × source
          + 0.25 × detector_confidence
          + 0.15 × engine_corroboration
          + 0.10 × cp_loss_certainty

Why these weights: the source is the strongest prior (a deterministic
template built from verified facts beats an LLM string every time),
detector confidence handles within-source variation, engine
corroboration catches LLM hallucinations that name a move Stockfish
disagrees with, and cp_loss certainty handles "is this even a real
issue" — a tiny cp_loss makes any explanation suspect.
"""

from __future__ import annotations

from typing import Dict, List, Optional


# In-house deterministic detectors (live in concept_dispatcher.py, not
# the chess_brain registry). Higher trust than registry detectors
# because we wrote and tested them against specific game scenarios.
LOCAL_DETERMINISTIC_PATTERNS = {
    "walked_into_mate",
    "walked_into_capture",
    "pawn_race",
}


def _source_weight(
    source: str,
    pattern_type: Optional[str],
    detector_details: Optional[Dict],
    attempts: int,
    failed_attempts: Optional[List[Dict]],
) -> float:
    if source.startswith("template:"):
        # Engine-verified mate (Stockfish's mate_in_after) is the most
        # trustworthy commentary in the system — a forced mate proof.
        if (
            pattern_type == "walked_into_mate"
            and (detector_details or {}).get("source") == "engine"
        ):
            return 1.00
        if pattern_type in LOCAL_DETERMINISTIC_PATTERNS:
            return 0.95
        return 0.85  # chess_brain registry-backed templates

    if source == "llm":
        # Legacy — kept for back-compat with already-saved data. New
        # captions never use this source (LLM was removed).
        if attempts <= 1 and not failed_attempts:
            return 0.65
        if attempts == 2:
            return 0.50
        return 0.30

    if source == "engine_fallback":
        # Deterministic single-sentence fallback when no template fires.
        # Always flag for coach review — the prose surface is empty for
        # this position until we either build a template or override it.
        return 0.40

    return 0.50  # unknown source — middle of the road


def _detector_weight(
    source: str,
    detector_confidence: Optional[float],
    failed_attempts: Optional[List[Dict]],
) -> float:
    if detector_confidence is not None:
        try:
            return max(0.0, min(1.0, float(detector_confidence)))
        except Exception:
            pass
    if source == "llm":
        # Validator pass on first try → 0.7; retries → 0.5.
        return 0.7 if not failed_attempts else 0.5
    return 0.8  # template fallback


def _engine_corroboration(
    source: str,
    text: str,
    best_move_san: Optional[str],
) -> float:
    if source.startswith("template:"):
        # Templates use best_move_san by construction.
        return 1.0
    if not text:
        return 0.0
    if best_move_san and best_move_san in text:
        return 1.0
    # Grounded LLM prose that doesn't name the saving move — middle.
    return 0.5


def _cp_loss_certainty(cp_loss: Optional[int]) -> float:
    cp = abs(int(cp_loss or 0))
    if cp >= 300:
        return 1.0
    if cp >= 100:
        # Linear from 0.5 at 100 to 1.0 at 300.
        return 0.5 + (cp - 100) / 400.0
    return 0.3


def compute_moment_confidence(
    *,
    source: str,
    pattern_type: Optional[str] = None,
    detector_details: Optional[Dict] = None,
    detector_confidence: Optional[float] = None,
    attempts: int = 0,
    failed_attempts: Optional[List[Dict]] = None,
    cp_loss: Optional[int] = None,
    best_move_san: Optional[str] = None,
    text: str = "",
    threshold: float = 0.8,
) -> Dict:
    """Score one commentary string. Returns:
        {
          "confidence":    float in [0, 1] (rounded to 3 decimals),
          "needs_review":  bool — True iff confidence < threshold,
          "breakdown": {source, detector, engine_corroboration, cp_loss_certainty}
        }
    """
    s_w = _source_weight(source, pattern_type, detector_details, attempts, failed_attempts)
    d_w = _detector_weight(source, detector_confidence, failed_attempts)
    e_w = _engine_corroboration(source, text, best_move_san)
    c_w = _cp_loss_certainty(cp_loss)

    score = 0.50 * s_w + 0.25 * d_w + 0.15 * e_w + 0.10 * c_w
    score = round(score, 3)
    return {
        "confidence": score,
        "needs_review": score < threshold,
        "breakdown": {
            "source": round(s_w, 3),
            "detector": round(d_w, 3),
            "engine_corroboration": round(e_w, 3),
            "cp_loss_certainty": round(c_w, 3),
        },
    }
