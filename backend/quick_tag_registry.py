"""
Quick Tag Registry - Config-Driven Tag Generation
==================================================
Version: v1
All quick tags are defined in config with predicates.
This allows adding new tags without changing logic.
Tags are adapted by rating band.
"""

from typing import Dict, List, Optional
from reflect_constants import (
    QuickTagId, RatingBand, 
    get_rating_band, ADAPTIVE_DEFAULTS
)
from reflect_predicates import BoardFacts, evaluate_predicate
import logging

logger = logging.getLogger(__name__)


# ============================================
# TAG DEFINITIONS (config-driven)
# ============================================
# Each tag has:
# - tag_id: stable identifier
# - labels: by rating band (A/B/C vs D/E)
# - predicates: conditions to show (any=True, all=False)
# - priority: higher = more likely to show first
# - bands: which bands can see this tag

TAG_DEFINITIONS = {
    # === GENERAL TAGS ===
    QuickTagId.PLAYED_FAST: {
        "labels": {
            "default": "I played too fast",
            "advanced": "I moved quickly without full calculation",
        },
        "predicates": [],  # Always available as option
        "priority": 3,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": [],  # No specific category boost
    },
    
    QuickTagId.TIME_PRESSURE: {
        "labels": {
            "default": "Time pressure",
            "advanced": "Time pressure forced the decision",
        },
        "predicates": ["time_pressure_detected"],
        "priority": 5,  # High priority when detected
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": [],
    },
    
    QuickTagId.NOT_SURE: {
        "labels": {
            "default": "Not sure what to do",
            "advanced": "Unclear about best approach",
        },
        "predicates": [],  # Always available (neutral option)
        "priority": 1,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": [],
    },

    QuickTagId.NONE_OF_THESE: {
        "labels": {
            "default": "None of these",
            "advanced": "None of these",
        },
        "predicates": [],  # Honest escape when the coach's guesses do not fit
        "priority": 0,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": [],
    },
    
    # === THREAT-RELATED TAGS ===
    QuickTagId.MISSED_CHECK: {
        "labels": {
            "default": "I didn't see the check",
            "advanced": "I missed the check threat",
        },
        "predicates": ["opponent_has_immediate_check"],
        "priority": 8,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["ignored_opponent_forcing", "missed_forcing_move"],
    },
    
    QuickTagId.MISSED_CAPTURE: {
        "labels": {
            "default": "I missed a capture threat",
            "advanced": "I overlooked the capture",
        },
        "predicates": ["opponent_has_winning_capture"],
        "priority": 7,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["ignored_opponent_forcing"],
    },
    
    QuickTagId.MISSED_THREAT: {
        "labels": {
            "default": "I missed a threat",
            "advanced": "I underestimated opponent's threat",
        },
        "predicates": ["user_ignored_forcing_reply"],
        "priority": 6,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["ignored_opponent_forcing", "critical_moment_drift"],
    },
    
    QuickTagId.THOUGHT_HAD_TIME: {
        "labels": {
            "default": "I thought I had time",
            "advanced": "I misjudged the tempo",
        },
        "predicates": ["user_ignored_forcing_reply"],
        "priority": 5,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["ignored_opponent_forcing"],
    },
    
    # === PIECE SAFETY TAGS ===
    QuickTagId.THOUGHT_PIECE_SAFE: {
        "labels": {
            "default": "I thought my piece was safe",
            "advanced": "I miscalculated the piece safety",
        },
        "predicates": ["user_piece_left_hanging"],
        "priority": 7,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["missed_forcing_move"],
    },
    
    QuickTagId.THOUGHT_PROTECTED: {
        "labels": {
            "default": "I thought it was protected",
            "advanced": "I miscounted defenders",
        },
        "predicates": ["user_piece_left_hanging"],
        "priority": 6,
        "bands": ["B", "C", "D", "E"],  # Not for beginners (too technical)
        "category_boost": ["missed_forcing_move"],
    },
    
    # === ATTACK/DEFENSE TAGS ===
    QuickTagId.CHOSE_ATTACK_OVER_SAFETY: {
        "labels": {
            "default": "I chose to attack instead of being safe",
            "advanced": "I prioritized attack over defense",
        },
        "predicates": ["user_attacked_instead_of_defending"],
        "priority": 6,
        "bands": ["B", "C", "D", "E"],
        "category_boost": ["ignored_opponent_forcing", "advantage_mismanagement"],
    },
    
    QuickTagId.ATTACKED_IGNORED_THREAT: {
        "labels": {
            "default": "I attacked and ignored his threat",
            "advanced": "I attacked while ignoring counterplay",
        },
        "predicates": ["user_attacked_instead_of_defending"],
        "priority": 7,
        "bands": ["B", "C", "D", "E"],
        "category_boost": ["ignored_opponent_forcing"],
    },
    
    QuickTagId.DEFENDED_NON_THREAT: {
        "labels": {
            "default": "I defended something that wasn't threatened",
            "advanced": "I overreacted to a non-threat",
        },
        "predicates": ["user_defended_phantom_threat"],
        "priority": 6,
        "bands": ["B", "C", "D", "E"],
        "category_boost": ["phantom_threat"],
    },
    
    # === POSITION EVALUATION TAGS ===
    QuickTagId.THOUGHT_WINNING: {
        "labels": {
            "default": "I thought I was winning",
            "advanced": "I overestimated my position",
        },
        "predicates": [],  # User self-reports this
        "priority": 4,
        "bands": ["B", "C", "D", "E"],
        "category_boost": ["advantage_mismanagement"],
    },
    
    QuickTagId.FELT_DANGER: {
        "labels": {
            "default": "I felt danger and reacted fast",
            "advanced": "I sensed danger and moved quickly",
        },
        "predicates": [],
        "priority": 4,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["phantom_threat", "critical_moment_drift"],
    },
    
    QuickTagId.WANTED_TO_FINISH: {
        "labels": {
            "default": "I wanted to finish quickly",
            "advanced": "I tried to force a quick finish",
        },
        "predicates": [],
        "priority": 4,
        "bands": ["B", "C", "D", "E"],
        "category_boost": ["advantage_mismanagement"],
    },
    
    # === OPENING TAGS ===
    QuickTagId.FOLLOWING_OPENING: {
        "labels": {
            "default": "I was following opening idea",
            "advanced": "I was following opening principles",
        },
        "predicates": ["is_opening_phase"],
        "priority": 5,
        "bands": ["A", "B", "C", "D", "E"],
        "category_boost": ["structural_misjudgment"],
    },
    
    # === ADVANCED TAGS (Band D/E only) ===
    QuickTagId.UNDERESTIMATED_COUNTERPLAY: {
        "labels": {
            "default": "I underestimated counterplay",
            "advanced": "I underestimated opponent's counterplay",
        },
        "predicates": ["user_ignored_forcing_reply"],
        "priority": 6,
        "bands": ["D", "E"],
        "category_boost": ["advantage_mismanagement", "critical_moment_drift"],
    },
    
    QuickTagId.RUSHED_CONVERSION: {
        "labels": {
            "default": "I rushed the conversion",
            "advanced": "I was impatient in the conversion",
        },
        "predicates": [],
        "priority": 5,
        "bands": ["D", "E"],
        "category_boost": ["advantage_mismanagement"],
    },
    
    QuickTagId.IGNORED_FORCING_SEQUENCE: {
        "labels": {
            "default": "I ignored forcing sequence",
            "advanced": "I missed the forcing continuation",
        },
        "predicates": ["simple_tactic_missed"],
        "priority": 7,
        "bands": ["D", "E"],
        "category_boost": ["missed_forcing_move"],
    },
    
    QuickTagId.CHOSE_ACTIVITY_OVER_SAFETY: {
        "labels": {
            "default": "I chose activity over safety",
            "advanced": "I prioritized piece activity over king safety",
        },
        "predicates": ["user_attacked_instead_of_defending"],
        "priority": 5,
        "bands": ["D", "E"],
        "category_boost": ["ignored_opponent_forcing", "advantage_mismanagement"],
    },
}


