"""
Concept dispatcher — runs the existing chess_brain detector registry
against a moment, picks the dominant detected pattern, renders a
deterministic caption from concept_templates.

This replaces the LLM call in the candidate-builder caption path. The
detectors already exist (services/chess_brain/detector_registry.py and
advanced_detectors.py). This module is the thin glue: position →
detector run → priority pick → caption.

No LLM. No hallucination. Every word in the caption comes from
detector facts or template constants.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import chess

from .concept_templates import render_caption, has_template

logger = logging.getLogger(__name__)


def detect_concepts(
    *,
    fen_before: str,
    user_move_san: str,
    best_move_san: Optional[str] = None,
    context: Optional[Dict] = None,
) -> List[Dict]:
    """Run all chess_brain detectors against this moment.

    Returns a flat list of detector results (each a dict from
    DetectorResult: pattern_type, details, teaching_hook, key_squares,
    confidence, category) sorted by registration priority (already
    sorted in the registry).

    Returns [] on any exception so callers can fall through gracefully.
    """
    if not fen_before or not user_move_san:
        return []

    try:
        board = chess.Board(fen_before)
    except Exception as e:
        logger.warning(f"[concept_dispatcher] FEN parse failed: {e}")
        return []

    try:
        from services.chess_brain.detector_registry import get_detector_registry
        registry = get_detector_registry()
    except Exception as e:
        logger.warning(f"[concept_dispatcher] detector registry import failed: {e}")
        return []

    ctx = context or {}
    try:
        tactical, strategic, behavioral = registry.run_all(
            board=board,
            user_move=user_move_san,
            best_move=best_move_san or "",
            context=ctx,
        )
    except Exception as e:
        logger.warning(f"[concept_dispatcher] detector run failed: {e}")
        return []

    # Tactical first (already priority-sorted), then strategic, then
    # behavioral. Behavioral is rarely the source of a caption — it's
    # meta (time trouble, tilt) and not what the player needs to see
    # in a "what would you play here?" card.
    out: List[Dict] = []
    for r in tactical + strategic + behavioral:
        if not r.detected:
            continue
        out.append({
            "pattern_type": r.pattern_type,
            "details": r.details or {},
            "teaching_hook": r.teaching_hook,
            "key_squares": r.key_squares or [],
            "confidence": r.confidence,
            "category": r.category,
        })
    return out


def pick_dominant_concept(detections: List[Dict]) -> Optional[Dict]:
    """Pick the highest-priority detection that ALSO has a caption
    template. If none has a template, return None — caller falls
    through to a generic caption.

    Detections are already priority-ordered (tactical first, sorted
    by detector priority). We walk the list and take the first one
    we can render.
    """
    for det in detections:
        if has_template(det.get("pattern_type")):
            return det
    return None


def caption_for_moment(
    *,
    fen_before: str,
    user_move_san: str,
    best_move_san: Optional[str] = None,
    context: Optional[Dict] = None,
) -> Tuple[Optional[str], Optional[Dict]]:
    """Run detectors → pick dominant → render caption.

    Returns (caption, metadata) where metadata describes which detector
    fired (for diagnostics/UI) or both None if no template-matched
    pattern was detected.
    """
    detections = detect_concepts(
        fen_before=fen_before,
        user_move_san=user_move_san,
        best_move_san=best_move_san,
        context=context,
    )
    dominant = pick_dominant_concept(detections)
    if not dominant:
        return None, None

    caption = render_caption(dominant["pattern_type"], dominant["details"])
    if not caption:
        return None, None

    return caption, {
        "pattern_type": dominant["pattern_type"],
        "category": dominant["category"],
        "key_squares": dominant["key_squares"],
        "confidence": dominant["confidence"],
    }
