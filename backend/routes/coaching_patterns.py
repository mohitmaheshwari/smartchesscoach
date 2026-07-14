"""coaching_patterns.py — Coaching pattern API endpoints.

Exposes all 5 coaching patterns:
1. Motif weaknesses (fork/pin/skewer/discovered/loose)
2. Phase accuracy (opening/middlegame/endgame)
3. Coordination gaps (NEW)
4. Prophylaxis gaps (NEW)
5. Opening deviations (NEW)

Used by Lab page to render 5 pattern cards + coaching surfaces.
"""

from fastapi import APIRouter, Depends
from services.player_profile_service import get_player_profile
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coaching-patterns", tags=["coaching-patterns"])


@router.get("/motif-weaknesses")
async def get_motif_weaknesses(
    user_id: str = None  # In real code, extract from JWT
) -> Dict:
    """
    Get user's motif weaknesses (fork/pin/skewer/discovered/loose).

    Returns: {
        "motifs": [
            {
                "motif": "fork",
                "weakness_count": 47,
                "recent_count": 2,
                "recovery_trend": 0.92,  # 0-1, higher = improving
                "accuracy": 0.85
            },
            ...
        ]
    }
    """
    try:
        # Get player's motif profile
        profile = await get_player_profile(user_id)

        if not profile or "motif_profile" not in profile:
            return {"motifs": []}

        motif_profile = profile["motif_profile"]

        motifs = []
        for motif_type in ["fork", "pin", "skewer", "discovered", "loose"]:
            motif_data = motif_profile.get(motif_type, {})

            if motif_data.get("weakness_count", 0) > 0:
                motifs.append({
                    "motif": motif_type,
                    "weakness_count": motif_data.get("weakness_count", 0),
                    "recent_count": motif_data.get("recent_count", 0),
                    "recovery_trend": motif_data.get("recovery_pct", 0.0),
                    "accuracy": motif_data.get("detection_accuracy", 0.85)
                })

        return {"motifs": motifs}

    except Exception as e:
        logger.error(f"Error fetching motif weaknesses for {user_id}: {e}")
        return {"motifs": []}


@router.get("/phase-accuracy")
async def get_phase_accuracy(user_id: str = None) -> Dict:
    """
    Get user's phase accuracy (opening/middlegame/endgame).

    Returns: {
        "opening": 82,
        "middlegame": 61,
        "endgame": 75,
        "weak_phase": "middlegame",
        "divergence_pct": 21
    }
    """
    try:
        # Get player profile with phase data
        profile = await get_player_profile(user_id)

        if not profile:
            return {}

        # Phase data stored in profile (populated during game analysis)
        phase_data = profile.get("phase_accuracy", {})

        return {
            "opening": phase_data.get("opening", 0),
            "middlegame": phase_data.get("middlegame", 0),
            "endgame": phase_data.get("endgame", 0),
            "weak_phase": phase_data.get("weak_phase", None),
            "divergence_pct": phase_data.get("divergence_pct", 0)
        }

    except Exception as e:
        logger.error(f"Error fetching phase accuracy for {user_id}: {e}")
        return {}


@router.get("/coordination-gap")
async def get_coordination_gap(user_id: str = None) -> Dict:
    """
    Get user's coordination gap status.

    Returns: {
        "has_gap": bool,
        "gap_type": "rook_isolation" | "piece_isolation" | None,
        "confidence": 0.75,
        "example_moves": 3
    }
    """
    try:
        profile = await get_player_profile(user_id)

        if not profile:
            return {"has_gap": False}

        coordination = profile.get("coordination_gap", {})

        return {
            "has_gap": coordination.get("has_gap", False),
            "gap_type": coordination.get("gap_type"),
            "confidence": coordination.get("confidence", 0.0),
            "example_moves": coordination.get("example_count", 0)
        }

    except Exception as e:
        logger.error(f"Error fetching coordination gap for {user_id}: {e}")
        return {"has_gap": False}


@router.get("/prophylaxis-gap")
async def get_prophylaxis_gap(user_id: str = None) -> Dict:
    """
    Get user's prophylaxis gap (reactive vs proactive thinking).

    Returns: {
        "has_gap": bool,
        "reactive_move_count": 12,
        "confidence": 0.70,
        "trend": "improving" | "stable" | "worsening"
    }
    """
    try:
        profile = await get_player_profile(user_id)

        if not profile:
            return {"has_gap": False}

        prophylaxis = profile.get("prophylaxis_gap", {})

        return {
            "has_gap": prophylaxis.get("has_gap", False),
            "reactive_move_count": prophylaxis.get("reactive_count", 0),
            "confidence": prophylaxis.get("confidence", 0.0),
            "trend": prophylaxis.get("trend", "unknown")
        }

    except Exception as e:
        logger.error(f"Error fetching prophylaxis gap for {user_id}: {e}")
        return {"has_gap": False}


@router.get("/opening-deviations")
async def get_opening_deviations(user_id: str = None) -> Dict:
    """
    Get user's opening deviations (detection only, no sound/unsound judgment yet).

    Returns: {
        "has_significant_deviation": bool,
        "deviation_openings": [
            {"opening": "Sicilian", "deviation_count": 5, "recent": 2},
            ...
        ]
    }
    """
    try:
        profile = await get_player_profile(user_id)

        if not profile:
            return {"has_significant_deviation": False}

        openings = profile.get("opening_deviations", {})

        deviation_list = []
        for opening_name, data in openings.items():
            if data.get("deviation_count", 0) >= 3:  # Meets gate threshold
                deviation_list.append({
                    "opening": opening_name,
                    "deviation_count": data.get("deviation_count", 0),
                    "recent": data.get("recent_count", 0)
                })

        return {
            "has_significant_deviation": len(deviation_list) > 0,
            "deviation_openings": deviation_list
        }

    except Exception as e:
        logger.error(f"Error fetching opening deviations for {user_id}: {e}")
        return {"has_significant_deviation": False}


@router.get("/all-patterns")
async def get_all_coaching_patterns(user_id: str = None) -> Dict:
    """
    Get all 5 coaching patterns in one call (used by Lab page).

    Returns: {
        "motifs": [...],
        "phase_accuracy": {...},
        "coordination": {...},
        "prophylaxis": {...},
        "openings": {...}
    }
    """
    return {
        "motifs": (await get_motif_weaknesses(user_id)).get("motifs", []),
        "phase_accuracy": await get_phase_accuracy(user_id),
        "coordination": await get_coordination_gap(user_id),
        "prophylaxis": await get_prophylaxis_gap(user_id),
        "openings": await get_opening_deviations(user_id)
    }