# ============================================
# CATEGORY-TO-TAG MAPPING (base tags by mistake category)
# ============================================
CATEGORY_BASE_TAGS = {
    "ignored_opponent_forcing": [
        QuickTagId.MISSED_THREAT,
        QuickTagId.MISSED_CHECK,
        QuickTagId.MISSED_CAPTURE,
        QuickTagId.THOUGHT_HAD_TIME,
        QuickTagId.ATTACKED_IGNORED_THREAT,
    ],
    "missed_forcing_move": [
        QuickTagId.THOUGHT_PIECE_SAFE,
        QuickTagId.THOUGHT_PROTECTED,
        QuickTagId.IGNORED_FORCING_SEQUENCE,
    ],
    "phantom_threat": [
        QuickTagId.DEFENDED_NON_THREAT,
        QuickTagId.FELT_DANGER,
    ],
    "advantage_mismanagement": [
        QuickTagId.WANTED_TO_FINISH,
        QuickTagId.THOUGHT_WINNING,
        QuickTagId.RUSHED_CONVERSION,
        QuickTagId.CHOSE_ATTACK_OVER_SAFETY,
    ],
    "critical_moment_drift": [
        QuickTagId.PLAYED_FAST,
        QuickTagId.MISSED_THREAT,
        QuickTagId.FELT_DANGER,
    ],
    "structural_misjudgment": [
        QuickTagId.FOLLOWING_OPENING,
        QuickTagId.NOT_SURE,
    ],
}


class QuickTagEngine:
    """
    Engine for generating contextual quick tags.
    Deterministic, config-driven, rating-adaptive.
    """
    
    def __init__(self, rating: int, stability_band: str = "moderate"):
        self.rating = rating
        self.rating_band = get_rating_band(rating)
        self.stability_band = stability_band
        self.adaptive_config = ADAPTIVE_DEFAULTS.get(
            self.rating_band, 
            ADAPTIVE_DEFAULTS[RatingBand.BAND_C]
        )
    
    def generate_tags(
        self,
        facts: BoardFacts,
        mistake_category: str,
        *,
        include_honest_escapes: bool = False,
    ) -> Dict:
        """
        Generate quick tags for a reflection moment.
        
        Returns:
            {
                "tags": [{"id": "...", "label": "...", "priority": N}, ...],
                "shown_tag_ids": ["...", ...],  # For analytics
                "max_selections": N,
                "neutral_option_id": "not_sure"
            }
        """
        candidate_tags = []
        
        # 1. Get base tags for this mistake category
        base_tag_ids = CATEGORY_BASE_TAGS.get(mistake_category, [])
        
        # 2. Evaluate all tags
        for tag_id, definition in TAG_DEFINITIONS.items():
            # Preserve the shipped V1 response exactly. The second honest
            # escape belongs to the default-off event-reflection contract.
            if tag_id == QuickTagId.NONE_OF_THESE and not include_honest_escapes:
                continue
            # Check if this band can see this tag
            if self.rating_band.value not in definition["bands"]:
                continue
            
            # Calculate priority
            priority = definition["priority"]
            
            # Boost if tag is relevant to this category
            if tag_id in base_tag_ids:
                priority += 3
            
            if mistake_category in definition.get("category_boost", []):
                priority += 2
            
            # Check predicates (any match = show tag)
            predicates = definition["predicates"]
            predicate_match = len(predicates) == 0  # No predicates = always show
            
            for pred_name in predicates:
                if evaluate_predicate(pred_name, facts):
                    predicate_match = True
                    priority += 2  # Boost priority if predicate matched
                    break
            
            # For category-specific tags, only show if predicate matches or is base tag
            if tag_id not in base_tag_ids and predicates and not predicate_match:
                continue
            
            # Get label based on rating band
            if self.adaptive_config.get("show_advanced_labels", False):
                label = definition["labels"].get("advanced", definition["labels"]["default"])
            else:
                label = definition["labels"]["default"]
            
            candidate_tags.append({
                "id": tag_id.value,
                "label": label,
                "priority": priority,
                "predicate_match": predicate_match,
            })
        
        # 3. Sort by priority (descending)
        candidate_tags.sort(key=lambda x: x["priority"], reverse=True)
        
        # 4. Limit to max tags for this band
        max_tags = self.adaptive_config.get("max_quick_tags", 5)
        final_tags = candidate_tags[:max_tags]
        
        if not include_honest_escapes:
            # Original V1 logic, intentionally unchanged for flag-off parity.
            neutral_present = any(
                t["id"] == QuickTagId.NOT_SURE.value for t in final_tags
            )
            if not neutral_present and len(final_tags) >= max_tags:
                final_tags[-1] = {
                    "id": QuickTagId.NOT_SURE.value,
                    "label": TAG_DEFINITIONS[QuickTagId.NOT_SURE]["labels"]["default"],
                    "priority": 1,
                    "predicate_match": True,
                }
            elif not neutral_present:
                final_tags.append({
                    "id": QuickTagId.NOT_SURE.value,
                    "label": TAG_DEFINITIONS[QuickTagId.NOT_SURE]["labels"]["default"],
                    "priority": 1,
                    "predicate_match": True,
                })
        else:
            # "Not sure" means the player cannot explain the move; "None
            # of these" means the coach's candidate explanations did not
            # fit. They are different evidence.
            required_escape_ids = (
                QuickTagId.NOT_SURE,
                QuickTagId.NONE_OF_THESE,
            )
            for required_id in required_escape_ids:
                if any(t["id"] == required_id.value for t in final_tags):
                    continue
                definition = TAG_DEFINITIONS[required_id]
                advanced = self.adaptive_config.get("show_advanced_labels", False)
                escape_tag = {
                    "id": required_id.value,
                    "label": definition["labels"]["advanced" if advanced else "default"],
                    "priority": definition["priority"],
                    "predicate_match": True,
                }
                if len(final_tags) < max_tags:
                    final_tags.append(escape_tag)
                    continue
                required_values = {item.value for item in required_escape_ids}
                replace_at = next(
                    (
                        index
                        for index in range(len(final_tags) - 1, -1, -1)
                        if final_tags[index]["id"] not in required_values
                    ),
                    None,
                )
                if replace_at is None:
                    raise RuntimeError("max_quick_tags cannot hold required escape options")
                final_tags[replace_at] = escape_tag
        
        # Clean output for frontend
        output_tags = [
            {"id": t["id"], "label": t["label"], "priority": t["priority"]}
            for t in final_tags
        ]
        
        result = {
            "tags": output_tags,
            "shown_tag_ids": [t["id"] for t in output_tags],
            "max_selections": 3,  # Max tags user can select
            "neutral_option_id": QuickTagId.NOT_SURE.value,
        }
        if include_honest_escapes:
            result["escape_option_ids"] = [
                QuickTagId.NOT_SURE.value,
                QuickTagId.NONE_OF_THESE.value,
            ]
        return result


def generate_quick_tags(
    fen_before: str,
    user_move: str,
    best_move: str,
    mistake_category: str,
    rating: int,
    cp_loss: float = 0,
    time_remaining_sec: Optional[int] = None,
    move_number: int = 0,
    *,
    include_honest_escapes: bool = False,
) -> Dict:
    """
    Main entry point for quick tag generation.
    Called by reflect endpoints.
    """
    # Build board facts
    facts = BoardFacts(
        fen_before=fen_before,
        user_move=user_move,
        best_move=best_move,
        cp_loss=cp_loss,
        time_remaining_sec=time_remaining_sec,
        move_number=move_number,
    )
    
    # Generate tags
    engine = QuickTagEngine(rating=rating)
    return engine.generate_tags(
        facts,
        mistake_category,
        include_honest_escapes=include_honest_escapes,
    )
